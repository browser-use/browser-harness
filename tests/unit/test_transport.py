import asyncio

import pytest

from browser_harness.transport import (
    WebDriverBiDiTransport,
    normalize_bidi_event,
    transport_from_environment,
)


def run(coro):
    return asyncio.run(coro)


def test_transport_factory_preserves_cdp_and_selects_bidi_explicitly():
    cdp = transport_from_environment({"BU_CDP_WS": "ws://edge.test/devtools/browser/1"})
    bidi = transport_from_environment(
        {
            "BU_BROWSER_PROTOCOL": "bidi",
            "BU_BIDI_URL": "http://localhost:9222",
            "BU_BIDI_CONNECT_HOST": "firefox.test",
        }
    )

    assert cdp.protocol == "cdp"
    assert cdp.engine == "edge"
    assert bidi.protocol == "bidi"
    assert bidi.engine == "firefox"
    assert bidi.endpoint == "http://localhost:9222"
    assert bidi.connect_host == "firefox.test"
    assert bidi.websocket_url == "ws://localhost:9222/session"


def test_bidi_transport_translates_navigation_and_script_evaluation():
    transport = WebDriverBiDiTransport("http://firefox.test:9222")
    transport.current_context = "context-1"
    calls = []

    async def command(method, params=None):
        calls.append((method, params))
        if method == "browsingContext.navigate":
            return {"navigation": "navigation-1", "url": params["url"]}
        if method == "script.evaluate":
            return {
                "type": "success",
                "result": {"type": "string", "value": "Angel3"},
            }
        raise AssertionError(method)

    transport._command = command

    navigation = run(
        transport.send_raw("Page.navigate", {"url": "https://angel3.test/tactical"})
    )
    evaluation = run(
        transport.send_raw(
            "Runtime.evaluate",
            {"expression": "document.title", "awaitPromise": True},
        )
    )

    assert navigation == {
        "frameId": "context-1",
        "loaderId": "navigation-1",
    }
    assert evaluation == {
        "result": {"type": "string", "value": "Angel3"},
    }
    assert calls == [
        (
            "browsingContext.navigate",
            {
                "context": "context-1",
                "url": "https://angel3.test/tactical",
                "wait": "none",
            },
        ),
        (
            "script.evaluate",
            {
                "expression": "document.title",
                "target": {"context": "context-1"},
                "awaitPromise": True,
                "resultOwnership": "none",
                "serializationOptions": {"maxObjectDepth": 10},
                "userActivation": False,
            },
        ),
    ]


def test_bidi_transport_reports_unsupported_diagnostics_before_dispatch():
    transport = WebDriverBiDiTransport("http://firefox.test:9222")
    transport.current_context = "context-1"

    with pytest.raises(RuntimeError, match="unsupported_browser_capability:HeapProfiler.collectGarbage"):
        run(transport.send_raw("HeapProfiler.collectGarbage"))


def test_bidi_events_normalize_to_guardian_health_categories():
    assert normalize_bidi_event(
        "log.entryAdded",
        {
            "type": "console",
            "method": "error",
            "text": "renderer failed",
            "args": [{"type": "string", "value": "renderer failed"}],
            "source": {"context": "context-1"},
        },
    ) == (
        "Runtime.consoleAPICalled",
        {
            "type": "error",
            "args": [{"type": "string", "value": "renderer failed"}],
        },
        "context-1",
    )

    assert normalize_bidi_event(
        "network.responseStarted",
        {
            "request": {"request": "request-1", "url": "https://angel3.test/api"},
            "response": {"url": "https://angel3.test/api", "status": 503, "statusText": "Unavailable"},
            "context": "context-1",
        },
    ) == (
        "Network.responseReceived",
        {
            "requestId": "request-1",
            "type": "Fetch",
            "response": {
                "url": "https://angel3.test/api",
                "status": 503,
                "statusText": "Unavailable",
            },
        },
        "context-1",
    )


def test_bidi_capability_manifest_uses_observed_subscriptions():
    transport = WebDriverBiDiTransport("http://firefox.test:9222")
    transport.browser_capabilities = {"browserName": "firefox", "browserVersion": "153.0"}
    transport.supported_events = {"log.entryAdded", "network.fetchError"}
    transport.unsupported_events = {"browsingContext.navigationFailed": "invalid argument"}

    manifest = transport.capabilities()

    assert manifest["engine"] == "firefox"
    assert manifest["protocol"] == "bidi"
    assert manifest["browser_version"] == "153.0"
    assert manifest["events"]["supported"] == ["log.entryAdded", "network.fetchError"]
    assert manifest["events"]["unsupported"] == {
        "browsingContext.navigationFailed": "invalid argument"
    }
    assert "evaluate" in manifest["actions"]


def test_bidi_transport_ends_session_before_closing_socket():
    calls = []

    class Socket:
        async def close(self):
            calls.append(("socket.close", None))

    transport = WebDriverBiDiTransport("http://firefox.test:9222")
    transport._socket = Socket()
    transport.session_id = "session-1"

    async def command(method, params=None):
        calls.append((method, params))
        return {}

    transport._command = command

    run(transport.close())

    assert calls == [("session.end", {}), ("socket.close", None)]
    assert transport._socket is None
    assert transport.session_id is None
