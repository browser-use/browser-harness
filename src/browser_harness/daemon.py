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
HEALTH_OBSERVATION_CONTROL_METHODS = {
    "Page.enable",
    "Page.disable",
    "Runtime.enable",
    "Runtime.disable",
    "Log.enable",
    "Log.disable",
    "Network.enable",
    "Network.disable",
    "Console.enable",
    "Console.disable",
    "Target.setAutoAttach",
    "Target.autoAttachRelated",
}
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
_HEALTH_CDP_METHODS = frozenset((
    "Runtime.exceptionThrown",
    "Runtime.consoleAPICalled",
    "Console.messageAdded",
    "Log.entryAdded",
    "Inspector.targetCrashed",
    "Target.targetCrashed",
    "Security.certificateError",
    "Network.requestWillBeSent",
    "Network.responseReceived",
    "Network.loadingFailed",
    "Target.attachedToTarget",
    "Target.detachedFromTarget",
    "Target.targetDestroyed",
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


def _bounded_text(value, limit=4096):
    return str(value)[:limit]


def _project_call_frames(stack_trace):
    if not isinstance(stack_trace, dict):
        return None
    frames = []
    for frame in stack_trace.get("callFrames", [])[:16]:
        if not isinstance(frame, dict):
            continue
        frames.append({
            "functionName": _bounded_text(frame.get("functionName", ""), 256),
            "url": _bounded_text(frame.get("url", ""), 2048),
            "lineNumber": frame.get("lineNumber"),
            "columnNumber": frame.get("columnNumber"),
        })
    return {"callFrames": frames}


def _project_remote_object(value):
    if not isinstance(value, dict):
        return {}
    projected = {
        key: value[key]
        for key in ("type", "subtype")
        if key in value
    }
    primitive = value.get("value")
    if isinstance(primitive, (str, int, float, bool)) or primitive is None:
        if "value" in value:
            projected["value"] = (
                _bounded_text(primitive)
                if isinstance(primitive, str)
                else primitive
            )
    for key in ("description", "unserializableValue"):
        if key in value:
            projected[key] = _bounded_text(value[key])
    return projected


def _project_health_params(method, params):
    if method == "Runtime.exceptionThrown":
        details = params.get("exceptionDetails") or {}
        exception = details.get("exception") or {}
        projected_details = {
            key: details[key]
            for key in ("lineNumber", "columnNumber")
            if key in details
        }
        for key in ("text", "url"):
            if key in details:
                projected_details[key] = _bounded_text(details[key])
        if exception.get("description") is not None:
            projected_details["exception"] = {
                "description": _bounded_text(exception["description"]),
            }
        stack = _project_call_frames(details.get("stackTrace"))
        if stack is not None:
            projected_details["stackTrace"] = stack
        return {"exceptionDetails": projected_details}
    if method == "Runtime.consoleAPICalled":
        projected = {
            "type": params.get("type"),
            "args": [
                _project_remote_object(argument)
                for argument in params.get("args", [])[:32]
            ],
        }
        stack = _project_call_frames(params.get("stackTrace"))
        if stack is not None:
            projected["stackTrace"] = stack
        return projected
    if method == "Console.messageAdded":
        message = params.get("message") or {}
        projected_message = {
            key: message[key]
            for key in ("level", "line", "column")
            if key in message
        }
        for key in ("source", "text", "url"):
            if key in message:
                projected_message[key] = _bounded_text(message[key])
        stack = _project_call_frames(message.get("stack") or message.get("stackTrace"))
        if stack is not None:
            projected_message["stack"] = stack
        return {"message": projected_message}
    if method == "Log.entryAdded":
        entry = params.get("entry") or {}
        projected_entry = {
            key: entry[key]
            for key in ("level", "lineNumber")
            if key in entry
        }
        for key in ("source", "text", "url"):
            if key in entry:
                projected_entry[key] = _bounded_text(entry[key])
        stack = _project_call_frames(entry.get("stackTrace"))
        if stack is not None:
            projected_entry["stackTrace"] = stack
        return {"entry": projected_entry}
    if method in ("Inspector.targetCrashed",):
        return {}
    if method == "Target.targetCrashed":
        return {
            key: params[key]
            for key in ("targetId", "status", "errorCode")
            if key in params
        }
    if method == "Security.certificateError":
        return {
            key: _bounded_text(params[key])
            for key in ("eventId", "errorType", "requestURL")
            if key in params
        }
    if method == "Network.requestWillBeSent":
        request = params.get("request") or {}
        return {
            **{
                key: params[key]
                for key in ("requestId", "type")
                if key in params
            },
            "request": {
                key: _bounded_text(request[key])
                for key in ("method", "url")
                if key in request
            },
        }
    if method == "Network.responseReceived":
        response = params.get("response") or {}
        projected_response = {
            key: response[key]
            for key in ("status",)
            if key in response
        }
        for key in ("url", "statusText"):
            if key in response:
                projected_response[key] = _bounded_text(response[key])
        return {
            **{
                key: params[key]
                for key in ("requestId", "type")
                if key in params
            },
            "response": projected_response,
        }
    if method == "Network.loadingFailed":
        projected = {
            key: params[key]
            for key in ("requestId", "type", "canceled", "blockedReason")
            if key in params
        }
        if "errorText" in params:
            projected["errorText"] = _bounded_text(params["errorText"])
        cors = params.get("corsErrorStatus")
        if isinstance(cors, dict):
            projected["corsErrorStatus"] = {
                key: _bounded_text(cors[key])
                for key in ("corsError", "failedParameter")
                if key in cors
            }
        return projected
    if method == "Target.attachedToTarget":
        target = params.get("targetInfo") or {}
        return {
            **{
                key: params[key]
                for key in ("sessionId", "waitingForDebugger")
                if key in params
            },
            "targetInfo": {
                key: _bounded_text(target[key])
                for key in ("targetId", "type", "url", "parentId")
                if key in target
            },
        }
    if method == "Target.detachedFromTarget":
        return {
            key: _bounded_text(params[key])
            for key in ("sessionId", "targetId")
            if key in params
        }
    if method == "Target.targetDestroyed":
        return (
            {"targetId": _bounded_text(params["targetId"])}
            if "targetId" in params
            else {}
        )
    return {}


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
        self.pending_session_handoff = None
        self.prepared_auto_session = None
        self.superseded_health_sessions = set()
        self.background_tasks = set()
        self.subscriptions = {}
        self.health_events = _HealthEventRing(
            event_max_count,
            event_max_bytes,
            event_max_item_bytes,
        )
        self.compatibility_events = _HealthEventRing(
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
                    "continuity_proofs": ["same_target_paused_session_handoff_v1"],
                    "retention": {
                        "max_events": ring.max_count,
                        "max_total_bytes": ring.max_bytes,
                        "max_event_bytes": ring.max_item_bytes,
                    },
                }
            },
            "observation": self._observation(),
        }

    def _event_record(self, method, params):
        return {
            "method": method,
            "params": params,
            "session_id": self.session,
            "daemon_fingerprint": self.daemon_fingerprint,
            "target_id": self.target_id,
            "target_epoch": self.target_epoch,
            "session_epoch": self.session_epoch,
        }

    def _record_health_event(self, method, params, _transport_session_id):
        if not method.startswith("BrowserHarness.") and method not in _HEALTH_CDP_METHODS:
            return None
        if (
            not method.startswith("BrowserHarness.")
            and _transport_session_id in self.superseded_health_sessions
        ):
            return None
        projected = (
            params
            if method.startswith("BrowserHarness.")
            else _project_health_params(method, params)
        )
        return self.health_events.append(self._event_record(method, projected))

    async def _enable_target_observation(self, target_id):
        enabled = True
        operations = (
            ("Target.setDiscoverTargets", {"discover": True}),
            (
                "Target.autoAttachRelated",
                {
                    "targetId": target_id,
                    "waitForDebuggerOnStart": True,
                    "filter": [
                        {"type": "page", "exclude": False},
                        {"exclude": True},
                    ],
                },
            ),
        )
        for method, params in operations:
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw(method, params, session_id=None),
                    timeout=5,
                )
            except Exception as exc:
                enabled = False
                log(f"enable Target observation ({method}): {exc}")
        return {
            "enabled": enabled,
            "scope": "browser",
            "session_id": None,
            "auto_attach": "related",
            "wait_for_debugger_on_start": True,
        }

    async def _enable_session_observation(self, session_id):
        proof = {}
        for domain in HEALTH_SESSION_DOMAINS:
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw(
                        f"{domain}.enable",
                        session_id=session_id,
                    ),
                    timeout=5,
                )
                enabled = True
            except Exception as exc:
                enabled = False
                log(f"enable {domain}: {exc}")
            proof[domain] = {
                "enabled": enabled,
                "scope": "session",
                "session_id": session_id,
            }
        try:
            await asyncio.wait_for(
                self.cdp.send_raw("DOM.enable", session_id=session_id),
                timeout=5,
            )
        except Exception as exc:
            log(f"enable DOM: {exc}")
        return proof

    async def _enable_observation(self):
        return {
            "Target": await self._enable_target_observation(self.target_id),
            **await self._enable_session_observation(self.session),
        }

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
            self.pending_session_handoff = None
            self.prepared_auto_session = None
            self.superseded_health_sessions.clear()
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
        prepared = self.prepared_auto_session
        if (
            prepared
            and prepared["target_id"] == target_id
            and previous["target_id"] == target_id
            and previous["session_id"]
        ):
            return self._adopt_prepared_overlap(prepared, previous)
        previous_session_id = previous["session_id"]
        if self.pending_session_handoff:
            previous_session_id = self.pending_session_handoff[
                "previous_session_id"
            ]
        if previous_session_id and previous_session_id != session_id:
            self.superseded_health_sessions.add(previous_session_id)
        self.pending_session_handoff = None
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
        self.pending_session_handoff = None
        self.prepared_auto_session = None
        if clear_target:
            self.superseded_health_sessions.clear()
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

    def _begin_session_handoff(self):
        self.attachment_generation += 1
        self.pending_session_handoff = {
            "target_id": self.target_id,
            "target_epoch": self.target_epoch,
            "previous_session_id": self.session,
            "previous_session_epoch": self.session_epoch,
        }
        self.session = None
        self.attachment_transition = True
        self.subscriptions = {}
        prepared = self.prepared_auto_session
        if prepared and prepared["target_id"] == self.target_id:
            self._adopt_prepared_auto_session(prepared)

    def _adopt_prepared_auto_session(self, prepared):
        pending = self.pending_session_handoff
        if not pending or prepared["target_id"] != pending["target_id"]:
            return False
        previous_session_id = pending["previous_session_id"]
        if previous_session_id and previous_session_id != prepared["session_id"]:
            self.superseded_health_sessions.add(previous_session_id)
        self.attachment_generation += 1
        self.target_id = pending["target_id"]
        self.target_epoch = pending["target_epoch"]
        self.session_epoch = pending["previous_session_epoch"] + 1
        self.session = prepared["session_id"]
        self.subscriptions = copy.deepcopy(prepared["subscriptions"])
        self.attachment_transition = False
        self.pending_session_handoff = None
        self.prepared_auto_session = None
        self._record_health_event(
            "BrowserHarness.sameTargetSessionHandoff",
            {
                "proof": "same_target_paused_session_handoff_v1",
                "target_id": self.target_id,
                "previous_session_id": pending["previous_session_id"],
                "previous_session_epoch": pending["previous_session_epoch"],
                "session_id": self.session,
                "session_epoch": self.session_epoch,
                "waiting_for_debugger_on_start": True,
                "required_domains": ["Target", *HEALTH_SESSION_DOMAINS],
                "subscriptions_before_resume": True,
                "resume_acknowledged": True,
            },
            self.session,
        )
        return True

    def _adopt_prepared_overlap(self, prepared, previous):
        if (
            prepared["target_id"] != previous["target_id"]
            or not previous["session_id"]
        ):
            return False
        self.pending_session_handoff = {
            "target_id": previous["target_id"],
            "target_epoch": previous["target_epoch"],
            "previous_session_id": previous["session_id"],
            "previous_session_epoch": previous["session_epoch"],
        }
        return self._adopt_prepared_auto_session(prepared)

    async def _resume_auto_attached_session(self, session_id):
        try:
            await asyncio.wait_for(
                self.cdp.send_raw(
                    "Runtime.runIfWaitingForDebugger",
                    session_id=session_id,
                ),
                timeout=5,
            )
            return True
        except Exception as exc:
            log(f"resume auto-attached session {session_id}: {exc}")
            return False

    async def _prepare_auto_attached_session(self, params):
        session_id = params.get("sessionId")
        target_info = params.get("targetInfo") or {}
        target_id = target_info.get("targetId")
        waiting = params.get("waitingForDebugger") is True
        if not session_id or not waiting:
            return False
        if target_id != self.target_id or target_info.get("type") != "page":
            await self._resume_auto_attached_session(session_id)
            return False
        session_proof = await self._enable_session_observation(session_id)
        subscriptions_ready = all(
            session_proof.get(domain, {}).get("enabled")
            for domain in HEALTH_SESSION_DOMAINS
        )
        resumed = await self._resume_auto_attached_session(session_id)
        if (
            not subscriptions_ready
            or not resumed
            or target_id != self.target_id
        ):
            return False
        prepared = {
            "target_id": target_id,
            "session_id": session_id,
            "subscriptions": {
                "Target": {
                    "enabled": True,
                    "scope": "browser",
                    "session_id": None,
                    "auto_attach": "related",
                    "wait_for_debugger_on_start": True,
                },
                **session_proof,
            },
        }
        self.prepared_auto_session = prepared
        if self.pending_session_handoff:
            return self._adopt_prepared_auto_session(prepared)
        observation = self._observation()
        if observation["ready"]:
            return self._adopt_prepared_overlap(
                prepared,
                {
                    "target_id": observation["target_id"],
                    "session_id": observation["session_id"],
                    "target_epoch": observation["target_epoch"],
                    "session_epoch": observation["session_epoch"],
                },
            )
        return True

    def _record_cdp_event(self, method, params, session_id):
        compatibility_params = _without_bodies(
            params,
            strip_root_data=method in _NETWORK_DATA_PAYLOAD_METHODS,
        )
        self.compatibility_events.append(
            self._event_record(method, compatibility_params)
        )
        sequence = self._record_health_event(method, params, session_id)
        if method == "Target.detachedFromTarget":
            detached_session = params.get("sessionId")
            detached_target = params.get("targetId")
            prepared = self.prepared_auto_session
            if prepared and detached_session == prepared["session_id"]:
                self.prepared_auto_session = None
            elif (
                detached_session == self.session
                if detached_session is not None
                else detached_target == self.target_id
            ):
                self._begin_session_handoff()
            if detached_session:
                self.superseded_health_sessions.discard(detached_session)
        elif method in ("Target.targetDestroyed", "Target.targetCrashed"):
            if params.get("targetId") == self.target_id:
                self._invalidate_attachment(
                    "target_destroyed" if method == "Target.targetDestroyed" else "target_crashed",
                    clear_target=True,
                )
        return sequence

    def _spawn_background(self, coroutine):
        task = asyncio.create_task(_silent(coroutine))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task

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
        orig = self.cdp._event_registry.handle_event
        mark_js = "if(!document.title.startsWith('\U0001F7E2'))document.title='\U0001F7E2 '+document.title"
        async def tap(method, params, session_id=None):
            self._record_cdp_event(method, params, session_id)
            if method == "Target.attachedToTarget":
                self._spawn_background(self._prepare_auto_attached_session(params))
            if method == "Page.javascriptDialogOpening":
                self.dialog = params
            elif method == "Page.javascriptDialogClosed":
                self.dialog = None
            elif method in ("Page.loadEventFired", "Page.domContentEventFired"):
                asyncio.create_task(_silent(asyncio.wait_for(self.cdp.send_raw("Runtime.evaluate", {"expression": mark_js}, session_id=self.session), timeout=2)))
            return await orig(method, params, session_id)
        self.cdp._event_registry.handle_event = tap
        await self.attach_first_page(reason="initial_attach")
        if self.background_tasks:
            await asyncio.gather(*tuple(self.background_tasks))

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
            result = self.compatibility_events.read_after(self.compatibility_cursor)
            self.compatibility_cursor = self.compatibility_events.sequence
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
        if (
            method in HEALTH_OBSERVATION_CONTROL_METHODS
            and any(attempt["seal"] is None for attempt in self.health_attempts.values())
        ):
            return {"error": "health_observation_control_is_guarded"}
        # Browser-level Target.* calls must not use a session (stale or otherwise).
        # For everything else, explicit session in req wins; else default.
        sid = None if method.startswith("Target.") else (req.get("session_id") or self.session)
        try:
            return {"result": await self.cdp.send_raw(method, params, session_id=sid)}
        except Exception as e:
            msg = str(e)
            if "Session with given id not found" in msg and sid:
                if self.session != sid and self._observation()["ready"]:
                    log(f"session handoff replaced stale session {sid} with {self.session}")
                    return {
                        "result": await self.cdp.send_raw(
                            method,
                            params,
                            session_id=self.session,
                        )
                    }
                if sid == self.session:
                    prepared = self.prepared_auto_session
                    observation = self._observation()
                    if (
                        prepared
                        and prepared["target_id"] == observation["target_id"]
                        and observation["ready"]
                        and self._adopt_prepared_overlap(
                            prepared,
                            {
                                "target_id": observation["target_id"],
                                "session_id": observation["session_id"],
                                "target_epoch": observation["target_epoch"],
                                "session_epoch": observation["session_epoch"],
                            },
                        )
                    ):
                        log(f"prepared overlap replaced stale session {sid} with {self.session}")
                        return {
                            "result": await self.cdp.send_raw(
                                method,
                                params,
                                session_id=self.session,
                            )
                        }
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
