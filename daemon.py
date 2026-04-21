"""CDP WS holder + IPC relay (Unix domain socket / TCP loopback). One daemon per BU_NAME."""
import asyncio, json, os, secrets, socket, sys, tempfile, time, urllib.request
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

IS_WIN = sys.platform == "win32"
NAME = os.environ.get("BU_NAME", "default")


def _tmp(suffix):
    # Unix keeps the fixed /tmp/ path so existing users (and macOS AF_UNIX
    # path-length limits) see zero change. Windows has no /tmp, so we fall
    # back to the per-user temp dir.
    if IS_WIN:
        return os.path.join(tempfile.gettempdir(), f"bu-{NAME}.{suffix}")
    return f"/tmp/bu-{NAME}.{suffix}"


# On Unix we serve on AF_UNIX at SOCK. On Windows AF_UNIX is unavailable,
# so we bind TCP loopback on an ephemeral port and write it to PORT_FILE;
# clients read that file to find us.
SOCK = None if IS_WIN else _tmp("sock")
PORT_FILE = _tmp("port") if IS_WIN else None
# On Windows the IPC channel is TCP loopback, which any local process can
# dial. A shared-secret token, written to a file the daemon owns and read by
# legitimate clients, gates every request so unrelated local processes can't
# issue CDP / shutdown commands. Unix gets this for free via AF_UNIX 0600.
TOKEN_FILE = _tmp("token") if IS_WIN else None
TOKEN = secrets.token_hex(16) if IS_WIN else None
LOG = _tmp("log")
PID = _tmp("pid")
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


def log(msg):
    open(LOG, "a").write(f"{msg}\n")


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
        # On Windows the TCP loopback has no kernel-level caller auth, so
        # every request must carry the shared-secret token. Use a constant-
        # time compare so a local attacker can't time-probe the token.
        if IS_WIN and not secrets.compare_digest(str(req.get("token", "")), TOKEN):
            return {"error": "unauthorized"}
        meta = req.get("meta")
        if meta == "ping":        return {"ok": True}
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

    if IS_WIN:
        # TCP loopback with a shared-secret token (TOKEN_FILE) gating every
        # request. Without the token an unrelated local process that dials
        # the port is rejected with {"error":"unauthorized"}. Unix gets
        # caller isolation from AF_UNIX 0600 and does not need a token.
        server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]
        # Atomic writes (write tmp + os.replace) so concurrent readers never
        # see a truncated file. Write TOKEN_FILE before PORT_FILE: a client
        # discovers the daemon via PORT_FILE, so the token must already be
        # on disk by the time anyone can find us.
        tmp_tok = TOKEN_FILE + ".tmp"
        open(tmp_tok, "w").write(TOKEN)
        os.replace(tmp_tok, TOKEN_FILE)
        tmp_port = PORT_FILE + ".tmp"
        open(tmp_port, "w").write(str(port))
        os.replace(tmp_port, PORT_FILE)
        log(f"listening on 127.0.0.1:{port} (name={NAME}, remote={REMOTE_ID or 'local'})")
    else:
        if os.path.exists(SOCK):
            os.unlink(SOCK)
        server = await asyncio.start_unix_server(handler, path=SOCK)
        os.chmod(SOCK, 0o600)
        log(f"listening on {SOCK} (name={NAME}, remote={REMOTE_ID or 'local'})")
    async with server:
        await d.stop.wait()


async def main():
    d = Daemon()
    await d.start()
    await serve(d)


def already_running():
    # On Windows a bare TCP connect isn't proof the port belongs to our
    # daemon — a reused ephemeral port on a stale PORT_FILE would answer
    # too, and we'd silently skip starting. Send an authenticated ping and
    # only treat the daemon as running if it replies with our token.
    try:
        if IS_WIN:
            port = int(open(PORT_FILE).read().strip())
            token = open(TOKEN_FILE).read().strip()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.sendall((json.dumps({"meta": "ping", "token": token}) + "\n").encode())
            data = b""
            while not data.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk: break
                data += chunk
            s.close()
            return bool(data) and json.loads(data).get("ok") is True
        else:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(1)
            s.connect(SOCK)
            s.close(); return True
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout, ValueError, OSError, json.JSONDecodeError):
        return False


if __name__ == "__main__":
    if already_running():
        print(f"daemon already running (name={NAME})", file=sys.stderr)
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
        for f in (PID, PORT_FILE, TOKEN_FILE) if IS_WIN else (PID,):
            try: os.unlink(f)
            except (FileNotFoundError, TypeError): pass
