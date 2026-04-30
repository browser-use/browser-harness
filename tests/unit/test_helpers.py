import os
import tempfile
import time
from unittest.mock import patch

import pytest
from PIL import Image

from browser_harness import helpers


def _run(fake_png, width, height, **kwargs):
    fake = lambda method, **_: {"data": fake_png(width, height)}
    with patch("browser_harness.helpers.cdp", side_effect=fake), tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "shot.png")
        helpers.capture_screenshot(path, **kwargs)
        return Image.open(path).size


def test_max_dim_downsizes_oversized_image(fake_png):
    assert max(_run(fake_png, 4592, 2286, max_dim=1800)) == 1800


def test_max_dim_skips_when_image_already_small(fake_png):
    assert _run(fake_png, 800, 400, max_dim=1800) == (800, 400)


def test_max_dim_default_is_no_resize(fake_png):
    assert _run(fake_png, 4592, 2286) == (4592, 2286)


def test_page_info_raises_clear_error_on_js_exception():
    def fake_send(req):
        return {}

    def fake_cdp(method, **kwargs):
        return {
            "result": {
                "type": "object",
                "subtype": "error",
                "description": "ReferenceError: location is not defined",
            },
            "exceptionDetails": {
                "text": "Uncaught",
                "lineNumber": 0,
                "columnNumber": 16,
            },
        }

    with patch("browser_harness.helpers._send", side_effect=fake_send), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        with pytest.raises(RuntimeError, match="ReferenceError"):
            helpers.page_info()


# --- fill_input ---

def test_fill_input_focuses_types_and_fires_events():
    cdp_calls = []
    js_calls = []

    def fake_cdp(method, **kwargs):
        cdp_calls.append((method, kwargs))
        return {}

    def fake_js(expr, **kwargs):
        js_calls.append(expr)
        return True  # focus call must return True (element found)

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp), \
         patch("browser_harness.helpers.js", side_effect=fake_js):
        helpers.fill_input("#my-input", "hello")

    assert any("#my-input" in e for e in js_calls)
    key_downs = [m for m, _ in cdp_calls if m == "Input.dispatchKeyEvent"]
    assert len(key_downs) > 0
    assert any("input" in e and "change" in e for e in js_calls)


def test_fill_input_raises_when_element_not_found():
    def fake_js(expr, **kwargs):
        return False  # element not found

    with patch("browser_harness.helpers.js", side_effect=fake_js):
        with pytest.raises(RuntimeError, match="element not found"):
            helpers.fill_input("#missing", "hello")


def test_fill_input_clear_first_sends_ctrl_a_backspace():
    key_events = []

    def fake_cdp(method, **kwargs):
        if method == "Input.dispatchKeyEvent":
            key_events.append(kwargs)
        return {}

    def fake_js(expr, **kwargs):
        return True  # element found

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp), \
         patch("browser_harness.helpers.js", side_effect=fake_js):
        helpers.fill_input("#inp", "x", clear_first=True)

    keys_seen = [e.get("key") for e in key_events if e.get("type") == "keyDown"]
    assert "a" in keys_seen
    assert "Backspace" in keys_seen


def test_fill_input_no_clear_skips_ctrl_a():
    key_events = []

    def fake_cdp(method, **kwargs):
        if method == "Input.dispatchKeyEvent":
            key_events.append(kwargs)
        return {}

    def fake_js(expr, **kwargs):
        return True  # element found

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp), \
         patch("browser_harness.helpers.js", side_effect=fake_js):
        helpers.fill_input("#inp", "x", clear_first=False)

    keys_seen = [e.get("key") for e in key_events if e.get("type") == "keyDown"]
    assert "Backspace" not in keys_seen


# --- wait_for_element ---

def test_wait_for_element_returns_true_when_found_immediately():
    def fake_js(expr, **kwargs):
        return True

    with patch("browser_harness.helpers.js", side_effect=fake_js):
        assert helpers.wait_for_element("#target", timeout=2.0) is True


def test_wait_for_element_returns_false_on_timeout():
    def fake_js(expr, **kwargs):
        return False

    with patch("browser_harness.helpers.js", side_effect=fake_js), \
         patch("browser_harness.helpers.time") as mock_time:
        # simulate time advancing past the deadline immediately
        start = time.time()
        mock_time.time.side_effect = [start, start + 5.0]
        mock_time.sleep = lambda _: None
        assert helpers.wait_for_element("#missing", timeout=1.0) is False


def test_wait_for_element_visible_uses_computed_style_check():
    js_exprs = []

    def fake_js(expr, **kwargs):
        js_exprs.append(expr)
        return True

    with patch("browser_harness.helpers.js", side_effect=fake_js):
        helpers.wait_for_element("#btn", visible=True)

    assert any("getComputedStyle" in e for e in js_exprs)
    assert any("display" in e for e in js_exprs)
    # must NOT use offsetParent (fails for position:fixed elements)
    assert not any("offsetParent" in e for e in js_exprs)


def test_wait_for_element_non_visible_uses_simple_check():
    js_exprs = []

    def fake_js(expr, **kwargs):
        js_exprs.append(expr)
        return True

    with patch("browser_harness.helpers.js", side_effect=fake_js):
        helpers.wait_for_element("#btn", visible=False)

    assert any("querySelector" in e and "offsetParent" not in e for e in js_exprs)


# --- wait_for_network_idle ---

def test_wait_for_network_idle_returns_true_when_no_events():
    call_count = 0

    def fake_send(req):
        nonlocal call_count
        call_count += 1
        return {"events": []}

    with patch("browser_harness.helpers._send", side_effect=fake_send), \
         patch("browser_harness.helpers.time") as mock_time:
        start = 1000.0
        # first call: not idle yet; second call: idle window elapsed
        mock_time.time.side_effect = [start, start, start, start + 0.6, start + 0.6]
        mock_time.sleep = lambda _: None
        result = helpers.wait_for_network_idle(timeout=5.0, idle_ms=500)

    assert result is True


def test_wait_for_network_idle_waits_for_inflight_request():
    # Verifies inflight tracking: must not return True until loadingFinished,
    # even though >idle_ms elapses between requestWillBeSent and loadingFinished.
    # An event-silence-only implementation would return True at iter2 (wrong).
    events_seq = [
        [{"method": "Network.requestWillBeSent", "params": {"requestId": "req1"}}],
        [],   # >500ms elapsed — old impl returns True here; new must NOT
        [{"method": "Network.loadingFinished",   "params": {"requestId": "req1"}}],
        [],   # idle_ms after loadingFinished → return True
    ]
    idx = 0

    def fake_send(req):
        nonlocal idx
        evs = events_seq[min(idx, len(events_seq) - 1)]
        idx += 1
        return {"events": evs}

    with patch("browser_harness.helpers._send", side_effect=fake_send), \
         patch("browser_harness.helpers.time") as mock_time:
        start = 1000.0
        # inflight non-empty → short-circuit skips time.time() in idle check for iter1/iter2
        mock_time.time.side_effect = [
            start, start,       # deadline + last_activity init
            start + 0.1,        # iter1 while-check
            start + 0.1,        # iter1 rWS last_activity update
                                # iter1 idle-check: inflight non-empty → short-circuit
            start + 0.7,        # iter2 while-check (>500ms since rWS but request still in flight)
                                # iter2 idle-check: inflight non-empty → short-circuit
            start + 0.8,        # iter3 while-check
            start + 0.8,        # iter3 lF last_activity update
            start + 0.8,        # iter3 idle-check: 0ms < 500 → not idle
            start + 1.4,        # iter4 while-check
            start + 1.4,        # iter4 idle-check: 600ms >= 500 → True
        ]
        mock_time.sleep = lambda _: None
        result = helpers.wait_for_network_idle(timeout=5.0, idle_ms=500)

    assert result is True
    assert idx == 4  # did not short-circuit at iter2 despite silence > idle_ms


def test_wait_for_network_idle_returns_false_on_timeout():
    # Continuous rWS keeps inflight non-empty → idle check short-circuits every iteration.
    # time.time() is only called for while-check and rWS last_activity (not idle check).
    def fake_send(req):
        return {"events": [{"method": "Network.requestWillBeSent", "params": {"requestId": "r"}}]}

    with patch("browser_harness.helpers._send", side_effect=fake_send), \
         patch("browser_harness.helpers.time") as mock_time:
        start = 1000.0
        mock_time.time.side_effect = [
            start, start,       # deadline + last_activity init
            start + 0.1,        # iter1 while-check (in deadline)
            start + 0.1,        # iter1 rWS last_activity update
                                # iter1 idle-check: inflight non-empty → short-circuit
            start + 20.0,       # iter2 while-check (past deadline → exit)
        ]
        mock_time.sleep = lambda _: None
        result = helpers.wait_for_network_idle(timeout=10.0, idle_ms=500)

    assert result is False

