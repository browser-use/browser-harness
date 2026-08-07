"""Browser Use Cloud auth for browser-harness.

The model-facing contract stays small: cloud browser startup either has a key
or tells the agent to run `browser-harness auth login`. OAuth details live here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from . import paths


AUTH_BASE = "https://api.browser-use.com"
# Browser Use currently exposes this registered CLI OAuth client. Keep an env
# escape hatch so a dedicated browser-harness client can be used once issued.
DEFAULT_CLIENT_ID = "browser-use-terminal"
CALLBACK_PATH = "/browser-use-cloud/callback"
AUTH_TIMEOUT_SECONDS = 600


class CloudAuthRequired(RuntimeError):
    def __init__(self):
        super().__init__("cloud-auth-required: run `browser-harness auth login`")


class AuthError(RuntimeError):
    pass


@dataclass
class PendingCallback:
    state: str
    code: str | None = None
    error: str | None = None
    error_description: str | None = None
    complete: bool = False


@dataclass
class BrowserAuthStart:
    server: HTTPServer
    callback: PendingCallback
    redirect_uri: str
    verifier: str
    auth_url: str
    expires_in: int | None
    opened: bool = False


@dataclass
class DeviceAuthStart:
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str | None = None
    expires_in: int | None = None
    interval: int = 5
    opened: bool = False

    @property
    def open_uri(self) -> str:
        return self.verification_uri_complete or self.verification_uri


@dataclass
class AuthRecord:
    api_key: str
    api_key_id: str | None = None
    project_id: str | None = None
    expires_at: str | None = None
    scopes: list[str] = field(default_factory=list)
    source: str = "oauth"

    @classmethod
    def from_token_response(cls, data: dict, *, source: str = "oauth") -> "AuthRecord":
        api_key = data.get("api_key")
        if not api_key:
            raise AuthError("auth token response did not include an api_key")
        scopes = data.get("scopes") or []
        if not isinstance(scopes, list):
            scopes = []
        return cls(
            api_key=api_key,
            api_key_id=data.get("api_key_id"),
            project_id=data.get("project_id"),
            expires_at=data.get("expires_at"),
            scopes=[str(s) for s in scopes],
            source=source,
        )

    def to_storage(self) -> dict:
        return {
            "api_key": self.api_key,
            "api_key_id": self.api_key_id,
            "project_id": self.project_id,
            "expires_at": self.expires_at,
            "scopes": self.scopes,
            "source": self.source,
        }


def auth_base() -> str:
    return (os.environ.get("BROWSER_USE_CLOUD_API_URL") or AUTH_BASE).rstrip("/")


def client_id() -> str:
    return os.environ.get("BROWSER_HARNESS_OAUTH_CLIENT_ID") or DEFAULT_CLIENT_ID


def auth_path() -> Path:
    override = os.environ.get("BH_AUTH_PATH")
    if override:
        return Path(override).expanduser()
    return paths.config_dir() / "auth.json"


def load_auth_file(path: Path | None = None) -> dict:
    path = path or auth_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise AuthError(f"auth file is not valid JSON: {path}") from e


def save_auth_record(record: AuthRecord, path: Path | None = None) -> None:
    path = path or auth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _chmod_private(path.parent, directory=True)
    existing = load_auth_file(path)
    existing["browser_use"] = record.to_storage()
    tmp = path.with_name(path.name + ".tmp")
    _write_private_json(tmp, existing)
    os.replace(tmp, path)
    _chmod_private(path)


def clear_auth(path: Path | None = None) -> bool:
    path = path or auth_path()
    data = load_auth_file(path)
    existed = bool(data.get("browser_use"))
    data.pop("browser_use", None)
    if data:
        tmp = path.with_name(path.name + ".tmp")
        _write_private_json(tmp, data)
        os.replace(tmp, path)
        _chmod_private(path)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return existed


def stored_auth_record(path: Path | None = None) -> dict | None:
    data = load_auth_file(path)
    value = data.get("browser_use")
    return value if isinstance(value, dict) else None


def get_browser_use_api_key() -> str:
    env_key = os.environ.get("BROWSER_USE_API_KEY")
    if env_key:
        return env_key
    stored = stored_auth_record()
    key = stored.get("api_key") if stored else None
    if key:
        return str(key)
    raise CloudAuthRequired()


def auth_status() -> dict:
    if os.environ.get("BROWSER_USE_API_KEY"):
        return {"status": "authenticated", "source": "env", "path": str(auth_path())}
    stored = stored_auth_record()
    if not stored or not stored.get("api_key"):
        return {"status": "missing", "source": None, "path": str(auth_path())}
    return {"status": "authenticated", "source": "stored", "path": str(auth_path())}


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def start_browser_auth(*, open_url=True, timeout=AUTH_TIMEOUT_SECONDS) -> BrowserAuthStart:
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(32)
    callback = PendingCallback(state=state)
    server = _callback_server(callback)
    host, port = server.server_address
    redirect_uri = f"http://{host}:{port}{CALLBACK_PATH}"
    req = {
        "client_id": client_id(),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "device_name": os.environ.get("BH_DEVICE_NAME") or "browser-harness",
    }
    try:
        data = _post_json(f"{auth_base()}/cloud/cli-auth/browser", req)
    except BaseException:
        server.server_close()
        raise
    auth_url = data.get("authorization_uri") or data.get("auth_url")
    if not auth_url:
        server.server_close()
        raise AuthError("auth start response did not include authorization_uri")
    expires_in = _int_or_none(data.get("expires_in"))
    opened = False
    if open_url:
        try:
            opened = bool(webbrowser.open(auth_url))
        except Exception:
            opened = False
    return BrowserAuthStart(
        server=server,
        callback=callback,
        redirect_uri=redirect_uri,
        verifier=verifier,
        auth_url=auth_url,
        expires_in=expires_in,
        opened=opened,
    )


def complete_browser_auth(start: BrowserAuthStart, *, timeout=AUTH_TIMEOUT_SECONDS) -> AuthRecord:
    deadline = time.time() + timeout
    start.server.timeout = 0.5
    try:
        while not start.callback.complete and time.time() < deadline:
            start.server.handle_request()
    finally:
        start.server.server_close()
    if not start.callback.complete:
        raise AuthError("timed out waiting for browser auth callback")
    if start.callback.error:
        detail = f": {start.callback.error_description}" if start.callback.error_description else ""
        raise AuthError(f"auth failed: {start.callback.error}{detail}")
    if not start.callback.code:
        raise AuthError("auth callback did not include a code")
    token = _exchange_authorization_code(start.callback.code, start.redirect_uri, start.verifier)
    record = AuthRecord.from_token_response(token)
    save_auth_record(record)
    return record


def browser_login(*, open_url=True, json_output=False, timeout=AUTH_TIMEOUT_SECONDS) -> AuthRecord:
    start = start_browser_auth(open_url=open_url, timeout=timeout)
    if json_output:
        print(json.dumps({
            "status": "needs_user_auth",
            "auth_url": start.auth_url,
            "callback": start.redirect_uri,
            "expires_in": start.expires_in,
            "opened": start.opened,
        }), flush=True)
    else:
        print("Open this URL to sign in to Browser Use Cloud:")
        print(start.auth_url, flush=True)
        if start.opened:
            print("Waiting for login to complete...", flush=True)
        else:
            print("Waiting for login to complete after you open the URL...", flush=True)
    record = complete_browser_auth(start, timeout=timeout)
    if json_output:
        print(json.dumps(_stored_success_output()), flush=True)
    else:
        print("Browser Use Cloud auth stored.")
    return record


def start_device_auth(*, open_url=True) -> DeviceAuthStart:
    data = _post_json(
        f"{auth_base()}/cloud/cli-auth/device",
        {"client_id": client_id(), "device_name": os.environ.get("BH_DEVICE_NAME") or "browser-harness"},
    )
    device_code = data.get("device_code")
    user_code = data.get("user_code")
    verification_uri = data.get("verification_uri") or data.get("verification_url")
    if not device_code or not user_code or not verification_uri:
        raise AuthError("device auth response missing device_code, user_code, or verification_uri")
    opened = False
    open_uri = data.get("verification_uri_complete") or verification_uri
    if open_url:
        try:
            opened = bool(webbrowser.open(open_uri))
        except Exception:
            opened = False
    return DeviceAuthStart(
        device_code=device_code,
        user_code=user_code,
        verification_uri=verification_uri,
        verification_uri_complete=data.get("verification_uri_complete"),
        expires_in=_int_or_none(data.get("expires_in")),
        interval=max(1, _int_or_none(data.get("interval")) or 5),
        opened=opened,
    )


def complete_device_auth(start: DeviceAuthStart, *, timeout: int | None = None) -> AuthRecord:
    deadline = time.time() + (timeout or start.expires_in or AUTH_TIMEOUT_SECONDS)
    interval = start.interval
    while time.time() < deadline:
        try:
            token = _post_json(f"{auth_base()}/cloud/cli-auth/token", {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": start.device_code,
                "client_id": client_id(),
            })
            record = AuthRecord.from_token_response(token)
            save_auth_record(record)
            return record
        except AuthError as e:
            err = _auth_error_code(str(e))
            if err == "authorization_pending":
                time.sleep(interval)
                continue
            if err == "slow_down":
                interval += 5
                time.sleep(interval)
                continue
            raise
    raise AuthError("timed out waiting for device auth")


def device_login(*, open_url=True, json_output=False) -> AuthRecord:
    start = start_device_auth(open_url=open_url)
    if json_output:
        print(json.dumps({
            "status": "needs_user_auth",
            "verification_uri": start.verification_uri,
            "verification_uri_complete": start.verification_uri_complete,
            "user_code": start.user_code,
            "expires_in": start.expires_in,
            "opened": start.opened,
        }), flush=True)
    else:
        print("Open this URL to sign in to Browser Use Cloud:")
        print(start.open_uri, flush=True)
        print(f"Code: {start.user_code}", flush=True)
        print("Waiting for login to complete...", flush=True)
    record = complete_device_auth(start)
    if json_output:
        print(json.dumps(_stored_success_output()), flush=True)
    else:
        print("Browser Use Cloud auth stored.")
    return record


def api_key_stdin_login(*, json_output=False, input_stream=None) -> AuthRecord:
    key = _read_manual_api_key(input_stream)
    record = AuthRecord(api_key=key, source="manual")
    save_auth_record(record)
    if json_output:
        print(json.dumps(_stored_success_output()), flush=True)
    else:
        print("Browser Use Cloud API key stored.")
    return record


def _exchange_authorization_code(code: str, redirect_uri: str, verifier: str) -> dict:
    return _post_json(f"{auth_base()}/cloud/cli-auth/token", {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
        "client_id": client_id(),
    })


def _callback_server(callback: PendingCallback) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler API
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != CALLBACK_PATH:
                self.send_error(404)
                return
            qs = urllib.parse.parse_qs(parsed.query)
            state = _one(qs, "state")
            if state != callback.state:
                callback.error = "invalid_state"
                callback.error_description = "OAuth callback state did not match"
            else:
                callback.code = _one(qs, "code")
                callback.error = _one(qs, "error")
                callback.error_description = _one(qs, "error_description")
            callback.complete = True
            body = b"<html><body><h1>Browser Use Cloud login complete</h1><p>You can close this tab.</p></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    return HTTPServer(("127.0.0.1", 0), Handler)


def _post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read() or b""
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            data = {}
        err = data.get("error") or data.get("state") or f"http_{e.code}"
        desc = data.get("error_description") or data.get("reason") or data.get("message")
        detail = f": {desc}" if desc else ""
        raise AuthError(f"{err}{detail}") from e
    except urllib.error.URLError as e:
        raise AuthError(f"network error: {e.reason}") from e


def _read_manual_api_key(input_stream=None) -> str:
    stream = input_stream or sys.stdin
    if hasattr(stream, "isatty") and stream.isatty():
        try:
            key = getpass.getpass("Browser Use API key: ")
        except EOFError as e:
            raise AuthError("no API key provided") from e
    else:
        key = stream.read()
    key = (key or "").strip()
    if not key:
        raise AuthError("no API key provided")
    if len(key) < 20:
        raise AuthError("API key looks too short")
    return key


def _write_private_json(path: Path, data: dict) -> None:
    raw = (json.dumps(data, indent=2) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _chmod_private(path: Path, *, directory=False) -> None:
    mode = stat.S_IRWXU if directory else stat.S_IRUSR | stat.S_IWUSR
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _one(qs: dict[str, list[str]], key: str) -> str | None:
    values = qs.get(key)
    return values[0] if values else None


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _auth_error_code(message: str) -> str:
    return message.split(":", 1)[0]


def _stored_success_output() -> dict:
    return {"status": "stored", "path": str(auth_path())}


def run_auth_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="browser-harness auth")
    sub = parser.add_subparsers(dest="command", required=True)
    login = sub.add_parser("login")
    login_mode = login.add_mutually_exclusive_group()
    login_mode.add_argument("--device-code", action="store_true")
    login_mode.add_argument("--api-key-stdin", action="store_true")
    login.add_argument("--json", action="store_true")
    login.add_argument("--no-open", action="store_true")
    sub.add_parser("status")
    sub.add_parser("logout")
    args = parser.parse_args(argv)

    try:
        if args.command == "login":
            if args.api_key_stdin:
                api_key_stdin_login(json_output=args.json)
            elif args.device_code:
                device_login(open_url=not args.no_open, json_output=args.json)
            else:
                browser_login(open_url=not args.no_open, json_output=args.json)
            return 0
        if args.command == "status":
            print(json.dumps(auth_status(), indent=2))
            return 0
        if args.command == "logout":
            removed = clear_auth()
            print(json.dumps({"status": "logged-out" if removed else "missing", "path": str(auth_path())}, indent=2))
            return 0
    except (AuthError, CloudAuthRequired) as e:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "reason": str(e)}), file=sys.stderr)
        else:
            print(str(e), file=sys.stderr)
        return 1
    return 2
