# united.com — flight checkout

React + Angular-ish single-flow checkout on united.com. **No Akamai / PerimeterX
block observed** when driven from the user's real Chrome via CDP — the Akamai
bot cookies (`_abck`, `bm_sz`, `bm_mi`, `bm_so`, `bm_sv`, `bm_lso`) are present
from first load, but `_abck` stays on `~0~` (not flagged) through the whole
checkout flow from home → search → fare pick → pax → seats → payment form.
Login is NOT required to reach the card entry page.

Coordinate clicks via `Input.dispatchMouseEvent` are NOT reliable on most of
the booking widget buttons (homepage `Find flights` submit, the fare `Select`
buttons, and the `Basic Economy works for me` checkbox specifically). Native
`element.click()` via `js(...)` works everywhere. Prefer it by default on
united.com and use coordinate clicks only to focus text inputs before
`type_text()` keystrokes.

## URL map

- Home: `https://www.united.com/en/us` (search widget `#bookFlightForm` inline)
- Search submits to `/en/us/fsr/choose-flights?f=EWR&t=ORD&d=YYYY-MM-DD&tt=1&sc=7&px=1&taxng=1&newHP=True&clm=7` (one-way one adult). You can hit this URL directly to skip the homepage form.
- Choose flights: `/en/us/fsr/choose-flights?...&st=bestmatches&tqp=R`
- Traveler info: `/en/us/traveler/choose-travelers?cartId=<UUID>&tqp=R`
- Travel add-ons: `/en/us/book-flight/customizetravel/<cartId>?tqp=R`
- Seat map: `/en/us/book-flight/seatmap/<cartId>?tqp=R`
- Checkout (card form): `/en/us/book-flight/checkout/<cartId>?tqp=R`

`cartId` (UUID) is issued at fare selection and carried through the rest.

## Flow

1. Home: `#bookFlightForm` pre-fills with last search. Radios `#radiofield-item-id-flightType-0` (round trip) / `#radiofield-item-id-flightType-1` (one way). Submit via `button[aria-label="Find flights"].click()` — coordinate click is silently dropped.
2. Results: each flight row has a cabin price card button whose text matches `/\$\d+[\s\S]*(Economy|First)/`. Click opens an inline drawer with 3 fare tiers (Basic / Standard / Flexible for Economy).
3. Basic Economy requires an acknowledgement: an unlabeled `input[type=checkbox]` with a UUID id must be clicked before the `button[aria-label^="Select United Economy Basic"]` becomes enabled. Until then the Select button has `disabled=""`. The `Standard` and `Flexible` Select buttons are enabled immediately.
4. Traveler info: flat form, native `<input>` / `<select>`. Angular reactive fields — use the value-setter pattern (dispatch `input`, `change`, `blur`). Required: firstName, lastName, email, phone, DOB (MM select + DD text + YYYY text), gender.
5. Travel add-ons page: one button, `Continue to seats`.
6. Seat map: `Continue to checkout` button (or `Skip seat selection` anchor link, same destination).
7. Checkout: single-page payment form, `<h1>Checkout United Airlines</h1>`. Card fields render inline (no cross-origin tokenization iframe). Billing address + email + phone are visible on first render (no PAN-gated reveal like Delta).

## Stable selectors

Home search widget:
- `#bookFlightForm` (the form — can call `.submit()` but reaching the submit button by aria label is cleaner)
- `button[aria-label="Find flights"]` — the submit
- `#bookFlightOriginInput`, `#bookFlightDestinationInput` (airport autocompletes)
- `#DepartDate_start` (input with value like `Apr 29`)

Results / fare drawer:
- Price card buttons: `button` whose innerText matches `/From\s*\$\d+.*Economy|First/` (no stable id — the id attribute is empty).
- Basic Economy ack checkbox: `input[type=checkbox]` inside `.app-pod-shopping-nestedFSR-NestedPriceCards-styles__basicFooter--*` (UUID id).
- Fare Select buttons: `button[aria-label^="Select United Economy Basic"]`, `"Select United Economy Standard"`, `"Select United Economy Flexible"`. Each has `aria-describedby="nested-atc-btn-ECO-BASIC|ECO-STANDARD|ECO-FLEX"` — stable across rows.

Traveler page (every `name=` is stable, ids are UUIDs — use name attrs):
- `input[name="rtiTraveler.travelers[0].firstName"]`
- `input[name="rtiTraveler.travelers[0].lastName"]`
- `input[name="rtiTraveler.travelers[0].middleName"]`
- `input[name="rtiTraveler.travelers[0].email"]`
- `input[name="rtiTraveler.travelers[0].extraDetails.phone.mobileNumber"]`
- `select[name="rtiTraveler.travelers[0].gender"]` (values `M`/`F`/`X`/`U`)
- `select[name="rtiTraveler.travelers[0].suffix"]`
- `select[name="rtiTraveler.travelers[0].frequentFlyer.program"]`
- DOB: `select[aria-label="Month"]` (0-indexed values, `"0"=January`), `input[placeholder="DD"]`, `input[placeholder="YYYY"]`. Three separate fields, NOT a single date input.
- `input[name="rtiTraveler.travelers[0].extraDetails.travelerNumbers.knownTravelerNumber"]`
- `input[name="rtiTraveler.travelers[0].extraDetails.travelerNumbers.redressNumber"]`
- `select[name="rtiTraveler.travelers[0].extraDetails.phone.countryCode"]` (values like `"1|US"`)
- Continue: `button` with innerText `"Continue"` (no id).

Checkout card fields (names stable):
- `input[name="commonpayment.cardInfo.cardNumber"]` — PAN, `type=tel`, formats live to `4111 1111 1111 1111`
- `input[name="commonpayment.cardInfo.expiryDate"]` — MM/YY, `type=tel`, formats to `12 / 29`
- `input[name="commonpayment.cardInfo.encryptSecurityCode"]` — CVV, `type=tel`
- `input[name="commonpayment.cardInfo.nameOnCard"]`
- `input[name="commonpayment.billingAddress1"]`
- `input[name="commonpayment.billingAddress2"]`
- `input[name="commonpayment.city"]`
- `#stateFilter` — **autocomplete text input** (NOT a select), options appear as `[role=option]`-ish `li`s below; type `"New York"` → `.click()` the option.
- `input[name="commonpayment.zipCode"]`
- `select[name="commonpayment.country"]` — default value `"US"`
- `input[name="commonpayment.phoneNumber"]`
- `input[name="commonpayment.email"]`
- Payment method radios (`name="paymentMethod"`): `#credit_or_debit` (default), `#pay_with_uplift`, `#tc`, `#travelbank`, `#paypal`, `#aliPay`, `#paze`.
- Submit (DO NOT CLICK for testing): `button` with innerText `"Agree and purchase"`.

## Coordinate clicks vs JS click

The specific widgets where `click(x, y)` via `Input.dispatchMouseEvent` was
dropped but `element.click()` worked:

- Homepage `button[aria-label="Find flights"]` (form submit)
- Fare-drawer `Select` buttons (`#mach-drawer`-equivalent — these are React buttons wired to a synthetic-event handler that the compositor-level click does not trigger)
- Basic Economy ack checkbox

Everywhere else JS click also works, so just default to JS click on united.com:

```python
js("""
(() => {
  const btn = [...document.querySelectorAll('button')]
    .find(b => b.innerText.trim() === 'Continue' && !b.disabled && b.getBoundingClientRect().width > 0);
  btn.scrollIntoView({block:'center'});
  btn.click();
})()
""")
```

For text inputs, coordinate click + `type_text()` works fine for PAN/CVV/expiry/name
and triggers the input masking that turns on the VISA badge and validates format.
The Angular setter trick works for all the billing address text inputs.

## Basic Economy acknowledgement trap

If you click `Select` on the Basic Economy card and nothing happens, the button
is `disabled=""`. There is an unlabeled `input[type=checkbox]` (UUID id, no
label element nearby — the visible text `"Basic Economy works for me."` is in
a sibling span) inside the `basicFooter` container that must be checked first.
Easiest query:

```js
document.querySelector('.app-pod-shopping-nestedFSR-NestedPriceCards-styles__basicFooter--DliQr input[type=checkbox]').click();
```

The container class suffix (`--DliQr`) is CSS-module hashed and may change.
A more resilient query: find the `<button>` with `aria-label^="Select United Economy Basic"`
and walk up to its closest `div` containing an `input[type=checkbox]`.

## Waits

- `wait_for_load()` returns before React hydrates on fare results and checkout
  pages. Add `time.sleep(3-5)` after each page transition before DOM probing.
- The fare drawer animates in; `sleep(1)` after clicking the price card.
- State autocomplete: after `type_text("New York")`, `sleep(1.5)` before
  looking for the `New York` option.

## Anti-bot / Akamai

Akamai Bot Manager (cookie prefix `bm_`) is active on united.com. Observed
cookies at load time:

`_abck, bm_mi, bm_so, bm_sz, bm_sv, bm_lso`

Driving from the user's real Chrome via CDP: `_abck` value contains `~0~`
throughout the flow (home → search → fare select → pax → seatmap → checkout).
The `0` means "not flagged as bot"; a positive integer would mean flagged.
No Akamai interstitial, no `sensor_data` POST was forced to re-submit, no
403/429 observed. No PerimeterX cookies present. No reCAPTCHA / hCaptcha.
No login wall up to the `Agree and purchase` button.

If you hit Akamai later (likely on submit / 3DS), look for the value in
`_abck` flipping off `~0~`, 403/429 responses from `/e/*` endpoints, or a
`"We're sorry"` interstitial. None of those happened on this flow.

## Traps

- The homepage `Find flights` button submit: coordinate clicks hit the right
  pixel but the React handler never fires. Use `btn.click()` or
  `document.getElementById('bookFlightForm').submit()`.
- The Basic Economy `Select` button is `disabled=""` until the ack checkbox
  is clicked. The disabled attribute means clicks silently no-op — no error,
  no console warning.
- `getBoundingClientRect().y` coordinates shift between queries because the
  page has a lot of lazy-loaded content. If you cache a coordinate from one
  `js()` call and use it in a later `click()`, it may be stale. Always fetch
  fresh coords inside the same call that triggers the action, or use JS click.
- `#stateFilter` is NOT a `<select>` despite the surrounding `.atm-c-base-autocomplete`
  structure. Type + click the option.
- Month dropdown on the traveler page has 0-indexed values (`"0"` = January,
  `"11"` = December) even though the visible text is "January".. "December".
- The "Save your credit card for airport and inflight purchases" checkbox is
  pre-checked on first render. If you care about not persisting card state,
  uncheck it.
- There are two iframe-looking things in the checkout DOM (`collect-iframe`,
  etc.) but the real card inputs are direct `<input type=tel>` elements —
  these iframes are analytics / 3DS collect, not tokenization. No iframe
  traversal needed for PAN entry.
