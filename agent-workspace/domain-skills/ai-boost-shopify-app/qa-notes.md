# AI Boost (Shopify app) — QA notes

Coupon popup + video guide widget app. Admin lives at `/store/<shop>/apps/ai-boost/app`,
backed by `ai-boost-three.vercel.app` (a Remix app embedded via App Bridge iframe).
Storefront widget script: `aiboost.core.js` from
`https://cdn.shopify.com/extensions/<ext-id>/ai-boost-33/assets/aiboost.core.js` (unminified
enough to `grep` — worth downloading with `curl` when you need ground truth instead of
guessing from screenshots).

## Dashboard/Analytics: there is no separate `/app/analytics` route

`/app` (the root, "Dashboard") IS the analytics page — it renders "Attributed revenue" /
"Orders recovered" / "Codes claimed" / "Purchases per claim" summary tiles plus a
"Shopper journey" funnel widget (Visited → Opened cart → Considered checkout → Saw offer
→ Claimed code → Applied code → Purchased), each stage with a step-over-step % and a
%-of-top row. No per-popup/per-coupon breakdown table lives on this page — the funnel is
shop-wide aggregate only. (A caveat string on the widget — "Beyond 90 days these come
from daily totals, so they can't be broken down by popup" — implies per-popup breakdown
exists on the Popups pages instead, not verified here since QA stayed scoped to the
dashboard to avoid colliding with concurrent agents on Popups/Coupons.)

Range control is a plain native `<select class="Polaris-Select__Input">` (same
native-setter trick as the placement `<select>` documented below) with options "Last 7
days"/"Last 30 days"/"Last 90 days"/"Last 12 months", values `7d`/`30d`/`90d`/`365d`. It
is NOT decorative — changing it updates `window.location.search` to `?range=<val>` and
triggers a real refetch, confirmed via `Network.enable` (a matched pair of `GET
/app?...range=<val>` requests fires on change). **There is a load-lag of ~2-4s after
firing the `change` event** before `document.body.innerText` reflects the new range —
reading immediately after `dispatchEvent` can catch a stale/mid-transition render (saw
the "Last 90 days" label + zeroed funnel still showing after setting the select back to
`30d`, then correct on a later read ~3s on). Always re-read after a few seconds' wait,
don't trust the first snapshot post-change.

Two exportable CSVs, fetchable directly from inside the iframe's authenticated `fetch()`
context (fast ground-truth source, no DOM scraping needed):
- `GET /app/export/claims?range=<7d|30d|90d|365d>` → CSV
  `Claimed,Coupon,Code,Status,Version,Attribution,Order,Order total,Redeemed` — one row
  per coupon claim, matched exactly to the dashboard's "Codes claimed" / "Orders
  recovered" / "Attributed revenue" tiles in a spot check.
- `GET /app/export/performance?range=<...>` → CSV header
  `Day,Event,Popup,Version,Count` — **observed returning header-only (0 data rows, 200
  OK) across all four range values**, on a shop where the same-page dashboard funnel
  simultaneously showed real non-zero Visited/Opened-cart/etc. counts for the identical
  range. Worth re-checking on a future pass — looked like a genuine data-source
  divergence (export query vs. dashboard aggregation reading from different places or
  using mismatched event-name filters), not a range-param or timing artifact (checked
  status 200 + exact byte length across `7d/30d/90d/365d`, all identical 31 chars).

Also observed: at `range=90d` and `range=365d`, the funnel's early stages (Visited
through Applied code) all render `0`, but the terminal "Purchased" stage still renders
`1` (matching the one known real order in this shop) — i.e. a stage further down the
funnel shows a *higher* count than every stage upstream of it, breaking the expected
monotonic funnel invariant. Reproduced twice with a full 4s settle each time, so not a
render-lag artifact. Consistent with the "beyond 90 days" caveat text describing a
different (daily-totals) data path for the upper funnel stages that doesn't backfill
correctly, while "Purchased" appears to be sourced from actual order data (unaffected by
the rollup gap). Also: the caveat text "**Beyond** 90 days" visibly displays while
*exactly* 90 days is selected, not just >90d — reads like an off-by-one in the tier
boundary (`>=90d` in code vs. "beyond" implying `>90d` in the copy).

## Admin iframe is genuinely cross-origin

Despite looking like a normal same-origin Remix page, EVERY `/app/...` admin route
(popups list, popup editor, coupons, results, simulate) is `admin.shopify.com` embedding
an iframe at `ai-boost-three.vercel.app` — cross-origin from the top frame. `js()`/
`click_at_xy()` against the top-level page do NOT reach into it. You must:

```python
targets = cdp("Target.getTargets", {})
# find the iframe target whose url contains ai-boost-three.vercel.app and your route
r = cdp("Target.attachToTarget", targetId="<iframe target id>", flatten=True)
sid = r["sessionId"]
cdp("Runtime.evaluate", session_id=sid, expression="...", returnByValue=True)
```

Every full-page reload (`goto_url` on the top frame) creates a brand new iframe target —
you must re-run `Target.getTargets` and re-attach after each reload. The old session_id
goes stale silently (calls will just error/hang), it does not auto-migrate.

Placement `<select>` is a plain native `<select>` (not a Polaris custom combobox) — set it
with the native-setter + `change` event trick, no need to click-and-choose an option:

```js
function setNativeValue(el, value) {
  const proto = Object.getPrototypeOf(el);
  const desc = Object.getOwnPropertyDescriptor(proto, "value");
  desc.set.call(el, value);
  el.dispatchEvent(new Event("change", { bubbles: true }));
}
```

Save button: plain `<button>` with text "Save", find via
`[...document.querySelectorAll("button")].find(b=>b.textContent.trim()==="Save")` and
`.click()` it directly (coordinates are unreliable across screen sizes / scroll position).

## Storefront: `window.__AI_BOOST__` debug surface

When the merchant has debug mode on, `window.__AI_BOOST__.debug === true` and
`window.__AI_BOOST__.debugApi` exposes `{state(), evaluate(), openMs(), fingerprint(),
clientId, flush()}`. `debugApi.evaluate()` returns exactly what the trigger-rule engine
would return, e.g. `{fire:false, reason:"condition_failed", failedAt:"conditions.all.cart_closed"}`
or `{fire:true, score:1.75, delayMs:2977, matched:[...]}`. Much faster than reading the
on-page "AI Boost" debug HUD (bottom-left `<div>`) via screenshots.

**Known flakiness**: `debugApi.evaluate` / `debugApi.state()` can silently go stale or
disappear (`typeof ... === "undefined"`) after certain page-lifecycle events — observed
after a `cart:close` → config re-fetch cycle, and unreproducibly on some fresh page loads
even though the real internal engine (visible via `console.info("[AI Boost] evaluate →", ...)`
logs, which fire on every internal poll tick) keeps working correctly. If `debugApi` looks
frozen/stale, do NOT trust it — cross-check with:
- `localStorage.getItem("aiboost:visitor")` → `impressionsThisSession`/`impressionsAllTime`
  (ground truth for "did it actually fire")
- Console log scraping via CDP `Runtime.consoleAPICalled` events for the live
  `"[AI Boost] evaluate →"` info logs (these come from the real internal `evaluateNow()`,
  not the debug binding)
- A screenshot of `document.querySelector("[id^=ai-boost-popup]").shadowRoot`.

This looks like a real (minor, debug-tooling-only) bug worth flagging upstream: the
`debugApi.evaluate` closure reference goes stale independently of the live engine.

## Reproducing trigger conditions programmatically

The default popup ("Cart saver") in this shop needs, in order: cart open ≥20s, checkout
button hovered ≥120ms dwell, cart closed and stays closed ≥3s (all ANDed).

- **Open cart**: click the theme's own cart-drawer trigger via JS `.click()` on
  `document.querySelector('a[href="#CartDrawer"], a[href*="/cart"], cart-icon-bubble')
  ?.closest("a")`. Raw CDP `Input.dispatchMouseEvent` at the icon's coordinates is
  unreliable in a shared/contended daemon session (see gotcha below) — prefer the JS
  `.click()` call, it bypasses hit-testing/coordinate drift entirely.
- **Linger ≥20s**: cart-open duration is wall-clock, not interaction-based — just wait,
  but see the keepalive note below.
- **Hover checkout with real dwell**: the tracker only fires on `pointerover`/`pointerout`
  (NOT `mouseover`/`mouseenter`/`mousemove`), and computes dwell as
  `Date.now() - hoverStart` **measured at `pointerout`** — you must dispatch both events
  with a real gap, not just `pointerover` and leave it:
  ```js
  el.dispatchEvent(new PointerEvent("pointerover", {bubbles:true, clientX, clientY, pointerType:"mouse"}));
  await new Promise(r => setTimeout(r, 400)); // > their internal 120ms minimum
  el.dispatchEvent(new PointerEvent("pointerout", {bubbles:true, clientX, clientY, pointerType:"mouse"}));
  ```
  Minimum dwell is 120ms (`Xe=120` in the minified bundle) — 400ms gives comfortable margin.
- **Close cart**: `document.querySelector("cart-drawer").close()` (it's a real custom
  element with a `.close()` method) is far more reliable than clicking whatever button
  looks like a close (X) icon — an `aria-label`-based `button.click()` sometimes closes a
  *different* control and leaves the debug-reported `isOpen` stuck `true` even though the
  drawer visually closed.
- After close, condition needs `delaySeconds: 3` to actually elapse before it fires — poll
  `debugApi.evaluate()` (or console logs) every ~1s for a few seconds after closing.

Session/frequency reset for repeat testing (frequency cap is `maxPerSession: 1` by
default): clear `localStorage` keys `aiboost:visitor`, `aiboost:viewed`,
`aiboost:cart:seen`, `aiboost:cid` and `sessionStorage` key `aiboost:sid`, then reload.
Don't use `Storage.clearDataForOrigin` — it also nukes the `storefront_digest` password-gate
bypass cookie on password-protected dev stores, and you'll be locked out at `/password`
with no known password to get back in. Clear only the four `aiboost:*` keys.

## Popup DOM: shadow root, not light DOM

The rendered popup lives at `document.getElementById('ai-boost-popup-<popupId>')` — a
plain `<div>` with `.shadowRoot` attached (not detectable by looking at `.children`,
which is always empty in light DOM). Pierce it:
`container.shadowRoot.querySelector(".card")` — class is `card center|sheet|toast` per
placement (`CENTER_MODAL→center`, `BOTTOM_SHEET→sheet`, `CORNER_TOAST→toast`), plus a
`.on` class once the open animation should be visible. Close (X) button is
`shadowRoot.querySelector("button.x")`.

Placement CSS confirmed correct at the source level (all three read as fixed-position
with `opacity/transform` transitions, 260ms `cubic-bezier(.32,.72,0,1)`, disabled outright
under `@media(prefers-reduced-motion:reduce){.card,.scrim{transition:none!important}}` —
also applies to the separate video-widget `.wrap`). Toast has no `.scrim` (by design,
correct for a non-modal toast) — don't expect a backdrop-click dismiss path for it.

Claim button: on click sets `disabled=true` and `textContent="…"` while awaiting
`onClaim()` — a plain ellipsis, no spinner. On success it swaps `formEl.textContent=""`
and appends the code-reveal DOM instantly (`copy` button + "Apply & go to cart" button) —
there is **no cross-fade/transition** between the email-capture form and the code reveal,
just an instant DOM replace. Worth flagging as a minor UX polish item, not a functional bug.

## Shared-daemon environment hazard (not app-specific, but bit this session hard)

This harness's default `BU_NAME="default"` daemon is commonly shared across many
concurrent unrelated automation tasks against the *same* real user Chrome (observed:
LinkedIn scraping, job-application bots, other Shopify store QA, etc. all running at once
in this environment). Consequences that cost real time on this task:

- `click_at_xy()`, `capture_screenshot()`, and any bare `cdp(...)` call **without an
  explicit `session_id`** silently use the daemon's shared, globally-mutable "last
  attached session" pointer. A concurrent process's `switch_tab()` call between your own
  calls will silently redirect your next click/screenshot to *their* tab. This produced
  real, if harmless, side effects here (typed text into an unrelated draft admin page).
  **Always capture the `session_id` returned by `switch_tab()` and pass it explicitly on
  every subsequent raw `cdp(...)` call** (`Input.dispatchMouseEvent`,
  `Page.captureScreenshot`, `Runtime.evaluate`, etc.) rather than relying on the
  convenience wrappers' implicit "current session".
- Watch for an unexpected `dialog` key in a `page_info()`/bare-`cdp()` response — that's
  the daemon reporting a **different tab's** unhandled JS `confirm()`/`alert()`, not
  yours. Don't dismiss it; it's not your dialog to accept or cancel. Just switch to your
  own tab with an explicit session and continue — it won't block your own session-scoped
  calls.
- Occasional `TimeoutError: timed out` mid-script even on a healthy connection — appears
  to be genuine contention on the daemon's IPC socket under concurrent load, not a stale
  session. Retrying after a short pause reliably recovers; don't assume the tab/session
  is dead.
- A tab's viewport/device metrics (`window.innerWidth/innerHeight`, mobile vs desktop) can
  change out from under you if another process calls
  `Emulation.setDeviceMetricsOverride` on a target you're both using. Don't assume desktop
  viewport — check `window.innerWidth`/`innerHeight` right before anything
  viewport-sensitive (positioning assertions, responsive screenshots).
- With 2+ other agents in this app simultaneously, `new_tab(...)` on `/apps/ai-boost/app`
  followed later by `page_info()` can return a URL that has silently changed out from
  under you (observed: my own top-level tab jumped to a coupon-detail page, then later to
  `/password`, without me navigating it) — the daemon's "current tab" pointer is getting
  reassigned by someone else's `switch_tab()`. Likewise `iframe_target("ai-boost-three.vercel.app")`
  is a substring match with **no guarantee it's scoped to your own top-level tab** when
  multiple agents each have an `ai-boost-three.vercel.app` iframe open — it can hand you
  a completely different agent's session (e.g. their coupon-detail iframe when you asked
  for the dashboard). The reliable fix: `cdp("Target.getTargets", {})`, filter to the
  exact top-level `/app`-path URL you expect, keep only entries with `"attached": True`
  (via a follow-up `Target.getTargetInfo` — the raw `getTargets` list doesn't include
  `parentId`/`attached` by default, `getTargetInfo` per-target does), then match candidate
  iframe targets to your top target by `targetInfo.parentId == <your top targetId>`
  (confirmed via `Target.getTargetInfo`, exact-equality check, not substring). Do this
  fresh — re-derive both IDs — any time you suspect a collision, and stop calling
  `new_tab`/`page_info`/`iframe_target` again once you have verified explicit target IDs;
  drive the rest of the session purely through `cdp(..., session_id=<verified sid>)`.
- Simplest reliable variant of the above, confirmed working end-to-end: filter
  `Target.getTargets` results by `browserContextId` (from your own top-level tab's
  `Target.getTargetInfo`) *and* URL substring together. Every tab you `new_tab()` yourself
  shares one `browserContextId` for the whole session; other agents' tabs (even on the
  identical `ai-boost-three.vercel.app` origin) sit in a different `browserContextId`, so
  this one filter is enough to isolate "my iframes only" without needing `parentId`
  round-trips. After every top-frame reload/navigate, the old iframe target dies and a new
  one appears — re-run the filtered `getTargets` and pick the target whose URL segment
  wasn't present in the previous listing (or just re-derive fresh; don't cache iframe
  target IDs across a navigation).

## UNIQUE_PER_CLAIM coupon strategy — confirmed behavior (as of this session)

There is a real, working `codeStrategy` radio in the coupon editor
(`/app/coupons/<id>`): "One shared code" (`SHARED`) vs "A unique code per shopper"
(`UNIQUE_PER_CLAIM`), plus a `codePrefix` field ("Unique codes look like
PREFIX-A7K2M9") and a `sharedCode` fallback field ("Used if Shopify is unreachable when a
shopper claims"). A pre-existing coupon named **"Unique Code Test"**
(`/app/coupons/1b265964-f380-44a6-bf9d-8526fdb8652c`) is already configured with
`codeStrategy: UNIQUE_PER_CLAIM`, `codePrefix: "UNIQ"`, `sharedCode: "UNIQFALLBACK"`, and
is wired to the "Cart saver" popup. Use this one for any future UNIQUE_PER_CLAIM testing
rather than creating a new coupon.

**Claim path is confirmed genuinely unique per shopper** — two claims (two simulated
visitors, frequency cap reset between them) produced two different codes
(`UNIQ-26Y8MCUA`, `UNIQ-2RT26MCJ`), each showing up as its own **separate, distinct
Shopify discount object** in Admin → Discounts (`"Unique Code Test (UNIQ-XXXXXXXX)"`,
one per claim) — not variations of the same underlying discount.

**Important, confirmed-precise finding: the pre-generated code pool (referenced this
session as deferred "Phase 5" work) does not exist yet.** Evidence:
- The claim network request (`POST /apps/ai-boost/v1/claim`, App Proxy route) took
  **~3.8s** end-to-end (`performance.getEntriesByType("resource")` duration) for the
  first claim — far too slow for a DB pool read, consistent with a live synchronous
  Shopify Admin API discount-creation call on the shopper's critical path.
  - Confirmed the same order of magnitude on the second claim.
- Immediately after each claim, a **brand-new discount row appears in Admin → Discounts**
  with the claimed code baked into its title — i.e. the app is calling the Admin API to
  create a new discount code object per claim, not drawing a code from a
  pre-generated/pre-created pool and just recording the assignment. A true pool-backed
  design would not need to create a new Shopify discount object synchronously per claim.
  - There is no "codes remaining in pool" indicator anywhere in the coupon editor UI, which
    is additional (weaker, UI-absence) evidence the pool feature isn't built.
- This matters operationally: it means UNIQUE_PER_CLAIM claims are *not* actually
  insulated from Shopify Admin API latency/outages on the shopper-facing path, contrary to
  the documented intent ("claim path stays a DB read rather than a live Admin API call").
  The `sharedCode` fallback field presumably covers the case where that live call fails
  outright, but does not fix the latency-on-every-claim issue.

**Attribution / redemption tracking is confirmed working correctly end-to-end.** There is
no per-claim redemption UI on the coupon editor page itself (it's a config-only page), and
no dedicated "Analytics" nav item — but the Dashboard (`/app`, nav item "AI Boost" /
Dashboard) shows a funnel (Visited → Opened cart → Considered checkout → Saw offer →
Claimed code → Applied code → Purchased) plus top-line stats (Attributed revenue, Orders
recovered, Codes claimed, Purchases per claim), and there's a same-origin authenticated CSV
export at `GET /app/export/claims?range=30d` (fetch it with `credentials:"include"` from
inside the app iframe's JS context — no need to trigger an actual file download). The CSV
columns are `Claimed,Coupon,Code,Status,Version,Attribution,Order,Order total,Redeemed` and
correctly distinguish `ISSUED` (claimed, never applied to an order) from `REDEEMED`
(matched to a real order via the `orders/create` webhook, with `Order` as a
`gid://shopify/Order/...` id, `Order total` as the actual paid total, and `Attribution:
discount_code`). Confirmed via a live Bogus-Gateway test-mode checkout (card `1`, approved)
that a claimed-and-applied code flips from `ISSUED` to `REDEEMED` with the correct order
total within ~10s of order completion, while a sibling code that was claimed but never
applied to any order correctly stays `ISSUED` forever (good negative control).

## Trigger-engine scoring: NOT a simple AND of 3 conditions (differs from earlier
## understanding in this file)

`debugApi.evaluate()` on this store's actual "Cart saver" popup is weighted-score based,
not a strict boolean AND of `cart_open_duration` / `checkout_hover` / `cart_closed`
(the on-page debug HUD's 3-row checklist is misleading — those rows appear to be a fixed
legacy display that doesn't reflect the coupon's real scoring inputs). Confirmed real
`evaluate()` output shape on a fire: `{"fire":true,"score":2.25,"delayMs":...,"matched":
[{"type":"cart_opened_proactively","score":1},{"type":"has_similar_historical_product",
"score":0.75},{"type":"cart_subtotal_gte","score":0.5}]}`.

**Trap**: dispatching only synthetic `PointerEvent("pointerover"/"pointerout")` on the
checkout button (as previously documented in this file) satisfies `checkout.hovered` and
`checkout.maxDwellMs` correctly in `debugApi.state()`, but is **not sufficient to make the
popup fire** — repeated clean runs (fresh reload, cleared `aiboost:*` keys, cart opened
≥20s, synthetic dwell ≥120ms, cart closed ≥3s) consistently plateaued at
`score:0.75, reason:"score_below_threshold"` and never fired. Switching the hover step to
**real compositor-level mouse movement** (`Input.dispatchMouseEvent type=mouseMoved` into
the button's bounding-rect center, a real ~500ms JS-side sleep, then move back out) made it
fire reliably (`score:2.25`) on the very next attempt, every time. Root cause not fully
diagnosed (plausibly `cart_opened_proactively` or another weighted signal depends on real
mouse-move telemetry the synthetic PointerEvent doesn't generate) — flagged as worth a
second look, but real `Input.dispatchMouseEvent` hover is the reliable repro going forward,
not synthetic PointerEvents.

The on-page debug HUD's green "Force show" button (inside `#ai-boost-debug`'s shadow root)
does **not** appear to actually force-render the popup — clicked it repeatedly with no
popup DOM node appearing (`document.querySelector("[id^=ai-boost-popup]")` stayed `null`).
Either it's non-functional, or it only forces a re-evaluation rather than bypassing the
score gate — worth a dedicated look, not relied on for this session's testing.
