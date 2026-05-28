"""Human behavior simulation for browser-harness.

Adds human-like timing, mouse trajectories, typing, and scrolling
on top of CDP primitives for UI automation reliability.

Usage:
    human_session("paced")                 # configure session (optional; default "paced")
    human_navigate("https://example.com")  # nav + load wait + human reading pause
    human_move(500, 300)                    # Fitts-timed ballistic trajectory + tremor
    human_click(500, 300, width=64)         # move + click; pass target width for Fitts
    human_type("hello", mode="semantic")    # per-char correct keycodes + key-hold dwell
    human_scroll(600, 400, 2000, device="trackpad")
    human_wait(2.0)                         # log-normal wait with live idle drift

Session state (cursor, click bias, tremor orientation) persists across separate
`browser-harness -c '...'` invocations via a per-BU_NAME state file, so the cursor
does not teleport to a fresh random point on every call.

KNOWN CEILINGS — NOT fixable inside this layer; documented honestly:
  * Event rate is floored ~20-40Hz by the per-call CDP/IPC round-trip and time.sleep
    granularity. Real pointing devices report at 60-1000Hz. A detector that bins
    inter-event intervals can flag the low rate regardless of trajectory shape.
  * Input.dispatchMouseEvent emits MouseEvents only: getCoalescedEvents().length == 1
    and there is no PointerEvent pressure/tilt stream. Pointer-fidelity detectors see
    synthetic input even with a perfect trajectory.
  * A CDP/remote-debugging attachment is itself detectable (anti-debugger probes,
    Runtime/Page domain side-effects) independent of behavior.
This layer targets heuristic and weak-ML detectors; against top-tier ensembles it
lowers per-action risk and buys time, it does not make a session indistinguishable.
"""

import json, math, os, random, tempfile, time

from browser_harness.helpers import cdp, _KEYS as _CORE_KEYS


# ---------------------------------------------------------------------------
# Pacing profiles — policy-based, not adaptive.
# move_step_ms  : per-event interval (>= IPC floor); also sets the event rate.
# move_time_mult: scales the Fitts'-Law movement-time estimate.
# ---------------------------------------------------------------------------

_PACING = {
    "fast": {
        "move_step_ms": 25,
        "move_time_mult": 0.7,
        "hover_range": (0.02, 0.05),
        "dwell_mean": 45,
        "type_speed": 1.5,
        "scroll_speed": 1.5,
        "wait_mult": 0.5,
        "event_jitter_ms": 1.5,
    },
    "paced": {
        "move_step_ms": 35,
        "move_time_mult": 1.0,
        "hover_range": (0.08, 0.20),
        "dwell_mean": 85,
        "type_speed": 1.0,
        "scroll_speed": 1.0,
        "wait_mult": 1.0,
        "event_jitter_ms": 3.0,
    },
    "physical": {
        "move_step_ms": 50,
        "move_time_mult": 1.3,
        "hover_range": (0.10, 0.25),
        "dwell_mean": 95,
        "type_speed": 0.8,
        "scroll_speed": 0.8,
        "wait_mult": 1.3,
        "event_jitter_ms": 4.0,
    },
}

# Typing profiles — CMU Keystroke Dataset (Killourhy & Maxion, DSN 2009).
# dd = down-down interval, hold = key hold duration (ms). WPM at 5 chars/word:
# hunt_peck ~36, average ~72, skilled ~100, expert ~140.
_TYPING_PROFILES = {
    "hunt_peck": {"dd_mean": 335, "dd_std": 182, "hold_mean": 95, "hold_std": 30},
    "average":   {"dd_mean": 166, "dd_std": 62,  "hold_mean": 79, "hold_std": 22},
    "skilled":   {"dd_mean": 120, "dd_std": 34,  "hold_mean": 75, "hold_std": 18},
    "expert":    {"dd_mean": 86,  "dd_std": 18,  "hold_mean": 65, "hold_std": 12},
}

_IPC_FLOOR_MS = 20

# Hand tremor model. Two anisotropic OU axes (2:1) rotated by a session-fixed angle.
# Combined isotropic-equivalent RMS = sqrt((1.0^2 + 0.5^2)/2) ~= 0.79px, inside the
# 0.3-1.2px human hand-tremor band (vs the prior 2.19px which exceeded it).
_TREMOR_STD_MAJOR = 1.0
_TREMOR_STD_MINOR = 0.5
_TREMOR_TAU = 0.12          # OU correlation time (s); autocorr per step = exp(-dt/tau)

# Fitts' Law: MT = a + b * log2(D/W + 1)  (Shannon form). Mouse-typical constants.
_FITTS_A_MS = 80.0
_FITTS_B_MS = 120.0
_FITTS_DEFAULT_W = 80.0     # assumed target width (px) when caller gives none

_SESSION_TTL = 600          # ignore persisted session state older than this (s)


# ---------------------------------------------------------------------------
# Session (state persists across -c invocations via a per-BU_NAME file)
# ---------------------------------------------------------------------------

def _state_path():
    base = os.environ.get("BH_TMP_DIR") or os.environ.get("BH_RUNTIME_DIR") or tempfile.gettempdir()
    name = os.environ.get("BU_NAME", "default")
    return os.path.join(base, "bh_human_session_%s.json" % name)


class _HumanSession:
    """Tracks cursor, per-session click bias, and tremor orientation.

    cursor is None until first action — avoids the [0, 0] teleport signature.
    click_bias is session-level (not per-click) so the statistical mean of click
    error does not converge to the target center over many clicks.
    State is restored from disk (unless fresh=True) so continuity survives the
    fresh Python process that each `browser-harness -c` spawns.
    """

    def __init__(self, pacing="paced", fresh=False):
        self.pacing = pacing
        self.profile = _PACING[pacing]
        self.viewport = None
        self.cursor = None
        self.click_bias = (random.gauss(0, 1.0), random.gauss(0, 1.0))
        self.tremor_angle = random.uniform(0, math.pi)
        if not fresh:
            self._load()

    def set_pacing(self, pacing):
        self.pacing = pacing
        self.profile = _PACING[pacing]

    def invalidate_viewport(self):
        self.viewport = None

    def _load(self):
        try:
            p = _state_path()
            with open(p) as f:
                d = json.load(f)
            if time.time() - float(d.get("ts", 0)) > _SESSION_TTL:
                return
            cur = d.get("cursor")
            if cur and len(cur) == 2:
                self.cursor = [float(cur[0]), float(cur[1])]
            cb = d.get("click_bias")
            if cb and len(cb) == 2:
                self.click_bias = (float(cb[0]), float(cb[1]))
            if "tremor_angle" in d:
                self.tremor_angle = float(d["tremor_angle"])
        except Exception:
            pass

    def _save(self):
        # Atomic write (tmp + os.replace) so a concurrent reader never sees a
        # half-written file; a corrupt/partial read in _load just falls back to
        # a fresh session.
        try:
            p = _state_path()
            tmp = "%s.%d.tmp" % (p, os.getpid())
            with open(tmp, "w") as f:
                json.dump({
                    "cursor": self.cursor,
                    "click_bias": list(self.click_bias),
                    "tremor_angle": self.tremor_angle,
                    "ts": time.time(),
                }, f)
            os.replace(tmp, p)
        except Exception:
            pass


_session = None


def _s():
    global _session
    if _session is None:
        _session = _HumanSession()
    return _session


def _viewport(s):
    if s.viewport is None:
        try:
            m = cdp("Page.getLayoutMetrics")
            vp = m.get("layoutViewport", {})
            s.viewport = (
                int(vp.get("clientWidth", 1200)),
                int(vp.get("clientHeight", 800)),
            )
        except (KeyError, TypeError, ValueError, OSError, RuntimeError):
            s.viewport = (1200, 800)
    return s.viewport


def _ensure_cursor(s):
    """Lazy cursor init at a random plausible viewport position."""
    if s.cursor is None:
        w, h = _viewport(s)
        s.cursor = [
            random.uniform(w * 0.2, w * 0.8),
            random.uniform(h * 0.2, h * 0.8),
        ]
    return s.cursor


def _clamp(x, y, s=None):
    s = s or _s()
    w, h = _viewport(s)
    return (max(0, min(w - 1, x)), max(0, min(h - 1, y)))


# ---------------------------------------------------------------------------
# Math helpers (pure Python — no numpy required)
# ---------------------------------------------------------------------------

def _lognormal(mean, std, max_sigma=3):
    """Sample log-normal with the requested mean/std, truncated at mean + max_sigma*std.

    Truncation prevents catastrophic right-tail outliers (e.g. a 50s wait for a 1s base).
    """
    if mean <= 0:
        return max(0.001, mean)
    variance = std ** 2
    mu = math.log(mean ** 2 / math.sqrt(variance + mean ** 2))
    sigma = math.sqrt(math.log(1 + variance / mean ** 2))
    val = random.lognormvariate(mu, sigma)
    return min(val, mean + max_sigma * std)


def _ou_axis(n, dt, std):
    """Exact-discretization OU chain seeded from its stationary distribution.

    Uses a = exp(-dt/tau) and innovation std = std*sqrt(1-a^2), so the realized
    stationary std equals `std` exactly and lag-1 autocorrelation equals a exactly
    (no Euler-Maruyama bias). dt is the REAL per-event interval, so the temporal
    correlation matches the wall-clock signal a detector observes.
    """
    if n <= 0:
        return []
    a = math.exp(-dt / _TREMOR_TAU)
    innov = std * math.sqrt(max(0.0, 1.0 - a * a))
    vals = [random.gauss(0, std)]
    for _ in range(n - 1):
        vals.append(a * vals[-1] + innov * random.gauss(0, 1))
    return vals


def _tremor(n, dt, angle):
    """Anisotropic tremor: two OU axes (2:1) rotated into screen coords by `angle`."""
    maj = _ou_axis(n, dt, _TREMOR_STD_MAJOR)
    mnr = _ou_axis(n, dt, _TREMOR_STD_MINOR)
    ca, sa = math.cos(angle), math.sin(angle)
    nx = [maj[i] * ca - mnr[i] * sa for i in range(n)]
    ny = [maj[i] * sa + mnr[i] * ca for i in range(n)]
    return nx, ny


def _ballistic_easing(n):
    """Asymmetric ease whose velocity peaks early (~t=0.33) with a long decel tail.

    Cumulative of a Beta(2, 3)-shaped velocity profile — the Meyer/Woodworth
    two-component (ballistic + corrective) reaching model — instead of the
    symmetric smoothstep bell that constant easing produces.
    """
    if n <= 1:
        return [1.0]
    av, bv = 2.0, 3.0
    w = []
    for i in range(n):
        s = i / (n - 1)
        w.append((s ** (av - 1)) * ((1 - s) ** (bv - 1)))
    total = sum(w) or 1.0
    out, acc = [], 0.0
    for wi in w:
        acc += wi
        out.append(acc / total)
    out[-1] = 1.0
    return out


def _fitts_ms(dist, width=None):
    """Movement time via Fitts' Law (Shannon form): MT = a + b*log2(D/W + 1)."""
    w = width if (width and width > 0) else _FITTS_DEFAULT_W
    idx = math.log2(dist / w + 1.0)
    return _FITTS_A_MS + _FITTS_B_MS * idx


def _bezier_trajectory(start, end, n, dt, angle):
    """Cubic Bezier + ballistic easing + sine-enveloped anisotropic OU tremor.

    Both control points share one side (C-arc) to avoid implausible S-curves.
    The sine envelope is C^1-continuous (no triangle cusp) and zeroes tremor at
    both endpoints, so the landing point is stable. The final point is forced to
    `end` exactly, which preserves the human_click teleport-fix invariant.
    """
    sx, sy = start
    ex, ey = end
    dist = math.hypot(ex - sx, ey - sy)
    if dist < 2:
        return [(ex, ey)]

    dx, dy = ex - sx, ey - sy
    norm = dist or 1
    perp_x, perp_y = -dy / norm, dx / norm

    side = random.choice([-1, 1])
    arc1 = dist * abs(random.gauss(0.09, 0.04)) * side
    arc2 = dist * abs(random.gauss(0.09, 0.04)) * side

    cp1 = (sx + dx * 0.3 + perp_x * arc1, sy + dy * 0.3 + perp_y * arc1)
    cp2 = (sx + dx * 0.7 + perp_x * arc2, sy + dy * 0.7 + perp_y * arc2)

    ease = _ballistic_easing(n)
    nx, ny = _tremor(n, dt, angle)

    points = []
    for i in range(n):
        t = ease[i]
        mt = 1.0 - t
        px = mt**3 * sx + 3 * mt**2 * t * cp1[0] + 3 * mt * t**2 * cp2[0] + t**3 * ex
        py = mt**3 * sy + 3 * mt**2 * t * cp1[1] + 3 * mt * t**2 * cp2[1] + t**3 * ey
        env = math.sin((i / max(1, n - 1)) * math.pi)
        px += nx[i] * env
        py += ny[i] * env
        points.append((px, py))

    points[-1] = (ex, ey)
    return points


def _target_offset(x, y, s=None):
    """Click point = session-level systematic bias + small per-click variance.

    Variance is bounded (~1.5px) so small UI targets are still hit. Bias is fixed
    per session so the click-error mean does not converge to the target center.
    """
    s = s or _s()
    bias_x, bias_y = s.click_bias
    var = 1.5
    return (
        x + bias_x + random.gauss(0, var),
        y + bias_y + random.gauss(0, var * 0.7),
    )


# ---------------------------------------------------------------------------
# Key code resolution
# ---------------------------------------------------------------------------

def _vk_for_char(ch):
    """Resolve (vk, code, text) for a character with correct virtual-key codes.

    Uses _CORE_KEYS for special keys, ASCII-UPPERCASE ordinals for letters
    (so 'a' -> VK 65 'KeyA', not ord('a')=97 = VK_NUMPAD1), and ASCII digits.
    """
    if ch in _CORE_KEYS:
        return _CORE_KEYS[ch]
    if len(ch) == 1:
        upper = ch.upper()
        if "A" <= upper <= "Z":
            return (ord(upper), "Key%s" % upper, ch)
        if "0" <= ch <= "9":
            return (ord(ch), "Digit%s" % ch, ch)
    return (0, ch, ch if len(ch) == 1 else "")


# ---------------------------------------------------------------------------
# Timing / dispatch helpers
# ---------------------------------------------------------------------------

def _jittered_sleep(base_ms, sigma_ms=None):
    if sigma_ms is None:
        sigma_ms = _s().profile["event_jitter_ms"]
    delay = max(_IPC_FLOOR_MS, base_ms + random.gauss(0, sigma_ms)) / 1000.0
    time.sleep(delay)


def _dispatch_char(ch, hold_s):
    """One keystroke: keyDown [+ char] -> hold -> keyUp, with correct keycodes."""
    vk, code, t = _vk_for_char(ch)
    base = {"key": ch, "code": code, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
    cdp("Input.dispatchKeyEvent", type="keyDown", **base, **({"text": t} if t else {}))
    if t and len(t) == 1:
        cdp("Input.dispatchKeyEvent", type="char", text=t,
            **{k: v for k, v in base.items() if k != "text"})
    time.sleep(max(0.01, hold_s))
    cdp("Input.dispatchKeyEvent", type="keyUp", **base)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def human_session(pacing="paced", fresh=False):
    """Configure session pacing.

    Modes:
        fast     — internal/admin tools (faster movement, smaller hover)
        paced    — ordinary UI automation (default)
        physical — keyboard/mouse event testing (most deliberate)

    fresh=True starts a clean session (ignores any persisted cursor/bias).
    """
    global _session
    _session = _HumanSession(pacing, fresh=fresh)
    return _session


def human_wait(base=1.0, drift=True):
    """Log-normal randomized wait. When drift=True and the cursor is known, the
    cursor wanders a few px during the wait instead of freezing — real users are
    never perfectly still while reading, and a frozen cursor between actions is a
    session-level bot tell.
    """
    s = _s()
    p = s.profile
    total = max(0.05, _lognormal(base, base * 0.3) * p["wait_mult"])

    if not drift or s.cursor is None or total < 0.4:
        time.sleep(total)
        return

    remaining = total
    ax, ay = s.cursor          # fixed anchor: drift offsets from here, not cumulatively
    while remaining > 0.05:
        chunk = min(remaining, random.uniform(0.15, 0.4))
        time.sleep(chunk)
        remaining -= chunk
        if remaining > 0.1 and random.random() < 0.5:
            nx, ny = _clamp(ax + random.gauss(0, 4.0), ay + random.gauss(0, 4.0), s)
            ix, iy = int(round(nx)), int(round(ny))
            cdp("Input.dispatchMouseEvent", type="mouseMoved", x=ix, y=iy)
            s.cursor = [float(ix), float(iy)]
    s._save()


def human_move(x, y, width=None):
    """Move cursor to (x, y) via a Fitts-timed ballistic Bezier trajectory.

    Movement time follows Fitts' Law (pass `width` = target width in px for a
    correct index of difficulty; a default is assumed otherwise). Long moves
    occasionally overshoot and correct. Coordinates are integer-quantized at
    dispatch so MouseEvent.clientX in the page is a normal integer. The session
    cursor is updated per event, so a mid-trajectory CDP failure leaves the
    cursor where the pointer actually stopped.
    """
    s = _s()
    p = s.profile
    cur = _ensure_cursor(s)

    x, y = _clamp(x, y, s)
    dist = math.hypot(x - cur[0], y - cur[1])
    if dist < 2:
        s.cursor = [float(x), float(y)]
        return

    dt = p["move_step_ms"] / 1000.0
    duration_ms = _fitts_ms(dist, width) * p["move_time_mult"]
    n = max(8, min(120, int(duration_ms / p["move_step_ms"])))

    segments = []
    if dist > 400 and random.random() < 0.15:
        over = min(dist * abs(random.gauss(0.06, 0.02)), 60.0)
        ux = cur[0] + (x - cur[0]) / dist * (dist + over)
        uy = cur[1] + (y - cur[1]) / dist * (dist + over)
        ux, uy = _clamp(ux, uy, s)
        n1 = max(6, int(n * 0.8))
        n2 = max(4, n - n1)
        segments.append(_bezier_trajectory((cur[0], cur[1]), (ux, uy), n1, dt, s.tremor_angle))
        segments.append(_bezier_trajectory((ux, uy), (x, y), n2, dt, s.tremor_angle))
    else:
        segments.append(_bezier_trajectory((cur[0], cur[1]), (x, y), n, dt, s.tremor_angle))

    for seg in segments:
        for px, py in seg:
            ix, iy = int(round(px)), int(round(py))
            cdp("Input.dispatchMouseEvent", type="mouseMoved", x=ix, y=iy)
            s.cursor = [float(ix), float(iy)]
            _jittered_sleep(p["move_step_ms"])

    s.cursor = [float(x), float(y)]
    s._save()


def human_click(x, y, button="left", width=None):
    """Move to the click target, then dispatch press/release at that point.

    Invariant: mousePressed coordinates EXACTLY equal the final mouseMoved
    coordinate — the offset (jitter) is folded into the move destination, not
    added after, so there is no teleport-on-click. A <=1px micro-drift during the
    dwell makes the release point differ slightly from the press (real fingers
    shift during a hold) while staying inside the target's hit-box.
    """
    s = _s()
    p = s.profile

    cx, cy = _target_offset(x, y, s)
    cx, cy = _clamp(cx, cy, s)

    human_move(cx, cy, width=width)

    hover_lo, hover_hi = p["hover_range"]
    time.sleep(random.uniform(hover_lo, hover_hi))

    ix, iy = int(round(cx)), int(round(cy))
    cdp("Input.dispatchMouseEvent",
        type="mousePressed", x=ix, y=iy, button=button, clickCount=1)

    dwell = _lognormal(p["dwell_mean"], p["dwell_mean"] * 0.28) / 1000.0
    time.sleep(max(0.02, dwell * 0.5))

    ddx = max(-1, min(1, int(round(random.gauss(0, 0.6)))))
    ddy = max(-1, min(1, int(round(random.gauss(0, 0.6)))))
    rx, ry = _clamp(ix + ddx, iy + ddy, s)
    rx, ry = int(round(rx)), int(round(ry))
    if (rx, ry) != (ix, iy):
        cdp("Input.dispatchMouseEvent", type="mouseMoved", x=rx, y=ry)
    time.sleep(max(0.02, dwell * 0.5))

    cdp("Input.dispatchMouseEvent",
        type="mouseReleased", x=rx, y=ry, button=button, clickCount=1)
    s.cursor = [float(rx), float(ry)]
    s._save()


def human_type(text, profile="skilled", mode="semantic"):
    """Type text with human-like inter-key timing AND key-hold dwell.

    Both modes emit correct virtual-key codes (via _vk_for_char) and a non-zero
    key hold — the default semantic mode no longer routes through the core
    press_key (which emits 0ms holds and VK_NUMPAD codes for lowercase letters).

    Modes:
        semantic  — per-key keyDown/char/keyUp with a sampled hold and a
                    log-normal inter-key gap. Sufficient for most form filling.
        physical  — down-down (DD) timing measured KeyDown-to-KeyDown per the
                    CMU dataset, with hold running concurrently with the gap.

    Profiles: hunt_peck (~36 WPM), average (~72), skilled (~100), expert (~140).
    """
    tp = _TYPING_PROFILES[profile]
    speed = _s().profile["type_speed"]
    if mode == "physical":
        _type_physical(text, tp, speed)
    else:
        _type_semantic(text, tp, speed)


def _type_semantic(text, tp, speed):
    dd_mean = tp["dd_mean"] / speed
    dd_std = tp["dd_std"] / speed
    hold_mean = tp["hold_mean"] / speed
    hold_std = tp["hold_std"] / speed
    for i, ch in enumerate(text):
        if i > 0:
            gap = _lognormal(dd_mean, dd_std)
            time.sleep(max(0.02, gap / 1000.0))
        hold = _lognormal(hold_mean, hold_std) / 1000.0
        _dispatch_char(ch, hold)


def _type_physical(text, tp, speed):
    """Physical typing: KeyDown-to-KeyDown timing per the CMU dataset.

    DD is measured from the previous keyDown to the current keyDown; hold runs
    concurrently with DD (it does not add to the inter-keystroke delay). When a
    sampled DD is shorter than the previous hold, DD is lifted to hold + 10ms so
    the realized DD distribution is not silently truncated for fast profiles.
    """
    hold_mean = tp["hold_mean"] / speed
    hold_std = tp["hold_std"] / speed
    dd_mean = tp["dd_mean"] / speed
    dd_std = tp["dd_std"] / speed

    prev_down_time = 0.0
    prev_hold = 0.0

    for i, ch in enumerate(text):
        hold = _lognormal(hold_mean, hold_std) / 1000.0
        if i > 0:
            dd = _lognormal(dd_mean, dd_std) / 1000.0
            dd = max(dd, prev_hold + 0.01)
            elapsed = time.monotonic() - prev_down_time
            time.sleep(max(0.001, dd - elapsed))

        vk, code, t = _vk_for_char(ch)
        base = {"key": ch, "code": code, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}

        down_time = time.monotonic()
        cdp("Input.dispatchKeyEvent", type="keyDown", **base,
            **({"text": t} if t else {}))
        if t and len(t) == 1:
            cdp("Input.dispatchKeyEvent", type="char", text=t,
                **{k: v for k, v in base.items() if k != "text"})

        time.sleep(max(0.01, hold))
        cdp("Input.dispatchKeyEvent", type="keyUp", **base)
        prev_down_time = down_time
        prev_hold = hold


def human_scroll(x, y, distance=3000, direction="down", device="trackpad"):
    """Scroll with human-like physics, anchored at the cursor.

    The cursor is first moved to (x, y) so the wheel events originate where the
    pointer actually is (no scroll at a never-visited point), and the session
    cursor is left at the anchor afterward.

    Device profiles:
        trackpad — small continuous deltas, high frequency (default; macOS pattern)
        wheel    — discrete detent multiples (a fixed notch x a small count),
                   matching a mechanical wheel's quantized deltaY
    """
    sign = -1 if direction == "down" else 1
    s = _s()
    speed = s.profile["scroll_speed"]

    x, y = _clamp(x, y, s)
    human_move(x, y)
    ix, iy = int(round(x)), int(round(y))

    if device == "wheel":
        notch = random.choice([100, 120])
        interval_mean = 101
        reading_prob = 0.12
    else:
        interval_mean = 40
        reading_prob = 0.04

    scrolled = 0
    while scrolled < distance:
        if device == "wheel":
            # Always a whole-notch multiple — never clamped to the remainder, so
            # every deltaY is a real detent magnitude. The last event may overscroll
            # by up to one event (<=3 notches), which is what a real wheel does.
            count = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
            delta = notch * count
        else:
            # Continuous trackpad deltas; clamp the final step to the remainder.
            delta = min(_lognormal(25, 10) / speed, distance - scrolled)
        d = int(round(sign * delta))
        if d == 0:
            break

        cdp("Input.dispatchMouseEvent", type="mouseWheel",
            x=ix, y=iy, deltaX=0, deltaY=d)
        scrolled += abs(d)

        if random.random() < reading_prob:
            time.sleep(random.uniform(0.8, 3.0))
        else:
            interval = _lognormal(interval_mean, interval_mean * 0.3) / speed / 1000.0
            time.sleep(max(0.025, interval))

    s.cursor = [float(ix), float(iy)]
    s._save()


def human_navigate(url):
    """Navigate then pause like a human reading the page.

    Resolves new_tab/goto_url and wait_for_load from the core helpers at call
    time (so this module does not hard-depend on their names), invalidates the
    cached viewport for the new page, and adds a log-normal reading pause.

    Prefers new_tab over goto_url per the SKILL.md rule that goto_url runs in the
    user's active tab and clobbers their work — the safe default opens a new tab.
    """
    import browser_harness.helpers as _h

    _s().invalidate_viewport()
    goto = getattr(_h, "new_tab", None) or getattr(_h, "goto_url", None)
    if goto:
        goto(url)
    wait_for_load = getattr(_h, "wait_for_load", None)
    if wait_for_load:
        try:
            wait_for_load()
        except Exception:
            pass
    human_wait(random.uniform(2.0, 5.0))
