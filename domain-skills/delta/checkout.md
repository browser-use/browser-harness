# delta.com — flight checkout

Angular-based booking flow. Stable IDs throughout. No Akamai/PerimeterX block when
driven from the user's real Chrome via CDP — search → cart → pax → payment form all
reachable without login. Login is optional (SkyMiles), not required to reach the
Complete Purchase step.

## URL map

- Home: `https://www.delta.com/` (search widget inline)
- Search-prefill URL (skips the widget):
  `https://www.delta.com/flight-search/search?tripType=ONE_WAY&priceSchedule=price&originCity=ATL&destinationCity=MCO&departureDate=YYYY-MM-DD&passengerCount=1&cabinFareClass=BE&awardTravel=false&refundableFlightsOnly=false&nonstopOnly=false&showBasicFares=true`
  Redirects to `/flightsearch/book-a-flight?...&cacheKeySuffix=<uuid>` with the form pre-populated.
- Results: `/flightsearch/search-results?cacheKeySuffix=<uuid>`
- Trip summary: `/completepurchase/trip-summary?cacheKeySuffix=<uuid>&cartId=<uuid>&app=sl-sho`
- Review & pay: `/completepurchase/review-pay?cacheKeySuffix=<uuid>&cartId=<uuid>`

`cacheKeySuffix` is carried across all pages; `cartId` is issued after fare selection.

## Flow

1. Hit the prefill URL → press `Find Flights`.
2. Fare grid renders. Click the fare cell (`#grid-row-0-fare-cell-desktop-BMAIN` for
   the cheapest Main). A "Select an Experience" drawer slides up.
3. In the drawer: check `#restrictions` (Accept Restrictions), then click
   `#mach-drawer-select-cta-BMAIN` (Select for Basic).
4. Trip summary page. Scan for button text `Continue to Review & Pay` — no stable ID.
5. Review & pay page: single-page form with pax info, contact, trip insurance,
   payment, billing. Card fields auto-render billing address fields once a valid
   PAN is typed (US is default country).

## Stable selectors

Search widget (home):
- `#one-way-route-picker-origin-button`
- `#one-way-route-picker-destination-button`
- `#date-picker-trigger-<random>` (aria-label `"Flight Date Field, ..."`)
- `#findFilghtsCta` (note the typo — that's the real ID)

Results grid:
- `#grid-row-<N>-fare-cell-desktop-BMAIN` — Main Basic
- `#grid-row-<N>-fare-cell-desktop-BDCP` — Comfort
- `#grid-row-<N>-fare-cell-desktop-CFIRST` — First
- Fare drawer: `#restrictions`, `#mach-drawer-select-cta-BMAIN` / `CMAIN` / `EMAIN`

Pax form (index `_0` for passenger 1):
- `#firstName_0`, `#lastName_0`, `#middleName_0`
- `#suffix_0_dropdown`, `#gender_0_dropdown`
- `#dobmonth_0_dropdown`, `#dobday_0_dropdown`, `#dobyear_0_dropdown`
- `#frequentFlyerProgram_0_dropdown`, `#frequentFlyerNumber_0`
- `#contact_info_phone`, `#contact_info_email`
- `#input_country_contact_dropdown`
- `#protectTrip` / `#noProtectTrip` (radio for trip insurance)

Payment:
- `#id_paymentCardNum_creditDebit` — PAN (triggers VISA/MC/AMEX detection + billing form)
- `#id_expirationDate_creditDebit` — MM/YY
- `#id_paymentCardSecurityCode_creditDebit` — CVV (type=password)
- `#id_nameOnCard_creditDebit`
- `#id_addressLine1Text_creditDebit`, `#id_addressLine2Text_creditDebit`
- `#id_cityLocalityName_creditDebit`, `#id_postalCode_creditDebit`
- `#id_countryCode_creditDebit-wrapper` (combobox span)
- `#id_countrySubdivisionCode_creditDebit-wrapper` (state combobox span)

## Dropdowns — Angular `idp-dropdown` pattern

There are two dropdown flavors, both custom (no `<select>`):

### Flavor A — `idp-dropdown` (pax DOB, gender, suffix, FF, contact country)

- Trigger: `#<name>_dropdown` with `role=combobox`, `aria-expanded`
- Options list: `#<name>-desc` (`<ul>`) with items `#<name>option-<N>` (1-based),
  option-1 is the "MM" / "Select" placeholder
- Displayed selection: `#idp-<name>__selected` (has `data-selected-value` and
  visible `.innerText` of the chosen option)

Pattern that works: click the trigger to open, then `scrollIntoView` the option
`<li>` and coordinate-click it. Do NOT skip `scrollIntoView` — the year list has
~100 entries and the option can be offscreen even after the dropdown opens.

### Flavor B — `.select-ui-wrapper` (billing state, billing country)

- Trigger: `#<name>-wrapper` (`<span role=combobox>`). Coordinate-clicking this
  span does NOT open it reliably — the inline `style="width:0px"` is misleading,
  `getBoundingClientRect` shows the real width, but mouse events are swallowed.
- What works: `.focus()` the wrapper, then `press_key(" ")` (Space). `aria-expanded`
  flips to `true`.
- Options: `#ui-list-<name><N>` (0-based). Click by `scrollIntoView` + coords.

## Forms — value-setter pattern

Angular reactive forms do NOT accept raw `.value = ...` or `insertText` alone for
non-focused inputs. Use the React/Angular-safe native setter when setting many
fields at once:

```js
const native = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
native.call(el, 'Test');
el.dispatchEvent(new Event('input', {bubbles: true}));
el.dispatchEvent(new Event('change', {bubbles: true}));
el.dispatchEvent(new Event('blur', {bubbles: true}));
```

For the card fields (PAN, CVV, expiration, name) the safest path is coordinate
`click(x, y)` to focus, then `type_text(...)` (CDP keystrokes). The PAN input
has input-masking that only runs on real key events — the JS setter leaves the
VISA/MC badge unlit and the billing fields do not appear. Type keystrokes.

## Billing address appears only after valid PAN

The Country/Region, Address Line 1/2, City, State, Postal inputs are NOT in the
DOM until a valid-looking PAN is typed into `#id_paymentCardNum_creditDebit`.
If you enumerate inputs before the PAN is filled you will not see them. Fill
PAN first, then re-enumerate.

## Waits

- `wait_for_load()` returns before the Angular bundle hydrates on results and
  review-pay pages. Add `wait(4-5)` after every page transition.
- The "Select an Experience" drawer animates in; `wait(1)` after clicking a fare
  cell before reading its content.

## Traps

- `#findFilghtsCta` exists twice in the DOM (homepage widget + booking-page
  widget). `document.getElementById(...)` returns the first, which has
  `getBoundingClientRect()` of 0×0 on the booking page. Enumerate all
  matching buttons and pick the one with `width > 0`.
- `press_key(" ")` on the state wrapper only works if you `.focus()` the
  wrapper first (same CDP session). Trying to send a Space without focus
  just scrolls the page.
- Clicking the "No, do not protect" trip-insurance radio by its `#noProtectTrip`
  centerpoint does not register (radio is inside a large clickable `<label>`
  card that intercepts at a different child). Trip insurance is NOT required to
  reach the card fields — skip it.
- The fare drawer Select button (`#mach-drawer-select-cta-BMAIN`) will appear
  disabled-looking in some screenshots when `#restrictions` is unchecked. Always
  check `#restrictions` first.
- There are several duplicate `#restrictions` checkboxes in the DOM (one on the
  results page drawer, one still mounted on review-pay). They are scoped to
  different components — use the one whose `getBoundingClientRect()` is
  non-zero.

## Anti-bot / captcha

None observed driving from the user's persistent Chrome profile via CDP. No
Akamai / PerimeterX interstitial, no hCaptcha/reCAPTCHA, no 3DS challenge
prior to submit. ATL→MCO nonstop search → pax form → card form took ~9 minutes
end-to-end on the first run including exploration.

Login is NOT required to reach card entry.
