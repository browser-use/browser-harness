# American Airlines — booking checkout (aa.com)

End-to-end guest checkout for a one-way revenue fare, through to the credit-card entry form. No antibot / CAPTCHA encountered on a clean, stock-Chrome CDP connection.

## URL map (in order)

| Step | URL | Title |
| --- | --- | --- |
| Home | `https://www.aa.com/` → redirects to `/homePage.do` | American Airlines … |
| Search results (**deep link**) | `https://www.aa.com/booking/search/find-flights?locale=en_US&fareType=Lowest&pax=1&adult=1&type=OneWay&searchType=Revenue&cabin=&carriers=ALL&travelType=personal&slices=<urlencoded JSON>` | Choose flights |
| After fare select | `https://www.aa.com/booking/choose-flights/1?sid=…` | same |
| Trip summary | `https://www.aa.com/booking/your-trip-summary?sid=…` | Your trip summary |
| Passenger details (separate Angular app) | `https://www.aa.com/airfare-sales/ui/passenger-ui/?search-journey-id=…&cid=…&sid=…` | Passengers |
| Seat map | `https://www.aa.com/booking/passengers/deeplink/airfare-booking/<journey-id>?journey-state-id=<journey-id>&shopping-cart=<cart-id>` | Choose your seat |
| Trip extras | `https://www.aa.com/ancillaries/offers/storefront/2/<cart-id>` | Trip extras |
| Checkout / payment | `https://www.aa.com/ecommerce/checkout-app/cart/<cart-id>` | American Airlines Checkout |

`<slices>` payload (URL-encoded):

```json
[{"orig":"DFW","origNearby":false,"dest":"AUS","destNearby":false,"date":"2026-05-06"}]
```

The deep link skips the home-page React form entirely. The in-page search form is React-controlled; plain `input.value = …` does not propagate to the controlled state, so prefer the deep link.

## Stable selectors & handles

### Search results (`/booking/choose-flights/1`)

- `button#flight-<N>-product-group-<CABIN>` — top-level cabin card (e.g. `flight-0-product-group-MAIN`). **Clicking this expands the fare tray in place**, it does not navigate. Use `.click()` via `js(...)`; the coordinate click has a tendency to scroll past the target.
- `button#slice-<N>-MAIN-basic-economy` / `slice-<N>-MAIN-coach` / `-coach-plus` / `-coach-select` / `-first` — the real "Select this fare" buttons inside the expanded tray. Visible only after the product-group button is clicked.
- `button#carousel-<YYYY-MM-DD>` — date carousel navigation.

### Basic-Economy upgrade-upsell modal

After clicking `slice-0-MAIN-basic-economy`, an upsell dialog appears. The decline button is:

- `button#btn-no-upgrade` — text is **"Accept restrictions"** (not "No, thanks"). Click this to proceed with Basic Economy.

### Trip summary

- `button#login-continue-btn` — "Log in and continue"
- `button#continue-as-guest-btn` — "Continue as guest" (use this)

### Passenger details (`/airfare-sales/ui/passenger-ui/`)

This is a **separate Angular app** using custom elements (`<adc-text-input>`, `<adc-select>`, `<app-passenger-page>`, etc.) with **open shadow roots**. Inputs are addressed by `formcontrolname` on the host element; the real `<input>` / `<select>` is inside `host.shadowRoot`.

Top-level card:

- `adc-button#paxCardButton0` — "Enter new passenger". Clicking it opens a `<mat-dialog-container>` with the passenger form.
- After save, it re-renders as "Edit, saved passenger information for, First Last".

Passenger form (hosts, inside the modal):

| formcontrolname | host id | inner element |
| --- | --- | --- |
| `firstName`, `middleName`, `lastName` | same | `<input>` in shadow root |
| `formMonth`, `formDay`, `formYear` | — | `<select>` (values: `01`, `01`, `1990`) |
| `gender` | `gender` | `<select>` — values are single letters: `M`, `F`, `U`, `X` (not `MALE`) |
| `country` | `residencyCountry` | `<select>` (`US`) |
| `state` | `residencystate` | `<select>` (`NY`) — repopulates *after* `country` is set, so set state **after** country |
| `loyaltyProgram`, `loyaltyNumber` | same | optional |
| `documentNumber`, `documentCountry` | — | optional |

Modal buttons (both `<adc-button>`, no stable id — filter by inner text):

- "Cancel"
- "Save" — commits the passenger and closes the modal.

Contact form (appears on the main passenger page after at least one passenger is saved, NOT inside the modal):

| host id | notes |
| --- | --- |
| `email`, `confirmationEmail` | text |
| `phoneType` | values: `CEL` (Mobile), `HOME`, `BUSINESS` |
| `countryCode` | phone country code, defaults to `US` |
| `phoneNumber` | `tel-national` |
| `tripPurposeType` | `BUSINESS` or `LEISURE` (required) |

Main Continue: `<adc-button>` with `className` containing `save-button` and innerText `Continue`. There is a second Continue ("Log in and continue") on the page — filter it out.

### Seat map

- `a#continueWithoutSeatsLink` — "Skip seats for all flights" (use this to skip)
- `button#nextFlightButton` — "Continue" (only if seats are selected)

### Trip extras (ancillaries)

- Single `<adc-button>` with text "Continue" — just click through.

### Checkout / payment (`/ecommerce/checkout-app/cart/<cart-id>`)

The checkout page is **plain HTML, no shadow DOM, no iframes for card fields**. Fields are directly addressable by id. Sections are progressively disclosed.

1. Trip insurance section — two radios with `name="allianz-insurance-selections"`:
   - `value="purchase"` / `value="decline"` — pick `decline`, then click `button#trip-insurance-continue-button`.
2. Payment method radios, `name="paymentMethod"`:
   - `value="CREDIT_CARD"`, `AFFIRM`, `APPLE_PAY`, `GOOGLE_PAY`, `PAYPAL`, `HOLD`.
   - Selecting `CREDIT_CARD` expands the card form inline.
3. Credit card fields (all plain `<input>` / `<select>`):

| id | name | autocomplete |
| --- | --- | --- |
| `firstNameInput` | firstName | cc-given-name |
| `lastNameInput` | lastName | cc-family-name |
| `cardNumberInput` | cardNumber | cc-number |
| `expirationDateInput` | expirationDate | cc-exp (format `MM/YY`) |
| `cvvInput` | cvv | cc-csc (`type=password`, **appears only after the card number is entered**) |
| `countryNameInput` | country | billing country |
| `addressInput` | address | billing street-address |
| `cityInput` | city | billing address-level2 |
| `stateInput` | state | billing address-level1 |
| `zipCodeInput` | zipCode | billing postal-code |

- Submit: `button` with text "Pay now" near the bottom of the page.
- "Secure checkout" lock icon sits next to the Pay now button.

## Fill recipe (shadow-piercing + native setter)

For both the passenger-details shadow inputs and the checkout inline inputs, React/Angular will ignore assignments via the prototype's `value` setter unless you dispatch the right composed events. Minimal pattern that works on both:

```js
function nativeSet(el, v) {
  const proto = Object.getPrototypeOf(el);
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
  el.dispatchEvent(new Event('input',  {bubbles: true, composed: true}));
  el.dispatchEvent(new Event('change', {bubbles: true, composed: true}));
  el.dispatchEvent(new Event('blur',   {bubbles: true, composed: true}));
}

// Shadow-piercing helper for <adc-text-input> / <adc-select>:
function setHost(hostId, val) {
  const h = document.getElementById(hostId);
  const inner = h.shadowRoot.querySelector('input, select');
  inner.focus();
  nativeSet(inner, val);
}
```

For the PAN / CVV specifically, prefer the harness's `type_text()` (CDP keystrokes) — the checkout page's card-number tokenizer is happy with either, but keystrokes are a safer default if AA ever switches to a Spreedly/CyberSource iframe.

## Traps

- **React search form on the homepage is controlled state.** Setting `input.value = …` then dispatching `input`/`change` on the native input does not take — the submitted URL has empty `orig`/`dest`. Use the deep-link URL above instead.
- **Basic-Economy upsell.** The decline button literally says "Accept restrictions" (id `btn-no-upgrade`). Easy to misread as an affirm-upgrade.
- **The "Continue" on the passenger page has two meanings.** Before you save a passenger, clicking the page-level `save-button adc-button` with text "Continue" silently opens the passenger modal instead of advancing. Save the passenger first (modal Save button), *then* hit the page-level Continue.
- **`state` select clears when `country` is rewritten.** Set country first, wait a tick, then set state. The Angular form control goes `ng-invalid` otherwise.
- **`gender` values are single letters** (`M`, `F`, `U`, `X`), not `MALE`/`FEMALE`. The a11y label shows "MaleFemaleUnspecifiedUndisclosed" concatenated, which is misleading.
- **Formcontrolname `firstName` exists twice in the DOM** — once on the passenger modal (`<adc-text-input id="firstName">`) and once on the checkout payment form (`<input id="firstNameInput">`). Target by the specific id to avoid collisions.
- **Viewport emulation resets across `Emulation.setDeviceMetricsOverride` boundaries** after navigation. Re-apply `setDeviceMetricsOverride` if the later page's `page_info().w` jumps back up.
- **Tab title is prefixed with the harness's `🟢 ` marker** on each real page, so `page_info().title` will start with that emoji — don't treat it as site content.

## Waits

- `wait_for_load(timeout=20)` plus a `time.sleep(3-5)` after every page transition. The Angular apps (passenger-ui, ancillaries, ecommerce) hydrate lazily and `load` fires before the forms mount.
- After `document.getElementById('slice-0-MAIN-basic-economy').click()`, wait 2-3s for the upsell `<mat-dialog-container>` to mount before trying to query `#btn-no-upgrade`.
- After selecting a payment-method radio, wait ~3s for the credit-card subsection to expand (the `cvvInput` only appears after the first couple of fields hydrate).

## Antibot posture (observed)

- No Akamai `_abck` / `bm_sz` challenge on the booking path with a vanilla user's Chrome.
- No PerimeterX. No interstitial. No CAPTCHA on search, fare-select, passenger, or checkout.
- Payment page is a first-party form — no Stripe/Braintree/Spreedly iframe on the CC fields at this stage. (Tokenization presumably happens on Pay-now submit; we did not submit.)
