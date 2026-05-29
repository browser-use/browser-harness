"""Hermetic unit tests for the human-behavior-simulation layer.

No browser, no daemon, no installed browser_harness: a fake browser_harness.helpers
is injected into sys.modules before agent_helpers.py is loaded, so every CDP call is
captured in-memory. Pure-math functions are tested statistically; the dispatch
functions are tested for the structural/integer/ordering invariants that the
behavioral model depends on.

Run:  python3 tests/unit/test_human_behavior.py
  or: pytest tests/unit/test_human_behavior.py
"""

import importlib.util
import math
import os
import statistics
import sys
import tempfile
import types

# --- inject a fake browser_harness.helpers BEFORE loading the module ----------

EVENTS = []          # captured CDP calls: list of (method, kwargs)
SLEEPS = []          # captured sleep durations
BATCHES = []         # captured dispatch_input_sequence event lists


def _fake_cdp(method, **kw):
    EVENTS.append((method, kw))
    if method == "Page.getLayoutMetrics":
        return {"layoutViewport": {"clientWidth": 1200, "clientHeight": 800}}
    return {}


def _fake_dispatch_seq(events, session_id=None):
    # Record the batch AND expand it into EVENTS, mirroring what the daemon does
    # server-side, so the existing per-event assertions keep working.
    BATCHES.append(events)
    for ev in events:
        EVENTS.append((ev["method"], ev.get("params") or {}))
    return {"ok": True, "count": len(events)}


_FAKE_KEYS = {
    "Enter": (13, "Enter", "\r"),
    "Tab": (9, "Tab", "\t"),
    "Backspace": (8, "Backspace", ""),
    " ": (32, "Space", " "),
}


def _install_fake_helpers():
    pkg = types.ModuleType("browser_harness")
    helpers = types.ModuleType("browser_harness.helpers")
    helpers.cdp = _fake_cdp
    helpers.dispatch_input_sequence = _fake_dispatch_seq
    helpers._KEYS = _FAKE_KEYS
    helpers.new_tab = lambda url: EVENTS.append(("new_tab", {"url": url}))
    helpers.goto_url = lambda url: EVENTS.append(("goto_url", {"url": url}))
    helpers.wait_for_load = lambda: EVENTS.append(("wait_for_load", {}))
    pkg.helpers = helpers
    sys.modules["browser_harness"] = pkg
    sys.modules["browser_harness.helpers"] = helpers


def _load_module():
    _install_fake_helpers()
    path = os.path.join(os.path.dirname(__file__), "..", "..", "agent-workspace", "agent_helpers.py")
    spec = importlib.util.spec_from_file_location("ah_under_test", os.path.abspath(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


os.environ["BH_TMP_DIR"] = tempfile.mkdtemp(prefix="bh_human_test_")
os.environ["BU_NAME"] = "unittest"
ah = _load_module()

# make sleeps instant but observable
import time as _time
_REAL_SLEEP = _time.sleep
_time.sleep = lambda d=0: SLEEPS.append(d)


def _reset():
    EVENTS.clear()
    SLEEPS.clear()
    BATCHES.clear()
    ah.human_session("paced", fresh=True)


def _mouse_events():
    return [(m, k) for (m, k) in EVENTS if m == "Input.dispatchMouseEvent"]


def _key_events():
    return [(m, k) for (m, k) in EVENTS if m == "Input.dispatchKeyEvent"]


# --- pure math ---------------------------------------------------------------

def test_vk_for_char_letters_digits_specials():
    assert ah._vk_for_char("a") == (65, "KeyA", "a")
    assert ah._vk_for_char("A") == (65, "KeyA", "A")
    assert ah._vk_for_char("z") == (90, "KeyZ", "z")
    assert ah._vk_for_char("5") == (53, "Digit5", "5")
    assert ah._vk_for_char("Enter") == (13, "Enter", "\r")
    # the bug being fixed: lowercase must NOT map to ord('a')=97 (VK_NUMPAD1)
    vk, _, _ = ah._vk_for_char("a")
    assert vk == 65 and not (97 <= vk <= 122)


def test_lognormal_recovers_mean_std():
    for mean, std in [(120, 34), (85, 24), (1.0, 0.3), (50, 80)]:  # incl std>mean
        xs = [ah._lognormal(mean, std, max_sigma=12) for _ in range(60000)]
        m = statistics.mean(xs)
        sd = statistics.pstdev(xs)
        assert abs(m - mean) / mean < 0.04, (mean, std, m)
        assert abs(sd - std) / std < 0.08, (mean, std, sd)


def test_ou_stationary_std_and_autocorr():
    dt = 0.035
    chain = ah._ou_axis(40000, dt, 1.0)
    sd = statistics.pstdev(chain)
    assert 0.95 <= sd <= 1.05, sd          # stationary std == requested (exact discretization)
    # lag-1 autocorrelation == exp(-dt/tau)
    expected = math.exp(-dt / ah._TREMOR_TAU)
    m = statistics.mean(chain)
    num = sum((chain[i] - m) * (chain[i + 1] - m) for i in range(len(chain) - 1))
    den = sum((c - m) ** 2 for c in chain)
    ac = num / den
    assert abs(ac - expected) < 0.03, (ac, expected)


def test_tremor_rms_in_human_band():
    dt = 0.035
    nx, ny = ah._tremor(40000, dt, 0.6)
    per_axis_rms = math.sqrt((sum(v * v for v in nx) + sum(v * v for v in ny)) / (2 * len(nx)))
    assert 0.3 <= per_axis_rms <= 1.2, per_axis_rms   # cited human hand-tremor band


def test_ballistic_easing_monotonic_and_early_peak():
    n = 100
    e = ah._ballistic_easing(n)
    assert e[0] == 0.0 or e[0] < 1e-9
    assert abs(e[-1] - 1.0) < 1e-9
    assert all(e[i + 1] >= e[i] - 1e-12 for i in range(n - 1)), "must be monotonic"
    vel = [e[i + 1] - e[i] for i in range(n - 1)]
    peak = vel.index(max(vel))
    assert peak < n * 0.5, peak            # velocity peaks in first half (asymmetric, not smoothstep)


def test_fitts_sublinear_and_increasing():
    short = ah._fitts_ms(50)
    long = ah._fitts_ms(1600)
    assert long > short
    # log law: a 32x distance increase must NOT produce a 32x time increase
    assert (long / short) < (1600 / 50)


def test_bezier_endpoint_exact_and_finite():
    pts = ah._bezier_trajectory((10.0, 10.0), (640.0, 480.0), n=40, dt=0.035, angle=0.5)
    assert len(pts) == 40
    assert pts[-1] == (640.0, 480.0)       # invariant: last point is the exact target
    assert all(math.isfinite(x) and math.isfinite(y) for x, y in pts)


# --- dispatch invariants -----------------------------------------------------

def _all_mouse_coords_int():
    for _, k in _mouse_events():
        assert isinstance(k["x"], int) and isinstance(k["y"], int), k
        if "deltaY" in k:
            assert isinstance(k["deltaY"], int), k


def test_human_move_integer_coords_and_cursor_update():
    _reset()
    ah.human_move(900, 600)
    _all_mouse_coords_int()
    moved = [k for m, k in _mouse_events() if k.get("type") == "mouseMoved"]
    assert len(moved) >= 8
    assert moved[-1]["x"] == 900 and moved[-1]["y"] == 600
    assert ah._s().cursor == [900.0, 600.0]


def test_human_click_teleport_invariant():
    _reset()
    ah.human_move(100, 100)
    ah.human_click(700, 400)
    me = _mouse_events()
    press_idx = next(i for i, (m, k) in enumerate(me) if k.get("type") == "mousePressed")
    # the event immediately before the press must be a mouseMoved at the SAME coords
    prev_type = me[press_idx - 1][1]["type"]
    assert prev_type == "mouseMoved"
    assert me[press_idx - 1][1]["x"] == me[press_idx][1]["x"]
    assert me[press_idx - 1][1]["y"] == me[press_idx][1]["y"]
    _all_mouse_coords_int()
    # release within 1px of press (micro-drift, stays in hit-box)
    rel = next(k for m, k in me if k.get("type") == "mouseReleased")
    prs = me[press_idx][1]
    assert abs(rel["x"] - prs["x"]) <= 1 and abs(rel["y"] - prs["y"]) <= 1


def test_human_type_semantic_correct_vk_and_hold():
    _reset()
    ah.human_type("ab5", mode="semantic")
    ke = _key_events()
    downs = [k for m, k in ke if k["type"] == "keyDown"]
    ups = [k for m, k in ke if k["type"] == "keyUp"]
    assert len(downs) == 3 and len(ups) == 3
    # no letter keyDown may carry a NUMPAD/function virtual-key code (the old bug)
    for d in downs:
        if d["key"].isalpha():
            assert d["windowsVirtualKeyCode"] not in range(97, 123), d
    a_down = downs[0]
    assert a_down["windowsVirtualKeyCode"] == 65 and a_down["code"] == "KeyA"
    # hold is structural: _dispatch_char always sleeps >= 0.01 between down and up
    assert any(s >= 0.01 for s in SLEEPS)


def test_human_type_physical_down_to_down_and_vk():
    _reset()
    ah.human_type("hi", mode="physical")
    ke = _key_events()
    seq = [(k["type"], k.get("windowsVirtualKeyCode")) for m, k in ke]
    # h: keyDown(72) char keyUp(72), i: keyDown(73) char keyUp(73)
    downs = [vk for t, vk in seq if t == "keyDown"]
    assert downs == [72, 73], downs


def test_human_scroll_cursor_anchored_and_integer_deltas():
    import random
    random.seed(3)
    # run many times: the old final-step clamp produced non-detent deltas ~39% of seeds
    for _ in range(60):
        _reset()
        ah.human_move(50, 50)
        EVENTS.clear()
        ah.human_scroll(600, 400, distance=800, device="wheel")
        me = _mouse_events()
        first_wheel = next(i for i, (m, k) in enumerate(me) if k.get("type") == "mouseWheel")
        assert any(k.get("type") == "mouseMoved" for m, k in me[:first_wheel])  # anchor move
        wheels = [k for m, k in me if k.get("type") == "mouseWheel"]
        assert len(wheels) >= 1
        for w in wheels:
            assert isinstance(w["deltaY"], int) and w["deltaY"] != 0
            assert abs(w["deltaY"]) % 100 == 0 or abs(w["deltaY"]) % 120 == 0, w  # every event a detent multiple
        assert ah._s().cursor == [600.0, 400.0]


def test_idle_drift_stays_near_anchor():
    import math as _m
    import random
    random.seed(11)
    _reset()
    ah.human_move(400, 400)
    anchor = tuple(ah._s().cursor)
    EVENTS.clear()
    ah.human_wait(10.0, drift=True)   # long wait => many drift steps
    for m, k in _mouse_events():
        if k.get("type") == "mouseMoved":
            assert _m.hypot(k["x"] - anchor[0], k["y"] - anchor[1]) <= 25, (k, anchor)


def test_click_release_stays_in_viewport_at_corner():
    _reset()
    ah.human_move(1100, 700)
    EVENTS.clear()
    ah.human_click(5000, 5000)        # clamps to bottom-right corner (1199, 799)
    for m, k in _mouse_events():
        assert 0 <= k["x"] <= 1199 and 0 <= k["y"] <= 799, k
    cx, cy = ah._s().cursor
    assert 0 <= cx <= 1199 and 0 <= cy <= 799


def test_human_wait_idle_drift_emits_moves():
    import random
    random.seed(7)
    _reset()
    ah.human_move(300, 300)
    EVENTS.clear()
    ah.human_wait(2.0, drift=True)
    moved = [k for m, k in _mouse_events() if k.get("type") == "mouseMoved"]
    assert len(moved) >= 1, "idle drift should emit at least one move over a 2s wait"
    _all_mouse_coords_int()


def test_human_navigate_invalidates_viewport_and_pauses():
    _reset()
    ah._s().viewport = (999, 999)
    ah.human_navigate("https://example.com")
    assert ah._s().viewport != (999, 999) or ah._s().viewport is None
    # prefers new_tab (does not clobber the user's active tab via goto_url)
    assert any(m == "new_tab" for m, k in EVENTS)
    assert not any(m == "goto_url" for m, k in EVENTS)


def test_no_public_config_leak():
    # only human_* verbs should be exportable (no leading-underscore tables/class)
    public = [n for n in vars(ah) if not n.startswith("_") and callable(getattr(ah, n))]
    human = [n for n in public if n.startswith("human_")]
    leaked = [n for n in public if n in ("PACING", "TYPING_PROFILES", "HumanSession")]
    assert leaked == [], leaked
    assert set(human) >= {"human_session", "human_wait", "human_move",
                          "human_click", "human_type", "human_scroll", "human_navigate"}


def test_move_dispatched_as_single_batch():
    _reset()
    ah.human_move(900, 600)
    assert len(BATCHES) == 1, "human_move should dispatch ONE server-side batch"
    evs = BATCHES[0]
    assert len(evs) >= 8
    for e in evs:
        assert e["method"] == "Input.dispatchMouseEvent"
        assert e["params"]["type"] == "mouseMoved"
        assert isinstance(e["params"]["x"], int) and isinstance(e["params"]["y"], int)
        assert isinstance(e["delay_ms"], (int, float)) and e["delay_ms"] >= 0
    assert evs[0]["delay_ms"] == 0.0                       # first event fires immediately
    assert evs[-1]["params"]["x"] == 900 and evs[-1]["params"]["y"] == 600  # exact endpoint


def test_move_event_rate_near_60hz():
    _reset()
    ah.human_move(1000, 700)
    nz = [e["delay_ms"] for e in BATCHES[0] if e["delay_ms"] > 0]
    avg = sum(nz) / len(nz)
    # paced move_step_ms=16 -> ~62Hz. Assert mean inter-event delay is 10-25ms:
    # NOT the old ~35ms (28Hz), and not absurdly fast (which would look uncoalesced).
    assert 10 <= avg <= 25, avg


def test_click_single_batch_press_release_invariant():
    _reset()
    ah.human_move(100, 100)
    BATCHES.clear(); EVENTS.clear()
    ah.human_click(700, 400)
    assert len(BATCHES) == 1, "the whole click is one batch"
    evs = BATCHES[0]
    types_ = [e["params"]["type"] for e in evs]
    assert types_.count("mousePressed") == 1 and types_.count("mouseReleased") == 1
    assert types_[-1] == "mouseReleased"
    pi = types_.index("mousePressed")
    assert types_[pi - 1] == "mouseMoved"                 # press follows a move
    assert evs[pi - 1]["params"]["x"] == evs[pi]["params"]["x"]   # at identical coords
    assert evs[pi - 1]["params"]["y"] == evs[pi]["params"]["y"]


def test_emit_falls_back_when_daemon_lacks_op():
    _reset()
    helpers = sys.modules["browser_harness.helpers"]
    orig = helpers.dispatch_input_sequence

    def _raise(events, session_id=None):
        raise RuntimeError("'method'")  # old daemon: unknown meta -> error

    helpers.dispatch_input_sequence = _raise
    try:
        EVENTS.clear(); BATCHES.clear()
        ah.human_move(800, 500)
        assert BATCHES == [], "raising batch op must not record a batch"
        moved = [k for m, k in _mouse_events() if k.get("type") == "mouseMoved"]
        assert len(moved) >= 8, "fallback must still dispatch via cdp()"
        assert moved[-1]["x"] == 800 and moved[-1]["y"] == 500
    finally:
        helpers.dispatch_input_sequence = orig


def test_emit_resumes_from_count_no_double_dispatch():
    # Daemon ran K events then failed (e.g. stale session). _emit must re-dispatch
    # ONLY events[K:] client-side, never the already-sent prefix (no double-fire).
    _reset()
    helpers = sys.modules["browser_harness.helpers"]
    orig = helpers.dispatch_input_sequence
    K = 3

    def _partial(events, session_id=None):
        BATCHES.append(events)  # the attempted batch (full list)
        return {"error": "Session with given id not found", "count": K}

    helpers.dispatch_input_sequence = _partial
    try:
        EVENTS.clear(); BATCHES.clear()
        ah.human_move(900, 600)
        n = len(BATCHES[0])
        moved = [k for m, k in _mouse_events() if k.get("type") == "mouseMoved"]
        assert len(moved) == n - K, (len(moved), n)   # remainder only, prefix NOT resent
        assert moved[-1]["x"] == 900 and moved[-1]["y"] == 600
    finally:
        helpers.dispatch_input_sequence = orig


def test_selftest_detects_exposed_tells():
    import json as _j
    _reset()
    canned = {"moves": [{"t": 0, "sx": 100, "cx": 100, "sy": 50, "cy": 50, "trusted": True, "coalesced": 1},
                        {"t": 16, "sx": 110, "cx": 110, "sy": 55, "cy": 55, "trusted": True, "coalesced": 1}],
              "clicks": [{"t": 40, "sx": 120, "cx": 120, "sy": 60, "cy": 60, "trusted": True, "coalesced": -1}]}

    def fake_eval(expr, await_promise=False):
        if "userAgent" in expr:
            return "Mozilla/5.0 (Macintosh) Chrome/120.0.0.0 Safari/537.36"
        if "JSON.stringify" in expr:
            return _j.dumps(canned)
        return True

    orig = ah._eval
    ah._eval = fake_eval
    try:
        r = ah.human_selftest(verbose=False)
        assert r["chrome_major"] == 120
        assert r["t2_screenx_exposed"] is True       # screenX==clientX (delta 0) on Chrome <142
        assert r["screen_client_max_delta_px"] == 0
        assert r["t1_coalesced_exposed"] is True      # all coalesced == 1
        assert r["is_trusted"] is True
    finally:
        ah._eval = orig


def test_selftest_detects_fixed_chrome():
    import json as _j
    _reset()
    canned = {"moves": [{"t": 0, "sx": 172, "cx": 100, "sy": 130, "cy": 50, "trusted": True, "coalesced": 3},
                        {"t": 16, "sx": 182, "cx": 110, "sy": 135, "cy": 55, "trusted": True, "coalesced": 2},
                        {"t": 33, "sx": 192, "cx": 120, "sy": 140, "cy": 60, "trusted": True, "coalesced": 2}],
              "clicks": [{"t": 50, "sx": 202, "cx": 130, "sy": 145, "cy": 65, "trusted": True, "coalesced": -1}]}

    def fake_eval(expr, await_promise=False):
        if "userAgent" in expr:
            return "Mozilla/5.0 Chrome/148.0.0.0 Safari/537.36"
        if "JSON.stringify" in expr:
            return _j.dumps(canned)
        return True

    orig = ah._eval
    ah._eval = fake_eval
    try:
        r = ah.human_selftest(verbose=False)
        assert r["chrome_major"] == 148
        assert r["t2_screenx_exposed"] is False       # window offset present
        assert r["screen_client_max_delta_px"] == 152  # |172-100| + |130-50| (manhattan x+y)
        assert r["t1_coalesced_exposed"] is False      # coalesced max 3 > 1
        assert r["delivered_rate_hz"] is not None
    finally:
        ah._eval = orig


class _FakeCGPoint:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class _FakeSize:
    def __init__(self, w, h):
        self.width = w
        self.height = h


class _FakeRect:
    def __init__(self, ox, oy, w, h):
        self.origin = _FakeCGPoint(ox, oy)
        self.size = _FakeSize(w, h)


class _FakeQuartz:
    kCGEventMouseMoved = 5
    kCGEventLeftMouseDown = 1
    kCGEventLeftMouseUp = 2
    kCGEventRightMouseDown = 3
    kCGEventRightMouseUp = 4
    kCGMouseButtonLeft = 0
    kCGMouseButtonRight = 1
    kCGHIDEventTap = 0
    kCGMouseEventClickState = 1

    def __init__(self, display=(0.0, 0.0, 3000.0, 3000.0), move_cursor=True):
        self.posted = []
        self.cursor = _FakeCGPoint(50.0, 50.0)
        self._display = display
        self._move_cursor = move_cursor

    def CGEventCreate(self, src):
        return ("create",)

    def CGEventGetLocation(self, e):
        return self.cursor

    def CGEventCreateMouseEvent(self, src, etype, pos, btn):
        return {"type": etype, "x": float(pos[0]), "y": float(pos[1]), "btn": btn, "clickState": 0}

    def CGEventSetIntegerValueField(self, e, field, val):
        if field == self.kCGMouseEventClickState:
            e["clickState"] = val

    def CGEventPost(self, tap, e):
        self.posted.append(e)
        if self._move_cursor and e["type"] == self.kCGEventMouseMoved:
            self.cursor = _FakeCGPoint(e["x"], e["y"])  # model the real cursor moving

    def CGGetActiveDisplayList(self, maxd, a, b):
        return (0, [1], 1)

    def CGDisplayBounds(self, did):
        return _FakeRect(*self._display)


def test_os_input_available_without_quartz():
    sys.modules.pop("Quartz", None)
    ok, reason = ah.os_input_available()
    # on darwin without pyobjc -> missing-dependency; on non-darwin -> macOS-only
    assert ok is False
    assert ("pyobjc" in reason) or ("macOS-only" in reason), reason


def test_os_screen_point_mapping():
    _reset()
    orig = ah._eval
    # window.screenX=10, screenY=80, top_chrome=80, side_chrome=0
    ah._eval = lambda expr, await_promise=False: "[10, 80, 80, 0]"
    try:
        sx, sy = ah._os_screen_point(ah._s(), 600, 400)
        assert sx == 610.0 and sy == 560.0, (sx, sy)  # 10+0+600, 80+80+400
    finally:
        ah._eval = orig


def test_human_click_os_posts_real_event_sequence():
    import sys as _sys
    if _sys.platform != "darwin":
        return  # OS path is macOS-only
    _reset()
    fake = _FakeQuartz()
    _sys.modules["Quartz"] = fake
    orig_eval, orig_act = ah._eval, ah._activate_chrome
    ah._eval = lambda expr, await_promise=False: "[10, 80, 80, 0]"   # window geometry
    ah._activate_chrome = lambda *a, **k: "Google Chrome"            # frontmost matches app_name
    try:
        r = ah.human_click_os(600, 400)
        assert r["screen_point"] == [610.0, 560.0]
        types_ = [e["type"] for e in fake.posted]
        assert fake.kCGEventLeftMouseDown in types_ and fake.kCGEventLeftMouseUp in types_
        di = types_.index(fake.kCGEventLeftMouseDown)
        ui = types_.index(fake.kCGEventLeftMouseUp)
        assert di < ui                                                # down before up
        assert all(t == fake.kCGEventMouseMoved for t in types_[:di])  # moves precede press
        down, up = fake.posted[di], fake.posted[ui]
        assert down["x"] == 610.0 and down["y"] == 560.0              # press at mapped screen point
        assert down["clickState"] == 1 and up["clickState"] == 1      # D1 fix: single-click state set
        last_move = fake.posted[di - 1]
        assert last_move["x"] == 610.0 and last_move["y"] == 560.0    # final move == press (no teleport)
    finally:
        ah._eval, ah._activate_chrome = orig_eval, orig_act
        _sys.modules.pop("Quartz", None)


def test_human_click_os_refuses_offscreen_point():
    import sys as _sys
    if _sys.platform != "darwin":
        return
    _reset()
    fake = _FakeQuartz(display=(0.0, 0.0, 100.0, 100.0))  # tiny display; (610,560) is outside
    _sys.modules["Quartz"] = fake
    orig_eval, orig_act = ah._eval, ah._activate_chrome
    ah._eval = lambda expr, await_promise=False: "[10, 80, 80, 0]"
    ah._activate_chrome = lambda *a, **k: "Google Chrome"
    try:
        raised = False
        try:
            ah.human_click_os(600, 400)
        except RuntimeError as e:
            raised = "outside all displays" in str(e)
        assert raised, "must refuse to click off all displays"
        assert fake.posted == [], "no events may be posted when the target is off-screen"
    finally:
        ah._eval, ah._activate_chrome = orig_eval, orig_act
        _sys.modules.pop("Quartz", None)


def test_os_goto_raises_when_cursor_does_not_move():
    import sys as _sys
    if _sys.platform != "darwin":
        return
    _reset()
    fake = _FakeQuartz(move_cursor=False)  # model Accessibility-denied: posts no-op, cursor stuck
    _sys.modules["Quartz"] = fake
    orig_eval, orig_act = ah._eval, ah._activate_chrome
    ah._eval = lambda expr, await_promise=False: "[10, 80, 80, 0]"
    ah._activate_chrome = lambda *a, **k: "Google Chrome"
    try:
        raised = False
        try:
            ah.human_click_os(600, 400)
        except RuntimeError as e:
            raised = "did not reach target" in str(e)
        assert raised, "must raise when the cursor never reaches the target (Accessibility denied)"
    finally:
        ah._eval, ah._activate_chrome = orig_eval, orig_act
        _sys.modules.pop("Quartz", None)


def test_os_calibrate_error_computation():
    _reset()
    orig = ah._eval

    import json as _j

    def fake_eval(expr, await_promise=False):
        if "outerHeight" in expr:
            return "[10, 80, 80, 0]"            # geometry -> pred (610, 560) for client (600,400)
        if "__bh_probe" in expr and "JSON.stringify" in expr:   # _READ_JS
            return _j.dumps({"moves": [{"sx": 610, "sy": 560, "cx": 600, "cy": 400,
                                        "coalesced": 1, "trusted": True}], "clicks": []})
        return True                             # probe install / cleanup

    ah._eval = fake_eval
    try:
        r = ah.os_calibrate()
        assert r["ok"] is True
        assert r["predicted_screen"] == [610.0, 560.0]
        assert r["browser_screen"] == [610, 560]
        assert r["error_px"] == [0.0, 0.0]
    finally:
        ah._eval = orig


def _run_all():
    fns = [g for n, g in sorted(globals().items()) if n.startswith("test_") and callable(g)]
    passed = 0
    for fn in fns:
        fn()
        print("PASS %s" % fn.__name__)
        passed += 1
    print("\n%d/%d tests passed" % (passed, len(fns)))


if __name__ == "__main__":
    _run_all()
