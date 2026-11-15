# Mercari (US) - Search listings; read item price, condition and seller

Field-tested against www.mercari.com on 2026-11-02 using a Browser Use cloud browser, logged out. Plain `curl` got `403` with a Cloudflare "Just a moment..." page for both `/search/` and `/us/item/<id>/`, so everything below runs in the browser.

robots.txt (fetched 2026-11-02) for `User-agent: *` disallows `/r/`, `/sell/`, `/mypage/`, `/transaction/`, `/favorites/`, `/*?ref=`, `/*?tracking_ref_id=`, `/*?login_callback=` (and the `&` forms) plus account and legal pages, and has no rule for `/search/`, `/us/item/` or `/u/`; this skill only loads `/search/?keyword=...` and clean `/us/item/<id>/` URLs and reads the data those pages load themselves.

## Quick summary

- **Search is client-rendered.** `/search/?keyword=<q>` ships no results in the HTML (`__NEXT_DATA__` is 227 bytes). The page itself sends `GET /v1/api?operationName=searchFacetQuery&variables=...` and gets 100 rows per batch with price, condition, status, brand and seller id. Block 1 reads that response with CDP `Network.getResponseBody`; it never calls the API itself.
- **More rows = scroll.** The grid is infinite-scroll (no pager, no page param in the URL). Scrolling to the bottom makes the page send the next `searchFacetQuery`; the last batch has `nextKey: "0"`.
- **Item pages are server-rendered.** `/us/item/<id>/` embeds an Apollo cache in `__NEXT_DATA__.props.pageProps.serverState`: `ItemDetail:<id>` (price, condition, status, ...) and `PublicUser:<seller id>` (username, rating, sales). Block 2 reads it and cross-checks price, condition, seller and sold state against the visible page.
- **Prices are cents** in both sources (`15000` = $150.00), and so are the URL price filters (`minPrice=10000`).
- **Never follow tile links.** Result tiles link to `/us/item/<id>/?ref=search_results`, and the seller link carries `?tracking_ref_id=`; robots.txt disallows both. Both blocks build `https://www.mercari.com/us/item/<id>/` instead.
- About 50 page loads in one cloud browser, 3 s or more apart: no challenge, no login wall, no 429. A cookie banner shows but does not block anything.

## What works

### 1. Search, several batches, with filters (browser, reads the page's own search response)

```python
import base64, collections, json, re, time, urllib.parse

BASE = "https://www.mercari.com"
PAUSE_S = 3                          # between page loads and between scroll batches
CONDITIONS = {1: "New", 2: "Like new", 3: "Good", 4: "Fair", 5: "Poor"}
SORT = {"best_match": 1, "newest": 2, "lowest_price": 3, "highest_price": 4, "recently_sold": 6}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(
    r"(?<![\w+])(?:\+[\s.-]?|00)[1-9](?:[\s.()-]{0,2}\d){6,14}(?!\d)"   # international: +44 20 7946 0958
    r"|(?<!\d)(?:1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")  # North American: (555) 123-4567

def redact(text):
    """Titles are seller-written free text: mask any email address or phone number in them."""
    return PHONE.sub("[phone]", EMAIL.sub("[email]", text or ""))

def search_url(keyword, conditions=(), status=None, min_usd=None, max_usd=None, sort=None):
    """The URL the site's own filter and sort controls write (all params observed in the UI)."""
    if not keyword.strip():
        raise ValueError("keyword must be non-empty")
    q = {"keyword": keyword}
    if conditions:
        if not set(conditions) <= set(CONDITIONS):
            raise ValueError(f"condition ids are {CONDITIONS}")
        q["itemConditions"] = "-".join(str(c) for c in sorted(conditions))
    if status:
        q["itemStatuses"] = {"for_sale": "1", "sold": "2-3"}[status]
    if min_usd is not None:
        q["minPrice"] = str(round(min_usd * 100))   # the UI writes cents
    if max_usd is not None:
        q["maxPrice"] = str(round(max_usd * 100))
    if sort:
        q["sortBy"] = str(SORT[sort])
    return f"{BASE}/search/?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)

def challenge_check():
    t = ((js("document.title") or "") + " " + (js("document.body ? document.body.innerText.slice(0, 400) : ''") or "")).lower()
    if any(s in t for s in ("just a moment", "verify you are human", "attention required", "access denied")):
        raise SystemExit(f"challenge page on {js('location.href')}: stop, do not retry or change the request")

def read_search(session, page_url, after, timeout=30):
    """Return (offset, data.search) for the next searchFacetQuery request this page itself sends.
    after=None waits for the first batch (offset 0); otherwise it scrolls and waits for an offset > after."""
    reqs, start, last_scroll = {}, time.time(), 0
    while time.time() < start + timeout:
        if after is not None and time.time() - last_scroll > 5:   # the result grid loads the next batch when you reach the bottom
            js("window.scrollTo(0, document.documentElement.scrollHeight)")
            last_scroll = time.time()
        for e in drain_events():
            if e.get("session_id") != session:
                continue
            m, p = e.get("method"), e.get("params") or {}
            if m == "Network.requestWillBeSent":
                u = urllib.parse.urlparse(p["request"]["url"])
                qs = urllib.parse.parse_qs(u.query)
                same_page = urllib.parse.unquote(p.get("documentURL") or "") == urllib.parse.unquote(page_url)
                if same_page and u.path == "/v1/api" and qs.get("operationName") == ["searchFacetQuery"]:
                    off = json.loads(qs["variables"][0])["criteria"].get("offset")
                    if (off == 0) if after is None else (off > after):
                        reqs[p["requestId"]] = {"offset": off}
            elif p.get("requestId") not in reqs:
                continue
            elif m == "Network.responseReceived":
                reqs[p["requestId"]]["status"] = p["response"]["status"]
            elif m == "Network.loadingFinished":
                if reqs[p["requestId"]].get("status") != 200:
                    raise SystemExit(f"search answered HTTP {reqs[p['requestId']].get('status')}: stop, do not retry")
                b = cdp("Network.getResponseBody", session_id=session, requestId=p["requestId"])
                data = json.loads(base64.b64decode(b["body"]) if b.get("base64Encoded") else b["body"])
                if data.get("errors"):
                    raise RuntimeError(f"search errors: {data['errors']}")
                return reqs[p["requestId"]]["offset"], data["data"]["search"]
        time.sleep(0.2)
    challenge_check()
    raise RuntimeError(f"no searchFacetQuery response after offset {after} within {timeout} s: {page_info()}")

def row(it):
    price = it.get("price")
    if not re.fullmatch(r"m\d+", it.get("id") or "") or not it.get("name") or not isinstance(price, int) or price <= 0:
        raise RuntimeError(f"unexpected row {json.dumps(it)[:200]}; refusing the batch")
    return {
        "id": it["id"],
        "title": redact(it["name"]),
        "price": price / 100,                                    # cents in the response
        "original_price": it["originalPrice"] / 100 if (it.get("originalPrice") or 0) > price else None,   # price drop
        "condition": (it.get("itemCondition") or {}).get("name"),
        "status": it.get("status"),                              # on_sale, trading (sold, not yet complete), sold_out
        "brand": (it.get("brand") or {}).get("name"),
        "category": it.get("categoryTitle"),
        "seller_id": (it.get("seller") or {}).get("id"),
        "url": f"{BASE}/us/item/{it['id']}/",                    # no ?ref=: robots.txt disallows /*?ref=
    }

def search(session, keyword, max_batches=2, **filters):
    """Returns (rows, count, status). status: "complete" or "truncated_max_batches"."""
    url = search_url(keyword, **filters)
    drain_events()
    goto_url(url)
    rows, seen, offset, count = [], set(), None, 0
    for batch in range(1, max_batches + 1):
        if batch > 1:
            time.sleep(PAUSE_S)
        offset, res = read_search(session, url, offset)
        if urllib.parse.unquote(js("location.href")) != urllib.parse.unquote(url):
            raise RuntimeError(f"page moved to {js('location.href')}, expected {url}")
        items, count = res.get("itemsList") or [], int(res.get("count") or 0)
        new = [row(it) for it in items if it["id"] not in seen]
        seen.update(r["id"] for r in new)
        rows.extend(new)
        print(f"{keyword!r} batch {batch}: offset {offset}, {len(items)} rows, {len(new)} new, count={count}")
        if not items or res.get("nextKey") in (None, "", "0"):   # "0" = no more batches
            return rows, count, "complete"
    return rows, count, "truncated_max_batches"

tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
session = switch_tab(tab, activate=True)   # the grid only loads more rows in a visible tab
try:
    rows, count, status = search(session, "nintendo switch oled", max_batches=2)
    print(len(rows), "rows of", count, "status:", status)
    for r in rows[:2]:
        print(json.dumps(r, ensure_ascii=False))
    print("statuses:", dict(collections.Counter(r["status"] for r in rows)))

    time.sleep(PAUSE_S)
    rows, count, status = search(session, "nintendo switch oled", conditions=(1, 2),
                                 status="for_sale", min_usd=100, max_usd=199, sort="lowest_price", max_batches=5)
    print(len(rows), "rows of", count, "status:", status, "| conditions:", sorted({r["condition"] for r in rows}),
          "| statuses:", sorted({r["status"] for r in rows}),
          "| price range:", min(r["price"] for r in rows), "-", max(r["price"] for r in rows),
          "| sorted:", [r["price"] for r in rows] == sorted(r["price"] for r in rows))

    time.sleep(PAUSE_S)
    rows, count, status = search(session, "nintendo switch oled", status="sold", max_batches=1)
    print(len(rows), "sold rows of", count, "| statuses:", dict(collections.Counter(r["status"] for r in rows)))

    time.sleep(PAUSE_S)
    rows, count, status = search(session, "zzqxqv notathing")
    print(len(rows), "rows for a nonsense query, status:", status)
finally:
    close_tab(tab)
```

Real output (2026-11-02):

```
'nintendo switch oled' batch 1: offset 0, 100 rows, 100 new, count=8889
'nintendo switch oled' batch 2: offset 47, 100 rows, 99 new, count=8889
199 rows of 8889 status: truncated_max_batches
{"id": "m34776430562", "title": "Nintendo Switch OLED Console - White - As is. For Parts or Repair", "price": 150.0, "original_price": 170.0, "condition": "Poor", "status": "on_sale", "brand": "Nintendo", "category": "Consoles", "seller_id": 996986135, "url": "https://www.mercari.com/us/item/m34776430562/"}
{"id": "m18850154865", "title": "Nintendo Switch OLED Modded – 1TB Storage + Accessories", "price": 480.0, "original_price": null, "condition": "Good", "status": "on_sale", "brand": "Nintendo", "category": "Consoles", "seller_id": 506215568, "url": "https://www.mercari.com/us/item/m18850154865/"}
statuses: {'on_sale': 187, 'trading': 12}
'nintendo switch oled' batch 1: offset 0, 99 rows, 99 new, count=149
'nintendo switch oled' batch 2: offset 100, 46 rows, 46 new, count=149
145 rows of 149 status: complete | conditions: ['Like new', 'New'] | statuses: ['on_sale'] | price range: 100.0 - 199.0 | sorted: True
'nintendo switch oled' batch 1: offset 0, 100 rows, 100 new, count=4471
100 sold rows of 4471 | statuses: {'trading': 75, 'sold_out': 25}
'zzqxqv notathing' batch 1: offset 0, 0 rows, 0 new, count=0
0 rows for a nonsense query, status: complete
```

`truncated_max_batches` is expected for the first search: `max_batches=2` stopped while about 8,700 more rows existed. The filtered search ran to the end (`nextKey: "0"`) with 145 rows although `count` said 149, so treat `count` as approximate.

### 2. Item page: price, condition, seller (browser, reads the page's own server state)

```python
import json, re, time, urllib.parse

BASE = "https://www.mercari.com"
PAUSE_S = 3

def redact(text):
    """Seller-written free text: mask email addresses and phone numbers."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text or "")
    return re.sub(r"(?<![\w+])(?:\+[\s.-]?|00)[1-9](?:[\s.()-]{0,2}\d){6,14}(?!\d)"
                  r"|(?<!\d)(?:1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)", "[phone]", text)

def item_url(item_id):
    """Only the clean item URL: tile links carry ?ref=search_results, which robots.txt disallows (/*?ref=)."""
    if not re.fullmatch(r"m\d{6,15}", item_id or ""):
        raise ValueError(f"refusing item id {item_id!r}: expected m + digits")
    return f"{BASE}/us/item/{item_id}/"

def challenge_check():
    t = ((js("document.title") or "") + " " + (js("document.body ? document.body.innerText.slice(0, 400) : ''") or "")).lower()
    if any(s in t for s in ("just a moment", "verify you are human", "attention required", "access denied")):
        raise SystemExit(f"challenge page on {js('location.href')}: stop, do not retry or change the request")

def item_ids_from_search(keyword, status, n):
    """Item ids from the result tiles of a search page (hrefs only; the tiles themselves are not clicked)."""
    q = urllib.parse.urlencode({"keyword": keyword, "itemStatuses": {"for_sale": "1", "sold": "2-3"}[status]},
                               quote_via=urllib.parse.quote)
    goto_url(f"{BASE}/search/?{q}")
    wait_for_load()
    for _ in range(40):
        hrefs = js("[...document.querySelectorAll('[data-testid=SearchResults] a[href^=\"/us/item/\"]')].map(a => a.getAttribute('href'))") or []
        ids = list(dict.fromkeys(m.group(1) for h in hrefs if (m := re.match(r"/us/item/(m\d+)/", h))))
        if ids:
            return ids[:n]
        time.sleep(0.5)
    challenge_check()
    raise RuntimeError(f"no result tiles on {js('location.href')}")

STATE = r"""(() => {
  const nd = document.getElementById('__NEXT_DATA__');
  if (!nd) return {pending: 'no __NEXT_DATA__'};
  const pp = JSON.parse(nd.textContent).props.pageProps || {};
  const q = s => { const e = document.querySelector('[data-testid="' + s + '"]'); return e ? e.innerText.trim() : null; };
  return {status_code: pp.statusCode, state: pp.serverState || null, query_id: (pp.query || {}).id,
          dom: {price: q('ItemPrice'), condition: q('ItemDetailsCondition'), username: q('ItemDetailsSellerUserName'),
                buyer_shipping: (q('ItemDetailsShipping') || '').split('\n')[0],   // "$0.00 $13.09" (now, before) or "Free"
                sold_banner: !!document.querySelector('[data-testid="SoldListing"]')}};
})()"""

def read_item(item_id, settle_s=25):
    url = item_url(item_id)
    goto_url(url)
    wait_for_load()
    deadline, data = time.monotonic() + settle_s, None
    while time.monotonic() < deadline:
        if js("location.href") == url:
            data = js(STATE)
            if data and data.get("query_id") == item_id and data.get("state") is not None:
                break
        time.sleep(0.5)
    else:
        challenge_check()
        raise RuntimeError(f"item page did not settle: {page_info()} {data and data.get('pending')}")
    st = data["state"]
    it = st.get(f"ItemDetail:{item_id}")
    if not it:
        return {"id": item_id, "error": f"no item (statusCode {data.get('status_code')})"}
    ref = lambda r: st.get((r or {}).get("__ref"), {})
    seller, dom = ref(it.get("seller")), data["dom"]
    price = it["price"] / 100
    cond = ref(it.get("itemCondition")).get("name")
    checks = {"price": (dom["price"], f"${price:,.2f}"), "condition": (dom["condition"], cond),   # page vs state
              "seller": (dom["username"], f"@{seller.get('username')}"),
              "sold": (dom["sold_banner"], it.get("status") != "on_sale")}
    for k, (shown, state) in checks.items():
        if shown != state:
            raise RuntimeError(f"{item_id}: {k} on page {shown!r} != page state {state!r}; refusing the item")
    fee = re.match(r"\$([\d,]+\.\d\d)", dom["buyer_shipping"])
    ship = 0.0 if dom["buyer_shipping"].startswith("Free") else float(fee.group(1).replace(",", "")) if fee else None
    return {
        "id": item_id,
        "title": redact(it.get("name")),
        "price": price,
        "original_price": it["originalPrice"] / 100 if (it.get("originalPrice") or 0) > it["price"] else None,
        "condition": cond,
        "status": it.get("status"),
        "brand": ref(it.get("brand")).get("name"),
        "category": it.get("categoryTitle"),
        "buyer_shipping": ship,   # what the page shows the buyer, after any promotion
        "shipping_payer": ref(it.get("shippingPayer")).get("name"),
        "ships_from": ref(it.get("shippingFromArea")).get("name"),
        "likes": it.get("numLikes"),
        "seller": {
            "id": seller.get("id"),
            "username": seller.get("username"),   # display name (PublicUser.name) left out: often a full real name
            "rating": (seller.get("ratings") or {}).get("average"),
            "reviews": (seller.get("ratings") or {}).get("count"),
            "sales": seller.get("numSales"),
            "listed": seller.get("numSellItems"),
            "id_verified": seller.get("kycVerificationStatus") == "verified",
            "pro_seller": seller.get("isProSeller"),
            "url": f"{BASE}/u/{seller['username']}/" if seller.get("username") else None,
        },
        "url": url,
    }

tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
switch_tab(tab, activate=True)   # result tiles render reliably only in a visible tab
try:
    ids = item_ids_from_search("nintendo switch oled", "for_sale", 2)
    time.sleep(PAUSE_S)
    ids += item_ids_from_search("nintendo switch oled", "sold", 1)
    print("ids:", ids)
    for i in ids + ["m00000000001"]:
        time.sleep(PAUSE_S)
        print(json.dumps(read_item(i), ensure_ascii=False))
finally:
    close_tab(tab)

try:
    item_url("m123/?ref=search_results")
except ValueError as e:
    print("refused:", e)
```

Real output (2026-11-02):

```
ids: ['m34776430562', 'm18850154865', 'm15731011026']
{"id": "m34776430562", "title": "Nintendo Switch OLED Console - White - As is. For Parts or Repair", "price": 150.0, "original_price": 170.0, "condition": "Poor", "status": "on_sale", "brand": "Nintendo", "category": "Consoles", "buyer_shipping": 0.0, "shipping_payer": "Buyer", "ships_from": "South Dakota", "likes": 13, "seller": {"id": 996986135, "username": "user996986135", "rating": 5, "reviews": 11, "sales": 7, "listed": 14, "id_verified": true, "pro_seller": false, "url": "https://www.mercari.com/u/user996986135/"}, "url": "https://www.mercari.com/us/item/m34776430562/"}
{"id": "m18850154865", "title": "Nintendo Switch OLED Modded – 1TB Storage + Accessories", "price": 480.0, "original_price": null, "condition": "Good", "status": "on_sale", "brand": "Nintendo", "category": "Consoles", "buyer_shipping": 0.0, "shipping_payer": "Seller", "ships_from": "New York", "likes": 36, "seller": {"id": 506215568, "username": "user506215568", "rating": 5, "reviews": 11, "sales": 8, "listed": 9, "id_verified": true, "pro_seller": false, "url": "https://www.mercari.com/u/user506215568/"}, "url": "https://www.mercari.com/us/item/m18850154865/"}
{"id": "m15731011026", "title": "Nintendo Switch OLED Model with Splatoon 2 Game", "price": 185.25, "original_price": 195.0, "condition": "Good", "status": "trading", "brand": "Nintendo", "category": "Consoles", "buyer_shipping": 0.0, "shipping_payer": "Buyer", "ships_from": "Maryland", "likes": 15, "seller": {"id": 211421893, "username": "cheesecakedog", "rating": 5, "reviews": 16, "sales": 16, "listed": 28, "id_verified": true, "pro_seller": false, "url": "https://www.mercari.com/u/cheesecakedog/"}, "url": "https://www.mercari.com/us/item/m15731011026/"}
{"id": "m00000000001", "error": "no item (statusCode 404)"}
refused: refusing item id 'm123/?ref=search_results': expected m + digits
```

## URL patterns and filters (all observed in the UI)

| Pattern | Result |
|---|---|
| `/search/?keyword=<q>` | Best match, 100 rows per `searchFacetQuery` batch |
| `&itemConditions=1-2` | Condition checkboxes, ids joined by `-`: `1` New, `2` Like new, `3` Good, `4` Fair, `5` Poor |
| `&itemStatuses=1` | Status "For sale" (only `on_sale` rows came back) |
| `&itemStatuses=2-3` | Status "Sold"; a hand-typed `itemStatuses=2` was rewritten by the page to `2-3` |
| `&minPrice=10000&maxPrice=19900` | Price filter in cents; the "$100 to $200" radio writes exactly these values |
| `&sortBy=` | Sort dropdown: `1` Best match, `2` Newest first, `3` Lowest price first, `4` Highest price first, `6` Recently sold |
| `/search/?keyword=<nonsense>` | 0 rows, `count: 0`, `nextKey: "0"` (not an error page) |
| `/us/item/<id>/` | item page, `<id>` is `m` + 11 digits; an unknown id returns the 404 page with `statusCode: 404` and no `ItemDetail` |
| `/us/item/<id>/?ref=search_results` | what tiles link to; disallowed by robots.txt (`/*?ref=`), not requested |

## Fields

### Search rows (`data.search.itemsList[i]` of `searchFacetQuery`)

| Output field | Source | Notes |
|---|---|---|
| `id` | `id` | `m` + digits, also in the item URL |
| `title` | `name` | seller-written; email addresses and phone numbers are replaced with `[email]` / `[phone]` |
| `price` | `price` / 100 | integer cents in the response |
| `original_price` | `originalPrice` / 100 | only when higher than `price` (a price drop); otherwise `originalPrice` equals `price` or is 0, mapped to `None` |
| `condition` | `itemCondition.name` | `New`, `Like new`, `Good`, `Fair`, `Poor` |
| `status` | `status` | `on_sale`; `trading` = sold, transaction not finished; `sold_out` = sold. Item pages for both had the `SoldListing` marker and no Buy button |
| `brand` | `brand.name` | `None` when the seller set none |
| `category` | `categoryTitle` | leaf category, e.g. `Consoles` |
| `seller_id` | `seller.id` | numeric; the search row has no seller name or rating, use block 2 for those |
| `url` | built from `id` | `https://www.mercari.com/us/item/<id>/`, no `?ref=` |
| (batch) `count` | `count` | approximate total |
| (batch) last batch | `nextKey` | `"0"` on the last batch |

### Item (block 2, `serverState`)

| Output field | Source | Notes |
|---|---|---|
| `price`, `original_price` | `ItemDetail.price`, `.originalPrice` (cents) | checked against the page's `[data-testid=ItemPrice]` |
| `condition` | `ItemDetailItemCondition:<n>.name` | checked against `[data-testid=ItemDetailsCondition]` |
| `status` | `ItemDetail.status` | `on_sale` or not; checked against the `[data-testid=SoldListing]` marker |
| `buyer_shipping` | visible `[data-testid=ItemDetailsShipping]` first line | `"$0.00 $13.09"` (current, before promotion) or `"Free"` (seller pays) |
| `shipping_payer`, `ships_from` | `MasterShippingPayer:<n>.name`, `ShippingFromArea:<n>.name` | `Buyer`/`Seller`; a US state |
| `seller.id`, `seller.username` | `PublicUser:<id>.id`, `.username` | username checked against `[data-testid=ItemDetailsSellerUserName]` |
| `seller.rating`, `seller.reviews` | `.ratings.average`, `.ratings.count` | |
| `seller.sales`, `seller.listed` | `.numSales`, `.numSellItems` | |
| `seller.id_verified`, `seller.pro_seller` | `.kycVerificationStatus == "verified"`, `.isProSeller` | |
| `seller.url` | built from username | `https://www.mercari.com/u/<username>/` (no robots rule; not loaded here). The page's own seller link adds a disallowed `?tracking_ref_id=` |

`PublicUser.name` (the seller's display name, often a full real name) and the item `description` are on the page too; the code leaves them out. Keep them out unless you have a reason and a basis to process personal data.

## Gotchas

- Use a visible tab. In a background tab (`Target.createTarget(background=True)` without activation) scrolling did not make the grid send the next batch (30 s timeout); the same code worked after `switch_tab(tab, activate=True)`, which both blocks call.
- Scrolling fires the same `searchFacetQuery` 2 or 3 times with the same offset. Block 1 takes the first response with an offset above the previous one and de-duplicates rows by `id` (batch 2 repeated 1 row of batch 1).
- The offsets in the response's `page` object are not the next request's offset (batch 1 said `offset: 47`, the page then asked for 47 and later 94). Do not build follow-up requests from them; let the page scroll.
- Default "Best match" results mix sold rows in: 12 of the first 199 for `nintendo switch oled` had `status: "trading"`. Add `status="for_sale"` if you only want buyable items. `status="sold"` returned both `trading` (75) and `sold_out` (25) rows.
- Rows carry a `promoteType` (0, 1 and 6 seen); its meaning was not verified, so the code does not report it.
- Block 1 matches responses by the page URL (`documentURL`) and refuses a batch if the tab ended up on a different URL, so a rewritten URL (like `itemStatuses=2` becoming `2-3`) fails loudly instead of returning the wrong search.
- On a Cloudflare page ("Just a moment...") both blocks raise `SystemExit`; stop and hand it to a human, do not retry or change anything to get past it. None appeared in the browser during testing.

## What does not work

- Plain HTTP: `curl` on `/search/?keyword=...` and `/us/item/<id>/` got `403` "Just a moment..." (Cloudflare).
- Following result tiles or the seller link: their URLs carry `?ref=` / `?tracking_ref_id=`, which robots.txt disallows.
- Deep result sets were not paged to the end; only a 145-row filtered search was. Whether Mercari caps very long scrolls is untested.
