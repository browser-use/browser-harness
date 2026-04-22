"""CDP WS holder + Unix socket relay. One daemon per BU_NAME."""

import asyncio
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
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
SOCK = f"/tmp/bu-{NAME}.sock"
LOG = f"/tmp/bu-{NAME}.log"
PID = f"/tmp/bu-{NAME}.pid"
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
    Path.home() / ".config/BraveSoftware/Brave-Browser",
    Path.home() / ".config/microsoft-edge",
    Path.home() / ".config/microsoft-edge-beta",
    Path.home() / ".config/microsoft-edge-dev",
    Path.home() / ".var/app/org.chromium.Chromium/config/chromium",
    Path.home() / ".var/app/com.google.Chrome/config/google-chrome",
    Path.home() / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser",
    Path.home() / ".var/app/com.microsoft.Edge/config/microsoft-edge",
    Path.home() / "AppData/Local/Google/Chrome/User Data",
    Path.home() / "AppData/Local/Chromium/User Data",
    Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge Beta/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge Dev/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge SxS/User Data",
]
INTERNAL = (
    "chrome://",
    "chrome-untrusted://",
    "devtools://",
    "chrome-extension://",
    "about:",
)
BU_API = "https://api.browser-use.com/api/v3"
REMOTE_ID = os.environ.get("BU_BROWSER_ID")
API_KEY = os.environ.get("BROWSER_USE_API_KEY")


def log(msg):
    with open(LOG, "a") as handle:
        handle.write(f"{msg}\n")


def get_ws_url():
    if url := os.environ.get("BU_CDP_WS"):
        return url
    for base in PROFILES:
        try:
            port, path = (base / "DevToolsActivePort").read_text().strip().split("\n", 1)
        except (FileNotFoundError, NotADirectoryError, ValueError):
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
    raise RuntimeError(
        f"DevToolsActivePort not found in {[str(p) for p in PROFILES]} — enable chrome://inspect/#remote-debugging in Chrome, Brave, or Edge, or set BU_CDP_WS for a remote browser"
    )


def stop_remote():
    if not REMOTE_ID or not API_KEY:
        return
    try:
        req = urllib.request.Request(
            f"{BU_API}/browsers/{REMOTE_ID}",
            data=json.dumps({"action": "stop"}).encode(),
            method="PATCH",
            headers={"X-Browser-Use-API-Key": API_KEY, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        log(f"stopped remote browser {REMOTE_ID}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log(f"stop_remote failed ({REMOTE_ID}): {e}")
    except Exception as e:
        log(f"stop_remote unexpected error ({REMOTE_ID}): {e}")


def is_real_page(t):
    if not isinstance(t, dict):
        return False
    return t.get("type") == "page" and not t.get("url", "").startswith(INTERNAL)


class Daemon:
    def __init__(self):
        self.cdp = None
        self.session = None
        self.events = deque(maxlen=BUF)
        self.dialog = None
        self.stop_event = None  # asyncio.Event, set inside start()
        self._original_handler = None

    async def attach_first_page(self):
        """Attach to a real page (or any page). Sets self.session. Returns attached target."""
        info = await self.cdp.send_raw("Target.getTargets")
        targets = info.get("targetInfos") if isinstance(info, dict) else None
        if not isinstance(targets, list):
            targets = []
        pages = [t for t in targets if is_real_page(t)]

        if not pages:
            created = await self.cdp.send_raw("Target.createTarget", {"url": "about:blank"})
            tid = created.get("targetId") if isinstance(created, dict) else None
            if not tid:
                raise RuntimeError("Target.createTarget did not return a targetId")
            log(f"no real pages found, created about:blank ({tid})")
            pages = [{"targetId": tid, "url": "about:blank", "type": "page"}]

        attached = await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": pages[0]["targetId"], "flatten": True}
        )
        self.session = attached.get("sessionId") if isinstance(attached, dict) else None
        if not self.session:
            raise RuntimeError(f"Failed to attach session for target {pages[0]['targetId']}")

        log(
            f"attached {pages[0]['targetId']} ({pages[0].get('url', '')[:80]}) session={self.session}"
        )
        for d in ("Page", "DOM", "Runtime", "Network"):
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw(f"{d}.enable", session_id=self.session), timeout=5
                )
            except Exception as e:
                log(f"enable {d}: {e}")
        return pages[0]

    async def start(self):
        self.stop_event = asyncio.Event()
        url = get_ws_url()
        log(f"connecting to {url}")
        self.cdp = CDPClient(url)
        try:
            await self.cdp.start()
        except Exception as e:
            raise RuntimeError(
                f"CDP WS handshake failed: {e} -- click Allow in the browser if prompted, then retry"
            )
        await self.attach_first_page()

        original_handler = self.cdp._event_registry.handle_event
        self._original_handler = original_handler
        mark_js = "if(!document.title.startsWith('\\U0001F7E2'))document.title='\\U0001F7E2 '+document.title"

        async def tap(method, params, session_id=None):
            self.events.append({"method": method, "params": params, "session_id": session_id})
            if method == "Page.javascriptDialogOpening":
                self.dialog = params
            elif method == "Page.javascriptDialogClosed":
                self.dialog = None
            elif method in ("Page.loadEventFired", "Page.domContentEventFired"):
                try:
                    await asyncio.wait_for(
                        self.cdp.send_raw(
                            "Runtime.evaluate",
                            {"expression": mark_js},
                            session_id=self.session,
                        ),
                        timeout=2,
                    )
                except Exception:
                    pass
            return await original_handler(method, params, session_id)

        self.cdp._event_registry.handle_event = tap

    async def stop(self):
        if self.cdp is None:
            return
        if self._original_handler is not None:
            self.cdp._event_registry.handle_event = self._original_handler
            self._original_handler = None
        closer = getattr(self.cdp, "stop", None)
        if callable(closer):
            try:
                result = closer()
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                log(f"cdp stop failed: {e}")
        self.cdp = None

    async def handle(self, req):
        if not isinstance(req, dict):
            return {"error": "request must be a JSON object"}

        meta = req.get("meta")
        if meta == "drain_events":
            out = list(self.events)
            self.events.clear()
            return {"events": out}

        if meta == "session":
            return {"session_id": self.session}

        if meta == "set_session":
            session_id = req.get("session_id")
            if not session_id:
                return {"error": "missing session_id"}
            self.session = session_id
            try:
                await asyncio.wait_for(self.cdp.send_raw("Page.enable", session_id=self.session), timeout=3)
                await asyncio.wait_for(
                    self.cdp.send_raw(
                        "Runtime.evaluate",
                        {
                            "expression": "if(!document.title.startsWith('\\U0001F7E2'))document.title='\\U0001F7E2 '+document.title"
                        },
                        session_id=self.session,
                    ),
                    timeout=2,
                )
            except Exception:
                pass
            return {"session_id": self.session}

        if meta == "pending_dialog":
            return {"dialog": self.dialog}

        if meta == "shutdown":
            if self.stop_event:
                self.stop_event.set()
            return {"ok": True}

        method = req.get("method")
        if not method:
            return {"error": "missing method"}

        params = req.get("params") or {}
        # Browser-level Target.* calls must not use a session.
        sid = None if method.startswith("Target.") else (req.get("session_id") or self.session)
        try:
            return {"result": await self.cdp.send_raw(method, params, session_id=sid)}
        except Exception as e:
            msg = str(e)
            if "Session with given id not found" in msg and sid == self.session and sid:
                log(f"stale session {sid}, re-attaching")
                if await self.attach_first_page():
                    return {
                        "result": await self.cdp.send_raw(method, params, session_id=self.session)
                    }
            return {"error": msg}


async def serve(d):
    if os.path.exists(SOCK):
        os.unlink(SOCK)

    async def handler(reader, writer):
        try:
            line = await reader.readline()
            if not line:
                return
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
            await writer.wait_closed()

    server = await asyncio.start_unix_server(handler, path=SOCK)
    os.chmod(SOCK, 0o600)
    log(f"listening on {SOCK} (name={NAME}, remote={REMOTE_ID or 'local'})")

    try:
        async with server:
            await d.stop_event.wait()
    finally:
        server.close()
        await server.wait_closed()


async def main():
    d = Daemon()
    await d.start()
    try:
        await serve(d)
    finally:
        await d.stop()


def already_running():
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(SOCK)
        s.close()
        return True
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout):
        return False


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
        try:
            os.unlink(PID)
        except FileNotFoundError:
            pass
        try:
            os.unlink(SOCK)
        except FileNotFoundError:
            pass
