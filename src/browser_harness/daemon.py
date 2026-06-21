"""CDP WS holder + IPC relay (Unix socket on POSIX, TCP loopback on Windows). One daemon per BU_NAME."""
import asyncio, json, os, socket, sys, time, urllib.error, urllib.request
from urllib.parse import urlparse
from collections import deque
from pathlib import Path

from . import _ipc as ipc
from . import local_profiles
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
API_KEY = os.environ.get("BROWSER_USE_API_KEY")


def log(msg):
    open(LOG, "a").write(f"{msg}\n")


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
    for base in PROFILES:
        try:
            active = (base / "DevToolsActivePort").read_text().splitlines()
        except (FileNotFoundError, NotADirectoryError):
            continue
        port = active[0].strip() if active else ""
        ws_path = active[1].strip() if len(active) > 1 else ""
        if port == want_port and ws_path:
            return f"ws://{host}:{port}{ws_path}"
    return None


def _explicit_cdp_configured():
    return bool(os.environ.get("BU_CDP_WS") or os.environ.get("BU_CDP_URL"))


def get_ws_url(selected_profile: local_profiles.LocalBrowserProfile | None = None):
    if url := os.environ.get("BU_CDP_WS"):
        return url
    if url := os.environ.get("BU_CDP_URL"):
        # HTTP DevTools endpoint (e.g. http://127.0.0.1:9333) — resolve to ws via /json/version.
        # Use this for a dedicated automation Chrome on a non-default profile, which avoids the
        # M144 "Allow remote debugging" dialog and the M136 default-profile lockdown.
        deadline = time.time() + 30
        last_err = None
        base_url = url.rstrip("/")
        while time.time() < deadline:
            try:
                return json.loads(urllib.request.urlopen(f"{base_url}/json/version", timeout=5).read())["webSocketDebuggerUrl"]
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 404 and (ws := _ws_from_devtools_active_port(url)):
                    return ws
                time.sleep(1)
            except Exception as e:
                last_err = e
                time.sleep(1)
        raise RuntimeError(f"BU_CDP_URL={url} unreachable after 30s: {last_err} -- is the dedicated automation Chrome running?")
    bases = [selected_profile.user_data_dir] if selected_profile else PROFILES
    deadline = time.time() + 30
    while time.time() < deadline:
        for base in bases:
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
                return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1).read())["webSocketDebuggerUrl"]
            except urllib.error.HTTPError as e:
                # Chrome 147+ disables /json/* HTTP discovery on the default user-data-dir;
                # the ws path Chrome wrote to DevToolsActivePort still works.
                if e.code == 404 and ws_path:
                    return f"ws://127.0.0.1:{port}{ws_path}"
                if e.code == 403:
                    raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
            except (OSError, KeyError, ValueError):
                pass
        time.sleep(0.2)
    if selected_profile:
        disabled = local_profiles.local_debugging_disabled_statuses()
        if disabled:
            raise RuntimeError("cdp-disabled: Chrome is open, but remote debugging is turned off. Open chrome://inspect/#remote-debugging in the selected profile and wait for user confirmation.")
        running = local_profiles.browser_process_running(selected_profile.browser_name, selected_profile.browser_path)
        state = "stale-port" if running else "browser-not-running"
        raise RuntimeError(
            f"{state}: selected profile {selected_profile.id} is not exposing a reachable local CDP endpoint; open/focus the selected profile, run local setup if needed, then retry"
        )
    for probe_port in (9222, 9223):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{probe_port}/json/version", timeout=1) as r:
                return json.loads(r.read())["webSocketDebuggerUrl"]
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
        except (OSError, KeyError, ValueError):
            continue
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
    return local_profiles.is_real_page_target(t)


class Daemon:
    def __init__(self):
        self.cdp = None
        self.session = None
        self.target_id = None
        self.selected_local_profile = None
        self.preferred_target_marker = None
        self.preferred_profile_id = None
        self.active_local_profile_id = None
        self.preferred_browser_context_id = None
        self.owned_target_ids = set()
        self.events = deque(maxlen=BUF)
        self.dialog = None
        self.stop = None  # asyncio.Event, set inside start()

    def _prepare_selected_local_profile(self):
        if _explicit_cdp_configured() or REMOTE_ID:
            return None
        profile_id = local_profiles.get_default_profile_id()
        if not profile_id:
            profiles = local_profiles.list_browser_profiles_payload()
            raise RuntimeError(
                "needs-profile: No default local Chrome profile is set. "
                "Run browser_profiles(), ask the user which profile id to use, then run browser_use_profile(id). "
                f"profiles={json.dumps(profiles, default=str)}"
            )
        profile = local_profiles.resolve_local_profile(profile_id)
        if local_profiles.remote_debugging_user_enabled(profile.user_data_dir) is False:
            raise RuntimeError(
                "cdp-disabled: Chrome remote debugging is turned off for the selected profile. "
                "Open chrome://inspect/#remote-debugging in that profile, tick the checkbox, wait for user confirmation, then retry."
            )
        opened = local_profiles.open_local_profile(profile.id, allow_marker=True)
        self.selected_local_profile = profile
        self.preferred_profile_id = profile.id
        self.preferred_target_marker = opened.get("target_marker")
        log(f"selected local profile {profile.id}; targeting={opened.get('profile_targeting')}")
        return profile

    async def _targets(self):
        return (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]

    async def _target_info(self, target_id):
        return (await self.cdp.send_raw("Target.getTargetInfo", {"targetId": target_id}))["targetInfo"]

    async def _ensure_target_browser_context(self, target_id):
        if not self.preferred_browser_context_id:
            return
        target = next((t for t in await self._targets() if t.get("targetId") == target_id), None)
        if target is None:
            raise RuntimeError("target-gone: target no longer exists")
        actual = target.get("browserContextId")
        if actual and actual != self.preferred_browser_context_id:
            raise RuntimeError("wrong-profile: refusing to switch to a target from a different Chrome profile context")

    async def _reattach_current_target(self):
        if not self.target_id:
            return False
        targets = await self._targets()
        if not any(t.get("targetId") == self.target_id for t in targets):
            raise RuntimeError("target-gone: Previous browser tab target is gone.")
        await self._ensure_target_browser_context(self.target_id)
        self.session = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": self.target_id, "flatten": True}
        ))["sessionId"]
        await self._enable_default_domains(self.session)
        return True

    async def _close_profile_marker_targets(self, browser_context_id=None, keep_target_id=None):
        try:
            targets = await self._targets()
        except Exception:
            return
        for target in targets:
            if not local_profiles.is_profile_marker_target(target):
                continue
            if browser_context_id and target.get("browserContextId") != browser_context_id:
                continue
            target_id = target.get("targetId")
            if not target_id or target_id == keep_target_id:
                continue
            await _silent(self.cdp.send_raw("Target.closeTarget", {"targetId": target_id}))

    async def _close_remote_debugging_setup_targets(self):
        try:
            targets = await self._targets()
        except Exception:
            return
        for target in targets:
            if not local_profiles.is_remote_debugging_setup_target(target):
                continue
            target_id = target.get("targetId")
            if target_id and target_id != self.target_id:
                await _silent(self.cdp.send_raw("Target.closeTarget", {"targetId": target_id}))

    def _select_work_target(self, targets, browser_context_id=None, exclude_target_ids=None):
        exclude_target_ids = set(exclude_target_ids or ())

        def in_scope(target):
            if target.get("targetId") in exclude_target_ids:
                return False
            if browser_context_id and target.get("browserContextId") != browser_context_id:
                return False
            return True

        scoped = [t for t in targets if in_scope(t)]
        return (
            next((t for t in scoped if local_profiles.is_real_page_target(t)), None)
            or next((t for t in scoped if local_profiles.is_reusable_placeholder_target(t)), None)
        )

    async def attach_first_page(self):
        """Attach to a real page (or any page). Sets self.session. Returns attached target or None."""
        attached_profile_marker = False
        attached_launched_profile = False
        attached_browser_context_id = None
        attached_profile_id = None
        page = None
        if self.preferred_target_marker:
            deadline = time.time() + 8
            while time.time() < deadline:
                page = next(
                    (t for t in await self._targets() if local_profiles.target_url_contains_marker(t, self.preferred_target_marker)),
                    None,
                )
                if page:
                    break
                await asyncio.sleep(0.15)
            if not page:
                raise RuntimeError("profile-target-missing: selected Chrome profile target did not appear; refusing to attach to an arbitrary existing profile")
            attached_profile_marker = True
            attached_profile_id = self.preferred_profile_id
            attached_browser_context_id = page.get("browserContextId")
            self.preferred_target_marker = None
            self.preferred_profile_id = None
            targets = await self._targets()
            page = self._select_work_target(
                targets,
                attached_browser_context_id,
                exclude_target_ids={page.get("targetId")},
            )
        else:
            targets = await self._targets()
            launched_profile_id = self.preferred_profile_id
            if launched_profile_id:
                page = self._select_work_target(targets)
                attached_profile_id = launched_profile_id
                attached_browser_context_id = page.get("browserContextId") if page else None
                attached_launched_profile = True
                self.preferred_profile_id = None
            else:
                page = self._select_work_target(targets)
        if not page:
            # No real pages - create one instead of attaching to omnibox popup.
            params = {"url": "about:blank"}
            target_context_id = attached_browser_context_id or self.preferred_browser_context_id
            if target_context_id:
                params["browserContextId"] = target_context_id
            tid = (await self.cdp.send_raw("Target.createTarget", params))["targetId"]
            self.owned_target_ids.add(tid)
            log(f"no real pages found, created about:blank ({tid})")
            page = {"targetId": tid, "url": "about:blank", "type": "page"}
            if target_context_id:
                page["browserContextId"] = target_context_id
            if attached_profile_id and not attached_browser_context_id:
                try:
                    info = await self._target_info(tid)
                    attached_browser_context_id = info.get("browserContextId")
                except Exception:
                    pass
        self.session = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": page["targetId"], "flatten": True}
        ))["sessionId"]
        self.target_id = page["targetId"]
        if attached_profile_marker or attached_launched_profile:
            self.active_local_profile_id = attached_profile_id
            self.preferred_browser_context_id = attached_browser_context_id
        elif not self.selected_local_profile:
            self.active_local_profile_id = None
            self.preferred_browser_context_id = None
        log(f"attached {page['targetId']} ({page.get('url','')[:80]}) session={self.session}")
        await self._enable_default_domains(self.session)
        if attached_profile_marker:
            await self._close_profile_marker_targets(attached_browser_context_id)
        await self._close_remote_debugging_setup_targets()
        return page

    async def close_owned_targets(self):
        if not self.cdp:
            return
        target_ids = list(self.owned_target_ids)
        self.owned_target_ids.clear()
        for target_id in target_ids:
            await _silent(self.cdp.send_raw("Target.closeTarget", {"targetId": target_id}))

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
        selected_profile = self._prepare_selected_local_profile()
        url = get_ws_url(selected_profile)
        log(f"connecting to {url}")
        self.cdp = CDPClient(url)
        try:
            await self.cdp.start()
        except Exception as e:
            if os.environ.get("BU_CDP_WS"):
                raise RuntimeError(
                    f"CDP WS handshake failed: {e} -- remote browser WebSocket connection failed. "
                    "This can happen when network policy blocks the connection, the WS URL is wrong or expired, or the remote endpoint is down. "
                    "If you use Browser Use cloud, verify auth and start a fresh cloud browser."
                )
            raise RuntimeError(f"CDP WS handshake failed: {e} -- click Allow in Chrome if prompted, then retry")
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
                info = await self._target_info(self.target_id)
            except Exception:
                return {"error": "target-gone"}
            return {
                "targetId": info.get("targetId"),
                "url": info.get("url", ""),
                "title": info.get("title", ""),
                "browserContextId": info.get("browserContextId"),
                "local_profile_id": self.active_local_profile_id,
            }
        if meta == "connection_status":
            if not self.target_id:
                return {"error": "not_attached"}
            try:
                info = await self._target_info(self.target_id)
            except Exception:
                return {"error": "cdp_disconnected"}
            page = None
            if is_real_page(info):
                page = {
                    "targetId": info.get("targetId"),
                    "title": info.get("title") or "(untitled)",
                    "url": info.get("url") or "",
                    "browserContextId": info.get("browserContextId"),
                }
            return {
                "target_id": self.target_id,
                "session_id": self.session,
                "local_profile_id": self.active_local_profile_id,
                "profile_context_id": self.preferred_browser_context_id,
                "page": page,
            }
        if meta == "set_session":
            target_id = req.get("target_id") or self.target_id
            if target_id:
                try:
                    await self._ensure_target_browser_context(target_id)
                except Exception as e:
                    return {"error": str(e)}
            old_session = self.session
            self.session = req.get("session_id")
            self.target_id = target_id
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
        if self.preferred_browser_context_id:
            try:
                if method == "Target.createTarget":
                    requested = params.get("browserContextId")
                    if requested and requested != self.preferred_browser_context_id:
                        return {"error": "wrong-profile: refusing to create a target in a different Chrome profile context"}
                    params = {**params, "browserContextId": self.preferred_browser_context_id}
                elif method == "Target.attachToTarget" and params.get("targetId"):
                    await self._ensure_target_browser_context(params["targetId"])
            except Exception as e:
                return {"error": str(e)}
        # Browser-level Target.* calls must not use a session (stale or otherwise).
        # For everything else, explicit session in req wins; else default.
        sid = None if method.startswith("Target.") else (req.get("session_id") or self.session)
        try:
            result = await self.cdp.send_raw(method, params, session_id=sid)
            if method == "Target.createTarget" and isinstance(result, dict):
                target_id = result.get("targetId")
                if target_id:
                    self.owned_target_ids.add(target_id)
            return {"result": result}
        except Exception as e:
            msg = str(e)
            if "Session with given id not found" in msg and sid == self.session and sid:
                log(f"stale session {sid}, re-attaching same target")
                try:
                    if await self._reattach_current_target():
                        return {"result": await self.cdp.send_raw(method, params, session_id=self.session)}
                except Exception as reattach_error:
                    return {"error": str(reattach_error)}
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
        await d.close_owned_targets()
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
