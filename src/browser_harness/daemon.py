"""CDP WS holder + IPC relay (Unix socket on POSIX, TCP loopback on Windows). One daemon per BU_NAME."""
import asyncio, copy, json, os, socket, sys, time, urllib.error, urllib.request, uuid
from collections import deque
from pathlib import Path

from . import _ipc as ipc
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
HEALTH_CAPABILITY = "health_events_v1"
HEALTH_SCHEMA_VERSION = 1
HEALTH_EVENT_SCHEMA_VERSION = 1
HEALTH_SESSION_DOMAINS = ("Page", "Runtime", "Log", "Network")
HEALTH_EVENT_MAX_COUNT = int(os.environ.get("BH_HEALTH_EVENT_MAX_COUNT", BUF))
HEALTH_EVENT_MAX_BYTES = int(os.environ.get("BH_HEALTH_EVENT_MAX_BYTES", 8 * 1024 * 1024))
HEALTH_EVENT_MAX_ITEM_BYTES = int(os.environ.get("BH_HEALTH_EVENT_MAX_ITEM_BYTES", 256 * 1024))
_BODY_KEYS = frozenset(("body", "postData", "postDataEntries", "payloadData"))
_NETWORK_DATA_PAYLOAD_METHODS = frozenset((
    "Network.dataReceived",
    "Network.eventSourceMessageReceived",
    "Network.directTCPSocketChunkReceived",
    "Network.directTCPSocketChunkSent",
    "Network.directUDPSocketChunkReceived",
    "Network.directUDPSocketChunkSent",
))
PROFILES = [
    Path.home() / "Library/Application Support/Google/Chrome",
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


async def _silent(coro):
    try:
        await coro
    except Exception:
        pass


def get_ws_url():
    if url := os.environ.get("BU_CDP_WS"):
        return url
    if url := os.environ.get("BU_CDP_URL"):
        # HTTP DevTools endpoint (e.g. http://127.0.0.1:9333) — resolve to ws via /json/version.
        # Use this for a dedicated automation Chrome on a non-default profile, which avoids the
        # M144 "Allow remote debugging" dialog and the M136 default-profile lockdown.
        deadline = time.time() + 30
        last_err = None
        while time.time() < deadline:
            try:
                return json.loads(urllib.request.urlopen(f"{url}/json/version", timeout=5).read())["webSocketDebuggerUrl"]
            except Exception as e:
                last_err = e
                time.sleep(1)
        raise RuntimeError(f"BU_CDP_URL={url} unreachable after 30s: {last_err} -- is the dedicated automation Chrome running?")
    for base in PROFILES:
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
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1).read())["webSocketDebuggerUrl"]
            except urllib.error.HTTPError as e:
                # Chrome 147+ disables /json/* HTTP discovery on the default user-data-dir;
                # the ws path Chrome wrote to DevToolsActivePort still works.
                if e.code == 404 and ws_path:
                    return f"ws://127.0.0.1:{port}{ws_path}"
                time.sleep(1)
            except (OSError, KeyError, ValueError):
                time.sleep(1)
        raise RuntimeError(
            f"Chrome's remote-debugging page is open, but DevTools is not live yet on 127.0.0.1:{port} — if Chrome opened a profile picker, choose your normal profile first, then tick the checkbox and click Allow if shown"
        )
    for probe_port in (9222, 9223):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{probe_port}/json/version", timeout=1) as r:
                return json.loads(r.read())["webSocketDebuggerUrl"]
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
    return t["type"] == "page" and not t.get("url", "").startswith(INTERNAL)


def _without_bodies(value, strip_root_data=False):
    if isinstance(value, dict):
        return {
            key: _without_bodies(child)
            for key, child in value.items()
            if key not in _BODY_KEYS and not (strip_root_data and key == "data")
        }
    if isinstance(value, list):
        return [_without_bodies(child) for child in value]
    return value


class _HealthEventRing:
    def __init__(self, max_count, max_bytes, max_item_bytes):
        if min(max_count, max_bytes, max_item_bytes) <= 0:
            raise ValueError("health event retention limits must be positive")
        self.max_count = max_count
        self.max_bytes = max_bytes
        self.max_item_bytes = max_item_bytes
        self.sequence = 0
        self.total_bytes = 0
        self.events = deque()
        self.lost_ranges = deque()

    def _record_loss(self, sequence):
        ordered = sorted((*self.lost_ranges, (sequence, sequence)))
        merged = []
        for start, end in ordered:
            if merged and start <= merged[-1][1] + 1:
                previous_start, previous_end = merged[-1]
                merged[-1] = (previous_start, max(previous_end, end))
            else:
                merged.append((start, end))
        while len(merged) > self.max_count:
            first, second = merged[:2]
            merged[:2] = [(first[0], second[1])]
        self.lost_ranges = deque(merged)

    def append(self, event):
        self.sequence += 1
        retained = {"sequence": self.sequence, **event}
        encoded_size = len(
            json.dumps(retained, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        if encoded_size > self.max_item_bytes or encoded_size > self.max_bytes:
            self._record_loss(self.sequence)
            return self.sequence
        while self.events and (
            len(self.events) >= self.max_count
            or self.total_bytes + encoded_size > self.max_bytes
        ):
            evicted, size = self.events.popleft()
            self.total_bytes -= size
            self._record_loss(evicted["sequence"])
        self.events.append((retained, encoded_size))
        self.total_bytes += encoded_size
        return self.sequence

    def read_after(self, after_sequence, through_sequence=None):
        upper = self.sequence
        if through_sequence is not None:
            upper = min(upper, through_sequence)
        events = [
            copy.deepcopy(event)
            for event, _ in self.events
            if after_sequence < event["sequence"] <= upper
        ]
        intersecting_losses = [
            (start, end)
            for start, end in self.lost_ranges
            if end > after_sequence and start <= upper
        ]
        available_from = self.events[0][0]["sequence"] if self.events else self.sequence + 1
        overflow = None
        if intersecting_losses:
            overflow = {
                "kind": "retention_or_truncation",
                "requested_after_sequence": after_sequence,
                "lost_through_sequence": max(end for _, end in intersecting_losses),
                "available_from_sequence": available_from,
            }
        returned_through = events[-1]["sequence"] if events else min(after_sequence, upper)
        return {
            "events": events,
            "range": {
                "requested_after_sequence": after_sequence,
                "available_from_sequence": available_from,
                "current_sequence": self.sequence,
                "returned_through_sequence": returned_through,
                "complete": overflow is None,
            },
            "overflow": overflow,
        }


class Daemon:
    def __init__(
        self,
        event_max_count=HEALTH_EVENT_MAX_COUNT,
        event_max_bytes=HEALTH_EVENT_MAX_BYTES,
        event_max_item_bytes=HEALTH_EVENT_MAX_ITEM_BYTES,
    ):
        self.cdp = None
        self.session = None
        self.target_id = None
        self.daemon_fingerprint = uuid.uuid4().hex
        self.target_epoch = 0
        self.session_epoch = 0
        self.attachment_generation = 0
        self.attachment_transition = False
        self.subscriptions = {}
        self.health_events = _HealthEventRing(
            event_max_count,
            event_max_bytes,
            event_max_item_bytes,
        )
        self.compatibility_cursor = 0
        self.health_attempts = {}
        self.dialog = None
        self.stop = None  # asyncio.Event, set inside start()

    def _observation(self):
        subscriptions = copy.deepcopy(self.subscriptions)
        required = ("Target", *HEALTH_SESSION_DOMAINS)
        ready = not self.attachment_transition and bool(self.target_id and self.session) and all(
            subscriptions.get(domain, {}).get("enabled") for domain in required
        )
        return {
            "ready": ready,
            "target_id": self.target_id,
            "session_id": self.session,
            "target_epoch": self.target_epoch,
            "session_epoch": self.session_epoch,
            "subscriptions": subscriptions,
        }

    def _capabilities(self):
        ring = self.health_events
        return {
            "daemon_fingerprint": self.daemon_fingerprint,
            "capabilities": {
                HEALTH_CAPABILITY: {
                    "schema_version": HEALTH_SCHEMA_VERSION,
                    "event_schema_version": HEALTH_EVENT_SCHEMA_VERSION,
                    "operations": ["begin", "events_since", "seal"],
                    "sequence_origin": 1,
                    "retention": {
                        "max_events": ring.max_count,
                        "max_total_bytes": ring.max_bytes,
                        "max_event_bytes": ring.max_item_bytes,
                    },
                }
            },
            "observation": self._observation(),
        }

    def _record_health_event(self, method, params, session_id):
        return self.health_events.append(
            {
                "method": method,
                "params": _without_bodies(
                    params,
                    strip_root_data=method in _NETWORK_DATA_PAYLOAD_METHODS,
                ),
                "session_id": session_id,
                "daemon_fingerprint": self.daemon_fingerprint,
                "target_id": self.target_id,
                "target_epoch": self.target_epoch,
                "session_epoch": self.session_epoch,
            }
        )

    async def _enable_observation(self):
        proof = {}
        operations = [("Target", "Target.setDiscoverTargets", {"discover": True}, None)]
        operations.extend(
            (domain, f"{domain}.enable", None, self.session)
            for domain in HEALTH_SESSION_DOMAINS
        )
        for domain, method, params, session_id in operations:
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw(method, params, session_id=session_id),
                    timeout=5,
                )
                enabled = True
            except Exception as exc:
                enabled = False
                log(f"enable {domain}: {exc}")
            proof[domain] = {
                "enabled": enabled,
                "scope": "browser" if session_id is None else "session",
                "session_id": session_id,
            }
        # DOM is required for existing harness primitives, but is not part of
        # the health observation contract.
        try:
            await asyncio.wait_for(
                self.cdp.send_raw("DOM.enable", session_id=self.session),
                timeout=5,
            )
        except Exception as exc:
            log(f"enable DOM: {exc}")
        return proof

    async def _set_attachment(self, target_id, session_id, reason):
        self.attachment_generation += 1
        generation = self.attachment_generation
        previous = {
            "target_id": self.target_id,
            "session_id": self.session,
            "target_epoch": self.target_epoch,
            "session_epoch": self.session_epoch,
        }
        if target_id != self.target_id:
            self.target_epoch += 1
        if session_id != self.session:
            self.session_epoch += 1
        self.target_id = target_id
        self.session = session_id
        self.attachment_transition = True
        self.subscriptions = {}
        proof = await self._enable_observation()
        if (
            generation != self.attachment_generation
            or target_id != self.target_id
            or session_id != self.session
        ):
            return False
        self.subscriptions = proof
        self.attachment_transition = False
        self._record_health_event(
            "BrowserHarness.attachmentChanged",
            {
                "reason": reason,
                "previous": previous,
                "current": self._observation(),
            },
            session_id,
        )
        return True

    def _invalidate_attachment(self, reason, clear_target):
        self.attachment_generation += 1
        previous = self._observation()
        if self.session is not None:
            self.session_epoch += 1
        self.session = None
        if clear_target and self.target_id is not None:
            self.target_epoch += 1
            self.target_id = None
        self.attachment_transition = False
        self.subscriptions = {}
        self._record_health_event(
            "BrowserHarness.attachmentInvalidated",
            {
                "reason": reason,
                "previous": previous,
                "current": self._observation(),
            },
            None,
        )

    def _record_cdp_event(self, method, params, session_id):
        sequence = self._record_health_event(method, params, session_id)
        if method == "Target.detachedFromTarget":
            detached_session = params.get("sessionId")
            detached_target = params.get("targetId")
            current = (
                detached_session == self.session
                if detached_session is not None
                else detached_target == self.target_id
            )
            if current:
                self._invalidate_attachment("target_detached", clear_target=False)
        elif method in ("Target.targetDestroyed", "Target.targetCrashed"):
            if params.get("targetId") == self.target_id:
                self._invalidate_attachment(
                    "target_destroyed" if method == "Target.targetDestroyed" else "target_crashed",
                    clear_target=True,
                )
        return sequence

    async def attach_first_page(self, reason="attach_first_page"):
        """Attach to a real page (or any page). Sets self.session. Returns attached target or None."""
        targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
        pages = [t for t in targets if is_real_page(t)]
        if not pages:
            # No real pages — create one instead of attaching to omnibox popup
            tid = (await self.cdp.send_raw("Target.createTarget", {"url": "about:blank"}))["targetId"]
            log(f"no real pages found, created about:blank ({tid})")
            pages = [{"targetId": tid, "url": "about:blank", "type": "page"}]
        session_id = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": pages[0]["targetId"], "flatten": True}
        ))["sessionId"]
        established = await self._set_attachment(pages[0]["targetId"], session_id, reason)
        if not established:
            return None
        log(f"attached {pages[0]['targetId']} ({pages[0].get('url','')[:80]}) session={self.session}")
        return pages[0]

    async def start(self):
        self.stop = asyncio.Event()
        url = get_ws_url()
        log(f"connecting to {url}")
        self.cdp = CDPClient(url)
        try:
            await self.cdp.start()
        except Exception as e:
            if os.environ.get("BU_CDP_WS"):
                raise RuntimeError(
                    f"CDP WS handshake failed: {e} -- remote browser WebSocket connection failed. "
                    "This can happen when network policy blocks the connection, the WS URL is wrong or expired, or the remote endpoint is down. "
                    "If you use Browser Use cloud, verify BROWSER_USE_API_KEY and get a fresh URL via start_remote_daemon()."
                )
            raise RuntimeError(f"CDP WS handshake failed: {e} -- click Allow in Chrome if prompted, then retry")
        await self.attach_first_page(reason="initial_attach")
        orig = self.cdp._event_registry.handle_event
        mark_js = "if(!document.title.startsWith('\U0001F7E2'))document.title='\U0001F7E2 '+document.title"
        async def tap(method, params, session_id=None):
            self._record_cdp_event(method, params, session_id)
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
        if meta == "ping":        return {"pong": True}
        if meta == "drain_events":
            result = self.health_events.read_after(self.compatibility_cursor)
            self.compatibility_cursor = self.health_events.sequence
            return {"events": result["events"], "overflow": result["overflow"]}
        if meta == "health_capabilities":
            return self._capabilities()
        if meta == "health_begin":
            attempt_id = req.get("attempt_id")
            if not isinstance(attempt_id, str) or not attempt_id or len(attempt_id) > 256:
                return {"error": "invalid_health_attempt_id"}
            existing = self.health_attempts.get(attempt_id)
            if existing:
                return copy.deepcopy(existing["begin"])
            begin = {
                "capability": HEALTH_CAPABILITY,
                "schema_version": HEALTH_SCHEMA_VERSION,
                "attempt_id": attempt_id,
                "daemon_fingerprint": self.daemon_fingerprint,
                "start_sequence": self.health_events.sequence,
                "sealed_through_sequence": None,
                "observation": self._observation(),
            }
            self.health_attempts[attempt_id] = {"begin": begin, "seal": None}
            return copy.deepcopy(begin)
        if meta == "health_events_since":
            attempt_id = req.get("attempt_id")
            attempt = self.health_attempts.get(attempt_id)
            if not attempt:
                return {"error": "unknown_health_attempt"}
            after_sequence = req.get("after_sequence")
            if (
                not isinstance(after_sequence, int)
                or isinstance(after_sequence, bool)
                or after_sequence < attempt["begin"]["start_sequence"]
            ):
                return {"error": "invalid_health_sequence"}
            seal = attempt["seal"]
            through_sequence = (
                seal["sealed_through_sequence"]
                if seal
                else req.get("through_sequence")
            )
            if (
                through_sequence is not None
                and (
                    not isinstance(through_sequence, int)
                    or isinstance(through_sequence, bool)
                    or through_sequence < after_sequence
                )
            ):
                return {"error": "invalid_health_sequence"}
            result = self.health_events.read_after(after_sequence, through_sequence)
            result["range"]["sealed_through_sequence"] = (
                seal["sealed_through_sequence"] if seal else None
            )
            return {
                "capability": HEALTH_CAPABILITY,
                "schema_version": HEALTH_SCHEMA_VERSION,
                "attempt_id": attempt_id,
                "daemon_fingerprint": self.daemon_fingerprint,
                **result,
            }
        if meta == "health_seal":
            attempt_id = req.get("attempt_id")
            attempt = self.health_attempts.get(attempt_id)
            if not attempt:
                return {"error": "unknown_health_attempt"}
            if attempt["seal"]:
                return copy.deepcopy(attempt["seal"])
            seal = {
                "capability": HEALTH_CAPABILITY,
                "schema_version": HEALTH_SCHEMA_VERSION,
                "attempt_id": attempt_id,
                "daemon_fingerprint": self.daemon_fingerprint,
                "start_sequence": attempt["begin"]["start_sequence"],
                "sealed_through_sequence": self.health_events.sequence,
                "observation": self._observation(),
            }
            attempt["seal"] = seal
            return copy.deepcopy(seal)
        if meta == "session":     return {"session_id": self.session}
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
            session_id = req.get("session_id")
            target_id = req.get("target_id") or self.target_id
            try:
                await self._set_attachment(target_id, session_id, "set_session")
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
