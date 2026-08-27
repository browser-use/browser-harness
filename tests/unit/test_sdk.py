"""Unit tests for browser_harness.sdk -- daemon replaced by a canned transport."""
import asyncio
import json
from pathlib import Path

import pytest

from browser_harness.sdk import Browser, Element, HarnessError, PageInfo
from browser_harness.sdk.views import Tab


class FakeTransport:
    """Stands in for HarnessClient.send. Handlers are keyed by CDP method name
    or ("meta", command); values are response dicts or callables(req) -> dict."""

    def __init__(self, handlers=None):
        self.handlers = dict(handlers or {})
        self.calls = []

    async def send(self, req, request_timeout=None):
        self.calls.append(req)
        key = ("meta", req["meta"]) if "meta" in req else req["method"]
        handler = self.handlers.get(key, {})
        r = handler(req) if callable(handler) else handler
        if "error" in r:
            raise HarnessError(r["error"])
        return r

    def cdp_calls(self, method):
        return [c for c in self.calls if c.get("method") == method]


def make_browser(handlers=None):
    browser = Browser(auto_start=False)
    browser._started = True
    transport = FakeTransport(handlers)
    browser.client.send = transport.send
    return browser, transport


def evaluate_value(value):
    """CDP Runtime.evaluate response carrying a returnByValue result."""
    return {"result": {"result": {"value": value}}}


def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        Browser(name="../etc")


def test_page_info_parses_geometry():
    payload = {"url": "https://x.test/", "title": "X", "w": 1200, "h": 800,
               "sx": 0, "sy": 150, "pw": 1200, "ph": 4000}
    browser, _ = make_browser({
        ("meta", "pending_dialog"): {},
        "Runtime.evaluate": evaluate_value(json.dumps(payload)),
    })
    info = asyncio.run(browser.page_info())
    assert isinstance(info, PageInfo)
    assert info.url == "https://x.test/"
    assert info.viewport_width == 1200
    assert info.scroll_y == 150
    assert info.page_height == 4000
    assert info.dialog is None


def test_page_info_reports_pending_dialog():
    browser, transport = make_browser({
        ("meta", "pending_dialog"): {"dialog": {"type": "confirm", "message": "Leave?"}},
    })
    info = asyncio.run(browser.page_info())
    assert info.dialog is not None
    assert info.dialog.type == "confirm"
    assert info.dialog.message == "Leave?"
    # geometry must not be queried while the js thread is frozen
    assert not transport.cdp_calls("Runtime.evaluate")


def test_find_all_filters_ax_tree():
    nodes = [
        {"ignored": True, "backendDOMNodeId": 1, "role": {"value": "button"}, "name": {"value": "Sign in"}},
        {"role": {"value": "button"}, "name": {"value": "Sign in"}},  # no backing DOM node
        {"backendDOMNodeId": 3, "role": {"value": "button"}, "name": {"value": "Sign in"}},
        {"backendDOMNodeId": 4, "role": {"value": "link"}, "name": {"value": "Sign in"}},
        {"backendDOMNodeId": 5, "role": {"value": "button"}, "name": {"value": "Cancel"}},
    ]
    browser, _ = make_browser({"Accessibility.getFullAXTree": {"result": {"nodes": nodes}}})

    buttons = asyncio.run(browser.find_all(role="button", name="Sign in"))
    assert [b.backend_node_id for b in buttons] == [3]

    # exact equality only -- no substring or case-insensitive matching
    assert asyncio.run(browser.find_all(role="button", name="sign")) == []
    assert asyncio.run(browser.find_all(name="sign in")) == []

    by_name = asyncio.run(browser.find_all(name="Sign in"))
    assert [b.backend_node_id for b in by_name] == [3, 4]

    unfiltered = asyncio.run(browser.find_all())
    assert [b.backend_node_id for b in unfiltered] == [3, 4, 5]


def test_element_click_dispatches_at_box_center():
    nodes = [{"backendDOMNodeId": 7, "role": {"value": "button"}, "name": {"value": "Go"}}]
    browser, transport = make_browser({
        "Accessibility.getFullAXTree": {"result": {"nodes": nodes}},
        "DOM.scrollIntoViewIfNeeded": {"result": {}},
        "DOM.getBoxModel": {"result": {"model": {"content": [10, 10, 110, 10, 110, 60, 10, 60]}}},
        "Input.dispatchMouseEvent": {"result": {}},
    })
    el = asyncio.run(browser.find(role="button"))
    assert el is not None
    asyncio.run(el.click())
    events = transport.cdp_calls("Input.dispatchMouseEvent")
    assert [e["params"]["type"] for e in events] == ["mousePressed", "mouseReleased"]
    assert all(e["params"]["x"] == 60 and e["params"]["y"] == 35 for e in events)


def test_press_key_special_key_carries_text_no_char_event():
    browser, transport = make_browser({"Input.dispatchKeyEvent": {"result": {}}})
    asyncio.run(browser.press_key("Enter"))
    events = transport.cdp_calls("Input.dispatchKeyEvent")
    assert [e["params"]["type"] for e in events] == ["keyDown", "keyUp"]
    assert events[0]["params"]["text"] == "\r"
    assert events[0]["params"]["windowsVirtualKeyCode"] == 13


def test_press_key_printable_emits_char_event():
    browser, transport = make_browser({"Input.dispatchKeyEvent": {"result": {}}})
    asyncio.run(browser.press_key("a"))
    events = transport.cdp_calls("Input.dispatchKeyEvent")
    assert [e["params"]["type"] for e in events] == ["keyDown", "char", "keyUp"]
    assert "text" not in events[0]["params"]
    assert events[1]["params"]["text"] == "a"


def test_new_tab_reuses_blank_current_tab():
    browser, transport = make_browser({
        ("meta", "current_tab"): {"targetId": "T1", "title": "", "url": "about:blank"},
        "Page.navigate": {"result": {"frameId": "f"}},
    })
    tid = asyncio.run(browser.new_tab("https://x.test/"))
    assert tid == "T1"
    assert not transport.cdp_calls("Target.createTarget")
    assert transport.cdp_calls("Page.navigate")[0]["params"]["url"] == "https://x.test/"


def test_switch_tab_accepts_tab_object():
    browser, transport = make_browser({
        "Runtime.evaluate": evaluate_value(None),
        "Target.activateTarget": {"result": {}},
        "Target.attachToTarget": {"result": {"sessionId": "S9"}},
        ("meta", "set_session"): {"ok": True},
    })
    sid = asyncio.run(browser.switch_tab(Tab(target_id="T9")))
    assert sid == "S9"
    assert transport.cdp_calls("Target.activateTarget")[0]["params"]["targetId"] == "T9"
    set_session = [c for c in transport.calls if c.get("meta") == "set_session"]
    assert set_session[0]["session_id"] == "S9" and set_session[0]["target_id"] == "T9"


def test_js_retries_illegal_return_with_wrapper():
    attempts = []

    def evaluate(req):
        attempts.append(req["params"]["expression"])
        if len(attempts) == 1:
            return {"result": {"exceptionDetails": {"text": "Uncaught"},
                               "result": {"description": "SyntaxError: Illegal return statement"}}}
        return {"result": {"result": {"value": 42}}}

    browser, _ = make_browser({"Runtime.evaluate": evaluate})
    assert asyncio.run(browser.js("return 42")) == 42
    assert attempts[1] == "(function(){return 42})()"


def test_js_validates_into_model():
    from pydantic import BaseModel

    class Cart(BaseModel):
        items: int
        total: float

    browser, _ = make_browser({
        "Runtime.evaluate": evaluate_value(json.dumps({"items": 3, "total": 9.5})),
    })
    cart = asyncio.run(browser.js("JSON.stringify(cart)", model=Cart))
    assert cart == Cart(items=3, total=9.5)


def test_list_tabs_excludes_internal_when_asked():
    targets = [
        {"type": "page", "targetId": "A", "title": "Doc", "url": "https://x.test/"},
        {"type": "page", "targetId": "B", "title": "Settings", "url": "chrome://settings"},
        {"type": "iframe", "targetId": "C", "title": "", "url": "https://ad.test/"},
        {"type": "page", "targetId": "D", "title": "Starting agent 1", "url": "about:blank"},
    ]
    browser, _ = make_browser({"Target.getTargets": {"result": {"targetInfos": targets}}})
    all_tabs = asyncio.run(browser.list_tabs())
    assert [t.target_id for t in all_tabs] == ["A", "B"]
    real = asyncio.run(browser.list_tabs(include_chrome=False))
    assert [t.target_id for t in real] == ["A"]


def test_client_reads_responses_larger_than_default_stream_limit(monkeypatch):
    """A heavy page's AX tree is one multi-MB JSON line -- must not trip asyncio's 64KiB readline limit."""
    import tempfile

    from browser_harness import _ipc
    from browser_harness.sdk.client import HarnessClient

    # not tmp_path -- pytest's dir is too deep for the 104-byte AF_UNIX sun_path limit
    sock_path = Path(tempfile.mkdtemp(prefix="bhsdk")) / "bu.sock"
    monkeypatch.setattr(_ipc, "_sock_path", lambda name: sock_path)
    big = {"result": {"nodes": ["x" * 1024] * 2048}}  # ~2MB line

    async def scenario():
        async def handler(reader, writer):
            await reader.readline()
            writer.write((json.dumps(big) + "\n").encode())
            await writer.drain()
            writer.close()

        server = await asyncio.start_unix_server(handler, path=str(sock_path))
        async with server:
            client = HarnessClient("default")
            return await client.cdp("Accessibility.getFullAXTree")

    result = asyncio.run(scenario())
    assert len(result["nodes"]) == 2048


def test_fill_input_raises_when_element_missing():
    browser, _ = make_browser({"Runtime.evaluate": evaluate_value(False)})
    with pytest.raises(HarnessError, match="element not found"):
        asyncio.run(browser.fill_input("#nope", "hi"))


def test_select_all_modifier_follows_browser_platform_not_client():
    """Select-all follows navigator.platform, never sys.platform -- remote browsers aren't macs."""

    def evaluate(req):
        assert "navigator.platform" in req["params"]["expression"]
        return {"result": {"result": {"value": "Linux x86_64"}}}

    browser, transport = make_browser({
        "Runtime.evaluate": evaluate,
        "Input.dispatchKeyEvent": {"result": {}},
    })
    asyncio.run(browser._select_all())
    key_events = transport.cdp_calls("Input.dispatchKeyEvent")
    assert [e["params"]["type"] for e in key_events] == ["rawKeyDown", "keyUp"]
    assert all(e["params"]["modifiers"] == 2 for e in key_events)  # ctrl, not cmd

    # cached -- second call must not re-query the page
    transport.handlers["Runtime.evaluate"] = {"error": "should not be called"}
    asyncio.run(browser._select_all())


# --- implementation conformance: things wire-parity cannot see ---


def test_every_timeout_surfaces_as_harness_error():
    """cdp() used to raise raw TimeoutError while js() raised HarnessError, so
    `except HarnessError` silently missed timeouts -- that killed the recovery
    paths in switch_tab/ensure_real_tab."""
    import tempfile

    from browser_harness import _ipc
    from browser_harness.sdk.client import HarnessClient

    sock_path = Path(tempfile.mkdtemp(prefix="bhto")) / "bu.sock"

    async def scenario():
        stop = asyncio.Event()

        async def handler(reader, writer):
            await reader.readline()
            await stop.wait()  # hold the connection open; never answer

        server = await asyncio.start_unix_server(handler, path=str(sock_path))
        try:
            client = HarnessClient("default", request_timeout=0.15)
            raised = []
            for call in (
                lambda: client.cdp("Page.navigate", url="x"),
                lambda: client.meta("current_tab"),
                lambda: client.send({"method": "DOM.getDocument", "params": {}}),
            ):
                try:
                    await call()
                except BaseException as e:  # noqa: BLE001 - the type is the assertion
                    raised.append(e)
            return raised
        finally:
            stop.set()  # release handlers before closing, or close() waits forever
            server.close()

    original = _ipc._sock_path
    _ipc._sock_path = lambda name: sock_path
    try:
        raised = asyncio.run(scenario())
    finally:
        _ipc._sock_path = original

    assert len(raised) == 3, "every call should have failed"
    for error in raised:
        assert isinstance(error, HarnessError), f"got {type(error).__name__}, not HarnessError"
        assert "timed out" in str(error)


def test_stale_element_error_is_actionable_and_keeps_box_model_text():
    """Stale handles gave a cryptic CDP string. The box-model message must stay
    verbatim -- the agent layer keys its select_dropdown fallback on it."""
    from browser_harness.sdk.browser import _stale

    element = Element(None, backend_node_id=7, role="button", name="Go")  # type: ignore[arg-type]
    stale = _stale(HarnessError("{'code': -32000, 'message': 'Node with given id does not belong to the document'}"), element)
    assert "stale" in str(stale) and "find()" in str(stale)

    box = HarnessError("{'code': -32000, 'message': 'Could not compute box model.'}")
    assert _stale(box, element) is box, "unrelated errors must pass through unchanged"


def test_ax_tree_is_not_refetched_for_back_to_back_lookups():
    """Several find() calls in one agent step should not each pull a multi-MB tree."""
    nodes = [{"backendDOMNodeId": 3, "role": {"value": "button"}, "name": {"value": "Go"}}]
    browser, transport = make_browser({"Accessibility.getFullAXTree": {"result": {"nodes": nodes}}})

    async def scenario():
        await browser.find_all(role="button")
        await browser.find_all(role="link")
        await browser.find_all()

    asyncio.run(scenario())
    assert len(transport.cdp_calls("Accessibility.getFullAXTree")) == 1

    # find() polls for new state, so it must bypass the cache
    asyncio.run(browser.find_all(role="button", fresh=True))
    assert len(transport.cdp_calls("Accessibility.getFullAXTree")) == 2


def test_package_ships_a_py_typed_marker():
    """Without it every downstream import resolves to Any."""
    import browser_harness

    assert (Path(browser_harness.__file__).parent / "py.typed").exists()
