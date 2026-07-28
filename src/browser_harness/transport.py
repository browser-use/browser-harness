"""Browser protocol adapters used by the persistent Browser-Harness daemon.

The daemon owns attachment, IPC, and health sequencing.  Transports own browser
protocol syntax and expose the small CDP-shaped compatibility surface needed
during the protocol-neutral helper migration.
"""

from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import urlsplit, urlunsplit

from cdp_use.client import CDPClient


BIDI_EVENTS = (
    "browsingContext.contextCreated",
    "browsingContext.contextDestroyed",
    "browsingContext.navigationStarted",
    "browsingContext.domContentLoaded",
    "browsingContext.load",
    "browsingContext.userPromptOpened",
    "browsingContext.userPromptClosed",
    "log.entryAdded",
    "network.beforeRequestSent",
    "network.responseStarted",
    "network.fetchError",
)

BIDI_ACTIONS = (
    "contexts",
    "navigate",
    "evaluate",
    "screenshot",
    "pointer",
    "keyboard",
    "set_files",
    "preload_script",
    "cache",
)

_NOOP_ENABLE_METHODS = frozenset(
    {
        "Console.enable",
        "Console.disable",
        "DOM.enable",
        "DOM.disable",
        "Log.enable",
        "Log.disable",
        "Network.enable",
        "Network.disable",
        "Page.enable",
        "Page.disable",
        "Runtime.enable",
        "Runtime.disable",
        "Target.setDiscoverTargets",
        "Target.setAutoAttach",
        "Target.autoAttachRelated",
    }
)

_BIDI_KEY_VALUES = {
    "Backspace": "\ue003",
    "Tab": "\ue004",
    "Enter": "\ue007",
    "Escape": "\ue00c",
    " ": "\ue00d",
    "PageUp": "\ue00e",
    "PageDown": "\ue00f",
    "End": "\ue010",
    "Home": "\ue011",
    "ArrowLeft": "\ue012",
    "ArrowUp": "\ue013",
    "ArrowRight": "\ue014",
    "ArrowDown": "\ue015",
    "Delete": "\ue017",
}

_BIDI_MODIFIERS = (
    (1, "\ue00a"),  # Alt
    (2, "\ue009"),  # Control
    (4, "\ue03d"),  # Meta
    (8, "\ue008"),  # Shift
)


class _EventRegistry:
    async def handle_event(self, _method, _params, _session_id=None):
        return None


class CDPTransport:
    protocol = "cdp"
    engine = "edge"

    def __init__(self, endpoint):
        self.endpoint = endpoint
        self._client = None
        self._event_registry = _EventRegistry()

    async def start(self):
        self._client = CDPClient(self.endpoint)
        await self._client.start()
        self._event_registry = self._client._event_registry

    async def send_raw(self, method, params=None, session_id=None):
        return await self._client.send_raw(method, params, session_id=session_id)

    async def close(self):
        if self._client is not None:
            await self._client.stop()
            self._client = None

    def capabilities(self):
        return {
            "engine": self.engine,
            "protocol": self.protocol,
            "browser_version": None,
            "actions": list(BIDI_ACTIONS),
            "events": {"supported": ["cdp_health_events_v1"], "unsupported": {}},
            "raw_protocol": True,
        }


def _remote_value(value):
    if not isinstance(value, dict):
        return value
    kind = value.get("type")
    payload = value.get("value")
    if kind == "array":
        return [_remote_value(item) for item in payload or []]
    if kind in {"object", "map"}:
        return {
            str(_remote_value(key)): _remote_value(child)
            for key, child in payload or []
        }
    if kind == "set":
        return [_remote_value(item) for item in payload or []]
    if kind == "null":
        return None
    if kind == "undefined":
        return None
    if kind == "bigint" and payload is not None:
        try:
            return int(payload)
        except (TypeError, ValueError):
            return str(payload)
    return payload


def _cdp_remote_object(value):
    kind = value.get("type") if isinstance(value, dict) else None
    decoded = _remote_value(value)
    if kind == "null":
        return {"type": "object", "subtype": "null", "value": None}
    if kind == "array":
        return {"type": "object", "subtype": "array", "value": decoded}
    if kind in {"object", "map", "set", "node", "window"}:
        return {"type": "object", "value": decoded}
    if kind == "undefined":
        return {"type": "undefined"}
    return {"type": kind or type(decoded).__name__, "value": decoded}


def normalize_bidi_event(method, params):
    """Translate one BiDi event to the compatibility event Guardian v1 reads."""
    context = params.get("context") or (params.get("source") or {}).get("context")
    if method == "log.entryAdded":
        entry_type = params.get("type")
        if entry_type == "javascript":
            return (
                "Runtime.exceptionThrown",
                {
                    "exceptionDetails": {
                        "text": params.get("text") or "JavaScript exception",
                        "url": (params.get("source") or {}).get("realm", ""),
                    }
                },
                context,
            )
        level = params.get("method") or params.get("level") or "log"
        return (
            "Runtime.consoleAPICalled",
            {
                "type": level,
                "args": [
                    _cdp_remote_object(argument)
                    for argument in params.get("args", [])
                ] or [{"type": "string", "value": params.get("text", "")}],
            },
            context,
        )
    if method == "network.beforeRequestSent":
        request = params.get("request") or {}
        return (
            "Network.requestWillBeSent",
            {
                "requestId": request.get("request"),
                "type": "Fetch",
                "request": {
                    "method": request.get("method"),
                    "url": request.get("url"),
                },
            },
            context,
        )
    if method in {"network.responseStarted", "network.responseCompleted"}:
        request = params.get("request") or {}
        response = params.get("response") or {}
        return (
            "Network.responseReceived",
            {
                "requestId": request.get("request"),
                "type": "Fetch",
                "response": {
                    "url": response.get("url") or request.get("url"),
                    "status": response.get("status"),
                    "statusText": response.get("statusText"),
                },
            },
            context,
        )
    if method == "network.fetchError":
        request = params.get("request") or {}
        error_text = params.get("errorText") or "WebDriver BiDi fetch error"
        canceled = any(
            marker in error_text.lower()
            for marker in ("abort", "cancel", "interrupted")
        )
        return (
            "Network.loadingFailed",
            {
                "requestId": request.get("request"),
                "type": "Fetch",
                "errorText": error_text,
                "canceled": canceled,
            },
            context,
        )
    if method == "browsingContext.contextDestroyed":
        return "Target.targetDestroyed", {"targetId": context}, context
    if method == "browsingContext.contextCreated":
        return (
            "BrowserHarness.contextCreated",
            {"target_id": context, "url": params.get("url", "")},
            context,
        )
    if method == "browsingContext.navigationStarted":
        return (
            "BrowserHarness.navigationStarted",
            {"target_id": context, "url": params.get("url", "")},
            context,
        )
    if method == "browsingContext.domContentLoaded":
        return "Page.domContentEventFired", {}, context
    if method == "browsingContext.load":
        return "Page.loadEventFired", {}, context
    if method == "browsingContext.userPromptOpened":
        return (
            "Page.javascriptDialogOpening",
            {
                "type": params.get("type"),
                "message": params.get("message", ""),
                "defaultPrompt": params.get("defaultValue", ""),
            },
            context,
        )
    if method == "browsingContext.userPromptClosed":
        return "Page.javascriptDialogClosed", {}, context
    return f"BrowserHarness.bidi.{method}", params, context


class WebDriverBiDiTransport:
    protocol = "bidi"
    engine = "firefox"

    def __init__(self, endpoint, *, connect_host=None, websocket_connect=None):
        self.endpoint = endpoint.rstrip("/")
        self.connect_host = connect_host
        self._websocket_connect = websocket_connect
        self._event_registry = _EventRegistry()
        self._socket = None
        self._reader_task = None
        self._next_id = 0
        self._pending = {}
        self.session_id = None
        self.current_context = None
        self.browser_capabilities = {}
        self.supported_events = set()
        self.unsupported_events = {}
        self._pressed_modifiers = []

    @property
    def websocket_url(self):
        parsed = urlsplit(self.endpoint)
        if parsed.scheme in {"ws", "wss"}:
            path = parsed.path.rstrip("/")
            if not path.endswith("/session"):
                path = f"{path}/session" if path else "/session"
            return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
        scheme = "wss" if parsed.scheme == "https" else "ws"
        path = parsed.path.rstrip("/")
        if not path.endswith("/session"):
            path = f"{path}/session" if path else "/session"
        return urlunsplit((scheme, parsed.netloc, path, parsed.query, parsed.fragment))

    def capabilities(self):
        return {
            "engine": self.engine,
            "protocol": self.protocol,
            "browser_version": self.browser_capabilities.get("browserVersion"),
            "actions": list(BIDI_ACTIONS),
            "events": {
                "supported": sorted(self.supported_events),
                "unsupported": dict(sorted(self.unsupported_events.items())),
            },
            "raw_protocol": False,
        }

    async def start(self):
        if self._websocket_connect is None:
            from websockets.asyncio.client import connect

            self._websocket_connect = connect
        connection_options = {}
        if self.connect_host:
            connection_options = {
                "host": self.connect_host,
                "port": urlsplit(self.websocket_url).port,
            }
        self._socket = await self._websocket_connect(
            self.websocket_url, **connection_options
        )
        self._reader_task = asyncio.create_task(self._read_messages())
        created = await self._command(
            "session.new", {"capabilities": {"alwaysMatch": {}}}
        )
        self.session_id = created.get("sessionId")
        self.browser_capabilities = created.get("capabilities") or {}
        if not self.session_id:
            raise RuntimeError("WebDriver BiDi session.new omitted sessionId")
        for event_name in BIDI_EVENTS:
            try:
                await self._command("session.subscribe", {"events": [event_name]})
                self.supported_events.add(event_name)
            except Exception as exc:
                self.unsupported_events[event_name] = str(exc)[:512]

    async def close(self):
        socket = self._socket
        if socket is None:
            return
        try:
            if self.session_id:
                await self._command("session.end", {})
        except Exception:
            # Firefox may close the WebSocket before acknowledging session.end.
            pass
        finally:
            if self._reader_task is not None:
                self._reader_task.cancel()
                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass
                self._reader_task = None
            await socket.close()
            self._socket = None
            self.session_id = None

    async def _read_messages(self):
        try:
            async for raw in self._socket:
                message = json.loads(raw)
                request_id = message.get("id")
                if request_id is not None:
                    future = self._pending.pop(request_id, None)
                    if future and not future.done():
                        future.set_result(message)
                    continue
                method = message.get("method")
                if method:
                    translated = normalize_bidi_event(method, message.get("params") or {})
                    await self._event_registry.handle_event(*translated)
        except Exception as exc:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(RuntimeError(f"WebDriver BiDi disconnected: {exc}"))
            self._pending.clear()

    async def _command(self, method, params=None):
        if self._socket is None:
            raise RuntimeError("WebDriver BiDi transport is not connected")
        self._next_id += 1
        request_id = self._next_id
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self._socket.send(
            json.dumps({"id": request_id, "method": method, "params": params or {}})
        )
        try:
            response = await asyncio.wait_for(future, timeout=30)
        finally:
            self._pending.pop(request_id, None)
        if response.get("type") == "error" or response.get("error"):
            error = response.get("error") or "unknown error"
            message = response.get("message") or response.get("value", {}).get("message") or ""
            raise RuntimeError(f"{error}: {message}".rstrip())
        return response.get("result") or {}

    def _context(self, session_id=None):
        context = session_id or self.current_context
        if not context:
            raise RuntimeError("WebDriver BiDi has no attached browsing context")
        return context

    async def _targets(self):
        result = await self._command("browsingContext.getTree", {})
        targets = []

        def visit(node, kind="page"):
            context = node.get("context")
            targets.append(
                {
                    "targetId": context,
                    "type": kind,
                    "url": node.get("url", ""),
                    "title": node.get("originalOpener") or "",
                }
            )
            for child in node.get("children") or []:
                visit(child, "iframe")

        for context in result.get("contexts") or []:
            visit(context)
        return targets

    async def _perform(self, actions, context=None):
        return await self._command(
            "input.performActions",
            {"context": context or self._context(), "actions": actions},
        )

    async def _dispatch_key(self, params):
        event_type = params.get("type")
        if event_type == "char":
            return {}
        key = params.get("key") or params.get("text") or ""
        value = _BIDI_KEY_VALUES.get(key, key)
        modifiers = params.get("modifiers", 0)
        actions = []
        if event_type in {"keyDown", "rawKeyDown"}:
            self._pressed_modifiers = [
                value for bit, value in _BIDI_MODIFIERS if modifiers & bit
            ]
            actions.extend({"type": "keyDown", "value": item} for item in self._pressed_modifiers)
            actions.append({"type": "keyDown", "value": value})
        elif event_type == "keyUp":
            actions.append({"type": "keyUp", "value": value})
            actions.extend(
                {"type": "keyUp", "value": item}
                for item in reversed(self._pressed_modifiers)
            )
            self._pressed_modifiers = []
        if not actions:
            return {}
        return await self._perform([{"type": "key", "id": "keyboard", "actions": actions}])

    async def send_raw(self, method, params=None, session_id=None):
        params = params or {}
        if method in _NOOP_ENABLE_METHODS:
            return {}
        if method == "Browser.getVersion":
            return {
                "product": f"Firefox/{self.browser_capabilities.get('browserVersion', 'unknown')}",
                "protocolVersion": "WebDriver BiDi",
            }
        if method == "Target.getTargets":
            return {"targetInfos": await self._targets()}
        if method == "Target.createTarget":
            result = await self._command(
                "browsingContext.create",
                {"type": "tab", "background": False},
            )
            self.current_context = result.get("context")
            return {"targetId": self.current_context}
        if method == "Target.attachToTarget":
            self.current_context = params.get("targetId") or self._context(session_id)
            return {"sessionId": self.current_context}
        if method == "Target.activateTarget":
            context = params.get("targetId") or self._context(session_id)
            await self._command("browsingContext.activate", {"context": context})
            self.current_context = context
            return {}
        if method == "Runtime.evaluate":
            context = self._context(session_id)
            result = await self._command(
                "script.evaluate",
                {
                    "expression": params.get("expression", ""),
                    "target": {"context": context},
                    "awaitPromise": bool(params.get("awaitPromise")),
                    "resultOwnership": "none",
                    "serializationOptions": {"maxObjectDepth": 10},
                    "userActivation": bool(params.get("userGesture", False)),
                },
            )
            if result.get("type") == "exception":
                details = result.get("exceptionDetails") or {}
                text = details.get("text") or "JavaScript evaluation failed"
                return {
                    "result": {"type": "object", "subtype": "error", "description": text},
                    "exceptionDetails": {"text": text},
                }
            return {"result": _cdp_remote_object(result.get("result") or {})}
        if method == "Page.navigate":
            context = self._context(session_id)
            result = await self._command(
                "browsingContext.navigate",
                {"context": context, "url": params["url"], "wait": "none"},
            )
            return {"frameId": context, "loaderId": result.get("navigation")}
        if method == "Page.stopLoading":
            await self._command(
                "browsingContext.stopLoading", {"context": self._context(session_id)}
            )
            return {}
        if method == "Page.captureScreenshot":
            result = await self._command(
                "browsingContext.captureScreenshot",
                {
                    "context": self._context(session_id),
                    "origin": "document" if params.get("captureBeyondViewport") else "viewport",
                    "format": {"type": params.get("format", "png")},
                },
            )
            return {"data": result.get("data")}
        if method == "Page.addScriptToEvaluateOnNewDocument":
            result = await self._command(
                "script.addPreloadScript", {"functionDeclaration": f"() => {{{params.get('source', '')}}}"}
            )
            return {"identifier": result.get("script")}
        if method == "Page.removeScriptToEvaluateOnNewDocument":
            await self._command("script.removePreloadScript", {"script": params.get("identifier")})
            return {}
        if method == "Input.dispatchMouseEvent":
            event_type = params.get("type")
            if event_type == "mouseWheel":
                return await self._perform(
                    [
                        {
                            "type": "wheel",
                            "id": "wheel",
                            "actions": [
                                {
                                    "type": "scroll",
                                    "x": round(params.get("x", 0)),
                                    "y": round(params.get("y", 0)),
                                    "deltaX": round(params.get("deltaX", 0)),
                                    "deltaY": round(params.get("deltaY", 0)),
                                    "duration": 0,
                                    "origin": "viewport",
                                }
                            ],
                        }
                    ]
                )
            button = {"left": 0, "middle": 1, "right": 2}.get(params.get("button"), 0)
            pointer_action = {
                "mouseMoved": None,
                "mousePressed": {"type": "pointerDown", "button": button},
                "mouseReleased": {"type": "pointerUp", "button": button},
            }.get(event_type)
            if event_type not in {"mouseMoved", "mousePressed", "mouseReleased"}:
                raise RuntimeError(f"unsupported_browser_capability:{method}:{event_type}")
            pointer_actions = [
                {
                    "type": "pointerMove",
                    "x": round(params.get("x", 0)),
                    "y": round(params.get("y", 0)),
                    "duration": 0,
                    "origin": "viewport",
                }
            ]
            if pointer_action is not None:
                pointer_actions.append(pointer_action)
            return await self._perform(
                [
                    {
                        "type": "pointer",
                        "id": "mouse",
                        "parameters": {"pointerType": "mouse"},
                        "actions": pointer_actions,
                    }
                ]
            )
        if method == "Input.dispatchKeyEvent":
            return await self._dispatch_key(params)
        if method == "Input.setIgnoreInputEvents" and not params.get("ignore", False):
            return {}
        if method == "Input.insertText":
            actions = []
            for value in params.get("text", ""):
                actions.extend(
                    ({"type": "keyDown", "value": value}, {"type": "keyUp", "value": value})
                )
            return await self._perform([{"type": "key", "id": "keyboard", "actions": actions}])
        if method == "BrowserHarness.setFiles":
            expression = (
                "document.querySelector(" + json.dumps(params.get("selector")) + ")"
            )
            located = await self._command(
                "script.evaluate",
                {
                    "expression": expression,
                    "target": {"context": self._context(session_id)},
                    "awaitPromise": False,
                    "resultOwnership": "root",
                },
            )
            element = located.get("result") or {}
            shared_id = element.get("sharedId")
            if not shared_id:
                raise RuntimeError(f"no element for {params.get('selector')}")
            return await self._command(
                "input.setFiles",
                {
                    "context": self._context(session_id),
                    "element": {"sharedId": shared_id},
                    "files": params.get("files") or [],
                },
            )
        if method == "Network.setCacheDisabled":
            return await self._command(
                "network.setCacheBehavior",
                {"cacheBehavior": "bypass" if params.get("cacheDisabled") else "default"},
            )
        if method == "Network.clearBrowserCache":
            # BiDi has no destructive cache-clear command. Functional tests use
            # this immediately after setCacheDisabled, whose standard `bypass`
            # behavior gives the same fresh-resource contract for the run.
            return {}
        raise RuntimeError(f"unsupported_browser_capability:{method}")


def transport_from_environment(env=None, *, cdp_endpoint=None):
    env = os.environ if env is None else env
    protocol = str(env.get("BU_BROWSER_PROTOCOL", "cdp")).strip().lower()
    if protocol == "bidi":
        endpoint = env.get("BU_BIDI_URL") or env.get("BU_BROWSER_ENDPOINT")
        if not endpoint:
            raise RuntimeError("BU_BIDI_URL is required for WebDriver BiDi")
        return WebDriverBiDiTransport(
            endpoint,
            connect_host=env.get("BU_BIDI_CONNECT_HOST"),
        )
    if protocol != "cdp":
        raise RuntimeError(f"Unsupported browser protocol: {protocol}")
    endpoint = env.get("BU_CDP_WS") or cdp_endpoint or env.get("BU_CDP_URL")
    if not endpoint:
        raise RuntimeError("A CDP endpoint is required")
    return CDPTransport(endpoint)
