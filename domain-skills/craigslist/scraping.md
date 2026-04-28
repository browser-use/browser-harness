# Craigslist — Scraping via http_get

Field-tested against sfbay.craigslist.org and multiple city subdomains on 2026-04-18.
`http_get` works without any bot detection — no CAPTCHA, no block, no rate limit observed.
Craigslist serves a full server-rendered HTML fallback (the `<ol class="cl-static-search-results">` block)
intended for no-JS browsers. This fallback contains **all matching results in one response** (300–360
items typical), regardless of the `s=` offset parameter. No browser needed.

## Key discovery: static HTML returns everything at once

When you `http_get` a Craigslist search URL, the server includes a `<ol class="cl-static-search-results">`
block that contains every matching listing (up to ~360) in a single HTML response. The `s=` pagination
parameter is ignored by the static renderer — it is only meaningful for the JS-driven XHR path used by
real browsers. For scraping purposes, this means:

- One `http_get` call per search query returns the full result set (no pagination loop needed).
- For broader searches, narrow via `query=`, `min_price=`, `max_price=`, and category code in the URL.
- If you need more than ~360 results, you must use a headless browser with JS. For most tasks,
  one request is sufficient.

## URL patterns

### City subdomains
```
https://{city}.craigslist.org/search/{category_code}?query=...
```

Confirmed working cities (exact subdomain names):

| City           | Subdomain        |
|----------------|------------------|
| SF Bay Area    | `sfbay`          |
| New York       | `newyork`        |
| Chicago        | `chicago`        |
| Los Angeles    | `losangeles`     |
| Seattle        | `seattle`        |
| Boston         | `boston`         |
| Miami          | `miami`          |
| Denver         | `denver`         |
| Austin         | `austin`         |
| Portland       | `portland`       |
| San Diego      | `sandiego`       |
| Phoenix        | `phoenix`        |

### Category codes (confirmed working)

| Code  | Category                  |
|-------|---------------------------|
| `sss` | For Sale — all            |
| `for` | For Sale — general        |
| `ela` | Electronics (listings)    |
| `ele` | Electronics (search)      |
| `fua` | Furniture                 |
| `clo` | Clothing & accessories    |
| `spo` | Sporting goods            |
| `toy` | Toys & games              |
| `cto` | Cars+trucks — by owner    |
| `cta` | Cars+trucks — by dealer   |
| `hhh` | Housing — all             |
| `apa` | Apartments                |
| `roo` | Rooms & shares            |
| `sub` | Sublets & temporary       |
| `jjj` | Jobs — all                |
| `sof` | Software/QA/DBA jobs      |
| `bbb` | Services — all            |
| `ggg` | Gigs — all                |
| `com` | Community                 |
| `eve` | Events                    |
| `vol` | Volunteers                |

### Query parameters

| Parameter     | Effect                                         |
|---------------|------------------------------------------------|
| `query=`      | Keyword search                                 |
| `sort=rel`    | Sort by relevance (default)                    |
| `sort=date`   | Sort by newest first                           |
| `sort=priceasc`  | Price low to high                           |
| `sort=pricedsc`  | Price high to low                           |
| `min_price=`  | Minimum price filter                           |
| `max_price=`  | Maximum price filter                           |
| `condition=10` | New (for-sale listings)                       |
| `condition=20` | Like new                                      |
| `condition=30` | Excellent                                     |
| `condition=40` | Good                                          |
| `condition=50` | Fair                                          |
| `condition=60` | Salvage                                       |
| `bedrooms=`   | Number of bedrooms (housing only)              |
| `auto_make_model=` | Car make/model filter (cars category)   |
| `s=`          | Pagination offset — **ignored in static HTML** |

### Example URLs
```python
# For-sale keyword search
"https://sfbay.craigslist.org/search/sss?query=macbook&sort=rel"

# Price-filtered electronics
"https://sfbay.craigslist.org/search/ela?query=iphone&min_price=100&max_price=500"

# Apartments, 2 bedrooms, price range
"https://sfbay.craigslist.org/search/apa?bedrooms=2&min_price=1000&max_price=2500"

# Cars by owner, Toyota
"https://sfbay.craigslist.org/search/cto?auto_make_model=toyota"

# Jobs in another city
"https://chicago.craigslist.org/search/jjj?query=python+developer"
```

## Listing card HTML structure

Each listing is an `<li class="cl-static-search-result">` inside `<ol class="cl-static-search-results">`.

```html
<li class="cl-static-search-result" title="MacBook Air M2 256GB 8GB RAM">
  <a href="https://sfbay.craigslist.org/sby/ele/d/san-jose-macbook-air-m2/7928508295.html">
    <div class="title">MacBook Air M2 256GB 8GB RAM</div>
    <div class="details">
      <div class="price">$900</div>
      <div class="location">San Jose</div>
    </div>
  </a>
</li>
```

Fields available in the listing card:
- **Title**: `title` attribute on `<li>` OR text inside `<div class="title">`
- **URL**: `href` on the `<a>` tag — always a full absolute URL
- **Price**: `<div class="price">` — may be absent on free/contact-for-price listings
- **Location/neighborhood**: `<div class="location">` — neighborhood name or city
- **Post ID**: last segment of the URL before `.html` (e.g. `/7928508295.html` → `7928508295`)

URL pattern: `https://{city}.craigslist.org/{area}/{category_code}/d/{slug}/{post_id}.html`

## Parsing search results (field-tested)

```python
import re
from helpers import http_get

def search_craigslist(city, category, query, min_price=None, max_price=None):
    params = f"query={query.replace(' ', '+')}&sort=rel"
    if min_price: params += f"&min_price={min_price}"
    if max_price: params += f"&max_price={max_price}"
    url = f"https://{city}.craigslist.org/search/{category}?{params}"
    headers = {"User-Agent": "Mozilla/5.0"}
    html = http_get(url, headers=headers)

    listings = re.findall(
        r'<li class="cl-static-search-result" title="([^"]+)"[^>]*>\s*'
        r'<a href="([^"]+)"[^>]*>.*?'
        r'<div class="price">([^<]*)</div>.*?'
        r'<div class="location">\s*([^<]*?)\s*</div>',
        html, re.DOTALL
    )

    results = []
    for title, url, price, location in listings:
        pid_match = re.search(r'/(\d+)\.html$', url)
        results.append({
            "post_id": pid_match.group(1) if pid_match else None,
            "title": title,
            "url": url,
            "price": price.strip() or None,  # None if listing has no price
            "location": location.strip(),
        })
    return results

# Usage
results = search_craigslist("sfbay", "sss", "macbook pro", max_price=1000)
for r in results[:5]:
    print(r["post_id"], r["price"], r["location"], r["title"][:50])
```

### Handling missing price

Listings without a price have no `<div class="price">` element. The regex above returns an empty string
for `price`; the example converts that to `None`. A more robust extraction:

```python
def parse_listings(html):
    results = []
    for block in re.findall(r'<li class="cl-static-search-result"(.*?)</li>', html, re.DOTALL):
        title = re.search(r'title="([^"]+)"', block)
        url   = re.search(r'href="([^"]+)"', block)
        price = re.search(r'<div class="price">([^<]+)</div>', block)
        loc   = re.search(r'<div class="location">\s*([^<]*?)\s*</div>', block)
        if not url: continue
        url_str = url.group(1)
        pid = re.search(r'/(\d+)\.html$', url_str)
        results.append({
            "post_id": pid.group(1) if pid else None,
            "title": title.group(1) if title else None,
            "url": url_str,
            "price": price.group(1).strip() if price else None,
            "location": loc.group(1).strip() if loc else None,
        })
    return results
```

## Individual listing page extraction

Listing pages are also fully server-rendered. All fields are present in the raw HTML.

```python
def get_listing(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    html = http_get(url, headers=headers)

    title    = re.search(r'<span id="titletextonly">([^<]+)</span>', html)
    price    = re.search(r'<span class="price">(\$[\d,]+)</span>', html)
    # Location is in parentheses right after the price span
    location = re.search(
        r'<span class="price">[^<]+</span><span>\s*\(([^)]+)\)\s*</span>', html
    )
    posted   = re.search(r'class="date timeago"[^>]+datetime="([^"]+)"', html)
    post_id  = re.search(r'post id:\s*(\d+)', html)

    # Description body
    body_block = re.search(r'section id="postingbody"[^>]*>(.*?)</section>', html, re.DOTALL)
    body_text  = ""
    if body_block:
        raw = re.sub(r'<[^>]+>', '', body_block.group(1)).strip()
        # Remove the "QR Code Link to This Post" print-only block
        body_text = re.sub(r'QR Code Link to This Post\s*', '', raw).strip()
        body_text = re.sub(r'\s+', ' ', body_text)

    # Images
    images = re.findall(r'https://images\.craigslist\.org/[^\s"\']+_600x450\.jpg', html)

    # Attributes (condition, make, model, etc.)
    attrs = {}
    for labl, valu in re.findall(
        r'<span class="labl">([^<]+)</span>.*?<span class="valu">\s*(?:<[^>]+>\s*)*([^<\n]+?)(?:\s*</|\s*<a)',
        html, re.DOTALL
    ):
        attrs[labl.strip().rstrip(':')] = valu.strip()

    return {
        "post_id":  post_id.group(1) if post_id else None,
        "title":    title.group(1) if title else None,
        "price":    price.group(1) if price else None,
        "location": location.group(1) if location else None,
        "posted":   posted.group(1) if posted else None,  # ISO 8601 with TZ
        "body":     body_text,
        "images":   images,
        "attrs":    attrs,
    }
```

### Sample output — for-sale listing
```python
{
    "post_id":  "7917381408",
    "title":    "Brand new iphone 15 case and screen protector",
    "price":    "$6",
    "location": "cupertino",
    "posted":   "2026-02-24T16:08:38-0800",
    "body":     "I bought a new phone. These are brand new! Plz lmk if you are interested.",
    "images":   ["https://images.craigslist.org/00e0e_xxx_600x450.jpg"],
    "attrs":    {"condition": "like new", "make / manufacturer": "Apple", "model name / number": "iPhone 15 Plus"},
}
```

### Housing-specific fields

Housing listings have `<span class="attr important">` blocks for bedrooms/bathrooms and square footage,
separate from the `<div class="attr">` attribute grid:

```python
# BR/BA
br_ba  = re.search(r'(\d+)BR\s*/\s*(\d+(?:\.\d+)?)Ba', html)
# Square footage
sqft   = re.search(r'(\d+)ft<sup>2</sup>', html)

if br_ba: bedrooms, bathrooms = br_ba.groups()
if sqft:  sqft_val = sqft.group(1)
```

## JSON-LD structured data (alternative extraction path)

Each search page includes an `ItemList` JSON-LD block with up to 330 items. Useful when you want
structured data (price as float, geo coordinates) without regex parsing of HTML:

```python
import json, re
from helpers import http_get

html = http_get("https://sfbay.craigslist.org/search/sss?query=laptop", headers={"User-Agent": "Mozilla/5.0"})
ld_blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)

for raw in ld_blocks:
    data = json.loads(raw)
    if data.get('@type') == 'ItemList':
        for item in data['itemListElement']:
            listing = item['item']
            print(
                listing.get('name'),
                listing.get('offers', {}).get('price'),
                listing.get('offers', {}).get('priceCurrency'),
                listing.get('offers', {}).get('availableAtOrFrom', {}).get('address', {}).get('addressLocality'),
            )
```

JSON-LD item fields available: `name`, `description`, `image` (list of URLs),
`offers.price` (float string e.g. `"900.00"`), `offers.priceCurrency`, `offers.availableAtOrFrom.address`,
`offers.availableAtOrFrom.geo.latitude`, `offers.availableAtOrFrom.geo.longitude`.

Note: JSON-LD items do not include the listing URL or post ID — use the HTML parser for those.
Combine both: use JSON-LD for price/geo, HTML for URL/post ID.

## Pagination behavior

The `s=` offset parameter in the URL is only respected by the JS-driven XHR layer in a real browser.
When accessed via `http_get`, the static HTML fallback renders all results regardless of `s=`:

```
s=0   → same 342 listings
s=120 → same 342 listings  (confirmed identical URL sets)
s=300 → same 342 listings
```

**Recommendation**: Do not attempt pagination via `http_get`. Use search filters to narrow results:

```python
# Instead of paginating, narrow by price range
under_500 = search_craigslist("sfbay", "sss", "macbook", max_price=500)
over_500  = search_craigslist("sfbay", "sss", "macbook", min_price=501)
```

If true pagination is required (e.g. you need more than 350 results), you must use a browser session
with `goto_url()` + `wait_for_load()`.

## Bot detection

None observed. Craigslist does not block `http_get` requests. During testing:
- All 6+ test cities returned full HTML (HTML size 174K–530K bytes per page)
- No CAPTCHA page, no redirect to `robot-check`, no `403`
- No cookie or session required
- Works with minimal `User-Agent` header: `"Mozilla/5.0"` is sufficient

Defensive check (in case behavior changes):

```python
def is_blocked(html):
    return (
        len(html) < 5000 or
        "blocked" in html[:2000].lower() or
        "captcha" in html[:2000].lower() or
        "cl-static-search-result" not in html
    )
```

## Gotchas

- **`data-pid` does not exist in static HTML**: Old Craigslist used `data-pid` attributes. The current
  static renderer uses `<li class="cl-static-search-result">` with title attribute and embedded `<a href>`.
  Do not search for `data-pid`, `result-row`, or `cl-search-result` — they are absent.

- **Post ID comes from the URL, not an attribute**: Extract it as the numeric segment before `.html`
  in the listing URL: `re.search(r'/(\d+)\.html$', url).group(1)`.

- **Price may be absent**: Free listings and "contact for price" listings have no `<div class="price">`.
  The regex returns an empty string; convert to `None`.

- **`s=` pagination is a no-op in static HTML**: The fallback renderer always returns the full result set.
  Don't loop over pages — filter instead.

- **HTML entities in titles**: Titles may contain `&amp;`, `&quot;`, etc. Use
  `html.unescape(title)` from the standard library if you need clean text.

- **URL structure varies by area**: The area code in the URL (`/sby/`, `/sfc/`, `/eby/`) is the sub-area
  of the city (e.g. South Bay, San Francisco, East Bay). It is part of the listing URL but not needed
  for constructing search URLs (which use the city subdomain only).

- **`<li class="cl-static-hub-links">` is not a listing**: The first `<li>` in the results `<ol>` is
  a "see also" block. The regex patterns above skip it automatically because it has no `title` attribute.

- **JSON-LD count < HTML count**: JSON-LD block may contain ~330 items while the HTML block shows ~350.
  The HTML parser is authoritative; JSON-LD is a secondary data source.

- **Body text contains print-only junk**: The `<section id="postingbody">` starts with a
  "QR Code Link to This Post" print-only element. Strip it with a simple string replacement
  (shown in the extractor above).

- **HTML-escaped body text**: Description bodies may contain `&amp;`, `&lt;`, etc. Unescape if needed:
  ```python
  import html as html_lib
  body_clean = html_lib.unescape(body_text)
  ```
