# Spirit Airlines — end-to-end checkout to payment-entry

Angular SPA. Path is: home search widget → fare grid → (Saver$ Club upsell) → (Premium Economy upsell) → `/book/passenger` → `/book/seats` → `/book/bags` → `/book/cars-and-hotels` → `/book/options` → `/book/payment`. Real Chrome via CDP passes with **no** antibot friction (no Akamai/PerimeterX/CAPTCHA observed on clean profile). Plain form fields, no Stripe/iframe tokenizer on PAN.

## URL map

- Home + search widget: `https://www.spirit.com/`
- Flight results + all upsells: `https://www.spirit.com/book/flights` (does NOT advance past fare-select until all cross-sell modals are resolved)
- Passenger: `https://www.spirit.com/book/passenger`
- Seats: `https://www.spirit.com/book/seats`
- Bags: `https://www.spirit.com/book/bags`
- Cars + hotels: `https://www.spirit.com/book/cars-and-hotels`
- Add-on options (Shortcut Boarding etc.): `https://www.spirit.com/book/options`
- Payment: `https://www.spirit.com/book/payment`

## Stable selectors

- `#flight-OriginStationCode`, `#flight-DestinationStationCode` — station typeahead inputs. `input` + `change` events commit; **then click the suggestion element** (`.station-picker-typeahead__station-name` or `.city-selection li`) to actually bind the IATA code. Setting `.value` alone leaves the Angular model invalid.
- `#dropdown-toggle-controler-toggleId` → `#oneWay | #roundTrip | #multiCity` — trip-type picker (must toggle the dropdown open before the nested buttons are clickable).
- `#nk-calendarhome-widget-0` — single-date picker in one-way mode. Accepts `MM/DD/YYYY` via native setter. In round-trip mode the ID shifts to a range picker (`#mask-calendar` / `#date-range-pickerhome-widget-0`), so re-query after changing trip type.
- Fare cells: `.p-grid__cell--second.clickable` (Value column). `innerText` is exactly `$<price>`. There are `.low-fare-price` nodes above — those are the weekly price strip, not the fare selector; skip them.
- Passenger form: `#title0` (select), `#firstName0`, `#lastName0`, `#dateOfBirth0` (`MM/DD/YYYY`), `#address`, `#city`, `#provinceState` (select, ISO state code), `#postalCode`, `#countryCode` (defaults `US`), `#contactEmailPrimary`, `#contactEmailConfirm`, `#phoneNumber` (auto-formats `555-555-0100`).
- Payment form — **plain inputs, no iframe**: `#accountHolderName`, `#cardNumber`, `#expMonthYear` (`MM/YY`), `#securityCode`. Native-setter + `input`/`change`/`blur` works for all of them, including PAN (auto-spaces). `#useSameAddress` checkbox pre-ticked — leave as-is to reuse the passenger billing address.
- Insurance gate: `label[for=radio-insuranceCoverage2]` = decline. Click the **label**; clicking the radio itself sometimes doesn't register.

## Upsells / gates (in order) and how to bypass

1. **OneTrust cookie banner** — `#onetrust-reject-all-handler` click (otherwise it sometimes blocks later clicks at the compositor level).
2. **Spirit Mastercard promo modal** on `/book/flights` — dismiss with `button.close` inside the modal. Shows up shortly after landing.
3. **Saver\$ Club gate** — modal appears immediately after clicking a `$` fare. Click button with text `CONTINUE WITH STANDARD` (the `CONTINUE WITH SAVER$ CLUB*` is the primary, enrolls you at +$69.95).
4. **Premium Economy upsell modal** — next, same page. Click `CONTINUE WITH VALUE` (not `UPGRADE`).
5. **Seat map** — text link `Skip Selection` in the page header. `CONTINUE` would proceed but without an explicit seat.
6. **Bags** — `CONTINUE WITHOUT ADDING BAGS` (styled as `btn-link`). Fires an **"Are you sure?" confirmation modal** — must then click `I DON'T NEED BAGS`.
7. **Cars + Hotels** — `Skip Selection`.
8. **Options (Shortcut Boarding etc.)** — just click `CONTINUE` (`.sf__right-action-btn`). No explicit skip; defaults to nothing added.
9. **Payment → Insurance** — select label for `radio-insuranceCoverage2` ("No, I don't want to insure…").

## Waits + timing

- After fare click, modal takes ~2-3s to render. Wait then re-query for `CONTINUE WITH STANDARD`.
- `wait_for_load()` is reliable between page transitions, but add a `time.sleep(2-3)` after each navigation for Angular hydration (buttons that look present may no-op until hydration finishes).
- `/book/bags` `CONTINUE WITHOUT ADDING BAGS` does NOT navigate — it fires a confirm modal. Don't chase the URL change.

## Traps

- Setting station `.value` via native setter reads back `"Fort Lauderdale, FL (FLL)"` but the Angular form is still `ng-invalid` until you click the suggestion. Always follow up with a `.station-picker-typeahead__station-name` click containing the airport name/IATA.
- Trip-type menu items (`#oneWay` etc.) have `offsetParent === null` when the dropdown is closed. Click `#dropdown-toggle-controler-toggleId` first or they silently don't click.
- Date picker in one-way vs round-trip has **different IDs** — don't cache the selector across trip-type switches.
- Fare grid: multiple nodes match `$75` text. Only `.p-grid__cell.p-grid__cell--second.clickable` is the clickable Value fare; the `.low-fare-price` nodes are decorative.
- PAN field (`#cardNumber`) accepts native-setter writes and auto-formats with spaces. No tokenizer iframe observed on `/book/payment` — direct form fill works.
- `#communicator-frame` iframe pointing at `checkout.wallet.cat.earlywarning.io` is an **Early Warning Services (Zelle/wallet-lookup) invisible iframe**, not the card tokenizer. Ignore it for PAN entry.

## Selectors / approaches that failed

- `coordinates-first click on the Value column header` — the big "Value" tile at the top of the compare-options block is not clickable; only the per-flight cell below is.
- Clicking `#radio-insuranceCoverage2` directly sometimes doesn't update Angular state; use the `<label>` instead.
- `document.querySelector('#mask-calendar')` on one-way mode returns null — the range-mode ID isn't used there.

## Minimum viable script sketch

```python
# home search
click reject-cookies
open trip dropdown, click #oneWay, close dropdown
set #flight-OriginStationCode = "FLL", click suggestion with "Fort Lauderdale"
set #flight-DestinationStationCode = "MCO", click suggestion with "Orlando"
set #nk-calendarhome-widget-0 = "MM/DD/YYYY" (>= today + buffer)
click button[type=submit] with text "SEARCH FLIGHTS"
# results
dismiss .close on Mastercard modal
click first .p-grid__cell--second.clickable with text "$<price>"
click "CONTINUE WITH STANDARD"
click "CONTINUE WITH VALUE"
# passenger
fill #title0, #firstName0, #lastName0, #dateOfBirth0, address/city/state/postal, emails, #phoneNumber
click CONTINUE
# upsells
click "Skip Selection"        # seats
click "CONTINUE WITHOUT ADDING BAGS"; click "I DON'T NEED BAGS"
click "Skip Selection"        # cars/hotels
click .sf__right-action-btn CONTINUE   # options
# payment
click label[for=radio-insuranceCoverage2]
fill #accountHolderName, #cardNumber, #expMonthYear, #securityCode
# STOP — do not click "PURCHASE MY TRIP"
```

## Viewport note

Spirit's layout is fine at 1280×900 but respects the real Chrome window; `Emulation.setDeviceMetricsOverride` sets CDP-reported size but the physical window still dictates `document.body.scrollHeight`. Drive scrolling with `window.scrollTo` explicitly — don't rely on the emulated viewport matching.
