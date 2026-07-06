"""Best-effort, opt-out telemetry for browser-harness.

Only low-cardinality operational events are sent. Callers should pass categories,
states, and booleans, never URLs, selectors, page text, prompts, or credentials.
"""

from __future__ import annotations

import json
import os
import platform
import re
import urllib.request
import uuid
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from . import paths


POSTHOG_KEY = "phc_rCPCLPtaXB3EuBdiH7JLKtU2Wj5iPnuwdsbw58CnjYXc"
POSTHOG_HOST = "https://eu.i.posthog.com"
DISABLE_ENVS = ("BH_TELEMETRY", "BROWSER_HARNESS_TELEMETRY")
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


def _config_dir() -> Path:
    return paths.config_dir()


def _config_path() -> Path:
    return _config_dir() / "telemetry.json"


def _load_config() -> dict:
    try:
        return json.loads(_config_path().read_text())
    except (FileNotFoundError, OSError, ValueError):
        return {}


def _save_config(data: dict) -> None:
    path = _config_path()
    try:
        parent_existed = path.parent.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed and platform.system() != "Windows":
            os.chmod(path.parent, 0o700)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
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
    if _env_disabled():
        return False
    return not bool(_load_config().get("disabled"))


def status() -> dict:
    config = _load_config()
    env_disabled = _env_disabled()
    enabled = not env_disabled and not bool(config.get("disabled"))
    return {
        "enabled": enabled,
        "disabled_by_env": env_disabled,
        "disabled_by_config": bool(config.get("disabled")),
        "install_id": _install_id(config, create=enabled),
        "config_path": str(_config_path()),
    }


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


def capture(event: str, properties: dict | None = None) -> None:
    if not is_enabled():
        return
    try:
        config = _load_config()
        props = {
            "browser_harness_version": _version() or "unknown",
            "python_version": platform.python_version(),
            "os": platform.system() or "unknown",
            "machine": platform.machine() or "unknown",
            "$process_person_profile": False,
            **_safe_properties(properties),
        }
        payload = {
            "api_key": POSTHOG_KEY,
            "distinct_id": _install_id(config),
            "event": event,
            "properties": props,
        }
        data = json.dumps(payload).encode("utf-8")
        host = os.environ.get("BH_POSTHOG_HOST", POSTHOG_HOST).rstrip("/")
        req = urllib.request.Request(
            f"{host}/i/v0/e/",
            method="POST",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "browser-harness"},
        )
        urllib.request.urlopen(req, timeout=float(os.environ.get("BH_TELEMETRY_TIMEOUT", "1"))).close()
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
    print("usage: browser-harness telemetry [status|enable|disable]")
    return 2
