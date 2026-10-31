# TCGplayer - Card Search, Market Price and Listings

Field-tested against www.tcgplayer.com on 2026-10-31 using a Browser Use cloud browser, logged out (plain HTTP was tried for product pages and returns an empty app shell, see below).

robots.txt (checked 2026-10-31) for `User-agent: *` allows `/` with `Crawl-Delay: 10` and disallows `/search/*/product?seller=*`, `/sellers/*/product/*`, `/search/articles`, `/search/decks`, `/login` and two `/content/.../deck` paths; this skill only opens `/search/<line>/product?productLineName=...&q=...` and `/product/<id>`, waits 10 s between page loads, and reads the JSON those pages fetch themselves.

## Quick summary

- Search (`/search/<line>/product?productLineName=<line>&q=<q>&view=grid&page=N`) and product pages (`/product/<id>`) are a client-side app. The HTML has no product data, no JSON-LD and a generic `<title>`.
- The data comes from the page's own XHRs: search results from `POST mp-search-api.tcgplayer.com/v1/search/request` (24 products per page, with `marketPrice`, `lowestPrice`, `totalListings`), product data from `GET mp-search-api.tcgplayer.com/v2/product/<id>/details`, the cheapest 10 listings from `POST mp-search-api.tcgplayer.com/v1/product/<id>/listings`, and recent sales from `POST mpapi.tcgplayer.com/v2/product/<id>/latestsales`. Both blocks below load the public page in the browser and read those responses with CDP `Network.getResponseBody`; they never call the API hosts themselves.
- `<line>` is TCGplayer's product-line slug: `magic`, `pokemon`, `yugioh`, `lorcana-tcg`, `one-piece-card-game`, `digimon-card-game`, `flesh-and-blood-tcg`, `star-wars-unlimited`, ... (71 lines in the `productLines` response the search page loads).
- `/product/<id>` needs no slug; any slug is ignored (`/product/1032/lightning-bolt` loaded product 1032, Aspect of Wolf).
- About 15 page loads at 10 s spacing in one cloud browser: every API response was HTTP 200, no captcha, no login wall, no consent wall.

## What works

### 1. Card search, multi-page (browser, reads the page's own search response)

```python
import base64, json, re, time, urllib.parse

CRAWL_DELAY_S = 10        # robots.txt: Crawl-Delay: 10
SEARCH_API = "mp-search-api.tcgplayer.com/v1/search/request"

def search_url(line, q, page=1):
    """The same URL shape the site's own 'Shop All' links and pager use."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", line) or not q.strip():
        raise ValueError("line must be a productLineUrlName like 'magic' and q must be non-empty")
    qs = urllib.parse.urlencode({"productLineName": line, "q": q, "view": "grid", "page": page})
    url = f"https://www.tcgplayer.com/search/{line}/product?{qs}"
    if "seller=" in url:   # robots.txt: Disallow: /search/*/product?seller=*
        raise ValueError("refusing a seller-filtered search URL")
    return url

def challenge_check():
    t = (js("document.title") or "").lower()
    body = (js("document.body ? document.body.innerText.slice(0, 400) : ''") or "").lower()
    if any(s in t + body for s in ("just a moment", "access denied", "attention required", "verify you are human")):
        raise SystemExit(f"challenge page on {js('location.href')}: stop and back off, do not retry")

def read_search(session, want_q, want_from, timeout=30):
    """Return the JSON of the search request the page itself sent (no extra requests are made)."""
    reqs, start = {}, time.time()
    while time.time() < start + timeout:
        for e in drain_events():
            if e.get("session_id") != session:
                continue
            m, p = e.get("method"), e.get("params") or {}
            if m == "Network.requestWillBeSent":
                r = p["request"]
                q = urllib.parse.parse_qs(urllib.parse.urlparse(r["url"]).query).get("q", [""])[0]
                if SEARCH_API in r["url"] and r["method"] == "POST" and q == want_q:
                    reqs[p["requestId"]] = {"post": json.loads(r.get("postData") or "{}")}
            elif p.get("requestId") not in reqs:
                continue
            elif m == "Network.responseReceived":
                reqs[p["requestId"]]["status"] = p["response"]["status"]
            elif m == "Network.loadingFailed":
                raise RuntimeError(f"search request failed: {p.get('errorText')}")
            elif m == "Network.loadingFinished":
                r = reqs[p["requestId"]]
                if r.get("status") != 200:
                    raise SystemExit(f"search API answered HTTP {r.get('status')}: stop and back off, do not retry")
                if r["post"].get("from") != want_from:
                    continue   # an earlier page's request still finishing
                b = cdp("Network.getResponseBody", session_id=session, requestId=p["requestId"])
                data = json.loads(base64.b64decode(b["body"]) if b.get("base64Encoded") else b["body"])
                if data.get("errors"):
                    raise RuntimeError(f"search API errors: {data['errors']}")
                return data["results"][0]
        time.sleep(0.2)
    challenge_check()
    raise RuntimeError(f"no {SEARCH_API} response with from={want_from} within {timeout} s: {page_info()}")

def row(it):
    ca = it.get("customAttributes") or {}
    pid = int(it["productId"])
    return {
        "product_id": pid,
        "name": it.get("productName"),
        "set": it.get("setName"),
        "set_code": it.get("setCode"),
        "rarity": it.get("rarityName"),
        "number": ca.get("number"),
        "market_price": it.get("marketPrice"),
        "lowest_price": it.get("lowestPrice"),
        "lowest_price_with_shipping": it.get("lowestPriceWithShipping"),
        "listings": int(it.get("totalListings") or 0),
        "sealed": it.get("sealed"),
        "url": f"https://www.tcgplayer.com/product/{pid}",
    }

def search(session, line, q, max_pages=2):
    """Returns (rows, total, status); status is "complete" or "truncated_max_pages"."""
    rows, seen = [], set()
    for page in range(1, max_pages + 1):
        if page > 1:
            time.sleep(CRAWL_DELAY_S)
        drain_events()
        goto_url(search_url(line, q, page))
        res = read_search(session, q, want_from=(page - 1) * 24)
        total, items = int(res["totalResults"]), res.get("results") or []
        new = [row(it) for it in items if int(it["productId"]) not in seen]
        seen.update(r["product_id"] for r in new)
        rows.extend(new)
        print(f"{line} {q!r} page {page}: {len(items)} products, {len(new)} new, total={total}")
        if page * 24 >= total or not items:
            return rows, total, "complete"
    return rows, total, "truncated_max_pages"

tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
session = switch_tab(tab)
try:
    rows, total, status = search(session, "magic", "lightning bolt", max_pages=2)
    print(len(rows), "products of", total, "status:", status)
    for r in rows[:3]:
        print(json.dumps(r, ensure_ascii=False))
    time.sleep(CRAWL_DELAY_S)
    rows, total, status = search(session, "pokemon", "charizard ex", max_pages=1)
    print(len(rows), "products of", total, "status:", status)
    print(json.dumps(rows[0], ensure_ascii=False))
    time.sleep(CRAWL_DELAY_S)
    rows, total, status = search(session, "magic", "zzqx notacard")
    print(len(rows), "products of", total, "status:", status)
finally:
    close_tab(tab)

try:   # robots.txt disallows /search/*/product?seller=*; a bad line slug is refused the same way
    search_url("magic/product?seller=1", "bolt")
except ValueError as e:
    print("refused:", e)
```

Real output (2026-10-31):

```
magic 'lightning bolt' page 1: 24 products, 24 new, total=104
magic 'lightning bolt' page 2: 24 products, 22 new, total=104
46 products of 104 status: truncated_max_pages
{"product_id": 1479, "name": "Lightning Bolt", "set": "Revised Edition", "set_code": "3ED", "rarity": "Common", "number": null, "market_price": 2.84, "lowest_price": 0.7, "lowest_price_with_shipping": 0.7, "listings": 606, "sealed": false, "url": "https://www.tcgplayer.com/product/1479"}
{"product_id": 719091, "name": "Lightning Bolt", "set": "Commander: Foundations", "set_code": "FDC", "rarity": "Uncommon", "number": "163", "market_price": 0.85, "lowest_price": 0.39, "lowest_price_with_shipping": 0.74, "listings": 51, "sealed": false, "url": "https://www.tcgplayer.com/product/719091"}
{"product_id": 697344, "name": "Lightning Bolt", "set": "Commander: Marvel Super Heroes", "set_code": "MSC", "rarity": "Uncommon", "number": "806", "market_price": 0.89, "lowest_price": 0.79, "lowest_price_with_shipping": 0.79, "listings": 201, "sealed": false, "url": "https://www.tcgplayer.com/product/697344"}
pokemon 'charizard ex' page 1: 24 products, 24 new, total=157
24 products of 157 status: truncated_max_pages
{"product_id": 124025, "name": "M Charizard EX", "set": "XY - Evolutions", "set_code": "EVO", "rarity": "Ultra Rare", "number": "13/108", "market_price": 38.27, "lowest_price": 6.54, "lowest_price_with_shipping": 6.54, "listings": 239, "sealed": false, "url": "https://www.tcgplayer.com/product/124025"}
magic 'zzqx notacard' page 1: 0 products, 0 new, total=0
0 products of 0 status: complete
refused: line must be a productLineUrlName like 'magic' and q must be non-empty
```

`truncated_max_pages` is expected: `max_pages` stopped the run while more results existed. Page 2 repeated 1 to 3 products from page 1 across four runs (default "Best Match" order shifts between loads), so the code de-duplicates by `product_id`.

### 2. Product page: market price, cheapest listings, latest sales (browser)

```python
import base64, json, re, time

PRODUCT_IDS = [1479, 719091, 1032]   # product_id values from block 1
CRAWL_DELAY_S = 10             # robots.txt: Crawl-Delay: 10

def challenge_check():
    t = (js("document.title") or "").lower()
    body = (js("document.body ? document.body.innerText.slice(0, 400) : ''") or "").lower()
    if any(s in t + body for s in ("just a moment", "access denied", "attention required", "verify you are human")):
        raise SystemExit(f"challenge page on {js('location.href')}: stop and back off, do not retry")

def read_product(session, pid, timeout=30):
    """Collect the JSON the product page itself loads: details, its cheapest-listings call, latest sales."""
    pats = {
        "details": re.compile(rf"mp-search-api\.tcgplayer\.com/v2/product/{pid}/details\b"),
        "listings": re.compile(rf"mp-search-api\.tcgplayer\.com/v1/product/{pid}/listings\b"),
        "sales": re.compile(rf"mpapi\.tcgplayer\.com/v2/product/{pid}/latestsales\b"),
    }
    reqs, got, start = {}, {}, time.time()
    while time.time() < start + timeout:
        for e in drain_events():
            if e.get("session_id") != session:
                continue
            m, p = e.get("method"), e.get("params") or {}
            if m == "Network.requestWillBeSent":
                r = p["request"]
                kind = next((k for k, rx in pats.items() if rx.search(r["url"])), None)
                if kind and r["method"] in ("GET", "POST"):
                    reqs[p["requestId"]] = {"kind": kind, "post": json.loads(r.get("postData") or "{}")}
            elif p.get("requestId") not in reqs:
                continue
            elif m == "Network.responseReceived":
                reqs[p["requestId"]]["status"] = p["response"]["status"]
            elif m == "Network.loadingFailed":
                raise RuntimeError(f"{reqs[p['requestId']]['kind']} request failed: {p.get('errorText')}")
            elif m == "Network.loadingFinished":
                r = reqs[p["requestId"]]
                if r.get("status") != 200:
                    raise SystemExit(f"{r['kind']} answered HTTP {r.get('status')}: stop and back off, do not retry")
                # the page sends listings twice (size 0 for filter counts, then size 10) and
                # latestsales twice (limit 1, then limit 25); keep the larger one
                size = r["post"].get("size", r["post"].get("limit", 0))
                if r["kind"] in got and got[r["kind"]][0] >= size:
                    continue
                b = cdp("Network.getResponseBody", session_id=session, requestId=p["requestId"])
                got[r["kind"]] = (size, json.loads(base64.b64decode(b["body"]) if b.get("base64Encoded") else b["body"]))
        if "details" in got and got.get("listings", (0,))[0] > 0 and got.get("sales", (0,))[0] > 1:
            break
        time.sleep(0.2)
    if "details" not in got:
        challenge_check()
        raise RuntimeError(f"no details response for product {pid} within {timeout} s: {page_info()}")
    return {k: v[1] for k, v in got.items()}

def parse(pid, raw):
    d = raw["details"]
    if int(d.get("productId") or 0) != pid:
        raise RuntimeError(f"asked for product {pid}, page loaded {d.get('productId')}")
    lres = ((raw.get("listings") or {}).get("results") or [{}])[0]
    sales = raw.get("sales") or {}
    return {
        "product_id": pid,
        "name": d.get("productName"),
        "set": d.get("setName"),
        "line": d.get("productLineName"),
        "rarity": d.get("rarityName"),
        "market_price": d.get("marketPrice"),
        "median_price": d.get("medianPrice"),
        "lowest_price": d.get("lowestPrice"),
        "lowest_price_with_shipping": d.get("lowestPriceWithShipping"),
        "listings_total": lres.get("totalResults"),
        "skus": [(s["sku"], s["condition"], s["variant"], s["language"]) for s in d.get("skus") or []],
        "cheapest_listings": [{
            "condition": l.get("condition"), "printing": l.get("printing"), "language": l.get("language"),
            "price": l.get("price"), "shipping": l.get("shippingPrice"), "quantity": int(l.get("quantity") or 0),
            "seller_rating": l.get("sellerRating"), "seller_sales": l.get("sellerSales"),
            "direct": l.get("directListing"), "listing_type": l.get("listingType"),
        } for l in lres.get("results") or []],
        "latest_sales": [{
            "date": s.get("orderDate"), "condition": s.get("condition"), "variant": s.get("variant"),
            "price": s.get("purchasePrice"), "shipping": s.get("shippingPrice"), "quantity": s.get("quantity"),
        } for s in sales.get("data") or []],
        "sales_meta": {k: sales.get(k) for k in ("totalResults", "nextPage")},
        "url": f"https://www.tcgplayer.com/product/{pid}",
    }

tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
session = switch_tab(tab)
out = []
try:
    for i, pid in enumerate(PRODUCT_IDS):
        if i:
            time.sleep(CRAWL_DELAY_S)
        drain_events()
        goto_url(f"https://www.tcgplayer.com/product/{int(pid)}")
        out.append(parse(int(pid), read_product(session, int(pid))))
finally:
    close_tab(tab)

for p in out:
    print(json.dumps({k: v for k, v in p.items() if k not in ("cheapest_listings", "latest_sales", "skus", "sales_meta")}, ensure_ascii=False))
    print(f"  skus={len(p['skus'])} cheapest_listings={len(p['cheapest_listings'])} "
          f"latest_sales={len(p['latest_sales'])} sales_meta={p['sales_meta']}")
    print("  cheapest:", json.dumps(p["cheapest_listings"][:2]))
    print("  latest sale:", json.dumps(p["latest_sales"][:1]))
```

Real output (2026-10-31):

```
{"product_id": 1479, "name": "Lightning Bolt", "set": "Revised Edition", "line": "Magic: The Gathering", "rarity": "Common", "market_price": 2.84, "median_price": 2.84, "lowest_price": 0.7, "lowest_price_with_shipping": 0.7, "listings_total": 606, "url": "https://www.tcgplayer.com/product/1479"}
  skus=5 cheapest_listings=10 latest_sales=5 sales_meta={'totalResults': 5, 'nextPage': ''}
  cheapest: [{"condition": "Heavily Played", "printing": "Normal", "language": "English", "price": 0.75, "shipping": 1.49, "quantity": 2, "seller_rating": 100.0, "seller_sales": "1401", "direct": false, "listing_type": "standard"}, {"condition": "Heavily Played", "printing": "Normal", "language": "English", "price": 0.83, "shipping": 1.49, "quantity": 2, "seller_rating": 100.0, "seller_sales": "50000+", "direct": false, "listing_type": "standard"}]
  latest sale: [{"date": "2026-10-31T13:06:45.887+00:00", "condition": "Lightly Played", "variant": "Normal", "price": 2.38, "shipping": 0.0, "quantity": 1}]
{"product_id": 719091, "name": "Lightning Bolt", "set": "Commander: Foundations", "line": "Magic: The Gathering", "rarity": "Uncommon", "market_price": 0.85, "median_price": 0.96, "lowest_price": 0.39, "lowest_price_with_shipping": 0.74, "listings_total": 51, "url": "https://www.tcgplayer.com/product/719091"}
  skus=30 cheapest_listings=10 latest_sales=5 sales_meta={'totalResults': 5, 'nextPage': ''}
  cheapest: [{"condition": "Near Mint", "printing": "Normal", "language": "English", "price": 0.76, "shipping": 3.99, "quantity": 4, "seller_rating": 100.0, "seller_sales": "25000+", "direct": true, "listing_type": "standard"}, {"condition": "Near Mint", "printing": "Normal", "language": "English", "price": 0.82, "shipping": 3.99, "quantity": 2, "seller_rating": 100.0, "seller_sales": "10000+", "direct": true, "listing_type": "standard"}]
  latest sale: [{"date": "2026-10-31T18:17:55.253+00:00", "condition": "Near Mint", "variant": "Normal", "price": 0.74, "shipping": 1.49, "quantity": 1}]
{"product_id": 1032, "name": "Aspect of Wolf", "set": "Alpha Edition", "line": "Magic: The Gathering", "rarity": "Rare", "market_price": null, "median_price": null, "lowest_price": 375.0, "lowest_price_with_shipping": null, "listings_total": 5, "url": "https://www.tcgplayer.com/product/1032"}
  skus=5 cheapest_listings=5 latest_sales=2 sales_meta={'totalResults': 2, 'nextPage': ''}
  cheapest: [{"condition": "Heavily Played", "printing": "Normal", "language": "English", "price": 375.0, "shipping": 1.99, "quantity": 1, "seller_rating": 100.0, "seller_sales": "50000+", "direct": false, "listing_type": "custom"}, {"condition": "Lightly Played", "printing": "Normal", "language": "English", "price": 649.95, "shipping": 0.0, "quantity": 1, "seller_rating": 99.3, "seller_sales": "5930", "direct": false, "listing_type": "custom"}]
  latest sale: [{"date": "2026-10-02T22:17:27.73+00:00", "condition": "Lightly Played", "variant": "Normal", "price": 500.0, "shipping": 0.0, "quantity": 1}]
```

## URL patterns (all observed)

| URL | Result |
|---|---|
| `/search/<line>/product?productLineName=<line>&q=<q>&view=grid&page=N` | search, 24 products per page; the page sends `"from": (N-1)*24, "size": 24` |
| `/search/<line>/product?productLineName=<line>&page=1` | the site's own "Shop All" link for a line (no `q`) |
| `/search/magic/product?q=...` without `productLineName` | the app rewrites the URL to add `productLineName=magic&setName=product` and puts `"setName": ["product"]` in the search request; results were the same 104 for "lightning bolt", but use the explicit form above |
| `/product/<id>` | product page; the tab ends on `/product/<id>?Language=English` or similar |
| `/search/*/product?seller=...`, `/sellers/*/product/*` | disallowed by robots.txt, never requested; `search_url` refuses `seller=` |

## Fields

### Search rows (`results[0].results[i]` of the search response)

| Output field | Source | Notes |
|---|---|---|
| `product_id` | `productId` (float) | cast to int; also the `/product/<id>` path |
| `name`, `set`, `set_code`, `rarity` | `productName`, `setName`, `setCode`, `rarityName` | |
| `number` | `customAttributes.number` | collector number, `null` on old sets, `"13/108"` style on Pokemon |
| `market_price` | `marketPrice` | TCGplayer Market Price, USD; can be `null` when there are too few sales |
| `lowest_price` | `lowestPrice` | cheapest listing price before shipping, any condition |
| `lowest_price_with_shipping` | `lowestPriceWithShipping` | |
| `listings` | `totalListings` | live listing count |
| (page) `total` | `results[0].totalResults` | total products for the query |

Each search row also carries up to 3 sample `listings` and `medianPrice`, `customAttributes` (card text, colors, type, release date).

### Product (block 2)

| Output field | Source | Notes |
|---|---|---|
| `market_price`, `median_price`, `lowest_price`, `lowest_price_with_shipping` | details | Alpha Aspect of Wolf (5 listings, 2 recent sales) had `market_price`, `median_price` and `lowest_price_with_shipping` all `null` while `lowest_price` was 375.0 |
| `skus` | details `skus[]` | `(sku, condition, variant, language)`; 5 for a single-printing card, 30 for one with foil and several languages |
| `listings_total` | listings `totalResults` | the page filters listings to `language: ["English"]` |
| `cheapest_listings` | listings `results[]` | the page's own first 10, sorted by `price+shipping` ascending, so the first row is not always `lowest_price` |
| `latest_sales` | latestsales `data[]` | `orderDate`, `condition`, `variant`, `purchasePrice`, `shippingPrice`, `quantity` |
| `sales_meta` | latestsales `totalResults`, `nextPage` | logged out this was 5 for Revised Lightning Bolt (606 listings), so treat it as "most recent few", not a full history |

Listing and sale rows also contain `sellerName`, `sellerId`, `sellerKey`, seller city/state and seller-written custom listing titles. The code leaves those out; add them only if you have a reason and a basis to process them.

## Gotchas

- Wait 10 s between page loads (`Crawl-Delay: 10`). Both blocks do.
- The page sends `listings` twice (`size: 0` for filter counts, then `size: 10`) and `latestsales` twice (`limit: 1`, then `limit: 25`). Block 2 keeps the larger one. The search request was also sent twice on some loads with the same body; block 1 takes the first one whose `q` and `from` match.
- `Network.getResponseBody` only works while the request is in the browser's buffer, so read it on `loadingFinished` and `drain_events()` right before each `goto_url`.
- Default sort is "Best Match" (`"algorithm": "sales_dismax"`), and its order changed between two runs a few minutes apart (Revised Edition first in one run, M11 first in the next). De-duplicate across pages.
- A query with no matches returns HTTP 200 with `totalResults: 0` (not an error page).
- Prices are USD; the page sends `"shippingCountry": "US"` from the cloud browser's location.
- `infinite-api.tcgplayer.com/card/magic/<id>` (loaded by the product page for the card-text widget) returned a different product for id 1032 (Fifth Edition, `tcgPlayerID` 2032). Do not use it as the product record.
- Both blocks open their own background tab with `Target.createTarget` and close it in `finally`. They worked in a background tab in the cloud browser.
- If a page shows a challenge or an API answers non-200, the code exits; stop and back off. Do not retry with a different user agent, session or IP.

## What does not work

- Plain HTTP: `GET /product/1479/magic-revised-edition-lightning-bolt` returned 200 with a 45 KB app shell, an empty `<title>`, a generic meta description and no prices or JSON-LD.
- Calling `mp-search-api` / `mpapi` directly was not attempted. They are the site's internal endpoints, not a public API; this skill only reads what the public pages load.
- Seller storefront searches (`?seller=`, `/sellers/*/product/*`) and deck/article search are disallowed by robots.txt.
- Full sales history: logged out, `latestsales` returned at most 5 sales in these runs.
