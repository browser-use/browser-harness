# FlightHub.com — Flight Search Automation

Field-tested 2026-05-22 using browser-harness + Mac Chrome CDP.
No anti-bot protections encountered beyond standard Cloudflare JS challenge
(handled automatically by a real browser session).

---

## Anti-Bot Protection

**FlightHub uses Cloudflare.** Key facts:

- Blocks all non-browser HTTP requests with **403 "Just a moment..."** JS
  challenge page — `curl`, `web_extract`, and plain HTTP clients cannot
  retrieve any page, including the direct search URL
- The JS challenge requires a real browser environment (JavaScript engine,
  proper TLS fingerprint, cookie management)
- **Solution:** Use a real browser (local Chrome via CDP, cloud browser with
  residential proxy, or Playwright with stealth) — Cloudflare passes the
  challenge without captchas for legitimate residential IPs

---

## Search URL Format

FlightHub search can be initiated via a **direct URL** — this avoids the
fragile datepicker and airport autocomplete:

```
https://www.flighthub.com/flight/search?
  seg0_from={ORIGIN}&seg0_to={DEST}&
  seg1_to={ORIGIN}&seg1_from={DEST}&
  seg0_date={YYYY-MM-DD}&seg1_date={YYYY-MM-DD}&
  order_by=cheapest&currency=cad&
  num_adults=1&num_children=0&num_infants=0&num_infants_lap=0&
  type=roundtrip&seat_class=Economy
```

| Parameter | Description |
|-----------|-------------|
| `seg0_from` | Origin IATA code (e.g., YYZ) |
| `seg0_to` | Destination IATA code (e.g., ICN) |
| `seg1_to` | Return origin (same as seg0_from) |
| `seg1_from` | Return destination (same as seg0_to) |
| `seg0_date` | Outbound departure date (YYYY-MM-DD) |
| `seg1_date` | Return departure date (YYYY-MM-DD) |
| `order_by` | Sort: cheapest, fastest, best |
| `currency` | Currency: usd, cad |
| `num_adults` | Adult passengers |
| `seat_class` | Economy, Premium, Business, First |

### Example

```
https://www.flighthub.com/flight/search?
  seg0_from=YYZ&seg0_to=ICN&
  seg1_to=YYZ&seg1_from=ICN&
  seg0_date=2026-07-03&seg1_date=2026-07-25&
  order_by=cheapest&currency=cad&
  num_adults=1&seat_class=Economy
```

---

## UI Search Flow (when URL approach fails)

When navigating to `https://www.flighthub.com/` directly, the page has an
SPA flight search form. This form is **automation-hostile** due to the
custom datepicker component, but the airport POI autocomplete works.

### Step 1: Airport Autocomplete

The departure and destination inputs are `#seg0_from_display` and
`#seg0_to_display`. `fill_input()` with real CDP keyboard events works:

```python
fill_input("#seg0_from_display", "YYZ")
time.sleep(2)
press_key("Tab")  # dismiss POI dropdown
fill_input("#seg0_to_display", "ICN")
time.sleep(2)
press_key("Tab")
```

**Gotcha:** The departure POI dropdown may block the destination input.
After filling departure, press Tab/Enter before filling destination.

### Step 2: Datepicker (FAILS — custom click-resistant component)

FlightHub uses a **custom JavaScript datepicker** (not `react-date-range`
as initially suspected). Standard click methods do NOT register:

| Method | Result |
|--------|--------|
| `element.click()` (JS) | ❌ No response |
| CDP `Input.dispatchMouseEvent` via `click_at_xy()` | ❌ No response |
| MouseEvent dispatch (`mousedown` + `mouseup` + `click`) | ❌ No response |
| `fill_input()` on date fields | ❌ No date input exists |

**Status: NOT automatable through the datepicker.** If a direct URL
approach exists (see above), use it instead. The datepicker behavior is
specific to FlightHub's implementation and was confirmed with screenshot
verification after each attempted click method.

### Step 3: Search Button

Selector: `.home-search-form-submit.search-form-submit.flights.fh`

This is a `<div>`, not a `<button>`. Click it with `click_at_xy()`:

```python
rect = js("JSON.stringify(document.querySelector('.home-search-form-submit').getBoundingClientRect())")
if rect:
    r = json.loads(rect)
    click_at_xy(r.x + r.width/2, r.y + r.height/2)
```

---

## Results Page

After navigating to the search URL, the page shows:

1. "Searching for the best flights..." dialog (may take 10-30s)
2. Flight cards appear as search completes

### Flight cards

Each flight card contains:
- Airline name and codes
- Departure/arrival times
- Number of stops + layover locations
- Total travel duration
- Price in selected currency
- "Select" button

### Extracting flight data

```python
# Wait for loading dialog to disappear
for attempt in range(12):  # up to ~60 seconds
    loading = js("document.querySelector('[class*=\"dialog\"]') ? true : false")
    if not loading:
        break
    time.sleep(5)

# Extract cards
listings = js("""
(function() {
    var cards = document.querySelectorAll(
        '[class*="flight-card"], [class*="result-item"], ' +
        '[class*="offer-card"], [class*="trip"]'
    );
    var result = [];
    var seen = new Set();
    cards.forEach(function(c) {
        var text = (c.innerText || '').trim();
        if (text.length > 50 && text.length < 1200 && !seen.has(text)) {
            seen.add(text);
            result.push(text.substring(0, 600));
        }
    });
    return JSON.stringify(result.slice(0, 30));
})()
""")
```

### CSS Selectors for Flight Cards

These are heuristic — the actual classnames are obfuscated, so a broad
selector is more reliable than specific classes:

- `[class*="flight-card"]`
- `[class*="result-item"]`
- `[class*="offer-card"]`
- `[class*="trip"]`
- `[class*="listing"]`

### Sorting

Not directly controllable via URL parameters beyond `order_by`:
`cheapest`, `fastest`, `best`.

---

## Key Lessons

1. **Direct URL first** — encode everything into the search URL parameters.
   Avoid the datepicker entirely — it is the most robust approach and works
   while the form interaction is blocked by the custom datepicker.

2. **real browser required** — FlightHub's Cloudflare challenge means you
   need a real browser (local Chrome via CDP, or a cloud browser with
   residential proxy). Headless mode may work but is more detectable.

3. **Datepicker is click-resistant** — if you must use the form approach,
   be prepared for the datepicker to reject all programmatic click methods.
   The only known workarounds are (a) direct URL or (b) inspecting network
   requests to find the backend API.

4. **Form submission is JS-driven** — the Search button is a `<div>` with
   a JS click handler, not an HTML `<button type="submit">`. Use CDP mouse
   events, not form submission APIs.

5. **POI autocomplete works** — unlike some other OTAs (Trip.com),
   FlightHub's airport autocomplete responds to `fill_input()` with real
   keyboard events. This is the one form element that can be automated.
