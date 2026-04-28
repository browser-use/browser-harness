# Booking.com — Scraping & Data Extraction

Field-tested against booking.com on 2026-04-18 using `http_get` and the
`dml/graphql` JSON API. All tests run without a browser session.

---

## TL;DR

**`http_get` returns nothing useful from booking.com.** Every HTML page —
search results, hotel pages, city pages, the homepage — is intercepted by an
AWS WAF JS challenge before any content is served. The challenge requires
JavaScript execution to complete a cryptographic puzzle and set an
`aws-waf-token` cookie. Without a real browser, you get a ~4-8 KB stub page.

**What you can do without a browser:**
- Enumerate hotel/city/region URLs from XML sitemaps (Googlebot UA required).
- Read `robots.txt` for URL pattern documentation.
- Query the GraphQL endpoint `https://www.booking.com/dml/graphql` for schema
  exploration (no auth = internal errors, but validation errors reveal the
  schema).

**For all actual data extraction, use the browser (`goto` + `js`).**

---

## AWS WAF JS Challenge — What It Is

Every `http_get` request to `www.booking.com` receives one of two variants of
a WAF stub:

**Variant A (~3,962 bytes) — modern SDK:**
```html
<script src="https://www.booking.com/__challenge_{KEY}/{HASH}/challenge.js"></script>
<script>
  AwsWafIntegration.getToken().then(() => { window.location.href = newHref; });
</script>
```

**Variant B (~8,410 bytes) — with AJAX error reporting:**
Same AWS WAF SDK, plus an `XMLHttpRequest`-based error reporter that POSTs to
`https://reports.booking.com/chal_report`. This variant is more common on
non-browser UA strings.

**Detection in your code:**
```python
def is_waf_blocked(html: str) -> bool:
    return (
        'AwsWafIntegration' in html
        or 'awsWafCookieDomainList' in html
        or 'challenge.js' in html
        or len(html) < 10_000 and '<title></title>' in html
    )
```

**What the challenge does:**
1. Loads a 1.3 MB obfuscated JS file (`challenge.js`) from a path-keyed URL.
2. Executes a cryptographic proof-of-work puzzle client-side.
3. Sets an `aws-waf-token` cookie on the `booking.com` domain.
4. Redirects to the original URL with `?chal_t={timestamp}&force_referer=`
   appended.

This challenge **cannot be solved by `http_get`**. It requires a real JS
engine. A `bkng` session cookie is set on the first blocked response, but it
has no value without the WAF token.

**User agents tested — all blocked:**
- Chrome desktop (`Mozilla/5.0 ... Chrome/120`)
- iPhone/Safari mobile
- `Googlebot/2.1` (HTML pages only; sitemaps are whitelisted)
- Default `urllib` UA

---

## What `http_get` CAN Access

### 1. XML Sitemaps (URL discovery)

Booking.com whitelists sitemap paths for Googlebot. This lets you enumerate
millions of property, city, region, and attraction URLs without a browser.

```python
import gzip, re, urllib.request

GOOGLEBOT = {"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"}

def fetch_sitemap_index(url: str) -> list[str]:
    """Returns list of child sitemap URLs from an index sitemap."""
    xml = http_get(url, headers=GOOGLEBOT)
    return re.findall(r'<loc>(https://[^<]+)</loc>', xml)

def fetch_sitemap_gz(gz_url: str) -> list[str]:
    """Decompresses a gzipped sitemap and returns all <loc> URLs."""
    req = urllib.request.Request(gz_url, headers=GOOGLEBOT)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = gzip.decompress(r.read())
    return re.findall(r'<loc>(https://[^<]+)</loc>', data.decode())

# Example: get all en-gb hotel URLs
hotel_idx = http_get(
    "https://www.booking.com/sitembk-hotel-index.xml",
    headers=GOOGLEBOT
)
# 74 shards for en-gb; each shard has ~45,000-50,000 property URLs
en_gb_shards = re.findall(
    r'<loc>(https://www\.booking\.com/sitembk-hotel-en-gb\.\d+\.xml\.gz)</loc>',
    hotel_idx
)
# hotel_urls = fetch_sitemap_gz(en_gb_shards[0])  # ~50K URLs per shard
```

**Available sitemap categories (confirmed, 275 total):**

| Index URL | Content |
|-----------|---------|
| `sitembk-hotel-index.xml` | All properties (~74 en-gb shards, ~3.5M URLs) |
| `sitembk-city-index.xml` | City landing pages (~6 en-gb shards, ~44K cities) |
| `sitembk-region-index.xml` | Region landing pages |
| `sitembk-country-index.xml` | Country landing pages |
| `sitembk-attractions-index.xml` | Attractions |
| `sitembk-hotel-review-index.xml` | Review pages |
| `sitembk-themed-city-{type}-index.xml` | Category-specific city pages (70+ types: hostels, luxury, spa, ski, etc.) |

### 2. `robots.txt`

```python
robots = http_get("https://www.booking.com/robots.txt", headers={"User-Agent": "Mozilla/5.0"})
```

- Returns immediately, no WAF.
- 136 Disallow entries, 275 Sitemap declarations.
- Documents all URL structures (search results, hotel pages, booking flow, etc.).

### 3. GraphQL Schema Exploration (no auth)

The endpoint `https://www.booking.com/dml/graphql` is **not WAF-protected**.
It accepts POST requests and returns JSON. Without a session, most queries
return `Internal Server Error` from the backend (`irene` service), but
**GraphQL validation errors fire before the backend** and reveal the schema.

```python
import json, urllib.request, gzip

GQL_URL = "https://www.booking.com/dml/graphql?lang=en-gb"
GQL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.booking.com",
    "Referer": "https://www.booking.com/searchresults.html",
    "x-booking-context-action-name": "searchresults",
    "x-booking-context-aid": "376510",
    "x-booking-site-type-id": "1",
}

def gql(operation_name: str, query: str, variables: dict = None) -> dict:
    payload = {"operationName": operation_name, "query": query}
    if variables:
        payload["variables"] = variables
    req = urllib.request.Request(
        GQL_URL,
        data=json.dumps(payload).encode(),
        headers=GQL_HEADERS,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode())
```

**Confirmed Query type fields (schema, field-tested 2026-04-18):**

| Field | Input type | Notes |
|-------|-----------|-------|
| `searchQueries` | none | Root for hotel search; nested `.search(SearchQueryInput!)` |
| `searchBox` | `SearchBoxInput!` | Destination autocomplete / search form state |
| `searchProperties` | `SearchInput!` | Returns 500 without auth session |
| `propertyDetails` | `PropertyDetailsQueryInput!` | Returns 500 without auth session |
| `popularDestinations` | `PopularDestinationsInput!` | Returns validation error (type mismatch) |

**Important:** Booking.com GraphQL uses an **operation name whitelist** for
some operations. If you get `GRAPHQL_UNKNOWN_OPERATION_NAME`, try any of the
following confirmed working names: `SearchResultsPage`, `SearchQuery`,
`HotelCardsList`, `SearchResultsList`, `PropertySearch`, `BookingSearch`.

**Operation names that bypass the whitelist restriction** (all return
`{ data: { __typename: 'Query' } }` with `{ __typename }`):
- `SearchResultsPage` ✓ (confirmed, use this)

**The search query structure** (known but returns 500 without session):
```graphql
query SearchResultsPage($input: SearchQueryInput!) {
    searchQueries {
        search(input: $input) {
            __typename  # Returns SearchQueryResult type
        }
    }
}
```

With `SearchQueryInput` fields (inferred from URL parameters, confirmed
accepted by validation):
```json
{
  "dest_id": "-1456928",
  "dest_type": "CITY",
  "checkin": "2026-05-01",
  "checkout": "2026-05-03",
  "group_adults": "2",
  "no_rooms": "1",
  "group_children": "0",
  "selected_currency": "USD"
}
```

---

## URL Parameter Reference

### Search Results
`https://www.booking.com/searchresults.html`

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `ss` | string | `Paris` | Free-text: city, hotel name, address |
| `dest_id` | string | `-1456928` | Numeric city/region ID (negative = city) |
| `dest_type` | string | `CITY` | `CITY`, `REGION`, `COUNTRY`, `HOTEL`, `AIRPORT`, `DISTRICT`, `LANDMARK` |
| `checkin` | `YYYY-MM-DD` | `2026-05-01` | |
| `checkout` | `YYYY-MM-DD` | `2026-05-03` | |
| `group_adults` | int | `2` | |
| `no_rooms` | int | `1` | |
| `group_children` | int | `0` | |
| `age` | int (repeatable) | `5` | Child age; one per child |
| `selected_currency` | string | `USD` | ISO 4217 currency code |
| `lang` | string | `en-us` | BCP 47 locale |
| `nflt` | string | `ht_id=204;class=4` | Semicolon-separated filters |
| `order` | string | `price` | Sort: `price`, `class`, `review_score`, `distance`, `upsort_bh` |
| `offset` | int | `25` | Pagination (0-based, step 25) |
| `rows` | int | `25` | Results per page (max 25) |
| `map` | `1` | `1` | Map view mode |
| `src` | string | `searchresults` | Source context (cosmetic) |

**Common `nflt` filter codes:**
- `ht_id=204` — Hotels only
- `class=3;class=4;class=5` — Star rating
- `review_score=90` — Guest rating ≥ 9.0
- `fc=2` — Free cancellation
- `rm_types=…` — Room type
- `pri=1;pri=2` — Price tier (budget / mid / upscale)

### Property Pages
`https://www.booking.com/hotel/{country_code}/{hotel_slug}.html`

Confirmed from sitemap (74 shards, ~3.5M properties):
```
https://www.booking.com/hotel/{cc}/{slug}.html
https://www.booking.com/hotel/{cc}/{slug}.en-gb.html
https://www.booking.com/hotel/{cc}/{slug}.{lang}.html
```
- `cc` = 2-letter ISO country code (e.g., `fr`, `us`, `gb`, `de`, `jp`)
- `slug` = hotel name, lowercase, hyphen-separated
- Locale suffix optional; omit for default (English)

### City / Region / Country Pages
```
https://www.booking.com/city/{cc}/{city-slug}.html
https://www.booking.com/region/{cc}/{region-slug}.html
https://www.booking.com/country/{cc}.html
```

---

## Browser-Based Extraction (Required for All Data)

Since `http_get` is blocked, all actual data extraction requires the browser
(`goto` + `js`). The WAF challenge resolves automatically in Chrome.

### Initial Navigation

```python
# Always use new_tab() for the first Booking.com load in a session
tid = new_tab("https://www.booking.com/searchresults.html?ss=Paris&checkin=2026-05-01&checkout=2026-05-03&group_adults=2&no_rooms=1&selected_currency=USD")
wait_for_load()
wait(3)  # React hydration takes ~3s after readyState=complete

# Check for WAF challenge still running (rare in real Chrome)
url = page_info()["url"]
if "chal_t=" in url:
    wait(5)  # WAF challenge resolving
    wait_for_load()
```

### GDPR / Cookie Consent Banner (EU Visitors)

Shown to visitors with EU IP addresses or EU `Accept-Language` headers **after**
the WAF challenge resolves. It blocks interaction until dismissed.

```python
def dismiss_cookie_banner():
    # Booking.com uses data-testid="accept" on the Accept button
    accepted = js("""
        (function() {
            var btn = document.querySelector('[data-testid="accept"]')
                   || document.querySelector('#onetrust-accept-btn-handler')
                   || document.querySelector('[aria-label*="Accept"]');
            if (btn) { btn.click(); return true; }
            return false;
        })()
    """)
    return accepted

# Call immediately after load if you have an EU IP
if dismiss_cookie_banner():
    wait(1)
```

The consent banner does **not** appear in the WAF stub — it only renders after
the full React app loads. Non-EU visitors (US IP, `Accept-Language: en-US`)
may not see it at all.

### Search Results Page Extraction

```python
results = js("""
  Array.from(document.querySelectorAll('[data-testid="property-card"]')).map(el => ({
    name: el.querySelector('[data-testid="title"]')?.innerText?.trim(),
    url: el.querySelector('[data-testid="title-link"]')?.href,
    price: el.querySelector('[data-testid="price-and-discounted-price"]')?.innerText?.trim(),
    rating: el.querySelector('[data-testid="review-score"]')?.innerText?.trim(),
    stars: el.querySelectorAll('[data-testid="rating-stars"] svg').length,
    location: el.querySelector('[data-testid="address"]')?.innerText?.trim(),
    availability_note: el.querySelector('[data-testid="availability-rate-information"]')?.innerText?.trim(),
    is_genius: !!el.querySelector('[data-testid="genius-label"]'),
  }))
""")
```

**Field notes:**
- `data-testid="property-card"` — confirmed selector for result cards (as of
  2025-2026; Booking migrated from `sr-hotel` class to data-testid attributes).
- `data-testid="price-and-discounted-price"` — contains the nightly rate;
  may show original + discounted price together as text.
- `data-testid="review-score"` — contains both the numeric score (e.g.,
  `"9.2"`) and the label (e.g., `"Superb"`); use `.split('\n')[0]` for score.
- `data-testid="rating-stars"` — star rating icons; count SVG children for
  star count.
- Results are loaded asynchronously; 3s wait after `wait_for_load()` is
  required for all cards to render.

### Pagination

```python
# Method 1: Next page button
next_btn = js("document.querySelector('[data-testid=\"pagination-next\"]')?.href")
if next_btn:
    goto_url(next_btn)
    wait_for_load()
    wait(3)

# Method 2: Offset parameter (25 results per page)
current_url = page_info()["url"]
offset = 25  # next page
goto_url(current_url + f"&offset={offset}")
wait_for_load()
wait(3)
```

### Property / Hotel Page Extraction

```python
detail = js("""
  ({
    name: document.querySelector('[data-testid="property-name"]')?.innerText?.trim()
       || document.querySelector('h2.hp__hotel-name, h1.pp-hotel-name-title')?.innerText?.trim(),
    rating: document.querySelector('[data-testid="rating-squares"]')
              ? document.querySelectorAll('[data-testid="rating-squares"] svg').length
              : null,
    score: document.querySelector('[data-testid="review-score-right-component"] .ac4a7896c7')?.innerText
        || document.querySelector('[aria-label*="Scored"]')?.getAttribute('aria-label'),
    address: document.querySelector('[data-testid="PropertyHeaderAddressDesktop"]')?.innerText?.trim()
          || document.querySelector('[id="hotel_address"]')?.innerText?.trim(),
    description: document.querySelector('[data-testid="property-description-content"]')?.innerText?.trim()
              || document.querySelector('#property_description_content')?.innerText?.trim(),
    amenities: Array.from(document.querySelectorAll('[data-testid="facility-list-item"]'))
                    .map(e => e.innerText?.trim()).filter(Boolean),
    room_types: Array.from(document.querySelectorAll('[data-testid="roomstable-accordion"]'))
                     .map(el => ({
                       name: el.querySelector('[data-testid="room-type-name"]')?.innerText?.trim(),
                       price: el.querySelector('[data-testid="price-and-discounted-price"]')?.innerText?.trim(),
                     })),
    lat: document.querySelector('a[href*="maps.google"]')
           ?.href?.match(/[?&]q=([^&]+)/)?.[1]?.split(',')[0],
    lon: document.querySelector('a[href*="maps.google"]')
           ?.href?.match(/[?&]q=([^&]+)/)?.[1]?.split(',')[1],
  })
""")
```

### JSON-LD Schema (Property Pages)

Property pages embed JSON-LD when fully rendered in browser. The schema type
is `Hotel`:

```python
ld_json = js("""
  (function() {
    for (var s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        var d = JSON.parse(s.textContent);
        if (d['@type'] === 'Hotel' || d['@type'] === 'LodgingBusiness') return d;
      } catch(e) {}
    }
    return null;
  })()
""")
# Returns:
# {
#   "@type": "Hotel",
#   "name": "Hotel de Crillon",
#   "aggregateRating": {"ratingValue": "9.2", "reviewCount": "1423"},
#   "address": {"streetAddress": "10 Place de la Concorde", "addressLocality": "Paris", ...},
#   "geo": {"latitude": 48.865, "longitude": 2.321},
#   "starRating": {"ratingValue": 5}
# }
```

JSON-LD is **not present in the WAF stub** — it only exists in the fully
rendered page. `http_get` will never see it.

### Embedded JavaScript Data (`__NEXT_DATA__` / `b_hotel_data`)

Booking.com's React app may embed search state in `window.__NEXT_DATA__` or
legacy `b_hotel_data` globals. Access via:

```python
next_data = js("window.__NEXT_DATA__")    # dict or None
b_hotel   = js("window.b_hotel_data")    # dict or None — legacy pages
```

These globals are not present in the WAF stub and their availability depends
on page version. Prefer data-testid selectors which are more stable.

---

## Pricing Extraction Patterns

Booking.com shows prices per night with multiple formatting variants:

```python
price_patterns = js("""
  ({
    // Search results card price
    search_price: document.querySelector('[data-testid="price-and-discounted-price"]')?.innerText,
    // Property page room price
    room_price: document.querySelector('[data-testid="price-and-discounted-price"]')?.innerText,
    // Original (crossed-out) price before discount
    original_price: document.querySelector('[data-testid="recommended-units-price"] s')?.innerText
                 || document.querySelector('.prco-valign-middle-helper del')?.innerText,
    // "Price for X nights" summary
    total_price: document.querySelector('[data-testid="checkout-price-summary"]')?.innerText,
    // Genius discount tag
    genius_discount: document.querySelector('[data-testid="genius-rate-badge"]')?.innerText,
  })
""")
```

**Price display nuances:**
- Prices shown are **per night** by default; multiply by nights for total.
- Currency is controlled by `selected_currency` URL param or user account
  setting.
- Taxes/fees may or may not be included; look for `"Includes taxes and fees"`
  or `"+ taxes & fees"` text adjacent to the price element.
- The `data-testid="price-and-discounted-price"` element returns a single
  string that may contain both original and discounted price
  (e.g., `"US$400\nUS$320"`).

---

## WAF Detection & Handling in Browser

The WAF resolves automatically in a real Chrome session. To detect if
something went wrong:

```python
def check_booking_waf():
    url = page_info()["url"]
    html_snippet = js("document.body?.innerHTML?.slice(0, 500)") or ""
    return (
        "chal_t=" in url
        or "AwsWafIntegration" in html_snippet
        or "challenge-container" in html_snippet
    )

def wait_past_waf(timeout=15):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not check_booking_waf():
            return True
        wait(1)
    return False  # timed out — WAF didn't resolve

# Use after goto_url():
goto_url("https://www.booking.com/searchresults.html?ss=London&checkin=2026-06-01&checkout=2026-06-03&group_adults=2&no_rooms=1")
wait_for_load()
wait_past_waf()
wait(2)  # hydration
```

---

## Sitemap-Based URL Discovery Workflow

Use this when you need a list of property URLs for a given country or city,
without needing to scrape search results pages in the browser:

```python
import gzip, re, urllib.request

GOOGLEBOT = {"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"}

def get_hotel_urls_for_country(cc: str, lang: str = "en-gb", max_shards: int = 2) -> list[str]:
    """Returns property page URLs for a country from sitemaps. No browser needed."""
    idx_url = f"https://www.booking.com/sitembk-hotel-index.xml"
    idx = http_get(idx_url, headers=GOOGLEBOT)
    pattern = rf'<loc>(https://www\.booking\.com/sitembk-hotel-{lang}\.\d+\.xml\.gz)</loc>'
    shards = re.findall(pattern, idx)[:max_shards]
    
    urls = []
    for shard_url in shards:
        req = urllib.request.Request(shard_url, headers=GOOGLEBOT)
        with urllib.request.urlopen(req, timeout=60) as r:
            xml = gzip.decompress(r.read()).decode()
        all_urls = re.findall(r'<loc>(https://[^<]+)</loc>', xml)
        # Filter by country code
        country_urls = [u for u in all_urls if f"/hotel/{cc}/" in u]
        urls.extend(country_urls)
    return urls

# Example: get French hotel URLs (no browser needed, instant)
# french_hotels = get_hotel_urls_for_country("fr", max_shards=1)
# len(french_hotels) -> ~8,000+ URLs from one shard
```

---

## Gotchas

- **WAF blocks everything via `http_get`** — there is no User-Agent or header
  combination that bypasses it. The challenge is cryptographic, not heuristic.
- **WAF has two page sizes** — ~3,962 bytes (newer SDK, no AJAX reporter) and
  ~8,410 bytes (older with error reporting). Both are equally blocked.
- **Sitemaps whitelist Googlebot UA** — `Googlebot/2.1` UA works for sitemap
  XML/GZ files but NOT for hotel/city/search HTML pages.
- **GraphQL endpoint is unprotected** but useless without a valid Booking.com
  session (irene service requires authentication for all substantive queries).
- **GraphQL op-name whitelist**: introspection (`__schema`) is blocked by
  operation name restriction. Use field validation errors to probe the schema.
- **GDPR consent banner**: shown after WAF resolves, before React renders
  search results. Must be dismissed (click `[data-testid="accept"]`) before
  interacting with EU sessions. Non-EU IPs may not see it.
- **React hydration delay**: `wait_for_load()` fires before card data renders.
  Always add 2-3s of `wait()` after `wait_for_load()`.
- **`sr-hotel` class is legacy** — Booking.com migrated to data-testid
  attributes. Use `[data-testid="property-card"]`, not `.sr-hotel`.
- **Price parsing**: the price element often contains the full string
  `"US$400\nUS$320"` when a discount applies. Split on `\n` and take the last
  item for current price.
- **Offset pagination cap**: Booking caps results at 1,000 properties per
  search (offset 0–975, rows=25). For cities with >1,000 properties, use
  filters (`nflt`) to segment results.
- **Currency must be set via URL param**: `selected_currency=USD` in the search
  URL; the cookie-based currency selection may not persist across navigation.
- **`dest_id` for cities**: Paris = `-1456928`, Amsterdam = `-2140479`,
  London = `-2601889`. Negative integers indicate city-level destinations.
  Get the ID by reading it from the URL after using `ss=` search.
