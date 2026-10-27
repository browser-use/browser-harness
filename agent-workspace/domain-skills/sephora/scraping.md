# Sephora — Category Listings & Product Details

Field-tested against www.sephora.com on 2026-10-23 and 2026-10-24 using a Browser Use cloud browser (plain HTTP was also tried and refused).

robots.txt (fetched 2026-10-23) for `User-agent: *` disallows `/search`, `/browse/`, `/gway/`, `/basket`, `/profile/...` and others, allows `/shop/` category pages, `/brand/` pages and `/product/` pages, and sets `Crawl-delay: 5`. This skill only loads `/`, `/shop/<slug>`, `/brand/<slug>` and `/product/<slug>-P<id>` and waits 5 s between page loads.

## Quick summary

- **No plain HTTP.** `curl` with a truthful User-Agent got Akamai `403 Access Denied` for `/shop/...` and `/product/...` (robots.txt and sitemap.xml returned 200). Use the browser.
- **Everything is in one embedded JSON blob.** Every fully loaded Sephora page in testing (home, category, brand, product, sale) had `<script id="linkStore" type="text/json">`. On a category page `page.nthCategory` holds 60 products per page plus `totalProducts`, `pageSize`, `currentPage`; on a brand page the same shape is `page.nthBrand`; on a product page `page.product` holds the product, the default SKU and every variant SKU (`regularChildSkus`).
- **Pagination is `?currentPage=N`** (60 per page). Face Serums: 519 products, 9 pages, page 9 held 39. Past the end (`?currentPage=99`) returns an empty `products` list, no error.
- **Product pages also carry JSON-LD** `ProductGroup` with one `Product` per variant (`sku`, `offers.price`, `offers.availability`) and `aggregateRating`. Its `reviews` array contains reviewer handles, so this skill does not output it.
- **Expect an occasional `Access Denied`.** In the first cloud browser of the day, the first navigation (a direct `/shop/` URL) got Akamai `403 Access Denied`. Both blocks open the homepage first, the way a visitor arrives, and stop (no retry loop) on any `Access Denied` page.

## What works

### 1. Category or brand listing, 2+ pages (browser, embedded `linkStore`)

```python
import json, re, time

LIST_URL = "https://www.sephora.com/shop/face-serum"   # a /shop/<category> or /brand/<brand> page
MAX_PAGES = 3      # 60 products per page
PAUSE = 5          # seconds between page loads; robots.txt asks for Crawl-delay: 5

if not re.fullmatch(r"https://www\.sephora\.com/(shop|brand)/[a-z0-9-]+", LIST_URL):
    raise SystemExit("LIST_URL must be https://www.sephora.com/shop/<slug> or /brand/<slug>, no query string")

def load(url, timeout=30):
    """Navigate the attached tab once, wait until location.href is exactly url, return the page's linkStore JSON."""
    deadline = time.time() + timeout
    try:
        goto_url(url)
    except TimeoutError:   # the harness stops waiting for Page.navigate after 5 s; the page may still arrive
        pass
    while True:
        try:
            state = js("""(() => ({href: location.href, title: document.title, ready: document.readyState,
                           store: document.getElementById('linkStore')?.textContent || ''}))()""") or {}
        except TimeoutError:   # page still busy with the navigation
            state = {}
        if "Access Denied" in (state.get("title") or ""):
            raise SystemExit(f"Sephora's CDN answered {url} with 'Access Denied' (HTTP 403). "
                             "Stop and back off; do not retry in a loop.")
        if state.get("href") == url and state.get("ready") == "complete" and state.get("store"):
            return json.loads(state["store"])
        if time.time() >= deadline:
            raise RuntimeError(f"{url} did not load with a linkStore in {timeout} s, tab is on {state.get('href')}")
        time.sleep(0.5)

def parse(p):
    sku = p.get("currentSku") or {}
    return {
        "product_id": p.get("productId"),                 # "P480284"
        "sku_id": sku.get("skuId"),                      # default SKU shown on the tile
        "brand": p.get("brandName"),
        "name": p.get("displayName"),
        "price": sku.get("listPrice"),                   # "$129.00" or a range "$96.00 - $142.00"
        "value_price": sku.get("valuePrice"),            # sets only: combined value of the items
        "rating": float(p["rating"]) if p.get("rating") else None,
        "reviews": int(p["reviews"]) if p.get("reviews") else 0,
        "variants": p.get("numberOfVariants"),
        "variation_type": p.get("variationType"),        # "Size", "Color", ...
        "sponsored": bool(p.get("sponsored")),
        "url": "https://www.sephora.com" + p["targetUrl"] if p.get("targetUrl") else None,
    }

# Reuse a tab already on sephora.com, otherwise enter via the homepage
# (in a fresh browser the first direct /shop/ load was denied in testing, the homepage was not).
opened_tab = None   # set only if this block opened the tab; it never closes a tab it did not open
href = js("location.href") or ""
if not href.startswith("https://www.sephora.com/"):
    opened_tab = new_tab("https://www.sephora.com/")
    wait_for_load()
    if "Access Denied" in (js("document.title") or ""):
        raise SystemExit("Sephora denied the homepage for this browser. Stop and back off.")

rows, seen, listing, total, size, pages_read = [], set(), {}, 0, 60, 0
for page in range(1, MAX_PAGES + 1):
    time.sleep(PAUSE)
    url = LIST_URL if page == 1 else f"{LIST_URL}?currentPage={page}"
    pg = load(url).get("page") or {}
    listing = pg.get("nthCategory") or pg.get("nthBrand")
    if not listing:
        raise RuntimeError(f"{url} has no page.nthCategory / page.nthBrand in linkStore: {list(pg)}")
    if int(listing.get("currentPage") or 1) != page:   # page 1 has currentPage None
        raise RuntimeError(f"asked for page {page}, linkStore says currentPage={listing.get('currentPage')}")
    if listing.get("totalProducts") is None:
        raise RuntimeError(f"{url}: listing has no totalProducts, cannot tell when the walk is complete")
    total, size = int(listing["totalProducts"]), int(listing.get("pageSize") or 60)
    products = listing.get("products") or []
    if not products and (page - 1) * size < total:
        raise RuntimeError(f"{url} has 0 products but totalProducts={total} means page {page} should not be empty")
    for p in products:
        if not p.get("productId") or not p.get("targetUrl"):   # required: identity and link
            raise RuntimeError(f"{url}: product card without productId/targetUrl, keys {sorted(p)[:12]}")
        row = parse(p)
        if row["product_id"] in seen:
            continue
        seen.add(row["product_id"])
        rows.append(row)
    pages_read = page
    print(f"page {page}/{-(-total // size)}: {len(products)} products, {len(rows)} unique so far")
    if page * size >= total:
        break

pages_total = -(-total // size)
print(listing.get("displayName"), listing.get("categoryId") or listing.get("brandId"), "totalProducts:", total)
if pages_read >= pages_total:
    if len(rows) != total:   # e.g. the listing shifted mid-walk: duplicates skipped, other products never seen
        raise RuntimeError(f"read {pages_read}/{pages_total} pages but got {len(rows)} unique products, "
                           f"totalProducts={total}; the walk is not complete")
    print(f"status: complete, {pages_read}/{pages_total} pages read, {len(rows)} unique rows")
else:
    print(f"status: PARTIAL, MAX_PAGES={MAX_PAGES} reached at page {pages_read}/{pages_total}: "
          f"{len(rows)} of {total} products, raise MAX_PAGES for the rest")
print(json.dumps(rows[:2], indent=1, ensure_ascii=False))
print(f"tab: opened {opened_tab}" if opened_tab else "tab: reused the existing sephora.com tab")
```

Observed output (fresh cloud browser, trimmed):

```
page 1/9: 60 products, 60 unique so far
page 2/9: 60 products, 120 unique so far
page 3/9: 60 products, 180 unique so far
Face Serums cat60103 totalProducts: 519
status: PARTIAL, MAX_PAGES=3 reached at page 3/9: 180 of 519 products, raise MAX_PAGES for the rest
[
 {
  "product_id": "P94421",
  "sku_id": "2744423",
  "brand": "Caudalie",
  "name": "Vinoperfect Brightening Dark Spot Serum Vitamin C Alternative",
  "price": "$82.00 - $119.00",
  "value_price": null,
  "rating": 4.2648,
  "reviews": 4271,
  "variants": 2,
  "variation_type": "Size",
  "sponsored": false,
  "url": "https://www.sephora.com/product/vinoperfect-brightening-dark-spot-serum-vitamin-c-alternative-P94421?skuId=2744423"
 },
 ...
]
tab: opened 458A283D2E3A9A0E04151F5C7C8BB2D6
```

The `status:` line says whether the walk is complete; with the default `MAX_PAGES = 3` it is `PARTIAL`, so never treat those rows as the whole category. With `MAX_PAGES = 20` the same category walked all 9 pages (`?currentPage=2` to `?currentPage=9`, the last with 39 products) and printed `status: complete, 9/9 pages read, 519 unique rows`, equal to `totalProducts`. `LIST_URL = "https://www.sephora.com/brand/the-ordinary"` printed `status: complete, 2/2 pages read, 67 unique rows` (60 + 7), equal to its `totalProducts`. The block raises instead of returning rows when a page before `totalProducts` is reached comes back empty, a card has no `productId` or `targetUrl`, the listing has no `totalProducts`, or every page was read but the unique row count differs from `totalProducts`.

### 2. Product details and all variants (browser, embedded `linkStore` + JSON-LD)

Pass any product URL from block 1 (`rows[i]["url"]`); the `?skuId=` part is dropped.

```python
import html, json, re, time

PRODUCT_URL = "https://www.sephora.com/product/studio-fix-powder-plus-foundation-24hr-oil-control-blur-matte-finish-12hr-buildable-coverage-P516457"
PAUSE = 5   # seconds between page loads (robots.txt Crawl-delay: 5)

PRODUCT_URL = PRODUCT_URL.split("?")[0].split("#")[0]   # ?skuId=... from listing URLs is optional
m = re.fullmatch(r"https://www\.sephora\.com/product/[^/?#]*?(P\d+)", PRODUCT_URL)
if not m:
    raise SystemExit("PRODUCT_URL must look like https://www.sephora.com/product/<slug>-P<digits>")
PRODUCT_ID = m.group(1)

def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

# Reuse a tab already on sephora.com (e.g. after the category block), otherwise enter via the homepage.
opened_tab = None   # set only if this block opened the tab; it never closes a tab it did not open
href = js("location.href") or ""
if not href.startswith("https://www.sephora.com/"):
    opened_tab = new_tab("https://www.sephora.com/")
    wait_for_load()
    if "Access Denied" in (js("document.title") or ""):
        raise SystemExit("Sephora denied the homepage for this browser. Stop and back off.")
time.sleep(PAUSE)

deadline = time.time() + 30
try:
    goto_url(PRODUCT_URL)
except TimeoutError:   # the harness stops waiting for Page.navigate after 5 s; the page may still arrive
    pass
while True:
    try:
        state = js("""(() => ({href: location.href, title: document.title, ready: document.readyState,
                       store: document.getElementById('linkStore')?.textContent || '',
                       ld: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent)}))()""") or {}
    except TimeoutError:   # page still busy with the navigation
        state = {}
    if "Access Denied" in (state.get("title") or ""):
        raise SystemExit(f"'Access Denied' (HTTP 403) for {PRODUCT_URL}. Stop and back off.")
    on_url = re.fullmatch(re.escape(PRODUCT_URL) + r"(\?skuId=\d+)?", state.get("href") or "")
    if on_url and state.get("ready") == "complete" and state.get("store"):
        break
    if time.time() >= deadline:
        raise RuntimeError(f"{PRODUCT_URL} did not load with a linkStore in 30 s, tab is on {state.get('href')}")
    time.sleep(0.5)

prod = (json.loads(state["store"]).get("page") or {}).get("product")
if not prod or prod.get("productId") != PRODUCT_ID:
    raise RuntimeError(f"linkStore has no page.product for {PRODUCT_ID} (got {prod and prod.get('productId')})")
if not all(s.get("skuId") for s in prod.get("regularChildSkus") or [prod.get("currentSku") or {}]):
    raise RuntimeError(f"{PRODUCT_ID}: a variant SKU has no skuId")

# JSON-LD ProductGroup: per-variant price + availability (skip its 'reviews', they carry reviewer handles)
offers = {}
for raw in state.get("ld") or []:
    try:
        d = json.loads(raw)
    except ValueError:
        continue
    if d.get("@type") in ("ProductGroup", "Product"):
        for v in d.get("hasVariant") or [d]:
            o = v.get("offers") or {}
            if v.get("sku"):
                offers[v["sku"]] = {"price": o.get("price"), "currency": o.get("priceCurrency"),
                                    "availability": (o.get("availability") or "").rsplit("/", 1)[-1]}

pd = prod.get("productDetails") or {}
cur = prod.get("currentSku") or {}
variants = []
for s in prod.get("regularChildSkus") or [cur]:
    variants.append({
        "sku_id": s.get("skuId"),
        "value": s.get("variationValue"),             # shade name / size
        "description": s.get("variationDesc"),
        "size": s.get("size"),
        "list_price": s.get("listPrice"),
        "out_of_stock": s.get("isOutOfStock"),
        "few_left": s.get("isOnlyFewLeft"),
        "availability": (offers.get(s.get("skuId")) or {}).get("availability"),
        "image": (s.get("skuImages") or {}).get("imageUrl"),
        "url": "https://www.sephora.com" + s["targetUrl"] if s.get("targetUrl") else None,
    })

detail = {
    "product_id": prod.get("productId"),
    "brand": cur.get("brandName"),
    "brand_id": (pd.get("brand") or {}).get("brandId"),
    "name": pd.get("displayName"),
    "category": (prod.get("parentCategory") or {}).get("displayName"),
    "rating": pd.get("rating"),
    "reviews": pd.get("reviews"),
    "loves": pd.get("lovesCount"),
    "variation_type": prod.get("variationType"),      # "Color", "Size", ...
    "default_sku": cur.get("skuId"),
    "price": cur.get("listPrice"),
    "short_description": text(pd.get("shortDescription"))[:300],
    "ingredients": text(cur.get("ingredientDesc") or next(   # per SKU; some SKUs have none
        (s["ingredientDesc"] for s in prod.get("regularChildSkus") or [] if s.get("ingredientDesc")), ""))[:300],
    "how_to_use": text(pd.get("suggestedUsage"))[:300],
    "url": PRODUCT_URL,
    "variant_count": len(variants),
    "variants": variants,
}
print(json.dumps({**detail, "variants": variants[:3]}, indent=1, ensure_ascii=False))
print("variants with JSON-LD offer:", sum(1 for v in variants if v["availability"]), "of", len(variants))
print(f"tab: opened {opened_tab}" if opened_tab else "tab: reused the existing sephora.com tab")
```

Observed output (same browser, right after block 1, trimmed to 3 of 71 variants):

```
{
 "product_id": "P516457",
 "brand": "MAC Cosmetics",
 "brand_id": "8010",
 "name": "Studio Fix Powder Plus Foundation with 24HR Oil Control + Blur-Matte Finish",
 "category": "Foundation",
 "rating": 4.259,
 "reviews": 1197,
 "loves": 49904,
 "variation_type": "Color",
 "default_sku": "3018157",
 "price": "$39.00",
 "short_description": "What it is: A talc-free, two-in-one foundation and setting powder with a blur-matte finish and up to 24-hour oil control. Coverage: Full Finish: Matte ...",
 "ingredients": "Synthetic Fluorphlogopite, Magnesium Potassium Fluorosilicate, Boron Nitride, ...",
 "how_to_use": "Suggested Usage: -Apply powder to prepped skin. ...",
 "url": "https://www.sephora.com/product/studio-fix-powder-plus-foundation-24hr-oil-control-blur-matte-finish-12hr-buildable-coverage-P516457",
 "variant_count": 71,
 "variants": [
  {
   "sku_id": "3018215",
   "value": "N3",
   "description": "Very fair with neutral peach undertone for fair skin",
   "size": "0.4 oz/12 mL",
   "list_price": "$39.00",
   "out_of_stock": false,
   "few_left": false,
   "availability": "InStock",
   "image": "https://www.sephora.com/productimages/sku/s3018215-main-zoom.jpg",
   "url": "https://www.sephora.com/product/studio-fix-powder-plus-foundation-24hr-oil-control-blur-matte-finish-12hr-buildable-coverage-P516457?skuId=3018215"
  },
  ...
 ]
}
variants with JSON-LD offer: 71 of 71
tab: reused the existing sephora.com tab
```

Neither block closes a tab. Each ends with `tab: opened <targetId>` if it opened the tab itself, or `tab: reused ...` if it ran in a tab that was already on sephora.com. When done, close only a tab your own run opened, by that id: `close_tab("<targetId>")`. A reused tab belongs to whoever opened it.

## Fields

Listing (`page.nthCategory.products[i]` or `page.nthBrand.products[i]`, block 1):

| Field | Path | Example / notes |
|---|---|---|
| Product ID | `productId` | `"P480284"`, the `-P<digits>` at the end of product URLs |
| SKU ID | `currentSku.skuId` | `"2838266"`, the default SKU on the tile, also `?skuId=` in `targetUrl` |
| Brand | `brandName` | `"Caudalie"` |
| Name | `displayName` | product name without brand |
| Price | `currentSku.listPrice` | string, `"$129.00"` or a range `"$96.00 - $142.00"` when sizes differ in price |
| Set value | `currentSku.valuePrice` | only on some sets, e.g. `"$105.00"` next to listPrice `"$82.00"` |
| Rating | `rating` | string `"4.7318"`, block 1 casts to float |
| Review count | `reviews` | string `"1137"`, block 1 casts to int |
| Variants | `numberOfVariants`, `variationType` | `71`, `"Color"`; a price range can show with `numberOfVariants` 1, so use block 2 for the real variant list |
| Sponsored | `sponsored` | boolean; `false` on all products seen (Face Serums pages 1 to 3, Foundation page 1, The Ordinary) |
| URL | `targetUrl` | relative `/product/<slug>-P<id>?skuId=<sku>` |
| Image | `heroImage` | `https://www.sephora.com/productimages/sku/s<sku>-main-zoom.jpg?imwidth=270...` |
| Flags | `currentSku.isNew`, `isBestseller`, `isSephoraExclusive`, `isLimitedEdition`, `isOnlineOnly`, `badge` | booleans / badge slug |
| Paging | `totalProducts`, `pageSize`, `currentPage` | `519`, `60`, `None` on page 1 then `2`, `3`, ... |

Other keys on the listing object: `categoryId` (`"cat60103"`), `displayName`, `categories` (category tree with `recordCount` and `targetUrl` for every subcategory, useful to discover more `/shop/` slugs), `refinements` (20 filter groups on Face Serums), `seoCanonicalUrl`.

Product page (`page.product`, block 2):

| Field | Path | Example / notes |
|---|---|---|
| Product ID | `productId` | `"P516457"` |
| Name, rating, reviews, loves | `productDetails.displayName`, `.rating`, `.reviews`, `.lovesCount` | `4.259`, `1197`, `49904` (numbers here, not strings) |
| Brand | `currentSku.brandName`, `productDetails.brand.brandId` | `"MAC Cosmetics"`, `"8010"` |
| Category | `parentCategory.displayName` | `"Foundation"` |
| Descriptions | `productDetails.shortDescription`, `.longDescription`, `.suggestedUsage` | HTML strings |
| Ingredients | `currentSku.ingredientDesc` or each variant's `ingredientDesc` | HTML; `None` on the default SKU of P516457, present on 68 of its 71 variants |
| Variants | `regularChildSkus[]` | 71 for P516457 (includes the default SKU); 1 for a single-size serum |
| Variant fields | `skuId`, `variationValue`, `variationDesc`, `size`, `listPrice`, `isOutOfStock`, `isOnlyFewLeft`, `skuImages.imageUrl`, `targetUrl` | `"3018215"`, `"N3"`, `"Very fair with neutral peach undertone..."`, `"0.4 oz/12 mL"`, `"$39.00"` |
| Variant offer | JSON-LD `ProductGroup.hasVariant[].offers` | `price` `"39.00"`, `priceCurrency` `"USD"`, `availability` `https://schema.org/InStock`; matched 71 of 71 SKUs by `sku` |

## Gotchas

- **`Access Denied` happens, and it is a stop signal.** Observed on 2026-10-23 in the first cloud browser: its first navigation, straight to `/shop/moisturizing-cream-oils-mists`, got Akamai `Access Denied`; 60 s later the homepage loaded fine, but a direct load of the same category right after it was denied again. Later in that same browser (after a few minutes on the site) direct `/shop/`, `/brand/` and `/product/` loads all worked. In 3 later fresh cloud browsers (2026-10-23 and 2026-10-24), block 1 (homepage, 5 s pause, then direct category loads) was never denied; in a 4th (2026-10-24) the homepage loaded and the first `/shop/face-serum` load was denied, and a separate fresh browser started 5 minutes later for this test ran both blocks without a denial. The blocks raise `SystemExit` on any `Access Denied` title; when that happens stop and back off for several minutes rather than retrying or rotating browsers.
- **Slow navigations.** On 2026-10-24 one `?currentPage=4` load took longer than the harness's 5 s wait for `Page.navigate`, and `goto_url` raised `TimeoutError`. The blocks catch that exception (and a timed-out `js` poll), keep polling the same navigation until their 30 s deadline, and never navigate a second time.
- **Client-side navigation does not refresh `linkStore`.** Clicking a category link inside the site loads products through a separate XHR and leaves the homepage's `linkStore` in the DOM (`page.home`). The blocks use full page loads (`goto_url`) and check `location.href` plus the page type (`nthCategory` / `nthBrand` / `product.productId`) before reading.
- **"Show More Products" is not pagination.** On Face Serums it sent no new product request (all 60 of the page were already in `linkStore`); it only renders more tiles. Use `?currentPage=N`.
- **Lazy-loaded tiles.** The DOM only had 4 to 12 `ProductTile` elements rendered at a time, while `linkStore` had all 60. Do not scrape tiles.
- **Location.** The header shows a store and delivery ZIP picked from the browser's IP. The listing's `pickupEligible` / `sameDayEligible` / `shipToHomeEligible` flags were `false` on every product in the server-rendered `linkStore` (Face Serums page 2), so treat them as unreliable there and check availability on the product page (block 2).
- **`/sale` is a content page** with no `products` in `linkStore`; use a `/shop/` category or a `/brand/` page.
- **Pacing.** robots.txt asks for `Crawl-delay: 5`; the blocks sleep 5 s before every page load. In the 2026-10-24 test browser, the homepage plus 15 page loads at that pace (including the full 9-page Face Serums walk) produced no denial; faster rates were not tested.
- No cookie/consent banner appeared in the page text of the homepage, category or product pages from a US exit IP.

## What does not work

- **Plain HTTP** (`curl`/`urllib`/`http_get` without the browser) to `/shop/...`, `/product/...`: `403 Access Denied` from Akamai. Changing the User-Agent to pass is not acceptable, so this skill uses the browser.
- **Search** (`/search?keyword=...`): disallowed by robots.txt, not used. Start from `/shop/` categories (see `categories` in block 1's listing object, or the homepage nav links) or `/brand/<slug>`.
- **Calling the listing API yourself**: on client-side navigation the page fetches `api-developer.sephora.com/v1/browseSearchProduct`; that host returned `403` even for its robots.txt, so this skill never calls it and reads the server-rendered `linkStore` instead.
- **Reviews**: the JSON-LD `reviews` array on product pages holds a few recent reviews with reviewer handles; not extracted here.
