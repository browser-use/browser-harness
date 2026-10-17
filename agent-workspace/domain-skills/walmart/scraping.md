# Walmart — Product Search & Data Extraction

Field-tested against walmart.com on 2026-04-18 using `http_get` (no browser required).
All code blocks were run and outputs verified against live responses.

---

## Fastest Approach: `http_get` with `__NEXT_DATA__`

Walmart's Next.js SSR embeds the full search or product payload as JSON in a
`<script id="__NEXT_DATA__">` tag. **No browser needed for search or product detail pages.**
~2–3 s per page fetch; no CAPTCHA or session cookies required.

### Critical UA rule

| User-Agent | Result |
|---|---|
| `Mozilla/5.0` (bare) | Full HTML + `__NEXT_DATA__` — **use this** |
| `Mozilla/5.0 ... Chrome/120 ...` (full) | PerimeterX "Robot or human?" challenge (200, 15 KB) |
| `Safari/17` full UA | Works (full HTML, ~1.15 MB) |
| `curl/7.x` | PerimeterX challenge |
| `python-requests/2.31` | PerimeterX challenge |

The bare `Mozilla/5.0` string bypasses PerimeterX. Any UA that looks like a headless
client or includes a recognizable browser fingerprint triggers the JS challenge page.

### Base fetch helper

```python
import json, re, gzip, urllib.request

def fetch_walmart(url):
    """
    Fetch any walmart.com page.
    Returns decoded HTML string.
    Raises RuntimeError if PerimeterX bot challenge is returned.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        html = data.decode()
    if "Robot or human" in html:
        raise RuntimeError(f"PerimeterX challenge triggered: {url}")
    return html

def parse_next_data(html):
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        raise ValueError("__NEXT_DATA__ not found — page structure may have changed")
    return json.loads(m.group(1))
```

---

## Search Results

### URL patterns

```python
# Keyword search
"https://www.walmart.com/search?q=laptop"

# Pagination — append &page=N
"https://www.walmart.com/search?q=laptop&page=2"

# Sort options (confirmed working)
"https://www.walmart.com/search?q=laptop&sort=best_match"    # default
"https://www.walmart.com/search?q=laptop&sort=best_seller"
"https://www.walmart.com/search?q=laptop&sort=price_low"
"https://www.walmart.com/search?q=laptop&sort=customer_rating"

# Price filter
"https://www.walmart.com/search?q=laptop&min_price=200&max_price=500"

# Browse by category (department ID path)
"https://www.walmart.com/browse/electronics/laptops/3944_1089430_3951"
```

### `__NEXT_DATA__` path to items

```
data
  .props.pageProps.initialData.searchResult
    .aggregatedCount        — int: total matching products (e.g. 18818)
    .paginationV2.maxPage   — int: last page number
    .itemStacks[]           — array of stacks (usually 2: sponsored + organic)
      .items[]              — array of product objects
```

### Full extractor (field-tested)

```python
def extract_search_results(html):
    """
    Returns (items, total_count, max_page).
    items is a list of dicts with confirmed fields.
    """
    data = parse_next_data(html)
    sr = data["props"]["pageProps"]["initialData"]["searchResult"]

    items = []
    for stack in sr.get("itemStacks", []):
        for item in stack.get("items", []):
            pi = item.get("priceInfo") or {}
            img = item.get("imageInfo") or {}
            rating = item.get("rating") or {}
            avail = item.get("availabilityStatusV2") or {}
            items.append({
                "usItemId":        item.get("usItemId"),           # str, Walmart item ID
                "name":            item.get("name"),               # str
                "brand":           item.get("brand"),              # str or None
                "price":           item.get("price"),              # int, current price in USD
                "linePrice":       pi.get("linePrice"),            # str "$429.00"
                "wasPrice":        pi.get("wasPrice") or None,     # str "$699.00" or None
                "savings":         pi.get("savings") or None,      # str "SAVE $270.00" or None
                "averageRating":   rating.get("averageRating"),    # float e.g. 4.3
                "numberOfReviews": rating.get("numberOfReviews"),  # int
                "availability":    avail.get("value"),             # "IN_STOCK" / "OUT_OF_STOCK"
                "isSponsored":     bool(item.get("isSponsoredFlag")),
                "url":             "https://www.walmart.com" + (item.get("canonicalUrl") or "").split("?")[0],
                "thumbnailUrl":    img.get("thumbnailUrl"),
            })

    total = sr.get("aggregatedCount")
    max_page = (sr.get("paginationV2") or {}).get("maxPage")
    return items, total, max_page


# Usage
html = fetch_walmart("https://www.walmart.com/search?q=laptop")
items, total, max_page = extract_search_results(html)
# items: 66 items on page 1, total=18818, max_page=11

# Filter out sponsored
organic = [i for i in items if not i["isSponsored"]]
```

### Field notes (confirmed)

- **`usItemId`**: string, matches the numeric ID at the end of `/ip/.../ITEMID` URLs.
  Some non-product rows (ad widgets) have `usItemId=None` — filter with `if item.get("usItemId")`.
- **`price`**: integer cents-less price (e.g. `429` for "$429.00"). Use `priceInfo.linePrice` for
  the formatted string including the dollar sign.
- **`wasPrice` / `savings`**: only present when item is on sale. Always `None` for full-price items.
- **`isSponsoredFlag`**: the first batch of results across both itemStacks are frequently sponsored.
  On a laptop search, ~56 of 66 SSR items carry `isSponsoredFlag: true`.
- **`rating`**: present on ~91% of items (60/66 in test). `averageRating` is a float; `numberOfReviews` is int.
- **`canonicalUrl`**: always includes `?classType=...&athbdg=...` query params — strip with `.split("?")[0]`
  to get a clean URL.
- **Two itemStacks**: Walmart returns two stacks (`itemStacks[0]` and `itemStacks[1]`). Merge them.
  `itemStacks[0]` is the primary grid; `itemStacks[1]` is a secondary sponsored/related block.

### Pagination

```python
for page in range(1, max_page + 1):
    html = fetch_walmart(f"https://www.walmart.com/search?q=laptop&page={page}")
    items, _, _ = extract_search_results(html)
    # process items...
```

Page responses average ~2.5 s each. No rate-limiting was observed across 3 sequential requests.
For bulk scraping, add a 1–2 s delay between requests to be safe.

---

## Category Listings at Scale: the `Browse` GraphQL Query

Page 2+ of any `/browse/...` or `/search` page comes from a persisted GraphQL query. Calling it yourself returns
compact JSON (~100–160 KB per call all in, vs a full page load) and exposes filters the URL doesn't.
Field-tested 2026-10-09/10 on the Food department (`976759`).

### Request

- `GET https://www.walmart.com/orchestra/snb/graphql/Browse/<sha256>/browse?variables=<url-encoded JSON>`.
  Past ~8 KB of URL, `POST` the same path with body `{"variables": …}`: that works too.
- The hash is in one of the page's `_next/static/chunks/*.js` files as `name:"Browse",hash:"<64 hex>"` (chunk
  `74258-*.js` in 2026-10; the number changes with deploys, so search the chunks). After a deploy, an old hash
  answers `PERSISTED_QUERY_NOT_FOUND`.
- Variables: start from the loaded page's `__NEXT_DATA__.props.pageProps.initialSearchQueryVariables`. They hold a
  top-level set plus `fitmentSearchParams` and `searchParams` copies, so set `page`, `ps`, `sort`, `cat_id`,
  `min_price`/`max_price` and `facet` in all three.
- Headers the page itself sends (missing the `x-o-*` group fails): `x-apollo-operation-name: Browse`,
  `x-o-gql-query: query Browse`, `x-o-platform: rweb`, `x-o-platform-version: <runtimeConfig.appVersion>`,
  `x-o-bu: WALMART-US`, `x-o-mart: B2C`, `x-o-segment: oaoh`, `x-o-ccm: server`, `tenant-id: elh9ie`, `wm_mp: true`,
  plus per-request correlation ids.
- Run it as `fetch()` from inside a loaded walmart.com page (same origin, the page's PerimeterX cookies). From a
  plain HTTP client the same request got only ~3–6 answers per PerimeterX window. The Android app's headers, which
  work for the product query `ItemById`, got a 412 on every `Browse` call.
- Set `additionalQueryParams.isMoreOptionsTileEnabled = false`. When it is on, a product's variants fold into one
  tile and ~15% of a listing never shows.

### What a query returns

- `aggregatedCount` plus up to `ps` results a page. `ps` accepts 40, 48 or 60; 80+ silently falls back to 40.
  Pages can carry more tiles than `ps` (variants).
- **~400-result cap**: a result set of up to ~1,000 serves nothing past its ~390th result, whatever
  `paginationV2.maxPage` says. Pages 1–10 at ps 40 and 1–7 at ps 60 both end there, and the `pap` parameter in
  `searchResult.debug.sisUrl` shows `ms_max_page_within_rerank: 10`. Bigger result sets page on to 26; 27+ repeat
  a page and 101+ answer "SIS failed". To enumerate a category, slice it until each query has at most ~380 results.
- **`aggregatedCount` is not a coverage target**:
  - About 95% of a slice's count shows up in its pages. Out-of-stock items mostly never do.
  - Some merchandising shelves carry phantom counts. Food's "Seasonal Grocery" (`976759_1567409`) claimed 1.1M of
    the department's 1.4M, yet all its slices together showed ~15K distinct items.
- Sorts seen working: `best_match`, `price_low`, `price_high`, `new`.

### Filters (slicing tools)

- `min_price` / `max_price`: whole dollars only, both bounds inclusive. A decimal bound gives 0 results.
- `facet: "brand:A||brand:B"` ORs brands. The brand facet in the answer lists only a slice's top 200 brands.
- The "Departments" facet (`cat_id` values like `976759_976794`) mixes real sub-categories with merchandising
  shelves that repeat them ("Shop All Candy"). It also omits some real children: collect child ids from the items'
  own `categoryPathId` (`0:976759:976794:…`) too.
- A `cat_id` Walmart can't browse answers with its parent's items and count, not an error.

---

## Product Detail Page

### URL pattern

```
https://www.walmart.com/ip/{slug}/{usItemId}
```

The slug is ignored in routing — only the numeric `usItemId` matters.
These work identically:
```
https://www.walmart.com/ip/anything/19717318352
https://www.walmart.com/ip/Apple-MacBook-Neo/19717318352
```

### `__NEXT_DATA__` path on a product page

```
data.props.pageProps.initialData.data
  .product        — core product object
  .idml           — long description, specs, highlights, warranty
  .reviews        — rating breakdown + first 10 customer reviews (SSR)
```

### Full extractor (field-tested)

```python
def extract_product_detail(html):
    """
    Returns a dict with all confirmed product fields.
    idml.specifications returns all spec rows as a flat dict.
    reviews returns the SSR-rendered first 10 customer reviews.
    """
    data = parse_next_data(html)
    d = data["props"]["pageProps"]["initialData"]["data"]
    product = d["product"]
    idml    = d.get("idml") or {}
    reviews = d.get("reviews") or {}

    pi = product.get("priceInfo") or {}
    cp = pi.get("currentPrice") or {}
    img = product.get("imageInfo") or {}
    avail = product.get("availabilityStatusV2") or {}

    specs = {
        spec.get("name"): spec.get("value")
        for spec in (idml.get("specifications") or [])
    }

    all_images = [
        img_item.get("url")
        for img_item in (img.get("allImages") or [])
        if img_item.get("url")
    ]

    customer_reviews = [
        {
            "title":    r.get("reviewTitle"),
            "rating":   r.get("rating"),           # int 1-5 (field is "rating", NOT "overallRating")
            "text":     r.get("reviewText"),
            "author":   r.get("userNickname"),
            "date":     r.get("reviewSubmissionTime"),
        }
        for r in (reviews.get("customerReviews") or [])
    ]

    return {
        # identity
        "usItemId":            product.get("usItemId"),
        "name":                product.get("name"),
        "brand":               product.get("brand"),
        "model":               product.get("model"),
        "upc":                 product.get("upc"),
        # price
        "price":               cp.get("price"),            # float, e.g. 599
        "priceString":         cp.get("priceString"),      # "$599.00"
        "wasPrice":            (pi.get("wasPrice") or {}).get("priceString"),
        "savings":             (pi.get("savings") or {}).get("savingsString"),
        # availability
        "availability":        avail.get("value"),         # "IN_STOCK" / "OUT_OF_STOCK"
        "availabilityDisplay": avail.get("display"),       # "In stock"
        # ratings
        "averageRating":       product.get("averageRating"),
        "numberOfReviews":     product.get("numberOfReviews"),
        # text
        "shortDescription":    product.get("shortDescription"),
        "longDescription":     idml.get("longDescription"),  # HTML string
        # media
        "thumbnailUrl":        img.get("thumbnailUrl"),
        "allImages":           all_images,          # up to 10 image URLs
        # specs
        "specifications":      specs,               # {"Brand": "Apple", "Processor": "A18 Pro", ...}
        "highlights":          [                    # top highlighted specs with icons
            {"name": h.get("name"), "value": h.get("value")}
            for h in (idml.get("productHighlights") or [])
        ],
        # URL
        "canonicalUrl":        "https://www.walmart.com" + (product.get("canonicalUrl") or ""),
        # fulfillment
        "fulfillmentOptions":  product.get("fulfillmentOptions") or [],
        # reviews (SSR-rendered, first 10)
        "reviewSummary": {
            "averageOverallRating":    reviews.get("averageOverallRating"),
            "totalReviewCount":        reviews.get("totalReviewCount"),
            "reviewsWithTextCount":    reviews.get("reviewsWithTextCount"),
            "recommendedPercentage":   reviews.get("recommendedPercentage"),
        },
        "customerReviews":     customer_reviews,
    }


# Usage
url = "https://www.walmart.com/ip/Apple-MacBook-Neo/19717318352"
html = fetch_walmart(url)
product = extract_product_detail(html)

# Example output (confirmed live):
# product["name"]         → "Apple MacBook Neo 13-inch Apple A18 Pro chip..."
# product["price"]        → 599
# product["priceString"]  → "$599.00"
# product["availability"] → "IN_STOCK"
# product["model"]        → "MHFD4LL/A"
# product["upc"]          → "195950852745"
# len(product["specifications"])  → 29 spec rows
# len(product["allImages"])       → 10
# product["specifications"]["Processor"] → "A18 Pro"
```

### Field notes (confirmed)

- **`averageRating` / `numberOfReviews`** on the product node: present for items with reviews.
  New/few-review items may return `None` for both.
- **`reviewSummary.averageOverallRating`** in the reviews node often differs slightly from
  `product.averageRating` — the reviews node is more precise (e.g. `4.75` vs `4.8`).
- **`customerReviews`** (SSR): always the first 10 reviews. The per-review rating field is `"rating"`
  (int 1–5), **not** `"overallRating"` (which is always `None`).
- **`longDescription`**: raw HTML string including `<ul>/<li>` tags. Strip tags before display.
- **`specifications`**: flat dict — confirmed 29–31 rows for electronics. Key names use display labels
  (e.g. `"RAM memory"`, `"Screen size"`, `"HD capacity"`).
- **`wasPrice` / `savings`** on detail page: same as search — `None` when item is not discounted.
- **No JSON-LD**: Walmart product pages do **not** include `<script type="application/ld+json">`.
  All structured data lives in `__NEXT_DATA__`.

---

## Store / Delivery Location

Results are per store. Ranking, badges ("Best seller", "N+ bought since yesterday"), sellers
and fulfillment all change with the location Walmart assigns. It picks that location from
the visitor's IP, so two sessions on different IPs can return the same page in different orders.

### Where the served location is

```
data.props.pageProps.initialData.pageMetadata.location
  .postalCode            — "95829"
  .storeId               — "3081"  (also .pickupStore / .deliveryStore)
  .city, .stateOrProvinceCode, .intentStrength ("IMPLICIT" = derived, not chosen)
data.props.pageProps.countryRegion
  .countryCode           — the visitor's IP country, or "not-available"
```

`pageMetadata.location` is there on browse (`/browse/...`) and seller (`/seller/<id>`) pages.
`countryRegion` and `searchResult.paginationV2.pageProperties.stores`, which echoes the store,
appear on browse pages only.

### Default location for visitors Walmart can't place

In the documented Israeli-exit session, `countryRegion.countryCode` returned `"not-available"`.
Walmart assigned **ZIP 95829, store 3081 (Sacramento, CA)**.
The `searchResult.debug.sisUrl` query included `isDefaulted=true` and `zipcode=94066&extended_zipcode=95829`.
Use `pageMetadata.location.postalCode` for the served ZIP; the internal `zipcode` parameter differs.

This observation covers one session in one country. It does not establish behavior across sessions or countries.
Check `pageMetadata.location.postalCode` and the store ID on every page.
For comparisons, keep only pages with the intended ZIP and store ID.
A fixed proxy country alone does not establish matching locations.

Field-tested 2026-09-26 through the Bright Data Scraping Browser with `-country-il`:
10 consecutive browse pages in one session all served 95829 / 3081.

### What changes with the store (Food department, field-tested 2026-10)

- An IP-placed session searches a primary store plus 8 nearby ones: `searchResult.debug.sisUrl` carries
  `stores=<id>&multiStoreIds=<8 ids>`. A proxy's US state-level targeting got the default above (95829 / 3081)
  instead of a store in that state.
- Writing the `assortmentStoreId` and `isoLoc` cookies with `document.cookie` from inside the page pinned the store
  for later requests. Some remote-browser providers reject cookie writes sent over CDP.
- How much the location matters depends on the department. Across 3 locations, the Food department's total moved
  ~0.2%. Only the store-assortment departments moved, by 1–28% (alcohol most): dairy & eggs, frozen, produce,
  meat & seafood, deli, bakery & bread, alcohol, international. Two pinned stores shared only 69–80% of their fresh
  produce. The rest of Food moved under 0.6%.

---

## Anti-Bot: PerimeterX

Walmart uses **PerimeterX** (app ID `PXu6b0qd2S`, confirmed in `runtimeConfig.perimeterX`).

| Signal | Detail |
|---|---|
| Bot detector | PerimeterX |
| Challenge page | "Robot or human?" — 200 OK, 15 KB HTML |
| Triggered by | Full browser UA strings (Chrome, curl, python-requests) |
| Bypassed by | `User-Agent: Mozilla/5.0` (bare prefix only) |
| No JS execution | SSR response is complete — no JS challenge to solve |

Detection in code:
```python
if "Robot or human" in html:
    raise RuntimeError("PerimeterX challenge — switch to browser harness")
```

If `http_get` starts returning the challenge after a run of successful fetches, switch to the
browser harness (see below).


### In remote browser sessions (field-tested 2026-10)

- About 50–70% of fresh remote-browser sessions landed on "Robot or human?" when loading a browse page (Bright Data
  Browser API reports it as the CDP event `Captcha.detected`). Its solver took 2–5 min and often failed. Dropping
  the session and opening a new one (another exit IP) was faster: ~20 s when clean.
- A 412 on an in-page `fetch()`: reload the page and retry; if the reload is challenged too, drop the session.
- Block images, fonts and media with `Network.setBlockedURLs`, which keeps the HTTP cache (request interception
  turns it off). Don't block CSS: without it the challenge stopped getting solved.

---

## Browser Harness Fallback

Use the browser harness when:
- PerimeterX starts blocking `http_get` on your IP
- You need to interact with the page (add to cart, filter UI, infinite scroll)
- You need variant switching (color/size selectors)

```python
# Browser-based search extraction
new_tab("https://www.walmart.com/search?q=laptop")
wait_for_load()
wait(2)  # JS renders product cards after readyState=complete

# Extract via __NEXT_DATA__ in-browser (identical structure to http_get)
import json
nd = js("document.getElementById('__NEXT_DATA__')?.textContent")
data = json.loads(nd)
sr = data["props"]["pageProps"]["initialData"]["searchResult"]
items = []
for stack in sr.get("itemStacks", []):
    items.extend(stack.get("items", []))
```

### Browser selectors (confirmed working for DOM-based extraction)

```python
# Product cards on search results page
results = js("""
  Array.from(document.querySelectorAll('[data-item-id]')).map(el => ({
    itemId:    el.getAttribute('data-item-id'),
    name:      el.querySelector('[itemprop="name"]')?.innerText?.trim(),
    price:     el.querySelector('[itemprop="price"]')?.getAttribute('content'),
    url:       el.querySelector('a[link-identifier]')?.href,
  })).filter(r => r.itemId)
""")

# If [data-item-id] misses items, use the Next.js data attribute alternative:
results_alt = js("""
  Array.from(document.querySelectorAll('[data-testid="list-view"]'))
    .map(el => el.innerText.trim())
""")
```

> **Prefer `__NEXT_DATA__` over DOM selectors** even in-browser — the JSON is complete and
> stable. DOM class names at Walmart are obfuscated and change between deployments.

### Session gotcha

Always open Walmart with `new_tab()` on first visit:
```python
new_tab("https://www.walmart.com/search?q=laptop")
wait_for_load()
wait(2)
```
After that, `goto_url()` works normally within the same session.

---

## Public API

Walmart's affiliate/partner API (`developer.api.walmart.com`) requires a registered API key
and returns HTTP 403 without one. No unauthenticated public product API is available.
The `__NEXT_DATA__` SSR approach replaces any need for the official API for read-only data.

---

## Gotchas

- **UA must be `Mozilla/5.0` bare**: Any fuller string (Chrome, Safari, curl, requests) hits
  PerimeterX. This is counterintuitive — the *shorter*, less realistic UA is the one that works.

- **Regex must use `id=` attribute match**: The regex
  `r'<script id="__NEXT_DATA__" type="application/json">...'` fails because the actual tag is
  `<script id="__NEXT_DATA__">` without `type`. Use:
  ```python
  re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
  ```

- **`usItemId` can be `None`**: ~5/66 items on a page are non-product ad widgets with no `usItemId`.
  Always filter: `[i for i in items if i.get("usItemId")]`.

- **Two `itemStacks`**: Walmart returns two stacks. Iterate over all stacks or you'll miss
  ~10 items from the second stack.

- **`canonicalUrl` includes tracking params**: Always strip with `.split("?")[0]`.

- **Review field is `"rating"` not `"overallRating"`**: Each `customerReviews` entry has a `"rating"`
  int field (1–5). The `"overallRating"` field is always `None`. Don't confuse with
  `product.averageRating` (the aggregate float).

- **No JSON-LD on product pages**: Zero `<script type="application/ld+json">` tags were found.
  All structured data is in `__NEXT_DATA__`.

- **`longDescription` is HTML**: Strip tags before text use. May contain promotional/financing copy
  mixed with real product description.

- **Page sizes vary**: Page 1 returned 66 items across 2 stacks; page 2 returned 55.
  Do not assume a fixed items-per-page count.

- **`http_get` default already sends `Mozilla/5.0`**: `helpers.http_get()` uses
  `"User-Agent": "Mozilla/5.0"` by default — no override needed when calling it directly.
  Only pass a custom `headers=` if you need to change something else.

- **`developer.api.walmart.com`** returns HTTP 403 without an API key. Not usable for
  unauthenticated scraping.
