# Residual CDP-input tells — research, decision, and plan

**Date:** 2026-05-29 · **Status:** decided (no fork) · scope: the human-behavior-sim layer.

Two behavioral tells were flagged as "not fixable from JS/CDP":
- **T1** — `PointerEvent.getCoalescedEvents()` is empty for CDP-injected mouse moves.
- **T2** — `screenX==clientX` (no window/desktop offset) on CDP-injected mouse events.

A 6-lens investigation (Chromium source + fingerprinting literature + prior-art repos) **reversed
the problem**. Conclusions, with the evidence that drove them:

## Findings

**T2 is already fixed upstream.** crbug 40280325 (`Input.dispatchMouseEvent` set screen==viewport)
was fixed via `ConvertWidgetPointToScreenPoint` in `content/browser/devtools/protocol/input_handler.cc`,
shipped in **Chrome 142 (Oct 2025)**. The `cdp-patches` library was archived the same month ("no
reason to use this anymore"). On any current Chrome, T2 needs no mitigation. The cross-origin-iframe
variant may not be fully covered — measure if a specific target matters.

**T1 is theoretical, not deployed.** No confirmed production use of `getCoalescedEvents()` length
checks was found across Cloudflare, DataDome, Akamai, PerimeterX/HUMAN, or Kasada in reverse-engineered
live anti-bot JS — it is a researcher-documented signal, not a shipped one. Fixing it requires a
Chromium binary patch (`third_party/blink/.../pointer_event_manager.cc`); CDP `Input.dispatchMouseEvent`
injects via `RenderWidgetHostImpl::ForwardMouseEvent`, bypassing the compositor coalescing queue.

## Approaches considered

| Approach | T1 | T2 | real profile | macOS | cost | verdict |
|---|---|---|---|---|---|---|
| **upstream Chrome ≥142** | ✗ | ✅ | kept | — | 0 | **closes T2 for free** |
| CDP `Input.synthesize*` | ✗ | n/a | kept | ok | low | produces touch/wheel, not pointermove — useless for moves |
| **OS injection (CGEvent)** | ✅ | ✅ | kept | hard | med | real events; needs foreground + moves cursor (sparingly) |
| Frida runtime hook | — | — | **broken** | **no** | huge | **rejected**: `__RESTRICT` blocks DYLD_INSERT; re-sign breaks keychain; SIP off unacceptable; arm64e PAC |
| Chromium fork | partial | ✅ | **broken** | hard | huge | **rejected**: profile conflict + ~1-3 dev-days per 4-week Chrome release |
| cdp-patches (OS, both) | ✅ | ✅ | kept | **n/a** | med | no macOS Quartz backend; archived |

## Decision

- **Do not fork Chromium and do not Frida-hook.** Cost ≫ benefit for a personal ethical-use tool;
  both destroy the real-profile value prop on macOS.
- **T2:** rely on upstream (Chrome ≥142). Verify, don't assume.
- **T1:** accept as a documented residual. It is not deployed in production. Closing it would cost a
  fork or a foreground-stealing OS-injection path — not justified until a real target is shown to check it.
- Higher-ROI work than T1/T2: behavioral timing entropy, event ordering, `pointerrawupdate`. (Runtime.enable
  is already dropped at the daemon.)

## Plan

**Phase 0 — measure, not guess (DONE, 2026-05-29).**
`human_selftest()` + `chrome_version()` in `agent_helpers.py` instrument the live page while driving
real `human_*` input and report, for *your* Chrome: T2 (screenX vs clientX delta), T1
(getCoalescedEvents length), delivered pointer-event rate (~60 fast path / ~30 fallback), isTrusted.
Run on a normal http(s) page:
```bash
browser-harness -c 'new_tab("https://example.com"); wait_for_load(); import json; print(json.dumps(human_selftest(), indent=2))'
```

**Phase 0 result — measured 2026-05-29 on the live machine (Chrome 148.0.7778.181):**
- **T2 screenX: NOT exposed** — screen-vs-client delta = 121px. The upstream fix is live; no action.
- **T1 coalesced: EXPOSED** — getCoalescedEvents max = 1 (CDP bypass confirmed on Chrome 148; matches research).
- isTrusted = true. Delivered pointer rate = **~48-56Hz** (median inter-move; server-side fast path
  verified active — `dispatch_input_sequence(...)` returned `{ok:True, count:2}` on a fresh daemon
  against real Chrome — ~18-21ms/event, up from the ~28Hz baseline).
- **Conclusion CONFIRMED by measurement:** the ONLY exposed tell (T1) is the one with zero production
  deployment → no fork, no OS-injection. Phases 1 and 2 are NOT triggered.
- Selftest polish: the verdict is now derived from the deterministic move stream (40+ events/run);
  the rate uses the **median** inter-move interval (the prior `(n-1)/span` swung 19-41Hz because it
  counted the gaps between the move/move/click trajectories). A catch-all probe verified **human_click
  fires a full, correct chain** (pointerdown/mousedown/pointerup/mouseup/click) — so it really clicks;
  the selftest's own click capture is best-effort/informational and never gates the verdict.
- Optional future tune: subtract estimated WS send time from each delay to lift ~50Hz toward ~60Hz —
  low value while T1 (coalesced) betrays CDP regardless of rate.

**Phase 1 — T2 remediation (conditional).** Only if the selftest shows T2 exposed (Chrome <142):
update Chrome (the free, undetectable fix). A JS getter override is detectable (toString/worker) — avoid.

**Phase 2 — T1 OS-injection mode — IMPLEMENTED 2026-05-30 (opt-in, macOS).**
`human_click_os(x, y)` / `human_move_os(x, y)` post real Quartz `CGEvent`s (lazy pyobjc import; the core
stays pure-stdlib) so the page sees genuine coalesced events + correct screenX + isTrusted. Pipeline:
capability gate → foreground the browser (`BH_BROWSER_APP`; refuses if the wrong app is frontmost) →
client→screen map → display-bounds check (refuses off-screen / wrong monitor) → Fitts/Bezier trajectory of
real moves at ~125Hz (to trigger compositor coalescing) → cursor-arrival verify (refuses if it did not
move = Accessibility not granted) → click with `kCGMouseEventClickState=1`. The three-layer guard
(frontmost / display-bounds / cursor-arrival) means it never posts a blind real click.
**Validated:** 30 hermetic tests (mocked Quartz) + `os_calibrate()` run LIVE returned error_px [0.0, 0] —
the client→screen mapping matches the browser's reported screenX/screenY EXACTLY on the primary display, so
clicks land where intended. Reviewed across two adversarial passes (APPROVE; the missing clickState,
off-screen, wrong-app, and silent-no-op risks were caught and fixed).
**Not yet exercised live:** the real CGEvent path needs `pip install pyobjc-framework-Quartz` into the
browser-harness env + Accessibility granted to the terminal/python; then `os_selftest()` measures whether
`getCoalescedEvents() > 1` actually results (the gated proof). Multi-monitor mapping is unvalidated
(os_calibrate only covered the primary display). COST stands — foreground + physical-cursor move → reserve
for the rare detection-sensitive click; keep CDP (`human_click`) for navigation/reading/bulk. The private
SkyLight `SLEventPostToPid` (cursor-stationary, background) is fragile/unbound — not pursued.

**Phase 3 — Chromium fork. Rejected** (see table). Recorded only so the decision isn't relitigated.
