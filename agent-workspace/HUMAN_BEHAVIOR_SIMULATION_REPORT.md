# Human Behavior Simulation Layer for browser-harness

> ⚠️ **STALE — PRE-IMPLEMENTATION DESIGN PROPOSAL (2026-05-28).** Superseded by the shipped code.
> This doc proposes a **numpy** implementation; the shipped layer is **pure stdlib**. OU parameters,
> the tremor envelope, target-offset model, cursor init, and the typing virtual-key path all changed
> after this was written. Do NOT treat its pseudocode or §3.3 "Validation metrics" as ground truth.
> **Authoritative now:** `agent-workspace/agent_helpers.py` + `agent-workspace/HUMAN_SIM_VALIDATION.md`.

**Date:** 2026-05-28
**Purpose:** External LLM review of proposed implementation strategy
**Reviewer context:** This report is self-contained. No prior knowledge of the codebase is assumed.

---

## 1. System Overview

### 1.1 What is browser-harness?

A Python CLI tool that controls the user's **real, running Chrome browser** via CDP (Chrome DevTools Protocol). Unlike Puppeteer/Playwright/Selenium which launch a new browser instance, browser-harness connects to Chrome started with `--remote-debugging-port=9222`.

**Key architectural constraint:** browser-harness does NOT launch Chrome. It connects to an existing instance. This means:
- No Chrome launch flags are controlled by the tool
- The browser's TLS fingerprint, GPU, fonts, plugins, cookies, sessions are all **real user data**
- `navigator.webdriver` is `undefined` (not `true` as with ChromeDriver)
- No `window.cdc_*` ChromeDriver artifacts exist

### 1.2 Current Code Architecture

```
browser-harness/
├── src/browser_harness/
│   ├── helpers.py          # 493 lines — all browser control primitives
│   ├── daemon.py           # CDP WebSocket daemon
│   ├── admin.py            # Daemon lifecycle (start/stop/ensure)
│   ├── run.py              # CLI entry point
│   └── _ipc.py             # IPC between CLI and daemon
├── agent-workspace/
│   ├── agent_helpers.py    # 7 lines — EMPTY, designated for extensions
│   └── domain-skills/      # 90+ site-specific playbooks
└── interaction-skills/     # 16 files — browser mechanics (dialogs, tabs, etc.)
```

**Extension point:** `agent_helpers.py` is auto-loaded by `helpers.py` at import time. Any function defined there becomes available as a top-level helper in browser-harness scripts. This is the designated location for the proposed human simulation layer.

### 1.3 Current Input Primitives (from helpers.py)

```python
# Mouse click — fires mousePressed + mouseReleased immediately, no preceding mouseMoved
def click_at_xy(x, y, button="left", clicks=1):
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button=button, clickCount=clicks)
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button=button, clickCount=clicks)

# Text input — bulk insertion, no per-character events
def type_text(text):
    cdp("Input.insertText", text=text)

# Scroll — single mouseWheel event, no easing or physics
def scroll(x, y, dy=-300, dx=0):
    cdp("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=dx, deltaY=dy)

# Key press — immediate keyDown/char/keyUp sequence
def press_key(key, modifiers=0):
    # ... dispatches 2-3 CDP events with zero delay between them

# Wait — fixed delay, no randomization
def wait(seconds=1.0):
    time.sleep(seconds)
```

**Summary:** All current primitives are mechanically instantaneous with zero human-like characteristics. No randomization, no trajectories, no timing variance.

---

## 2. Research Findings

### 2.1 Threat Model: What Bot Detectors Actually Measure

Modern bot detection operates on two layers:

| Layer | Signals | browser-harness Status |
|-------|---------|----------------------|
| **Static fingerprint** | navigator.webdriver, WebGL renderer, screen geometry, canvas hash, font enumeration, TLS fingerprint (JA3), plugins, speech voices, hardware concurrency | **All clean.** Real Chrome = real fingerprint. 14 detection vectors neutralized automatically. |
| **Behavioral fingerprint** | Mouse trajectories, keystroke timing, scroll physics, click precision, session patterns, event timestamp regularity | **Fully exposed.** Zero simulation. This is the only remaining attack surface. |

**Key insight from research:** Commercial anti-detect browsers (Multilogin $99/mo, GoLogin $49/mo, Kameleo €59/mo) spend enormous engineering effort on C++ Chromium forks to achieve what browser-harness gets for free (real fingerprints). But they also include behavioral simulation that browser-harness lacks entirely.

### 2.2 Bot Detection Signal Priority (Shen et al. 2021, ACM Computing Surveys)

Ranked by detection importance:

1. **Event timestamp regularity** — #1 signal. Perfect 16.67ms intervals = immediate flag
2. **Velocity profile** — constant-speed movement is detectable
3. **Trajectory linearity** — straight-line mouse paths are detectable
4. **Micro-jitter absence** — humans exhibit 0.3-1.2px RMS hand tremor
5. **Click dwell time** — zero-ms or integer-ms mousePressed→mouseReleased is a flag
6. **Pre-click hover absence** — humans pause 80-200ms before clicking
7. **Overshoot + correction** — 10-15% of long-distance moves show this
8. **Fitts' Law violation** — movement time must scale with distance/target size

### 2.3 Ensemble Detection Warning

Modern systems (Cloudflare Bot Management, DataDome, Akamai, HUMAN/PerimeterX) use 200-2000+ signal ensembles with ML classifiers. **Fixing one signal while leaving others at default makes the session MORE suspicious, not less.** The signals must be temporally and causally consistent:

- Mouse movement must precede every click (can't teleport)
- Scroll events must correlate with viewport focus
- Form completion time must scale with field length
- All simulated signals must share a single timeline

### 2.4 Existing Field Data (from 90+ domain-skills)

browser-harness already has site-specific anti-bot knowledge:

| Site | Detection Stack | Required Wait | Threshold |
|------|----------------|---------------|-----------|
| Glassdoor | Cloudflare Bot Mgmt | `wait(5)` post-load | ~5 pages/min |
| G2 | DataDome 5.6.1 | `wait(5)` post-load | 100 req/s API |
| eBay | PerimeterX | `wait(3)` between pages | 5-10 rapid req |
| Facebook | Account-level | `≥2s` between scrolls | Behavioral |
| Booking.com | AWS WAF | `wait(5)` on challenge | Crypto PoW |
| Walmart | PerimeterX | Bare `Mozilla/5.0` UA | UA-sensitive |
| 10+ sites | None | None | No detection |

---

## 3. Proposed Implementation

### 3.1 Design Principles

1. **Layer on top, don't modify core.** All code goes in `agent_helpers.py` (auto-loaded by helpers.py). Core primitives remain untouched for backward compatibility.
2. **Opt-in, not mandatory.** New `human_*` prefixed functions. Existing `click_at_xy()` stays instant for speed-critical operations.
3. **Statistically grounded.** All distributions and parameters from peer-reviewed research with specific citations.
4. **Ensemble-consistent.** All behavioral signals share a single random seed and temporal model.
5. **numpy-only dependency.** No exotic packages. numpy is already commonly available.

### 3.2 Proposed API

```python
# Mouse movement + click (replaces click_at_xy for stealth scenarios)
human_click(x, y, button="left")
    # 1. Generate Bezier trajectory from current cursor position to (x, y)
    # 2. Dispatch ~100-150 mouseMoved events along trajectory
    # 3. Pre-click hover pause (80-200ms)
    # 4. mousePressed with position jitter (σ=2-4px from target)
    # 5. Click dwell (log-normal, μ=85ms)
    # 6. mouseReleased with 0.5px drift

# Mouse movement without click (for hover actions)
human_move(x, y)
    # Bezier trajectory only, no click

# Human-like typing (replaces type_text for stealth scenarios)
human_type(text, profile="skilled")
    # Per-character press_key with log-normal inter-key delays
    # Profiles: hunt_peck (36 WPM), average (72), skilled (100), expert (140)
    # Optional error injection (1-3% rate with backspace correction)

# Human-like scrolling
human_scroll(x, y, distance, direction="down")
    # Multiple mouseWheel events with log-normal deltas
    # Reading pauses injected at 12% probability
    # Trackpad-style inertia deceleration

# Randomized wait (replaces wait() for stealth scenarios)
human_wait(base_seconds=1.0)
    # Log-normal distribution around base_seconds

# Session-level human simulation
human_session_start()
    # Initialize cursor position tracking
    # Set up OU process for idle drift
    # Configure timing model

# Composite: navigate like a human
human_navigate(url)
    # goto_url(url) + wait_for_load() + human_wait(2-5s reading time)
```

### 3.3 Algorithm Details

#### 3.3.1 Mouse Trajectory: Cubic Bezier + Smoothstep + OU Noise

**Why this combination:**
- Cubic Bezier alone produces ~6-8° mean angle change (human target: 8.2° per Ahmed & Traore 2011)
- WindMouse produces 54° (6.6x too jagged) — rejected
- Catmull-Rom spline produces 0.46° (18x too smooth) — rejected
- OU noise adds micro-tremor bringing total to ~7-10° — within human range

**Algorithm:**

```python
import numpy as np

def _bezier_trajectory(start, end, num_points=120):
    """Generate human-like mouse trajectory using cubic Bezier + OU noise."""
    sx, sy = start
    ex, ey = end
    dist = np.hypot(ex - sx, ey - sy)

    # Control points: offset perpendicular to straight line
    # Arc magnitude ~9% of distance with Gaussian variance
    mid_x, mid_y = (sx + ex) / 2, (sy + ey) / 2
    dx, dy = ex - sx, ey - sy
    perp_x, perp_y = -dy, dx  # perpendicular vector
    norm = np.hypot(perp_x, perp_y) or 1
    perp_x, perp_y = perp_x / norm, perp_y / norm

    arc1 = dist * np.random.normal(0.09, 0.04)
    arc2 = dist * np.random.normal(0.09, 0.04)

    cp1 = (sx + dx * 0.3 + perp_x * arc1, sy + dy * 0.3 + perp_y * arc1)
    cp2 = (sx + dx * 0.7 + perp_x * arc2, sy + dy * 0.7 + perp_y * arc2)

    # Bezier evaluation with smoothstep time easing
    t_linear = np.linspace(0, 1, num_points)
    t = t_linear * t_linear * (3 - 2 * t_linear)  # smoothstep

    mt = 1 - t
    points_x = mt**3 * sx + 3 * mt**2 * t * cp1[0] + 3 * mt * t**2 * cp2[0] + t**3 * ex
    points_y = mt**3 * sy + 3 * mt**2 * t * cp1[1] + 3 * mt * t**2 * cp2[1] + t**3 * ey

    # OU noise (micro-tremor), scaled down at endpoints
    theta, sigma, dt = 0.7, 0.5, 1/60
    noise_x, noise_y = np.zeros(num_points), np.zeros(num_points)
    for i in range(1, num_points):
        noise_x[i] = noise_x[i-1] + theta * (0 - noise_x[i-1]) * dt + sigma * np.sqrt(dt) * np.random.randn()
        noise_y[i] = noise_y[i-1] + theta * (0 - noise_y[i-1]) * dt + sigma * np.sqrt(dt) * np.random.randn()

    # Scale jitter down at endpoints (stable start/end)
    jitter_scale = 1.0 - np.abs(2 * t_linear - 1)
    points_x += noise_x * jitter_scale
    points_y += noise_y * jitter_scale

    return list(zip(points_x, points_y))
```

**Validation metrics:**
- Path deviation from straight line: ~7% (human range: 2-15%)
- Mean angle change: ~7-10° (human empirical: 8.2°)
- Velocity profile: bell-shaped (smoothstep)
- Micro-jitter RMS: ~0.28px (human range: 0.3-1.2px)

#### 3.3.2 Event Timing

**Critical: #1 detection signal.**

```python
def _human_delay(base_ms, sigma_ms=3.0):
    """Add Gaussian jitter to avoid timestamp regularity."""
    jitter = np.random.normal(0, sigma_ms)
    delay = max(1, base_ms + jitter) / 1000.0
    time.sleep(delay)

# Between mouseMoved events: 16.67ms ± 3-5ms Gaussian
# Pre-click hover: uniform(80, 200) ms
# Click dwell: log-normal(μ=log(85), σ=0.28) ms ≈ 50-150ms
# Post-click pause: uniform(50, 150) ms
```

#### 3.3.3 Keystroke Dynamics (CMU Keystroke Dataset, Killourhy & Maxion 2009)

```python
TYPING_PROFILES = {
    "hunt_peck": {"dd_mean": 335, "dd_std": 182, "hold_mean": 95, "hold_std": 30},
    "average":   {"dd_mean": 166, "dd_std": 62,  "hold_mean": 79, "hold_std": 22},
    "skilled":   {"dd_mean": 120, "dd_std": 34,  "hold_mean": 75, "hold_std": 18},
    "expert":    {"dd_mean": 86,  "dd_std": 18,  "hold_mean": 65, "hold_std": 12},
}

def human_type(text, profile="skilled"):
    """Type text with human-like inter-key timing."""
    p = TYPING_PROFILES[profile]
    for i, ch in enumerate(text):
        # Log-normal inter-key delay
        if i > 0:
            dd = np.random.lognormal(
                mean=np.log(p["dd_mean"]) - 0.5 * (p["dd_std"]/p["dd_mean"])**2,
                sigma=p["dd_std"] / p["dd_mean"]
            )
            time.sleep(max(20, dd) / 1000.0)

        # Key down
        press_key(ch)
        # Note: press_key already dispatches keyDown + char + keyUp
        # For deeper realism, could split into separate keyDown/keyUp
        # with log-normal hold time, but current implementation is adequate
        # for most detection systems.
```

**Parameters source:** CMU Keystroke Dynamics Benchmark (51 subjects, peer-reviewed DSN 2009). The `skilled` profile (DD mean=120ms, std=34ms, ~100 WPM) is recommended as default — closely matches the CMU empirical average (118ms, 42ms).

#### 3.3.4 Scroll Simulation

```python
def human_scroll(x, y, distance=3000, direction="down"):
    """Scroll with human-like physics."""
    sign = -1 if direction == "down" else 1
    scrolled = 0
    while scrolled < distance:
        # Log-normal scroll delta
        delta = np.random.lognormal(mean=np.log(167), sigma=0.4)
        delta = min(delta, distance - scrolled)

        cdp("Input.dispatchMouseEvent", type="mouseWheel",
            x=x, y=y, deltaX=0, deltaY=sign * delta)

        scrolled += delta

        # Reading pause (12% probability)
        if np.random.random() < 0.12:
            pause = np.random.uniform(0.8, 3.0)
            time.sleep(pause)
        else:
            # Normal inter-scroll delay
            delay = np.random.lognormal(mean=np.log(0.101), sigma=0.3)
            time.sleep(max(0.03, delay))
```

#### 3.3.5 Human Click (Full Sequence)

```python
_cursor_pos = [0, 0]  # Track current cursor position

def human_click(x, y, button="left"):
    """Move cursor to target via Bezier trajectory, then click with human timing."""
    global _cursor_pos

    # 1. Generate trajectory
    trajectory = _bezier_trajectory(_cursor_pos, (x, y))

    # 2. Dispatch mouseMoved events along trajectory
    for px, py in trajectory:
        cdp("Input.dispatchMouseEvent", type="mouseMoved", x=px, y=py)
        _human_delay(16.67, sigma_ms=3.0)  # ~60fps with jitter

    # 3. Pre-click hover
    time.sleep(np.random.uniform(0.08, 0.20))

    # 4. Click with position jitter
    click_x = x + np.random.normal(0, 2.5)
    click_y = y + np.random.normal(0, 2.0)

    cdp("Input.dispatchMouseEvent", type="mousePressed",
        x=click_x, y=click_y, button=button, clickCount=1)

    # 5. Click dwell (log-normal)
    dwell = np.random.lognormal(mean=np.log(85), sigma=0.28) / 1000.0
    time.sleep(max(0.03, dwell))

    # 6. Release with slight drift
    release_x = click_x + np.random.normal(0, 0.5)
    release_y = click_y + np.random.normal(0, 0.5)

    cdp("Input.dispatchMouseEvent", type="mouseReleased",
        x=release_x, y=release_y, button=button, clickCount=1)

    # 7. Update cursor position
    _cursor_pos = [release_x, release_y]
```

---

## 4. Open Questions for Review

### 4.1 Algorithm Selection

**Q1:** Is cubic Bezier + smoothstep + OU noise the right combination? Or should we consider:
- B-spline with randomly placed knots for more trajectory variety?
- Separate ballistic phase (fast) + corrective phase (slow near target) per Fitts' Law?
- Completely different approach like recorded human trajectory replay from a dataset?

**Q2:** The OU process parameters (θ=0.7, σ=0.5) produce RMS 0.28px, which is slightly below the human lower bound of 0.3px. Should we increase σ to 0.6-0.8 for better coverage of the human distribution?

### 4.2 Architecture Decisions

**Q3:** Should cursor position tracking (`_cursor_pos`) be:
- A global variable (simple, current proposal)?
- A class instance (`HumanSession`) that also tracks session state?
- Stored in the CDP daemon for cross-script persistence?

**Q4:** Should we implement overshoot-and-correction (documented as occurring in 10-15% of long-distance moves >400px)? It adds complexity but addresses a known detection signal. If yes, what algorithm?

**Q5:** The `human_type()` function currently uses `press_key()` which dispatches keyDown+char+keyUp instantly. For deeper realism, should we split these into separate events with per-key hold time (dwell)? The CMU dataset provides hold time distributions (mean=79ms, std=22ms). This would triple the CDP calls per character.

### 4.3 Timing Model

**Q6:** The current proposal uses `time.sleep()` for inter-event delays. Python's `time.sleep()` has ~1ms granularity on most systems but can be up to ~15ms on some platforms. Is this sufficient for event timing jitter, or should we use a busy-wait loop for sub-millisecond precision?

**Q7:** Should we implement a global "fatigue model" where typing speed gradually decreases (2-5%) over long sessions? Academic literature (CMU dataset) shows this effect but it may be over-engineering.

### 4.4 Ensemble Consistency

**Q8:** The current design has independent random generators for each behavioral dimension (mouse, keyboard, scroll). Should these be correlated? For example:
- Faster mouse movement → faster typing (same "user energy level")
- Longer reading pauses → slower scroll speed
- Time-of-day affecting all timing parameters

**Q9:** Should we inject synthetic `visibilitychange`/`blur`/`focus` events to simulate tab switching? Research shows humans switch tabs every 2-10 minutes. This would require JS injection via `Page.addScriptToEvaluateOnNewDocument`, which browser-harness currently avoids.

### 4.5 Validation Strategy

**Q10:** How should we validate the implementation? Options:
- Run against creepjs.com / fingerprintjs.com and compare scores
- Test against Cloudflare Bot Management on a known-protected site (Glassdoor)
- Statistical analysis: compare generated trajectory metrics against Ahmed & Traore 2011 dataset
- A/B test: same task with `click_at_xy()` vs `human_click()` on DataDome-protected sites

### 4.6 Performance Trade-offs

**Q11:** `human_click()` takes ~2 seconds (120 mouseMoved events × 16.67ms + hover + dwell) vs `click_at_xy()` at ~50ms. For scripts that perform 100+ clicks, this is 200s vs 5s. Should we implement an adaptive mode that:
- Uses `human_click()` for first N interactions (establishing behavioral baseline)
- Gradually reduces trajectory points for subsequent clicks
- Falls back to `click_at_xy()` for off-screen/background operations

**Q12:** Should `num_points` in the trajectory scale with distance (Fitts' Law: longer distance → more points → longer duration)? Current fixed 120 points means short moves take disproportionately long.

### 4.7 Dependency Policy

**Q13:** numpy is proposed as the sole dependency. Alternatives:
- **Pure Python (math + random only):** No dependency, but 5-10x slower for trajectory generation. Acceptable since we sleep between events anyway?
- **numpy:** Fast, convenient, widely available. But adds a dependency to a tool that currently has zero Python dependencies beyond stdlib.
- **scipy:** Adds CubicSpline, stats distributions. Overkill?

### 4.8 Scope and Phasing

**Q14:** Should we implement all features at once, or phase:
- **Phase 1:** `human_wait()` + timing jitter only (addresses #1 detection signal, minimal code)
- **Phase 2:** `human_click()` with Bezier trajectory (addresses #2-4 signals)
- **Phase 3:** `human_type()` + `human_scroll()` (full behavioral stack)

Or is there a reason to ship everything together (ensemble consistency argument)?

---

## 5. Competitive Positioning

### 5.1 After Implementation

| Tool | Fingerprint Layer | Behavioral Layer | Cost | Dependency |
|------|-------------------|-----------------|------|------------|
| **browser-harness + proposed** | Real Chrome (best possible) | Research-grade simulation | Free | numpy |
| Multilogin | C++ Chromium fork | Built-in | $99/month | Custom binary |
| GoLogin | Orbita Chromium fork | Built-in | $49/month | Custom binary |
| Browser Use (cloud) | Stock Playwright | LLM-emergent behavior | API pricing | Cloud service |
| puppeteer-stealth | JS patches (leaky) | ghost-cursor (partial) | Free | Node.js |
| Bright Data Scraping Browser | Managed Chromium | Server-side | $13.50/GB | Cloud service |

### 5.2 Unique Advantages of This Approach

1. **Fingerprint authenticity:** No other tool achieves this without a custom browser fork. browser-harness uses THE USER'S ACTUAL BROWSER with their actual history, cookies, extensions, and hardware.

2. **Research-grounded behavioral simulation:** Most commercial tools use ad-hoc randomization. The proposed implementation uses peer-reviewed parameters (CMU Keystroke Dataset, Ahmed & Traore 2011, Shen et al. 2021).

3. **Zero cost, single-file addition.** The entire implementation goes into one Python file (`agent_helpers.py`) that is auto-loaded by the existing architecture.

4. **AI agent integration.** browser-harness is designed for AI agent control (Claude, GPT, etc.). Human simulation makes AI-driven browser sessions indistinguishable from human ones.

---

## 6. Existing Code Context

### 6.1 How agent_helpers.py is loaded (from helpers.py:478-493)

```python
def _load_agent_helpers():
    p = AGENT_WORKSPACE / "agent_helpers.py"
    if not p.exists():
        return
    spec = importlib.util.spec_from_file_location("browser_harness_agent_helpers", p)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if name.startswith("_"):
            continue
        globals()[name] = value

_load_agent_helpers()
```

**Implication:** Any public function (not starting with `_`) defined in `agent_helpers.py` becomes a top-level import from `browser_harness.helpers`. So `human_click(x, y)` would be callable directly in browser-harness scripts just like `click_at_xy(x, y)`.

### 6.2 CDP primitives available (used by proposed code)

```python
cdp("Input.dispatchMouseEvent", type="mouseMoved|mousePressed|mouseReleased|mouseWheel", x=..., y=..., button=..., clickCount=..., deltaX=..., deltaY=...)
cdp("Input.dispatchKeyEvent", type="keyDown|char|keyUp", key=..., code=..., text=..., modifiers=..., windowsVirtualKeyCode=..., nativeVirtualKeyCode=...)
cdp("Input.insertText", text=...)
cdp("Page.addScriptToEvaluateOnNewDocument", source=...)  # available but currently unused
cdp("Runtime.evaluate", expression=..., returnByValue=True, awaitPromise=True)
```

### 6.3 Design constraints (from SKILL.md)

- Core helpers stay short. Task-specific additions go in `agent_helpers.py`.
- Don't add a manager layer. No retries framework, session manager, daemon supervisor, config system, or logging framework.
- Prefer compositor-level actions over framework hacks.

---

## 7. Summary of Review Request

Please evaluate:

1. **Algorithm correctness:** Are the proposed algorithms (Bezier + smoothstep + OU, log-normal timing, CMU keystroke model) the best choices? What alternatives should be considered?

2. **Parameter calibration:** Are the statistical parameters well-chosen and properly sourced? Any concerning gaps between proposed values and known human distributions?

3. **Architecture fit:** Does the proposed single-file, opt-in, `human_*` prefix approach fit well with the existing codebase? Any anti-patterns?

4. **Completeness:** Are there critical behavioral signals not addressed by this proposal?

5. **Risk assessment:** What are the most likely failure modes? Which bot detection systems would this approach fail against, and why?

6. **Implementation priority:** What should be built first for maximum impact with minimum code?

7. **Answers to Q1-Q14** above, with reasoning.
