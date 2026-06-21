"""CDP WS holder + IPC relay (Unix socket on POSIX, TCP loopback on Windows). One daemon per BU_NAME."""
import asyncio, json, os, socket, sys, urllib.request
from collections import deque
from pathlib import Path
from uuid import uuid4

from . import _ipc as ipc
from .browser import get_browser_endpoint, open_configured_profile_marker, open_local_profile_marker
from cdp_use.client import CDPClient


def _load_env():
    repo_root = Path(__file__).resolve().parents[2]
    workspace = Path(os.environ.get("BH_AGENT_WORKSPACE", repo_root / "agent-workspace")).expanduser()
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
INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")
PROFILE_MARKER_URL_PREFIX = "https://browser-use.com/browser-use-profile-target/"
BU_API = "https://api.browser-use.com/api/v3"
REMOTE_ID = os.environ.get("BU_BROWSER_ID")
API_KEY = os.environ.get("BROWSER_USE_API_KEY")


def log(msg):
    open(LOG, "a").write(f"{msg}\n")


async def _silent(coro):
    try:
        await coro
    except Exception:
        pass


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


def is_page_target(t):
    return t.get("type") == "page"


def is_profile_marker_target(t):
    return is_page_target(t) and "browser-use-profile-target" in t.get("url", "")


def profile_marker_target_url(marker):
    return f"{PROFILE_MARKER_URL_PREFIX}{marker}"


def target_url_contains_marker(t, marker):
    return is_profile_marker_target(t) and marker in t.get("url", "")


def stale_browser_context_error(msg):
    lower = str(msg).lower()
    return "failed to find browser context with id" in lower or ("browser context" in lower and "not found" in lower)


def select_initial_page_target(targets):
    real = [t for t in targets if is_real_page(t) and not is_profile_marker_target(t)]
    if real:
        return real[0]
    pages = [t for t in targets if is_page_target(t)]
    return pages[0] if pages else None


class Daemon:
    def __init__(self):
        self.cdp = None
        self.session = None
        self.target_id = None
        self.events = deque(maxlen=BUF)
        self.dialog = None
        self.stop = None  # asyncio.Event, set inside start()
        self.managed_browser = None
        self.preferred_target_marker = os.environ.get("BH_TARGET_MARKER") or None
        self.preferred_browser_context_id = None

    async def attach_first_page(self):
        """Attach to a real page (or any page). Sets self.session. Returns attached target or None."""
        target = None
        attached_marker = False
        if self.preferred_target_marker:
            deadline = asyncio.get_running_loop().time() + 8
            while asyncio.get_running_loop().time() < deadline:
                targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
                target = next(
                    (t for t in targets if target_url_contains_marker(t, self.preferred_target_marker)),
                    None,
                )
                if target:
                    self.preferred_target_marker = None
                    self.preferred_browser_context_id = target.get("browserContextId")
                    attached_marker = True
                    break
                await asyncio.sleep(0.15)
            if target is None:
                raise RuntimeError("selected Chrome profile target did not appear; refusing to attach to an arbitrary existing profile")
        else:
            targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
            target = select_initial_page_target(targets)
            self.preferred_browser_context_id = None
        if not target:
            # No real pages — create one instead of attaching to omnibox popup
            params = {"url": "about:blank"}
            if self.preferred_browser_context_id:
                params["browserContextId"] = self.preferred_browser_context_id
            tid = (await self.cdp.send_raw("Target.createTarget", params))["targetId"]
            log(f"no real pages found, created about:blank ({tid})")
            target = {"targetId": tid, "url": "about:blank", "type": "page"}
        self.session = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": target["targetId"], "flatten": True}
        ))["sessionId"]
        self.target_id = target["targetId"]
        log(f"attached {target['targetId']} ({target.get('url','')[:80]}) session={self.session}")
        await self._enable_default_domains(self.session)
        if attached_marker:
            log("profile marker attached; waiting for first task target before closing marker")
        return target

    async def close_profile_marker_targets(self, browser_context_id=None, keep_target_id=None):
        try:
            targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
        except Exception:
            return
        for target in targets:
            if not is_profile_marker_target(target):
                continue
            if browser_context_id and target.get("browserContextId") != browser_context_id:
                continue
            target_id = target.get("targetId")
            if not target_id or target_id == keep_target_id:
                continue
            try:
                await self.cdp.send_raw("Target.closeTarget", {"targetId": target_id})
            except Exception:
                pass

    async def target_context_id(self, target_id):
        info = (await self.cdp.send_raw("Target.getTargetInfo", {"targetId": target_id}))["targetInfo"]
        return info.get("browserContextId")

    async def ensure_target_context(self, target_id):
        if not self.preferred_browser_context_id:
            return
        actual = await self.target_context_id(target_id)
        if actual and actual != self.preferred_browser_context_id:
            raise RuntimeError("refusing to switch to a target from a different Chrome profile context")

    async def reacquire_profile_context(self):
        opened = await asyncio.to_thread(open_configured_profile_marker)
        if not opened:
            raise RuntimeError("cannot recover stale Chrome profile context: no default profile is configured")
        marker = opened["marker"]
        deadline = asyncio.get_running_loop().time() + 8
        while asyncio.get_running_loop().time() < deadline:
            targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
            target = next((t for t in targets if target_url_contains_marker(t, marker)), None)
            if target:
                self.preferred_browser_context_id = target.get("browserContextId")
                log(f"reacquired profile context {self.preferred_browser_context_id or '(none)'} via marker {marker}")
                return target
            await asyncio.sleep(0.15)
        raise RuntimeError("selected Chrome profile target did not appear while recovering stale browser context")

    async def verify_profile_target(self):
        """Re-anchor the controlled target into the selected profile if it has
        drifted to another context or closed. The daemon is reused across CLI
        commands, so without this it could keep driving a tab in the wrong
        profile. Uses only Target.* calls over the existing websocket, so it
        can't trigger Chrome's debugging popup. If the target still exists in the
        selected context it's left as-is (we keep the same tab across commands).
        """
        if not self.preferred_browser_context_id:
            return {"status": "no-profile"}
        try:
            targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
        except Exception as e:
            return {"status": "cdp_disconnected", "reason": str(e)}
        by_id = {t.get("targetId"): t for t in targets}
        current = by_id.get(self.target_id) if self.target_id else None
        if current and current.get("browserContextId") == self.preferred_browser_context_id:
            return {"status": "ok", "target_id": self.target_id}
        previous = self.target_id
        # Prefer a real page in the selected context, then any non-marker page;
        # if none, re-open a marker to reacquire the context (closed window).
        in_ctx = [
            t for t in targets
            if is_page_target(t) and t.get("browserContextId") == self.preferred_browser_context_id
        ]
        chosen = next((t for t in in_ctx if is_real_page(t) and not is_profile_marker_target(t)), None)
        chosen = chosen or next((t for t in in_ctx if not is_profile_marker_target(t)), None)
        if chosen is None:
            try:
                target = await self.reacquire_profile_context()
            except Exception as e:
                return {"status": "context-stale", "previous": previous, "reason": str(e)}
            chosen = target
        self.session = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": chosen["targetId"], "flatten": True}
        ))["sessionId"]
        self.target_id = chosen["targetId"]
        await self._enable_default_domains(self.session)
        await self.close_profile_marker_targets(self.preferred_browser_context_id, keep_target_id=self.target_id)
        reason = "target-gone" if previous and previous not in by_id else "wrong-context"
        log(f"reanchored controlled target {previous} -> {self.target_id} ({reason}) in profile context {self.preferred_browser_context_id}")
        return {"status": "reanchored", "target_id": self.target_id, "previous": previous, "reason": reason}

    async def recover_controlled_session(self):
        """Refresh the CDP session after a stale-session error. Re-attaches the
        same controlled target when it's still open in the selected context (so
        we don't switch tabs on a dropped session); re-anchors only when it's
        gone or drifted. Returns True when a usable session was restored.
        """
        if self.target_id:
            try:
                targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
            except Exception:
                targets = []
            current = next((t for t in targets if t.get("targetId") == self.target_id), None)
            in_context = current is not None and (
                not self.preferred_browser_context_id
                or current.get("browserContextId") == self.preferred_browser_context_id
            )
            if in_context:
                try:
                    self.session = (await self.cdp.send_raw(
                        "Target.attachToTarget", {"targetId": self.target_id, "flatten": True}
                    ))["sessionId"]
                    await self._enable_default_domains(self.session)
                    log(f"reattached same controlled target {self.target_id} session={self.session}")
                    return True
                except Exception as e:
                    log(f"reattach same target {self.target_id} failed: {e}")
        if self.preferred_browser_context_id:
            res = await self.verify_profile_target()
            return res.get("status") in ("ok", "reanchored")
        return bool(await self.attach_first_page())

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

    async def start(self):
        self.stop = asyncio.Event()
        endpoint = get_browser_endpoint()
        self.managed_browser = endpoint.managed
        if endpoint.target_marker:
            self.preferred_target_marker = endpoint.target_marker
        log(f"connecting to {endpoint.ws_url} (kind={endpoint.kind}, http={endpoint.http_url or ''})")
        self.cdp = CDPClient(endpoint.ws_url)
        try:
            await self.cdp.start()
        except Exception as e:
            if os.environ.get("BU_CDP_WS"):
                raise RuntimeError(
                    f"CDP WS handshake failed: {e} -- remote browser WebSocket connection failed. "
                    "This can happen when network policy blocks the connection, the WS URL is wrong or expired, or the remote endpoint is down. "
                    "If you use Browser Use cloud, verify BROWSER_USE_API_KEY and get a fresh URL via start_remote_daemon()."
                )
            raise RuntimeError(f"CDP WS handshake failed: {e}")
        # Open the marker now that the websocket is live, so a failed connection
        # leaves no stray tab. profile-target pre-opens its own (target_marker).
        if not self.preferred_target_marker and endpoint.marker_profile_id:
            opened = await asyncio.to_thread(open_local_profile_marker, endpoint.marker_profile_id)
            self.preferred_target_marker = opened["marker"]
            log(f"opened profile marker {opened['marker']} in {endpoint.marker_profile_id} after connect")
        await self.attach_first_page()
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
        if meta == "capabilities":
            return {"capabilities": ["create_target", "profile_marker", "context_guard", "verify_profile"]}
        if meta == "verify_profile":
            return await self.verify_profile_target()
        if meta == "drain_events":
            out = list(self.events); self.events.clear()
            return {"events": out}
        if meta == "session":     return {"session_id": self.session}
        if meta == "profile_marker":
            marker = req.get("marker") or uuid4().hex
            self.preferred_target_marker = marker
            return {"marker": marker, "url": profile_marker_target_url(marker)}
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
            new_target_id = req.get("target_id") or self.target_id
            if new_target_id:
                try:
                    await self.ensure_target_context(new_target_id)
                except Exception as e:
                    return {"error": str(e)}
            self.session = req.get("session_id")
            self.target_id = new_target_id
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
        if meta == "create_target":
            params = {"url": req.get("url") or "about:blank"}
            if self.preferred_browser_context_id:
                params["browserContextId"] = self.preferred_browser_context_id
            for attempt in (0, 1):
                try:
                    target_id = (await self.cdp.send_raw("Target.createTarget", params))["targetId"]
                    await self.close_profile_marker_targets(self.preferred_browser_context_id, keep_target_id=target_id)
                    return {"targetId": target_id}
                except Exception as e:
                    if attempt == 0 and self.preferred_browser_context_id and stale_browser_context_error(e):
                        try:
                            await self.reacquire_profile_context()
                        except Exception as recover_error:
                            return {"error": f"{e}; failed to recover selected Chrome profile context: {recover_error}"}
                        params = {"url": req.get("url") or "about:blank"}
                        if self.preferred_browser_context_id:
                            params["browserContextId"] = self.preferred_browser_context_id
                        continue
                    return {"error": str(e)}
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
                if await self.recover_controlled_session():
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
    try:
        await d.start()
        await serve(d)
    finally:
        if d.managed_browser:
            d.managed_browser.stop()


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
