"""BH_HUMAN_MOUSE=1: click_at_xy travels like a hand (daemon meta=mouse) and draws the arrow; off, it is main's click."""
import asyncio
import math
import random
import threading
import time
from unittest.mock import patch

import pytest

from browser_harness import daemon, helpers, pointer

VIEW = (0.0, 0.0, 1280.0, 720.0)
QUAD = [1, 2, 3, 4, 5, 6, 7, 8]


class _Tab:
    """A fake browser with one tab T1: answers every call after `rtt` s, like a cloud browser; records each."""

    def __init__(self, rtt=0.0):
        self.rtt, self.sent, self.stale = rtt, [], set()

    async def send_raw(self, method, params=None, session_id=None):
        self.sent.append((time.monotonic(), method, dict(params or {}), session_id))
        await asyncio.sleep(self.rtt)
        if session_id in self.stale:
            raise RuntimeError("{'code': -32001, 'message': 'Session with given id not found'}")
        if method == "Target.attachToTarget":
            return {"sessionId": f"S{sum(m == method for _, m, _, _ in self.sent)}"}
        if method == "Runtime.evaluate" and params.get("expression") == daemon.VIEWPORT_JS:
            return {"result": {"value": [1280, 720, 2]}}
        return {}

    def methods(self, prefix=""):
        return [m for _, m, _, _ in self.sent if m.startswith(prefix)]

    def mouse(self):
        return [p for _, m, p, _ in self.sent if m == "Input.dispatchMouseEvent"]


@pytest.fixture
def tab(monkeypatch):
    """A daemon with the default owner on tab T1, on its own loop thread; helpers._send goes to it as over IPC."""
    monkeypatch.setenv("BH_TAB_MARKER", "0")
    monkeypatch.delenv("BH_HUMAN_MOUSE", raising=False)
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    d = daemon.Daemon()
    d.cdp = _Tab()
    d.owner("default")
    d._own("default", "T1")
    d.requests = []

    def send(req, response_timeout=5.0):
        d.requests.append(req)
        r = asyncio.run_coroutine_threadsafe(d.handle(req), loop).result(response_timeout)
        if "error" in r:
            raise RuntimeError(r["error"])
        return r

    monkeypatch.setattr(helpers, "_send", send)
    yield d
    loop.call_soon_threadsafe(loop.stop)


# --- flag off: main's click, untouched ---

@pytest.mark.parametrize("value", [None, "0", "off", ""])
def test_flag_off_click_is_mains_press_and_release_only(tab, monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("BH_HUMAN_MOUSE", value)
    helpers.click_at_xy(100, 50)
    assert tab.cdp.mouse() == [
        {"type": "mousePressed", "x": 100, "y": 50, "button": "left", "clickCount": 1},
        {"type": "mouseReleased", "x": 100, "y": 50, "button": "left", "clickCount": 1},
    ]
    assert not tab.cdp.methods("Overlay.") and not any(r.get("meta") == "mouse" for r in tab.requests)
    assert tab.drawn == {}


def test_flag_off_fill_input_focuses_with_js_and_never_clicks(monkeypatch):
    monkeypatch.delenv("BH_HUMAN_MOUSE", raising=False)
    calls, exprs = [], []
    with patch("browser_harness.helpers.cdp", side_effect=lambda m, **k: calls.append((m, k)) or {}), \
         patch("browser_harness.helpers.js", side_effect=lambda e, **k: exprs.append(e) or True):
        helpers.fill_input("#inp", "x", clear_first=False)
    assert exprs[0] == '(()=>{const e=document.querySelector("#inp");if(!e)return false;e.focus();return true;})()'
    assert "Input.dispatchMouseEvent" not in [m for m, _ in calls]


def test_screenshots_without_a_drawn_arrow_are_one_plain_call(tab):
    helpers.cdp("Page.captureScreenshot", format="png")
    assert [m for m in tab.cdp.methods() if m.startswith(("Page.capture", "Overlay."))] == ["Page.captureScreenshot"]


# --- flag on: human travel, pipelined in the daemon ---

def test_flag_on_click_travels_presses_on_arrival_and_draws(tab, monkeypatch):
    monkeypatch.setenv("BH_HUMAN_MOUSE", "1")
    helpers.click_at_xy(600, 400)
    ev = tab.cdp.mouse()
    moves = [e for e in ev if e["type"] == "mouseMoved"]
    assert pointer.MOVES[0] <= len(moves) <= pointer.MOVES[1]
    assert [e["type"] for e in ev[len(moves):]] == ["mousePressed", "mouseReleased"]
    assert (moves[-1]["x"], moves[-1]["y"]) == (600, 400) and all("quad" not in e and "at" not in e for e in ev)
    assert [r["meta"] for r in tab.requests] == ["mouse"]  # one IPC request per click
    assert "Overlay.enable" in tab.cdp.methods() and "Overlay.highlightQuad" in tab.cdp.methods()
    # the next click starts where this one ended
    helpers.click_at_xy(650, 420)
    nxt = [e for e in tab.cdp.mouse()[len(ev):] if e["type"] == "mouseMoved"]
    assert math.dist((nxt[0]["x"], nxt[0]["y"]), (600, 400)) < math.dist((nxt[0]["x"], nxt[0]["y"]), (650, 420))


def test_flag_on_against_a_daemon_without_meta_mouse_says_reload(monkeypatch):
    monkeypatch.setenv("BH_HUMAN_MOUSE", "1")

    def old_daemon(req, **k):
        raise RuntimeError(f"unknown request {req['meta']!r}: this daemon speaks protocol 2; update browser-harness")
    monkeypatch.setattr(helpers, "_send", old_daemon)
    with pytest.raises(RuntimeError, match="--reload"):  # never a silent plain click
        helpers.click_at_xy(1, 1)


def test_flag_on_fill_input_clicks_the_field_centre_unless_covered(monkeypatch):
    monkeypatch.setenv("BH_HUMAN_MOUSE", "1")
    for own, clicks in ((True, [(50.0, 20.0)]), (False, [])):
        clicked = []
        answers = iter([[50.0, 20.0, 400, own], True, True])
        with patch("browser_harness.helpers.cdp", return_value={}), \
             patch("browser_harness.helpers.click_at_xy", side_effect=lambda x, y: clicked.append((x, y))), \
             patch("browser_harness.helpers.js", side_effect=lambda e, **k: next(answers)):
            helpers.fill_input("#inp", "x")
        assert clicked == clicks


def test_flag_on_fill_input_raises_when_element_not_found(monkeypatch):
    monkeypatch.setenv("BH_HUMAN_MOUSE", "1")
    with patch("browser_harness.helpers.js", return_value=None), pytest.raises(RuntimeError, match="element not found"):
        helpers.fill_input("#missing", "x")


def test_mouse_sends_the_path_on_schedule_without_waiting_for_each_answer(monkeypatch):
    monkeypatch.setattr(pointer, "path", lambda *a, **k: (
        [{"at": 0.02 * i, "type": "mouseMoved", "x": 10 * i, "y": 5 * i} for i in range(1, 11)]
        + [{"at": 0.25, "type": "mousePressed", "x": 100, "y": 50, "button": "left", "clickCount": 1},
           {"at": 0.3, "type": "mouseReleased", "x": 100, "y": 50, "button": "left", "clickCount": 1}]))
    d = daemon.Daemon()
    d.cdp, d.viewport["s1"] = _Tab(rtt=0.2), [1280, 720, 1]

    async def run():
        t0 = time.monotonic()
        return await d.mouse("s1", (100, 50)), time.monotonic() - t0
    r, wall = asyncio.run(run())
    assert r == {"sent": 12, "late": 0}
    assert 0.5 <= wall < 0.9  # 12 round trips would be 2.4 s: pipelined, the schedule plus one round trip
    sent = [s for s in d.cdp.sent if s[1] == "Input.dispatchMouseEvent"]
    assert sent[-2][0] - sent[0][0] >= 0.22  # held to its time, not sent early
    assert d.pointer == {"s1": (100, 50)}


def test_mouse_returns_after_the_ack_limit_when_chrome_does_not_answer(monkeypatch):
    monkeypatch.setattr(daemon, "MOUSE_ACK_S", 0.1)
    d = daemon.Daemon()
    d.cdp, d.viewport["s1"], d.pointer["s1"] = _Tab(rtt=5), [800, 600, 1], (1, 1)  # a hidden tab answers after ~5 s
    t0 = time.monotonic()
    r = asyncio.run(d.mouse("s1", (300, 300)))
    assert r["late"] == r["sent"] > 0 and time.monotonic() - t0 < 1.5


def test_a_stale_session_fails_fast_and_meta_mouse_reattaches_the_same_tab_once(tab, monkeypatch):
    monkeypatch.setenv("BH_HUMAN_MOUSE", "1")
    helpers.cdp("Runtime.evaluate", expression="1")  # attaches T1 as S1
    tab.cdp.stale.add("S1")
    helpers.click_at_xy(300, 200)
    by_session = {}
    for _, m, p, s in tab.cdp.sent:
        if m == "Input.dispatchMouseEvent":
            by_session.setdefault(s, []).append(p["type"])
    assert len(by_session["S1"]) <= 3  # stopped once an answer said stale
    assert by_session["S2"][-2:] == ["mousePressed", "mouseReleased"]


def test_the_press_pulse_draws_after_the_click_returns(monkeypatch):
    monkeypatch.setattr(pointer, "path", lambda *a, **k: (
        [{"at": 0.01 * i, "type": "mouseMoved", "x": i, "y": i, "quad": QUAD} for i in range(1, 4)]
        + [{"at": 0.05, "type": "mousePressed", "x": 3, "y": 3, "button": "left", "clickCount": 1},
           {"at": 0.08, "type": "mouseReleased", "x": 3, "y": 3, "button": "left", "clickCount": 1}]
        + [{"at": 0.05 + k / 10, "quad": QUAD} for k in range(1, 4)]))
    d = daemon.Daemon()
    d.cdp, d.viewport["s1"] = _Tab(rtt=0.05), [1280, 720, 1]

    async def run():
        t0 = time.monotonic()
        r = await d.mouse("s1", (3, 3))
        wall, before = time.monotonic() - t0, d.cdp.methods()
        await asyncio.sleep(0.4)
        return r, wall, before, d.cdp.methods()
    r, wall, before, after = asyncio.run(run())
    assert r == {"sent": 5, "late": 0} and wall < 0.25
    assert before.count("Overlay.enable") == 1 and before.index("Overlay.enable") < before.index("Overlay.highlightQuad")
    assert after.count("Overlay.highlightQuad") == 6  # 3 moves, then 3 pulse frames after returning
    assert d.drawn == {"s1": QUAD}


def test_screenshots_leave_the_drawn_arrow_out_and_draw_it_again(tab, monkeypatch):
    monkeypatch.setenv("BH_HUMAN_MOUSE", "1")
    helpers.click_at_xy(300, 200)
    time.sleep(0.4)  # the press pulse is done
    n = len(tab.cdp.sent)
    helpers.cdp("Page.captureScreenshot", format="png")
    time.sleep(0.05)
    assert [m for _, m, _, _ in tab.cdp.sent[n:]] == ["Overlay.hideHighlight", "Page.captureScreenshot", "Overlay.highlightQuad"]


def test_a_detached_session_forgets_its_pointer_and_gets_no_more_drawing(tab, monkeypatch):
    monkeypatch.setenv("BH_HUMAN_MOUSE", "1")
    helpers.click_at_xy(300, 200)  # its press pulse still draws for ~0.3 s
    sid = tab.owners["default"].tabs["T1"]
    tab._record_event("Target.detachedFromTarget", {"sessionId": sid, "targetId": "T1"})
    n = len(tab.cdp.sent)
    time.sleep(0.4)
    assert tab.cdp.sent[n:] == [] and not (tab.pointer or tab.viewport or tab.drawn or tab._overlay_on)


def test_the_drawn_arrow_hides_when_idle(monkeypatch):
    monkeypatch.setattr(pointer, "IDLE", 0.05)
    d = daemon.Daemon()
    d.cdp = _Tab(rtt=0.01)

    async def run():
        d.draw("s1", QUAD)
        await asyncio.sleep(0.15)
    asyncio.run(run())
    assert d.cdp.methods() == ["Overlay.enable", "Overlay.highlightQuad", "Overlay.hideHighlight"] and d.drawn == {}


# --- pointer.path: the events of one click ---

def test_path_moves_from_the_pointer_presses_on_arrival_then_pulses():
    ev = pointer.path((100, 600), (1100, 100), [1280, 720, 2], press=("left", 1), rng=random.Random(5))
    inputs = [e for e in ev if "type" in e]
    assert [e["type"] for e in inputs[-2:]] == ["mousePressed", "mouseReleased"]
    assert all((e["x"], e["y"]) == (1100, 100) for e in inputs[-3:])
    assert [e["at"] for e in ev] == sorted(e["at"] for e in ev)
    assert len([e for e in ev if "type" not in e]) == len(pointer.PRESS) - 1  # the pulse frames
    assert ev[0]["quad"] == pointer.arrow(ev[0]["x"], ev[0]["y"], pointer.samples(
        (100, 600), (1100, 100), (0.0, 0.0, 1280.0, 720.0), random.Random(5))[0][3], dpr=2)


def test_path_with_an_unknown_pointer_starts_near_the_target():
    ev = pointer.path(None, (400, 300), None, rng=random.Random(1))
    assert ev and math.dist((ev[0]["x"], ev[0]["y"]), (400, 300)) < 200 and "mousePressed" not in [e.get("type") for e in ev]
