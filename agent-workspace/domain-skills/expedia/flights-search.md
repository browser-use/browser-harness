# Expedia.ca — Flight Search Automation

Field-tested 2026-05-22 using browser-harness + Mac Chrome CDP with
residential Canadian ISP IP.

---

## Anti-Bot Protection

**Expedia uses DataDome (or similar behavior-based anti-bot).** Key facts:

- Blocks datacenter IPs with HTTP 429 ("Too Many Requests") and captcha
  pages ("Show us your human side…")
- Even headless Chromium with stealth init scripts gets blocked after
  1-2 requests from the same IP
- **With residential IP + real Chrome:** Works reliably — Canadian ISP IP
  through real Mac Chrome (not headless) passes DataDome checks without
  captchas or rate limiting
- **From datacenter IPs:** Use a cloud browser with residential proxies
  (Browser Use cloud, ScrapingBee, BrightData)

---

## Search URL Format

Expedia flight search can be initiated via a **direct URL** — this is the
**primary recommended approach**. It avoids the fragile datepicker,
airport autocomplete, and traveller widget entirely:

```
https://www.expedia.ca/Flights-Search?
  flight-type=roundtrip&mode=search&trip=roundtrip&
  leg1=from:YYZ,to:ICN,departure:2026/07/03TANYT&
  leg2=from:ICN,to:YYZ,departure:2026/07/25TANYT&
  passengers=adults:1&options=cabin:economy&
  sort=price%3Aa
```

URL parameters:
- `leg1` — outbound: `from:{IATA},to:{IATA},departure:{YYYY/MM/DD}TANYT`
- `leg2` — return: same format
- `passengers` — `adults:N,children:N`
- `options` — `cabin:economy|premium|business|first`
- `sort` — `price:a` (ascending), `price:d` (descending),
            `duration:a`, `departure:a`, `arrival:a`

### Navigation in browser-harness

Use the `goto_url()` + `new_tab()` fallback pattern — the pre-filled URL
already loads results directly, no Search button click needed:

```python
try:
    goto_url("https://www.expedia.ca/Flights-Search?...")
    wait_for_load(timeout=25)
    has_results = js('!!document.querySelector("[data-stid*=listing]")')
    if not has_results:
        raise Exception("no results loaded")
except:
    new_tab("https://www.expedia.ca/Flights-Search?...")
    wait_for_load(timeout=25)
```

**CRITICAL: Do NOT click the Search button.** The pre-filled URL already
returns search results. Clicking Search just reloads the same page, which
can reset applied filters and clear extracted results entirely.

---

## UI Search Flow (when URL approach fails)

When navigating to `https://www.expedia.ca/Flights` directly, the page has:

### Step 1: Select trip type

Radio buttons: "Roundtrip" / "One-way" / "Multi-city"

Selector: `button[data-testid*="trip-type"]` or `a[data-stid*="trip-type"]`

### Step 2: Origin (Leaving from)

Selector: `input[aria-label="Leaving from"]` or `#origin-airport`

Fill: clear first, then type `YYZ`, wait for autocomplete dropdown,
press Enter (or click first result).

```python
origin = page.locator("#origin-airport")
origin.fill("")
origin.type("YYZ", delay=100)
page.wait_for_timeout(1000)
page.keyboard.press("ArrowDown")
page.keyboard.press("Enter")
```

### Step 3: Destination (Going to)

Same pattern, field `#destination-airport` or `input[aria-label="Going to"]`.

### Step 4: Dates

Dates are a date-picker widget. **Do NOT use the date picker via clicks**
(highly unreliable, see lessons below). Instead:

- Set date fields via JavaScript to bypass the calendar widget:

```python
page.evaluate("""() => {
  const depart = document.querySelector('input[aria-label*="Depart"]');
  const ret = document.querySelector('input[aria-label*="Return"]');
  if (!depart) return false;
  // React controlled input — need native setter
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
  ).set;
  nativeSetter.call(depart, '2026-07-01');
  depart.dispatchEvent(new Event('input', { bubbles: true }));
  depart.dispatchEvent(new Event('change', { bubbles: true }));
  if (ret) {
    nativeSetter.call(ret, '2026-07-23');
    ret.dispatchEvent(new Event('input', { bubbles: true }));
    ret.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return true;
}()")
```

### Step 5: Travellers & Cabin

Toggle button: `button[data-testid="travelers-field-trigger"]`

Inside the panel:
- Adults stepper: +/- buttons within a container
- Cabin class: select element with options (Economy, Premium, Business, First)
- Close with "Done" button: find `button` containing text "Done"

### Step 6: Click Search

Search button locators:
- `button[data-testid="search-button"]`
- `button:has-text("Search")`
- Any `button` inside the search form

After clicking, wait for results:
```python
page.wait_for_url("**/Flights-Search**", timeout=15000)
page.wait_for_selector('[data-testid*="flight"]', timeout=30000)
```

---

## Results Page

After search, the page shows a list of flight combinations.

### Flight cards

Each flight option is a card. Selectors in the URL-preload results page:
- `div[data-stid*="listing"]` — **primary working selector** with
  browser-harness

Selectors for the form-submitted results page:
- `div[data-testid="listing"]`
- `div[role="listitem"]`

### Extracting flight data from cards

Using browser-harness `js()` with the URL-preload approach (up to 200
listings):

```python
result = []
for i in range(200):
    try:
        text = js('(document.querySelectorAll("[data-stid*=\\"listing\\"]")[%d]||{}).innerText' % i)
        if text:
            result.append(text[:500])
    except:
        pass
```

Using browser-harness `js()` with a single expression:

```python
listings = js("""
(function() {
    var cards = document.querySelectorAll('[data-stid*="listing"]');
    return JSON.stringify(Array.from(cards).slice(0, 30).map(function(c) {
        return c.innerText.substring(0, 500);
    }).filter(function(t) { return t.length > 50; }));
})()
""")
```

Using Playwright for structured extraction (form-submit result page):

```python
results = page.evaluate("""() => {
  const cards = document.querySelectorAll('div[data-testid="listing"], div[role="listitem"]');
  return Array.from(cards).slice(0, 20).map(card => {
    const priceEl = card.querySelector('[data-testid="price"], .uitk-type-500');
    const durationEl = card.querySelector('[data-testid="duration"]');
    const stopsEl = card.querySelector('[data-testid="stops"]');
    const airlineEl = card.querySelector('[data-testid="airline"]');
    const times = card.querySelectorAll('[data-testid="time"]');
    return {
      price: priceEl?.innerText?.trim(),
      duration: durationEl?.innerText?.trim(),
      stops: stopsEl?.innerText?.trim(),
      airline: airlineEl?.innerText?.trim(),
      depTime: times[0]?.innerText?.trim(),
      arrTime: times[1]?.innerText?.trim(),
    };
  }).filter(c => c.price);
}()")
```

### Sorting

Sort options: dropdown or button group — look for "Sort by" trigger,
then options: "Cheapest" / "Fastest" / "Best" / "Departure" / "Arrival".

### Stop Filters — Critical Quirk

**Expedia's stop checkboxes are exclusive — not inclusive.** Each
checkbox shows exactly that many stops, not "up to that many":

| Checkbox | Shows |
|----------|-------|
| Nonstop | 0 stops only (not "0 or 1") |
| 1 stop | Exactly 1 stop only |
| 2+ stops | 2+ stops only |

**To search for 0 OR 1 stop:**
1. Click "Nonstop" checkbox
2. Wait **5+ seconds** for page refresh
3. Click "1 stop" checkbox
4. Wait **5+ seconds** for page refresh

Each click triggers a full page reload with new results. Do NOT assume
they'll stack — wait for the reload to complete between clicks.

#### Finding stop filter checkboxes

Filter element IDs are dynamic (e.g., `NUM_OF_STOPS-0-:rs:`) with random
suffixes. Find by `aria-label` match:

```python
stops = js("""
JSON.stringify(
    Array.from(document.querySelectorAll('input[type=checkbox]'))
        .filter(i => (i.getAttribute('aria-label')||'').match(/stop/i))
        .map(i => ({id: i.id, label: i.getAttribute('aria-label'), checked: i.checked}))
)
""")
```

### Other Filters

Common filter panels:
- **Price range:** min/max inputs or slider
- **Airlines:** Checkbox list
- **Times:** Checkbox groups for morning/afternoon/evening

---

## Click-through to Fare Selection

To get the REAL total price (not the listing estimate):

1. Click a flight card/button → opens fare details or booking page
2. Look for "Continue" or "Select" button: `button:has-text("Select")`
3. On the fare selection page, extract the total:
   ```
   div[data-testid="price-summary"]
   div[data-testid="fare-total"]
   h4:has-text("Total")
   ```
4. Take screenshot to verify price

---

## Key Lessons

1. **URL-first strategy** — encode everything you can into the search URL
   parameter format. Avoid interacting with the datepicker, airport
   autocomplete, and traveller widget (all fragile).

2. **Direct URL loading** skips the landing page bot check entirely in
   many cases. Navigate to `Flights-Search?...` URL directly rather than
   clicking through from the homepage.

3. **Do NOT click Search with URL pre-load** — the pre-filled URL already
   returns results. Clicking Search reloads the same page and resets any
   applied filters.

4. **Residential IP + real Chrome works** — from a home ISP connection
   with a non-headless Chrome instance, Expedia's DataDome passes without
   captchas. Cloud browser with residential proxies only needed from
   datacenter IPs.

5. **Stop filters are exclusive** — each checkbox toggles a specific stop
   count. To show 0 AND 1 stop, click both sequentially with 5+ second
   waits for the page refresh between clicks.

6. **Filter IDs are dynamic** — use `aria-label` matching instead of
   hard-coded IDs for stop checkboxes and other filter elements.

7. **`goto_url()` + `new_tab()` fallback** — navigate the existing tab
   silently first; if results don't load, open a new tab as fallback.
   This avoids unnecessary macOS window popups.

8. **Fresh browser context per search** — don't reuse cookies/session
   across repeated searches from the same IP, as bot score accumulates.

9. **Use non-headless mode** with xvfb on headless servers — headless
   mode is heavily fingerprintable. The `--disable-blink-features=
   AutomationControlled` flag + `navigator.webdriver` override is
   essential.

10. **Wait for async loads** — after search or filter application, wait
    for the URL to change to `/Flights-Search*` and for flight elements
    to appear. 15-30s timeout recommended. Filter changes take 5+ seconds.
