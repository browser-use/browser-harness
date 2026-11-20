# southwest.com — flight checkout to payment entry

Automating Southwest.com end-to-end up to the payment form. No Akamai/CAPTCHA/login required to reach card entry — guest checkout is the default flow.

## URL patterns

- Home: `https://www.southwest.com/`
- Search results (deep-linkable): `https://www.southwest.com/air/booking/select-depart.html?adultsCount=1&adultPassengersCount=1&originationAirportCode=DAL&destinationAirportCode=HOU&departureDate=2026-04-29&departureTimeOfDay=ALL_DAY&fareType=USD&tripType=oneway&passengerType=ADULT`
- Cart review: `/air/booking/price.html?...` (same query params)
- Passengers: `/air/booking/passenger.html?...`
- Seats: `/air/seat/select-seats`
- Payment: `/air/booking/purchase.html`

The search URL is directly deep-linkable — you can skip the homepage form entirely by constructing this URL with known IATA codes and an ISO date.

## Framework — Downshift comboboxes everywhere

All dropdowns (trip type, gender, suffix, contact method, state, credit card type) are **Downshift-style combobox inputs**. Characteristics:
- `<input role="combobox" readonly aria-autocomplete="list">` with `aria-expanded`
- Menu is dynamically inserted with id `<input-id>--menu` and items `<input-id>--item-N`
- **Menu closes on blur** — any tool call between open and select drops it.

### Opening a combobox — the trap

Plain CDP `click(x, y)` works for SOME comboboxes (origin/destination/date) but does **not** open gender/state/creditCardType. Coordinate clicks at the right pixel still leave `aria-expanded="false"`.

**Works reliably** — dispatch synthesized `mousedown`+`mouseup`+`click` sequence on the input:
```js
const r = g.getBoundingClientRect();
['mousedown', 'mouseup', 'click'].forEach(t => {
  g.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true,
    clientX: r.x+r.width/2, clientY: r.y+r.height/2, button: 0}));
});
```

### Selecting an option — the other trap

After opening, the rendered item elements (`<li role="option">`) wrap inner `<button>` elements. Neither coordinate-click nor `.click()` on the outer `<li>` commits the value. **You must call `.click()` on the inner button**:
```js
const item = document.getElementById('creditCardType--item-2');
const btn = item.querySelector('button') || item;
btn.click();
```

**Never** call `scrollIntoView()` on an option after opening — it triggers blur and closes the listbox. If an option is off-screen, see "Virtualized listboxes" below.

### Virtualized listboxes — the state dropdown

The state dropdown (`creditCardState`) uses react-virtualized. Only the first ~10 options render at a time. `scrollTop` assignment on the flyout container has no effect (clientHeight is 0).

**Workaround** — dispatch a typed-character keydown which filters the list:
```js
g.focus();
g.dispatchEvent(new KeyboardEvent('keydown', {
  key: 'N', code: 'KeyN', keyCode: 78, which: 78, bubbles: true, cancelable: true
}));
```
Then in a second call (needs a React render cycle), find the option by `textContent` and click its inner button.

## Text inputs

Most text inputs accept plain value-setter:
```js
const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
setter.call(el, val);
el.dispatchEvent(new Event('input', {bubbles: true}));
el.dispatchEvent(new Event('change', {bubbles: true}));
el.dispatchEvent(new Event('blur', {bubbles: true}));
```

**Exception — card number (`#creditCardNumber`) and CVV** use a masked tokenizer: value-setter yields nothing (input stays empty). Use real CDP keystrokes (`type_text()`) after focusing the field. On success, the PAN is read back as `XXXXXXXXXXXX1111` and CVV as `***`.

## Passenger page gender field — known stable ID

```
passengerFirstName-0, passengerMiddleName-0, passengerLastName-0, passengerDateOfBirth-0 (MM/DD/YYYY),
passengerGender-0, contactMethod, contactPhoneNumber
```

DOB accepts `01/01/1990` via value-setter directly. Gender requires the synth-open + inner-button-click pattern above.

Contact method defaults to "Text me" — fine, just provide `contactPhoneNumber`. No email required on the passenger page; email is collected on the purchase page.

## Seat selection — confirm step

Seats are `<button id="22A">` with aria-label `Seat 22A (Standard, Window)`. A coordinate click on the seat button opens a **"Selected Seat" dialog** (role="dialog"). The dialog closes fast; look for a standalone `<button>Select</button>` on the page body (not inside a dialog, not inside any seat button). Calling `.click()` on that Select button commits the seat assignment.

After commit, the passenger label updates from `Test P. No seat selected` to `Test P. Seat: 22A`.

Continue to purchase is an `<a href="/air/booking/purchase.html">Continue</a>` — not a button. Look for the `<a>` with that href.

## Stable selectors that worked

- `#originationAirportCode`, `#destinationAirportCode` (text autocomplete, type IATA code → option `select-id-XXXXX-item-0`)
- `#departureDate` — accepts `MM/DD` format via `type_text()`
- `#flightBookingSubmit` — search button
- `button[aria-label^="Choice fare $"]` — fare selection buttons
- `button[aria-label*="Continue to seats"]` — passenger-page next
- `a[href*="/air/booking/purchase.html"]` — seat-page next
- Gender selection: synth-open `#passengerGender-0`, then `document.getElementById('passengerGender-0--item-1').querySelector('button').click()` (item-1 = Male)

## Selectors / approaches that failed

- `press_key("ArrowDown")` + `press_key("Enter")` to navigate combobox options — focus leaves input, menu closes before arrow press registers.
- CDP `click(x, y)` on combobox trigger — works for origin/date fields but NOT gender/state/creditCardType.
- `scrollIntoView()` on an open listbox option — blurs the combobox and closes the menu.
- `btn.click()` on the outer `<li role="option">` — doesn't commit; must click inner `<button>`.
- Setting `scrollTop` on the virtualized state listbox container — clientHeight is 0, scroll has no effect.

## Waits beyond `wait_for_load()`

- After `Continue` to `/passenger.html`: 3s for React hydration before inspecting fields (otherwise `passengerGender-0` React props aren't attached yet).
- After search submit: 3-4s; results page streams in.
- After selecting a fare, 2s for cart to populate and Continue button to appear.
- After keydown filter on state listbox: 400-500ms for React to re-render the visible rows.

## Antibot

None encountered on this run. No CAPTCHA, no Akamai challenge, no login wall, no 3DS. Guest checkout completes through card-entry without any interstitial.

## Viewport

`cdp("Emulation.setDeviceMetricsOverride", width=1280, height=900, deviceScaleFactor=1, mobile=False)` keeps screenshots under the 2000px crash limit. Note: the override can get cleared by navigation — re-apply if `window.innerWidth` drifts back to 1699.
