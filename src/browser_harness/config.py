"""Persistent browser preferences: which browser, which startup tab, tab marker.

The file is ``~/.config/browser-harness/config.json`` (``BH_CONFIG_DIR`` moves the
directory). It is read when the daemon starts, so one file applies to every
caller — Claude Code, Codex, a plain terminal — unlike ``BU_CDP_URL``, which is
per process and has to be exported again in every shell.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import paths

CONFIG_FILE = "config.json"
STARTUP_TABS = ("new", "first_page")
BROWSER_KEYS = ("preferred_browser", "startup_tab", "tab_marker")


def config_path() -> Path:
    return paths.config_dir() / CONFIG_FILE


def load() -> dict:
    """The whole config file. A missing or damaged file reads as empty."""
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def browser_settings() -> dict:
    """The browser section, validated.

    Unknown keys and invalid values are ignored rather than fatal: a typo must
    not stop the daemon from starting. ``startup_tab`` defaults to ``new``;
    ``tab_marker`` stays None when unset, so the environment keeps the last word.
    """
    section = load().get("browser")
    out = {"preferred_browser": None, "startup_tab": "new", "tab_marker": None}
    if not isinstance(section, dict):
        return out
    preferred = section.get("preferred_browser")
    if isinstance(preferred, str) and preferred.strip():
        out["preferred_browser"] = preferred.strip()
    startup_tab = section.get("startup_tab")
    if isinstance(startup_tab, str) and startup_tab.strip().lower() in STARTUP_TABS:
        out["startup_tab"] = startup_tab.strip().lower()
    tab_marker = section.get("tab_marker")
    if isinstance(tab_marker, bool):
        out["tab_marker"] = tab_marker
    return out


def write(settings: dict) -> Path:
    """Merge ``settings`` into the browser section and save.

    A None value removes the key, so ``config clear`` is the same code path.
    Other sections of the file are kept.
    """
    path = config_path()
    data = load()
    section = data.get("browser")
    section = dict(section) if isinstance(section, dict) else {}
    for key, value in settings.items():
        if value is None:
            section.pop(key, None)
        else:
            section[key] = value
    data["browser"] = section
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def parse_assignment(text: str) -> tuple[str, object]:
    """``key=value`` into (key, value), with booleans and known tab policies typed."""
    key, sep, raw = text.partition("=")
    key = key.strip()
    if not sep or not key:
        raise ValueError(f"expected key=value, got {text!r}")
    value = raw.strip()
    if value.lower() in {"true", "yes", "on", "1"}:
        return key, True
    if value.lower() in {"false", "no", "off", "0"}:
        return key, False
    if value.lower() in {"none", "null", ""}:
        return key, None
    if key == "startup_tab":
        value = value.lower()
        if value not in STARTUP_TABS:
            raise ValueError(f"startup_tab must be one of {', '.join(STARTUP_TABS)}, got {value!r}")
        return key, value
    return key, value


def _cli_name():
    from .naming import cli_name

    return cli_name()


def run_config_cli(args) -> int:
    """``config show`` / ``config set key=value ...`` / ``config clear key ...``."""
    args = list(args)
    if not args or args[0] in {"show", "get"}:
        path = config_path()
        print(f"config file: {path}" + ("" if path.exists() else " (not created yet)"))
        settings = browser_settings()
        print(f"  preferred_browser  {settings['preferred_browser'] or '(not set — first live browser wins)'}")
        print(f"  startup_tab        {settings['startup_tab']}")
        print(f"  tab_marker         {'on' if settings['tab_marker'] else 'off' if settings['tab_marker'] is False else '(environment default)'}")
        return 0
    action = args[0]
    if action == "set":
        if len(args) < 2:
            print(f"usage: {_cli_name()} config set key=value [key=value ...]", file=os.sys.stderr)
            return 2
        settings = {}
        for item in args[1:]:
            try:
                key, value = parse_assignment(item)
            except ValueError as e:
                print(f"{_cli_name()} config: {e}", file=os.sys.stderr)
                return 2
            if key not in BROWSER_KEYS:
                print(f"{_cli_name()} config: unknown key {key!r} (known: {', '.join(BROWSER_KEYS)})", file=os.sys.stderr)
                return 2
            settings[key] = value
        path = write(settings)
        print(f"saved {path}")
        for key, value in settings.items():
            print(f"  {key} = {value}")
        return 0
    if action == "clear":
        if not args[1:]:
            print(f"usage: {_cli_name()} config clear [key ...]", file=os.sys.stderr)
            return 2
        settings = {}
        for key in args[1:]:
            if key not in BROWSER_KEYS:
                print(f"{_cli_name()} config: unknown key {key!r} (known: {', '.join(BROWSER_KEYS)})", file=os.sys.stderr)
                return 2
            settings[key] = None
        path = write(settings)
        print(f"saved {path}")
        return 0
    print(f"usage: {_cli_name()} config [show|set key=value|clear key]", file=os.sys.stderr)
    return 2
