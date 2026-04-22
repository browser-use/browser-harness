# Frontier Airlines — flyfrontier.com checkout

Working path **home → Select → Passengers → Bundles → SeatMap → Bags → Extras → Payment/New**. The only real search entry is the homepage widget; direct `booking.flyfrontier.com/Flight/InternetBookingEngine?...` deep links return 404.

## URLs (in order)

1. `https://www.flyfrontier.com/` — search widget (not a `<form>`; submit happens via `#btnSearch`).
2. `https://booking.flyfrontier.com/Flight/Select` — fare grid + sticky "CONTINUE" summary footer.
3. `https://booking.flyfrontier.com/Passengers/Edit` — passenger details + contact.
4. `https://booking.flyfrontier.com/Bundles/Index` — upsell grid + "BUNDLE AND SAVE" confirmation modal.
5. `https://booking.flyfrontier.com/SeatMap/Index` — seat map + "SELECT YOUR SEAT NOW" upsell.
6. `https://booking.flyfrontier.com/Bags/Index` — carry-on / checked bag radios + carry-on upsell modal.
7. `https://booking.flyfrontier.com/Extras/Add` — disruption assistance (Hopper iframe) + agent-assist radios.
8. `https://booking.flyfrontier.com/Payment/New` — credit card + billing form.

## Stable selectors

### Homepage search widget

| Field | Selector |
|---|---|
| Trip type (one-way) | `#rboneway` |
| Origin text input | `#origin` (jQuery UI autocomplete, `.ui-autocomplete` list, select by `aria-label` on `.ui-menu-item` e.g. `"Philadelphia (PHL)"`) |
| Destination | `#destination` (same pattern) |
| Departure date | `#departureDate` — DO NOT use `.value = ...`; the widget is jQuery UI datepicker. Use `$('#departureDate').datepicker('setDate', new Date(Y, M, D))` (note 0-indexed month) |
| Return date | `#returnDate` |
| Submit | `#btnSearch` (an `<a>` inside `.booking-widget`, not a real form-submit). Widget has no enclosing `<form>` — parent chain is `.ToFrom → .destinations → fieldset → #findFlights`. |

### Select page (fare grid)

- Fare radios: `input[type=radio][name^="frontierAvailability.MarketFareKeys"]`; match by `aria-label` (e.g. `"Standard fare $44 departs at 5:05 AM..."`). Click the enclosing `<label>` so jQuery handlers fire — clicking the radio alone skips some handlers.
- Cheapest fare class: `.ibe-farebox-fare-basic` (then `.ibe-farebox-fare-economy`, `-premium`, `-business`).
- Continue buttons (two variants by whether Discount Den is the selected fare type):
  - Standard: `#ibe-Anonymous-STD-summary-continue-button`
  - Discount Den: `#ibe-Anonymous-DD-summary-continue-button`

### Discount Den gate

Triggers after clicking Standard continue. The visible DOM shows BOTH the DD slider and a bunch of hidden signup/signin sliders that match `.slider-container` — filter by visible `innerText` starting with `"WANT A BETTER DEAL"`. Dismiss with `.no-thanks-dd-button` inside it. The `.close-icon` at the top of the slider does NOT dismiss it; only `.no-thanks-dd-button` advances the flow.

### Passengers page

- Passenger: `#frontierPassengers_0__Name_First`, `_Last`, `#frontierPassengers_0__Info_Gender` (numeric values: `1`=Male, `2`=Female), `#date_of_birth_0` (MM/DD/YYYY).
- Contact: `#frontierContact_Name_First`, `_Last`, `#frontierContact_EmailAddress`, `#js_first_phone_number` (format `(XXX) XXX-XXXX`), `#frontierContact_CountryCode`, `#frontierContact_PostalCode`.
- Submit: `#submit_passenger_info_button`.

Note: many `er*` / `erSignup*` / `frontierRegisterMember_*` inputs on this page are hidden slider-modal fields for the signup flow — ignore them. Filter by `getBoundingClientRect().width > 0` or skip ids starting with `erSignup` / `erSignin` / `erForgot` / `frontierRegisterMember_`.

### Bundles page

- Submit: `.js-bundlesSubmitButton` (CONTINUE).
- After submit, a "BUNDLE AND SAVE" modal appears. Dismiss via `#BundleConfirmContinue` (text: "Continue without a bundle") — the enclosing `.ibe-modal-content-container` div also has this text but clicking it does nothing.

### Seat map

- Continue: `#saveSelectedSeats`.
- Skip modal: `button.seatslider-link` whose `innerText` is exactly `"Continue without selecting seats"`.

### Bags

- Carry-on radios: `#CO_000` (none), `#CO_100` (1x), `#CO_200` (1x + priority).
- Checked bags: `#CH_000` (none), `#CH_100`…`#CH_600`.
- Click the enclosing `<label>`, not the radio.
- Initial submit throws errors unless both carry-on AND checked are selected.
- Submit: `.js-bagsSubmitButton`.
- Upsell modal: dismiss with `button.js-modal-close-button.ibe-model-upgrade-linkbutton` ("Continue without adding a Carry-On").

### Extras

- Agent assist (mandatory): `#ibe-extras-agent-assist-radio-free` (value `AAFF`) vs `#ibe-extras-agent-assist-radio-paid`.
- Disruption Assistance is in a Hopper iframe at `iframe#iframe_ExtrasDisruptionAssistance` with src `fintech-portal.hts.hopper.com`. Inside: `#option-1` (buy) vs `#none` (decline). Reach via `iframe_target("fintech-portal.hts.hopper.com")`.
- GoWild pass upsell slider auto-opens and closing with `.close-icon` works here.
- Submit: `.js-extrasSubmitButton`.

### Payment/New

All credit-card inputs are plain DOM (not iframe-tokenized), so `.value = ...` works:

- `#cardholder_name`
- `#card_number` (`type="tel"`, placeholder `XXXX-XXXX-XXXX-XXXX`, auto-inserts dashes on input events — use `type_text()` or assign then fire `input` event)
- `#card_expiration_month` select (`"01"`…`"12"`)
- `#card_expiration_year` select (values are 2-digit years: `"29"` not `"2029"`)
- `#card_cvv`
- `#same_as_contact` checkbox (pre-checked; uncheck to reveal billing fields)
- `#billing_payment_address_1`, `_2`, `_country`, `_zipcode`, `_city`, `_state`, `_email`.
- Country select option values are ISO-2 (`"US"`); state select values are prefixed (`"US|NY"`, not just `"NY"`).

## Traps

- No enclosing `<form>` around the homepage search widget — submitting requires `#btnSearch.click()`, not `form.submit()`.
- `jQuery UI datepicker`: direct `input.value = "05/03/2026"` dispatches but does NOT update the widget's internal state — use the datepicker API.
- Many hidden slider modals (sign-up, sign-in, password-reset, GoWild, Kids Fly Free) live on every page and match `.slider-container` — filter by `offsetParent !== null` AND exclude those with titles `PASSWORD RESET`, `SIGN UP`, `CONFIRM IDENTITY`, `ACCOUNT SIGN IN`, `CANCELLATIONS`, `JOIN THE CLUB`, `GOWILD`, `KIDS FLY`, `PASSHOLDER`.
- Discount Den gate close icon is a no-op — must click `.no-thanks-dd-button`.
- Page `ph` (page height) is 2500–3400 px; a `deviceScaleFactor=1` viewport of 1280×900 keeps screenshots under the 2000 px limit.

## Fare signal

PHL→MCO on 2026-05-03 showed `$39 Discount Den / $44 Standard` in the `.ibe-farebox-fare-basic` box, matching the "web-exclusive rates" thesis. Fare radios carry the raw fare token in `value` (e.g. `0~Z~~F9~Z07DXD2~CLUB~~0~29~~X|F9~2415~...~PHL~05/03/2026 05:05~MCO~05/03/2026 07:47`).

## Viewport

```
cdp("Emulation.setDeviceMetricsOverride", width=1280, height=900, deviceScaleFactor=1, mobile=False)
```
