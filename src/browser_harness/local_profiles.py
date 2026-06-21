"""Native Chromium-family profile discovery and selected-profile state."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


MARKER_URL_PREFIX = "https://browser-use.com/browser-use-profile-target/"
INTERNAL_URL_PREFIXES = (
    "chrome://",
    "chrome-untrusted://",
    "devtools://",
    "chrome-extension://",
    "about:",
)


@dataclass(frozen=True)
class LocalBrowserInstall:
    browser_name: str
    browser_path: Path
    user_data_dir: Path

    def payload(self) -> dict:
        return {
            "browser_name": self.browser_name,
            "browser_path": str(self.browser_path),
            "user_data_dir": str(self.user_data_dir),
        }


@dataclass(frozen=True)
class LocalBrowserProfile:
    id: str
    browser_name: str
    browser_path: Path
    user_data_dir: Path
    profile_dir: str
    profile_name: str
    profile_path: Path
    display_name: str

    def payload(self) -> dict:
        data = asdict(self)
        for key in ("browser_path", "user_data_dir", "profile_path"):
            data[key] = str(data[key])
        return data


@dataclass(frozen=True)
class LocalCandidate:
    id: str
    browser_name: str
    browser_path: str | None
    profile_path: str
    http_url: str | None
    ws_url: str
    source: str
    connectable: bool
    state: str
    stale: bool
    browser_running: bool | None
    remote_debugging_enabled: bool | None
    reason: str | None
    next_step: str | None

    def payload(self) -> dict:
        return asdict(self)


def config_dir() -> Path:
    if raw := os.environ.get("BH_CONFIG_DIR"):
        return Path(raw).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "browser-harness"
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return Path(base).expanduser() / "browser-harness" if base else Path.home() / "AppData" / "Roaming" / "browser-harness"
    base = os.environ.get("XDG_CONFIG_HOME")
    return Path(base).expanduser() / "browser-harness" if base else Path.home() / ".config" / "browser-harness"


def profile_config_path() -> Path:
    return config_dir() / "profile.json"


def get_default_profile_id() -> str | None:
    for key in ("BH_SELECTED_LOCAL_PROFILE", "BH_LOCAL_PROFILE"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    try:
        data = json.loads(profile_config_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    value = str(data.get("default_local_profile_id") or "").strip()
    return value or None


def set_default_profile_id(profile_id: str | None) -> dict:
    path = profile_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if profile_id:
        profile = resolve_local_profile(profile_id)
        require_browser_binary(profile)
        data = {
            "default_local_profile_id": profile.id,
            "default_local_profile_label": profile.display_name,
        }
    else:
        data = {
            "default_local_profile_id": None,
            "default_local_profile_label": None,
        }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)
    return data


def known_local_browser_installs() -> list[LocalBrowserInstall]:
    home = Path.home()
    program_files = Path(os.environ.get("ProgramFiles") or "C:/Program Files")
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)") or "C:/Program Files (x86)")
    local_app_data = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    candidates = [
        ("Google Chrome", Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), home / "Library/Application Support/Google/Chrome"),
        ("Chrome Canary", Path("/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"), home / "Library/Application Support/Google/Chrome Canary"),
        ("Brave", Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"), home / "Library/Application Support/BraveSoftware/Brave-Browser"),
        ("Microsoft Edge", Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"), home / "Library/Application Support/Microsoft Edge"),
        ("Chromium", Path("/Applications/Chromium.app/Contents/MacOS/Chromium"), home / "Library/Application Support/Chromium"),
        ("Arc", Path("/Applications/Arc.app/Contents/MacOS/Arc"), home / "Library/Application Support/Arc/User Data"),
        ("Dia", Path("/Applications/Dia.app/Contents/MacOS/Dia"), home / "Library/Application Support/Dia"),
        ("Comet", Path("/Applications/Comet.app/Contents/MacOS/Comet"), home / "Library/Application Support/Comet"),
        ("Helium", Path("/Applications/Helium.app/Contents/MacOS/Helium"), home / "Library/Application Support/Helium"),
        ("Sidekick", Path("/Applications/Sidekick.app/Contents/MacOS/Sidekick"), home / "Library/Application Support/Sidekick"),
        ("Thorium", Path("/Applications/Thorium.app/Contents/MacOS/Thorium"), home / "Library/Application Support/Thorium"),
        ("SigmaOS", Path("/Applications/SigmaOS.app/Contents/MacOS/SigmaOS"), home / "Library/Application Support/SigmaOS/User Data"),
        ("Wavebox", Path("/Applications/Wavebox.app/Contents/MacOS/Wavebox"), home / "Library/Application Support/WaveboxApp"),
        ("Ghost Browser", Path("/Applications/Ghost Browser.app/Contents/MacOS/Ghost Browser"), home / "Library/Application Support/Ghost Browser"),
        ("Blisk", Path("/Applications/Blisk.app/Contents/MacOS/Blisk"), home / "Library/Application Support/Blisk"),
        ("Opera", Path("/Applications/Opera.app/Contents/MacOS/Opera"), home / "Library/Application Support/com.operasoftware.Opera"),
        ("Vivaldi", Path("/Applications/Vivaldi.app/Contents/MacOS/Vivaldi"), home / "Library/Application Support/Vivaldi"),
        ("Yandex", Path("/Applications/Yandex.app/Contents/MacOS/Yandex"), home / "Library/Application Support/Yandex/YandexBrowser"),
        ("Iridium", Path("/Applications/Iridium.app/Contents/MacOS/Iridium"), home / "Library/Application Support/Iridium"),
        ("Google Chrome", Path("/usr/bin/google-chrome"), home / ".config/google-chrome"),
        ("Google Chrome", Path("/usr/bin/google-chrome-stable"), home / ".config/google-chrome"),
        ("Brave", Path("/usr/bin/brave-browser"), home / ".config/BraveSoftware/Brave-Browser"),
        ("Brave", Path("/usr/bin/brave"), home / ".config/BraveSoftware/Brave-Browser"),
        ("Brave", Path("/snap/bin/brave"), home / ".config/BraveSoftware/Brave-Browser"),
        ("Microsoft Edge", Path("/usr/bin/microsoft-edge"), home / ".config/microsoft-edge"),
        ("Microsoft Edge", Path("/usr/bin/microsoft-edge-stable"), home / ".config/microsoft-edge"),
        ("Chromium", Path("/usr/bin/chromium"), home / ".config/chromium"),
        ("Chromium", Path("/usr/bin/chromium-browser"), home / ".config/chromium"),
        ("Chromium", Path("/snap/bin/chromium"), home / ".config/chromium"),
        ("Opera", Path("/usr/bin/opera"), home / ".config/opera"),
        ("Opera", Path("/snap/bin/opera"), home / ".config/opera"),
        ("Vivaldi", Path("/usr/bin/vivaldi"), home / ".config/vivaldi"),
        ("Vivaldi", Path("/usr/bin/vivaldi-stable"), home / ".config/vivaldi"),
        ("Vivaldi", Path("/snap/bin/vivaldi"), home / ".config/vivaldi"),
        ("Yandex", Path("/usr/bin/yandex-browser"), home / ".config/yandex-browser"),
        ("Yandex", Path("/usr/bin/yandex-browser-stable"), home / ".config/yandex-browser"),
        ("Iridium", Path("/usr/bin/iridium-browser"), home / ".config/iridium"),
        ("Ungoogled Chromium", Path("/usr/bin/ungoogled-chromium"), home / ".config/chromium"),
        ("Thorium", Path("/usr/bin/thorium-browser"), home / ".config/thorium"),
        ("Sidekick", home / ".local/share/sidekick/sidekick", home / ".config/Sidekick"),
        ("Wavebox", Path("/usr/bin/wavebox"), home / ".config/Wavebox"),
        ("Google Chrome", program_files / "Google/Chrome/Application/chrome.exe", local_app_data / "Google/Chrome/User Data"),
        ("Google Chrome", program_files_x86 / "Google/Chrome/Application/chrome.exe", local_app_data / "Google/Chrome/User Data"),
        ("Google Chrome", local_app_data / "Google/Chrome/Application/chrome.exe", local_app_data / "Google/Chrome/User Data"),
        ("Brave", program_files / "BraveSoftware/Brave-Browser/Application/brave.exe", local_app_data / "BraveSoftware/Brave-Browser/User Data"),
        ("Brave", local_app_data / "BraveSoftware/Brave-Browser/Application/brave.exe", local_app_data / "BraveSoftware/Brave-Browser/User Data"),
        ("Microsoft Edge", program_files / "Microsoft/Edge/Application/msedge.exe", local_app_data / "Microsoft/Edge/User Data"),
        ("Microsoft Edge", program_files_x86 / "Microsoft/Edge/Application/msedge.exe", local_app_data / "Microsoft/Edge/User Data"),
        ("Chromium", local_app_data / "Chromium/Application/chrome.exe", local_app_data / "Chromium/User Data"),
        ("Opera", local_app_data / "Programs/Opera/opera.exe", home / "AppData/Roaming/Opera Software/Opera Stable"),
        ("Opera", program_files / "Opera/opera.exe", home / "AppData/Roaming/Opera Software/Opera Stable"),
        ("Vivaldi", local_app_data / "Vivaldi/Application/vivaldi.exe", local_app_data / "Vivaldi/User Data"),
        ("Vivaldi", program_files / "Vivaldi/Application/vivaldi.exe", local_app_data / "Vivaldi/User Data"),
        ("Yandex", local_app_data / "Yandex/YandexBrowser/Application/browser.exe", local_app_data / "Yandex/YandexBrowser/User Data"),
        ("Iridium", local_app_data / "Iridium/Application/iridium.exe", local_app_data / "Iridium/User Data"),
        ("Sidekick", local_app_data / "Sidekick/Application/sidekick.exe", local_app_data / "Sidekick/User Data"),
        ("Thorium", local_app_data / "Thorium/Application/thorium.exe", local_app_data / "Thorium/User Data"),
        ("Wavebox", local_app_data / "WaveboxApp/Application/wavebox.exe", local_app_data / "WaveboxApp/User Data"),
        ("Blisk", local_app_data / "Blisk/Application/blisk.exe", local_app_data / "Blisk/User Data"),
    ]
    installs: list[LocalBrowserInstall] = []
    seen: dict[tuple[str, Path], int] = {}
    for browser_name, browser_path, user_data_dir in candidates:
        if not browser_path.exists() and not user_data_dir.exists():
            continue
        key = (browser_name, user_data_dir)
        candidate = LocalBrowserInstall(browser_name, browser_path, user_data_dir)
        if key in seen:
            index = seen[key]
            if not installs[index].browser_path.exists() and browser_path.exists():
                installs[index] = candidate
        else:
            seen[key] = len(installs)
            installs.append(candidate)
    return installs


def known_profile_roots() -> list[tuple[str, Path]]:
    home = Path.home()
    return [
        ("Google Chrome", home / "Library/Application Support/Google/Chrome"),
        ("Chrome Canary", home / "Library/Application Support/Google/Chrome Canary"),
        ("Comet", home / "Library/Application Support/Comet"),
        ("Arc", home / "Library/Application Support/Arc/User Data"),
        ("Dia", home / "Library/Application Support/Dia/User Data"),
        ("Microsoft Edge", home / "Library/Application Support/Microsoft Edge"),
        ("Microsoft Edge Beta", home / "Library/Application Support/Microsoft Edge Beta"),
        ("Microsoft Edge Dev", home / "Library/Application Support/Microsoft Edge Dev"),
        ("Microsoft Edge Canary", home / "Library/Application Support/Microsoft Edge Canary"),
        ("Brave", home / "Library/Application Support/BraveSoftware/Brave-Browser"),
        ("Google Chrome", home / ".config/google-chrome"),
        ("Chromium", home / ".config/chromium"),
        ("Chromium", home / ".config/chromium-browser"),
        ("Microsoft Edge", home / ".config/microsoft-edge"),
        ("Microsoft Edge Beta", home / ".config/microsoft-edge-beta"),
        ("Microsoft Edge Dev", home / ".config/microsoft-edge-dev"),
        ("Chromium", home / ".var/app/org.chromium.Chromium/config/chromium"),
        ("Google Chrome", home / ".var/app/com.google.Chrome/config/google-chrome"),
        ("Brave", home / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser"),
        ("Microsoft Edge", home / ".var/app/com.microsoft.Edge/config/microsoft-edge"),
        ("Google Chrome", home / "AppData/Local/Google/Chrome/User Data"),
        ("Chrome Canary", home / "AppData/Local/Google/Chrome SxS/User Data"),
        ("Chromium", home / "AppData/Local/Chromium/User Data"),
        ("Microsoft Edge", home / "AppData/Local/Microsoft/Edge/User Data"),
        ("Microsoft Edge Beta", home / "AppData/Local/Microsoft/Edge Beta/User Data"),
        ("Microsoft Edge Dev", home / "AppData/Local/Microsoft/Edge Dev/User Data"),
        ("Microsoft Edge Canary", home / "AppData/Local/Microsoft/Edge SxS/User Data"),
        ("Brave", home / "AppData/Local/BraveSoftware/Brave-Browser/User Data"),
    ]


def detect_local_profiles() -> list[LocalBrowserProfile]:
    profiles: list[LocalBrowserProfile] = []
    seen: set[tuple[Path, str]] = set()
    for install in known_local_browser_installs():
        if not install.user_data_dir.exists():
            continue
        names = load_profile_names_from_local_state(install.user_data_dir)
        try:
            entries = list(install.user_data_dir.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            profile_dir = entry.name
            if not is_valid_local_profile_dir(entry):
                continue
            key = (install.user_data_dir, profile_dir)
            if key in seen:
                continue
            seen.add(key)
            profile_name = names.get(profile_dir) or profile_dir
            profiles.append(LocalBrowserProfile(
                id=f"{browser_slug(install.browser_name)}:{profile_dir}",
                browser_name=install.browser_name,
                browser_path=install.browser_path,
                user_data_dir=install.user_data_dir,
                profile_dir=profile_dir,
                profile_name=profile_name,
                profile_path=entry,
                display_name=f"{install.browser_name} - {profile_name}",
            ))
    profiles.sort(key=lambda p: (p.browser_name, profile_dir_sort_key(p.profile_dir), natural_key(p.profile_name)))
    return profiles


def list_local_profiles_payload() -> dict:
    default_profile_id = get_default_profile_id()
    return {
        "status": "ok",
        "default_profile_id": default_profile_id,
        "profiles": [p.payload() for p in detect_local_profiles()],
    }


def list_browser_profiles_payload(verbose: bool = False) -> dict:
    if verbose:
        return list_local_profiles_payload()
    selected = get_default_profile_id()
    return {
        "selected": selected,
        "profiles": [
            {
                "id": p.id,
                "label": p.display_name,
                "selected": p.id == selected,
            }
            for p in detect_local_profiles()
        ],
    }


def use_browser_profile(profile_id: str) -> dict:
    data = set_default_profile_id(profile_id)
    return {
        "selected": data.get("default_local_profile_id"),
        "label": data.get("default_local_profile_label"),
    }


def resolve_local_profile(profile_ref: str | None = None) -> LocalBrowserProfile:
    profile_ref = (profile_ref or get_default_profile_id() or "").strip()
    if not profile_ref:
        raise RuntimeError("no default local Chrome profile is set")
    profiles = detect_local_profiles()
    for profile in profiles:
        if profile.id == profile_ref:
            return profile
    matches = [
        p for p in profiles
        if p.profile_name == profile_ref or p.profile_dir == profile_ref or p.display_name == profile_ref
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"no local profile matched {profile_ref!r}; run browser_profiles()")
    raise RuntimeError(f"multiple local profiles matched {profile_ref!r}; pass the exact profile id")


def require_browser_binary(profile: LocalBrowserProfile) -> None:
    if not browser_binary_usable(profile.browser_path):
        raise RuntimeError(f"browser binary not found or not executable for {profile.id}: {profile.browser_path}")


def browser_binary_usable(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        return True if sys.platform == "win32" else os.access(path, os.X_OK)
    except OSError:
        return False


def load_profile_names_from_local_state(user_data_dir: Path) -> dict[str, str]:
    try:
        value = json.loads((user_data_dir / "Local State").read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    info_cache = value.get("profile", {}).get("info_cache", {})
    if not isinstance(info_cache, dict):
        return {}
    out = {}
    for profile_dir, info in info_cache.items():
        if isinstance(info, dict):
            name = str(info.get("name") or "").strip()
            if name:
                out[profile_dir] = name
    return out


def remote_debugging_user_enabled(user_data_dir: Path) -> bool | None:
    try:
        value = json.loads((user_data_dir / "Local State").read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    user_enabled = value.get("devtools", {}).get("remote_debugging", {}).get("user-enabled")
    return user_enabled if isinstance(user_enabled, bool) else None


def is_valid_local_profile_dir(path: Path) -> bool:
    return any((path / relative).exists() for relative in ("Preferences", "Cookies", "History", "Network/Cookies"))


def browser_slug(name: str) -> str:
    out = []
    last_dash = False
    for ch in name.lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
            last_dash = False
        elif not last_dash:
            out.append("-")
            last_dash = True
    return "".join(out).strip("-")


def profile_dir_sort_key(profile_dir: str) -> tuple[int, list[tuple[int, object]]]:
    return (0, []) if profile_dir == "Default" else (1, natural_key(profile_dir))


def natural_key(value: str) -> list[tuple[int, object]]:
    out: list[tuple[int, object]] = []
    buf = ""
    is_digit = False
    for ch in value:
        digit = ch.isdigit()
        if buf and digit != is_digit:
            out.append((0, int(buf)) if is_digit else (1, buf))
            buf = ""
        buf += ch
        is_digit = digit
    if buf:
        out.append((0, int(buf)) if is_digit else (1, buf))
    return out


def browser_process_running(browser_name: str, browser_path: Path | None = None) -> bool | None:
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(["tasklist", "/FO", "CSV"], text=True, timeout=5, stderr=subprocess.DEVNULL)
            exe = browser_path.name.lower() if browser_path else ""
            return bool(exe and exe in out.lower())
        out = subprocess.check_output(["ps", "-axo", "pid=,comm=,args="], text=True, timeout=5, stderr=subprocess.DEVNULL)
        if browser_path:
            path = str(browser_path)
            if path and path in out:
                return True
        return browser_name.lower() in out.lower()
    except Exception:
        return None


def local_candidates() -> list[LocalCandidate]:
    roots: list[tuple[str, Path | None, Path]] = [
        (install.browser_name, install.browser_path, install.user_data_dir)
        for install in known_local_browser_installs()
    ]
    seen_roots = {(name, root) for name, _path, root in roots}
    for name, root in known_profile_roots():
        if (name, root) not in seen_roots:
            seen_roots.add((name, root))
            roots.append((name, None, root))
    return local_candidates_from_roots(roots, [9222, 9223])


def local_candidates_from_roots(
    roots: list[tuple[str, Path | None, Path]],
    probe_ports: list[int],
) -> list[LocalCandidate]:
    candidates: list[LocalCandidate] = []
    seen_ws: set[str] = set()
    for browser_name, browser_path, user_data_dir in roots:
        active = user_data_dir / "DevToolsActivePort"
        try:
            lines = active.read_text().splitlines()
        except (FileNotFoundError, NotADirectoryError, OSError):
            continue
        port = lines[0].strip() if lines else ""
        ws_path = lines[1].strip() if len(lines) > 1 else ""
        if not port or not ws_path:
            continue
        ws_url = f"ws://127.0.0.1:{port}{ws_path}"
        if ws_url in seen_ws:
            continue
        seen_ws.add(ws_url)
        connectable = tcp_port_open("127.0.0.1", int(port) if port.isdigit() else 0)
        running = browser_process_running(browser_name, browser_path)
        enabled = remote_debugging_user_enabled(user_data_dir)
        if connectable:
            state, reason, next_step = "reachable", None, "connect local browser"
        else:
            state, reason, next_step = local_disconnected_candidate_details(running, enabled)
        candidates.append(LocalCandidate(
            id=f"local-{len(candidates) + 1}",
            browser_name=browser_name,
            browser_path=str(browser_path) if browser_path else None,
            profile_path=str(user_data_dir),
            http_url=f"http://127.0.0.1:{port}",
            ws_url=ws_url,
            source=str(active),
            connectable=connectable,
            state=state,
            stale=not connectable,
            browser_running=running,
            remote_debugging_enabled=enabled,
            reason=reason,
            next_step=next_step,
        ))
    for port in probe_ports:
        http_url = f"http://127.0.0.1:{port}"
        try:
            ws_url = resolve_ws_from_http(http_url, timeout=0.5)
        except Exception:
            continue
        if ws_url in seen_ws:
            continue
        seen_ws.add(ws_url)
        candidates.append(LocalCandidate(
            id=f"local-{len(candidates) + 1}",
            browser_name=f"CDP port {port}",
            browser_path=None,
            profile_path="",
            http_url=http_url,
            ws_url=ws_url,
            source="port-probe",
            connectable=True,
            state="reachable",
            stale=False,
            browser_running=None,
            remote_debugging_enabled=None,
            reason=None,
            next_step="connect local browser",
        ))
    return candidates


def local_debugging_disabled_statuses() -> list[dict]:
    out = []
    for install in known_local_browser_installs():
        running = browser_process_running(install.browser_name, install.browser_path)
        enabled = remote_debugging_user_enabled(install.user_data_dir)
        if running is True and enabled is False:
            out.append({
                "browser_name": install.browser_name,
                "browser_path": str(install.browser_path),
                "user_data_dir": str(install.user_data_dir),
                "browser_running": running,
                "remote_debugging_enabled": enabled,
            })
    return out


def local_disconnected_candidate_details(
    browser_running_value: bool | None,
    remote_debugging_enabled_value: bool | None,
) -> tuple[str, str, str]:
    if browser_running_value is True and remote_debugging_enabled_value is False:
        return (
            "cdp-disabled",
            "Chrome is open, but remote debugging is turned off for this browser instance.",
            "local setup",
        )
    if browser_running_value is True:
        return (
            "stale-port",
            "DevToolsActivePort exists, but the recorded CDP port is not reachable. Chrome appears open, but it is not exposing that debug endpoint.",
            "open selected profile, then reconnect",
        )
    return (
        "stale-port",
        "DevToolsActivePort exists, but the recorded CDP port is not reachable. Chrome was likely closed or the debug server stopped.",
        "open selected profile, then reconnect",
    )


def resolve_ws_from_http(http_url: str, timeout: float = 15.0) -> str:
    url = f"{http_url.rstrip('/')}/json/version"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = json.loads(resp.read() or b"{}")
    ws = data.get("webSocketDebuggerUrl")
    if not ws:
        raise RuntimeError(f"{url} missing webSocketDebuggerUrl")
    return ws


def tcp_port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    if not port:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def profile_marker_target_url(marker: str) -> str:
    return f"{MARKER_URL_PREFIX}{marker}"


def target_url_contains_marker(target: dict, marker: str) -> bool:
    return is_profile_marker_target(target) and marker in str(target.get("url") or "")


def is_profile_marker_target(target: dict) -> bool:
    return target.get("type") == "page" and MARKER_URL_PREFIX in str(target.get("url") or "")


def is_remote_debugging_setup_target(target: dict) -> bool:
    return target.get("type") == "page" and str(target.get("url") or "").startswith("chrome://inspect/#remote-debugging")


def is_internal_browser_url(url: str) -> bool:
    return str(url or "").startswith(INTERNAL_URL_PREFIXES)


def is_real_page_target(target: dict) -> bool:
    if target.get("type") != "page":
        return False
    if is_profile_marker_target(target):
        return False
    url = str(target.get("url") or "")
    return bool(url.strip()) and not is_internal_browser_url(url)


def is_reusable_placeholder_target(target: dict) -> bool:
    if target.get("type") != "page":
        return False
    if is_profile_marker_target(target) or is_remote_debugging_setup_target(target):
        return False
    url = str(target.get("url") or "")
    return url in ("", "about:blank") or url.startswith("about:blank#")


def open_local_profile(
    profile_ref: str | None = None,
    allow_marker: bool = True,
    url: str | None = None,
) -> dict:
    profile = resolve_local_profile(profile_ref)
    require_browser_binary(profile)
    profile_directory_arg = f"--profile-directory={profile.profile_dir}"
    running = browser_process_running(profile.browser_name, profile.browser_path)
    needs_marker = allow_marker and running is not False
    marker = str(int(time.time() * 1000)) if needs_marker else None
    target_url = profile_marker_target_url(marker) if marker else None
    args = [str(profile.browser_path)]
    if sys.platform == "darwin":
        args.append(f"--user-data-dir={profile.user_data_dir}")
    args.append(profile_directory_arg)
    if target_url:
        args.append(target_url)
    elif url:
        args.append(url)
    elif allow_marker:
        args.append("--no-startup-window")
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {
        "status": "ok",
        "opened": True,
        "profile": profile.payload(),
        "profile_targeting": "marker" if marker else ("profile-launch" if allow_marker else "profile-focus"),
        "target_marker": marker,
        "target_url": target_url or url,
        "next_step": "Give Chrome a moment to start, then retry browser work.",
    }
