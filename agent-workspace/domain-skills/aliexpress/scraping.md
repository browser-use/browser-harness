# AliExpress — Product Search & Product Page Scraping

Field-tested against `www.aliexpress.com` on 2026-10-23 using a Browser Use cloud browser (US exit) and plain HTTP (Python `urllib` from a US IP, no API key). All pages were logged out.

robots.txt (checked 2026-10-23 on `www.aliexpress.com`) does not disallow `/w/` (search) or `/item/` (product) for `User-agent: *`, and disallows the whole site for named AI crawlers (GPTBot, ClaudeBot, CCBot, Google-Extended and others); `www.aliexpress.us/robots.txt` answered plain HTTP with a 302 cookie redirect.

## Quick summary

- **Search results** (`/w/wholesale-<slug>.html?SearchText=...&page=N`) are server-rendered with every card's data in an inline `window._dida_config_._init_data_` object: title, product ID, sale and original price, sold count, star rating, sponsored flag, and for some cards the store name. 60 cards per page on broad queries.
- **Welcome-deal cards have no `prices` object.** On "phone case" 15 to 32 of 60 cards per page were new-shopper "FREE with any purchase" cards with `prices: null`; on "mechanical keyboard" 0 of 60. Their amounts are only in the card's tracking map (`trace.utLogMap.salePriceAmount` / `originPriceAmount`, in cents). The code below falls back to that map and flags those rows with `welcome_deal: true` and `price_source: "tracking"`.
- **Plain HTTP works for search pages** (about 830 KB of HTML per page, data embedded) with a truthful client User-Agent. 6 pages at 3 s spacing returned 60 cards each, no captcha.
- **The browser works for search pages too** and reads the same object straight from `window`. Both paths repeat some products across pages, so dedupe by `product_id`.
- **Stop on `zero_result`, not on a short page.** A narrow query returned 39 cards on page 1 (`totalResults` 40), then 60 cards on pages 2 and 3 (`totalResults` 438).
- **Pagination stops at page 60.** `page=60` returned 60 cards; `page=61` and `page=100` returned `searchResultType: "zero_result"` with 0 cards, while page 60 of the same "phone case" query still reported `totalResults` 183,155. That is at most 3,600 cards per query and sort (the 60-page cap was measured on the default sort; other `sortType` values were checked only on their first one or two pages). Treat 3,600 as the limit: this skill does not rerun one query under other sorts or reshaped queries to collect past the cap.
- **Product pages are client-rendered.** The HTML has no product data (`window.runParams` is empty). The page calls `acs.aliexpress.us/h5/mtop.aliexpress.pdp.pc.query`, a JSONP response with variants (SKUs), per-SKU price and stock, the default shipping option, store info, rating and specs. Read that response with CDP `Network.getResponseBody` in the browser.
- **Product pages can be refused almost immediately.** In 3 separate test sessions the product API first answered `FAIL_SYS_USER_VALIDATE` (slider captcha) on product page 1, on page 2, and not within 13 pages. Treat product pages as a small enrichment step, not a bulk source. Search pages kept working in the same browsers.
- **Plain HTTP does not work for product pages**: both `www.aliexpress.com/item/<id>.html` and `www.aliexpress.us/item/<id>.html` failed with an infinite 302 redirect loop.

## What works

### 1. Search + pagination over plain HTTP (fastest)

Plain Python, no browser: run it with `python3` or inside `browser-harness`. It uses `urllib` directly so it can read `Retry-After` on a 429.

```python
import email.utils, gzip, http.client, json, re, time, urllib.error, urllib.parse, urllib.request

# Truthful client User-Agent; it returned the full search page on 2026-10-23.
HEADERS = {
    "User-Agent": "browser-harness-skill/1.0 (+https://github.com/browser-use/browser-harness)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
}
SITE_MAX_PAGES = 60                       # AliExpress serves at most 60 pages per query
MAX_WAIT = 120                            # longest Retry-After / backoff sleep; a longer ask stops the run


class SearchBlocked(RuntimeError):
    """A search page without usable data (captcha or layout change). Stop; do not retry in a loop."""


def search_url(query, page=1, sort=None):
    # Non-Latin queries give an empty slug ("wholesale-.html"); that URL also returned results.
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    params = {"SearchText": query, "page": page, **({"sortType": sort} if sort else {})}
    return f"https://www.aliexpress.com/w/wholesale-{slug}.html?{urllib.parse.urlencode(params)}"   # safe="": "/" -> %2F


def retry_after_seconds(value):
    """Retry-After is either delta-seconds or an HTTP-date. -> seconds or None."""
    value = (value or "").strip()
    if value.isdigit():
        return int(value)
    try:
        return max(0.0, email.utils.parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError, IndexError):
        return None


def fetch(url, attempts=4, timeout=30):
    """GET with capped backoff on 429, 5xx and network errors. Raises if every attempt fails
    or the server asks to wait longer than MAX_WAIT."""
    delay = 5
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:   # subclass of URLError, so it is caught first
            if e.code != 429 and e.code < 500:
                raise                         # 3xx loop / 4xx: retrying will not help
            wait, err = retry_after_seconds(e.headers.get("Retry-After")) or delay, e
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError) as e:
            wait, err = delay, e
        if attempt == attempts:
            raise RuntimeError(f"GET failed after {attempts} attempts: {url}") from err
        if wait > MAX_WAIT:
            raise RuntimeError(f"server asked to wait {wait:.0f}s (> {MAX_WAIT}s); stopping: {url}") from err
        print(f"  retry {attempt}/{attempts - 1} in {wait:.0f}s after {err!r}")
        time.sleep(wait)
        delay *= 2


def parse_init_data(html):
    """Return the `_init_data_` object embedded in a search page, or None."""
    m = re.search(r"_init_data_\s*=\s*\{\s*data\s*:\s*", html)
    if not m:
        return None
    data, _ = json.JSONDecoder().raw_decode(html, m.end())
    return data


def obj(x):
    return x if isinstance(x, dict) else {}

def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None

def cents(v):
    """'109' -> 1.09; None / '' / non-digits -> None. utLogMap amounts are integer cents as strings."""
    return int(v) / 100 if isinstance(v, (int, str)) and str(v).isdigit() else None


def normalize(data):
    """-> (items, page_info). Works on the object from plain HTTP or the browser."""
    data = obj(data)
    data = obj(data.get("data", data))     # {"data": {"root": ...}} -> {"root": ...}
    fields = obj(obj(data.get("root")).get("fields"))
    page_info = obj(fields.get("pageInfo"))
    content = obj(obj(fields.get("mods")).get("itemList")).get("content")
    cards = [c for c in content if isinstance(c, dict)] if isinstance(content, list) else []
    # Display currency: from any priced card, else the page's own tracking map.
    page_currency = obj(obj(page_info.get("trace")).get("utLogMap")).get("currency")
    for c in cards:
        cur = obj(obj(c.get("prices")).get("salePrice")).get("currencyCode")
        if isinstance(cur, str):
            page_currency = cur
            break
    items = []
    for c in cards:
        pid = c.get("productId") if isinstance(c.get("productId"), str) and c.get("productId") else None
        prices = obj(c.get("prices"))
        sale, orig = obj(prices.get("salePrice")), obj(prices.get("originalPrice"))
        trace = obj(c.get("trace"))
        ut = obj(trace.get("utLogMap"))
        if num(sale.get("minPrice")) is not None:
            price, price_text, original = num(sale.get("minPrice")), sale.get("formattedPrice"), num(orig.get("minPrice"))
            currency, source = sale.get("currencyCode"), "card"
        else:                              # welcome-deal card: prices is null, amounts only in tracking
            price, price_text, original = cents(ut.get("salePriceAmount")), None, cents(ut.get("originPriceAmount"))
            currency, source = (page_currency, "tracking") if price is not None else (None, None)
        store = None
        ext = obj(trace.get("custom")).get("p4pExtendParam")
        if isinstance(ext, str):
            try:
                store = obj(json.loads(ext)).get("store_name")
            except ValueError:
                pass
        img = obj(c.get("image")).get("imgUrl")
        img = ("https:" + img if img.startswith("//") else img) if isinstance(img, str) and img else None
        items.append({
            "product_id": pid,
            "title": obj(c.get("title")).get("displayTitle"),
            "price": price,
            "price_text": price_text,
            "original_price": original,
            "currency": currency,
            "price_source": source,            # "card", "tracking" (welcome deal) or None
            "welcome_deal": "welcomegift" in str(c.get("productDetailUrl") or ""),
            "sold": obj(c.get("trade")).get("tradeDesc"),
            "sold_count": int(ut["real_trade_count"]) if str(ut.get("real_trade_count", "")).isdigit() else None,
            "rating": num(obj(c.get("evaluation")).get("starRating")),
            "store_name": store,               # only on some cards, see Gotchas
            "sponsored": "p4p" in c,
            "image": img,
            "url": f"https://www.aliexpress.com/item/{pid}.html" if pid else None,
        })
    return items, page_info


def search(query, sort=None, max_pages=3, pause=3):
    """-> (rows, report). Stops on an empty `zero_result` page or at max_pages; raises on a block."""
    max_pages = min(max_pages, SITE_MAX_PAGES)
    rows, report = {}, {"pages_read": 0, "stopped": None, "totalResults": None}
    for page in range(1, max_pages + 1):
        html = fetch(search_url(query, page, sort))
        data = parse_init_data(html)
        if data is None:
            raise SearchBlocked(f"page {page}: no _init_data_ (len={len(html)}); captcha or layout change")
        items, info = normalize(data)
        if not items:
            if info.get("searchResultType") == "zero_result":
                report["stopped"] = "zero_result"     # past the last page: the only real end
                break
            raise SearchBlocked(f"page {page}: 0 items, searchResultType={info.get('searchResultType')!r}")
        if info.get("page") not in (None, page):
            raise SearchBlocked(f"asked for page {page}, page reports {info.get('page')}")
        new = 0
        for i, it in enumerate(items):
            key = it["product_id"] or f"no-id:p{page}:{i}"   # keep id-less cards instead of dropping them
            if key not in rows:
                rows[key] = it
                new += 1
        report.update(pages_read=page, totalResults=info.get("totalResults"))
        print(f"page {page}: {len(items)} items, {new} new, totalResults={info.get('totalResults')}")
        time.sleep(pause)
    else:
        report["stopped"] = "site_cap_60" if max_pages == SITE_MAX_PAGES else f"max_pages={max_pages}"
        print(f"stopped at the page cap ({report['stopped']}), not at the end of results")
    return rows, report


rows, report = search("phone case", max_pages=3)
vals = list(rows.values())
print(len(vals), "unique products", report)
print("no product_id:", sum(r["product_id"] is None for r in vals))
print("price_source:", {s: sum(r["price_source"] == s for r in vals) for s in ("card", "tracking", None)})
print("present:", {k: sum(r[k] is not None for r in vals) for k in ("price", "original_price", "sold", "sold_count", "rating", "store_name", "image")},
      "sponsored:", sum(r["sponsored"] for r in vals))
for src in ("card", "tracking"):
    ex = next((r for r in vals if r["price_source"] == src), None)
    if ex:
        print(json.dumps(ex))
```

Observed output (trimmed):

```
page 1: 60 items, 60 new, totalResults=91793
page 2: 60 items, 54 new, totalResults=83550
page 3: 60 items, 52 new, totalResults=83551
stopped at the page cap (max_pages=3), not at the end of results
166 unique products {'pages_read': 3, 'stopped': 'max_pages=3', 'totalResults': 83551}
no product_id: 0
price_source: {'card': 102, 'tracking': 64, None: 0}
present: {'price': 166, 'original_price': 153, 'sold': 159, 'sold_count': 159, 'rating': 143, 'store_name': 66, 'image': 166} sponsored: 38
{"product_id": "3256813091598934", "title": "INS Korean Simple Blue Pink Bow Girl Mirror Cute Phone Case For iPhone 17 16 15 Pro Max ...", "price": 1.09, "price_text": "US $1.09", "original_price": 3.73, "currency": "USD", "price_source": "card", "welcome_deal": false, "sold": "600+ sold", "sold_count": 677, "rating": 4.9, "store_name": null, "sponsored": false, "image": "https://ae-pic-a1.aliexpress-media.com/kf/Sd58da08b5ba94a8ca1e95899d8680f30s.jpg", "url": "https://www.aliexpress.com/item/3256813091598934.html"}
{"product_id": "3256810401258185", "title": "Custom Matte Case For iPhone 17 16 15 14 13 12 11 Pro Max ...", "price": 1.09, "price_text": null, "original_price": 7.71, "currency": "USD", "price_source": "tracking", "welcome_deal": true, "sold": "5,000+ sold", "sold_count": 9365, "rating": 4.6, "store_name": null, "sponsored": false, "image": "https://ae-pic-a1.aliexpress-media.com/kf/Sd7c4a6e7aac3432b929b506d91338afeG.jpg", "url": "https://www.aliexpress.com/item/3256810401258185.html"}
```

64 of the 166 "phone case" products had `prices: null`; without the `utLogMap` fallback they would have had no price at all. Pages 2 and 3 repeated 6 and 8 products already seen, so always dedupe by `product_id`. `original_price` is missing on some priced cards: their `prices` object simply has no `originalPrice`. No 429 or 5xx came back, so the retry path did not fire. Earlier runs the same day gave 165 to 173 unique products for the same 3 pages.

### 2. Search + pagination in the browser

Same data, read from `window` instead of the HTML, in a normal browser session. `open_search` only parses once the tab's own URL carries the requested `SearchText` and `page` and that document is `complete`, so it never reads the previous page.

```python
import json, re, time, urllib.parse

def search_url(query, page=1, sort=None):
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    params = {"SearchText": query, "page": page, **({"sortType": sort} if sort else {})}
    return f"https://www.aliexpress.com/w/wholesale-{slug}.html?{urllib.parse.urlencode(params)}"

# Runs in the page: reads the same _init_data_ object the server-rendered HTML embeds.
EXTRACT = r"""
(() => {
  const base = {href: location.href, ready: document.readyState};
  const d = window._dida_config_ && window._dida_config_._init_data_;
  const root = d && d.data && (d.data.data || d.data).root;
  if (!root || !root.fields) return JSON.stringify({...base, error: 'no _init_data_', title: document.title});
  const o = x => (x && typeof x === 'object' && !Array.isArray(x)) ? x : {};
  const n = x => typeof x === 'number' ? x : null;
  const f = root.fields, info = o(f.pageInfo);
  const content = o(o(f.mods).itemList).content;
  const cards = (Array.isArray(content) ? content : []).filter(c => c && typeof c === 'object');
  const sp = c => o(o(c.prices).salePrice);
  const pageCur = (cards.map(c => sp(c).currencyCode).find(x => typeof x === 'string'))
                  || o(o(info.trace).utLogMap).currency || null;
  const cents = v => (v != null && /^\d+$/.test(String(v))) ? Number(v) / 100 : null;
  return JSON.stringify({...base, info: {totalResults: info.totalResults, page: info.page, pageSize: info.pageSize,
                                         resultType: info.searchResultType},
    items: cards.map(c => {
      const pid = (typeof c.productId === 'string' && c.productId) ? c.productId : null;
      const tr = o(c.trace), ut = o(tr.utLogMap);
      let store = null;
      try { store = JSON.parse(o(tr.custom).p4pExtendParam).store_name || null } catch (e) {}
      const s = sp(c), orig = o(o(c.prices).originalPrice);
      let price, price_text = null, original, currency = null, source = null;
      if (n(s.minPrice) != null) {
        price = s.minPrice; price_text = s.formattedPrice ?? null; original = n(orig.minPrice); currency = s.currencyCode; source = 'card';
      } else {   // welcome-deal card: prices is null, amounts only in tracking
        price = cents(ut.salePriceAmount); original = cents(ut.originPriceAmount);
        if (price != null) { currency = pageCur; source = 'tracking'; }
      }
      const img = o(c.image).imgUrl;
      return {product_id: pid, title: o(c.title).displayTitle ?? null,
        price, price_text, original_price: original, currency, price_source: source,
        welcome_deal: String(c.productDetailUrl || '').includes('welcomegift'),
        sold: o(c.trade).tradeDesc ?? null, sold_count: cents(ut.real_trade_count) == null ? null : Number(ut.real_trade_count),
        rating: n(o(c.evaluation).starRating), store_name: store, sponsored: 'p4p' in c,
        image: (typeof img === 'string' && img) ? (img.startsWith('//') ? 'https:' + img : img) : null,
        url: pid ? 'https://www.aliexpress.com/item/' + pid + '.html' : null};
    })});
})()
"""

def open_search(url, timeout=30, attempts=2):
    """Navigate and return EXTRACT's result for THIS url's document (never the previous page's)."""
    want = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    for attempt in range(1, attempts + 1):
        try:
            goto_url(url)
        except TimeoutError:              # daemon IPC timeout; the navigation may still be running
            pass
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.5)
            try:
                res = json.loads(js(EXTRACT))
            except (TimeoutError, RuntimeError):   # evaluate timed out, or the context was replaced mid-navigation
                continue
            got = urllib.parse.parse_qs(urllib.parse.urlsplit(res["href"]).query)
            if res["ready"] == "complete" and all(got.get(k) == v for k, v in want.items()):
                return res
        print(f"  attempt {attempt}: {url} did not finish loading in {timeout}s")
    raise TimeoutError(f"search page did not load: {url}")

def search_in_browser(query, sort=None, max_pages=3, pause=3):
    max_pages = min(max_pages, 60)        # site cap
    rows, report = {}, {"pages_read": 0, "stopped": None}
    for page in range(1, max_pages + 1):
        res = open_search(search_url(query, page, sort))
        if "error" in res:
            raise RuntimeError(f"page {page}: {res}")   # captcha or layout change: stop, do not retry in a loop
        if not res["items"]:
            if res["info"]["resultType"] == "zero_result":
                report["stopped"] = "zero_result"
                break
            raise RuntimeError(f"page {page}: 0 items, info={res['info']}")
        if res["info"]["page"] not in (None, page):
            raise RuntimeError(f"asked for page {page}, page reports {res['info']['page']}")
        new = 0
        for i, it in enumerate(res["items"]):
            key = it["product_id"] or f"no-id:p{page}:{i}"
            if key not in rows:
                rows[key] = it
                new += 1
        report["pages_read"] = page
        print(f"page {page}: {len(res['items'])} items, {new} new, info={res['info']}")
        time.sleep(pause)
    else:
        report["stopped"] = f"max_pages={max_pages}"
        print(f"stopped at the page cap ({report['stopped']}), not at the end of results")
    return rows, report

new_tab()                                 # blank background tab; open_search navigates it
rows, report = search_in_browser("phone case", max_pages=3)
vals = list(rows.values())
print(len(vals), "unique products", report)
print("price_source:", {s: sum(r["price_source"] == s for r in vals) for s in ("card", "tracking", None)})
ex = next((r for r in vals if r["price_source"] == "tracking"), None) or next(iter(vals), None)
print(json.dumps(ex))
```

Observed output (trimmed):

```
page 1: 60 items, 60 new, info={'totalResults': 83551, 'page': 1, 'pageSize': 60, 'resultType': 'normal_result'}
page 2: 60 items, 54 new, info={'totalResults': 91750, 'page': 2, 'pageSize': 60, 'resultType': 'normal_result'}
page 3: 60 items, 49 new, info={'totalResults': 91750, 'page': 3, 'pageSize': 60, 'resultType': 'normal_result'}
stopped at the page cap (max_pages=3), not at the end of results
163 unique products {'pages_read': 3, 'stopped': 'max_pages=3'}
price_source: {'card': 110, 'tracking': 53, None: 0}
{"product_id": "3256811701939685", "title": "Red Cherry Pattern Mirror Phone Case For iPhone 17 Pro Max ...", "price": 1.09, "price_text": null, "original_price": 3.54, "currency": "USD", "price_source": "tracking", "welcome_deal": true, "sold": "600+ sold", "sold_count": 628, "rating": 4.9, "store_name": "Shop1105082514 Store", "sponsored": false, "image": "https://ae-pic-a1.aliexpress-media.com/kf/S90e05db4d57d44fe991d1ebc759edadcr.jpg", "url": "https://www.aliexpress.com/item/3256811701939685.html"}
```

The browser repeats products across pages too (here 6 and 11 repeats on pages 2 and 3), so dedupe the same way.

### Sorting

Pass `sort=` to `search_url` / `search` / `search_in_browser` (it becomes `sortType` in the query string). Confirmed on 2026-10-23 by reading which sort the page's own `mods.sortBar` marked `selected`:

| `sortType` | Sort bar shows | First prices observed (phone case) | Welcome-deal cards (`prices: null`) per 60, phone case |
|---|---|---|---|
| (omitted) | Best matches | - | 18 (page 1), 24 (page 2) |
| `total_tranpro_desc` | Popular (orders desc) | - | 29 (page 1), 32 (page 2) |
| `price_asc` | Price low to high | 0.33, 0.33, 0.78, 0.86 | not counted |
| `price_desc` | Price high to low | 765, 588.09, 465.69, 261.85 (a later run: 337.03, 261.29) | not counted |

Use a sort to choose the order you want, not to read past the 3,600-card cap. Pass the same `normalize()` / `EXTRACT` over every sort. Popular sort had about half its cards as welcome deals, so any extractor that only reads `prices` loses price on half that sort.

### 3. Product page: variants, per-variant price and stock, shipping, store

Open the product page in the browser and read the page's own `mtop.aliexpress.pdp.pc.query` response from the network log. This block takes product IDs from a live search so it never depends on a delisted item. `search_ids` only reads a completed document whose own URL carries the requested query parameters, and `capture_pdp` only returns a response whose `productId` equals the requested one.

```python
import json, re, time, urllib.parse

class ProductAPIRefused(RuntimeError):
    """The product API answered with a captcha ("punish") instead of data. Stop and wait."""

def obj(x):
    return x if isinstance(x, dict) else {}

def capture_pdp(product_id, timeout=25):
    """Open a product page; return its `mtop.aliexpress.pdp.pc.query` result dict, or None if none arrived."""
    try:
        drain_events()                    # discard events from earlier pages
    except TimeoutError:
        pass
    try:
        goto_url(f"https://www.aliexpress.com/item/{product_id}.html")
    except TimeoutError:                  # IPC timeout; the navigation may still be running
        pass
    pending, deadline = [], time.time() + timeout
    while time.time() < deadline:
        try:
            events = drain_events()       # the daemon keeps only the last 500 events, so poll often
        except TimeoutError:
            events = []
        for e in events:
            if e.get("method") == "Network.responseReceived" and \
               "mtop.aliexpress.pdp.pc.query" in obj(obj(e.get("params")).get("response")).get("url", ""):
                pending.append(e["params"]["requestId"])
        while pending:
            rid = pending.pop(0)
            body = None
            for _ in range(20):           # body is readable once the response has finished loading
                try:
                    body = cdp("Network.getResponseBody", requestId=rid)["body"]
                    break
                except (RuntimeError, TimeoutError):
                    time.sleep(0.5)
            if body is None:
                continue
            m = re.match(r"^\s*[\w.]+\((.*)\)\s*;?\s*$", body, re.S)   # JSONP: mtopjsonp1({...})
            try:
                d = json.loads(m.group(1) if m else body)
            except ValueError:
                continue
            ret = [x for x in obj(d).get("ret") or [] if isinstance(x, str)]
            if any(x.startswith("SUCCESS") for x in ret):
                result = obj(obj(d.get("data")).get("result"))
                got = obj(result.get("PRICE")).get("productId")
                if str(got) != str(product_id):
                    print(f"  ignoring a response for product {got}, wanted {product_id}")
                    continue
                return result
            if any("TOKEN" in x for x in ret):
                continue                  # FAIL_SYS_TOKEN_EMPTY: the page sets a token cookie and retries itself
            # FAIL_SYS_USER_VALIDATE / RGV587_ERROR = slider captcha ("punish") on the API. Back off.
            raise ProductAPIRefused(f"product API refused: {ret}")
        time.sleep(0.25)
    return None

def parse_pdp(r):
    sku = obj(r.get("SKU"))
    prices = obj(obj(r.get("PRICE")).get("skuIdStrPriceInfoMap"))
    props_list = [p for p in sku.get("skuProperties") or [] if isinstance(p, dict)]
    names = {f'{prop.get("skuPropertyId")}:{v.get("propertyValueIdLong")}': v.get("propertyValueDisplayName")
             for prop in props_list for v in prop.get("skuPropertyValues") or [] if isinstance(v, dict)}
    variants = []
    for p in sku.get("skuPaths") or []:
        p = obj(p)
        sid = p.get("skuIdStr")
        pi = obj(prices.get(sid))
        variants.append({
            "sku_id": sid,
            "options": [names.get(k, k) for k in str(p.get("path") or "").split(";") if k],
            "price": pi.get("salePriceString"),
            "original_price": obj(pi.get("originalPrice")).get("formatedAmount"),
            "stock": p.get("skuStock"),
            "salable": p.get("salable"),
        })
    options = {prop.get("skuPropertyName"): [obj(v).get("propertyValueDisplayName") for v in prop.get("skuPropertyValues") or []]
               for prop in props_list}
    span = lambda a, b, sep: f"{a}{sep}{b}" if a is not None and b is not None else None
    shipping = []
    for o in obj(r.get("SHIPPING")).get("deliveryLayoutInfo") or []:
        b = obj(obj(o).get("bizData"))
        shipping.append({
            "method": b.get("deliveryProviderName") or b.get("company"),
            "fee": "Free" if b.get("shippingFee") == "free" else b.get("formattedAmount"),
            "ship_from": b.get("shipFrom"),
            "ship_to": b.get("shipToCode"),
            "eta": span(b.get("displayEtaMinDate"), b.get("displayEtaMaxDate"), " - "),
            "days": span(b.get("deliveryDayMin"), b.get("deliveryDayMax"), "-"),
            "tracking": b.get("tracking"),
        })
    shop = obj(r.get("SHOP_CARD_PC"))
    seller = obj(shop.get("sellerInfo"))
    rating = obj(r.get("PC_RATING"))
    props = obj(r.get("PRODUCT_PROP_PC"))
    store_url = seller.get("storeURL") if isinstance(seller.get("storeURL"), str) else ""
    pid = obj(r.get("PRICE")).get("productId")
    return {
        "product_id": str(pid) if pid is not None else None,
        "title": obj(r.get("PRODUCT_TITLE")).get("text"),
        "rating": rating.get("rating"),
        "reviews": rating.get("totalValidNum"),
        "sales_text": rating.get("otherText"),
        "store_name": shop.get("storeName"),
        "store_url": ("https:" + store_url if store_url.startswith("//") else store_url) or None,
        "store_positive_rate": shop.get("sellerPositiveRate"),
        "store_open_since": seller.get("formatOpenTime"),
        "options": options,
        "variants": variants,
        "shipping": shipping,
        "images": [i for i in obj(r.get("HEADER_IMAGE_PC")).get("imagePathList") or [] if isinstance(i, str)],
        "specs": [(obj(a).get("attrName"), obj(a).get("attrValue")) for a in props.get("showedProps") or props.get("outerProps") or []],
    }

def search_ids(url, timeout=30):
    """Open a search page and return its product IDs, after confirming the tab shows that URL's query."""
    want = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    goto_url(url)
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.5)
        try:
            res = json.loads(js("""JSON.stringify((() => { const d = window._dida_config_ && window._dida_config_._init_data_;
              const root = d && d.data && (d.data.data || d.data).root;
              const c = root && root.fields && root.fields.mods && root.fields.mods.itemList && root.fields.mods.itemList.content;
              return {href: location.href, ready: document.readyState,
                      ids: Array.isArray(c) ? c.map(x => x && x.productId).filter(x => typeof x === 'string') : null}; })())"""))
        except (TimeoutError, RuntimeError):
            continue
        got = urllib.parse.parse_qs(urllib.parse.urlsplit(res["href"]).query)
        if res["ready"] == "complete" and all(got.get(k) == v for k, v in want.items()):
            if res["ids"] is None:
                raise RuntimeError(f"search page has no _init_data_: {res['href']}")
            return res["ids"]
    raise TimeoutError(f"search page did not load: {url}")

new_tab()
ids = search_ids("https://www.aliexpress.com/w/wholesale-mechanical-keyboard.html?SearchText=mechanical+keyboard")
print(len(ids), "ids from search")
if not ids:
    raise RuntimeError("search returned no product IDs")
parsed, no_response, refused_at = [], [], None
for pid in ids[:3]:
    time.sleep(8)                         # polite pacing between product pages
    try:
        r = capture_pdp(pid)
    except ProductAPIRefused as e:
        refused_at = pid
        print(pid, e, "- stopping; wait several minutes before more product pages")
        break
    if r is None:
        no_response.append(pid)
        print(pid, "no product API response seen (layout change?)", page_info()["url"])
        continue
    d = parse_pdp(r)
    parsed.append(d)
    print(json.dumps({**d, "images": d["images"][:2], "variants": d["variants"][:3], "specs": d["specs"][:3],
                      "n_variants": len(d["variants"]), "n_images": len(d["images"]), "n_specs": len(d["specs"])}))
print(f"parsed {len(parsed)} of {len(ids[:3])}; no response: {no_response}; refused at: {refused_at}")
```

Observed output (one of the 3 products, trimmed):

```json
{"product_id": "3256807353643961",
 "title": "AJAZZ AK820 and AK820PRO Mechanical Gaming Keyboard 75% Layout PBT OEM Keycap RGB Backlight Full Key Anti-Ghosting Type-C",
 "rating": "4.9", "reviews": 5048, "sales_text": "This seller: 700+ sales | Total sales: 10,000+",
 "store_name": "Stone's Store", "store_url": "https://www.aliexpress.com/store/1103576287",
 "store_positive_rate": "100.0", "store_open_since": "Mar 1, 2024",
 "options": {"Color": ["AK820 Gray", "AK820Pro Gift Purple", "AK820Pro Gift Gray", "AK820 Purple", "AK820 Black"], "Axis Body": ["Red Switch"]},
 "variants": [{"sku_id": "12000061215413600", "options": ["AK820Pro Gift Purple", "Red Switch"], "price": "$77.93", "original_price": "$170.69", "stock": 10, "salable": true},
              {"sku_id": "12000041213380330", "options": ["AK820 Black", "Red Switch"], "price": "$25.32", "original_price": "$61.08", "stock": 68, "salable": true}],
 "shipping": [{"method": "AliExpress Selection Standard Shipping", "fee": "$1.99", "ship_from": "China", "ship_to": "US",
               "eta": "Oct. 29 - Nov. 03", "days": "6-11", "tracking": "visible"}],
 "n_variants": 5, "n_images": 6, "n_specs": 15}
```

The final line of that run was `parsed 3 of 3; no response: []; refused at: None`. The third product had a variant with `"stock": 0, "salable": false`. In another test session the same block was refused on its first product and stopped cleanly:

```
3256806808315712 product API refused: ['FAIL_SYS_USER_VALIDATE', 'RGV587_ERROR::SM::...'] - stopping; wait several minutes before more product pages
parsed 0 of 3; no response: []; refused at: 3256806808315712
```

Other shipping values seen on 2026-10-23: `{"method": "AE_US_SAVER", "fee": "Free", "ship_from": "United States", "days": "3-9", ...}` (US-warehouse item), `{"method": "AliExpress Premium Shipping", "fee": "Free", ...}` and `{"method": "DHL", "fee": "$826.63", ...}` (shipping on a bulk phone-case listing).

## Fields

### Search card (`_init_data_.data.root.fields.mods.itemList.content[i]`)

Blocks 1 and 2 return the same keys. "Present" counts are from the final block 1 run: 166 unique "phone case" products, 64 of them priced from `utLogMap`.

| Output field | Source path | Example | Present |
|---|---|---|---|
| `product_id` | `productId` (string), else `None` | `"3256811701939685"` | 166 of 166 |
| `title` | `title.displayTitle` | `"Red Cherry Pattern Mirror Phone Case ..."` | 166 of 166 |
| `price` | `prices.salePrice.minPrice` if numeric; else `trace.utLogMap.salePriceAmount` / 100 | `1.09` | 166 of 166 (102 from `prices`, 64 from `utLogMap`) |
| `price_text` | `prices.salePrice.formattedPrice` | `"US $1.09"` | 102 of 166 (null on welcome-deal cards) |
| `original_price` | `prices.originalPrice.minPrice`; on welcome-deal cards `trace.utLogMap.originPriceAmount` / 100 | `3.54` | 153 of 166 |
| `currency` | `prices.salePrice.currencyCode`; on welcome-deal cards, the page's currency | `"USD"` | 166 of 166 |
| `price_source` | which of the two price paths was used | `"card"` / `"tracking"` / `None` | always set (`None` only when there is no price) |
| `welcome_deal` | `"welcomegift" in productDetailUrl` | `true` | boolean, always |
| `sold` | `trade.tradeDesc` | `"600+ sold"` (rounded text) | 159 of 166 |
| `sold_count` | `trace.utLogMap.real_trade_count` | `628` (exact) | 159 of 166 |
| `rating` | `evaluation.starRating` if numeric | `4.9` | 143 of 166 |
| `store_name` | `trace.custom.p4pExtendParam` (JSON string) `.store_name` | `"Shop1105082514 Store"` | 66 of 166 |
| `sponsored` | `"p4p" in card` | `true` | boolean, 38 of 166 true |
| `image` | `image.imgUrl`, protocol-relative made `https:` | `https://ae-pic-a1.aliexpress-media.com/kf/...jpg` | 166 of 166 |
| `url` | built from `productId` (`None` if no id) | `https://www.aliexpress.com/item/<id>.html` | 166 of 166 |

How much `prices: null` matters depends on the query. Pages checked on 2026-10-23 (cards with `prices: null` out of 60): phone case 18 and 24 (pages 1-2), phone case Popular sort 29 and 32, usb cable 16, mechanical keyboard 0. Across those 360 cards, every one of the 119 null-price cards was a welcome-deal card and vice versa.

Page-level: `fields.pageInfo` has `totalResults`, `page`, `pageSize` (60), `searchResultType` (`normal_result` or `zero_result`), and `trace.utLogMap.currency` (`"USD"`).

### Product page (`mtop.aliexpress.pdp.pc.query` -> `data.result`)

| Block | Useful keys |
|---|---|
| `PRODUCT_TITLE` | `text` |
| `SKU` | `skuProperties[]` (`skuPropertyName`, `skuPropertyValues[].propertyValueDisplayName`, `propertyValueIdLong`, `skuPropertyImagePath`), `skuPaths[]` (`skuIdStr`, `path` = `"propId:valueId;..."`, `skuStock`, `salable`), `selectedSkuIdStr` |
| `PRICE` | `productId`, `skuIdStrPriceInfoMap[skuId]` -> `salePriceString`, `originalPrice.value`, `originalPrice.formatedAmount` (sic) |
| `QUANTITY_PC` | `allSkuQuantityView[skuId].maxBuyCount`, `hintText` (e.g. `"Max. 1 pcs/shopper"`) |
| `SHIPPING` | `deliveryLayoutInfo[].bizData`: `deliveryProviderName`, `shippingFee` (`"free"` or `"charge"`), `formattedAmount`, `shipFrom`, `shipToCode`, `deliveryDayMin/Max`, `displayEtaMinDate/MaxDate`, `tracking`, `showMoreCount` |
| `SHOP_CARD_PC` | `storeName`, `sellerPositiveRate`, `benefitInfoList` (`positive reviews`, `Communication`, `Items as description`), `sellerInfo.storeURL`, `sellerInfo.formatOpenTime`, `sellerInfo.countryCompleteName` |
| `PC_RATING` | `rating`, `totalValidNum` (review count), `otherText` (sales text) |
| `HEADER_IMAGE_PC` | `imagePathList` (gallery) |
| `PRODUCT_PROP_PC` | `showedProps[]` / `outerProps[]` -> `attrName`, `attrValue` |
| `WISHLIST` | `wishItemCount`, `storeWishedCount` |
| `GLOBAL_DATA.globalData` | `productId`, `categoryPath`, `sellerId` |

`parse_pdp` returns: `product_id`, `title`, `rating`, `reviews`, `sales_text`, `store_name`, `store_url`, `store_positive_rate`, `store_open_since`, `options` (property name -> value names), `variants[]` (`sku_id`, `options`, `price`, `original_price`, `stock`, `salable`), `shipping[]` (`method`, `fee`, `ship_from`, `ship_to`, `eta`, `days`, `tracking`), `images`, `specs` (name, value pairs). `rating` and `store_positive_rate` are strings as sent by the API.

## Gotchas

- **Region redirect.** From a US IP, `www.aliexpress.com/item/<id>.html` redirected to `www.aliexpress.us/item/<id>.html?gatewayAdapt=glo2usa`, and the product API was served from `acs.aliexpress.us`. Match the API by its name (`mtop.aliexpress.pdp.pc.query`), not by host. Search pages stayed on `www.aliexpress.com`, but card links in the rendered DOM pointed at `www.aliexpress.us`.
- **Product IDs from a US IP start with `3256`** (US-site IDs). The cards also carry a `1005...` global ID inside `trace.pdpParams.pdp_ext_f` (`orig_item_id`). Other regions were not tested.
- **Prices, currency and shipping are geo-dependent.** Everything above was USD with ship-to `US`. The product page shows `"Add location for exact delivery"` and quotes shipping for the country, not a ZIP. Prices also vary per session: the same search card showed `$25.32` in one load and `$24.16` in another, and the same SKU (`AK820 Black`) was `$25.32` on the product page in one browser session and `$26.39` in a later one. Store a timestamp with every price.
- **Only the default shipping option is in the product response.** `deliveryLayoutInfo` had exactly 1 entry on every product checked (6 distinct products), while `bizData.showMoreCount` was `100`. The other options load only when the shipping panel is opened.
- **Some product pages aggregate several merchants.** One AJAZZ page carried a compliance note saying it aggregates "reviews and sales volume of similar items offered by multiple overseas merchants". `reviews` and `sales_text` can cover more than one seller; `store_name` is the merchant currently selected.
- **Welcome-deal cards hide their price.** Logged out, many cards are new-shopper offers: the rendered card shows `"FREE with any purchase"` instead of a price, links to `/ssr/300001493/welcomegiftspmpc?...productIds=<1005 id>`, and has `prices: null` in `_init_data_`. The amounts are only in `trace.utLogMap` as integer-cent strings: `salePriceAmount` (e.g. `"109"`), `originPriceAmount`, `sellerOfferPriceAmount`. On the 228 priced cards where `salePriceAmount` was present it equalled `prices.salePrice.cent` every time, and `originPriceAmount` matched `originalPrice.minPrice` on 224 of 228. On 2 welcome-deal product pages opened logged out, every variant's price was `$1.09`, the same as their `salePriceAmount`. Treat it as the logged-out new-shopper price; keep `price_source` / `welcome_deal` so you can filter these rows out. 1 of 119 null-price cards had no `salePriceAmount`, so `price` can still be `None`.
- **`utLogMap.quotaCurrencyCode` is not the display currency.** It said `CNY` on 49 of 60 cards whose prices were in USD cents. Take the currency from `prices.salePrice.currencyCode` of any priced card on the page, else from `pageInfo.trace.utLogMap.currency` (what `normalize` does).
- **Store name on search cards is partial.** It comes from an ad-tracking field (`p4pExtendParam`) and was on 66 to 90 of about 170 unique cards across runs. For a reliable store name, open the product page (`SHOP_CARD_PC.storeName`).
- **`sold` is display text** with rounding (`"10,000+ sold"`, `"600+ sold"`, `"32 sold"`). `sold_count` (`utLogMap.real_trade_count`) is the exact number; it agreed with `sold` (equal, or at least the `N+` floor) on 343 of 349 cards that had both.
- **Results reshuffle between requests.** `totalResults` changed between pages of the same query (83,301 -> 83,208 -> 83,274 in the browser), and both plain HTTP and the browser repeated products from earlier pages (3 to 11 per page). Dedupe by `product_id`.
- **A short page is not the end.** "ajazz ak820 pro gift purple red switch" returned 39 cards on page 1 with `totalResults` 40, then 60 cards on pages 2 and 3 with `totalResults` 438. Only an empty `zero_result` page ends a search.
- **Page cap is 60.** Page 61 returns `zero_result`. If your loop stops at its own `max_pages` instead, it says so; that is a cap, not the end of results.
- **Product data is not in the DOM or HTML.** `window.runParams` is `{}` and `window._d_c_.DCData` only has image lists. Do not scrape CSS classes; read the API response.
- **The event buffer is small.** The harness daemon keeps the last 500 CDP events. A product page fires about 400 network responses, so a single `drain_events()` after load missed the API response. Poll `drain_events()` every 0.25 s while the page loads (as in `capture_pdp`).
- **No consent banner or login wall** appeared on search or product pages from the US cloud browser.
- **The product API refuses early and unpredictably.** The first refusal came at a different point in each of 3 test sessions on 2026-10-23: on the 1st product page in one (after only 1 search page), on the 2nd in another, and not within 13 product pages about 9 s apart in a third. A refusal is `ret: ["FAIL_SYS_USER_VALIDATE", "RGV587_ERROR::SM::..."]`. The page then rendered only header and footer (title just the tab marker) plus an iframe at `acs.aliexpress.us//h5/mtop.aliexpress.pdp.pc.query/1.0/_____tmd_____/punish?x5secdata=...`, which is a slider captcha. Search pages kept working in the same browser, and in one browser the product refusal was still in place 8 minutes later. Do not solve or bypass it: stop, wait, and lower your rate (`capture_pdp` raises `ProductAPIRefused` so the loop stops on the first refusal). Get prices, sold counts and ratings from search cards, and open product pages only for the few items that need variants, stock or shipping.
- **First product request in a new browser can fail with `FAIL_SYS_TOKEN_EMPTY::令牌为空`.** The page then sets its token cookie and repeats the same API call, which succeeds. `capture_pdp` skips token errors and waits for the repeat; do not treat that first response as a block.
- **Pacing.** Keep at least 3 s between search pages and more between product pages, and stop on the first page without `_init_data_` or the first API refusal instead of retrying in a loop. `fetch` only retries 429, 5xx and network errors, honoring `Retry-After` up to 120 s and stopping if asked to wait longer; none of those were seen on 2026-10-23.
- **The tabs stay in the background.** Nothing here calls `activate_tab`; search and product pages loaded and fired their API calls in a background tab of the cloud browser.

## What does not work

- **Plain HTTP on product pages.** `https://www.aliexpress.com/item/3256807353643961.html` and `https://www.aliexpress.us/item/3256807353643961.html` both raised `HTTPError 302 ... infinite loop` (`Moved Temporarily`, a cookie-based redirect). Use the browser for product pages.
- **Reading product data from the HTML.** The rendered product HTML (about 385 KB) has no SKU or price JSON; it is fetched after load.
- **Pages beyond 60** of any search (`zero_result`).
- **All shipping options in one call.** Only the default option is returned with the page (see Gotchas).
