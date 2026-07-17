# Human Behavior Simulation — Validation (shipped code)

**Date:** 2026-05-29
**Status:** Shipped & validated. This is the authoritative validation artifact for
`agent-workspace/agent_helpers.py`. The two `HUMAN_*_REVIEW*.md` / `*REPORT.md` files are
**stale design/review drafts** kept for history only — numbers there do not reflect the code.

browser-harness connects to the user's real running Chrome via CDP, so the static fingerprint
is genuinely the user's own. This layer addresses the residual **behavioral** surface for
**ethical-use-only** UI automation reliability (own accounts / authorized targets / ToS-respecting).

---

## How to run the tests

```bash
python3 tests/unit/test_human_behavior.py        # 24/24 — behavior + dispatch + selftest logic
python3 tests/unit/test_daemon_input_sequence.py # 3/3  — daemon batch handler + Runtime omit
```

To measure what YOUR Chrome actually exposes (T1 coalesced / T2 screenX / delivered rate /
isTrusted), run `human_selftest()` on a normal http(s) page — see `CEILING_DECISIONS.md`:

```bash
browser-harness -c 'new_tab("https://example.com"); wait_for_load(); import json; print(json.dumps(human_selftest(), indent=2))'
```

The suite injects a fake `browser_harness.helpers` (capturing every CDP call) so the module's
load contract and dispatch invariants are exercised without a live browser.

## Validated results (against the SHIPPED parameters)

| Property | Result | Target / source | Status |
|---|---|---|---|
| `_lognormal` mean/std recovery (incl. std>mean) | within ~1-2% over 60k draws | requested mean/std | PASS |
| OU tremor **stationary std** | **1.001** (req 1.0) | exact discretization, no Euler bias | PASS |
| OU **lag-1 autocorrelation** | **0.7455** | `exp(-dt/τ)` = 0.7470 at dt=35ms, τ=0.12s | PASS |
| Tremor **per-axis RMS** | **0.795 px** | human hand-tremor band 0.3–1.2 px | PASS |
| Tremor anisotropy | 2:1 axes, session-fixed rotation | structured (not isotropic noise) | PASS |
| Ballistic easing | velocity peaks at ~t=0.33, monotonic | Meyer/Woodworth 2-component | PASS |
| Fitts' Law MT (paced, W=80) | D=50→164ms, 200→297, 800→495, 1600→607 | log law, not linear | PASS |
| Realized per-step turning angle | **5.58°** | Ahmed & Traore ~8.2° (see calibration note) | TRADE |
| Bezier endpoint | exactly == target | teleport-fix invariant | PASS |
| `human_click` invariant | mousePressed == final mouseMoved (int) | no teleport-on-click | PASS |
| `_vk_for_char('a')` | (65, 'KeyA', 'a') | NOT ord('a')=97=VK_NUMPAD1 | PASS |
| Integer coords to CDP | every x/y/deltaY is int | plausible MouseEvent.clientX | PASS |
| Wheel deltas are detent multiples | 5000 seeds / 48810 events / **0 non-detent** | discrete wheel notch | PASS |
| Idle drift bound | ≤25px from anchor over a 10s wait | bounded wander (not random walk) | PASS |
| Release micro-drift | ≤1px, clamped in-viewport | finger shift during hold | PASS |

## Calibration decision (amplitude vs curvature)

The cited curvature (8.2°/step, Ahmed & Traore 2011) and the cited tremor amplitude band
(0.3–1.2px RMS, signal #4) **cannot both be satisfied by one constant tremor σ**. The earlier
draft chose σ=12 → ~2.19px std, which hit the angle but **exceeded the amplitude band** (a direct
contradiction of its own signal #4). The shipped code **prioritizes amplitude**: tremor std is set
to land at ~0.795px (inside the human band), with the realized per-step angle falling to ~5.58°.
Rationale: micro-jitter RMS is a directly-measured detector signal; the 8.2° figure is an asserted
aggregate. Both metrics now sit in a plausible region rather than one being wildly off.

## Ceilings — what the 2026-05-29 daemon/core update fixed, and what it cannot

Researched against Chromium source + fingerprinting literature.

1. **Event RATE — FIXED.** High-frequency mouse/wheel dispatch now runs server-side via the
   daemon's persistent CDP WS (new `meta:"input_sequence"` handler in `daemon.py` +
   `helpers.dispatch_input_sequence`), so top-level events reach the page at ~60Hz instead of
   the ~28–30Hz the per-call IPC client path tops out at. A mid-batch send failure resumes the
   remainder client-side (resume-from-count; never re-sends the dispatched prefix); a pre-batch
   daemon falls back to the client path automatically (restart the daemon for the fast path).
2. **Coalesced events — NOT fixable in software.** CDP `Input.dispatchMouseEvent` injects via
   `RenderWidgetHostImpl::ForwardMouseEvent`, bypassing the compositor coalescing queue, so
   `PointerEvent.getCoalescedEvents()` stays empty at *any* injection rate. (This is precisely
   why we target ~60Hz, not higher — extra uncoalesced events look more anomalous, not less.)
   Closing it requires a patched Chromium binary.
3. **screenX/screenY — residual tell.** CDP sets `screenX==clientX` (no window/desktop offset),
   which a real windowed browser never produces; Cloudflare Turnstile checks this. Not settable
   via CDP and not safely patchable from page JS. Unfixed.
4. **pressure / tilt / pointerType — NOT a tell.** pressure 0 (no button) / 0.5 (button), tilt 0,
   pointerType "mouse" are exactly the W3C defaults a real mouse reports. (Corrects an earlier
   over-statement that the absence of a pressure/tilt stream was synthetic.)
5. **CDP-presence — mitigated.** The daemon omits `Runtime.enable` by default
   (`BH_CDP_ENABLE_RUNTIME=1` restores it), removing the console-serialization detection class;
   `Runtime.evaluate` works without it and nothing in browser-harness consumes Runtime events.
   An attached remote-debugging client remains fundamentally detectable by other means.

Net: defeats heuristic/weak-ML detectors and the event-rate signal. The coalesced-events and
screenX tells mean a top-tier ensemble inspecting CDP input fidelity can still identify the
session; full parity needs a patched Chromium, out of scope for this pure-Python layer.

## Backward compatibility

Core primitives (`click_at_xy`, `type_text`, `scroll`, `press_key`, `wait`) are untouched. The
`human_*` verbs are additive and opt-in. New optional kwargs (`human_click(..., width=)`,
`human_wait(..., drift=)`, `human_session(..., fresh=)`) default to backward-compatible behavior,
except `human_wait` now emits bounded idle drift by default (`drift=True`); pass `drift=False` to
restore a dead sleep.

## Public API

`human_session(pacing="paced", fresh=False)` · `human_navigate(url)` · `human_move(x, y, width=None)` ·
`human_click(x, y, button="left", width=None)` · `human_type(text, profile="skilled", mode="semantic")` ·
`human_scroll(x, y, distance=3000, direction="down", device="trackpad")` · `human_wait(base=1.0, drift=True)`

Config tables (`_PACING`, `_TYPING_PROFILES`) and `_HumanSession` are underscore-private (not exported
into the core helper namespace). Session state (cursor / click-bias / tremor-orientation) persists
across separate `browser-harness -c '...'` invocations via a per-`BU_NAME` state file (atomic write,
TTL `_SESSION_TTL`=600s).
