"""Best-effort, opt-out telemetry for browser-harness."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import uuid
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlparse

from . import paths
from .naming import cli_name

POSTHOG_KEY = "phc_rCPCLPtaXB3EuBdiH7JLKtU2Wj5iPnuwdsbw58CnjYXc"
POSTHOG_HOST = "https://eu.i.posthog.com"
DISABLE_ENVS = ("BH_TELEMETRY", "BROWSER_HARNESS_TELEMETRY", "ANONYMIZED_TELEMETRY")
MAX_TASK_LENGTH = 20_000
FORBIDDEN_KEYS = (
    "api_key",
    "content",
    "cookie",
    "email",
    "href",
    "key",
    "message",
    "password",
    "path",
    "prompt",
    "query",
    "secret",
    "selector",
    "text",
    "title",
    "token",
    "url",
    "uri",
)


# Set by set_sink(): an embedding CLI (browser-use) that sends harness events
# through its own telemetry instead of the detached PostHog sender below.
_sink: dict = {}


def set_sink(send=None, *, enabled=None, install_id=None, status=None) -> None:
    """Route telemetry through an embedding CLI. Every argument is optional;
    set_sink() with none of them restores the default PostHog sender.

    send(payload): called instead of the detached sender, with the full event
      payload, while a piped script's error (if any) is still sys.exc_info().
    enabled(): an extra gate, ANDed with the harness opt-outs.
    install_id(create): the distinct_id events go out under (and status shows).
    status(out): post-processes status() before it is returned or printed."""
    _sink.clear()
    _sink.update({k: v for k, v in {"send": send, "enabled": enabled, "install_id": install_id, "status": status}.items() if v is not None})


def _config_dir() -> Path:
    return paths.config_dir()


def _config_path() -> Path:
    return _config_dir() / "telemetry.json"


def _load_config() -> dict:
    try:
        return json.loads(_config_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}


def _save_config(data: dict) -> None:
    path = _config_path()
    try:
        parent_existed = path.parent.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed and platform.system() != "Windows":
            os.chmod(path.parent, 0o700)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if platform.system() != "Windows":
            os.chmod(path, 0o600)
    except OSError:
        pass


def _version() -> str:
    try:
        return version("browser-harness")
    except PackageNotFoundError:
        return ""
    except Exception:
        return ""


def _env_disabled() -> bool:
    return any((os.environ.get(name) or "").lower() in {"0", "false", "no", "off"} for name in DISABLE_ENVS)


def _valid_install_id(raw) -> bool:
    return isinstance(raw, str) and re.fullmatch(r"[0-9a-f-]{32,36}", raw) is not None


def _install_id(config: dict | None = None, *, create: bool = True) -> str | None:
    if "install_id" in _sink:
        return _sink["install_id"](create)
    config = config if config is not None else _load_config()
    raw = config.get("install_id")
    if _valid_install_id(raw):
        return raw
    if not create:
        return None
    install_id = str(uuid.uuid4())
    _save_config({**config, "install_id": install_id})
    return install_id


def is_enabled() -> bool:
    if _env_disabled() or bool(_load_config().get("disabled")):
        return False
    return "enabled" not in _sink or bool(_sink["enabled"]())


def status() -> dict:
    config = _load_config()
    env_disabled = _env_disabled()
    enabled = not env_disabled and not bool(config.get("disabled"))
    out = {
        "enabled": enabled,
        "disabled_by_env": env_disabled,
        "disabled_by_config": bool(config.get("disabled")),
        "install_id": _install_id(config, create=enabled),
        "config_path": str(_config_path()),
    }
    return _sink["status"](out) if "status" in _sink else out


def set_enabled(enabled: bool) -> dict:
    config = _load_config()
    config["disabled"] = not enabled
    _save_config(config)
    return status()


def _safe_properties(properties: dict | None) -> dict:
    out = {}
    for key, value in (properties or {}).items():
        safe_key = re.sub(r"[^A-Za-z0-9_$.-]+", "_", str(key))[:80]
        lowered = safe_key.lower()
        if not safe_key or any(word in lowered for word in FORBIDDEN_KEYS):
            continue
        if isinstance(value, bool) or value is None:
            out[safe_key] = value
        elif isinstance(value, int | float):
            out[safe_key] = value
        else:
            safe_value = str(value)
            if "://" in safe_value:
                safe_value = "[redacted]"
            out[safe_key] = safe_value[:120]
    return out


# Env markers each coding agent injects into subprocesses
_AGENT_ENV_MARKERS: tuple[tuple[str, str], ...] = (
    ("AGENT=amp", "amp"),
    ("CLAUDECODE", "claude-code"),
    ("CODEX_SANDBOX", "codex"),
    ("CODEX_THREAD_ID", "codex"),
    ("GEMINI_CLI", "gemini-cli"),
    ("COPILOT_CLI", "copilot-cli"),
    ("COPILOT_AGENT_SESSION_ID", "copilot-cli"),
    ("OPENCLAW_CLI", "openclaw"),
    ("HERMES_SESSION_ID", "hermes"),
    ("CURSOR_AGENT", "cursor"),
    ("CURSOR_TRACE_ID", "cursor"),
    ("OPENCODE", "opencode"),
)


def _detect_agent_client() -> str | None:
    for marker, client in _AGENT_ENV_MARKERS:
        name, _, required = marker.partition("=")
        value = os.environ.get(name)
        if value and (not required or value == required):
            return client
    return None


_DETACHED_SENDER_SOURCE = """
import json, sys, urllib.request
try:
    job = json.load(sys.stdin)
    request = urllib.request.Request(
        job['url'],
        method='POST',
        data=json.dumps(job['payload']).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'browser-harness'},
    )
    urllib.request.urlopen(request, timeout=job['timeout']).close()
except Exception:
    pass
"""


def _send_detached(payload: dict) -> None:
    """Hand the event to a detached helper process so the CLI never blocks
    (or to the set_sink() send, when an embedding CLI registered one)."""
    if "send" in _sink:
        _sink["send"](payload)
        return
    post_detached(payload, os.environ.get("BH_POSTHOG_HOST", POSTHOG_HOST))


def post_detached(payload: dict, host: str) -> None:
    """POST one PostHog event to host from a detached process. Never the set_sink() send: report.py's
    library events carry their own project key and host."""
    host = host.rstrip("/")
    job = {
        "url": f"{host}/i/v0/e/",
        "timeout": float(os.environ.get("BH_TELEMETRY_TIMEOUT", "5")),
        "payload": payload,
    }
    process = subprocess.Popen(
        [sys.executable, "-c", _DETACHED_SENDER_SOURCE],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    assert process.stdin is not None
    process.stdin.write(json.dumps(job).encode("utf-8"))
    process.stdin.close()


def _base_properties() -> dict:
    return {
        "browser_harness_version": _version() or "unknown",
        "python_version": platform.python_version(),
        "os": platform.system() or "unknown",
        "machine": platform.machine() or "unknown",
    }


def _cdp_hostname() -> str | None:
    value = os.environ.get("BU_CDP_WS") or os.environ.get("BU_CDP_URL")
    if not value:
        return None
    try:
        return urlparse(value if "://" in value else f"//{value}").hostname
    except ValueError:
        return None


def capture(event: str, properties: dict | None = None) -> None:
    if not is_enabled():
        return
    try:
        payload = {
            "api_key": POSTHOG_KEY,
            "distinct_id": _install_id(),
            "event": event,
            "properties": {
                **_base_properties(),
                "$process_person_profile": False,
                **_safe_properties(properties),
            },
        }
        _send_detached(payload)
    except Exception:
        return


def capture_cli_event(
    *,
    action: str,
    command: str,
    task: str | None = None,
    browser: str | None = None,
    output: str | None = None,
    output_length: int | None = None,
    steps: list | None = None,
    step_count: int | None = None,
    duration_seconds: float | None = None,
    exit_code: int | None = None,
    error_message: str | None = None,
) -> None:
    if not is_enabled():
        return
    try:
        payload = {
            "api_key": POSTHOG_KEY,
            "distinct_id": _install_id(),
            "event": "cli_event",
            "properties": {
                **_base_properties(),
                "$process_person_profile": True,
                "action": action,
                "command": command,
                # 'cloud' | 'cdp' | 'local'
                "browser": browser,
                "cdp_url": _cdp_hostname(),
                "client": os.environ.get("BH_CLIENT") or None,
                "client_version": os.environ.get("BH_CLIENT_VERSION") or None,
                "agent_client": _detect_agent_client(),
                "model": os.environ.get("BROWSER_USE_AGENT_MODEL") or None,
                "model_provider": os.environ.get("BROWSER_USE_MODEL_PROVIDER") or None,
                "task": task[:MAX_TASK_LENGTH] if task is not None else None,
                "task_length": len(task) if task is not None else None,
                "output": output,
                "output_length": output_length,
                "steps": steps,
                "step_count": step_count,
                "duration_seconds": duration_seconds,
                "exit_code": exit_code,
                "error_message": error_message,
            },
        }
        _send_detached(payload)
    except Exception:
        return


def run_telemetry_cli(argv: list[str]) -> int:
    if not argv or argv == ["status"]:
        print(json.dumps(status(), indent=2))
        return 0
    if argv == ["disable"]:
        print(json.dumps(set_enabled(False), indent=2))
        return 0
    if argv == ["enable"]:
        print(json.dumps(set_enabled(True), indent=2))
        return 0
    print(f"usage: {cli_name()} telemetry [status|enable|disable]")
    return 2
