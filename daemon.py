"""CDP WS holder + local socket relay. One daemon per BU_NAME."""
import asyncio, json, os, socket, sys, tempfile, time, urllib.request
from collections import deque
from pathlib import Path

from cdp_use.client import CDPClient


def _load_env():
    p = Path(__file__).parent / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

NAME = os.environ.get("BU_NAME", "default")
TMPDIR = Path(tempfile.gettempdir())
UNIX_DIR = Path("/tmp")
TRANSPORT = os.environ.get("BU_DAEMON_TRANSPORT", "auto").strip().lower()
if TRANSPORT not in {"auto", "unix", "tcp"}:
    raise RuntimeError(f"unsupported BU_DAEMON_TRANSPORT={TRANSPORT!r}; expected auto, unix, or tcp")
if TRANSPORT == "unix" and not hasattr(socket, "AF_UNIX"):
    raise RuntimeError("BU_DAEMON_TRANSPORT=unix requires AF_UNIX support")
USE_UNIX = TRANSPORT == "unix" or (TRANSPORT == "auto" and hasattr(socket, "AF_UNIX") and os.name != "nt")
CURRENT_TRANSPORT = "unix" if USE_UNIX else "tcp"
BUF = 500
PROFILES = [
    Path.home() / "Library/Application Support/Google/Chrome",
    Path.home() / "Library/Application Support/Microsoft Edge",
    Path.home() / "Library/Application Support/Microsoft Edge Beta",
    Path.home() / "Library/Application Support/Microsoft Edge Dev",
    Path.home() / "Library/Application Support/Microsoft Edge Canary",
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
    Path.home() / "AppData/Local/Chromium/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge Beta/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge Dev/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge SxS/User Data",
]
INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")
BU_API = "https://api.browser-use.com/api/v3"
REMOTE_ID = os.environ.get("BU_BROWSER_ID")
API_KEY = os.environ.get("BROWSER_USE_API_KEY")


def _metadata_dir():
    if os.name == "nt":
        return TMPDIR
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        return Path(xdg_runtime) / "browser-harness"
    return Path.home() / ".cache" / "browser-harness"


def _ensure_metadata_dir():
    meta = _metadata_dir()
    meta.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(meta, 0o700)
        except OSError:
            pass
    return meta


def _supported_transports():
    if hasattr(socket, "AF_UNIX"):
        return ("unix", "tcp")
    return ("tcp",)


def _paths(name=None, transport=None):
    transport = transport or CURRENT_TRANSPORT
    n = name or NAME
    meta = _metadata_dir()
    if transport == "unix":
        base = UNIX_DIR / f"bu-{n}"
        return str(base) + ".sock", str(meta / f"bu-{n}.unix.pid"), None, str(meta / f"bu-{n}.unix.log")
    if transport == "tcp":
        base = meta / f"bu-{n}.tcp"
        return None, str(base) + ".pid", str(base) + ".port", str(base) + ".log"
    raise RuntimeError(f"unsupported transport {transport!r}")


SOCK, PID, PORT, LOG = _paths()


def log(msg):
    open(LOG, "a").write(f"{msg}\n")


def _connect_transport(transport, timeout=1):
    sock, _, port_path, _ = _paths(transport=transport)
    if transport == "unix":
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(sock)
        return s
    try:
        port = int(Path(port_path).read_text().strip())
    except (OSError, ValueError):
        raise FileNotFoundError(port_path)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(("127.0.0.1", port))
    return s


def _transport_alive(transport):
    try:
        _, pid_path, port_path, _ = _paths(transport=transport)
        if transport == "tcp" and pid_path:
            try:
                pid = int(Path(pid_path).read_text().strip())
                os.kill(pid, 0)
            except (OSError, ValueError):
                return False
        s = _connect_transport(transport)
        s.close()
        return True
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout, OSError):
        return False


def _live_transports():
    return [transport for transport in _supported_transports() if _transport_alive(transport)]


def get_ws_url():
    if url := os.environ.get("BU_CDP_WS"):
        return url
    for base in PROFILES:
        try:
            port, path = (base / "DevToolsActivePort").read_text().strip().split("\n", 1)
        except (FileNotFoundError, NotADirectoryError):
            continue
        deadline = time.time() + 30
        while True:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.settimeout(1)
            try:
                probe.connect(("127.0.0.1", int(port.strip())))
                break
            except OSError:
                if time.time() >= deadline:
                    raise RuntimeError(
                        f"Chrome's remote-debugging page is open, but DevTools is not live yet on 127.0.0.1:{port.strip()} — if Chrome opened a profile picker, choose your normal profile first, then tick the checkbox and click Allow if shown"
                    )
                time.sleep(1)
            finally:
                probe.close()
        return f"ws://127.0.0.1:{port.strip()}{path.strip()}"
    raise RuntimeError(f"DevToolsActivePort not found in {[str(p) for p in PROFILES]} — enable chrome://inspect/#remote-debugging, or set BU_CDP_WS for a remote browser")


def stop_remote():
    if not REMOTE_ID or not API_KEY: return
    try:
        req = urllib.request.Request(
            f"{BU_API}/browsers/{REMOTE_ID}",
            data=json.dumps({"action": "stop"}).encode(),
            method="PATCH",
            headers={"X-Browser-Use-API-Key": API_KEY, "Content-Type": "application/json"},
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
        self.events = deque(maxlen=BUF)
        self.dialog = None
        self.stop = None  # asyncio.Event, set inside start()

    async def attach_first_page(self):
        """Attach to a real page (or any page). Sets self.session. Returns attached target or None."""
        targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
        pages = [t for t in targets if is_real_page(t)]
        if not pages:
            # No real pages — create one instead of attaching to omnibox popup
            tid = (await self.cdp.send_raw("Target.createTarget", {"url": "about:blank"}))["targetId"]
            log(f"no real pages found, created about:blank ({tid})")
            pages = [{"targetId": tid, "url": "about:blank", "type": "page"}]
        self.session = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": pages[0]["targetId"], "flatten": True}
        ))["sessionId"]
        log(f"attached {pages[0]['targetId']} ({pages[0].get('url','')[:80]}) session={self.session}")
        for d in ("Page", "DOM", "Runtime", "Network"):
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw(f"{d}.enable", session_id=self.session),
                    timeout=5
                )
            except Exception as e:
                log(f"enable {d}: {e}")
        return pages[0]

    async def start(self):
        self.stop = asyncio.Event()
        url = get_ws_url()
        log(f"connecting to {url}")
        self.cdp = CDPClient(url)
        try:
            await self.cdp.start()
        except Exception as e:
            raise RuntimeError(f"CDP WS handshake failed: {e} -- click Allow in Chrome if prompted, then retry")
        await self.attach_first_page()
        orig = self.cdp._event_registry.handle_event
        mark_js = "if(!document.title.startsWith('\U0001F7E2'))document.title='\U0001F7E2 '+document.title"
        async def tap(method, params, session_id=None):
            self.events.append({"method": method, "params": params, "session_id": session_id})
            if method == "Page.javascriptDialogOpening":
                self.dialog = params
            elif method == "Page.javascriptDialogClosed":
                self.dialog = None
            elif method in ("Page.loadEventFired", "Page.domContentEventFired"):
                try: await asyncio.wait_for(self.cdp.send_raw("Runtime.evaluate", {"expression": mark_js}, session_id=self.session), timeout=2)
                except Exception: pass
            return await orig(method, params, session_id)
        self.cdp._event_registry.handle_event = tap

    async def handle(self, req):
        meta = req.get("meta")
        if meta == "drain_events":
            out = list(self.events); self.events.clear()
            return {"events": out}
        if meta == "session":     return {"session_id": self.session}
        if meta == "set_session":
            self.session = req.get("session_id")
            try:
                await asyncio.wait_for(self.cdp.send_raw("Page.enable", session_id=self.session), timeout=3)
                await asyncio.wait_for(self.cdp.send_raw("Runtime.evaluate", {"expression": "if(!document.title.startsWith('\U0001F7E2'))document.title='\U0001F7E2 '+document.title"}, session_id=self.session), timeout=2)
            except Exception: pass
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
    _ensure_metadata_dir()
    if USE_UNIX and SOCK and os.path.exists(SOCK):
        os.unlink(SOCK)
    if not USE_UNIX and PORT and os.path.exists(PORT):
        os.unlink(PORT)

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

    if USE_UNIX:
        server = await asyncio.start_unix_server(handler, path=SOCK)
        os.chmod(SOCK, 0o600)
        listen_desc = SOCK
    else:
        server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]
        Path(PORT).write_text(str(port))
        listen_desc = f"127.0.0.1:{port}"
    log(f"listening on {listen_desc} (name={NAME}, remote={REMOTE_ID or 'local'})")
    async with server:
        await d.stop.wait()


async def main():
    d = Daemon()
    await d.start()
    await serve(d)


def already_running():
    return _live_transports()


if __name__ == "__main__":
    live = already_running()
    if live:
        print(f"daemon already running for BU_NAME {NAME!r} on {', '.join(live)} transport(s)", file=sys.stderr)
        sys.exit(0)
    _ensure_metadata_dir()
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
        try:
            if SOCK:
                os.unlink(SOCK)
        except FileNotFoundError: pass
        try:
            if PORT:
                os.unlink(PORT)
        except FileNotFoundError: pass
