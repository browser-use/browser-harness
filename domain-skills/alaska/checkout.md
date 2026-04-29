# alaska — guest checkout to card-entry

Drives www.alaskaair.com from search through the credit-card entry form as a guest. No login needed. Reaches a filled payment form; stop before `Book now`.

## URL patterns

- **Results deep link (cash mode once toggled)**: `https://www.alaskaair.com/search/results?O={orig}&D={dest}&OD={YYYY-MM-DD}&A=1&C=0&L=0&RT=false`. The site sometimes lands in award/points mode. Flip via the `Money`/`Points` toggle (see selectors).
- **Cart**: `https://www.alaskaair.com/search/cart?...` — arrived via `Add to cart` from results.
- **Guest info**: `https://www.alaskaair.com/book/guest-info` — arrived via `Continue as guest` from cart.
- **Seat selection**: `https://www.alaskaair.com/book/seat-selection`.
- **Review & pay**: `https://www.alaskaair.com/book/checkout` — the payment page, card fields live here.

## Framework — Auro design system (Alaska's web components)

The site is built on Alaska's Auro components. Every form control is a custom element whose real state lives on the wrapper, not the shadow-DOM internals. **Setting `.value` programmatically does not satisfy the form validator.** Validators trigger "Invalid X" errors unless the value was set by a real keystroke or a click-driven `auro-menuoption` selection.

Reliable patterns:
- Text fields (`AURO-INPUT`): click the wrapper, then `type_text(...)`. Do not set `.value` and hope it sticks.
- Selects (`AURO-SELECT`): click the wrapper to open the dropdown, then click the matching `auro-menuoption` (has a `value=` attribute). A sibling native `<select id="native-select-{id}">` exists but is not the validator source of truth.
- Buttons: the visible CTAs are `FS-AURO-BUTTON` or `AURO-BUTTON`. Coordinate-click them; their center is a stable target.

## Card fields — CyberSource Flex Microform

PAN and Security Code are served from **two separate cross-origin iframes** from `flex.cybersource.com/microform/bundle/v2.9.0/iframe.html`. A coordinate click on the visible iframe box does **not** reliably focus the inner input (observed: click + `type_text` landed nowhere).

The approach that works:

1. Find the iframe `targetId`s via `cdp("Target.getTargets")` filtered on `"cybersource" in url` — there are exactly two.
2. Focus the input inside the iframe with `js("document.getElementById('number').focus()", target_id=pan_frame_id)` (CVV input id is `securityCode`).
3. Call `type_text(...)` — `Input.insertText` is routed to whatever element currently has focus, including cross-origin iframes, so the value lands in the Microform without touching frame coordinates.

PAN field id inside iframe: `number`. CVV id: `securityCode`. Both at the frame document root.

## Stable selectors (guest-info + checkout)

- `#firstName`, `#lastName` — AURO-INPUT text fields (traveler 1).
- `#gender`, `#dateOfBirthMonth` — AURO-SELECT; pick option via `auro-menuoption[value=...]` after opening.
- `#dateOfBirthDay`, `#dateOfBirthYear` — AURO-INPUT digits.
- `#email`, `#phone`, `#zipCode` — AURO-INPUT under contact info.
- `#saver-upsell-dialog` — `FS-AURO-DIALOG` that appears after picking a Saver fare with a `Continue with Saver` `FS-AURO-BUTTON` inside. Find by walking into light-DOM descendants; click by rect, not selector.
- `#expiration-month`, `#expiration-year` — card exp AURO-SELECT; options are plain two-digit values like `12`, `2029`.
- `#name`, `#addressLineOne`, `#billingInfoCity`, `#billingInfoZipCode` — AURO-INPUT billing fields.
- `#billingInfoState` — AURO-SELECT; option values are 2-letter state codes (`NY`).
- Insurance: `#TripInsurance_AWP0` (yes) / `#TripInsurance_AWP1` (no). These radios render off-screen visually (e.g. `x ≈ -15000`). `.click()` via JS works; coordinate click does not.
- "Credit/debit card" payment-method radio: not an `<input>` — a plain `BUTTON` next to a `SPAN` with text `Credit/debit card`. Click the span/button by rect.

## What doesn't work

- `el.value = "..."` on any Auro form element: display may update, but Auro's validator emits "Invalid X" on submit anyway. Always type or click-select.
- Coordinate clicks on CyberSource iframe boxes + `type_text`: focus doesn't land in the inner input. Use the iframe-target-focus pattern above.
- Deep-search `document.querySelectorAll('button')` for dialog CTAs: Auro buttons are `FS-AURO-BUTTON` custom elements, not `BUTTON`. Filter on `tagName.includes('AURO-BUTTON')` and walk `shadowRoot` chains.

## Waits

- After clicking `Continue with Saver`: 3-5s for Svelte/Sapper transition to the trip-summary view.
- After `Continue as guest`: 5-6s to load `/book/guest-info`.
- After `Continue` on guest-info: 5-6s; re-check URL (`/book/seat-selection`) because validation errors keep you on the same URL with no thrown exception.
- After `Skip seats`: 5-6s to `/book/checkout`.

## Traps

- Homepage (`alaskaair.com`) pops a credit-card promo modal on load; deep-linking straight to `/search/results?...` avoids it entirely.
- The results deep link lands in points/award mode by default. There is a single `button[role=switch]` with `innerText="Money\nPoints\nPoints"` — `.click()` toggles it.
- The "Protect your trip" insurance section is required and blocks advancing with no error until you select No. Use `document.getElementById('TripInsurance_AWP1').click()` — the radio is visually hidden at `x ≈ -15000`, so coordinate clicks won't find it.
- reCAPTCHA Enterprise badge appears on `/book/checkout`. It did not challenge in this run; behavior under heavy scripted sessions is unknown.

## Known-working fake data shape

Cash fare SEA→PDX one-way, $249 Saver, April 29 2026 — smallest reachable price path. Swap `O=`/`D=` in the deep link for other Alaska hubs (LAX, SFO, PDX, SAN).
