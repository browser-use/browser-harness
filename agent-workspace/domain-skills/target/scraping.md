# Target — Category Listings & Product Details

Field-tested against www.target.com on 2026-10-23 using a Browser Use cloud browser (category listing, live PDP price) and http_get / plain urllib (product details).

robots.txt (checked 2026-10-23) for `User-agent: *` disallows `/s?` (search pages) and allows `/c/` category pages (including the `?Nao=` pagination links) and `/p/` product pages. redsky.target.com/robots.txt disallows `/` for all user agents, so this skill never sends a request to redsky itself; block 1 only reads the responses the category page already received.

## Quick summary

- **Search (`/s?searchTerm=...`) is disallowed by robots.txt**, so this skill lists products from **category pages** (`/c/<slug>/-/N-<id>`) instead. Get category URLs from the `/c/` breadcrumb links in a product page's HTML, from `bread_crumb_list` in block 1's listing response, or from Target's site navigation.
- **Category listings** are not in the HTML. The grid is filled client-side by the page's own `GET redsky.target.com/redsky_aggregations/v1/web/plp_search_v2` (title, price, rating, TCIN, URL) and `.../product_summary_with_fulfillment_v1` (shipping/pickup status). Block 1 loads the category page in the browser and reads those two responses with CDP `Network.getResponseBody`, so no extra request is made. Page 2+ is the page's own pagination URL `?Nao=24`, `?Nao=48`, ... (24 organic per page).
- **Product details** (`/p/-/A-<TCIN>`): plain HTTP GET returned **200** with `__NEXT_DATA__` holding the full product record (title, brand, DPCI, UPC, breadcrumbs, rating distribution, review/question counts, bullets, description, images). Price and fulfillment are **not** in that HTML (deferred modules).
- **Live price + fulfillment on a product page**: open it in the browser, read two `data-test` modules. They only render while the tab is visible; bringing a hidden tab to the front is an explicit opt-in (`ALLOW_FOREGROUND` in block 3).
- No JSON-LD product data on category or product pages (category pages have only a `WebPage` breadcrumb block, product pages had none).

## What works

### 1. Category listing, 2+ pages (browser, reads the page's own responses)

```python
import base64, html, json, re, time

CATEGORY_URL = "https://www.target.com/c/air-fryers-kitchen-appliances-dining/-/N-ncrpx"   # any /c/<slug>/-/N-<id> page
MAX_PAGES = 3   # 24 organic results per page

if not re.fullmatch(r"https://www\.target\.com/c/[^?#]+/-/N-[0-9A-Za-z]+", CATEGORY_URL):
    raise SystemExit("CATEGORY_URL must be https://www.target.com/c/<slug>/-/N-<id> with no query string")

LISTING = "/redsky_aggregations/v1/web/plp_search_v2"
SUMMARY = "/redsky_aggregations/v1/web/product_summary_with_fulfillment_v1"

def blocked(status, what="listing"):
    return (f"Target answered the category page's own {what} request with HTTP {status} "
            "(PerimeterX returns 435). Stop and back off; do not retry or try to solve the captcha.")

def body(session, request_id):
    r = cdp("Network.getResponseBody", session_id=session, requestId=request_id)
    return json.loads(base64.b64decode(r["body"]) if r.get("base64Encoded") else r["body"])

def navigate(url, timeout=15):
    """Load url in the attached tab and confirm the tab is really there before reading."""
    before = js("location.href")
    goto_url(url)
    deadline = time.time() + timeout
    while (href := js("location.href")) != url:
        if time.time() > deadline:
            raise RuntimeError(f"asked for {url} (tab was on {before}), tab is on {href}")
        time.sleep(0.2)

def read_page(session, timeout=30):
    """Read the JSON the page itself fetched while loading (no extra requests)."""
    reqs, listing, ful, start = {}, None, {}, time.time()
    while time.time() < start + timeout:
        for e in drain_events():
            if e.get("session_id") != session:   # events from other attached tabs
                continue
            m, p = e.get("method"), e.get("params") or {}
            if m == "Network.requestWillBeSent":
                url = p["request"]["url"]
                kind = "listing" if LISTING in url else "summary" if SUMMARY in url else None
                if kind:
                    reqs[p["requestId"]] = {"kind": kind}
            elif p.get("requestId") not in reqs:
                continue
            elif m == "Network.responseReceived":
                reqs[p["requestId"]]["status"] = p["response"]["status"]
            elif m == "Network.loadingFailed":
                raise RuntimeError(f"{reqs[p['requestId']]['kind']} request failed: {p.get('errorText')}")
            elif m == "Network.loadingFinished":
                r = reqs[p["requestId"]]
                if r.get("status") != 200:
                    if r["kind"] == "listing":
                        raise SystemExit(blocked(r.get("status")))
                    if r.get("status") == 435:
                        raise SystemExit(blocked(435, "fulfillment"))
                    raise RuntimeError(f"fulfillment request HTTP {r.get('status')}")
                data = body(session, p["requestId"])["data"]
                if r["kind"] == "listing":
                    listing = data["search"]
                else:
                    for s in data.get("product_summaries") or []:
                        ful[s["tcin"]] = s.get("fulfillment") or {}
        if listing is not None:
            missing = {p["tcin"] for p in listing.get("products") or []} - ful.keys()
            if not missing:
                return listing, ful
        time.sleep(0.2)
    if listing is None:
        raise RuntimeError(f"no {LISTING} response within {timeout} s, check the page: {page_info()}")
    raise RuntimeError(f"no fulfillment for {len(missing)} of {len(listing['products'])} TCINs within {timeout} s; "
                       "department landing pages (no 'page 1 of N' pager) do this, use a subcategory")

def parse(p, f):
    item = p.get("item") or {}
    parent = p.get("parent") or {}
    price = p.get("price") or parent.get("price") or {}
    stats = (p.get("ratings_and_reviews") or parent.get("ratings_and_reviews") or {}).get("statistics") or {}
    rating = stats.get("rating") or {}
    stores = f.get("store_options") or [{}]
    return {
        "tcin": p.get("tcin"),
        "title": html.unescape((item.get("product_description") or {}).get("title") or ""),
        "brand": (item.get("primary_brand") or {}).get("name"),
        "price": price.get("formatted_current_price"),   # "$59.99" or "See price in cart"
        "price_value": price.get("current_retail"),      # float, use .get: not every price object has it
        "reg_price": price.get("reg_retail"),
        "rating": rating.get("average"),                 # None for unrated items
        "rating_count": rating.get("count"),
        "url": (item.get("enrichment") or {}).get("buy_url"),
        "ship_status": (f.get("shipping_options") or {}).get("availability_status"),
        "pickup_status": (stores[0].get("order_pickup") or {}).get("availability_status"),
        "sold_out": f.get("sold_out"),
        "sponsored": bool(p.get("is_sponsored_sku")),
    }

def is_blank(url):   # the same blank-tab cases browser-harness's own new_tab() reuses
    url = url or ""
    return (url in ("", "about:blank", "data:text/html,") or url.startswith("about:blank#")
            or url.startswith(("chrome://newtab", "chrome://new-tab-page", "edge://newtab", "about:newtab")))

try:
    cur = current_tab()
except Exception:
    cur = {}
rows, seen, meta, tab = [], set(), {}, None
try:
    if cur.get("targetId") and is_blank(cur.get("url")):
        tab = cur.get("targetId")   # reuse the blank tab
    else:   # what new_tab() does, but the id is known before attaching, so finally can close it
        tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
    session = switch_tab(tab)     # its CDP session id; read_page ignores events from any other tab
    for page in range(MAX_PAGES):
        if page:
            time.sleep(3)   # polite pacing between page loads
        drain_events()
        navigate(f"{CATEGORY_URL}?Nao={page * 24}" if page else CATEGORY_URL)   # the page's own pagination URL
        listing, ful = read_page(session)
        meta = (listing.get("search_response") or {}).get("metadata") or {}
        if meta.get("offset") != page * 24:
            raise RuntimeError(f"asked for offset {page * 24}, page returned {meta.get('offset')}")
        products = listing.get("products") or []
        if not products:
            break
        for p in products:
            row = parse(p, ful[p["tcin"]])
            if row["sponsored"] or row["tcin"] in seen:   # sponsored slots and cross-page repeats
                continue
            seen.add(row["tcin"])
            rows.append(row)
        print(f"page {meta.get('current_page')}/{meta.get('total_pages')}: {len(products)} products, {len(rows)} unique so far")
        if meta.get("current_page", 0) >= (meta.get("total_pages") or 0):
            break
finally:
    if tab:
        close_tab(tab)

print("total_results:", meta.get("total_results"))
print(json.dumps(rows[:2], indent=1))
```

Observed output (trimmed):

```
page 1/12: 30 products, 24 unique so far
page 2/12: 30 products, 48 unique so far
page 3/12: 30 products, 72 unique so far
total_results: 270
[
 {
  "tcin": "92969684",
  "title": "Cuisinart Air Fryer Toaster Oven 7-in-1, 1800W Stainless Steel CTOA-122NAS",
  "brand": "Cuisinart",
  "price": "$139.99",
  "price_value": 139.99,
  "reg_price": 229.99,
  "rating": 4.01,
  "rating_count": 761,
  "url": "https://www.target.com/p/cuisinart-1800w-air-fryer-toaster-oven-stainless-steel-finish/-/A-92969684",
  "ship_status": "IN_STOCK",
  "pickup_status": "IN_STOCK",
  "sold_out": false,
  "sponsored": false
 },
 ...
]
```

With `MAX_PAGES = 20` the same category walked all 12 pages (the base URL, then `?Nao=24` to `?Nao=264`) and returned 270 unique rows, equal to `total_results`. Pages 1 to 4 each held 30 products, 24 organic plus 6 sponsored slots (`is_sponsored_sku: true`, some repeating an organic TCIN) that block 1 skips; pages 5 to 11 held 24 and page 12 held 6. "Fryers" (`/c/fryers-kitchen-appliances-dining/-/N-4rru8`, 349 results, 15 pages) returned 72 unique rows from 3 pages the same way.

### 2. Product details by TCIN (plain HTTP, no browser)

```python
import html, json, re

TCIN = "89110863"   # from the category rows above, or the A-<digits> part of any /p/ URL
TCIN = TCIN.strip().removeprefix("A-")   # accept "A-89110863" too

page = http_get(f"https://www.target.com/p/-/A-{TCIN}", headers={
    "User-Agent": "browser-harness/1.0 (target domain skill)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
})
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
if not m:
    raise SystemExit("no __NEXT_DATA__ (block page or layout change)")
queries = (json.loads(m.group(1)).get("props") or {}).get("dehydratedState", {}).get("queries") or []
layout = next((q["state"]["data"]["data"] for q in queries
               if str(q.get("queryKey", [""])[0]).endswith("fetch-cdui-layout-v1")), None)
core = next((mod["module_data"]["data"]["product"] for mod in (layout or {}).get("data_source_modules") or []
             if mod.get("module_type") == "ProductDetailWebDatasourceCore"), None)
if not core:
    raise SystemExit("no ProductDetailWebDatasourceCore module (block page, bad TCIN or layout change)")

item = core.get("item") or {}
desc = item.get("product_description") or {}
stats = (core.get("ratings_and_reviews") or {}).get("statistics") or {}
rating = stats.get("rating") or {}
images = (item.get("enrichment") or {}).get("image_info") or {}
detail = {
    "tcin": core.get("tcin"),
    "title": html.unescape(desc.get("title") or ""),
    "brand": (item.get("primary_brand") or {}).get("name"),
    "dpci": item.get("dpci"),
    "upc": (item.get("primary_barcode") or None),
    "url": (item.get("enrichment") or {}).get("buy_url"),
    "category_path": [b["name"] for b in (core.get("category") or {}).get("breadcrumbs") or []][1:],
    "rating": rating.get("average"),
    "rating_count": rating.get("count"),
    "review_count": stats.get("review_count"),
    "question_count": stats.get("question_count"),
    "rating_distribution": rating.get("distribution"),
    "highlights": [html.unescape(re.sub("<[^>]+>", "", b)) for b in (desc.get("soft_bullets") or {}).get("bullets") or []],
    "specs": [html.unescape(re.sub("<[^>]+>", "", b)) for b in desc.get("bullet_descriptions") or []],
    "description": html.unescape(re.sub("<[^>]+>", " ", desc.get("downstream_description") or "")).strip(),
    "package_dimensions": item.get("package_dimensions"),
    "primary_image": (images.get("primary_image") or {}).get("url"),
    "image_count": int(bool((images.get("primary_image") or {}).get("url"))) + len(images.get("alternate_images") or []),
}
print(json.dumps(detail, indent=1)[:2500])
```

Observed output (trimmed):

```
{
 "tcin": "89110863",
 "title": "Gourmia 6qt Digital Window Air Fryer with 12 Presets & Guided Cooking Black: Stainless Steel, 1-Year Warranty",
 "brand": "Gourmia",
 "dpci": "072-04-0231",
 "upc": "810002864582",
 "category_path": ["Kitchen & Dining", "Kitchen Appliances", "Fryers", "Air Fryers"],
 "rating": 4.07,
 "rating_count": 2297,
 "review_count": 1018,
 "question_count": 242,
 "rating_distribution": {"rating1": 379, "rating2": 108, "rating3": 73, "rating4": 153, "rating5": 1584},
 "highlights": ["6-QT capacity can cook family staples and party favorites for a variety of crowds", ...],
 "specs": ["Dimensions (Overall): 13.58 Inches (H) x 14.05 Inches (W) x 11.46 Inches (D)", "Weight: 12.1 Pounds", ...],
 "description": "Check on your food at-a-glance with the Gourmia 6-QT. Digital Window Air Fryer. ..."
}
```

The same request from `curl` with the same User-Agent also returned 200 and a 369 KB page. An unknown TCIN (`A-1`) returned HTTP 404, which `http_get` raises as `HTTPError`.

### 3. Live price and fulfillment on a product page (browser)

```python
import json, time

TCIN = "89110863".strip().removeprefix("A-")
ALLOW_FOREGROUND = False   # opt-in: True lets this block bring the tab to the front (visible tab switch)

URL = f"https://www.target.com/p/-/A-{TCIN}"

# what new_tab() does, but the id is known before attaching, so finally can close it
tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
try:
    switch_tab(tab)
    before = js("location.href")
    goto_url(URL)
    deadline = time.time() + 15
    while (href := js("location.href")) != URL:   # confirm the tab really is on the requested page before reading it
        if time.time() > deadline:
            raise SystemExit(f"asked for {URL} (tab was on {before}), tab is on {href}")
        time.sleep(0.2)
    wait_for_load()

    # Price and fulfillment are deferred modules, filled after load by
    # www.target.com/cdui_orchestrations/v1/pages/pdp/deferred_enrichment/modules
    # They stay a grey placeholder while the tab is hidden (document.visibilityState == "hidden").
    live = {}
    for i in range(20):
        live = js("""(() => {
          const t = s => (document.querySelector(s)?.innerText || '').trim();
          return {
            visibility: document.visibilityState,
            title: t('[data-test="product-title"]'),
            price_block: t('[data-test="module-product-detail-price-v2"]'),
            fulfillment: t('[data-test="module-product-detail-fulfillment-v1"]'),
            rating_block: t('[data-test="ratingFeedbackContainer"]'),
          };
        })()""")
        if live["price_block"] and live["fulfillment"]:
            break
        if i == 5 and live["visibility"] == "hidden":
            if not ALLOW_FOREGROUND:
                raise SystemExit("tab is hidden and the price/fulfillment modules did not render; "
                                 "set ALLOW_FOREGROUND = True to bring it to the front")
            activate_tab(current_tab())
        time.sleep(1)
    else:
        raise SystemExit(f"price/fulfillment modules did not render in 20 s: {json.dumps(live)}")
    print(json.dumps(live, indent=1))
finally:
    close_tab(tab)
```

Observed output (store name trimmed):

```
{
 "visibility": "visible",
 "title": "Gourmia 6qt Digital Window Air Fryer with 12 Presets & Guided Cooking Black: Stainless Steel, 1-Year Warranty",
 "price_block": "$59.99 reg $69.99\n$10 off",
 "fulfillment": "Pickup\nReady within 2 hours\nDelivery\nAs soon as 8pm today\nShipping\nArrives by Wed, Oct 28\nPickup at <nearest store>\nReady within 2 hours\nAlways free\nChange",
 "rating_block": "4.07 out of 5 stars\n2,297\n242 Questions"
}
```

If you only need price and stock for a TCIN, the category rows from block 1 already carry them, so this step is optional.

## Fields

Category listing (block 1). Product fields come from `plp_search_v2` `data.search.products[i]`; the fulfillment fields come from `product_summary_with_fulfillment_v1` `data.product_summaries[i].fulfillment`, matched by `tcin`.

| Field | Path | Example / notes |
|---|---|---|
| TCIN | `tcin` | `"92969684"`, Target's item id, the `A-<digits>` in URLs |
| Title | `item.product_description.title` | block 1 runs `html.unescape` (Target's search API escaped `&` as `&#38;`; no escapes seen in Air Fryers page 1) |
| Brand | `item.primary_brand.name` | `"Cuisinart"` |
| Price (display) | `price.formatted_current_price` | `"$139.99"`, or `"See price in cart"` (2 of 270 air fryer rows) |
| Price (number) | `price.current_retail`, `price.reg_retail` | `139.99`, `229.99`; falls back to `parent.price` when the item has none |
| Rating | `ratings_and_reviews.statistics.rating.average` | `4.01`; falls back to `parent.ratings_and_reviews`; `None` on 85 of 270 air fryer rows (unrated) |
| Rating count | `ratings_and_reviews.statistics.rating.count` | `761` (star ratings; written reviews are fewer, see PDP `review_count`) |
| URL | `item.enrichment.buy_url` | absolute `https://www.target.com/p/<slug>/-/A-<tcin>` |
| Shipping | `fulfillment.shipping_options.availability_status` | `IN_STOCK` on all 270 air fryer rows |
| Pickup | `fulfillment.store_options[0].order_pickup.availability_status` | `UNAVAILABLE`, `IN_STOCK`, `OUT_OF_STOCK`; for the store Target picked for the browser's IP |
| Sold out | `fulfillment.sold_out` | boolean |
| Sponsored | `is_sponsored_sku` | `true` on ad slots |
| Paging | `data.search.search_response.metadata` | `current_page`, `total_pages`, `total_results`, `count` (24), `offset` |

Other data in the same listing response, not parsed by block 1: `item.enrichment.image_info.primary_image.url` (scene7 image), `search_response.bread_crumb_list` (category path), `search_response.facet_list` (filters, each with its own `/c/...` URL), `search_response.sort_options`.

Product page (`ProductDetailWebDatasourceCore.module_data.data.product`, block 2): `tcin`, `item.product_description.{title,bullet_descriptions,soft_bullets.bullets,downstream_description}`, `item.dpci`, `item.primary_barcode` (UPC), `item.primary_brand`, `item.package_dimensions`, `item.enrichment.image_info`, `category.breadcrumbs`, `ratings_and_reviews.statistics.{rating.average,rating.count,rating.distribution,review_count,question_count,recommended_percentage}`.

## Gotchas

- **No extra requests.** Block 1 never calls redsky itself (its robots.txt disallows everything). It reads the two responses the category page fetched while loading, via the `Network.*` events the harness daemon records and `cdp("Network.getResponseBody", requestId=...)`. The daemon keeps only the last 500 events, so the block drains them before each navigation and polls every 0.2 s while the page loads. The event buffer is shared by every attached tab, so `read_page` keeps only events whose `session_id` is the block's own tab session (from `switch_tab`) and fetches bodies on that session. `navigate` records the tab's URL, loads the new one and waits until `location.href` equals it before any reading; block 3 does the same.
- **Pagination is a page load.** Clicking the pager's "next page" button changed the URL to `?Nao=24&moveTo=product-list-grid` and the page sent `plp_search_v2` with `offset=24`. Block 1 loads `?Nao=<offset>` directly and checks `metadata.offset` matches.
- **Use a subcategory, not a department landing page.** `/c/electronics/-/N-5xtg6` sent `plp_search_v2` (30 products) but rendered promos and carousels with no product grid or pager, and fulfillment arrived for only 9 of the 30 TCINs within 30 s. Block 1 stops with an error there. Leaf and mid-level categories (Air Fryers, Fryers) have the grid and the "page 1 of N" pager and worked.
- **Hidden tabs.** Block 1 also worked in a background tab (`visibilityState` `hidden`) for Air Fryers, so it does not need to bring the tab to the front.
- **Sponsored slots.** The first pages hold 30 products for `count=24`; the 6 extras are sponsored (`is_sponsored_sku: true`), and some repeat an organic TCIN on the same page. The block drops sponsored rows and dedupes by TCIN, and stops at `total_pages` or an empty page.
- **Results depend on location.** The store, pickup status and some prices come from the store Target picks for the browser's IP (`store_ids`, `zip` in the listing URL). In one cloud session the store was in New York and 266 of 270 air fryer rows were pickup `UNAVAILABLE`; another session got `IN_STOCK` for the first row.
- **A fresh browser can be blocked on its very first page load.** On 2026-10-23, 6 of 11 fresh cloud browser sessions got HTTP 435 (PerimeterX) on the category page's first load, with no earlier requests: 5 on its own `plp_search_v2` request (block 1 stops with its block message) and 1 on `product_summary_with_fulfillment_v1` (block 1 stops with `fulfillment request HTTP 435`). Back off; do not retry in that session or try to solve the captcha. Twice a new session started 5 to 6 minutes later ran all blocks. Another time 4 sessions in a row were blocked, with waits of about 5, 10 and 15 minutes between them, and a fifth, about 20 minutes after the fourth, ran blocks 1 and 3. Block 2 (plain HTTP) still returned 200 from the first of those blocked sessions.
- **Pacing.** Block 1 waits 3 s between page loads. In unblocked sessions on 2026-10-23, about 30 category page loads (including one 12-page walk) produced no 429 and no new block; heavier rates were not tested.
- **Tabs.** Block 1 reuses the current tab if it is blank (the same URLs browser-harness's `new_tab()` treats as blank: empty, `about:blank`, `about:blank#...`, `data:text/html,`, and the Chrome/Edge new tab pages), otherwise it creates a background tab the way `new_tab()` does; block 3 always creates its own. Both take the tab id before attaching and close the tab in `finally`, so an error at any step after creation still closes it. In fresh cloud browsers on 2026-10-23, `list_tabs()` showed 0 open tabs after block 1 stopped on a 435 and after block 3 finished. When block 1 left an extra blank tab open, block 3's new background tab stayed `hidden` and stopped with its `ALLOW_FOREGROUND` message. Closing the last tab left the cloud browser with 0 tabs, and the next `new_tab()` still worked. Once, with three tabs open, `goto_url` for page 2 raised `Page.navigate timed out after 5s`; it did not recur with one tab.
- **Hidden tabs do not render the PDP price.** In a background tab the price module stayed a placeholder (`data-test="price-module-placeholder"`) and `visibilityState` was `hidden`; `activate_tab(current_tab())` fixed it. Block 3 does that only with `ALLOW_FOREGROUND = True` because it visibly switches tabs; otherwise it stops with a message. In a cloud browser with only this tab open, the new tab was already `visible` and rendered the price without it.
- **DOM selectors (fallback).** Category cards were `[data-test="@web/site-top-of-funnel/ProductCardWrapper"]` (30 on Air Fryers page 1 on desktop) and the pager `[data-test="listing-page-pagination"]` read `page 1 of 12`. Prefer the JSON.
- No cookie/consent banner blocked anything on www.target.com from a US exit IP.

## What does not work

- **Search pages (`/s?searchTerm=...`)**: disallowed for all user agents by robots.txt, so this skill does not use them. Start from a category page (block 1) or from known TCINs or product URLs (blocks 2 and 3).
- **Plain HTTP category page**: `https://www.target.com/c/air-fryers-kitchen-appliances-dining/-/N-ncrpx` returned 200 and a 164 KB page whose `__NEXT_DATA__` held no products (6 `/p/` links in the whole HTML); the grid is filled client-side.
- **Calling redsky yourself**: redsky.target.com/robots.txt disallows `/` for all user agents, so neither block 1 nor any other block sends requests there. Plain-HTTP calls to Target's APIs also returned **435** (PerimeterX) earlier on 2026-10-23.
- **Price/stock from product HTML**: the `ProductDetailPrice` and fulfillment modules in `__NEXT_DATA__` are `is_enrichment_deferred: true` with no data; use block 1 or block 3.
- **JSON-LD**: no product data on category or product pages.
