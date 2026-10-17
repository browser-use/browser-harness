"""Owned-target scopes: one invocation, one disposable browser context, one target.

ScopeTable is built from a send_raw callable and a static ping reply, never
from the Daemon. It therefore cannot read or write Daemon.session, target_id,
events, dialog, or dedicated_target_id, and cannot reach attach_first_page.
"""
import asyncio, re, secrets
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, NewType, Union

PROTOCOL = 1
MAX_OPEN_SCOPES = 8
SCOPE_EVENT_BUF = 500
ENABLE_TIMEOUT_S = 4.0
# Provisioning plus dispose stays under the client's 10s IPC socket timeout,
# so _lock is always released and the caller gets a reply, not a socket error.
PROVISION_TIMEOUT_S = 6.0
DISPOSE_TIMEOUT_S = 3.0
OWNED_CAPABILITY = "owned_target"

ScopeId = NewType("ScopeId", str)
SendRaw = Callable[..., Awaitable[dict]]
_SCOPE_ID_RE = re.compile(r"\A[0-9a-f]{32}\Z")


def parse_scope_id(raw) -> ScopeId | None:
    return ScopeId(raw) if isinstance(raw, str) and _SCOPE_ID_RE.match(raw) else None


class Refusal(str, Enum):
    ENUMERATION = "enumeration"
    FOREIGN_TARGET = "foreign-target"
    FOREIGN_SESSION = "foreign-session"
    SECOND_TARGET = "second-target"
    DOMAIN_NOT_ALLOWED = "domain-not-allowed"
    LIFECYCLE = "lifecycle"
    UNKNOWN_META = "unknown-meta"
    UNKNOWN_SCOPE = "unknown-scope"
    SCOPE_CLOSED = "scope-closed"
    STALE_SESSION = "stale-session"
    CAPACITY = "capacity"

    def reply(self) -> dict:
        return {"error": f"owned-scope: {self.value}"}


@dataclass(frozen=True)
class OwnedTarget:
    scope_id: ScopeId
    context_id: str
    target_id: str
    session_id: str


class ScopeState(Enum):
    OPEN = "open"
    CLOSING = "closing"


@dataclass
class OwnedScope:
    target: OwnedTarget
    state: ScopeState = ScopeState.OPEN
    page_claimed: bool = False
    events: deque = field(default_factory=lambda: deque(maxlen=SCOPE_EVENT_BUF))
    dialog: dict | None = None


@dataclass(frozen=True)
class OnOwnedSession:
    method: str
    params: dict


@dataclass(frozen=True)
class BrowserLevelForOwnedTarget:
    method: str
    params: dict


Route = Union[OnOwnedSession, BrowserLevelForOwnedTarget, Refusal]

# Network is safe on the owned session only because the target lives in its
# own browser context: context-wide cookie reads see only the scope's data.
SESSION_DOMAINS = frozenset({
    "Page", "Runtime", "DOM", "DOMSnapshot", "CSS", "Input", "Network",
    "Emulation", "Accessibility", "Overlay", "Log", "Performance", "IO",
})
OWNED_TARGET_METHODS = frozenset({"Target.getTargetInfo", "Target.closeTarget"})
TARGET_NEUTRAL_METHODS = frozenset({"Browser.getVersion"})
ENUMERATING_METHODS = frozenset({
    "Target.getTargets", "Target.setDiscoverTargets", "Target.setAutoAttach",
    "Target.getBrowserContexts",
})
CREATING_METHODS = frozenset({"Target.createTarget", "Target.createBrowserContext"})


def route_cdp(target: OwnedTarget, method: str, params: dict, requested_session: str | None) -> Route:
    if requested_session not in (None, target.session_id):
        return Refusal.FOREIGN_SESSION
    if method in ENUMERATING_METHODS:
        return Refusal.ENUMERATION
    if method in CREATING_METHODS:
        return Refusal.SECOND_TARGET
    if method in OWNED_TARGET_METHODS:
        target_id = params.get("targetId")
        # Without targetId Chrome answers with the browser target itself.
        if target_id is None:
            return Refusal.ENUMERATION
        if target_id != target.target_id:
            return Refusal.FOREIGN_TARGET
        return BrowserLevelForOwnedTarget(method, params)
    if method.startswith("Target."):
        return Refusal.FOREIGN_TARGET
    if method in TARGET_NEUTRAL_METHODS:
        return BrowserLevelForOwnedTarget(method, params)
    if method.split(".", 1)[0] in SESSION_DOMAINS:
        return OnOwnedSession(method, params)
    return Refusal.DOMAIN_NOT_ALLOWED


_LIFECYCLE_METAS = frozenset({"set_session", "shutdown", "begin_owned_target"})
_INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")


class ScopeTable:
    """Owns every OwnedScope and is the only writer of scope state."""

    def __init__(self, send_raw: SendRaw, ping_reply: dict) -> None:
        self._send = send_raw
        self._ping_reply = dict(ping_reply)
        self._open: dict[ScopeId, OwnedScope] = {}
        self._closed: deque[ScopeId] = deque(maxlen=64)
        self._lock = asyncio.Lock()

    async def begin(self) -> dict:
        async with self._lock:
            if len(self._open) >= MAX_OPEN_SCOPES:
                return Refusal.CAPACITY.reply()
            context_id = None
            scope_id = None
            try:
                async with asyncio.timeout(PROVISION_TIMEOUT_S):
                    context_id = (await self._send(
                        "Target.createBrowserContext", {"disposeOnDetach": True}
                    ))["browserContextId"]
                    target_id = (await self._send(
                        "Target.createTarget",
                        {"url": "about:blank", "background": True, "browserContextId": context_id},
                    ))["targetId"]
                    session_id = (await self._send(
                        "Target.attachToTarget", {"targetId": target_id, "flatten": True}
                    ))["sessionId"]
                    scope_id = ScopeId(secrets.token_hex(16))
                    # Registered before the enables so the first Page/Runtime event
                    # is already absorbed here, never into the daemon's global buffer.
                    self._open[scope_id] = OwnedScope(OwnedTarget(scope_id, context_id, target_id, session_id))
                    enables = [
                        asyncio.create_task(asyncio.wait_for(
                            self._send(f"{d}.enable", session_id=session_id), ENABLE_TIMEOUT_S
                        ))
                        for d in ("Page", "DOM", "Runtime", "Network")
                    ]
                    try:
                        await asyncio.gather(*enables)
                    except BaseException:
                        for task in enables:
                            task.cancel()
                        await asyncio.gather(*enables, return_exceptions=True)
                        raise
            except BaseException as e:
                if scope_id is not None:
                    self._open.pop(scope_id, None)
                if context_id is not None:
                    try:
                        await asyncio.wait_for(
                            self._send("Target.disposeBrowserContext", {"browserContextId": context_id}),
                            DISPOSE_TIMEOUT_S,
                        )
                    except Exception:
                        pass
                if not isinstance(e, Exception):
                    raise
                if isinstance(e, TimeoutError):
                    return {"error": "owned target provisioning timed out"}
                return {"error": str(e) or type(e).__name__}
            return {"owned_target": {"protocol": PROTOCOL, "scope_id": scope_id, "target_id": target_id}}

    async def handle(self, req: dict) -> dict:
        scope_id = parse_scope_id(req.get("scope"))
        meta = req.get("meta")
        if scope_id is None:
            return Refusal.UNKNOWN_SCOPE.reply()
        if meta == "end_owned_target":
            return await self.end(scope_id)
        scope = self._open.get(scope_id)
        if scope is None:
            return (Refusal.SCOPE_CLOSED if scope_id in self._closed else Refusal.UNKNOWN_SCOPE).reply()
        if scope.state is ScopeState.CLOSING:
            return Refusal.SCOPE_CLOSED.reply()
        if meta is not None:
            return await self._meta(scope, meta)
        return await self._cdp(scope, req)

    async def _meta(self, scope: OwnedScope, meta: str) -> dict:
        target = scope.target
        if meta == "ping":
            return dict(self._ping_reply)
        if meta == "drain_events":
            out = list(scope.events)
            scope.events.clear()
            return {"events": out}
        if meta == "session":
            return {"session_id": target.session_id}
        if meta == "pending_dialog":
            return {"dialog": scope.dialog}
        if meta == "claim_owned_page":
            if scope.page_claimed:
                return Refusal.SECOND_TARGET.reply()
            scope.page_claimed = True
            return {"targetId": target.target_id}
        if meta in ("current_tab", "connection_status"):
            try:
                info = (await self._send("Target.getTargetInfo", {"targetId": target.target_id}))["targetInfo"]
            except Exception:
                return {"error": "cdp_disconnected"}
            if meta == "current_tab":
                return {"targetId": info.get("targetId"), "url": info.get("url", ""), "title": info.get("title", "")}
            url = info.get("url") or ""
            page = None
            if info.get("type") == "page" and not url.startswith(_INTERNAL):
                page = {"targetId": info.get("targetId"), "title": info.get("title") or "(untitled)", "url": url}
            return {"target_id": target.target_id, "session_id": target.session_id, "page": page}
        if meta in _LIFECYCLE_METAS:
            return Refusal.LIFECYCLE.reply()
        return Refusal.UNKNOWN_META.reply()

    async def _cdp(self, scope: OwnedScope, req: dict) -> dict:
        target = scope.target
        route = route_cdp(target, req.get("method") or "", req.get("params") or {}, req.get("session_id"))
        if isinstance(route, Refusal):
            return route.reply()
        session_id = target.session_id if isinstance(route, OnOwnedSession) else None
        try:
            return {"result": await self._send(route.method, route.params, session_id=session_id)}
        except Exception as e:
            if "Session with given id not found" in str(e):
                return Refusal.STALE_SESSION.reply()
            return {"error": str(e)}

    async def end(self, scope_id: ScopeId) -> dict:
        async with self._lock:
            scope = self._open.get(scope_id)
            if scope is None:
                if scope_id in self._closed:
                    return {"ok": True, "closed": "already"}
                return Refusal.UNKNOWN_SCOPE.reply()
            scope.state = ScopeState.CLOSING
            try:
                await asyncio.wait_for(
                    self._send("Target.disposeBrowserContext", {"browserContextId": scope.target.context_id}),
                    DISPOSE_TIMEOUT_S,
                )
            except TimeoutError:
                return {"error": "dispose failed: timed out"}
            except Exception as e:
                return {"error": f"dispose failed: {e}"}
            del self._open[scope_id]
            self._closed.append(scope_id)
            return {"ok": True, "closed": "disposed"}

    def absorb_event(self, method: str, params: dict, session_id: str | None) -> bool:
        if session_id is None:
            return False
        for scope in self._open.values():
            if scope.target.session_id != session_id:
                continue
            scope.events.append({"method": method, "params": params, "session_id": session_id})
            if method == "Page.javascriptDialogOpening":
                scope.dialog = params
            elif method == "Page.javascriptDialogClosed":
                scope.dialog = None
            return True
        return False

    async def close_all(self) -> list[str]:
        errors = []
        for scope_id in list(self._open):
            reply = await self.end(scope_id)
            if "error" in reply:
                errors.append(f"{scope_id}: {reply['error']}")
        return errors
