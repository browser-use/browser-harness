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
- isTrusted = true. Delivered pointer rate = **41Hz** (server-side fast path verified active:
  `dispatch_input_sequence(...)` returned `{ok:True, count:2}` on a fresh daemon against real Chrome;
  ~24ms/event = 16ms delay + WS send latency, up from the ~28Hz baseline).
- **Conclusion CONFIRMED by measurement:** the ONLY exposed tell (T1) is the one with zero production
  deployment → no fork, no OS-injection. Phases 1 and 2 are NOT triggered.
- Minor: the probe's click-capture returned 0 (diagnostic gap, not a finding — the 36-move stream
  supplied every metric). Optional polish: also capture `mousedown` / lengthen the settle.
- Optional future tune: subtract estimated WS send time from each delay to lift 41Hz toward ~60Hz —
  low value while T1 (coalesced) betrays CDP regardless of rate.

**Phase 1 — T2 remediation (conditional).** Only if the selftest shows T2 exposed (Chrome <142):
update Chrome (the free, undetectable fix). A JS getter override is detectable (toString/worker) — avoid.

**Phase 2 — T1 OS-injection mode (on the shelf; build only if a confirmed target checks coalesced).**
Scoped `human_click_os(x, y)` using pyobjc Quartz `CGEventPost` so the click is a real OS event
(real coalescing + screenX + isTrusted). Design: resolve the Chrome window's screen rect
(`CGWindowListCopyWindowInfo`), map viewport→screen, foreground-activate, post down/up, optionally
restore. Constraints: TCC Accessibility grant; foreground + physical-cursor move (so reserve it for the
rare detection-sensitive click; keep CDP for navigation/reading/bulk). The private SkyLight
`SLEventPostToPid` (cursor-stationary, background) is fragile/unbound — not pursued.

**Phase 3 — Chromium fork. Rejected** (see table). Recorded only so the decision isn't relitigated.
