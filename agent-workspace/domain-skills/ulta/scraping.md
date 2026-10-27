# Ulta Beauty — Category, Brand and Search Listings & Product Details

Field-tested against www.ulta.com on 2026-10-23, rerun on 2026-10-24, using a Browser Use cloud browser (search results) and plain HTTP with Python's urllib (category, brand and product pages).

robots.txt (checked 2026-10-23) has no `User-agent: *` group, so nothing is disallowed for generic clients; every path used here (`/shop/`, `/brand/`, `/search`, `/p/`, `/sitemap/`) is allowed. The named-bot groups only disallow `/auth/`, `/authorize`, `/u/`, `/metrics*`, `/wishlists/`, `/curbside-alert/` and similar account paths, none of which this skill touches.

## Quick summary

- **Category and brand listings (`/shop/...`, `/brand/...`) are server-rendered.** A plain GET with a truthful UA returned **200** and the full grid inside `window.__APOLLO_STATE__`: the `ProductListingResults` module holds 64 `items` per page (product ID, SKU, brand, name, list/sale price, rating, review count, URL), plus `resultCount`, `page` and `loadMoreUrl`. Pagination is `?page=N`. No browser needed.
- **Search (`/search?search=...`) is client-rendered.** Over plain HTTP the same module is present but has no items, so block 2 loads the search page in the browser and reads the rendered product cards (`li[data-test="products-list-item"]`). Pagination is the page's own "Load More" link, `&page=N`.
- **Product pages (`/p/<slug>-<productId>?sku=<sku>`)**: plain GET returned **200** with `Product`, `ProductGroup` (all shades/sizes) and `BreadcrumbList` JSON-LD, plus `ProductPricing` / `ProductDetail` modules in `__APOLLO_STATE__` (sale price, details, how-to-use, ingredients, questions count).
- Category URLs: `https://www.ulta.com/sitemap/shop.xml` listed 288 `/shop/` URLs on 2026-10-23 (`/sitemap/index.xml` lists the other sitemaps, including `brand.xml`).

## What works

### 1. Category or brand listing, all pages (plain HTTP, no browser)

Runs as plain `python3` or inside `browser-harness`.

```python
import json, re, subprocess, sys, time, urllib.parse

LISTING_URL = "https://www.ulta.com/shop/makeup/face/foundation"   # any /shop/... or /brand/... listing page
MAX_PAGES = 3          # 64 products per page; a hard cap: hitting it with pages left prints PARTIAL
UA = "browser-harness/1.0 (ulta domain skill; plain urllib)"   # truthful client UA

FETCH_CHILD = r"""
import gzip, json, sys, urllib.error, urllib.request
url, ua = sys.argv[1], sys.argv[2]
req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html", "Accept-Encoding": "gzip"})
try:
    with urllib.request.urlopen(req) as r:
        status, final, body, enc = r.status, r.geturl(), r.read(), r.headers.get("Content-Encoding")
except urllib.error.HTTPError as e:
    status, final, body, enc = e.code, e.geturl() or url, b"", None
if enc == "gzip":
    body = gzip.decompress(body)
sys.stdout.buffer.write(json.dumps({"status": status, "url": final}).encode() + b"\n" + body)
"""

def get_once(url, budget):
    """One GET in a child process that is killed at `budget` s: DNS, connect, headers and a trickled body all
    stop at the deadline, and no thread or socket outlives the call. Returns (status, final_url, body)."""
    try:
        p = subprocess.run([sys.executable, "-I", "-c", FETCH_CHILD, url, UA], capture_output=True, timeout=budget)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"no complete response within {budget:.1f} s (request process killed)")
    if p.returncode != 0:
        raise ConnectionError((p.stderr.decode(errors="replace").strip().splitlines() or ["fetch failed"])[-1])
    head, _, body = p.stdout.partition(b"\n")
    meta = json.loads(head)
    return meta["status"], meta["url"], body

def fetch(url, deadline_s=120):
    """GET a page; retry only transient failures. One monotonic deadline covers every try and every wait;
    no sleep after the last try."""
    end, waits = time.monotonic() + deadline_s, [5, 15, 30]
    for attempt in range(len(waits) + 1):
        try:
            status, final_url, body = get_once(url, min(30, end - time.monotonic()))
        except (ConnectionError, TimeoutError) as e:
            err = repr(e)
        else:
            if status in (403, 429):
                raise SystemExit(f"HTTP {status} on {url}: Ulta is refusing or rate-limiting. Stop and back off.")
            if 400 <= status < 500:
                raise RuntimeError(f"HTTP {status} on {url}")
            if 300 <= status < 400:
                raise RuntimeError(f"HTTP {status} on {url}: unhandled redirect or not-modified, no body to parse")
            if 200 <= status < 300:
                if final_url != url:
                    raise RuntimeError(f"asked for {url}, was redirected to {final_url}")
                return body.decode("utf-8")
            err = f"HTTP {status}"
        if attempt == len(waits) or time.monotonic() + waits[attempt] >= end:
            raise RuntimeError(f"giving up on {url} after {attempt + 1} tries: {err}")
        time.sleep(waits[attempt])

def apollo_state(html):
    m = re.search(r"window\.__APOLLO_STATE__ = (\{.*?\})\s*\n", html, re.S)
    if not m:
        raise RuntimeError("no window.__APOLLO_STATE__ in the HTML (block page or layout change)")
    return json.loads(m.group(1))

def find_module(node, name):
    if isinstance(node, dict):
        if node.get("moduleName") == name and "items" in node:
            return node
        node = list(node.values())
    if isinstance(node, list):
        for v in node:
            hit = find_module(v, name)
            if hit:
                return hit
    return None

def money(s):
    """'$52.00' -> 52.0; ranges like '$27.50 - $55.00' -> 27.5 (the low end); None stays None."""
    m = re.search(r"\$([\d,]+(?:\.\d+)?)", s or "")
    return float(m.group(1).replace(",", "")) if m else None

parts = urllib.parse.urlsplit(LISTING_URL)
if parts.netloc != "www.ulta.com" or not re.match(r"^/(shop|brand)/", parts.path) or parts.query:
    raise SystemExit("LISTING_URL must be https://www.ulta.com/shop/... or /brand/... with no query string")

REQUIRED = ("productId", "skuId", "brandName", "productName")   # a page missing any of these is rejected

rows, seen, total, next_url, served = [], set(), None, None, 0
for page in range(1, MAX_PAGES + 1):
    if page > 1:
        time.sleep(3)   # polite pacing between pages
    url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"
    plr = find_module(apollo_state(fetch(url)), "ProductListingResults")
    if plr is None:
        raise RuntimeError(f"{url} has no ProductListingResults module: a department landing page? "
                           "Use a deeper /shop/... URL from https://www.ulta.com/sitemap/shop.xml")
    if plr.get("page") != page:
        raise RuntimeError(f"asked for page {page}, page module says {plr.get('page')}")
    total, size = plr.get("resultCount"), plr.get("pageSize")
    items = plr.get("items") or []
    if not isinstance(total, int) or not isinstance(size, int) or size < 1:
        raise RuntimeError(f"{url}: resultCount {total!r} / pageSize {size!r} missing: layout change")
    if total and not items:
        raise RuntimeError(f"{url}: 0 items but resultCount {total}: empty listing module, not accepting it")
    bad = [i for i, it in enumerate(items)
           if not all(it.get(k) for k in REQUIRED) or not (it.get("action") or {}).get("url")]
    if bad:
        raise RuntimeError(f"{url}: {len(bad)} of {len(items)} items lack {REQUIRED} or action.url "
                           f"(first at index {bad[0]}): layout change, not accepting this page")
    if plr.get("loadMoreUrl") and len(items) != size:
        raise RuntimeError(f"{url}: {len(items)} items on a non-last page (pageSize {size}): truncated page")
    served += len(items)
    for it in items:
        if it.get("skuId") in seen:
            continue
        seen.add(it.get("skuId"))
        rows.append({
            "product_id": it.get("productId"),         # e.g. pimprod2057355 / xlsImpprod5770257
            "sku": it.get("skuId"),                    # the default shade/size shown on the card
            "brand": it.get("brandName"),
            "name": it.get("productName"),
            "list_price": it.get("listPrice"),         # "$52.00" or "$27.50 - $55.00"
            "sale_price": it.get("salePrice"),         # None unless on sale
            "price_value": money(it.get("salePrice") or it.get("listPrice")),
            "rating": it.get("rating"),                # None/0 for unrated items
            "review_count": it.get("reviewCount"),
            "variants": it.get("variantLabel"),        # "57 colors", "3 sizes", ...
            "promo": it.get("promoText"),
            "sponsored": bool(it.get("sponsored")),
            "url": (it.get("action") or {}).get("url"),
            "image": (it.get("image") or {}).get("imageUrl"),
        })
    next_url = plr.get("loadMoreUrl")
    print(f"page {page}: {len(items)} items, {len(rows)} unique so far, resultCount {total}, next {next_url}")
    if not next_url:
        break

complete = not next_url
if complete and served != total:
    raise RuntimeError(f"last page reached but the pages served {served} items, resultCount says {total}: "
                       "listing is incomplete, not reporting it as COMPLETE")
if complete:
    print(f"COMPLETE: {len(rows)} rows ({served} items served, {served - len(rows)} duplicate skus dropped), "
          f"resultCount {total}")
else:
    print(f"PARTIAL: stopped at MAX_PAGES={MAX_PAGES} with {len(rows)} of {total} rows; "
          f"more pages exist (next {next_url}). Raise MAX_PAGES to collect them.")
print(json.dumps(rows[:2], indent=1, ensure_ascii=False))
```

Observed output (trimmed):

```
page 1: 64 items, 64 unique so far, resultCount 254, next https://www.ulta.com/shop/makeup/face/foundation?page=2
page 2: 64 items, 128 unique so far, resultCount 254, next https://www.ulta.com/shop/makeup/face/foundation?page=3
page 3: 64 items, 192 unique so far, resultCount 254, next https://www.ulta.com/shop/makeup/face/foundation?page=4
PARTIAL: stopped at MAX_PAGES=3 with 192 of 254 rows; more pages exist (next https://www.ulta.com/shop/makeup/face/foundation?page=4). Raise MAX_PAGES to collect them.
[
 {
  "product_id": "pimprod2057355",
  "sku": "2651970",
  "brand": "Estée Lauder",
  "name": "Double Wear Stay-in-Place Longwear Matte Foundation",
  "list_price": "$52.00",
  "sale_price": null,
  "price_value": 52.0,
  "rating": 4.2,
  "review_count": 10236,
  "variants": "57 colors",
  "promo": "Bundle & Save!",
  "sponsored": false,
  "url": "https://www.ulta.com/p/double-wear-stay-in-place-longwear-matte-foundation-pimprod2057355?sku=2651970",
  "image": "https://media.ultainc.com/i/ulta/2651970"
 },
 ...
]
```

`complete` is `False` and the `PARTIAL` line prints whenever the cap stops the walk while `loadMoreUrl` is still set; treat those rows as a truncated sample, not the category. `COMPLETE` needs more than a missing `loadMoreUrl`: every non-last page must hold exactly `pageSize` items, a page with 0 items while `resultCount` is nonzero raises, and the items served across all pages must equal `resultCount`, otherwise the block raises instead of printing `COMPLETE` (rows can be fewer than `resultCount` only through duplicate skus, which the line reports; mocked offline: an empty module, a 30-item non-last page, a last page that left 74 of 100 served, and a missing `resultCount` all raised). A page whose items lack `productId`, `skuId`, `brandName`, `productName` or `action.url` raises instead of being appended (checked offline with a mocked response; every live item on the pages below had all five).

Scale checks: with `MAX_PAGES = 20`, Foundation walked pages 1 to 4 (64, 64, 64, 62 items), returned 254 unique rows, equal to `resultCount`, and printed `COMPLETE: 254 rows (254 items served, 0 duplicate skus dropped), resultCount 254` (2026-10-24 rerun; on 2026-10-23 the 254 rows had 11 on sale, 27 unrated, 0 sponsored). `/brand/nars` printed `COMPLETE: 46 rows (46 items served, 0 duplicate skus dropped), resultCount 46` from one page. Face Moisturizer (`/shop/skin-care/moisturizers/face-moisturizer`, `resultCount` 1211) served `?page=10` (64 items) and `?page=19` (59 items, `loadMoreUrl` null), so 18 x 64 + 59 = 1211 (2026-10-23). `/brand/clinique?page=2` returned 64 of 237. `/shop/skin-care` raised the landing-page error.

### 2. Site search, 2+ pages (browser, reads the rendered cards)

Search results are fetched client-side after load, so this needs the browser. It opens its own background tab and closes it at the end.

```python
import json, re, time, urllib.parse

QUERY = "mascara"
MAX_PAGES = 3          # about 64 organic cards per page, plus up to ~15 "Sponsored" cards on pages 1-2
SKIP_SPONSORED = True

CARDS_JS = r"""(() => {
  const txt = (el) => el ? el.textContent.trim() : null;
  const cards = [...document.querySelectorAll('li[data-test="products-list-item"]')].map((li) => {
    const a = li.querySelector('a[href*="/p/"]');
    const priceBox = li.querySelector('.pal-c-ProductCardBody--price');
    const sr = priceBox ? [...priceBox.querySelectorAll('.sr-only')].map(txt) : [];
    const shown = priceBox ? [...priceBox.querySelectorAll('span')].filter(s => !s.classList.contains('sr-only') && !s.children.length).map(txt) : [];
    return {sku: li.dataset.skuId, url: a ? a.href : null,
            brand: txt(li.querySelector('.pal-c-ProductCardBody--brandName')),
            name: txt(li.querySelector('.pal-c-ProductCardBody--title')),
            rating_label: txt(li.querySelector('.pal-c-Ratings .sr-only')),       // "4.5 out of 5 stars ; 11892 reviews"
            price_sr: sr, price_shown: shown,
            variants: txt(li.querySelector('.pal-c-ProductCardHeader__variant')),
            tags: [...li.querySelectorAll('.pal-c-Tag__messageText')].map(txt)};
  });
  const heading = [...document.querySelectorAll('h1, h2')].map(txt).find(t => /^\d[\d,]*\+? results? for/i.test(t || '')) || null;   // '400+ results for "mascara"'
  const more = [...document.querySelectorAll('a[href*="page="]')].find(a => /load more/i.test(a.textContent));
  return {href: location.href, heading, next: more ? more.href : null, cards};
})()"""

def money(s):
    m = re.search(r"\$([\d,]+(?:\.\d+)?)", s or "")
    return float(m.group(1).replace(",", "")) if m else None

def parse(c):
    m = re.search(r"([\d.]+) out of 5 stars ; (\d+) reviews", c["rating_label"] or "")
    sale = next((s for s in c["price_sr"] if s.lower().startswith("sale price")), None)
    lst = next((s for s in c["price_sr"] if s.lower().startswith("list price")), None)
    shown = next((s for s in c["price_shown"] if s.startswith("$")), None)
    path = urllib.parse.urlsplit(c["url"] or "").path
    return {
        "product_id": path.rsplit("-", 1)[-1] if path.startswith("/p/") else None,   # pimprod..., xlsImpprod..., mkt..., or digits
        "sku": c["sku"],
        "brand": c["brand"],
        "name": c["name"],
        "price": sale[len("sale price "):] if sale else shown,    # "$12.99" or "$12.99 - $13.99"
        "list_price": lst[len("list price "):] if lst else shown,
        "on_sale": bool(sale),
        "price_value": money(sale or shown),
        "rating": float(m.group(1)) if m else None,             # None when the card shows no stars
        "review_count": int(m.group(2)) if m else None,
        "variants": c["variants"] or None,
        "sponsored": "Sponsored" in c["tags"],
        "tags": [t for t in c["tags"] if t != "Sponsored"],
        "url": c["url"],
    }

def same_search(href, url):
    a, b = urllib.parse.urlsplit(href), urllib.parse.urlsplit(url)
    return (a.netloc, a.path, urllib.parse.parse_qs(a.query)) == (b.netloc, b.path, urllib.parse.parse_qs(b.query))

CHALLENGE_JS = r"""(() => /access denied|just a moment|attention required|are you a (human|robot)|pardon our interruption/i
  .test(document.title + ' ' + (document.body ? document.body.innerText.slice(0, 500) : ''))
  || !!document.querySelector('iframe[src*="captcha"], iframe[title*="challenge" i], #px-captcha, #challenge-form'))()"""

def missing_fields(r):
    """Cards that are still unhydrated or lost their layout: no sku, /p/ link, brand or name."""
    return [i for i, c in enumerate(r["cards"])
            if not (c["sku"] and "/p/" in (c["url"] or "") and c["brand"] and c["name"])]

def load(url, timeout=60):
    """Navigate, confirm the tab is on that search URL, wait until every card has its required fields
    (16 s and more on a cold browser). One deadline for the whole wait; raises on a challenge page."""
    goto_url(url)
    deadline, bad, ncards = time.time() + timeout, None, 0
    while True:
        href = js("location.href") or ""
        if js(CHALLENGE_JS):
            raise SystemExit(f"bot challenge or block page at {href}: stopping, do not retry around it")
        if "/search/no-results" in href:
            return None
        if href and not href.startswith(("https://www.ulta.com/search?", "about:blank")):
            raise SystemExit(f"Ulta redirected the search to {href} (brand or category page): "
                             "scrape that URL with block 1 instead")
        if same_search(href, url):
            r = js(CARDS_JS)
            if r and r["cards"]:
                bad, ncards = missing_fields(r), len(r["cards"])
                if not bad:
                    return r
        if time.time() > deadline:
            if bad:
                raise RuntimeError(f"{url}: {len(bad)} of {ncards} cards still lack sku/url/brand/name "
                                   f"after {timeout} s (first at index {bad[0]}): selector drift, see Gotchas")
            raise RuntimeError(f"no result cards for {url} within {timeout} s (tab is on {href}): {page_info()}")
        time.sleep(0.5)

url = "https://www.ulta.com/search?" + urllib.parse.urlencode({"search": QUERY})
tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
rows, seen, heading, next_url = [], set(), None, None
try:
    switch_tab(tab)
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            time.sleep(3)   # polite pacing between pages
        r = load(url)
        if r is None:
            print(f"no results for {QUERY!r}")
            next_url = None
            break
        heading = r["heading"]
        kept = 0
        for c in r["cards"]:
            row = parse(c)
            if (SKIP_SPONSORED and row["sponsored"]) or row["sku"] in seen:
                continue
            seen.add(row["sku"])
            rows.append(row)
            kept += 1
        print(f"page {page}: {len(r['cards'])} cards, {kept} kept, {len(rows)} total, heading {heading!r}")
        next_url = r["next"]
        if not next_url:
            break
        url = next_url   # the page's own "Load More" link: ...&page=N
finally:
    close_tab(tab)

complete = not next_url
if complete:
    print(f"COMPLETE: {len(rows)} rows, heading {heading!r}")
else:
    print(f"PARTIAL: stopped at MAX_PAGES={MAX_PAGES} with {len(rows)} rows; the page still has a "
          f"Load More link ({next_url}), heading {heading!r}. Raise MAX_PAGES to collect more.")
print(json.dumps(rows[:2], indent=1, ensure_ascii=False))
```

Observed output (trimmed):

```
page 1: 76 cards, 61 kept, 61 total, heading '400+ results for "mascara"'
page 2: 64 cards, 64 kept, 125 total, heading '400+ results for "mascara"'
page 3: 64 cards, 64 kept, 189 total, heading '400+ results for "mascara"'
PARTIAL: stopped at MAX_PAGES=3 with 189 rows; the page still has a Load More link (https://www.ulta.com/search?search=mascara&page=4), heading '400+ results for "mascara"'. Raise MAX_PAGES to collect more.
[
 {
  "product_id": "pimprod2020260",
  "sku": "2574523",
  "brand": "Maybelline",
  "name": "Lash Sensational Sky High Mascara",
  "price": "$12.99 - $13.99",
  "list_price": "$12.99 - $13.99",
  "on_sale": false,
  "price_value": 12.99,
  "rating": 4.5,
  "review_count": 11892,
  "variants": "9 colors",
  "sponsored": false,
  "tags": ["Free Gift with purchase"],
  "url": "https://www.ulta.com/p/lash-sensational-sky-high-mascara-pimprod2020260?sku=2574523"
 },
 ...
]
```

The search heading only says `400+`, so with a Load More link still present the block prints `PARTIAL` and sets `complete = False`; it does not guess a total. Earlier runs of the same query gave 73/73/64, 74/75/64, 74/73/64 (2026-10-23) and 74/77/64 and 77/64/64 cards (2026-10-24): the sponsored mix and the page 1 organic count vary between loads. On a freshly started browser the first search page took about 16 s before any card rendered, hence the 60 s wait in `load()`. `load()` returns a page only when every card has `sku`, a `/p/` link, `brand` and `name`; cards that never fill in within the 60 s raise (mocked offline: one card with `brand` missing raised after 60.5 s; a card whose `name` filled in on the 4th poll was accepted). It also checks the page for a bot challenge (title or first 500 characters of body text matching "Access Denied", "Just a moment", "Attention Required", "Pardon Our Interruption", or a captcha/challenge iframe) and raises `SystemExit` without retrying; no live page matched, the raise was checked with a mock. Other queries in the 2026-10-24 rerun: `"cushion foundation"` returned 16 cards, 16 kept, heading `16 results for "cushion foundation"`, no next link, `COMPLETE: 16 rows`; a sale card parsed as `"price": "$14.99", "list_price": "$19.99", "on_sale": true`. `"nars"` redirected to `https://www.ulta.com/brand/nars` (block 2 stops and points to block 1). `"zzqxv nonexistent"` redirected to `/search/no-results?...` and printed `no results`.

### 3. Product page details (plain HTTP, no browser)

```python
import json, re, subprocess, sys, time, urllib.parse

PRODUCT_URL = "https://www.ulta.com/p/double-wear-stay-in-place-longwear-matte-foundation-pimprod2057355?sku=2651970"   # any /p/... URL from block 1 or 2
UA = "browser-harness/1.0 (ulta domain skill; plain urllib)"

FETCH_CHILD = r"""
import gzip, json, sys, urllib.error, urllib.request
url, ua = sys.argv[1], sys.argv[2]
req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html", "Accept-Encoding": "gzip"})
try:
    with urllib.request.urlopen(req) as r:
        status, final, body, enc = r.status, r.geturl(), r.read(), r.headers.get("Content-Encoding")
except urllib.error.HTTPError as e:
    status, final, body, enc = e.code, e.geturl() or url, b"", None
if enc == "gzip":
    body = gzip.decompress(body)
sys.stdout.buffer.write(json.dumps({"status": status, "url": final}).encode() + b"\n" + body)
"""

def get_once(url, budget):
    """Same as block 1: one GET in a child process killed at `budget` s, so nothing outlives the call."""
    try:
        p = subprocess.run([sys.executable, "-I", "-c", FETCH_CHILD, url, UA], capture_output=True, timeout=budget)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"no complete response within {budget:.1f} s (request process killed)")
    if p.returncode != 0:
        raise ConnectionError((p.stderr.decode(errors="replace").strip().splitlines() or ["fetch failed"])[-1])
    head, _, body = p.stdout.partition(b"\n")
    meta = json.loads(head)
    return meta["status"], meta["url"], body

def fetch(url, deadline_s=120):
    """Same retry policy as block 1: one monotonic deadline across all tries and waits, no sleep after the last."""
    end, waits = time.monotonic() + deadline_s, [5, 15, 30]
    for attempt in range(len(waits) + 1):
        try:
            status, final_url, body = get_once(url, min(30, end - time.monotonic()))
        except (ConnectionError, TimeoutError) as e:
            err = repr(e)
        else:
            if status in (403, 429):
                raise SystemExit(f"HTTP {status} on {url}: Ulta is refusing or rate-limiting. Stop and back off.")
            if 400 <= status < 500:
                raise RuntimeError(f"HTTP {status} on {url}")
            if 300 <= status < 400:
                raise RuntimeError(f"HTTP {status} on {url}: unhandled redirect or not-modified, no body to parse")
            if 200 <= status < 300:
                got, want = urllib.parse.urlsplit(final_url), urllib.parse.urlsplit(url)
                if got.path != want.path or (want.query and urllib.parse.parse_qs(got.query) != urllib.parse.parse_qs(want.query)):
                    raise RuntimeError(f"asked for {url}, was redirected to {final_url}")
                return body.decode("utf-8")
            err = f"HTTP {status}"
        if attempt == len(waits) or time.monotonic() + waits[attempt] >= end:
            raise RuntimeError(f"giving up on {url} after {attempt + 1} tries: {err}")
        time.sleep(waits[attempt])

def md_unescape(s):
    """ProductDetail text is Markdown-escaped: 'Water\\\\Aqua' -> 'Water\\Aqua', 'Tocopherol \\[ May Contain' -> 'Tocopherol [ May Contain'."""
    return re.sub(r"\\(.)", r"\1", s) if s else s

def find(node, name):
    if isinstance(node, dict):
        if node.get("moduleName") == name:
            return node
        node = list(node.values())
    if isinstance(node, list):
        for v in node:
            hit = find(v, name)
            if hit:
                return hit
    return None

if not re.match(r"^https://www\.ulta\.com/p/[^?#]+$", PRODUCT_URL.split("?")[0]):
    raise SystemExit("PRODUCT_URL must be an https://www.ulta.com/p/... product URL")

html = fetch(PRODUCT_URL)
ld = {}
for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
    try:
        d = json.loads(block)
    except ValueError:
        continue
    ld.setdefault(d.get("@type"), d)
product, group, crumbs = ld.get("Product"), ld.get("ProductGroup") or {}, ld.get("BreadcrumbList") or {}
if not product:
    raise RuntimeError("no Product JSON-LD on the page (block page, removed product or layout change)")

for k in ("productID", "sku", "name", "offers"):
    if not product.get(k):
        raise RuntimeError(f"Product JSON-LD has no {k!r} (layout change): not accepting this page")
want_sku = urllib.parse.parse_qs(urllib.parse.urlsplit(PRODUCT_URL).query).get("sku", [None])[0]
if want_sku and str(product["sku"]) != want_sku:
    raise RuntimeError(f"asked for sku {want_sku}, page describes sku {product['sku']}")

m = re.search(r"window\.__APOLLO_STATE__ = (\{.*?\})\s*\n", html, re.S)
if not m:
    raise RuntimeError("no window.__APOLLO_STATE__ in the HTML (block page or layout change)")
state = json.loads(m.group(1))
pricing, detail = find(state, "ProductPricing"), find(state, "ProductDetail")
for name, mod in (("ProductPricing", pricing), ("ProductDetail", detail)):
    if not mod:
        raise RuntimeError(f"no {name} module in __APOLLO_STATE__ (layout change): not accepting partial details")

offer = product.get("offers") or {}
rating = product.get("aggregateRating") or {}
brand = product.get("brand")
info = {
    "product_id": product.get("productID"),
    "sku": product.get("sku"),
    "name": product.get("name"),
    "brand": brand.get("name") if isinstance(brand, dict) else brand,
    "variant": pricing.get("variantLabel") or product.get("Color"),
    "price": offer.get("price"),                   # current price of this sku, as a string ("52.00")
    "currency": offer.get("priceCurrency"),
    "list_price": pricing.get("listPrice"),
    "sale_price": pricing.get("salePrice"),
    "availability": (offer.get("availability") or "").rsplit("/", 1)[-1],
    "rating": rating.get("ratingValue"),
    "review_count": rating.get("reviewCount"),
    "questions_count": detail.get("questionsCount"),
    "gtin12": product.get("gtin12"),               # GTIN of the sku in the URL
    "category_path": [e["item"]["name"] for e in crumbs.get("itemListElement") or []][1:],
    "description": product.get("description"),
    "details_markdown": detail.get("description"),
    "how_to_use": detail.get("usage"),
    "ingredients": md_unescape(detail.get("ingredients")),   # raw value carries Markdown backslash escapes
    "attributes": {p["name"]: p["value"] for p in product.get("additionalProperty") or []
                   if p.get("name") != "Product Ingredients"},
    "images": product.get("image") or [],
    "variant_count": len(group.get("hasVariant") or []),
    "variants": [{"sku": v.get("sku"), "name": v.get("color") or v.get("name"),
                  "gtin12": v.get("gtin12"),     # None except on the product's default sku; for others fetch ?sku=<sku>, read top-level gtin12
                  "url": v.get("url")}
                 for v in group.get("hasVariant") or []],
    "url": offer.get("url") or PRODUCT_URL,
}
out = dict(info, variants=info["variants"][:3], details_markdown=(info["details_markdown"] or "")[:200],
           how_to_use=(info["how_to_use"] or "")[:120], ingredients=(info["ingredients"] or "")[:120])
print(json.dumps(out, indent=1, ensure_ascii=False))
```

Observed output (trimmed):

```
{
 "product_id": "pimprod2057355",
 "sku": "2651970",
 "name": "Double Wear Stay-in-Place Longwear Matte Foundation",
 "brand": "Estée Lauder",
 "variant": "0N1 Alabaster (lightest with neutral undertones)",
 "price": "52.00",
 "currency": "USD",
 "list_price": "$52.00",
 "sale_price": null,
 "availability": "InStock",
 "rating": 4.2,
 "review_count": 10242,
 "questions_count": 38,
 "gtin12": "887167494855",
 "category_path": ["Makeup", "Face", "Foundation"],
 "description": "Flawless, full-of-life matte. This buildable, breathable longwear foundation is made for more. ...",
 "details_markdown": "#### Research Results\n\n- 93% said it reduces the appearance of shine immediately* ...",
 "how_to_use": "SHAKE: Then dispense a fingertip amount---press once if you are using the pump.  \n\nDOT: ...",
 "ingredients": "Water\\Aqua\\Eau, Methyl Trimethicone, Dimethicone, Trimethylsiloxysilicate, Niacinamide, ...",
 "attributes": {"Face Coverage": ["Medium"], "Face Finish": ["Natural"], "Face Form": ["Liquid"], "Skin Type": ["Combination", "Dry", "Normal", "Oily", "Sensitive"]},
 "images": ["https://media.ulta.com/i/ulta/2651970?w=500&h=500", "..._alt01?w=500&h=500", ...],
 "variant_count": 57,
 "variants": [{"sku": "2651970", "name": "0N1 Alabaster", "gtin12": "887167494855", "url": "...?sku=2651970"},
              {"sku": "2651971", "name": "1C0 Shell", "gtin12": null, "url": "...?sku=2651971"},
              {"sku": "2651972", "name": "1C1 Cool Bone", "gtin12": null, "url": "...?sku=2651972"}],
 ...
}
```

The `ingredients` line above is JSON-printed, so `Water\\Aqua\\Eau` is one literal backslash each (`Water\Aqua\Eau`, as the site shows it). The raw `ProductDetail.ingredients` value had two (`Water\\Aqua\\Eau` in Python, four in JSON) because the text is Markdown-escaped; `md_unescape` strips one level. On the cushion foundation below, the same function turned `Tocopherol \[ May Contain: ...\]` into `Tocopherol [ May Contain: ...]`.

`gtin12` per variant: Double Wear had it on 1 of 57 `hasVariant` entries, Infallible Cushion on 1 of 20, in both cases the product's default sku. Fetching `?sku=2651971` returned top-level `"gtin12": "887167494251"` for that shade while its `hasVariant` entry stayed `null`. So a full GTIN list costs one product-page fetch per sku.

Same block on other product types, same run: a sale item (`infallible-cushion-foundation-pimprod2058959?sku=2656834`) gave `"price": "14.99", "list_price": "$19.99", "sale_price": "$14.99"`; an old numeric-ID item (`voluminous-original-washable-mascara-2641`) gave `"product_id": "2641"`; a marketplace item (`primelash-mascara-mkt77008704`) and a URL without `?sku=` (`radiant-creamy-concealer-xlsImpprod15251325`, default sku 2504450) both parsed. A made-up product URL returned HTTP 404 and the block raised. All of these, rerun on 2026-10-24, had `ProductPricing` and `ProductDetail` modules.

Block 3 refuses partial pages: it raises when the Product JSON-LD lacks `productID`, `sku`, `name` or `offers`, when `__APOLLO_STATE__` or its `ProductPricing` / `ProductDetail` module is missing, when the URL's `?sku=` differs from the page's `Product.sku`, or when a redirect changes the path (or, for a URL with a query, drops or changes that query). Each of those raises was checked offline with a mocked response; the live pages above passed all of them.

## Fields

| Field | Block 1 source (`ProductListingResults.items[]`) | Block 2 source (search card) | Block 3 source (product page) |
|---|---|---|---|
| product_id | `productId` | last `-` segment of the `/p/` URL path | JSON-LD `Product.productID` |
| sku | `skuId` | `li[data-sku-id]` | JSON-LD `Product.sku` |
| brand | `brandName` | `.pal-c-ProductCardBody--brandName` | JSON-LD `Product.brand` |
| name | `productName` | `.pal-c-ProductCardBody--title` | JSON-LD `Product.name` |
| price | `listPrice` / `salePrice` (`"$52.00"`, ranges like `"$27.50 - $55.00"`) | price box `.sr-only` "sale price $X" / "list price $Y", else visible span | JSON-LD `offers.price` (string, no `$`), `ProductPricing.listPrice` / `salePrice` |
| rating | `rating` (float, None for unrated) | `.pal-c-Ratings .sr-only` "4.5 out of 5 stars ; 11892 reviews" | JSON-LD `aggregateRating.ratingValue` |
| review_count | `reviewCount` | same sr-only label | JSON-LD `aggregateRating.reviewCount` |
| url | `action.url` | card `a[href*="/p/"]` | JSON-LD `offers.url` |
| variants | `variantLabel` ("57 colors") | `.pal-c-ProductCardHeader__variant` | JSON-LD `ProductGroup.hasVariant[]` (sku, color, url; `gtin12` only on the default sku, `null` on the rest) |
| gtin12 | n/a | n/a | JSON-LD `Product.gtin12` (the sku in the URL, present on both products tested) |
| ingredients | n/a | n/a | `ProductDetail.ingredients`, Markdown-escaped; block 3 unescapes it |
| sponsored | `sponsored` | tag text "Sponsored" | n/a |
| extras | `promoText`, `image.imageUrl`, `resultCount`, `pageSize` (64), `loadMoreUrl` | other tags ("Sale", "Only at Ulta", "Free Gift with purchase") | `availability`, breadcrumbs, `ProductDetail.description` / `usage` / `questionsCount`, `additionalProperty` attributes, images |

## Gotchas

- **Listing vs landing pages.** Top-level department URLs such as `/shop/skin-care` returned 200 but have no `ProductListingResults` module; block 1 raises and points you at the sitemap. Leaf categories (`/shop/makeup/face/foundation`) and `/brand/<slug>` pages have it.
- **Sort and filter params are not server-rendered.** `/shop/makeup/face/foundation?sort=price_low_to_high` returned 200 but without the listing module. Block 1 therefore accepts only bare listing URLs and pages with `?page=N`; sort the rows yourself.
- **Review counts drift between surfaces.** The same product showed 10236 reviews on the listing and 10242 on its product page within minutes (the listing data is cached). Use block 3 when the exact count matters.
- **Search pages carry sponsored cards.** Pages 1 and 2 of "mascara" usually had 13 to 15 cards tagged "Sponsored" mixed into the grid (74 and 75 cards total), page 3 had none; in the last two runs only page 1 had them (15 of 77, then 15 of 76), page 2 had 64 organic cards. Block 2 drops them by default (`SKIP_SPONSORED`). Listing pages fetched over HTTP had `sponsored: false` on every item observed.
- **Search redirects.** A brand-name query (`nars`) redirected to `/brand/nars`; a query with no matches redirected to `/search/no-results?search=...`. Block 2 checks `location.href` after every navigation and handles both. Multi-word queries are encoded with `urlencode` (`cushion+foundation`), which is also what the page shows in `location.href`.
- **Product IDs come in several shapes:** `pimprod2057355`, `xlsImpprod5770257`, `VP11362`, `mkt77008704` (marketplace sellers) and plain digits (`2641`). Do not filter on a `pimprod` prefix.
- **Unrated items.** 27 of 254 Foundation rows had no rating; search cards for unrated items have no ratings label, so `rating` and `review_count` are `None`.
- **Selector drift (block 2 is the fragile part).** Search cards are read through design-system class names: `.pal-c-ProductCardBody--brandName`, `--title`, `--price`, `.pal-c-Ratings`, `.pal-c-ProductCardHeader__variant`, `.pal-c-Tag__messageText`. No ARIA alternative carries those fields separately: on `/search?search=lipstick` (74 cards) there were 0 `[role="listitem"]` attributes, each card's only `aria-label` was `"product"` (a `role="group"` wrapper), and the card link's accessible name is brand and name run together (`"Maybelline Serum Lipstick"`), with no price or rating. `li[data-test="products-list-item"]`, `data-sku-id` and the `/p/` link are the steadier anchors. Failure signal after a redesign: `load()` raises "cards still lack sku/url/brand/name" after 60 s; re-inspect one card's classes then. `price` is not a required field (every card in this run had one), so check `price_value` for `None` yourself if you rely on it. Blocks 1 and 3 read embedded JSON and JSON-LD and do not depend on CSS.
- **Region.** Ulta is a US storefront. Every load in this run, from the cloud browser and from plain HTTP, stayed on `https://www.ulta.com/` with no geo redirect, `lang="en-US"`, prices in `$` and JSON-LD `priceCurrency` `USD`; no country or region selector was found on the search page. Behavior from non-US locations was not tested.
- **Consent banner.** In the browser a OneTrust cookie banner (`#onetrust-banner-sdk`, visible, about 88 px tall) rendered on load. It did not block reading the cards, so block 2 never clicks it. Plain HTTP responses are unaffected.
- **Lazy loading.** Search cards were all in the DOM once the first ones appeared; scrolling the page did not change the card count (74 before and after on page 1). Images inside cards use `loading="lazy"`, which does not affect the fields above.
- **Pacing.** None of the roughly 40 plain GETs and 25 browser page loads in this session (mostly 2 to 3 s apart) drew a 403, 429 or challenge page, so no rate limit was observed; that is not a promise of headroom. The 2026-10-24 reruns (32 plain GETs and 12 browser page loads) also drew none. The blocks sleep 3 s between pages and stop on 403/429 instead of retrying. HTTP retries share one 120 s monotonic deadline per URL: each try is a child Python process (`sys.executable -I -c FETCH_CHILD`) that is killed at min(30 s, time left), so DNS, connect, headers and the whole body read stop at the deadline even if a server trickles bytes, the socket closes with the process, and there is no sleep after the last try. An earlier version ran each try in a thread and only stopped waiting for it; against a trickling mock that left 2 abandoned requests still open after `fetch` raised. Mocked on localhost against both `fetch` copies of the current version: a refused port gave up after 4 tries and 50.7 s; a server sending 1 byte every 0.5 s gave up after 3 tries at 110.0 s (default deadline), and after 1 try at 12.0 s with `deadline_s=12`, for a trickled body and for trickled headers alike; after each of those, 0 child processes, 0 open server-side connections and 0 extra threads remained. A 503 was retried, a 404 raised, a 429 stopped, and a redirect to another path raised.
- **Page size.** Listing pages are 64 items; the last page holds the remainder and has `loadMoreUrl: null`. A page past the end (`?page=5` on a 4-page category) returned 200 with 0 items.

## What does not work

- **Search over plain HTTP.** `/search?search=mascara` returned 200 over urllib but its `ProductListingResults` module had no `items`, `resultCount` or `page`; the grid is filled client-side. Use block 2 (browser).
- **Sorted or filtered listings over plain HTTP** (see Gotchas): the server-rendered listing module is missing for `?sort=...`.
- **Department landing pages** (`/shop/skin-care`, `/shop/makeup`) have no product grid to scrape; use their subcategories.
