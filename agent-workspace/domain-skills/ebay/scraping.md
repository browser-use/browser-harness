# eBay — Scraping & Data Extraction

Field-tested against ebay.com on 2026-04-18 with `http_get`,
re-tested 2026-05-15 from a CN/HK IP without `BROWSER_USE_API_KEY` (see Prerequisites).

## Prerequisites

- **Set `BROWSER_USE_API_KEY` if you can.** When set, `http_get` routes through fetch-use
  (residential proxies, retries). Without it, the request goes through your local IP via
  urllib, and **eBay's edge (Akamai) returns HTTP 403/503 before any HTML is served** for
  any IP it doesn't trust — common for VPN, datacenter, or non-US residential IPs.
- **Fallback when `http_get` fails at the edge:** drive a real Chrome via the harness
  (`new_tab(url)` + `wait_for_load()` + `js("return document.documentElement.outerHTML")`).
  Chrome inherits the user's geolocation/cookies and is not blocked. The card-level regex
  parsers below work identically on the resulting HTML.

## Critical: Bot Detection (two layers)

eBay sits behind two independent block layers. The skill must detect both:

1. **Akamai edge** — IP reputation check. Returns `HTTP 403` (often a 389-byte
   `errors.edgesuite.net` page titled "Access Denied") or `HTTP 503` for transient
   throttling. Fires on the very first request from a low-reputation IP, before any
   eBay HTML is served.
2. **eBay in-page interstitial ("Pardon Our Interruption")** — fires after roughly
   **5–10 requests per IP in a short window** once the edge has let you in. The block
   page is ~13 KB and contains no listing data.

**Always check before parsing:**
```python
import urllib.error

def is_blocked(html_or_exc):
    """Detect both Akamai edge blocks (HTTPError) and the in-page interstitial."""
    if isinstance(html_or_exc, urllib.error.HTTPError):
        return html_or_exc.code in (403, 429, 503)
    if not isinstance(html_or_exc, str):
        return True
    return 'Pardon Our Interruption' in html_or_exc or len(html_or_exc) < 20_000

def safe_get(url, headers):
    """http_get + edge-block detection. Returns html or None."""
    try:
        html = http_get(url, headers=headers)
    except urllib.error.HTTPError as e:
        if is_blocked(e):
            return None
        raise
    return None if is_blocked(html) else html

html = safe_get("https://www.ebay.com/sch/i.html?_nkw=laptop&LH_BIN=1", HEADERS)
if html is None:
    raise RuntimeError("eBay block (edge or in-page) — back off, switch IP, or use Chrome fallback")
```

**When blocked:** wait at minimum 60–120 seconds before retrying. The block is IP-session-scoped,
not a hard IP ban; it clears after inactivity.

**Headers required (minimal UA gets blocked faster, full browser UA lasts longer):**
```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}
```

A plain `"User-Agent": "Mozilla/5.0"` also works for the first few requests,
but the full Chrome UA lasts slightly longer before triggering the block.

## Search URL Structure

```
https://www.ebay.com/sch/i.html?_nkw={query}&{filters}
```

Confirmed working URL examples:
```python
# Buy It Now only, sorted by lowest price
"https://www.ebay.com/sch/i.html?_nkw=mechanical+keyboard&LH_BIN=1&_sop=15"

# Auctions only
"https://www.ebay.com/sch/i.html?_nkw=vintage+camera&LH_Auction=1"

# New condition only, page 2
"https://www.ebay.com/sch/i.html?_nkw=laptop&LH_ItemCondition=1000&_pgn=2"
```

### Filter Parameters (all confirmed working)

| Parameter | Value | Effect |
|-----------|-------|--------|
| `LH_BIN` | `1` | Buy It Now only |
| `LH_Auction` | `1` | Auctions only |
| `LH_ItemCondition` | see below | Filter by condition |
| `_sop` | see below | Sort order |
| `_pgn` | `2`, `3`, … | Page number (confirmed: returns ~65–88 items/page) |
| `_ipg` | `25`, `50`, `100`, `200` | Items per page (unconfirmed, standard eBay param) |

### Condition Codes for `LH_ItemCondition`

| Code | Label |
|------|-------|
| `1000` | New |
| `1500` | New Other (open box, no original packaging) |
| `2000` | Manufacturer Refurbished |
| `2500` | Seller Refurbished |
| `2750` | Like New |
| `3000` | Used |
| `4000` | Very Good |
| `5000` | Good |
| `6000` | Acceptable |
| `7000` | For parts or not working |

### Sort Codes for `_sop`

| Code | Sort Order |
|------|-----------|
| `1` | Best Match (default) |
| `10` | Ending Soonest |
| `12` | Newly Listed |
| `15` | Lowest Price + Shipping |
| `16` | Highest Price |

### Item Detail URL

```
https://www.ebay.com/itm/{listing_id}
```

The listing ID is a plain integer (e.g. `167040158614`). Always strip query parameters
from extracted URLs — tracking params bloat the URL and are not needed for navigation.

## Search Results: HTML Structure (No JSON-LD)

**JSON-LD is absent on search results pages.** The listing data is embedded in HTML
with eBay-specific class names. The response is large (~1.5–1.8 MB uncompressed).

### Card Structure

Each result is an `<li>` element with `data-listingid=<id>`. Key elements within each card:

| Data | Pattern |
|------|---------|
| Listing ID | `data-listingid=(\d+)` on the `<li>` |
| Item URL | `href=(https://(?:www\.)?ebay\.com/itm/(\d+))` |
| Title | `s-card__title` > `su-styled-text primary` > text |
| Current price | `s-card__price[^>]*>([^<]+)<` (returns raw inner text — currency varies by IP geo) |
| Original/list price | `strikethrough[^>]*>([^<]+)<` (raw inner text) |
| Image | `class=s-card__image[^>]*src=([^\s>]+)` |
| Alt title | `img[alt]` in the card (same as product title) |

### Confirmed Extractor (field-tested, 60 items from a single search)

```python
import re

def extract_search_results(html):
    """
    Parse eBay search results HTML into a list of dicts.
    Returns [] if blocked or no results.
    """
    if 'Pardon Our Interruption' in html or len(html) < 20_000:
        return []

    cards = re.split(r'(?=<li[^>]+data-listingid=)', html)
    results = []
    seen_ids = set()

    for card in cards[1:]:  # skip preamble before first card
        # Listing ID (dedup)
        lid_m = re.search(r'data-listingid=(\d+)', card)
        if not lid_m:
            continue
        listing_id = lid_m.group(1)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)

        # Item URL (clean, no tracking params)
        url_m = re.search(r'href=(https://(?:www\.)?ebay\.com/itm/(\d+))', card)
        item_url = url_m.group(1).split('?')[0] if url_m else None

        # Title from s-card__title
        title_m = re.search(r's-card__title[^>]*>.*?primary[^>]*>([^<]+)', card, re.DOTALL)
        title = title_m.group(1).strip() if title_m else None

        # Skip placeholder "Shop on eBay" stub cards
        if not title or title == 'Shop on eBay':
            continue

        # Current price (raw inner text — currency varies by IP geo,
        # e.g. "$159.00", "HKD 297.54", "EUR 49.99"). Do NOT assume "$" prefix.
        price_m = re.search(r's-card__price[^>]*>([^<]+)<', card)
        price = price_m.group(1).strip() if price_m else None

        # Original / list price (strikethrough — present when discounted)
        orig_m = re.search(r'strikethrough[^>]*>([^<]+)<', card)
        original_price = orig_m.group(1).strip() if orig_m else None

        # Thumbnail image URL
        img_m = re.search(r'class=s-card__image[^>]*src=([^\s>]+)', card)
        image = img_m.group(1) if img_m else None

        results.append({
            'listing_id': listing_id,
            'url': item_url,
            'title': title,
            'price': price,
            'original_price': original_price,  # None if not on sale
            'image': image,
        })

    return results
```

**Usage:**
```python
from helpers import http_get
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

html = http_get("https://www.ebay.com/sch/i.html?_nkw=mechanical+keyboard&LH_BIN=1&_sop=15", headers=HEADERS)
items = extract_search_results(html)
print(f"{len(items)} items")
for item in items[:5]:
    print(f"  {item['listing_id']} | {item['title'][:50]} | {item['price']}")
# Output (confirmed): 60 items
# 168219240588 | One Plus Keyboard 81 Pro Winter Bonfire Mecha... | $159.00
# 167461643107 | Logitech 920-012869 G515 TKL Wired Low Profil... | $49.99
# 167040158614 | Logitech - PRO X TKL LIGHTSPEED Wireless Mech... | $74.99
```

## "No exact matches" — fuzzy fallback results

When the search query has no precise match, eBay still returns ~60 cards but they are
**fuzzy/recommended substitutes**, not exact matches. The page renders normally and the
extractor returns full results — only a small "No exact matches found" hint marks the
difference. Detect this before treating results as authoritative:

```python
def has_exact_match(html):
    return 'No exact matches found' not in html

# Field-tested 2026-05-15: query "dj posket4" → 0 exact matches, 60 recommended cards.
# 5 of 60 contained "posket" in the title (fuzzy match on the most distinctive token);
# the other 55 were unrelated. Always surface this signal — the user may have typoed
# the query, and silently returning fuzzy results looks like a successful match.
```

## Item Detail Pages: JSON-LD (Reliable)

Item detail pages at `/itm/{id}` serve **two JSON-LD blocks**: `BreadcrumbList` and `Product`.
The `Product` schema is the most useful — it contains price, condition, availability, brand, images, and return policy.

```python
import re, json

def extract_item_detail(html):
    """
    Extract structured data from an eBay item page.
    Returns dict or None if blocked.
    """
    if 'Pardon Our Interruption' in html:
        return None

    ld_blocks = re.findall(r'application/ld\+json[^>]*>(.*?)</script>', html, re.DOTALL)
    product = None
    breadcrumbs = []

    for ld_str in ld_blocks:
        try:
            d = json.loads(ld_str.strip())
        except Exception:
            continue

        if d.get('@type') == 'Product':
            product = d
        elif d.get('@type') == 'BreadcrumbList':
            breadcrumbs = [i.get('name') for i in d.get('itemListElement', [])]

    if not product:
        return None

    offers = product.get('offers', {})
    if isinstance(offers, list):
        offers = offers[0]

    # Schema.org condition URL -> human label
    CONDITION_MAP = {
        'NewCondition':          'New',
        'UsedCondition':         'Used',
        'RefurbishedCondition':  'Refurbished',
        'DamagedCondition':      'For Parts / Not Working',
        'LikeNewCondition':      'Like New',
        'VeryGoodCondition':     'Very Good',
        'GoodCondition':         'Good',
        'AcceptableCondition':   'Acceptable',
    }
    cond_url = offers.get('itemCondition', '')
    cond_key = cond_url.split('/')[-1]  # e.g. "RefurbishedCondition"
    condition = CONDITION_MAP.get(cond_key, cond_key)

    # List price from priceSpecification (only present when there's a "was" price)
    price_spec = offers.get('priceSpecification', {})
    list_price = price_spec.get('price') if price_spec.get('name') == 'List Price' else None

    # Shipping (first destination)
    shipping_details = offers.get('shippingDetails', [])
    if shipping_details:
        shipping_val = shipping_details[0].get('shippingRate', {}).get('value', '')
        shipping = 'Free' if str(shipping_val) in ('0', '0.0') else f"${shipping_val}"
    else:
        shipping = None

    # Return policy
    return_policies = offers.get('hasMerchantReturnPolicy', [])
    return_days = return_policies[0].get('merchantReturnDays') if return_policies else None

    return {
        'listing_id': offers.get('url', '').split('/itm/')[-1],
        'name': product.get('name'),
        'brand': product.get('brand', {}).get('name') if isinstance(product.get('brand'), dict) else product.get('brand'),
        'price': offers.get('price'),
        'list_price': list_price,     # was-price, None if no discount shown
        'currency': offers.get('priceCurrency'),
        'availability': offers.get('availability', '').split('/')[-1],  # e.g. "InStock"
        'condition': condition,
        'condition_url': cond_url,
        'shipping': shipping,
        'return_days': return_days,
        'images': product.get('image', []),
        'gtin13': product.get('gtin13'),
        'mpn': product.get('mpn'),
        'color': product.get('color'),
        'breadcrumbs': breadcrumbs,
    }
```

**Field-tested on item 167040158614:**
```python
html = http_get("https://www.ebay.com/itm/167040158614", headers=HEADERS)
detail = extract_item_detail(html)
# {
#   'listing_id':   '167040158614',
#   'name':         'Logitech - PRO X TKL LIGHTSPEED Wireless Mechanical Gaming Keyboard - 920-012118',
#   'brand':        'Logitech',
#   'price':        74.99,
#   'list_price':   '219.99',
#   'currency':     'USD',
#   'availability': 'InStock',
#   'condition':    'Refurbished',
#   'shipping':     'Free',
#   'return_days':  30,
#   'images':       ['https://i.ebayimg.com/images/g/vwsAAeSwEcFpw~hW/s-l1600.jpg', ...],  # 5 images
#   'gtin13':       '097855189066',
#   'mpn':          '920-012118',
#   'color':        'Black',
#   'breadcrumbs':  ['eBay', 'Electronics', 'Computers/Tablets & Networking', ...],
# }
```

### Item Specifics from `ux-textspans` (complementary to JSON-LD)

The `ux-textspans` elements in item pages contain additional data not in JSON-LD,
including seller name, feedback %, items sold, detailed condition text, and all item specifics.

```python
import re

def extract_ux_textspans(html):
    """Return list of all ux-textspans text values from an item page."""
    return [m.group(1) for m in re.finditer(r'ux-textspans[^>]*>([^<]+)</span>', html)]

# From item 167040158614 (confirmed):
# Index [3]  -> item title
# Index [4]  -> subtitle / seller tagline
# Index [5]  -> seller name ("Logitech")
# Index [6]  -> seller feedback count ("(20742)")
# Index [7]  -> seller feedback % ("99.6% positive")
# Index [10] -> current price ("US $74.99")
# Index [12] -> list price ("US $219.99")
# Index [33] -> condition label ("Excellent - Refurbished")
# Index [36] -> quantity sold ("45 sold")
# Pairs from [105] onward: item specifics as label/value pairs
```

## Pagination

Use `_pgn=N` (confirmed working, returns ~65–88 items per page):
```python
for page in range(1, 4):
    url = f"https://www.ebay.com/sch/i.html?_nkw=laptop&LH_BIN=1&_sop=15&_pgn={page}"
    html = http_get(url, headers=HEADERS)
    if is_blocked(html):
        break
    items = extract_search_results(html)
    print(f"Page {page}: {len(items)} items")
    # IMPORTANT: add delay between pages to avoid bot detection
    time.sleep(3)
```

**Rate-limit safe pattern**: 3–5 second delay between requests. Beyond ~10 rapid requests
in a session, eBay returns "Pardon Our Interruption" for all subsequent requests from that IP.

## APIs (All Require Auth or Are Dead)

| API | Status | Notes |
|-----|--------|-------|
| Finding API (svcs.ebay.com) | **Dead** — HTTP 500 | Was free/JSONP, no longer works |
| Browse API (api.ebay.com) | **Requires OAuth** — HTTP 400 | Needs eBay developer account + token |
| Shopping API (open.api.ebay.com) | **Requires token** | Returns `"Token not available"` error |
| RSS feed (`_rss=1`) | **Blocked same as HTML** | Returns "Pardon Our Interruption" when rate-limited |

**Bottom line**: There is no public unauthenticated eBay API in 2026. Use HTML scraping.

## Practical Workflow

### Scrape a search and follow top items

```python
import re, json, time
from helpers import http_get

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def is_blocked(html):
    return 'Pardon Our Interruption' in html or len(html) < 20_000

# Step 1: Search
html = http_get(
    "https://www.ebay.com/sch/i.html?_nkw=mechanical+keyboard&LH_BIN=1&_sop=15&LH_ItemCondition=1000",
    headers=HEADERS
)
if is_blocked(html):
    raise RuntimeError("Rate limited — wait 60-120s and retry")

items = extract_search_results(html)
print(f"Found {len(items)} items")

# Step 2: Fetch details for top results (with delay)
details = []
for item in items[:5]:
    time.sleep(3)
    detail_html = http_get(item['url'], headers=HEADERS)
    if is_blocked(detail_html):
        print(f"Blocked on item {item['listing_id']}, stopping")
        break
    detail = extract_item_detail(detail_html)
    if detail:
        details.append(detail)
        print(f"  {detail['name'][:50]} | {detail['price']} {detail['currency']} | {detail['condition']}")
```

## Gotchas

- **"Pardon Our Interruption" is not a CAPTCHA** — it's eBay's bot-detection interstitial. It doesn't require solving — just wait and back off. `'captcha'` does NOT appear in the blocked page.

- **No JSON-LD on search results** — The `application/ld+json` blocks that Amazon and other sites embed are absent from eBay search pages. Parse the HTML using regex on `s-card` class names.

- **JSON-LD IS on item pages** — Two blocks: `BreadcrumbList` and `Product`. The `Product` block is authoritative. Use the regex `r'application/ld\+json[^>]*>(.*?)</script>'` (note the `[^>]*` before `>` — eBay doesn't use `type="..."` quote style consistently in all contexts).

- **Duplicate listing IDs in the HTML** — Each card's listing ID appears 2–3 times (image link, title link, watch button). Always deduplicate using a `seen_ids` set when splitting on `data-listingid`.

- **Placeholder cards ("Shop on eBay")** — The first card slot may be a promoted/placeholder card with title `"Shop on eBay"` and listing ID `"123456"`. Filter these out.

- **Item URLs have tracking params** — Raw extracted URLs look like `https://www.ebay.com/itm/167040158614?_skw=...&epid=...&hash=...&itmprp=...`. Always strip to `itm/{id}` with `.split('?')[0]`.

- **`www.ebay.com` vs `ebay.com`** — Some item URLs in search results omit `www.`. Normalize with `url.replace('//ebay.com/', '//www.ebay.com/')`.

- **Search response is large** — Uncompressed HTML is 1.5–1.8 MB per page. The `http_get` helper handles gzip transparently, so the actual transfer is much smaller, but parsing a 1.8 MB string is slow. Use `re.split` on card boundaries rather than an HTML parser for speed.

- **`_sop` sort and `LH_ItemCondition` require full browser-like UA** — Requests with just `"Mozilla/5.0"` (minimal UA) return empty results for these parameters more quickly than full Chrome UA. Always use the full UA string.

- **Condition in JSON-LD is a schema.org URL** — `offers.itemCondition` returns `"https://schema.org/RefurbishedCondition"`, not a human label. Split on `/` and map the last segment using `CONDITION_MAP` (see `extract_item_detail` above).

- **`list_price` only present when discounted** — `offers.priceSpecification` only appears in JSON-LD when eBay shows a "List Price" comparison. Check `price_spec.get('name') == 'List Price'` before using.

- **Seller data is NOT in JSON-LD** — `d.get('seller')` returns `None` on item pages. The seller name, feedback %, and items sold count are only in `ux-textspans` elements in the HTML body.

- **Akamai edge block (HTTP 403/503) is upstream of "Pardon Our Interruption"** —
  When IP reputation is low (VPN, datacenter, non-US residential), `http_get` raises
  `urllib.error.HTTPError(403)` returning a 389-byte `errors.edgesuite.net` page,
  not the in-page interstitial. A text-only `is_blocked()` misses this entirely.
  Always use `safe_get()` (above) which catches both layers.

- **Currency varies by client IP** — eBay localizes prices server-side. A US IP returns
  `$74.99`; a CN/HK IP returns `HKD 297.54`; an EU IP returns `EUR 64.99`. The
  `s-card__price` extractor returns raw inner text; do not hard-code a `$` prefix.
  For numeric comparison, split currency and amount:
  `re.match(r'([A-Z$€£¥]+)\s*([\d,.]+)', price)`.

- **"No exact matches" is silent** — eBay returns ~60 cards even when the query has zero
  exact matches; the page is structurally identical to a successful search except for a
  small "No exact matches found" hint. Always call `has_exact_match(html)` and surface
  the result to the agent before claiming the listings answer the user's query.
