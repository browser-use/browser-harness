# Human Behavior Simulation — Implementation Review

> ⚠️ **STALE — describes a 348-line draft that no longer exists.** The shipped code is ~560 lines and
> diverges on: OU tremor (Euler θ=0.7/σ=0.5 → **exact discretization**, dt tied to the real per-event
> interval, std re-calibrated to **0.795px**, anisotropic), envelope (triangle → **sine**), target-offset
> (per-click bias → **session-level** bias), cursor init ([0,0] → **lazy random**), typing (default
> semantic now uses `_vk_for_char` + non-zero hold; no longer routes through the buggy `press_key`),
> velocity (smoothstep → **ballistic Beta(2,3)**), plus **Fitts' Law MT**, **overshoot**, **scroll detents**,
> **idle drift**, **cross-`-c` session persistence**, and namespace hardening.
> Its §4 "Validated Test Results" table reflects the abandoned σ=0.6 OU (RMS 0.451px) — **NOT** shipped
> behavior. Review questions A2 (sine envelope), A3 (device param), R1 (persistence), C2 (`_vk_for_char`)
> are already resolved in code.
> **Authoritative now:** `agent-workspace/agent_helpers.py` + `agent-workspace/HUMAN_SIM_VALIDATION.md`.

**Date:** 2026-05-28
**Reviewer:** Gemini Deep Think
**Context:** This is a completed implementation. We seek a code-level review, not a design review. A prior design review by GPT 5.5 Pro Extended Thinking was already incorporated.

---

## 1. What This Is

A single-file Python module (`agent_helpers.py`, 348 lines) that adds human-like behavioral simulation to **browser-harness**, a CDP-based browser automation tool. browser-harness connects to the user's real running Chrome via `--remote-debugging-port`, giving it perfect static fingerprints (real GPU, fonts, cookies, TLS). This module addresses the remaining behavioral detection surface.

## 2. Architecture

```
browser-harness/
├── src/browser_harness/
│   └── helpers.py          # Core CDP primitives (click_at_xy, type_text, scroll, etc.)
│                           # Auto-loads agent_helpers.py at import time via:
│                           #   _load_agent_helpers() → importlib → exports public names
├── agent-workspace/
│   └── agent_helpers.py    # THIS FILE — human simulation layer
```

**Loading mechanism** (`helpers.py:478-493`):
```python
def _load_agent_helpers():
    p = AGENT_WORKSPACE / "agent_helpers.py"
    spec = importlib.util.spec_from_file_location("browser_harness_agent_helpers", p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if name.startswith("_"):
            continue
        globals()[name] = value  # exports public names into helpers namespace
```

So `human_click(x, y)` becomes callable just like `click_at_xy(x, y)` in browser-harness scripts.

## 3. The Complete Implementation

```python
"""Human behavior simulation for browser-harness.

Adds human-like timing, mouse trajectories, typing, and scrolling
on top of CDP primitives for UI automation reliability.

Usage:
    human_session("paced")          # configure session (optional, defaults to "paced")
    human_click(500, 300)           # Bezier trajectory + click with timing
    human_type("hello", mode="semantic")  # per-character with inter-key delays
    human_scroll(600, 400, 2000)    # scroll with reading pauses
    human_wait(2.0)                 # log-normal randomized wait
"""

import math, random, time

from browser_harness.helpers import cdp, press_key


# ---------------------------------------------------------------------------
# Pacing profiles — policy-based, not adaptive
# ---------------------------------------------------------------------------

PACING = {
    "fast": {
        "move_speed": 0.3,
        "hover_range": (0.02, 0.05),
        "dwell_mean": 45,
        "type_speed": 1.5,
        "scroll_speed": 1.5,
        "wait_mult": 0.5,
        "event_jitter_ms": 1.5,
    },
    "paced": {
        "move_speed": 1.0,
        "hover_range": (0.08, 0.20),
        "dwell_mean": 85,
        "type_speed": 1.0,
        "scroll_speed": 1.0,
        "wait_mult": 1.0,
        "event_jitter_ms": 3.0,
    },
    "physical": {
        "move_speed": 1.2,
        "hover_range": (0.10, 0.25),
        "dwell_mean": 95,
        "type_speed": 0.8,
        "scroll_speed": 0.8,
        "wait_mult": 1.3,
        "event_jitter_ms": 4.0,
    },
}

# ---------------------------------------------------------------------------
# Typing profiles — CMU Keystroke Dataset (Killourhy & Maxion, DSN 2009)
# dd = down-down interval, hold = key hold duration (ms)
# ---------------------------------------------------------------------------

TYPING_PROFILES = {
    "hunt_peck": {"dd_mean": 335, "dd_std": 182, "hold_mean": 95, "hold_std": 30},
    "average":   {"dd_mean": 166, "dd_std": 62,  "hold_mean": 79, "hold_std": 22},
    "skilled":   {"dd_mean": 120, "dd_std": 34,  "hold_mean": 75, "hold_std": 18},
    "expert":    {"dd_mean": 86,  "dd_std": 18,  "hold_mean": 65, "hold_std": 12},
}


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class HumanSession:
    """Tracks cursor position and pacing configuration across interactions."""

    def __init__(self, pacing="paced"):
        self.cursor = [0.0, 0.0]
        self.pacing = pacing
        self.profile = PACING[pacing]

    def set_pacing(self, pacing):
        self.pacing = pacing
        self.profile = PACING[pacing]


_session = None


def _s():
    global _session
    if _session is None:
        _session = HumanSession()
    return _session


# ---------------------------------------------------------------------------
# Math helpers (pure Python — no numpy required)
# ---------------------------------------------------------------------------

def _lognormal(mean, std):
    """Sample from log-normal given desired mean and std in natural units."""
    if mean <= 0:
        return max(0.001, mean)
    variance = std ** 2
    mu = math.log(mean ** 2 / math.sqrt(variance + mean ** 2))
    sigma = math.sqrt(math.log(1 + variance / mean ** 2))
    return random.lognormvariate(mu, sigma)


def _smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def _ou_noise(n, theta=0.7, sigma=0.5, dt=1.0 / 60):
    """Ornstein-Uhlenbeck process for micro-tremor simulation."""
    vals = [0.0]
    for _ in range(n - 1):
        prev = vals[-1]
        vals.append(prev + theta * (0 - prev) * dt + sigma * math.sqrt(dt) * random.gauss(0, 1))
    return vals


def _distance_points(dist):
    """Scale trajectory point count with distance (Fitts' Law)."""
    return max(20, min(200, int(dist * 0.08)))


def _bezier_trajectory(start, end):
    """Cubic Bezier + smoothstep easing + OU micro-jitter + path noise.

    Produces curvature ~7-10 deg/step (human empirical: 8.2 deg, Ahmed & Traore 2011).
    """
    sx, sy = start
    ex, ey = end
    dist = math.hypot(ex - sx, ey - sy)

    if dist < 2:
        return [(ex, ey)]

    n = _distance_points(dist)

    dx, dy = ex - sx, ey - sy
    norm = dist or 1
    perp_x, perp_y = -dy / norm, dx / norm

    arc1 = dist * random.gauss(0.09, 0.04)
    arc2 = dist * random.gauss(0.09, 0.04)

    cp1 = (sx + dx * 0.3 + perp_x * arc1, sy + dy * 0.3 + perp_y * arc1)
    cp2 = (sx + dx * 0.7 + perp_x * arc2, sy + dy * 0.7 + perp_y * arc2)

    noise_x = _ou_noise(n, theta=0.7, sigma=0.6)
    noise_y = _ou_noise(n, theta=0.7, sigma=0.6)

    step_px = dist / max(1, n - 1)
    path_noise_sigma = step_px * 0.14

    points = []
    for i in range(n):
        t_lin = i / max(1, n - 1)
        t = _smoothstep(t_lin)
        mt = 1.0 - t

        px = mt**3 * sx + 3 * mt**2 * t * cp1[0] + 3 * mt * t**2 * cp2[0] + t**3 * ex
        py = mt**3 * sy + 3 * mt**2 * t * cp1[1] + 3 * mt * t**2 * cp2[1] + t**3 * ey

        jitter_scale = 1.0 - abs(2 * t_lin - 1)
        px += noise_x[i] * jitter_scale
        py += noise_y[i] * jitter_scale
        px += random.gauss(0, path_noise_sigma) * jitter_scale
        py += random.gauss(0, path_noise_sigma) * jitter_scale

        points.append((px, py))

    return points


def _target_offset(x, y):
    """Target-acquisition uncertainty: slight offset biased down-right (hand anatomy)."""
    return (
        x + random.gauss(1.5, 2.5),
        y + random.gauss(1.0, 2.0),
    )


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

def _jittered_sleep(base_ms, sigma_ms=None):
    if sigma_ms is None:
        sigma_ms = _s().profile["event_jitter_ms"]
    delay = max(8, base_ms + random.gauss(0, sigma_ms)) / 1000.0
    time.sleep(delay)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def human_session(pacing="paced"):
    """Configure or reconfigure the session pacing.

    Modes:
        fast     — internal/admin tools, speed over realism
        paced    — ordinary UI automation (default)
        physical — keyboard/mouse event testing, most deliberate
    """
    global _session
    _session = HumanSession(pacing)
    return _session


def human_wait(base=1.0):
    """Log-normal randomized wait around base seconds."""
    p = _s().profile
    actual = _lognormal(base, base * 0.3) * p["wait_mult"]
    time.sleep(max(0.05, actual))


def human_move(x, y):
    """Move cursor to (x, y) via Bezier trajectory with OU micro-jitter."""
    s = _s()
    trajectory = _bezier_trajectory(s.cursor, (x, y))
    speed = s.profile["move_speed"]
    base_interval = max(25, 16.67 * speed)

    for px, py in trajectory:
        cdp("Input.dispatchMouseEvent", type="mouseMoved", x=px, y=py)
        _jittered_sleep(base_interval)

    s.cursor = [x, y]


def human_click(x, y, button="left"):
    """Move cursor via Bezier trajectory, then click with human timing.

    Full event sequence: mouseMoved (trajectory) -> hover pause ->
    mousePressed (with position jitter) -> dwell -> mouseReleased (with drift).
    """
    s = _s()
    p = s.profile

    human_move(x, y)

    hover_lo, hover_hi = p["hover_range"]
    time.sleep(random.uniform(hover_lo, hover_hi))

    cx, cy = _target_offset(x, y)

    cdp("Input.dispatchMouseEvent",
        type="mousePressed", x=cx, y=cy, button=button, clickCount=1)

    dwell = _lognormal(p["dwell_mean"], p["dwell_mean"] * 0.28) / 1000.0
    time.sleep(max(0.03, dwell))

    rx = cx + random.gauss(0, 0.5)
    ry = cy + random.gauss(0, 0.5)
    cdp("Input.dispatchMouseEvent",
        type="mouseReleased", x=rx, y=ry, button=button, clickCount=1)

    s.cursor = [rx, ry]


def human_type(text, profile="skilled", mode="semantic"):
    """Type text with human-like inter-key timing.

    Modes:
        semantic  — press_key per character with log-normal inter-key delays.
                    Sufficient for most form filling and UI interaction.
        physical  — separate keyDown/keyUp with per-key hold (dwell) time.
                    Use when testing actual keyboard event handling.

    Profiles: hunt_peck (~36 WPM), average (~72), skilled (~100), expert (~140).
    """
    tp = TYPING_PROFILES[profile]
    speed = _s().profile["type_speed"]
    dd_mean = tp["dd_mean"] / speed
    dd_std = tp["dd_std"] / speed

    if mode == "physical":
        _type_physical(text, tp, speed)
    else:
        _type_semantic(text, dd_mean, dd_std)


def _type_semantic(text, dd_mean, dd_std):
    for i, ch in enumerate(text):
        if i > 0:
            delay = _lognormal(dd_mean, dd_std)
            time.sleep(max(0.02, delay / 1000.0))
        press_key(ch)


def _type_physical(text, tp, speed):
    hold_mean = tp["hold_mean"] / speed
    hold_std = tp["hold_std"] / speed
    dd_mean = tp["dd_mean"] / speed
    dd_std = tp["dd_std"] / speed

    _KEYS = {
        "Enter": (13, "Enter", "\r"), "Tab": (9, "Tab", "\t"),
        "Backspace": (8, "Backspace", ""), " ": (32, "Space", " "),
    }

    prev_up_time = 0.0

    for i, ch in enumerate(text):
        if i > 0:
            dd = _lognormal(dd_mean, dd_std) / 1000.0
            elapsed = time.monotonic() - prev_up_time
            remaining = max(0.005, dd - elapsed)
            time.sleep(remaining)

        vk, code, t = _KEYS.get(ch, (ord(ch) if len(ch) == 1 else 0, ch, ch if len(ch) == 1 else ""))
        base = {"key": ch, "code": code, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}

        cdp("Input.dispatchKeyEvent", type="keyDown", **base, **({"text": t} if t else {}))
        if t and len(t) == 1:
            cdp("Input.dispatchKeyEvent", type="char", text=t,
                **{k: v for k, v in base.items() if k != "text"})

        hold = _lognormal(hold_mean, hold_std) / 1000.0
        time.sleep(max(0.02, hold))

        cdp("Input.dispatchKeyEvent", type="keyUp", **base)
        prev_up_time = time.monotonic()


def human_scroll(x, y, distance=3000, direction="down"):
    """Scroll with human-like physics: log-normal deltas and reading pauses."""
    sign = -1 if direction == "down" else 1
    speed = _s().profile["scroll_speed"]
    scrolled = 0

    while scrolled < distance:
        delta = _lognormal(167, 60) / speed
        delta = min(delta, distance - scrolled)
        if delta < 1:
            break

        cdp("Input.dispatchMouseEvent",
            type="mouseWheel", x=x, y=y, deltaX=0, deltaY=sign * delta)
        scrolled += delta

        if random.random() < 0.12:
            time.sleep(random.uniform(0.8, 3.0))
        else:
            interval = _lognormal(101, 30) / speed / 1000.0
            time.sleep(max(0.03, interval))
```

## 4. Validated Test Results

### 4.1 Statistical Validation (math functions, isolated)

| Test | Result | Target | Status |
|------|--------|--------|--------|
| Lognormal(85,24) | mean=85.7, std=24.3 | ~85, ~24 | PASS |
| Lognormal(120,34) | mean=120.0, std=34.5 | ~120, ~34 | PASS |
| Lognormal(167,60) | mean=165.0, std=60.7 | ~167, ~60 | PASS |
| Bezier endpoint accuracy | 0.00px error | <5px | PASS |
| Trajectory curvature | 7.6 deg ± 0.8 | ~8.2 deg (Ahmed & Traore 2011) | PASS |
| OU noise RMS (sigma=0.6) | 0.451px | 0.3-1.2px (human range) | PASS |
| Distance scaling 50px | 20 pts, 0.3s | Fitts' Law | PASS |
| Distance scaling 1000px | 80 pts, 1.3s | Fitts' Law | PASS |
| Distance scaling 2000px | 160 pts, 2.7s | Fitts' Law | PASS |

### 4.2 Browser Integration Test (CDP, live Chrome)

| Function | fast mode | paced mode | Status |
|----------|----------|-----------|--------|
| human_move | 1.23s | ~3s | PASS |
| human_click | 0.67s | 4.36s | PASS |
| human_wait(0.5) | 0.36s | - | PASS |
| human_scroll(500px) | 0.29s | - | PASS |

### 4.3 IPC Constraint Discovered During Testing

browser-harness daemon creates a new IPC socket connection per CDP call. Rapid-fire calls (<25ms intervals) saturate the daemon. Fix: `human_move` enforces `max(25, 16.67 * speed)` ms minimum between `mouseMoved` events.

## 5. Design Decisions Already Made (via GPT 5.5 Review)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| State management | `HumanSession` class | Explicit state, survives tab switches (vs. fragile global) |
| Pacing | Policy-based (fast/paced/physical) | Auditable and predictable (vs. adaptive stealth) |
| Dependencies | Pure Python stdlib | Zero dependency friction (vs. numpy requirement) |
| Typing modes | semantic / physical | Most UIs need semantic; physical only for event-handler testing |
| Trajectory scaling | Distance-proportional points | Short moves fast, long moves natural (Fitts' Law) |
| Overshoot | Replaced with target-acquisition uncertainty | `_target_offset` with bivariate Gaussian (vs. complex overshoot model) |
| Synthetic focus/blur | Not implemented | Contradicts tool's compositor-level philosophy |
| Fatigue model | Not implemented | Over-engineering for Phase 1 |

## 6. Specific Review Questions

### Code Quality
**C1.** The `_lognormal(mean, std)` conversion to mu/sigma uses the standard formula, but does it handle edge cases correctly? What happens when `std > mean` (high variance)?

**C2.** The `_type_physical` function duplicates the `_KEYS` mapping from `helpers.py`. Should it import the mapping, or is the duplication acceptable given the limited overlap (4 keys vs 14)?

**C3.** Is the `_target_offset` bivariate Gaussian (mean=1.5px right, 1.0px down) a reasonable model for hand-anatomy click bias? The down-right bias comes from the observation that most users click with a rightward wrist angle.

### Algorithm Correctness
**A1.** The path noise uses `path_noise_sigma = step_px * 0.14` which produces ~8 deg curvature. But this means the noise amplitude scales with distance (longer moves = bigger noise). Is this physically correct, or should path noise be distance-independent?

**A2.** The `jitter_scale = 1.0 - abs(2 * t_lin - 1)` produces a triangle envelope: zero at endpoints, max at midpoint. This means the trajectory always starts and ends on the exact Bezier curve with zero noise. Is a triangle the right shape, or should noise taper more gradually (e.g., sine envelope)?

**A3.** In `human_scroll`, the `_lognormal(167, 60)` for scroll delta comes from eye-tracking literature (Liu et al. 2010). But this is for mouse-wheel scrolling. On macOS with a trackpad (the common case for this tool), scroll deltas are typically smaller and more continuous. Should there be a device-type parameter?

### Robustness
**R1.** The `_session` global is module-level and persists across browser-harness script invocations within the same daemon lifetime. But the cursor position tracking starts at `[0, 0]` — it doesn't know where the real cursor is. Is this a problem? Should we query actual cursor position from Chrome?

**R2.** The 25ms IPC floor in `human_move` was discovered empirically. Is there a more principled way to determine this, or should it be configurable?

**R3.** What happens if `human_click` targets coordinates outside the viewport? The CDP `Input.dispatchMouseEvent` accepts any coordinates, but Chrome may not deliver the event to the correct element. Should we clamp to viewport bounds?
