# jetblue / checkout

End-to-end JetBlue (jetblue.com) one-way cash checkout: search -> flight -> cart -> traveler details -> seats/extras -> payment. Verified reachable to payment-entry with test data in ~9 minutes.

## Site map

- Home: `https://www.jetblue.com`
- Search results (deep link, skips home form): `https://www.jetblue.com/booking/flights?from={IATA}&to={IATA}&depart=YYYY-MM-DD&isMultiCity=false&noOfRoute=1&adults=1&children=0&infants=0&roundTripFaresFlag=false&sharedMarket=false&usePoints=false`
- Cart: `https://www.jetblue.com/booking/cart`
- Checkout (all three steps share this URL; tabs rendered as sections): `https://www.jetblue.com/booking/checkout` (titles change: `Traveler Details` -> `Seats & Extras` -> `Review & Pay`)

Deep-linking the search URL is much faster than interacting with the home-page search form (which uses React aria-generated ids and a custom `dot-city-selector` autocomplete).

## Framework

Angular + custom web components (prefix `jb-*`, `dot-*`, `cb-*`). No shadow DOM — everything is in the light DOM, which means standard `querySelector` + coord clicks work. Common components:

- `jb-select` / `jb-select-button` — dropdowns. Open via coord click; options render as `<span>` inside a `jb-flyout`. No `role=option` set; match by `innerText` equality.
- `jb-autocomplete` — text autocomplete (e.g. city). Input id `jb-autocomplete-N-search`.
- `jb-input` / `jb-input-label` — text fields. Input id `jb-input-label-id-N-input`. Label text lives in a sibling `<label>`.
- `jb-radio` — radio buttons (payment method selection).
- `jb-date-picker` — date dropdown.
- `dot-booker-air-form` / `dot-traveler-selector` — larger form blocks.

## Flow & stable selectors

### 1. Search results page

Flight cards are `<jb-card>` elements containing text like `"Core\nOptions from\n$94"`. Click one of these to expand fare options. Selector: `Array.from(document.querySelectorAll('jb-card')).find(c => c.innerText.includes('Core'))` then click its center.

After expansion, three `<button>` elements appear with text exactly `"Select"`. Click one.

### 2. Fare upsell modal

A modal appears with two buttons: `"Select Blue Basic"` and `"Select Blue"`. Click by `innerText` equality. Picking Blue Basic takes you straight to `/booking/cart`.

### 3. Cart page

Single button: `"Continue to checkout"`. Click it -> `/booking/checkout` (Traveler Details).

### 4. Traveler Details

First task: click the button with exact text `"Continue as guest"` (alternative is `Sign in`). This reveals the guest form below.

Form fields (use `document.getElementById`):

- `#jb-input-label-id-3-input` -> First Name
- `#jb-input-label-id-4-input` -> Middle (optional)
- `#jb-input-label-id-5-input` -> Last Name
- `#jb-input-label-id-6-input` (`type=email`) -> Email
- `#radar-address-autocomplete` -> Address line 1 (powered by Radar; pick a suggestion from the autocomplete list — it auto-fills city/state/ZIP)
- `#trip-contact-address-line-2` -> Address line 2
- `#trip-contact-city` / `#trip-contact-postal-code`
- `input[type=tel]` -> Phone (there's only one on the page)

Dropdowns (use `jb-select` matched by first-line `innerText`):

- `Title` (required; options: `Mr/Mrs/Miss/Ms/Dr`)
- `Gender` (options: `Female/Male`)
- `Month` / `Day` / `Year` (DOB) — `Month` options are short (`Jan`, `Feb`, ...); `Year` list is long, scroll the list via `el.scrollIntoView({block:'center'})` on the target span.

**N-index on `jb-input-label-id-N`** shifts as sections render; do not hard-code it without verifying `label` text. First Name may be id-3 on one render, id-8 on another.

Submit: button with text `"Next: Seats & Extras"`.

### 5. Seats & Extras

Fastest path: click the element with exact text `"Skip to Review & Pay"` (it's a `<div>` that acts as a shortcut link). Skips seat selection entirely.

### 6. Review & Pay (payment)

Payment method default: radio `#jb-radio-0` = "Credit or debit card" (already selected).

Visible fields in the parent frame:

- `input[aria-label="Name as it appears on card"]`
- `input[aria-label="Expiration date in mm/yy format"]` (accepts raw `1229` input)

**Card number and CVV are inside cross-origin TokenEx iframes** (this is the critical trap — see below).

## Critical trap: TokenEx OOPIF iframes for PAN/CVV

Iframes:

- `#tx_iframe_tokenex-card-number-container` (src: `htp.tokenex.com/iframe/v3?...&Mode=Data`)
- `#tx_iframe_cvv_tokenex-security-code-container` (src: `...&Mode=CVV`)

These are **out-of-process iframes (OOPIF)**. Compositor-level coordinate clicks focus the right pixel, but `Input.dispatchKeyEvent` fired against the **top-level page session** is **not routed into the OOPIF** — the iframe never sees the keystrokes. Both `type_text()` and page-session CDP key events silently fail, leaving the fields empty. The visible error after submit attempts: `"Card number is required"` despite the field being focused.

What works: **attach to each OOPIF's CDP target and dispatch key events against the iframe's own session.**

```python
# 1) Find the tokenex iframe targets
targets = cdp("Target.getTargets")
pan_id  = next(t['targetId'] for t in targets['targetInfos'] if 'tokenex' in t.get('url','') and 'Mode=Data' in t['url'])
cvv_id  = next(t['targetId'] for t in targets['targetInfos'] if 'tokenex' in t.get('url','') and 'Mode=CVV'  in t['url'])

# 2) Attach (flatten=True is required so we can pass session_id on each call)
pan_session = cdp("Target.attachToTarget", targetId=pan_id, flatten=True)['sessionId']
cvv_session = cdp("Target.attachToTarget", targetId=cvv_id, flatten=True)['sessionId']

# 3) Focus the actual input INSIDE the iframe, then dispatch key events against that session.
#    Both iframes expose input id="data" (PAN: name=cardNumber, CVV: name=Data).
cdp("Runtime.evaluate", expression='document.getElementById("data").focus();', session_id=pan_session)
for ch in "4111111111111111":
    cdp("Input.dispatchKeyEvent", type="keyDown", text=ch, key=ch, code=f"Digit{ch}", session_id=pan_session)
    cdp("Input.dispatchKeyEvent", type="keyUp",   key=ch, code=f"Digit{ch}", session_id=pan_session)
```

This is the general pattern for any TokenEx-hosted PCI field (Delta, United, and other airlines/hotels also use TokenEx). Direct `.value =` inside the iframe won't trigger TokenEx's internal validation; key events do.

Billing address auto-populates from the Traveler Details step — no re-entry.

## Waits

- `wait_for_load()` after each major navigation is fine.
- After clicking a fare card, wait ~3s for the fare-options sub-cards to render.
- After clicking `Select Blue Basic`, the URL transitions (3-5s).
- After `Next: Seats & Extras` and `Skip to Review & Pay`, wait ~5s — TokenEx iframes take a second to inject after the page renders; querying `#tx_iframe_tokenex-card-number-container` too early returns null.
- DOB `Year` dropdown has ~100 entries; use `element.scrollIntoView({block:'center'})` on the target `<span>` inside the open flyout — page `window.scrollBy` does not scroll the flyout's internal list reliably.

## Did-not-work list

- `.value = "..."` on the TokenEx iframe's `#data` input — no visible effect; TokenEx listens for keystrokes.
- `type_text()` after a coord click into the PAN iframe — clicks hit the compositor but key events go to the top-level page, not the OOPIF.
- `cdp("Input.dispatchKeyEvent", ...)` without a `session_id` — same reason; events land on the top frame.
- Opening the DOB Year dropdown and clicking `span[text=1990]` before scrolling it into view — span was present in DOM but off-screen; click landed on a different year span.
- `querySelector('[role=option]')` inside `jb-flyout` — options don't carry `role=option`; match by `innerText` on `<span>` children.

## Antibot posture

No CAPTCHA, no Akamai/PerimeterX interstitial, no login wall, no 3DS/OTP on filled non-submitted fields. TrustArc cookie banner appears but is non-blocking — click `Accept` once or leave it (it covers the bottom-left corner and doesn't intercept form clicks).
