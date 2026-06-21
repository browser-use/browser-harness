import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4


PROFILE_MARKER_URL_PREFIX = "https://browser-use.com/browser-use-profile-target/"
PROFILE_ROOTS = [
    Path.home() / "Library/Application Support/Google/Chrome",
    Path.home() / "Library/Application Support/Google/Chrome Canary",
    Path.home() / "Library/Application Support/Comet",
    Path.home() / "Library/Application Support/Arc/User Data",
    Path.home() / "Library/Application Support/Dia/User Data",
    Path.home() / "Library/Application Support/Microsoft Edge",
    Path.home() / "Library/Application Support/Microsoft Edge Beta",
    Path.home() / "Library/Application Support/Microsoft Edge Dev",
    Path.home() / "Library/Application Support/Microsoft Edge Canary",
    Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser",
    Path.home() / ".config/google-chrome",
    Path.home() / ".config/chromium",
    Path.home() / ".config/chromium-browser",
    Path.home() / ".config/microsoft-edge",
    Path.home() / ".config/microsoft-edge-beta",
    Path.home() / ".config/microsoft-edge-dev",
    Path.home() / ".var/app/org.chromium.Chromium/config/chromium",
    Path.home() / ".var/app/com.google.Chrome/config/google-chrome",
    Path.home() / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser",
    Path.home() / ".var/app/com.microsoft.Edge/config/microsoft-edge",
    Path.home() / "AppData/Local/Google/Chrome/User Data",
    Path.home() / "AppData/Local/Google/Chrome SxS/User Data",
    Path.home() / "AppData/Local/Chromium/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge Beta/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge Dev/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge SxS/User Data",
    Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/User Data",
]


@dataclass
class ManagedBrowser:
    process: subprocess.Popen
    profile_dir: tempfile.TemporaryDirectory | None
    marker_path: Path
    persist: bool = False

    def stop(self):
        if self.persist:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        try:
            self.marker_path.unlink()
        except FileNotFoundError:
            pass
        if self.profile_dir is not None:
            self.profile_dir.cleanup()


@dataclass
class BrowserEndpoint:
    ws_url: str
    http_url: str | None = None
    kind: str = "cdp-ws"
    managed: ManagedBrowser | None = None
    target_marker: str | None = None
    # Profile to open a marker tab in after the websocket connects. Deferred so a
    # failed connection doesn't leave a stray tab in the user's Chrome.
    marker_profile_id: str | None = None


@dataclass
class LocalBrowserInstall:
    browser_name: str
    browser_path: Path
    user_data_dir: Path


@dataclass
class LocalBrowserProfile:
    id: str
    browser_name: str
    browser_path: Path
    user_data_dir: Path
    profile_dir: str
    profile_name: str
    profile_path: Path
    display_name: str

    def to_json(self):
        return {
            "id": self.id,
            "browserName": self.browser_name,
            "browserPath": str(self.browser_path),
            "userDataDir": str(self.user_data_dir),
            "profileDir": self.profile_dir,
            "profileName": self.profile_name,
            "profilePath": str(self.profile_path),
            "displayName": self.display_name,
            # Compatibility with profile-use output names.
            "BrowserName": self.browser_name,
            "BrowserPath": str(self.browser_path),
            "ProfileName": self.profile_name,
            "ProfilePath": str(self.profile_path),
            "DisplayName": self.display_name,
        }


def profile_marker_target_url(marker):
    return f"{PROFILE_MARKER_URL_PREFIX}{marker}"


def _config_path():
    return Path(os.environ.get("BH_CONFIG", Path.home() / ".browser-harness" / "config.json"))


def _load_config():
    path = _config_path()
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, OSError, ValueError):
        return {}


def _save_config(config):
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")


def default_profile():
    profile_id = _load_config().get("defaultProfileId")
    if not profile_id:
        return None
    try:
        return resolve_local_profile(profile_id).to_json()
    except Exception:
        return None


def set_default_profile(profile_ref, browser_name=None):
    profile = resolve_local_profile(profile_ref, browser_name=browser_name)
    config = _load_config()
    config["defaultProfileId"] = profile.id
    config["defaultBrowserName"] = profile.browser_name
    _save_config(config)
    return profile.to_json()


def _browser_slug(name):
    out = []
    dash = False
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
            dash = False
        elif not dash:
            out.append("-")
            dash = True
    return "".join(out).strip("-")


def _profile_dir_sort_key(profile_dir):
    return (0, "") if profile_dir == "Default" else (1, profile_dir)


def _known_browser_installs():
    home = Path.home()
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    local_app_data = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData/Local")))
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
        ("Vivaldi", Path("/usr/bin/vivaldi"), home / ".config/vivaldi"),
        ("Vivaldi", Path("/usr/bin/vivaldi-stable"), home / ".config/vivaldi"),
        ("Google Chrome", program_files / "Google/Chrome/Application/chrome.exe", local_app_data / "Google/Chrome/User Data"),
        ("Google Chrome", program_files_x86 / "Google/Chrome/Application/chrome.exe", local_app_data / "Google/Chrome/User Data"),
        ("Google Chrome", local_app_data / "Google/Chrome/Application/chrome.exe", local_app_data / "Google/Chrome/User Data"),
        ("Brave", program_files / "BraveSoftware/Brave-Browser/Application/brave.exe", local_app_data / "BraveSoftware/Brave-Browser/User Data"),
        ("Brave", local_app_data / "BraveSoftware/Brave-Browser/Application/brave.exe", local_app_data / "BraveSoftware/Brave-Browser/User Data"),
        ("Microsoft Edge", program_files / "Microsoft/Edge/Application/msedge.exe", local_app_data / "Microsoft/Edge/User Data"),
        ("Microsoft Edge", program_files_x86 / "Microsoft/Edge/Application/msedge.exe", local_app_data / "Microsoft/Edge/User Data"),
        ("Chromium", local_app_data / "Chromium/Application/chrome.exe", local_app_data / "Chromium/User Data"),
    ]
    installs = []
    seen = {}
    for browser_name, browser_path, user_data_dir in candidates:
        if not browser_path.exists() and not user_data_dir.exists():
            continue
        key = (browser_name, user_data_dir)
        install = LocalBrowserInstall(browser_name, browser_path, user_data_dir)
        if key in seen:
            idx = seen[key]
            if not installs[idx].browser_path.exists() and browser_path.exists():
                installs[idx] = install
        else:
            seen[key] = len(installs)
            installs.append(install)
    return installs


def _profile_names_from_local_state(user_data_dir):
    try:
        value = json.loads((user_data_dir / "Local State").read_text())
    except (FileNotFoundError, OSError, ValueError):
        return {}
    info = value.get("profile", {}).get("info_cache", {})
    if not isinstance(info, dict):
        return {}
    return {
        profile_dir: item.get("name")
        for profile_dir, item in info.items()
        if isinstance(item, dict) and item.get("name")
    }


def _remote_debugging_user_enabled(user_data_dir):
    try:
        value = json.loads((user_data_dir / "Local State").read_text())
    except (FileNotFoundError, OSError, ValueError):
        return None
    return value.get("devtools", {}).get("remote_debugging", {}).get("user-enabled")


def _valid_profile_dir(path):
    return any((path / rel).exists() for rel in ("Preferences", "Cookies", "History", "Network/Cookies"))


def detect_local_profiles():
    profiles = []
    seen = set()
    for install in _known_browser_installs():
        if not install.user_data_dir.exists():
            continue
        names = _profile_names_from_local_state(install.user_data_dir)
        try:
            entries = list(install.user_data_dir.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir() or not _valid_profile_dir(entry):
                continue
            profile_dir = entry.name
            key = (install.user_data_dir, profile_dir)
            if key in seen:
                continue
            seen.add(key)
            profile_name = names.get(profile_dir) or profile_dir
            profiles.append(LocalBrowserProfile(
                id=f"{_browser_slug(install.browser_name)}:{profile_dir}",
                browser_name=install.browser_name,
                browser_path=install.browser_path,
                user_data_dir=install.user_data_dir,
                profile_dir=profile_dir,
                profile_name=profile_name,
                profile_path=entry,
                display_name=f"{install.browser_name} - {profile_name}",
            ))
    profiles.sort(key=lambda p: (p.browser_name, _profile_dir_sort_key(p.profile_dir), p.profile_name))
    return profiles


def list_local_profiles():
    return [profile.to_json() for profile in detect_local_profiles()]


def list_local_browsers():
    by_name = {}
    for profile in detect_local_profiles():
        item = by_name.setdefault(profile.browser_name, {
            "name": profile.browser_name,
            "browserPath": str(profile.browser_path),
            "profileCount": 0,
            "managedHeaded": False,
            "managedHeadless": False,
        })
        item["profileCount"] += 1
    managed_headed = bool(_browser_paths())
    if managed_headed:
        item = by_name.setdefault("Chromium", {
            "name": "Chromium",
            "browserPath": _browser_paths()[0],
            "profileCount": 0,
            "managedHeaded": False,
            "managedHeadless": False,
        })
        item["managedHeaded"] = True
        item["managedHeadless"] = True
    return sorted(by_name.values(), key=lambda item: item["name"])


def resolve_local_profile(profile_ref, browser_name=None):
    profiles = detect_local_profiles()
    if browser_name:
        profiles = [p for p in profiles if p.browser_name == browser_name]
    for profile in profiles:
        if profile.id == profile_ref:
            return profile
    matches = [
        p for p in profiles
        if profile_ref in {p.profile_name, p.profile_dir, p.display_name}
    ]
    if not matches:
        raise RuntimeError(f"no local profile matched {profile_ref!r}")
    if len(matches) > 1:
        raise RuntimeError(f"multiple local profiles matched {profile_ref!r}; pass the exact profile id")
    return matches[0]


def _profile_value(profile, *names):
    for name in names:
        if profile.get(name):
            return profile[name]
    return None


def open_local_profile(profile_name, browser_name=None, url=None):
    profile = resolve_local_profile(profile_name, browser_name=browser_name)
    args = [str(profile.browser_path)]
    if sys.platform == "darwin":
        args.append(f"--user-data-dir={profile.user_data_dir}")
    args.append(f"--profile-directory={profile.profile_dir}")
    if url:
        args.append(url)
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return profile.to_json()


def open_local_profile_marker(profile_name, browser_name=None, marker=None):
    marker = marker or uuid4().hex
    target_url = profile_marker_target_url(marker)
    profile = open_local_profile(profile_name, browser_name=browser_name, url=target_url)
    return {"marker": marker, "url": target_url, "profile": profile}


def _endpoint_from_user_data_dir(user_data_dir, wait=30):
    deadline = time.time() + wait
    last_err = None
    active = user_data_dir / "DevToolsActivePort"
    while time.time() < deadline:
        try:
            lines = active.read_text().splitlines()
            port = lines[0].strip() if lines else ""
            path = lines[1].strip() if len(lines) > 1 else ""
            if not port:
                raise RuntimeError(f"{active} did not contain a port")
            http = f"http://127.0.0.1:{port}"
            try:
                return BrowserEndpoint(ws_from_http(http, timeout=1), http, "devtools-active-port")
            except urllib.error.HTTPError as e:
                if e.code == 404 and path:
                    return BrowserEndpoint(f"ws://127.0.0.1:{port}{path}", http, "devtools-active-port")
                last_err = e
            except Exception as e:
                last_err = e
        except (FileNotFoundError, OSError, RuntimeError) as e:
            last_err = e
        time.sleep(0.25)
    raise RuntimeError(
        f"selected profile did not expose a reachable DevTools endpoint after {wait}s: {last_err}. "
        "Open chrome://inspect/#remote-debugging in that profile and allow remote debugging, then retry."
    )


def _configured_profile_ref():
    return (
        os.environ.get("BH_PROFILE")
        or os.environ.get("BH_BROWSER_PROFILE")
        or os.environ.get("BH_LOCAL_PROFILE")
        or _load_config().get("defaultProfileId")
    )


def _configured_browser_name():
    return os.environ.get("BH_BROWSER") or os.environ.get("BH_BROWSER_NAME")


def configured_local_profile():
    profile_ref = _configured_profile_ref()
    if not profile_ref:
        return None
    browser_name = _configured_browser_name()
    return resolve_local_profile(profile_ref, browser_name=browser_name)


def configured_profile_remote_debugging_enabled():
    profile = configured_local_profile()
    return _remote_debugging_user_enabled(profile.user_data_dir) if profile else None


def open_configured_profile(marker=None):
    profile = configured_local_profile()
    if not profile:
        return None
    return open_local_profile(profile.id)


def open_configured_profile_marker(marker=None):
    profile = configured_local_profile()
    if not profile:
        return None
    return open_local_profile_marker(profile.id, marker=marker)


def _classify_profile_connection(profile, timeout=2):
    """Classify the selected profile's connection state from DevToolsActivePort
    and Local State, without opening a tab. Returns (endpoint, state):

      "ok"                 reachable, endpoint set
      "permission-blocked" reachable but Chrome rejected DevTools with 403
      "cdp-disabled"       Chrome running, remote-debugging checkbox off
      "browser-closed"     no reachable DevTools port

    Only "ok" carries an endpoint; the caller raises a blocked error otherwise.
    """
    enabled = _remote_debugging_user_enabled(profile.user_data_dir)
    active = profile.user_data_dir / "DevToolsActivePort"
    try:
        lines = active.read_text().splitlines()
    except (FileNotFoundError, OSError):
        lines = []
    port = lines[0].strip() if lines else ""
    path = lines[1].strip() if len(lines) > 1 else ""
    if port:
        http = f"http://127.0.0.1:{port}"
        try:
            return BrowserEndpoint(ws_from_http(http, timeout=timeout), http, "devtools-active-port"), "ok"
        except urllib.error.HTTPError as e:
            if e.code == 404 and path:
                return BrowserEndpoint(f"ws://127.0.0.1:{port}{path}", http, "devtools-active-port"), "ok"
            if e.code == 403:
                return None, "permission-blocked"
            # answered but unhealthy: fall through to the checkbox/closed split
        except Exception:
            # stale port file: nothing listening
            pass
    if enabled is False:
        return None, "cdp-disabled"
    return None, "browser-closed"


def _profile_connection_blocked_message(profile, state):
    label = profile.display_name or profile.id
    if state == "permission-blocked":
        return (
            f"permission-blocked: Chrome rejected the CDP websocket with HTTP 403 for {label}. "
            "Accept Chrome's 'Allow remote debugging?' dialog, then retry. Do not run setup or reload."
        )
    if state == "cdp-disabled":
        return (
            f"cdp-disabled: Chrome is open for {label}, but remote debugging is turned off. "
            "Enable chrome://inspect/#remote-debugging — tick 'Allow remote debugging for this browser instance' — then retry. Relay this and retry; do not reload or diagnose."
        )
    return (
        f"browser-closed: DevToolsActivePort not found for {label}. "
        "Open the selected Chrome profile and enable remote debugging at chrome://inspect/#remote-debugging, then retry. Relay this and retry; do not reload or diagnose."
    )


def open_configured_profile_endpoint():
    profile = configured_local_profile()
    if not profile:
        return None
    endpoint, state = _classify_profile_connection(profile)
    if state != "ok":
        raise RuntimeError(_profile_connection_blocked_message(profile, state))
    # Reuse a marker the profile-target command already opened (BH_TARGET_MARKER);
    # otherwise let the daemon open it after the websocket connects.
    env_marker = os.environ.get("BH_TARGET_MARKER")
    if env_marker:
        endpoint.target_marker = env_marker
    else:
        endpoint.marker_profile_id = profile.id
    return endpoint


def _ambiguous_profile_error():
    profiles = list_local_profiles()
    if len(profiles) <= 1:
        return None
    lines = [
        "No default local browser profile is configured; refusing to attach to an arbitrary Chrome profile.",
        "Set one with: browser-harness default-profile --profile <id-or-name>",
        "Available profiles:",
    ]
    for profile in profiles:
        lines.append(f"  {profile['id']}\t{profile['displayName']}\t{profile['profilePath']}")
    return "\n".join(lines)


def _truthy_env(name):
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value.lower() not in {"0", "false", "no", "off"}


def _urlopen_json(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def ws_from_http(http_url, timeout=15):
    value = _urlopen_json(f"{http_url.rstrip('/')}/json/version", timeout=timeout)
    ws = value.get("webSocketDebuggerUrl")
    if not ws:
        raise RuntimeError(f"{http_url}/json/version missing webSocketDebuggerUrl")
    return ws


def _host_for_ws_url(http_url):
    p = urlparse(http_url)
    host = p.hostname or "127.0.0.1"
    if ":" in host:
        return f"[{host}]"
    return host


def _ws_from_devtools_active_port(http_url):
    p = urlparse(http_url)
    want_port = str(p.port) if p.port else ""
    if not want_port:
        return None
    host = _host_for_ws_url(http_url)
    for base in PROFILE_ROOTS:
        try:
            active = (base / "DevToolsActivePort").read_text().splitlines()
        except (FileNotFoundError, NotADirectoryError, OSError):
            continue
        port = active[0].strip() if active else ""
        path = active[1].strip() if len(active) > 1 else ""
        if port == want_port and path:
            return f"ws://{host}:{port}{path}"
    return None


def resolve_http_endpoint(http_url, wait=30, request_timeout=5):
    base = http_url.rstrip("/")
    deadline = time.time() + wait
    last_err = None
    while time.time() < deadline:
        try:
            return BrowserEndpoint(
                ws_url=ws_from_http(base, timeout=request_timeout),
                http_url=base,
                kind="cdp-url",
            )
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 404:
                ws = _ws_from_devtools_active_port(base)
                if ws:
                    return BrowserEndpoint(ws_url=ws, http_url=base, kind="devtools-active-port")
        except Exception as e:
            last_err = e
        time.sleep(0.25)
    raise RuntimeError(f"BU_CDP_URL={http_url} unreachable after {wait}s: {last_err}")


def _devtools_active_port_endpoints():
    seen = set()
    for base in PROFILE_ROOTS:
        try:
            active = (base / "DevToolsActivePort").read_text().splitlines()
        except (FileNotFoundError, NotADirectoryError, OSError):
            continue
        port = active[0].strip() if active else ""
        path = active[1].strip() if len(active) > 1 else ""
        if not port or not path:
            continue
        http = f"http://127.0.0.1:{port}"
        key = (http, path)
        if key in seen:
            continue
        seen.add(key)
        yield base, http, f"ws://127.0.0.1:{port}{path}"


def find_existing_endpoint():
    for _base, http, ws in _devtools_active_port_endpoints():
        try:
            return BrowserEndpoint(ws_from_http(http, timeout=1), http, "devtools-active-port")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return BrowserEndpoint(ws, http, "devtools-active-port")
        except Exception:
            continue
    for port in (9222, 9223):
        http = f"http://127.0.0.1:{port}"
        try:
            return BrowserEndpoint(ws_from_http(http, timeout=1), http, "port-probe")
        except Exception:
            continue
    return None


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _has_gui():
    if sys.platform == "darwin" or sys.platform == "win32":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _browser_paths():
    out = []
    for name in ("BH_CHROME_PATH", "CHROME_PATH"):
        value = os.environ.get(name)
        if value:
            out.append(value)
    candidates = [
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/opt/homebrew/Caskroom/chromium/latest/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/microsoft-edge",
        "/usr/bin/brave-browser",
    ]
    out.extend(p for p in candidates if Path(p).exists())
    for name in (
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "microsoft-edge",
        "brave-browser",
    ):
        path = shutil.which(name)
        if path:
            out.append(path)
    deduped = []
    seen = set()
    for path in out:
        if path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped


def launch_managed_browser(headless=None):
    paths = _browser_paths()
    if not paths:
        raise RuntimeError("No Chromium executable found. Set BH_CHROME_PATH or CHROME_PATH.")
    if headless is None:
        headless = _truthy_env("BH_MANAGED_HEADLESS")
    if headless is None:
        headless = not _has_gui()
    errors = []
    for executable in paths:
        try:
            return _launch_managed_browser(executable, bool(headless))
        except Exception as e:
            errors.append(f"{executable}: {e}")
    raise RuntimeError("No Chromium executable successfully exposed DevTools:\n" + "\n".join(errors))


def _launch_managed_browser(executable, headless):
    port = _free_port()
    profile = tempfile.TemporaryDirectory(prefix="browser-harness-managed.")
    profile_path = Path(profile.name)
    marker_path = profile_path / "BrowserHarnessManagedChrome.json"
    args = [
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if headless:
        args += ["--headless=new", "--window-size=1280,720"]
    else:
        args += ["--new-window", "--window-size=1512,900"]
    args += ["about:blank"]
    process = subprocess.Popen(
        [executable, *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    managed = ManagedBrowser(process=process, profile_dir=profile, marker_path=marker_path)
    marker_path.write_text(json.dumps({
        "pid": process.pid,
        "port": port,
        "executable": executable,
        "profile_path": str(profile_path),
        "started_at": time.time(),
    }, indent=2))
    http = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    last_err = None
    while time.time() < deadline:
        if process.poll() is not None:
            managed.stop()
            raise RuntimeError("managed browser exited before DevTools became available")
        try:
            ws = ws_from_http(http, timeout=1)
            return BrowserEndpoint(ws_url=ws, http_url=http, kind="managed", managed=managed)
        except Exception as e:
            last_err = e
            time.sleep(0.25)
    managed.stop()
    raise RuntimeError(f"managed browser DevTools did not become available: {last_err}")


def get_browser_endpoint():
    if url := os.environ.get("BU_CDP_WS"):
        return BrowserEndpoint(ws_url=url, kind="cdp-ws")
    if url := os.environ.get("BU_CDP_URL"):
        return resolve_http_endpoint(url)
    endpoint = open_configured_profile_endpoint()
    if endpoint:
        return endpoint
    ambiguous = _ambiguous_profile_error()
    if ambiguous and not _truthy_env("BH_ALLOW_ARBITRARY_PROFILE"):
        raise RuntimeError(ambiguous)
    endpoint = find_existing_endpoint()
    if endpoint:
        return endpoint
    if _truthy_env("BH_NO_MANAGED_BROWSER"):
        raise RuntimeError(
            "No local Chrome CDP endpoint found. Enable chrome://inspect/#remote-debugging, "
            "set BU_CDP_WS/BU_CDP_URL, or unset BH_NO_MANAGED_BROWSER to allow managed Chrome."
        )
    return launch_managed_browser()
