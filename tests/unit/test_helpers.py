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


def _seed_skill(tmp_path):
    site = tmp_path / "domain-skills" / "example"
    site.mkdir(parents=True)
    (site / "scraping.md").write_text("hi")


def test_goto_url_omits_domain_skills_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("BH_DOMAIN_SKILLS", raising=False)
    monkeypatch.setattr(helpers, "AGENT_WORKSPACE", tmp_path)
    _seed_skill(tmp_path)
    with patch("browser_harness.helpers.cdp", return_value={"frameId": "f"}):
        result = helpers.goto_url("https://www.example.com/")
    assert result == {"frameId": "f"}


def test_goto_url_includes_domain_skills_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("BH_DOMAIN_SKILLS", "1")
    monkeypatch.setattr(helpers, "AGENT_WORKSPACE", tmp_path)
    _seed_skill(tmp_path)
    with patch("browser_harness.helpers.cdp", return_value={"frameId": "f"}):
        result = helpers.goto_url("https://www.example.com/")
    assert result == {"frameId": "f", "domain_skills": ["scraping.md"]}


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


def test_fill_input_clear_first_sends_select_all_then_backspace():
    import sys

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

    # The "a" must be dispatched with the platform-correct modifier (Meta=4 on
    # macOS, Ctrl=2 elsewhere). Without the modifier, the field would never get
    # selected — it would just receive a literal "a".
    expected_mod = 4 if sys.platform == "darwin" else 2
    a_events = [e for e in key_events if e.get("key") == "a"]
    assert a_events, "expected an 'a' key event for select-all"
    assert all(e.get("modifiers") == expected_mod for e in a_events), \
        f"select-all 'a' must carry modifiers={expected_mod}; got {[e.get('modifiers') for e in a_events]}"

    # Crucial: no `char` event for the "a" — emitting one makes Chrome treat
    # Cmd/Ctrl+A as a printable letter instead of a shortcut.
    assert not any(e.get("type") == "char" and e.get("text") == "a" for e in key_events), \
        "select-all must not emit a 'char' event with text='a' (would cancel the shortcut)"

    # Backspace still fires (via press_key, which uses keyDown).
    keys_down = [e.get("key") for e in key_events if e.get("type") in ("keyDown", "rawKeyDown")]
    assert "Backspace" in keys_down


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


def test_wait_for_element_visible_uses_check_visibility():
    js_exprs = []

    def fake_js(expr, **kwargs):
        js_exprs.append(expr)
        return True

    with patch("browser_harness.helpers.js", side_effect=fake_js):
        helpers.wait_for_element("#btn", visible=True)

    # Prefers checkVisibility (walks ancestor chain) with a computed-style
    # fallback for older Chrome.
    assert any("checkVisibility" in e for e in js_exprs)
    assert any("getComputedStyle" in e for e in js_exprs)
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



def test_wait_for_network_idle_filters_events_to_active_session():
    """Background tabs (e.g. a polling page the agent switched away from) keep
    emitting Network events into the daemon's global buffer. The wait must
    filter by session_id of the currently-attached tab — otherwise it would
    see the background tab's traffic and either fail to return idle or wait
    on the wrong tab's requests."""
    active = "session-ACTIVE"
    background = "session-BACKGROUND"

    # First /drain_events/ payload: rWS + lF on the BACKGROUND session that we
    # must ignore, plus zero events on the active session. With filtering, the
    # active session sees no traffic and the idle window can elapse.
    events_seq = [
        [
            {"session_id": background, "method": "Network.requestWillBeSent", "params": {"requestId": "bg1"}},
            {"session_id": background, "method": "Network.loadingFinished",   "params": {"requestId": "bg1"}},
        ],
        [],  # second drain — quiet on both sessions; idle window should fire here
    ]
    drain_idx = 0

    def fake_send(req):
        nonlocal drain_idx
        if req.get("meta") == "session":
            return {"session_id": active}
        if req.get("meta") == "drain_events":
            evs = events_seq[min(drain_idx, len(events_seq) - 1)]
            drain_idx += 1
            return {"events": evs}
        return {}

    with patch("browser_harness.helpers._send", side_effect=fake_send), \
         patch("browser_harness.helpers.time") as mock_time:
        start = 1000.0
        # No inflight on active session → idle check uses time.time().
        mock_time.time.side_effect = [start, start, start, start + 0.6, start + 0.6]
        mock_time.sleep = lambda _: None
        result = helpers.wait_for_network_idle(timeout=5.0, idle_ms=500)

    assert result is True, (
        "wait_for_network_idle must return True even when the BACKGROUND "
        "session is busy, as long as the ACTIVE session is idle. Without the "
        "session filter, the background rWS/lF pair would have updated "
        "last_activity and prevented the idle window from elapsing."
    )


# --- press_key: shortcut and key-metadata behavior ---

def _capture_press_key(key, modifiers=0):
    """Run press_key with a fake cdp that records every dispatchKeyEvent."""
    events = []

    def fake_cdp(method, **kwargs):
        if method == "Input.dispatchKeyEvent":
            events.append(kwargs)
        return {}

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        helpers.press_key(key, modifiers=modifiers)
    return events


def test_press_key_letter_uses_canonical_code_and_vk():
    """Letters must resolve to CDP physical-key codes (KeyA) and the
    upper-case ASCII codepoint as vk (65). Without that, Chrome's shortcut
    handlers don't recognise the press as the same physical key a real
    keyboard would emit."""
    events = _capture_press_key("a")
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert keydown["code"] == "KeyA"
    assert keydown["windowsVirtualKeyCode"] == 65
    assert keydown["nativeVirtualKeyCode"] == 65
    # Uppercase letter still maps to KeyA / 65 — vk is case-insensitive.
    events = _capture_press_key("Z")
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert keydown["code"] == "KeyZ"
    assert keydown["windowsVirtualKeyCode"] == 90


def test_press_key_digit_uses_canonical_code_and_vk():
    events = _capture_press_key("5")
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert keydown["code"] == "Digit5"
    assert keydown["windowsVirtualKeyCode"] == ord("5")  # 53


def test_press_key_special_key_uses_kkeys_table():
    """Pre-existing behavior preserved: special keys carry their virtual
    key codes from _KEYS so listeners checking e.keyCode/e.key still fire."""
    events = _capture_press_key("Enter")
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert keydown["code"] == "Enter"
    assert keydown["windowsVirtualKeyCode"] == 13
    assert keydown.get("text") == "\r"  # Enter inserts a CR


def test_press_key_no_modifiers_emits_text_and_char_event():
    """For ordinary text input, keyDown carries `text` and a `char` event
    fires — Chrome inserts the printable character into the focused input."""
    events = _capture_press_key("a")
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert keydown.get("text") == "a"
    chars = [e for e in events if e["type"] == "char"]
    assert len(chars) == 1
    assert chars[0].get("text") == "a"


def test_press_key_with_ctrl_suppresses_text_and_char():
    """Holding Ctrl makes the press a shortcut, not text input. The keyDown
    must omit `text` and no `char` event must fire — otherwise Chrome
    inserts the printable letter alongside firing the shortcut handler."""
    events = _capture_press_key("a", modifiers=2)  # Ctrl
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert "text" not in keydown, (
        f"keyDown must NOT carry text when Ctrl is held — Chrome would "
        f"insert the letter. Got: {keydown}"
    )
    assert keydown["modifiers"] == 2
    chars = [e for e in events if e["type"] == "char"]
    assert chars == [], f"expected zero char events with Ctrl held, got: {chars}"


def test_press_key_with_meta_suppresses_text_and_char():
    """Same as Ctrl, but for Cmd on macOS (modifier 4 = Meta)."""
    events = _capture_press_key("s", modifiers=4)  # Cmd
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert "text" not in keydown
    assert keydown["modifiers"] == 4
    assert keydown["code"] == "KeyS"
    assert keydown["windowsVirtualKeyCode"] == ord("S")
    assert not any(e["type"] == "char" for e in events)


def test_press_key_with_alt_suppresses_text_and_char():
    """Alt-shortcuts also should not insert text (e.g. browser/menu shortcuts
    on Linux/Windows)."""
    events = _capture_press_key("f", modifiers=1)  # Alt
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert "text" not in keydown
    assert not any(e["type"] == "char" for e in events)


def test_press_key_shift_alone_still_emits_text_and_char():
    """Shift alone is text input (Shift+A still types whatever the caller
    asked for). Only Alt/Ctrl/Meta turn the press into a shortcut."""
    events = _capture_press_key("A", modifiers=8)  # Shift
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert keydown.get("text") == "A"
    assert keydown["modifiers"] == 8
    chars = [e for e in events if e["type"] == "char"]
    assert len(chars) == 1
    assert chars[0].get("text") == "A"


def test_press_key_ctrl_shift_combo_still_suppresses():
    """Multi-modifier shortcuts (e.g. Ctrl+Shift+P for command palette) must
    also suppress text/char — Ctrl wins over Shift's text-input semantics."""
    events = _capture_press_key("p", modifiers=2 | 8)  # Ctrl+Shift
    keydown = next(e for e in events if e["type"] == "keyDown")
    assert "text" not in keydown
    assert keydown["modifiers"] == 10
    assert not any(e["type"] == "char" for e in events)


def test_press_key_emits_keyup_with_consistent_metadata():
    """Every press emits a matching keyUp regardless of modifiers."""
    events = _capture_press_key("a", modifiers=2)
    keyup = next(e for e in events if e["type"] == "keyUp")
    assert keyup["code"] == "KeyA"
    assert keyup["windowsVirtualKeyCode"] == 65
    assert keyup["modifiers"] == 2
