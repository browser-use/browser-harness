"""CDP WS holder + IPC relay (Unix socket on POSIX, TCP loopback on Windows). One daemon per BU_NAME."""
import asyncio, json, os, socket, sys, time, urllib.error, urllib.request
from urllib.parse import urlparse
from collections import deque
from pathlib import Path

import websockets

from . import _ipc as ipc
from . import auth
from . import paths
from .browser_family import (
    browser_family_filter_active,
    browser_family_label,
    browser_family_mode,
    browser_path_allowed,
)
from cdp_use.client import CDPClient


def _load_env():
    repo_root = Path(__file__).resolve().parents[2]
    workspace = paths.workspace_dir()
    for p in (repo_root / ".env", workspace / ".env"):
        if not p.exists():
            continue
        _load_env_file(p)


def _load_env_file(p):
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

NAME = os.environ.get("BU_NAME", "default")
SOCK = ipc.sock_addr(NAME)
LOG = str(ipc.log_path(NAME))
PID = str(ipc.pid_path(NAME))
BUF = 500
PROFILES = [
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
INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")
BU_API = "https://api.browser-use.com/api/v3"
REMOTE_ID = os.environ.get("BU_BROWSER_ID")
LOCAL_CDP_OPEN_TIMEOUT_SECONDS = 120
REMOTE_CDP_OPEN_TIMEOUT_SECONDS = 30
DEFAULT_PROFILE_PROBE_TIMEOUT_SECONDS = 3
DEDICATED_BROWSER_PORTS = (9223, 9333, 9334)


def log(msg):
    open(LOG, "a").write(f"{msg}\n")


def _explicit_cdp_endpoint_configured():
    return bool(os.environ.get("BU_CDP_WS") or os.environ.get("BU_CDP_URL"))


def _cdp_open_timeout_seconds():
    raw = os.environ.get("BH_CDP_OPEN_TIMEOUT_SECONDS")
    default = REMOTE_CDP_OPEN_TIMEOUT_SECONDS if _explicit_cdp_endpoint_configured() else LOCAL_CDP_OPEN_TIMEOUT_SECONDS
    if not raw:
        return default
    try:
        return max(1.0, float(raw))
    except ValueError:
        return default


def _default_profile_probe_timeout_seconds():
    raw = os.environ.get("BH_DEFAULT_PROFILE_PROBE_TIMEOUT_SECONDS")
    if not raw:
        return DEFAULT_PROFILE_PROBE_TIMEOUT_SECONDS
    try:
        return max(1.0, float(raw))
    except ValueError:
        return DEFAULT_PROFILE_PROBE_TIMEOUT_SECONDS


def _local_browser_mode():
    mode = (os.environ.get("BH_LOCAL_BROWSER_MODE") or "auto").strip().lower()
    return mode if mode in {"auto", "default", "dedicated"} else "auto"


def _candidate_profiles():
    return [base for base in PROFILES if browser_path_allowed(base)]


def _read_json_url(url, timeout=1):
    return json.loads(urllib.request.urlopen(url, timeout=timeout).read())


def _dedicated_browser_ports():
    raw = os.environ.get("BH_DEDICATED_CHROME_PORT")
    if not raw:
        return DEDICATED_BROWSER_PORTS
    try:
        port = int(raw)
    except ValueError:
        return DEDICATED_BROWSER_PORTS
    return (port, *[p for p in DEDICATED_BROWSER_PORTS if p != port])


def _dedicated_user_data_dir():
    raw = os.environ.get("BH_DEDICATED_CHROME_USER_DATA_DIR")
    return Path(raw).expanduser().resolve() if raw else paths.config_dir() / "automation-profile"


def _browser_executable_candidates():
    import platform, shutil

    for key in ("BH_CHROME_PATH", "CHROME_PATH"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            yield raw
    system = platform.system()
    if system == "Windows":
        roots = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        relative = [
            ("Google", "Chrome", "Application", "chrome.exe"),
            ("BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            ("Microsoft", "Edge", "Application", "msedge.exe"),
        ]
        for root in roots:
            for parts in relative:
                yield str(Path(root, *parts))
        for cmd in ("chrome.exe", "chrome", "brave.exe", "brave", "msedge.exe", "msedge"):
            if found := shutil.which(cmd):
                yield found
        return
    if system == "Darwin":
        yield "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        yield "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        yield "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
    for cmd in ("google-chrome-stable", "google-chrome", "chromium-browser", "chromium", "brave-browser", "microsoft-edge"):
        if found := shutil.which(cmd):
            yield found


def _browser_executable():
    seen = set()
    for raw in _browser_executable_candidates():
        if not raw:
            continue
        p = Path(raw).expanduser()
        key = os.path.normcase(str(p))
        if key in seen:
            continue
        seen.add(key)
        if not browser_path_allowed(p):
            log(f"skipping browser candidate outside BH_BROWSER_FAMILY={browser_family_mode()}: {p}")
            continue
        try:
            if p.is_file():
                return str(p)
        except OSError:
            continue
    return None


def _ws_from_cdp_http_url(cdp_url, timeout=1):
    return _read_json_url(f"{cdp_url.rstrip('/')}/json/version", timeout=timeout)["webSocketDebuggerUrl"]


def _launch_dedicated_browser(port):
    import subprocess

    browser = _browser_executable()
    if not browser:
        raise RuntimeError(f"no {browser_family_label()} executable found for dedicated browser; set BH_CHROME_PATH")
    profile = _dedicated_user_data_dir()
    profile.mkdir(parents=True, exist_ok=True)
    args = [
        browser,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    log(f"starting dedicated browser on port {port}: {browser}")
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **ipc.spawn_kwargs())


def _dedicated_browser_ws_url():
    last_err = None
    for port in _dedicated_browser_ports():
        cdp_url = f"http://127.0.0.1:{port}"
        try:
            return _ws_from_cdp_http_url(cdp_url, timeout=1)
        except Exception as e:
            last_err = e
    for port in _dedicated_browser_ports():
        cdp_url = f"http://127.0.0.1:{port}"
        try:
            _launch_dedicated_browser(port)
        except Exception as e:
            last_err = e
            continue
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                return _ws_from_cdp_http_url(cdp_url, timeout=1)
            except Exception as e:
                last_err = e
                time.sleep(0.25)
    raise RuntimeError(f"dedicated automation browser did not expose CDP: {last_err}")


async def _start_cdp_client(url, open_timeout=None):
    """Start CDPClient with a longer websocket open timeout for Chrome's Allow popup."""
    client = CDPClient(url)
    connect_kwargs = {
        "max_size": client.max_ws_frame_size,
        "open_timeout": _cdp_open_timeout_seconds() if open_timeout is None else open_timeout,
    }
    if client.additional_headers:
        connect_kwargs["additional_headers"] = client.additional_headers
    client.ws = await websockets.connect(client.url, **connect_kwargs)
    client._message_handler_task = asyncio.create_task(client._handle_messages())
    return client


async def _silent(coro):
    try:
        await coro
    except Exception:
        pass


def _ws_from_devtools_active_port(http_url: str) -> str | None:
    """When /json/version returns 404 (Chrome 147+ default profile), match DevToolsActivePort by port."""
    p = urlparse(http_url)
    want_port = str(p.port) if p.port else ""
    if not want_port:
        return None
    host = p.hostname or "127.0.0.1"
    if ":" in host:  # urlparse strips IPv6 brackets; restore them for the ws:// URL
        host = f"[{host}]"
    for base in _candidate_profiles():
        try:
            active = (base / "DevToolsActivePort").read_text().splitlines()
        except (FileNotFoundError, NotADirectoryError):
            continue
        port = active[0].strip() if active else ""
        ws_path = active[1].strip() if len(active) > 1 else ""
        if port == want_port and ws_path:
            return f"ws://{host}:{port}{ws_path}"
    return None


def select_ws_url():
    if url := os.environ.get("BU_CDP_WS"):
        return url, "explicit-ws"
    if url := os.environ.get("BU_CDP_URL"):
        # HTTP DevTools endpoint (e.g. http://127.0.0.1:9333) — resolve to ws via /json/version.
        # Use this for a dedicated automation Chrome on a non-default profile, which avoids the
        # M144 "Allow remote debugging" dialog and the M136 default-profile lockdown.
        deadline = time.time() + 30
        last_err = None
        base_url = url.rstrip("/")
        while time.time() < deadline:
            try:
                return json.loads(urllib.request.urlopen(f"{base_url}/json/version", timeout=5).read())["webSocketDebuggerUrl"], "explicit-http"
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 403:
                    raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
                if e.code == 404 and (ws := _ws_from_devtools_active_port(url)):
                    return ws, "explicit-http-devtools-active-port"
                time.sleep(1)
            except Exception as e:
                last_err = e
                time.sleep(1)
        raise RuntimeError(f"BU_CDP_URL={url} unreachable after 30s: {last_err} -- is the dedicated automation Chrome running?")
    if _local_browser_mode() == "dedicated":
        log("BH_LOCAL_BROWSER_MODE=dedicated; using dedicated automation browser")
        return _dedicated_browser_ws_url(), "dedicated"
    deadline = time.time() + 30
    while time.time() < deadline:
        for base in _candidate_profiles():
            try:
                active = (base / "DevToolsActivePort").read_text().splitlines()
            except (FileNotFoundError, NotADirectoryError):
                continue
            port = active[0].strip() if active else ""
            ws_path = active[1].strip() if len(active) > 1 else ""
            if not port:
                continue
            # Resolve the live WS URL via /json/version instead of trusting the path stored
            # alongside the port in DevToolsActivePort: if Chrome was previously launched
            # with a different --user-data-dir on the same port, that file is left behind
            # with a stale browser UUID and the WS upgrade returns 404.
            try:
                return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1).read())["webSocketDebuggerUrl"], "local-http"
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
                # Chrome 147+ disables /json/* HTTP discovery on the default user-data-dir;
                # the ws path Chrome wrote to DevToolsActivePort still works once remote
                # debugging has already been allowed for this Chrome instance. In auto
                # mode we still try it first with a short startup probe so signed-in
                # Chrome sessions are reused instead of silently losing auth in the
                # dedicated browser.
                if e.code == 404 and ws_path:
                    return f"ws://127.0.0.1:{port}{ws_path}", "default-profile-direct"
            except (OSError, KeyError, ValueError):
                pass
        time.sleep(0.2)
    if browser_family_filter_active():
        log(f"skipping blind CDP port probe because BH_BROWSER_FAMILY={browser_family_mode()} is set")
    else:
        for probe_port in (9222, 9223):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{probe_port}/json/version", timeout=1) as r:
                    return json.loads(r.read())["webSocketDebuggerUrl"], "probe-http"
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
            except (OSError, KeyError, ValueError):
                continue
    if _local_browser_mode() == "auto":
        log("no reusable local CDP endpoint found; using dedicated automation browser")
        return _dedicated_browser_ws_url(), "dedicated"
    raise RuntimeError(f"DevToolsActivePort not found in {[str(p) for p in _candidate_profiles()]} for {browser_family_label()} — enable chrome://inspect/#remote-debugging, or set BU_CDP_WS for a remote browser")


def get_ws_url():
    url, _source = select_ws_url()
    return url


def stop_remote():
    if not REMOTE_ID:
        return
    try:
        key = auth.get_browser_use_api_key()
        req = urllib.request.Request(
            f"{BU_API}/browsers/{REMOTE_ID}",
            data=json.dumps({"action": "stop"}).encode(),
            method="PATCH",
            headers={"X-Browser-Use-API-Key": key, "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=15).read()
        log(f"stopped remote browser {REMOTE_ID}")
    except Exception as e:
        log(f"stop_remote failed ({REMOTE_ID}): {e}")


def is_real_page(t):
    return t["type"] == "page" and not t.get("url", "").startswith(INTERNAL)


class Daemon:
    def __init__(self):
        self.cdp = None
        self.session = None
        self.target_id = None
        self.events = deque(maxlen=BUF)
        self.dialog = None
        self.stop = None  # asyncio.Event, set inside start()

    async def attach_first_page(self):
        """Attach to a real page (or any page). Sets self.session. Returns attached target or None."""
        targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
        pages = [t for t in targets if is_real_page(t)]
        if not pages:
            # No real pages - create one instead of attaching to omnibox popup.
            tid = (await self.cdp.send_raw("Target.createTarget", {"url": "about:blank"}))["targetId"]
            log(f"no real pages found, created about:blank ({tid})")
            pages = [{"targetId": tid, "url": "about:blank", "type": "page"}]
        self.session = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": pages[0]["targetId"], "flatten": True}
        ))["sessionId"]
        self.target_id = pages[0]["targetId"]
        log(f"attached {pages[0]['targetId']} ({pages[0].get('url','')[:80]}) session={self.session}")
        await self._enable_default_domains(self.session)
        return pages[0]

    async def _enable_default_domains(self, session_id):
        """Enable Page/DOM/Runtime/Network on a CDP session.

        Used by both initial attach and set_session (called after switch_tab/
        new_tab). Without this, helpers that depend on Network.* events —
        notably wait_for_network_idle() — silently stop receiving events
        after a tab switch, because each fresh CDP session starts with all
        domains disabled.

        Runs the four enables in parallel via gather so the worst-case time is
        bounded by a single CDP round trip rather than four sequential ones —
        important on the set_session path, where the helper's IPC socket has
        a 5s read timeout.
        """
        async def enable_one(d):
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw(f"{d}.enable", session_id=session_id),
                    timeout=4,
                )
            except Exception as e:
                log(f"enable {d} on {session_id}: {e}")
        await asyncio.gather(*(enable_one(d) for d in ("Page", "DOM", "Runtime", "Network")))

    def _install_event_tap(self):
        orig = self.cdp._event_registry.handle_event
        mark_js = "if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title"

        async def tap(method, params, session_id=None):
            self.events.append({"method": method, "params": params, "session_id": session_id})
            if method == "Page.javascriptDialogOpening":
                self.dialog = params
            elif method == "Page.javascriptDialogClosed":
                self.dialog = None
            elif method in ("Page.loadEventFired", "Page.domContentEventFired"):
                asyncio.create_task(_silent(asyncio.wait_for(self.cdp.send_raw("Runtime.evaluate", {"expression": mark_js}, session_id=self.session), timeout=2)))
            return await orig(method, params, session_id)

        self.cdp._event_registry.handle_event = tap

    async def start(self):
        self.stop = asyncio.Event()
        url, source = select_ws_url()
        open_timeout = (
            _default_profile_probe_timeout_seconds()
            if source == "default-profile-direct" and _local_browser_mode() == "auto"
            else _cdp_open_timeout_seconds()
        )
        log(f"connecting to {url} (source={source}, open_timeout={open_timeout:g}s)")
        try:
            self.cdp = await _start_cdp_client(url, open_timeout=open_timeout)
        except Exception as e:
            if source == "default-profile-direct" and _local_browser_mode() == "auto":
                log(
                    "default profile direct websocket is not already permitted; "
                    f"falling back to dedicated automation browser after {e}"
                )
                url = _dedicated_browser_ws_url()
                open_timeout = _cdp_open_timeout_seconds()
                log(f"connecting to {url} (source=dedicated-fallback, open_timeout={open_timeout:g}s)")
                self.cdp = await _start_cdp_client(url, open_timeout=open_timeout)
                await self.attach_first_page()
                self._install_event_tap()
                return
            if os.environ.get("BU_CDP_WS"):
                raise RuntimeError(
                    f"CDP WS handshake failed after {open_timeout:g}s: {e} -- remote browser WebSocket connection failed. "
                    "This can happen when network policy blocks the connection, the WS URL is wrong or expired, or the remote endpoint is down. "
                    "If you use Browser Use cloud, verify auth and get a fresh URL via start_remote_daemon()."
                )
            raise RuntimeError(f"CDP WS handshake failed after {open_timeout:g}s: {e} -- click Allow in Chrome if prompted, then retry")
        await self.attach_first_page()
        self._install_event_tap()

    async def handle(self, req):
        # Token guard for Windows TCP loopback: any local process can otherwise
        # connect and issue CDP commands. expected_token() is None on POSIX so
        # this check is a no-op there (AF_UNIX + chmod 600 is the boundary).
        expected = ipc.expected_token()
        if expected is not None and req.get("token") != expected:
            return {"error": "unauthorized"}
        meta = req.get("meta")
        # Liveness probe — lets clients confirm the listener is actually this
        # daemon and not an unrelated process that reused our port post-crash.
        # `pid` lets restart_daemon() verify the live daemon's identity before
        # signaling — protects against SIGTERM-by-stale-pid-file after PID reuse.
        if meta == "ping":        return {"pong": True, "pid": os.getpid()}
        if meta == "drain_events":
            out = list(self.events); self.events.clear()
            return {"events": out}
        if meta == "session":     return {"session_id": self.session}
        if meta == "current_tab":
            # Resolve the attached page's target info server-side. Helpers can't
            # send Target.getTargetInfo themselves: daemon strips session_id for
            # any Target.* method (browser-level call), and without a targetId
            # Chrome silently returns the *browser* target.
            if not self.target_id:
                return {"error": "not_attached"}
            try:
                info = (await self.cdp.send_raw("Target.getTargetInfo", {"targetId": self.target_id}))["targetInfo"]
            except Exception:
                return {"error": "cdp_disconnected"}
            return {"targetId": info.get("targetId"), "url": info.get("url", ""), "title": info.get("title", "")}
        if meta == "connection_status":
            if not self.target_id:
                return {"error": "not_attached"}
            try:
                info = (await self.cdp.send_raw("Target.getTargetInfo", {"targetId": self.target_id}))["targetInfo"]
            except Exception:
                return {"error": "cdp_disconnected"}
            page = None
            if is_real_page(info):
                page = {
                    "targetId": info.get("targetId"),
                    "title": info.get("title") or "(untitled)",
                    "url": info.get("url") or "",
                }
            return {"target_id": self.target_id, "session_id": self.session, "page": page}
        if meta == "set_session":
            old_session = self.session
            self.session = req.get("session_id")
            self.target_id = req.get("target_id") or self.target_id
            # Run the old-session Network.disable (defense in depth — keeps
            # background-tab traffic out of the global event buffer; the
            # consumer-side filter in wait_for_network_idle is the actual
            # correctness gate) in parallel with the four enables on the new
            # session. Different sessions, independent CDP requests. Keeps
            # the synchronous reply under the helper's 5s IPC read timeout
            # even on a remote daemon — sequentially these would have stacked
            # to ~22s worst case.
            tasks = []
            if old_session and old_session != self.session:
                async def disable_old():
                    try:
                        await asyncio.wait_for(
                            self.cdp.send_raw("Network.disable", session_id=old_session),
                            timeout=2,
                        )
                    except Exception: pass
                tasks.append(disable_old())
            tasks.append(self._enable_default_domains(self.session))
            await asyncio.gather(*tasks)
            # 🐴 tab-marker title prefix is purely cosmetic — fire-and-forget so
            # it doesn't add to the synchronous IPC budget.
            asyncio.create_task(_silent(asyncio.wait_for(
                self.cdp.send_raw(
                    "Runtime.evaluate",
                    {"expression": "if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title"},
                    session_id=self.session,
                ),
                timeout=2,
            )))
            return {"session_id": self.session}
        if meta == "pending_dialog": return {"dialog": self.dialog}
        if meta == "shutdown":    self.stop.set(); return {"ok": True}

        method = req["method"]
        params = req.get("params") or {}
        # Browser-level Target.* calls must not use a session (stale or otherwise).
        # For everything else, explicit session in req wins; else default.
        sid = None if method.startswith("Target.") else (req.get("session_id") or self.session)
        try:
            return {"result": await self.cdp.send_raw(method, params, session_id=sid)}
        except Exception as e:
            msg = str(e)
            if "Session with given id not found" in msg and sid == self.session and sid:
                log(f"stale session {sid}, re-attaching")
                if await self.attach_first_page():
                    return {"result": await self.cdp.send_raw(method, params, session_id=self.session)}
            return {"error": msg}


async def serve(d):
    async def handler(reader, writer):
        try:
            line = await reader.readline()
            if not line: return
            resp = await d.handle(json.loads(line))
            writer.write((json.dumps(resp, default=str) + "\n").encode())
            await writer.drain()
        except Exception as e:
            log(f"conn: {e}")
            try:
                writer.write((json.dumps({"error": str(e)}) + "\n").encode())
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()

    serve_task = asyncio.create_task(ipc.serve(NAME, handler))
    stop_task = asyncio.create_task(d.stop.wait())
    await asyncio.sleep(0.05)  # let serve() bind so sock_addr() resolves to the live endpoint
    log(f"listening on {ipc.sock_addr(NAME)} (name={NAME}, remote={REMOTE_ID or 'local'})")
    try:
        await asyncio.wait({serve_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        if serve_task.done(): await serve_task  # surfaces a serve crash
    finally:
        for t in (serve_task, stop_task):
            t.cancel()
            try: await t
            except (asyncio.CancelledError, Exception): pass
        ipc.cleanup_endpoint(NAME)


async def main():
    d = Daemon()
    await d.start()
    await serve(d)


def already_running():
    # Ping handshake (not a bare connect) so a stale .port file + port reuse
    # after a daemon crash doesn't make us mistake an unrelated listener for ours.
    return ipc.ping(NAME, timeout=1.0)


if __name__ == "__main__":
    if already_running():
        print(f"daemon already running on {SOCK}", file=sys.stderr)
        sys.exit(0)
    open(LOG, "w").close()
    open(PID, "w").write(str(os.getpid()))
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log(f"fatal: {e}")
        sys.exit(1)
    finally:
        stop_remote()
        try: os.unlink(PID)
        except FileNotFoundError: pass
