# ai-boost (Shopify embedded app) — QA notes

Dev store: `ai-boost-test.myshopify.com`. Admin app: `https://admin.shopify.com/store/ai-boost-test/apps/ai-boost/app`.
Codebase: `~/Documents/Claude/projects/ai-boost` (Remix admin app under `apps/server`, storefront widget under `packages/storefront`, rule engine under `packages/rules`).

## Structure

- Admin pages: Popups list (`/app/popups`), popup editor (`/app/popups/:id` and `/app/popups/new`), Coupons (`/app/coupons`), Videos, Setup.
- The whole admin app is a **cross-origin iframe** embedded in `admin.shopify.com`: `iframe.src` points at `https://ai-boost-three.vercel.app/app/...` (the actual Remix app, deployed on Vercel). Confirm with `iframe_target("ai-boost-three.vercel.app")`.
- **The outer `admin.shopify.com` tab URL does NOT update on the embedded app's client-side (Remix/React Router) navigation.** `list_tabs()` / `page_info()` / `goto_url()` only see the outer Shopify URL, which stays frozen at whatever the iframe's *first* load was (e.g. `/app/popups`) even after the app SPA-navigates to `/app/coupons/new` inside the iframe. **Always check real location via `js("location.href", target_id=iframe_target(...))`, never via `page_info()`, when working inside this app.**
- Storefront debug mode: `window.__AI_BOOST__.debug` (boolean) and `window.__AI_BOOST__.debugApi` — `.state()` returns the full live detector state (`cart`, `checkout`, `visitor`, `liveCart`), `.evaluate` and `.gates`/`.forceFire` are NOT on the public `debugApi` (those belong to the on-page debug **overlay** component's internal `OverlayDeps`, mounted separately — see below). Console also logs `[AI Boost] evaluate →` on every rule re-evaluation when `debug` is on.
- The visual debug overlay (`<ai-boost-debug>` custom element, shadow DOM) is a separate lazy-loaded bundle (`aiboost.debug.js`), not always mounted just because `debug:true` — it seems to persist across page loads only if something (dev toggle / URL param, not yet identified) explicitly mounted it earlier in the browser profile. On a *fresh* page load it is often absent even with debug on; `window.__AI_BOOST_DEBUG__` is the mount function if you need to force it.

## Interaction gotchas (Polaris admin UI, inside the iframe)

- **Bulk Delete (and any action guarded by a real confirm)** on the Popups list uses a **native `window.confirm()`**, not a Polaris `<Modal>`. `click_at_xy` on the confirming button will time out waiting on `Input.dispatchMouseEvent` because the native dialog freezes the renderer thread. Either use CDP `Page.handleJavaScriptDialog` (reactive) or stub before clicking:
  ```python
  js("""
  window.__dialogs__=[];
  window.confirm=m=>{window.__dialogs__.push(String(m));return true;};
  """, target_id=tid)
  ```
  Read `window.__dialogs__` after to confirm the exact copy shown (useful for QA — the message includes real counts, e.g. `"Delete 4 popups? Claims keep their revenue, but any experiment history is removed."`).
- The Popups list `IndexTable` renders **two "More actions" buttons** (`aria-label="More actions"`) — a `sizeMedium` one and a `sizeMicro` one, likely a normal + sticky/condensed bulk-bar pair. Only the sticky/micro one (2nd match, i.e. `document.querySelectorAll("button")[6]` in a typical DOM order) reliably opens the `Polaris-ActionList` popover with the real bulk Duplicate/Delete menu items in this app; the other one may not render a populated menu. If a coordinate click on the "..." button doesn't produce visible `Polaris-ActionList__Item` elements in `document.querySelectorAll("*")` text search, try the *other* "More actions" button.
- Prefer driving this admin app via `iframe_target()` + `js()` (real DOM `.click()` on precisely identified elements, or dispatched `MouseEvent`s) over `click_at_xy` coordinate clicks. This session repeatedly hit tab-focus drift (see below) that made coordinate clicks land on unrelated background tabs; DOM-level clicks scoped to the iframe's own CDP session target are immune to that.
- Row checkboxes / bulk-select bar: clicking a row checkbox switches the list header into a bulk-actions bar (`"N selected"` + Turn on / Turn off / More actions). Standard Polaris `IndexTable` behavior, nothing app-specific.

## Session-wide tooling gotcha: tab-focus drift with many open tabs

In a Chrome profile with a large number of tabs open (seen here: ~80), `switch_tab(targetId)` reliably re-attaches the CDP session (confirmed via `js("location.href")` on that target succeeding), but:

- `capture_screenshot()` can intermittently return a **stale/cached frame** from a different tab, or from before the switch fully applied. Don't trust a screenshot alone to confirm which tab an action landed on — cross-check with `js("location.href")` on the specific target.
- `click_at_xy()` / synthetic input occasionally lands on a **different, previously-active tab** (observed repeatedly snapping to an unrelated storefront tab mid-sequence) even right after a confirmed-correct `switch_tab()` + `page_info()` check. Root cause not fully isolated (possibly OS-level frontmost-window vs CDP-target mismatch when many tabs/windows exist). Workaround that worked reliably: do everything through `iframe_target()` + `js()` DOM manipulation instead of coordinate clicks whenever the target is inside an iframe or a Polaris/React app where elements can be queried and `.click()`'d directly.
- A tab that is not the genuine OS-visible/foreground tab has **`document.visibilityState === 'hidden'`**, and Chrome throttles `IntersectionObserver` and `requestAnimationFrame` callbacks to zero in that state — confirmed with a from-scratch minimal `IntersectionObserver` test (never fired, on a plain freshly-inserted div, no app code involved). Overriding `document.visibilityState` via `Object.defineProperty` only fools JS reads of the property; it does **not** un-throttle the renderer's actual rendering pipeline (rAF still never fires). If you need to test IntersectionObserver-driven behavior (e.g. "element scrolled into view for N seconds" triggers), you cannot reliably do it against a backgrounded tab in a many-tab session — either close down to a small number of tabs so the target tab is genuinely frontmost, or fall back to a **unit test with a fake `IntersectionObserver`** against the real source (see below) instead of a live browser assertion.
- `Emulation.setEmulatedMedia` (used to force `hover:none`/`pointer:coarse` for mobile testing) does **not** survive a `goto_url()` / `Page.navigate()` to the same or a new document — it silently reverts to the real desktop capabilities on the next page load. It **does** survive `cdp("Page.reload")`. If you must navigate (not just reload) while emulating touch/no-hover, re-apply `Emulation.setEmulatedMedia` immediately after the navigation completes and before any code that reads `matchMedia` runs (i.e., before the widget's `CheckoutDetector.start()` fires on page load) — otherwise the app will silently take the desktop code path despite `Emulation.setDeviceMetricsOverride({mobile:true})` still being active for viewport *size* purposes. `width`/`height`/`mobile` device-metrics themselves persisted fine across navigation in this session; only the explicit media-feature override needed re-applying.

## Testing IntersectionObserver-gated storefront logic without a live browser

When the live tab can't be trusted to actually render (backgrounded, per above), and the logic under test is a small deterministic unit (e.g. `packages/storefront/src/detect/checkout.ts`'s mobile viewport-dwell fallback), it's faster and more reliable to write a throwaway Vitest spec next to the existing `*.test.ts` file, using the same `matchMedia` stub pattern already in `checkout.test.ts`, plus a minimal controllable `IntersectionObserver` fake:

```ts
class FakeIO {
  static instances: FakeIO[] = [];
  cb: IntersectionObserverCallback;
  observed: Element[] = [];
  constructor(cb: IntersectionObserverCallback) { this.cb = cb; FakeIO.instances.push(this); }
  observe(el: Element) { this.observed.push(el); }
  disconnect() {}
  trigger(isIntersecting: boolean) {
    this.cb([{ isIntersecting, target: this.observed[0] } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
  }
}
// beforeEach: vi.stubGlobal('IntersectionObserver', FakeIO)
```

This exercises the *real* shipped source directly (import from `./checkout.js` etc.), sidestepping both the browser occlusion problem and jsdom's total lack of a real `IntersectionObserver`. Vitest config here is `include: src/**/*.test.ts`, so a scratch spec must live under `packages/storefront/src/**` to be picked up — copy it in, run `npx vitest run <path>`, then delete it; don't leave scratch specs in the tree.

## Known-good findings (as of this session's QA pass)

- `packages/storefront/src/detect/checkout.ts`: mobile fallback (`attachMobileFallbacks` → `observeCheckoutButton` viewport-dwell timer + `attachTabHidden` visibilitychange exit-intent + `pagehide` exit-intent) is correctly gated behind `hasHover` and verified working via both a live browser (`visibilitychange`→hidden path) and a from-scratch Vitest spec against the real source (all paths: viewport-dwell fire, viewport-dwell non-fire on early exit, no hover-listener leak on mobile, `pagehide` exit-intent, `visibilitychange` exit-intent, late-rendered-button re-attach via `cart:open` retry).
- **Gap**: `packages/storefront/src/detect/checkout.test.ts` has zero coverage of the mobile-only code paths (`attachMobileFallbacks`, `observeCheckoutButton`, `VIEWPORT_DWELL_MS`, `attachTabHidden`) despite the file's own top-of-suite comment noting the mobile fallback "could not fire at all for several rounds and nothing noticed." Worth a real PR adding permanent tests for this (the scratch spec above is a starting point).
- `popup.ts` popup component CSS is viewport-safe by design: `width:352px;max-width:calc(100vw - 32px)` (modal) and `width:min(520px,100vw)` (sheet variant) — no clipping expected on narrow viewports, confirmed visually at 390×844.
- The merchant-only debug overlay (`<ai-boost-debug>`, fixed bottom-left, ~300px wide) visually overlaps the bottom of the cart drawer (subtotal/checkout button) on a 390px-wide viewport. Not shopper-facing (gated behind debug mode) so low severity, but worth a layout tweak (e.g. collapse/reposition on narrow screens) since a merchant testing on their own phone would hit this.

### Coupon lifecycle (edit / archive / percentage guard) — verified end-to-end

Tested by editing a live ACTIVE coupon's value, and by creating+activating+archiving a
throwaway coupon at an extreme 100% value, then cross-checking the *real* Shopify
Discounts admin page (`/store/<shop>/discounts`, same-origin, plain `js()`/top-level DOM
works fine there — no iframe needed) rather than trusting this app's own DB/UI.

- **Edit on an ACTIVE coupon is allowed by the UI** (no "locked while active" restriction) and
  correctly goes through `discountCodeBasicUpdate` (`runSync`'s `update` action in
  `apps/server/app/lib/coupon-sync.server.ts`), not a destructive recreate. Verified: edited
  value 10→15 on a live ACTIVE coupon, reloaded (full page reload, new iframe target), value
  persisted in this app's DB, and Shopify's own Discounts list showed the flag text update to
  "15% off ..." — not 1500%, confirming `toShopifyPercentage()`
  (`apps/server/app/shopify/discounts.server.ts:34`, `percent/100`, bounds-checked 0<percent≤100)
  is exercised correctly on the update path too, not just create.
- **Percentage guard holds at the boundary**: created+activated a coupon with `value=100`
  (max allowed by the Zod schema, `apps/server/app/lib/coupon-form.ts`'s
  `value <= 0 || value > 100` check). Shopify's Discounts page correctly showed "100% off ...",
  not 10000%. Nothing here reproduces the historical 10x bug class — both the client-side Zod
  bound and the server-side `toShopifyPercentage()` bound independently prevent it.
- **Archive → `discountCodeDeactivate`, not delete, confirmed live**: archiving a coupon flips
  this app's status to `ARCHIVED` (excluded from `listActiveCoupons()`'s `status: 'ACTIVE'`
  filter in `apps/server/app/models/coupon.server.ts:58` — that's the filter that actually
  matters for whether the storefront claim endpoint will hand out the code, *not* the admin
  list UI, which shows all statuses unfiltered with no tab/segment control). The underlying
  Shopify discount is **not deleted** — same `gid://shopify/DiscountCodeNode/...` id persists
  on the Discounts admin page, just with its Status column changed to **"Expired"** (that is
  Shopify's own UI label for a code discount that has been deactivated via
  `discountCodeDeactivate` — do not confuse this with a discount that had an actual `endsAt`
  in the past; same visual label, different cause).
- **Archived coupons cannot be deleted through this app's UI by design**: `canDeleteCoupon()`
  (`apps/server/app/lib/popup-form.ts:262`) requires `status === 'DRAFT'` (and zero claims).
  An archived throwaway coupon is therefore stuck (intentionally) — the only way back to a
  deletable state would be bypassing the guard, which defeats the point of the guard. If you
  create a throwaway coupon for QA and archive it, **do not expect to delete it afterward**;
  either leave it archived (harmless, inert, excluded from active listing/claims) or use a
  DRAFT coupon for any test that ends in deletion instead of activate→archive→delete.
- No status filter/tabs exist on the Coupons list (`/app/coupons`) as of this session —
  `listCoupons()` (the loader backing `app.coupons._index.tsx`) returns every status
  unfiltered, so ARCHIVED and ACTIVE coupons render in the same flat table. Don't go looking
  for an "Active" tab to verify the archive-hides-it behavior — check `listActiveCoupons()`'s
  server-side filter conditions or the storefront claim behavior instead.
