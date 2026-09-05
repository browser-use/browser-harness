"""Bounded event history and request state, updated before any reader runs."""
from collections import deque
import json
import time
import uuid


class EventHistory:
    def __init__(self, capacity=500, max_event_bytes=16384):
        self.events = deque(maxlen=capacity)
        self.max_event_bytes = max_event_bytes
        self.generation = uuid.uuid4().hex
        self.sequence = 0
        self.legacy_sequence = 0

    def append(self, event):
        self.sequence += 1
        if len(json.dumps(event, ensure_ascii=True).encode()) > self.max_event_bytes:
            event = {"method": event["method"], "session_id": event["session_id"], "params": {}, "truncated": True}
        self.events.append((self.sequence, event))

    def read(self, cursor=None, session_id=None):
        sequence = 0
        if cursor is not None:
            if not isinstance(cursor, dict) or cursor.get("generation") != self.generation:
                raise RuntimeError("EventCursorExpired: daemon changed; start a new reader with cursor=None")
            sequence = cursor.get("sequence")
            if type(sequence) is not int or not 0 <= sequence <= self.sequence:
                raise ValueError("invalid event cursor sequence")
        oldest = self.events[0][0] if self.events else self.sequence + 1
        return {
            "events": [{**event, "sequence": seq} for seq, event in self.events
                       if seq > sequence and (session_id is None or event["session_id"] == session_id)],
            "cursor": {"generation": self.generation, "sequence": self.sequence},
            "dropped": max(0, oldest - sequence - 1),
        }

    def drain(self):
        result = [event for seq, event in self.events if seq > self.legacy_sequence]
        self.legacy_sequence = self.sequence
        return result


class RequestState:
    """One active session. Unknown coverage must never be reported as idle."""
    def __init__(self, session_id=None, max_requests=4096):
        self.session_id = session_id
        self.pending = set()
        self.max_requests = max_requests
        self.enabled = False
        self.navigation_seen = False
        self.error = None
        self.last_activity = time.monotonic()

    def record(self, method, params, session_id):
        if session_id != self.session_id or session_id is None:
            return
        frame = params.get("frame", {})
        if method == "Page.frameNavigated" and frame.get("id") and not frame.get("parentId") and self.enabled:
            self.navigation_seen = True
        if not method.startswith("Network."):
            return
        self.last_activity = time.monotonic()
        request_id = params.get("requestId")
        if method == "Network.requestWillBeSent" and request_id:
            if len(self.pending) >= self.max_requests and request_id not in self.pending:
                self.error = "request tracking overflow"
            else:
                # Redirects reuse the same request ID; they are one pending load.
                self.pending.add(request_id)
        elif method in ("Network.loadingFinished", "Network.loadingFailed"):
            self.pending.discard(request_id)

    def snapshot(self):
        known = self.enabled and self.navigation_seen and self.error is None
        return {"session_id": self.session_id, "known": known, "inflight": len(self.pending),
                "quiet_ms": max(0, (time.monotonic() - self.last_activity) * 1000),
                "reason": self.error or (None if known else "network coverage incomplete; navigate after attachment or wait for a DOM condition")}
