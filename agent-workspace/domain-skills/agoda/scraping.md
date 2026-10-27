# Agoda — Hotel search results and hotel pages

Field-tested against www.agoda.com on 2026-10-24 using a Browser Use cloud browser (search and hotel pages) and plain HTTP (city id lookup).

robots.txt (fetched 2026-10-24) allows `/search`, `/city/<slug>.html` and `/<slug>/hotel/<city>.html` for `User-agent: *`; it disallows `/*/hotel/all/`, `/book/`, `/account/` and the booking flow, which this skill never touches.

## Quick summary

- Plain HTTP GET of `/search?...` and of a hotel page returns HTTP 200 with a JavaScript shell (about 430 KB and 340 KB): empty `<title>`, no hotel names, no filled JSON-LD. You need a real browser for results and hotel data.
- Plain HTTP GET of a city landing page (`/city/bangkok-th.html`, about 87 KB) does contain the numeric city id in `"defaultSearchURL":"/search?city=9395..."`. Use that to build search URLs without the autocomplete widget.
- In the browser, each result is an `li[data-selenium="hotel-item"]` with `data-hotelid`. Name, star rating, review score and count (from an ARIA label or screen-reader text) and URL are on every card; the nightly price is on available cards only. Sold-out cards have no price and are kept with `price` None and `sold_out` True. 97 or 98 cards per page in these runs; 3 pages gave 294 cards, which were 289 unique properties in one run and 294 in another, and 293 cards (293 unique) in a third. The same hotel can appear on two pages (5 did in the first run), so block 2 dedupes by `hotel_id`.
- Cards are virtualized: only the ones near the viewport have content, so scroll and merge by `data-hotelid`. In a hidden background tab they never render, so block 2 raises unless you opt in to `FOREGROUND = True`.
- Pagination is a Next button; the URL does not change between pages.
- Hotel pages carry `<script type="application/ld+json">` of `@type: Hotel` (name, address, postal code, aggregateRating, image, description, map center) plus rendered blocks for stars, live review count, top amenities and the "from USD x" price.

## What works

### 1. City slug -> city id (plain HTTP, no browser)

City slugs are the `/city/<slug>.html` landing pages, for example `bangkok-th`, `tokyo-jp`. An unknown slug answers `302` to a page that returns `404`, so `city_id` raises `HTTPError 404`. Only 5xx answers are retried, all inside one 120 s deadline; 403 and 429 raise at once.

```python
import json, re, time, urllib.error, urllib.request

UA = "agoda-city-id-lookup/1.0 (python-urllib)"   # honest client name, no browser spoofing

def city_id(slug):
    """slug like 'bangkok-th' or 'tokyo-jp' (the /city/<slug>.html landing page)."""
    url = f"https://www.agoda.com/city/{slug}.html"
    deadline, delay = time.time() + 120, 5        # one deadline for every attempt and backoff
    while True:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
            with urllib.request.urlopen(req, timeout=max(1, min(30, deadline - time.time()))) as r:
                if r.geturl() != url:
                    raise ValueError(f"{url} redirected to {r.geturl()} - unknown city slug?")
                html = r.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:      # 403/429 = blocked or rate limited: stop, do not retry
            if e.code not in (500, 502, 503, 504) or time.time() + delay + 1 > deadline:
                raise
            time.sleep(delay); delay *= 2
    m = re.search(r'"defaultSearchURL":"/search\?city=(\d+)', html)
    if not m:
        raise ValueError(f"no city id on {url}")
    return int(m.group(1))

for slug in ["bangkok-th", "tokyo-jp"]:
    print(slug, city_id(slug))
    time.sleep(2)
```

Output on 2026-10-24:

```
bangkok-th 9395
tokyo-jp 5085
```

### 2. Search results for a city and dates, several pages (browser)

Builds the search URL with `urllib.parse.urlencode`, opens it, waits until the tab shows that URL (all requested parameters intact), scrolls each page until every card has rendered with its required fields, then clicks Next. `price` is the per-night price before taxes in `currency`, for the dates in the URL. `PAGES` is a cap: when more pages exist the run prints `PARTIAL` and saves `"complete": false`. A challenge or block page raises at once and is never retried. Run it in a dedicated browser: if the tab opened hidden, the block raises unless you set `FOREGROUND = True`, which brings the tab to the front of that Chrome window.

```python
import datetime, json, re, time, urllib.parse

CITY_ID = 9395       # Bangkok; get others with city_id("tokyo-jp") from the block above
PAGES = 3            # page cap; each results page holds ~100 properties
FOREGROUND = False   # opt-in: True may bring this tab to the front (visible to whoever uses that Chrome)
check_in = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
params = {"city": CITY_ID, "checkIn": check_in, "los": 2, "rooms": 1, "adults": 2,
          "children": 0, "locale": "en-us", "currency": "USD"}
SEARCH_URL = "https://www.agoda.com/search?" + urllib.parse.urlencode(params)

CARDS = r"""
JSON.stringify([...document.querySelectorAll('li[data-selenium="hotel-item"]')].map(li => {
  const q = s => li.querySelector(s);
  const id = li.getAttribute('data-hotelid');
  const a = q('a[data-selenium="hotel-name"]');
  const name = a ? a.innerText.trim() : '', href = a ? a.getAttribute('href') : null;
  const price = q('[data-selenium="display-price"]');
  const sold_out = /Sold out on your dates/i.test(li.innerText);
  // virtualized: a card counts only once id, name, url and (price or sold-out note) are all there
  if (!id || !name || !href || (!price && !sold_out)) return {id, empty: true};
  const star = q('[data-testid="rating-container"]');
  const sm = star && star.innerText.match(/([\d.]+) stars? out of 5/);
  // two layouts seen: data-element-name + aria-label, or data-testid + screen-reader text
  const rev = q('[data-element-name="property-card-review"],[data-testid="property-card-review"]');
  const rm = rev && ((rev.getAttribute('aria-label') || '') + ' ' + rev.innerText)
    .match(/([\d.]+) out of 10 with ([\d,]+) review/);
  // two href forms seen: /<slug>/hotel/<city>.html?... and /accom/property?propertyId=<id>&...
  const u = new URL(href, location.origin);
  const pid = u.searchParams.get('propertyId');
  return {
    hotel_id: id,
    name,
    stars: sm ? parseFloat(sm[1]) : null,
    review_score: rm ? parseFloat(rm[1]) : null,
    review_count: rm ? parseInt(rm[2].replace(/,/g, '')) : null,
    price: price ? parseFloat(price.innerText.replace(/,/g, '')) : null,
    currency: q('[data-selenium="hotel-currency"]')?.innerText || null,
    sold_out,
    promoted: /\bPromoted\b/.test(li.innerText),
    area: q('[data-selenium="area-city-text"]')?.innerText || null,
    url: u.pathname === '/accom/property' && pid ? u.origin + u.pathname + '?propertyId=' + pid
                                                 : u.origin + u.pathname,
  };
}))
"""

# Generic block-page markers. No challenge was seen on Agoda in these runs, so these are not Agoda-specific.
CHALLENGE = r"""
(() => {
  const text = (document.title + ' ' + (document.body ? document.body.innerText : '')).slice(0, 20000);
  return /captcha|are you a robot|verify (that )?you are (a )?human|unusual traffic|access denied|request blocked|pardon our interruption/i.test(text)
    || !!document.querySelector('iframe[src*="captcha"], iframe[src*="challenge"], #px-captcha, .g-recaptcha, .h-captcha');
})()
"""
LABEL = "document.querySelector('[data-selenium=\"pagination-text\"]')?.innerText || ''"

def try_js(expr, default=None):
    """Agoda pages can block the main thread for several seconds; evaluate then times out.
    No sleep here: every caller is a deadline loop that already sleeps between tries."""
    try:
        return js(expr)
    except RuntimeError:
        return default

def check_challenge():
    if try_js(CHALLENGE):
        raise RuntimeError(f"challenge or block page at {try_js('location.href')}: stop here, do not retry")

def on_requested_url(href, url):
    """Agoda appends ds=... and sort=...; every parameter we asked for must still be there unchanged."""
    want, got = urllib.parse.urlsplit(url), urllib.parse.urlsplit(href or "")
    got_q = dict(urllib.parse.parse_qsl(got.query))
    return (got.netloc, got.path) == (want.netloc, want.path) and \
        all(got_q.get(k) == v for k, v in urllib.parse.parse_qsl(want.query))

def page_numbers(label):
    m = re.fullmatch(r"Page (\d+) of (\d+)", (label or "").strip())
    return (int(m[1]), int(m[2])) if m else None

def wait_for_cards(timeout=60):
    deadline, href = time.time() + timeout, None
    while time.time() < deadline:
        check_challenge()
        href = try_js("location.href") or href
        if on_requested_url(href, SEARCH_URL) and \
                try_js("document.querySelector('li[data-selenium=hotel-item] a[data-selenium=hotel-name]') !== null"):
            return
        time.sleep(1)
    text = try_js("document.body.innerText.replace(/\\s+/g, ' ').trim().slice(0, 120)")
    raise RuntimeError(f"no hotel cards for the requested search after {timeout}s; at {href}; page text {text!r}")

def harvest_page(timeout=120):
    """Cards are virtualized: only ones near the viewport have content. Scroll and merge by id.
    If ids seen earlier are no longer in the DOM, the list was replaced under us: start the page over.
    One deadline covers every attempt; a challenge or the deadline raises, never a partial page."""
    deadline, attempt = time.time() + timeout, 1
    while True:
        check_challenge()
        rows, missing, gone = harvest_once(deadline)
        if not missing:
            return rows
        print(f"  {len(missing)} cards missing ({len(gone)} no longer in the DOM), attempt {attempt}")
        if not gone or time.time() + 3 >= deadline:   # no sleep after the last attempt
            raise RuntimeError(f"{len(missing)} cards never rendered: {missing[:5]}, "
                               f"visibility={try_js('document.visibilityState')}")
        time.sleep(3); attempt += 1

def harvest_once(deadline):
    rows, order = {}, []
    def collect():
        cards = json.loads(js(CARDS))
        if not cards:
            check_challenge()
            raise RuntimeError(f"no result cards on {try_js('location.href')}")
        for r in cards:
            hid = r.get("hotel_id") or r.get("id")
            if not hid:
                raise RuntimeError("result card without data-hotelid: markup changed?")
            if hid not in rows:
                order.append(hid); rows[hid] = None
            if not r.get("empty"):
                rows[hid] = r
    js("window.scrollTo(0, 0)"); time.sleep(1)
    bottom_hits = 0
    while bottom_hits < 3:                       # 3 checks at the bottom = lazy loading finished
        if time.time() > deadline:
            raise RuntimeError(f"page harvest passed its deadline at {len(order)} cards")
        collect()
        at_bottom = js("scrollY + innerHeight >= document.documentElement.scrollHeight - 5")
        bottom_hits = bottom_hits + 1 if at_bottom else 0
        js("window.scrollBy(0, 600)"); time.sleep(0.8)
    for hid in [h for h in order if rows[h] is None]:   # skipped or slow cards: visit each, wait up to 10 s
        js(f"document.querySelector('li[data-hotelid=\"{hid}\"]')?.scrollIntoView({{block: 'center'}})")
        card_deadline = min(deadline, time.time() + 10)
        while rows[hid] is None and time.time() < card_deadline:
            time.sleep(1); collect()
    missing = [h for h in order if rows[h] is None]
    gone = [h for h in missing if not js(f"!!document.querySelector('li[data-hotelid=\"{h}\"]')")]
    return [rows[h] for h in order if rows[h] is not None], missing, gone

def next_page(cur):
    """Click Next and wait until the label reads page cur + 1. Raises if there is no Next button."""
    js("document.querySelector('[data-selenium=\"pagination-next-btn\"]')?.scrollIntoView({block: 'center'})")
    time.sleep(1)
    box = js("(() => { const b = document.querySelector('[data-selenium=\"pagination-next-btn\"]'); "
             "if (!b) return null; const r = b.getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; })()")
    if not box:
        raise RuntimeError(f"no Next button on page {cur} (label {try_js(LABEL)!r})")
    click_at_xy(*box)
    deadline = time.time() + 60
    while time.time() < deadline:
        time.sleep(1)
        check_challenge()
        nums = page_numbers(try_js(LABEL))
        if nums and nums[0] == cur + 1:
            wait_for_cards(); return nums
    raise RuntimeError(f"page did not advance from {cur} (label {try_js(LABEL)!r})")

new_tab(SEARCH_URL)
wait_for_cards()
if js("document.visibilityState") != "visible":   # hidden tabs never render the lazy cards
    if not FOREGROUND:
        raise RuntimeError("tab is hidden, so cards will not render: use a dedicated browser "
                           "or set FOREGROUND = True to bring this tab to the front")
    activate_tab(current_tab())
print("search:", js("location.href"))
nums = page_numbers(try_js(LABEL))
if not nums:
    raise RuntimeError(f"unexpected pagination label {try_js(LABEL)!r}")
cur, total = nums
results, seen, dupes = [], set(), 0
while True:
    rows = harvest_page()
    print(f"Page {cur} of {total}: {len(rows)} properties")
    for r in rows:                                # the same hotel can show on two pages; keep the first
        if r["hotel_id"] in seen:
            dupes += 1; continue
        seen.add(r["hotel_id"]); results.append(dict(r, page=cur))
    if cur >= total or cur >= PAGES:
        break
    time.sleep(3)                                 # polite pacing between pages
    cur, total = next_page(cur)

status = {"complete": cur >= total, "pages_read": cur, "pages_total": total,
          "search_url": SEARCH_URL, "params": params}
print("unique", len(results), "duplicates dropped", dupes)
for r in results[:3]:
    print(r)
print("sold_out", sum(r["sold_out"] for r in results), "promoted", sum(r["promoted"] for r in results),
      "no price", sum(r["price"] is None for r in results),
      "no stars", sum(r["stars"] is None for r in results),
      "no review score", sum(r["review_score"] is None for r in results))
if not status["complete"]:
    print(f"PARTIAL: stopped at the PAGES = {PAGES} cap on page {cur} of {total}; more results exist")
json.dump(dict(status, results=results), open("agoda_results.json", "w"), indent=1, ensure_ascii=False)
```

Output on 2026-10-24, so `checkIn` is 2026-11-23 (trimmed):

```
search: https://www.agoda.com/search?city=9395&checkIn=2026-11-23&los=2&rooms=1&adults=2&children=0&locale=en-us&currency=USD&ds=zr2H4S2qsZq8000i
Page 1 of 75: 98 properties
Page 2 of 75: 98 properties
Page 3 of 75: 97 properties
unique 293 duplicates dropped 0
{'hotel_id': '51238093', 'name': 'Maison Hotel Bangkok', 'stars': 5, 'review_score': 8.9, 'review_count': 9464, 'price': 72, 'currency': 'USD', 'sold_out': False, 'promoted': False, 'area': 'Sukhumvit, Bangkok - City center', 'url': 'https://www.agoda.com/accom/property?propertyId=51238093', 'page': 1}
...
sold_out 23 promoted 4 no price 23 no stars 0 no review score 0
PARTIAL: stopped at the PAGES = 3 cap on page 3 of 75; more results exist
```

### 3. Hotel page basics (browser)

Run after block 2 in the same tab, or on its own. Uses JSON-LD for the stable fields and the rendered page for star rating, live review count, the "from" price and top amenities. It reuses the tab only if that tab is already on agoda.com, confirms the tab shows the requested URL (path, `propertyId` and stay parameters) before reading, raises on a challenge, and needs a visible tab like block 2 (same `FOREGROUND` opt-in). A hotel with no rate for the dates is returned with `from_price` None and `sold_out` True; a page that shows neither a price nor a sold-out heading in its room grid within 60 s raises.

```python
import datetime, json, re, time, urllib.parse

HOTEL_URLS = [   # any `url` values from the search rows
    "https://www.agoda.com/bless-residence/hotel/bangkok-th.html",
    "https://www.agoda.com/accom/property?propertyId=14654101",   # the other href form
    "https://www.agoda.com/accom/property?propertyId=14651963",   # had no rate for 2026-11-23 when tested; other dates may have one
]
FOREGROUND = False   # opt-in: True may bring this tab to the front (visible to whoever uses that Chrome)
check_in = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
STAY = {"checkIn": check_in, "los": 2, "rooms": 1, "adults": 2, "currencyCode": "USD"}

HOTEL = r"""
(() => {
  const t = s => document.querySelector(s)?.innerText.trim() || null;
  const ld = [...document.querySelectorAll('script[type="application/ld+json"]')]
    .map(s => { try { return JSON.parse(s.textContent); } catch (e) { return null; } })
    .find(d => d && d['@type'] === 'Hotel') || {};
  const star = (t('[data-selenium="mosaic-hotel-rating"]') || '').match(/([\d.]+) stars? out of 5/);
  const rev = (t('[data-selenium="review-score-with-test"],[data-testid="review-score-with-test"],[data-element-name="review-score-with-test"]') || '').match(/([\d.]+)[\s\S]*?([\d,]+) reviews/);
  const from = (t('[data-element-name="cheapest-room-price-property-nav-bar"]') || '').match(/from ([A-Z]{3}) ([\d,.]+)/);
  // no rate for these dates: no "from" bar, and the room grid's own h2 reads "Sold out!" or
  // "Unavailable on Agoda" (both seen). Other "sold out" text on the page (one room type) does not count.
  const grid = document.querySelector('#property-room-grid-root');
  const sold_out = !from && !!grid && [...grid.querySelectorAll('h2')]
    .some(h => /^(Sold out!?|Unavailable on Agoda)$/i.test(h.innerText.trim()));
  const pid = new URLSearchParams(location.search).get('propertyId');
  const geo = (ld.hasMap || '').match(/center=([-\d.]+)%2c([-\d.]+)/i);
  // free text: drop email addresses and phone-like numbers (9+ digits) before printing
  const redact = s => s.replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, '[email]')
    .replace(/\+?\d[\d ().-]{7,}\d/g, m => m.replace(/\D/g, '').length >= 9 ? '[phone]' : m);
  return JSON.stringify({
    jsonld_loaded: ld['@type'] === 'Hotel',   // the script tag exists empty at first, filled ~2 s later
    name: t('h1[data-selenium="hotel-header-name"]') || ld.name || null,
    // on /accom/property?propertyId=... pages JSON-LD url is the bare "/accom/property"
    url: ld.url && !ld.url.endsWith('/accom/property') ? ld.url
         : location.origin + location.pathname + (pid ? '?propertyId=' + pid : ''),
    stars: star ? parseFloat(star[1]) : null,
    address: t('[data-selenium="hotel-address-map"]'),
    postal: ld.address || null,
    lat: geo ? parseFloat(geo[1]) : null,
    lng: geo ? parseFloat(geo[2]) : null,
    review_score: rev ? parseFloat(rev[1]) : (ld.aggregateRating?.ratingValue ?? null),
    review_count: rev ? parseInt(rev[2].replace(/,/g, '')) : null,
    jsonld_rating: ld.aggregateRating || null,
    from_price: from ? {currency: from[1], amount: parseFloat(from[2].replace(/,/g, ''))} : null,
    sold_out,
    top_amenities: [...document.querySelectorAll('[data-element-name="atf-top-amenities-item"]')].map(e => e.innerText.trim()),
    image: ld.image ? new URL(ld.image, location.origin).href : null,
    description: redact(ld.description || '').slice(0, 300),
  });
})()
"""

# Generic block-page markers. No challenge was seen on Agoda in these runs, so these are not Agoda-specific.
CHALLENGE = r"""
(() => {
  const text = (document.title + ' ' + (document.body ? document.body.innerText : '')).slice(0, 20000);
  return /captcha|are you a robot|verify (that )?you are (a )?human|unusual traffic|access denied|request blocked|pardon our interruption/i.test(text)
    || !!document.querySelector('iframe[src*="captcha"], iframe[src*="challenge"], #px-captcha, .g-recaptcha, .h-captcha');
})()
"""

def try_js(expr, default=None):
    """The hotel page can block its main thread for 5-15 s while it renders; evaluate then times out.
    No sleep here: the loops below sleep between tries, and the error path must not wait."""
    try:
        return js(expr)
    except RuntimeError:
        return default

def check_challenge():
    if try_js(CHALLENGE):
        raise RuntimeError(f"challenge or block page at {try_js('location.href')}: stop here, do not retry")

def on_requested_url(href, url):
    """Agoda appends ds=...; every parameter we asked for must still be there unchanged."""
    want, got = urllib.parse.urlsplit(url), urllib.parse.urlsplit(href or "")
    got_q = dict(urllib.parse.parse_qsl(got.query))
    return (got.netloc, got.path) == (want.netloc, want.path) and \
        all(got_q.get(k) == v for k, v in urllib.parse.parse_qsl(want.query))

def open_hotel(url, timeout=90):
    u = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(u.query), **STAY)
    target = u._replace(query=urllib.parse.urlencode(query)).geturl()
    if current_tab()["url"].startswith("https://www.agoda.com/"):
        goto_url(target)                          # reuse this skill's own Agoda tab
    else:
        new_tab(target)                           # never navigate a tab that is on another site
    href, deadline = None, time.time() + timeout
    while time.time() < deadline:
        check_challenge()
        href = try_js("location.href") or href
        if on_requested_url(href, target) and \
                try_js("document.querySelector('h1[data-selenium=hotel-header-name]') !== null"):
            break
        time.sleep(1)
    else:
        raise RuntimeError(f"hotel page {target} not rendered after {timeout}s; last location {href}")
    if js("document.visibilityState") != "visible":
        if not FOREGROUND:
            raise RuntimeError("tab is hidden: use a dedicated browser or set FOREGROUND = True")
        activate_tab(current_tab())

def read_hotel(timeout=60):
    """Accept the page once name, url and JSON-LD are there and the price state is known:
    a "from" price, or the room grid's sold-out heading (then from_price is None and sold_out is True)."""
    d, deadline = None, time.time() + timeout
    while time.time() < deadline:
        check_challenge()
        raw = try_js(HOTEL)
        d = json.loads(raw) if raw else d
        if d and d["name"] and d["url"] and d["jsonld_loaded"] and (d["from_price"] or d["sold_out"]):
            return d
        time.sleep(2)
    raise RuntimeError(f"incomplete hotel page at {try_js('location.href')}: {d} "
                       "(no 'from' price and no sold-out heading in the room grid)")

for i, u in enumerate(HOTEL_URLS):
    if i:
        time.sleep(3)   # polite pacing between hotel pages
    open_hotel(u)
    print(json.dumps(read_hotel(), indent=1, ensure_ascii=False))
```

Output on 2026-10-24 (first hotel in full, description trimmed; then the sold-out one, trimmed):

```
{
 "jsonld_loaded": true,
 "name": "The Bless Hotel & Residence",
 "url": "https://www.agoda.com/bless-residence/hotel/bangkok-th.html",
 "stars": 4,
 "address": "10 Sukhumvit Soi 33, North Klongton, Wattana, Sukhumvit, Bangkok, Thailand, 10110",
 "postal": {
  "@type": "PostalAddress",
  "addressCountry": "Thailand",
  "addressLocality": "Sukhumvit",
  "addressRegion": "Bangkok",
  "postalCode": "10110",
  "streetAddress": "10 Sukhumvit Soi 33, North Klongton, Wattana"
 },
 "lat": 13.7337676461285,
 "lng": 100.567924976349,
 "review_score": 8.5,
 "review_count": 13034,
 "jsonld_rating": {
  "@type": "AggregateRating",
  "ratingValue": 8.5,
  "worstRating": 1,
  "bestRating": 10,
  "reviewCount": 12409
 },
 "from_price": {
  "currency": "USD",
  "amount": 56
 },
 "sold_out": false,
 "top_amenities": [
  "Free Wi-Fi",
  "Swimming pool",
  "Free parking",
  "Front desk [24-hour]",
  "Fitness center",
  "Restaurants",
  "Bar",
  "Airport transfer"
 ],
 "image": "https://pix8.agoda.net/hotelImages/177997/-1/794165056d07deceb10d1f2d79f00e4c.jpg?ce=0&s=1024x768",
 "description": "Experience Comfort and Convenience at The Bless Hotel & Residence, BangkokNestle..."
}
...
{
 "jsonld_loaded": true,
 "name": "Madison Bangkok",
 "url": "https://www.agoda.com/accom/property?propertyId=14651963",
 ...
 "from_price": null,
 "sold_out": true,
 ...
}
```

## Fields

Search card (block 2):

| Field | Source on the card | Example |
|---|---|---|
| `hotel_id` | `li[data-selenium="hotel-item"]` attribute `data-hotelid` | `"177997"` |
| `name` | `a[data-selenium="hotel-name"]` text | `"The Bless Hotel & Residence"` |
| `stars` | `[data-testid="rating-container"]` text `"4 stars out of 5"` | `4` (half stars appear as `3.5`, `4.5`) |
| `review_score` | `[data-element-name="property-card-review"]` (its `aria-label`) or `[data-testid="property-card-review"]` (its screen-reader text): `"Average rating Excellent 8.5 out of 10 with 13,032 reviews"` | `8.5` |
| `review_count` | same text | `13032` |
| `price` | `[data-selenium="display-price"]` | `54` (per night, before taxes) |
| `currency` | `[data-selenium="hotel-currency"]` | `"USD"` |
| `sold_out` | card text `"Sold out on your dates!"` | `false` |
| `promoted` | card text `"Promoted"` (Agoda says it earns more commission on these) | `false` |
| `area` | `[data-selenium="area-city-text"]` | `"Sukhumvit, Bangkok - City center"` |
| `url` | `a[data-selenium="hotel-name"]` `href`, search parameters stripped | `https://www.agoda.com/bless-residence/hotel/bangkok-th.html` or `https://www.agoda.com/accom/property?propertyId=177997` |
| `page` | results page the row was read from | `1` |

A card is accepted only when `hotel_id`, `name`, `url` and either `price` or the sold-out note are present. `agoda_results.json` holds `complete`, `pages_read`, `pages_total`, `search_url`, `params` (the dates and party size) and `results` (the rows above).

Hotel page (block 3):

| Field | Source | Example |
|---|---|---|
| `jsonld_loaded` | JSON-LD `@type == "Hotel"` parsed | `true` |
| `name` | `h1[data-selenium="hotel-header-name"]`, falls back to JSON-LD `name` | `"The Bless Hotel & Residence"` |
| `url` | JSON-LD `url` | canonical hotel URL |
| `stars` | `[data-selenium="mosaic-hotel-rating"]` text | `4` |
| `address` | `[data-selenium="hotel-address-map"]` | full one-line address |
| `postal` | JSON-LD `address` (PostalAddress) | street, locality, region, postalCode, country |
| `lat`, `lng` | `center=` parameter of JSON-LD `hasMap` | `13.7337676461285`, `100.567924976349` |
| `review_score`, `review_count` | `review-score-with-test` block text `"8.5 Excellent 13,034 reviews"` | `8.5`, `13034` |
| `jsonld_rating` | JSON-LD `aggregateRating` (1-10 scale) | `ratingValue 8.5, reviewCount 12409` |
| `from_price` | `[data-element-name="cheapest-room-price-property-nav-bar"]` text `"from USD 54"` | `{"currency": "USD", "amount": 54}`, or `null` when sold out |
| `sold_out` | no "from" bar and an `h2` in `#property-room-grid-root` reading `"Sold out!"` or `"Unavailable on Agoda"` | `false` |
| `top_amenities` | `[data-element-name="atf-top-amenities-item"]` | `["Free Wi-Fi", "Swimming pool", ...]` |
| `image` | JSON-LD `image` (protocol-relative, made absolute) | `https://pix8.agoda.net/hotelImages/...` |
| `description` | JSON-LD `description`, first 300 characters, email addresses and phone-like numbers (9+ digits) replaced | long marketing text |

## Gotchas

- **Cookie banner.** A "Manage Cookie Preference ... Dismiss" banner (`data-selenium="consent-banner"`) shows on every first load. It does not cover the results and the code above works without dismissing it.
- **Hidden tab = no cards.** In a background tab (`document.visibilityState == "hidden"`) cards stayed as empty shells (only "<name> opens in a new tab"); in one run 7 of them never filled however far you scrolled. `activate_tab(current_tab())` fixed it, but it changes the visible tab, so blocks 2 and 3 only call it when you set `FOREGROUND = True` and raise otherwise. In a fresh cloud browser `new_tab` reused the one blank tab, which was already visible, so no activation was needed; with other tabs open, `new_tab` opens a background tab and the hidden-tab error fires (seen in this run).
- **Virtualized list.** The page starts with 10 `li` elements, grows to 49 and then 98 while you scroll, and cards far from the viewport lose their inner content. Reading once after scrolling to the bottom gave only 44 filled cards out of 98. Collect on every scroll step and merge by `data-hotelid`; a final `scrollIntoView` pass picks up any card that was skipped.
- **Pagination.** The first page said "Page 1 of 75" for a 2026-11-23 check-in and "Page 1 of 74" for 2026-11-30. Next is `[data-selenium="pagination-next-btn"]`; `location.href` stays the same (Agoda appends `ds=...` and `sort=agodaRecommended`), so you cannot deep-link to page N. Block 2 waits for that label to read page N+1; it does not require the first card to change, since a hotel can repeat across pages. It stops on its own only when the label says `Page N of N`. A missing Next button before that, or a page that does not advance within 60 s, raises. The last page itself was not reached in this run.
- **Prices depend on dates.** The same hotel page showed "from USD 54" for a 2026-11-23 check-in and "from USD 72" for 2026-11-30, and "from USD 56" for 2026-11-23 a few hours later. Sold-out cards have no price block (24 of 289, 24 of 294 and 23 of 293 in three runs, all of them the cards with `price` None). Always keep `checkIn`, `los`, `adults`, `rooms` with the data.
- **Sold-out hotel pages.** Opening a hotel whose search card said "Sold out on your dates!" with the same dates (Madison Bangkok and Jasmine City Hotel Asoke for 2026-11-23) showed no "from" bar and, in the "Select your room" block, an `h2` "Sold out!" with "Our last room is already booked". About an hour later the same two pages showed the same line under an `h2` "Unavailable on Agoda" instead, and that block was `#property-room-grid-root`; block 3 accepts either heading there. An available hotel (propertyId 14654101) showed "Hurry up! 1 room type has already sold out for your dates!" in the same grid next to a "from USD 135" bar, so block 3 counts only the grid heading, and only when there is no "from" price. Block 3 returns sold-out pages with `from_price` None and `sold_out` True instead of waiting for a price that never comes.
- **Locale and currency.** Pass `locale=en-us&currency=USD` on search and `currencyCode=USD` on hotel pages; the regexes match English text ("stars out of 5", "reviews", "from USD").
- **Review counts disagree.** JSON-LD `aggregateRating.reviewCount` lags the rendered count (12,409 vs 13,034 for the same hotel the same minute; 16,192 vs 17,767 for another). Use the rendered number if you want what users see.
- **JSON-LD arrives late.** `script[data-selenium="bay-hotel-schema-json-ld"]` is in the DOM empty when the `h1` appears and is filled about 2 s later (0 then 23,163 characters). Reading too early returned `postal`, `lat`, `image` all `null`; block 3 waits for `jsonld_loaded`.
- **JSON-LD `url` on `/accom/property` pages** is the bare `https://www.agoda.com/accom/property`, so block 3 rebuilds the URL with `propertyId` there.
- **JSON-LD price is empty.** `priceRange` reads `"room rates from  per night (USD) - We Price Match!"` with no number. Read the price from the rendered "from" bar.
- **JSON-LD `hasMap`** is a Google Static Maps URL with Agoda's own key and signature in it. Parse only the `center=` coordinates; do not store or reuse the URL.
- **Slow main thread.** With three Agoda tabs open, `Runtime.evaluate` (and so `js(...)` and `wait_for_load()`) timed out after 5 s on a loading hotel page. The `try_js` wrapper retries until the overall deadline. Keep one Agoda tab open.
- **Card layouts vary between sessions.** Sessions on the same day got different card markup. Review block: either `data-element-name="property-card-review"` with the score in `aria-label`, or `data-testid="property-card-review"` with no `aria-label` and the same sentence as screen-reader text (code that only read the `aria-label` lost 285 of 294 scores). Hotel link: either `/<slug>/hotel/<city>.html?...` or `/accom/property?propertyId=<id>&...`; both open the same hotel page. Block 2 handles all of these.
- **List replaced after load.** In one run with a visible tab, 13 ids collected early never got content (the run failed loudly); Agoda also rewrites the URL after load (adds `ds=...` or `sort=agodaRecommended`). Block 2 checks whether the unfilled ids are still in the DOM and, if they are gone and no challenge is showing, harvests the page again; all attempts share one 120 s deadline and it raises rather than return a partial page. The cause was not pinned down.
- **Selectors.** Agoda's CSS class names are generated (`afab5-...`, `sc-...`); the `data-selenium`, `data-testid`, `data-element-name` and `aria-label` hooks used here matched in every layout seen in this run.
- **Stuck loading modal.** In one fresh cloud browser the search page sat on Agoda's "Just a moment! We're finding great stays for your dates and destination." modal for over 2 minutes with 0 cards; its script bundles from `cdn6.agoda.net` never loaded (resource status 0). The next fresh browser showed cards after 13 s. `wait_for_cards` raises after 60 s and prints the page text; do not loop on it.
- **Pacing and challenges.** Three result pages plus a handful of hotel pages, with 3 s between page loads, met no CAPTCHA, block page or HTTP 429. No published rate limit was found. Keep at least that pause. Blocks 2 and 3 check every wait loop for generic challenge markers (CAPTCHA text or iframes, "verify you are human", "access denied", "unusual traffic") and raise at once; since none was seen here, these markers are not Agoda-specific. On a challenge or a 403/429, stop and tell the user; do not retry, switch user agents or reshape the query.

## What does not work

- **Plain HTTP for search results or hotel pages.** Both return HTTP 200 shells with no hotel data (checked by counting hotel names and JSON-LD content in the response). The JSON-LD on hotel pages only exists after JavaScript runs.
- **Reading the list once.** Because of virtualization, a single read after scrolling misses most cards (44 of 98 filled in one test).
- **Deep-linking to page 2+.** Clicking Next does not change the URL, so there is no observed page parameter to request directly.
- **Background tabs.** Cards never render while the tab is hidden.
