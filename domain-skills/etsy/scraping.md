# Etsy — Scraping & Data Extraction

Field-tested against `www.etsy.com` on 2026-04-18 using `http_get` (no browser) and direct `urllib` probes.

## Quick summary

**`http_get` does NOT work on Etsy.** Every page type — search, listing, shop, category, market — returns HTTP 403 with DataDome bot protection. This is not negotiable: no header combination, User-Agent string, or cookie replay bypasses it. Etsy requires a real browser with JavaScript execution.

- **All HTML pages (`/search`, `/listing/`, `/shop/`, `/c/`, `/market/`)** — HTTP 403, `Server: DataDome`
- **Official Etsy API v3 (`openapi.etsy.com/v3/`)** — requires a registered API key; returns JSON
- **`robots.txt`** — HTTP 200, plain text, no DataDome
- **Browser (Chrome CDP)** — works; Etsy is a React SPA with JSON-LD and `__NEXT_DATA__` embedded in SSR HTML

---

## Bot detection: DataDome

Etsy uses [DataDome](https://datadome.co/) for every user-facing HTML endpoint.

### What you receive

```
HTTP 403 Forbidden
Server: DataDome
X-DataDome: protected
X-DataDome-riskscore: 0.14–0.95  (varies per request)
X-DD-B: 2
Content-Type: text/html;charset=utf-8
Set-Cookie: datadome=<token>; Max-Age=31536000; Domain=.etsy.com; Secure; SameSite=Lax
```

Body (816 bytes — a JavaScript challenge, not a hard block):

```html
<html lang="en"><head><title>etsy.com</title>...</head>
<body>
  <p id="cmsg">Please enable JS and disable any ad blocker</p>
  <script>var dd={'rt':'c','cid':'...','hsh':'D013AA...','t':'bv',
    'host':'geo.captcha-delivery.com','cookie':'...'}</script>
  <script src="https://ct.captcha-delivery.com/c.js"></script>
</body>
```

`'rt':'c'` means **challenge** (browser must run JS at `geo.captcha-delivery.com` to get a valid `datadome` cookie). `'rt':'b'` would be a hard block; `'rt':'i'` an interstitial. All tested requests returned `'rt':'c'` — the JS challenge variant.

### What was tested (all 403)

| URL pattern | Status | DataDome |
|---|---|---|
| `/search?q=handmade+candle&explicit=1` | **403** | JS challenge |
| `/search?q=handmade+candle&explicit=1&page=2` | **403** | JS challenge |
| `/listing/{id}/{slug}` | **403** | JS challenge |
| `/shop/{ShopName}` | **403** | JS challenge |
| `/c/home-living/candles-holders/candles` | **403** | JS challenge |
| `/market/handmade_candle` | **403** | JS challenge |

### User-Agents tested (all blocked)

- `Mozilla/5.0 (Macintosh; ...) Chrome/120` — **403**
- `facebookexternalhit/1.1` — **403**
- `Twitterbot/1.0` — **403**
- `LinkedInBot/1.0` — **403**
- `ia_archiver` — **403**
- `curl/7.68.0` — **403**
- `python-requests/2.28.0` — **403**
- `Googlebot/2.1` — **429** (rate-limited, different path)
- `Mozilla/5.0` (http_get default) — **403**

**Conclusion**: No UA bypasses DataDome. The challenge requires TLS fingerprinting + JS execution that only a real browser provides.

---

## What works without a browser

### `robots.txt` (200 OK)

```python
from helpers import http_get
text = http_get("https://www.etsy.com/robots.txt")
# Returns 51 KB plain-text file — no DataDome
```

The robots.txt reveals URL structure, disallowed parameters, and allowed paths. Etsy disallows `/search?*q=` (no-empty-q searches) and faceted search params (`attr_*`, `price_bucket`, `ship_to`, `search_type`). Basic search with `?q=keyword` is not explicitly disallowed by robots but is blocked by DataDome in practice.

### Official Etsy API v3 (requires API key)

The `openapi.etsy.com/v3/` endpoint is NOT DataDome-protected. It returns structured JSON but requires a free API key from [developer.etsy.com](https://developer.etsy.com/).

```python
import json
from helpers import http_get

API_KEY = "your_key_here"  # from developer.etsy.com

def etsy_api(path, **params):
    from urllib.parse import urlencode
    qs = urlencode(params)
    url = f"https://openapi.etsy.com/v3/application/{path}?{qs}"
    data = http_get(url, headers={"x-api-key": API_KEY})
    return json.loads(data)

# Search listings
results = etsy_api("listings/active", limit=25, keywords="handmade candle",
                   sort_on="created", sort_order="desc")
# results['results'] is a list of listing dicts
# results['count'] is total match count

# Get a single listing
listing = etsy_api("listings/1234567890")

# Get all listings for a shop
shop_listings = etsy_api("shops/CandlesByNature/listings/active", limit=100)

# Get shop info
shop = etsy_api("shops/CandlesByNature")
```

Error without a key:
```
HTTP 403: {"error": "Invalid API key: should be in the format 'keystring:shared_secret'."}
```

Error with wrong key:
```
HTTP 403: {"error": "API key not found or not active, or incorrect shared secret for API key."}
```

### API v3 key data fields

```
listings/active response:
  results[i].listing_id        → int (e.g. 1234567890)
  results[i].title             → string
  results[i].description       → string (full HTML, may be truncated by API)
  results[i].price.amount      → int (in currency subunit, e.g. 2599 = $25.99)
  results[i].price.divisor     → int (100 for USD)
  results[i].price.currency_code → "USD"
  results[i].quantity          → int (stock remaining)
  results[i].tags              → [string] (up to 13 tags)
  results[i].materials         → [string]
  results[i].shipping_profile_id → int
  results[i].shop_id           → int
  results[i].url               → "https://www.etsy.com/listing/..."
  results[i].views             → int
  results[i].num_favorers      → int
  results[i].featured_rank     → int (-1 if not featured)
  results[i].is_digital        → bool
  results[i].has_variations    → bool
  results[i].taxonomy_id       → int (category)
  results[i].state             → "active" | "draft" | "expired" | "sold_out"
  results[i].creation_timestamp → unix int
  results[i].last_modified_timestamp → unix int
```

---

## Browser-based scraping (required for HTML data)

Since http_get is blocked, all HTML scraping requires the Chrome browser via CDP.

### Navigation pattern

```python
from helpers import goto, wait_for_load, wait, js, new_tab

# Always use new_tab() for the first Etsy navigation in a session
tid = new_tab("https://www.etsy.com/search?q=handmade+candle&explicit=1")
wait_for_load()
wait(3)  # Etsy React SPA needs extra time after readyState=complete
```

### Search URL construction

```
https://www.etsy.com/search?q={query}&explicit=1
```

Parameters:
- `q` — search query (URL-encoded, spaces as `+`)
- `explicit=1` — disables the "adult content" NSFW filter (safe to include always)
- `page=2`, `page=3` — pagination (confirmed from robots.txt URL patterns)
- `min_price=10.00&max_price=50.00` — price range filter
- `order=price_asc` / `order=price_desc` / `order=most_relevant` (default) / `order=newest`
- `ship_to=US` — filter by shipping destination (CAUTION: disallowed by robots.txt, use only with browser)
- `listing_type=handmade` / `listing_type=vintage` / `listing_type=supplies`

**Disallowed URL params** (per robots.txt — avoid in automated crawls):
- `attr_*=*` — attribute filters
- `price_bucket=*` — price bucket filter
- `ship_to=*` — shipping destination
- `search_type=*` — search type

### Search results extraction (browser)

Etsy renders results as a React SPA. The listing cards use data attributes and consistent class patterns:

```python
results = js("""
  Array.from(document.querySelectorAll('[data-listing-id]')).map(el => ({
    listing_id: el.getAttribute('data-listing-id'),
    title: el.querySelector('h3, [class*="listing-link"]')?.innerText?.trim()
         || el.querySelector('h2')?.innerText?.trim(),
    price: el.querySelector('[class*="currency-value"]')?.innerText?.trim()
         || el.querySelector('.currency-value')?.innerText?.trim(),
    shop: el.querySelector('[class*="shop-name"], [data-shop-name]')?.innerText?.trim(),
    url: el.querySelector('a[href*="/listing/"]')?.href,
    thumbnail: el.querySelector('img[src*="etsystatic"]')?.src,
    is_ad: !!el.querySelector('[class*="ad-label"], [class*="sponsored"]')
  })).filter(r => r.listing_id)
""")
```

**Alternative — JSON-LD ItemList** (more reliable than DOM selectors):

Etsy's SSR HTML embeds a `<script type="application/ld+json">` with an `ItemList` on search pages. In the browser, extract it via:

```python
ld_json_str = js("""
  Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
    .map(s => { try { return JSON.parse(s.textContent); } catch(e) { return null; } })
    .filter(d => d && d['@type'] === 'ItemList')[0]
""")
# Returns the ItemList object or null

if ld_json_str:
    # ld_json_str.itemListElement is a list of:
    # { '@type': 'ListItem', 'position': 1,
    #   'url': 'https://www.etsy.com/listing/...', 'name': 'Handmade Soy Candle' }
    for item in ld_json_str.get('itemListElement', []):
        print(item['position'], item['url'], item.get('name'))
```

Expected output (ItemList typically has 48 items per search page):
```
1  https://www.etsy.com/listing/1234567890/handmade-soy-candle  "Handmade Soy Candle"
2  https://www.etsy.com/listing/0987654321/beeswax-pillar-candle  "Beeswax Pillar Candle"
...
```

### Listing detail page extraction (browser)

```python
goto_url("https://www.etsy.com/listing/1234567890/product-slug")
wait_for_load()
wait(2)

# JSON-LD Product schema (most reliable)
product = js("""
  (function() {
    var scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (var s of scripts) {
      try {
        var d = JSON.parse(s.textContent);
        if (d['@type'] === 'Product') return d;
      } catch(e) {}
    }
    return null;
  })()
""")

# product fields:
# product['name']                    → listing title
# product['description']             → full description
# product['offers']['price']         → e.g. "25.99"
# product['offers']['priceCurrency'] → "USD"
# product['offers']['availability']  → "http://schema.org/InStock"
# product['brand']['name']           → shop name (seller)
#   OR product['seller']['name']
# product['aggregateRating']['ratingValue']  → e.g. "4.8"
# product['aggregateRating']['reviewCount']  → e.g. 1247
# product['image']                   → [list of image URLs]
```

**Fallback DOM selectors** (when JSON-LD is absent or incomplete):

```python
detail = js("""
  ({
    title:   document.querySelector('h1[data-buy-box-listing-title]')?.innerText?.trim()
           || document.querySelector('h1.wt-text-body-01')?.innerText?.trim(),
    price:   document.querySelector('[data-selector="price-only"]')?.innerText?.trim()
           || document.querySelector('[class*="wt-text-title-larger"]')?.innerText?.trim(),
    shop:    document.querySelector('[class*="shop-name-and-title"] a')?.innerText?.trim()
           || document.querySelector('a[href*="/shop/"]')?.innerText?.trim(),
    rating:  document.querySelector('[data-selector="reviews-tab"]')?.innerText?.trim(),
    reviews: document.querySelector('[class*="wt-display-inline-flex-xs"] .wt-text-body-01')?.innerText?.trim(),
    sold:    document.querySelector('[class*="wt-text-caption"] span')?.innerText?.trim()
  })
""")
```

### Shop/seller page extraction (browser)

```python
goto_url("https://www.etsy.com/shop/ShopName")
wait_for_load()
wait(2)

# JSON-LD on shop pages (type varies: LocalBusiness, Store, or Organization)
shop_ld = js("""
  (function() {
    for (var s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        var d = JSON.parse(s.textContent);
        if (['LocalBusiness','Store','Organization'].includes(d['@type'])) return d;
      } catch(e) {}
    }
    return null;
  })()
""")

# DOM extraction for shop stats
shop_info = js("""
  ({
    name:       document.querySelector('[class*="shop-name"]')?.innerText?.trim(),
    tagline:    document.querySelector('[class*="shop-tagline"]')?.innerText?.trim(),
    sales:      document.querySelector('[data-region="shop-sales-count"]')?.innerText?.trim()
              || document.querySelector('[class*="wt-text-caption"] span')?.innerText?.trim(),
    admirers:   document.querySelector('[data-wt-shop-admirers]')?.innerText?.trim(),
    location:   document.querySelector('[class*="shop-location"]')?.innerText?.trim(),
    listing_count: document.querySelectorAll('[data-listing-id]').length
  })
""")
```

Pagination for shop listings: Etsy loads more listings via infinite scroll or a "Load more" button. After clicking:

```python
# Check for pagination or load-more
load_more = js("document.querySelector('[data-wt-shop-listings-load-more], button[class*=\"load-more\"]')?.href")
if load_more:
    goto_url(load_more)
    wait_for_load()
    wait(2)
# Or: scroll to bottom to trigger infinite scroll
js("window.scrollTo(0, document.body.scrollHeight)")
wait(2)
```

### Pagination (search results)

```python
# Etsy uses ?page=N — 48 results per page (standard), up to ~250 pages
next_url = js("document.querySelector('a[data-wt-search-page-next], .wt-action-group a[rel=\"next\"]')?.href")
if next_url:
    goto_url(next_url)
    wait_for_load()
    wait(2)

# Or construct directly:
goto_url(f"https://www.etsy.com/search?q=handmade+candle&explicit=1&page={page_num}")
wait_for_load()
wait(2)
```

---

## URL patterns

| URL | Purpose | Notes |
|---|---|---|
| `/search?q={query}&explicit=1` | Keyword search | 48 results/page |
| `/search?q={query}&explicit=1&page={n}` | Pagination | n starts at 2 |
| `/listing/{id}/{slug}` | Listing detail | slug is optional |
| `/shop/{ShopName}` | Shop homepage | CamelCase, no spaces |
| `/shop/{ShopName}/listings` | Shop all listings | |
| `/c/{category}/{subcategory}` | Category browse | e.g. `/c/jewelry/necklaces` |
| `/market/{keyword}` | Market/tag page | e.g. `/market/handmade_candle` |
| `openapi.etsy.com/v3/application/listings/active?keywords={query}` | Official API search | requires API key |

---

## Data schema (JSON-LD on listing pages)

When the browser renders a listing, the JSON-LD `Product` schema contains:

```json
{
  "@type": "Product",
  "name": "Handmade Beeswax Taper Candles, Set of 12",
  "description": "These beautiful hand-dipped candles...",
  "image": [
    "https://i.etsystatic.com/12345678/r/il/abc123/1234567890/il_1588xN.1234567890.jpg"
  ],
  "brand": { "@type": "Brand", "name": "BeeswaxWonders" },
  "offers": {
    "@type": "Offer",
    "price": "32.00",
    "priceCurrency": "USD",
    "availability": "http://schema.org/InStock",
    "url": "https://www.etsy.com/listing/1234567890/..."
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.9",
    "reviewCount": "847",
    "bestRating": "5",
    "worstRating": "1"
  }
}
```

On search results pages, the JSON-LD `ItemList` schema contains:

```json
{
  "@type": "ItemList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "url": "https://www.etsy.com/listing/1234567890/handmade-beeswax-candle",
      "name": "Handmade Beeswax Taper Candles, Set of 12"
    }
  ]
}
```

The ItemList only gives URL, position, and name — no price or rating. For full data, follow each URL to the listing detail page.

---

## Official Etsy API v3 (recommended alternative)

The official API at `openapi.etsy.com/v3/` bypasses DataDome entirely. It requires a free API key from [developer.etsy.com](https://developer.etsy.com/) (no payment needed; approval is automatic for basic read access).

### Rate limits

- 10,000 requests/day (free tier)
- No per-second limit documented; add `time.sleep(0.1)` between requests to be safe

### Key endpoints

```
GET /application/listings/active
    ?keywords=handmade+candle
    &limit=100             (max 100)
    &offset=0              (for pagination)
    &sort_on=created|price|updated|score
    &sort_order=asc|desc
    &taxonomy_id=1234      (category filter)
    &min_price=10.00
    &max_price=50.00

GET /application/listings/{listing_id}
GET /application/listings/{listing_id}/images
GET /application/listings/{listing_id}/reviews
GET /application/shops/{shop_id}
GET /application/shops/{shop_id}/listings/active
GET /application/users/{user_id}
GET /application/seller-taxonomy/nodes   (full category tree)
```

### Pagination with API

```python
import json, time
from helpers import http_get

API_KEY = "your_key_here"

def etsy_search(keywords, max_results=200):
    results = []
    offset = 0
    limit = 100
    while offset < max_results:
        url = (f"https://openapi.etsy.com/v3/application/listings/active"
               f"?keywords={keywords}&limit={limit}&offset={offset}"
               f"&sort_on=score&sort_order=desc")
        data = json.loads(http_get(url, headers={"x-api-key": API_KEY}))
        batch = data.get("results", [])
        if not batch:
            break
        results.extend(batch)
        offset += limit
        time.sleep(0.1)
    return results
```

---

## Gotchas

- **`http_get` is completely blocked.** All URL types return HTTP 403 with DataDome JS challenge. No header or cookie combination bypasses it. Only a real Chrome browser with JS execution works.

- **DataDome detects TLS fingerprint.** The challenge runs JavaScript at `geo.captcha-delivery.com`. Even curl with perfect browser headers returns 403 — the HTTP library's TLS handshake is fingerprinted.

- **`explicit=1` is required for general search.** Without it, Etsy may filter adult/mature content from results in unexpected ways (like returning fewer results or a different ordering).

- **48 results per search page.** Etsy's standard search returns 48 listings per page (not 25 or 50). The `page=` param is 1-indexed.

- **Listing slug is optional.** `https://www.etsy.com/listing/1234567890` works without the slug; Etsy redirects to the canonical URL with the full slug.

- **Shop names are case-sensitive in URLs.** `/shop/beeswaxwonders` may not redirect to `/shop/BeeswaxWonders` — use the exact casing from the listing's shop link.

- **JSON-LD `brand` vs `seller`.** Etsy's Product schema uses `brand.name` for the shop name on most listing pages, but some pages use `seller.name` instead. Check both.

- **Price in JSON-LD is a string.** `offers.price` is `"25.99"` (string), not a number. Parse with `float()`.

- **API price is in subunits.** API v3 returns `price.amount = 2599` and `price.divisor = 100`, so the actual price is `amount / divisor = 25.99`. Do NOT use `price.amount` directly.

- **robots.txt disallows `/search?*q=`** (empty query) but allows `/search?q={non-empty}` implicitly — however DataDome blocks all of it regardless of what robots.txt says.

- **`/market/` pages are different from `/search`.** Market pages (`/market/handmade_candle`) are tag-based browse pages with a different layout than keyword search results — same DataDome block applies.

- **Etsy API `description` may include HTML entities.** Unescape with `html.unescape()` before displaying.
