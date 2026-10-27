# Poshmark — Browse listings and extract title, brand, size, price, original price, URL

Field-tested against poshmark.com on 2026-10-24 using a Browser Use cloud browser and plain Python `urllib`.

robots.txt (fetched 2026-10-24) disallows `/search`, `/api`, `/listings` and `/users` for `User-agent: *`; everything below only requests `/brand/...` and `/category/...` browse pages, which it allows.

## Quick summary

- Brand and category browse pages (`/brand/Levi's-Women-Jeans`, `/category/Men-Shoes`) are server-rendered. Every page embeds `window.__INITIAL_STATE__` with 48 full listing objects, plus a JSON-LD `ItemList` with the 48 canonical listing URLs.
- Plain HTTP with an honest User-Agent returned HTTP 200 for every browse page tried (about 50 requests, 2 s apart, no 429, no captcha). No browser needed for the main task.
- Pagination is `?max_id=N` (N = page number). This is the URL the site's own "Next" button produces. With `sort_by=added_desc`, consecutive pages shared 0 to 2 IDs (new listings push rows onto the next page); the code de-duplicates by `id`.
- Filters are plain query params: `size[]=28`, `price[]=25-50`, `brand[]=Nike` (on category pages), `sort_by=...`, `availability=available`.
- Results are capped at 105 pages (about 5000 rows): `more.total` reports 5000 for any large result set. On `/brand/Levi's-Women-Jeans?sort_by=added_desc`, page 104 had `is_next_max_id_present: true`, page 105 had 48 rows and `false`, and pages 106, 107, 120 and 200 returned 0 rows. With the default sort, pages 106, 120 and 200 still returned 48 rows each (no overlap with page 105) but with `false`, and default-sort rows reshuffle between requests anyway. Treat the cap as a hard stop: stop when `has_next` is false, and when `total` is 5000 the code returns status `truncated_site_cap` instead of `complete`. Hitting your own `max_pages` while `has_next` is true returns `truncated_max_pages`.
- Keyword search lives under `/search`, which robots.txt disallows, so it was not requested. Use brand/category pages plus filters, then filter titles locally if you need keywords.

## What works

### 1. Plain HTTP, multi-page, with filters (main method)

```python
import gzip, json, math, re, socket, time, urllib.error, urllib.parse, urllib.request

UA = "poshmark-listing-export/1.0 (python-urllib; personal research script)"
BASE = "https://poshmark.com"
RETRYABLE = {429, 500, 502, 503, 504}
SITE_CAP_TOTAL = 5000   # more.total never exceeds this; has_next turns false at page 105
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(
    r"(?<![\w+])(?:\+[\s.-]?|00)[1-9](?:[\s.()-]{0,2}\d){6,14}(?!\d)"   # international: +44 20 7946 0958, 0049 30 123456
    r"|(?<![\w+])0[1-9](?:[\s.()-]?\d){8,11}(?!\d)"                     # national trunk 0: 020 7946 0958, 07700 900123
    r"|(?<!\d)(?:1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")  # North American: (555) 123-4567, 1-555-123-4567, 15551234567
ALLOWED_PATH = re.compile(r"(?:brand|category)/(?!\.\.?$)[^/?#\\]+")   # one segment under /brand or /category

def redact(text):
    """Titles are seller-written free text: mask any email address or phone number in them."""
    return PHONE.sub("[phone]", EMAIL.sub("[email]", text))

def read_body(r, deadline):
    """Read in chunks, each socket wait capped at the time left, so a server that trickles bytes cannot outlive the deadline."""
    sock, chunks = getattr(getattr(r.fp, "raw", None), "_sock", None), []
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("deadline passed while reading the response body")
        if sock is not None:
            sock.settimeout(min(30, left))
        chunk = r.read1(65536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)

def fetch(url, budget_s=120):
    """GET with capped exponential backoff under ONE deadline that also covers reading the body.
    Raises on 403/404 or when the budget is spent."""
    deadline, delay, attempt = time.monotonic() + min(budget_s, 120), 5, 0
    while True:
        attempt += 1
        remaining = deadline - time.monotonic()
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Encoding": "gzip", "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=max(0.1, min(30, remaining))) as r:
                body = read_body(r, deadline)
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return r.geturl(), body.decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code not in RETRYABLE:
                raise
            err = e
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError) as e:   # socket.timeout: Python < 3.10
            err = e
        if time.monotonic() + delay >= deadline:   # no sleep after the last attempt
            raise RuntimeError(f"giving up on {url} after {attempt} attempts: {err}")
        time.sleep(delay)
        delay *= 2

def browse_url(path, filters=None, page=1):
    """path: 'brand/<Brand>-<Dept>-<Category>' or 'category/<Dept>-<Category>' (both allowed by robots.txt).
    Anything else (e.g. 'search', which robots.txt disallows) raises before any request is made."""
    if not ALLOWED_PATH.fullmatch(path):
        raise ValueError(f"refusing {path!r}: only brand/<slug> and category/<slug> browse pages are allowed")
    q = list((filters or {}).items())
    if page > 1:
        q.append(("max_id", page))
    url = f"{BASE}/{urllib.parse.quote(path, safe='/-_')}"
    return url + ("?" + urllib.parse.urlencode(q, doseq=True) if q else "")

def parse_page(html):
    marker = "window.__INITIAL_STATE__="
    i = html.find(marker)
    if i < 0:
        raise RuntimeError("no __INITIAL_STATE__ in page (layout changed or not a listings page)")
    state = json.JSONDecoder().raw_decode(html, i + len(marker))[0]
    if state.get("showCaptcha"):
        raise RuntimeError("Poshmark served a captcha; stop and raise it to a human, do not retry")
    grid = next((v["gridData"] for k, v in state.items()
                 if k.startswith("$_") and isinstance(v, dict) and "gridData" in v), None)
    if grid is None:
        raise RuntimeError("no gridData module in __INITIAL_STATE__")
    def money(m):
        v = float((m or {}).get("val") or 0)
        return v if math.isfinite(v) and v > 0 else None   # 0.0 means "not set"; NaN/inf/negative rejected
    rows = []
    for it in grid.get("data") or []:
        bad = [f for f, ok in (("id", re.fullmatch(r"[0-9a-f]{24}", str(it.get("id") or ""))),
                               ("title", it.get("title")), ("price", money(it.get("price_amount"))))
               if not ok]
        if bad:
            raise RuntimeError(f"listing {it.get('id')!r} is missing {bad}; refusing the page")
        rows.append({
            "id": it["id"],
            "title": redact(it["title"]),
            "brand": it.get("brand"),
            "size": (it.get("size_obj") or {}).get("display_with_size_system") or it.get("size"),
            "price": money(it.get("price_amount")),
            "original_price": money(it.get("original_price_amount")),
            "currency": (it.get("price_amount") or {}).get("currency_code"),
            "department": (it.get("department") or {}).get("display"),
            "category": it.get("category"),
            "status": (it.get("inventory") or {}).get("status"),
            # ID-only permalink (301s to /listing/<Title-Slug>-<id>); the slug repeats the seller-written title.
            "url": f"{BASE}/listing/{it['id']}",
        })
    more = grid.get("more") or {}
    return rows, more.get("total"), bool(more.get("is_next_max_id_present"))

def same_url(a, b):
    """Same host, path and query (order and %-encoding ignored), so a redirect or a different page is never read."""
    pa, pb = urllib.parse.urlparse(a), urllib.parse.urlparse(b)
    q = lambda p: sorted(urllib.parse.parse_qsl(p.query, keep_blank_values=True))
    return (pa.netloc, urllib.parse.unquote(pa.path), q(pa)) == (pb.netloc, urllib.parse.unquote(pb.path), q(pb))

def scrape(path, filters=None, max_pages=3, pause_s=2.0):
    """Returns (rows, status). status is "complete", "truncated_max_pages" (more pages exist)
    or "truncated_site_cap" (Poshmark stopped paging at its ~5000-row cap; treat as a hard stop)."""
    seen, out = set(), []
    for page in range(1, max_pages + 1):
        url = browse_url(path, filters, page)
        final, html = fetch(url)
        if not same_url(final, url):
            raise RuntimeError(f"server sent us elsewhere: asked {url}, got {final}; "
                               "call scrape() again with that path if it is the page you want")
        rows, total, has_next = parse_page(html)
        if not rows and (has_next or total):
            raise RuntimeError(f"page {page} has 0 rows but total={total}, next={has_next}: {final}")
        new = [r for r in rows if r["id"] not in seen]
        seen.update(r["id"] for r in new)
        out.extend(new)
        print(f"page {page}: {len(rows)} rows, {len(new)} new, total={total}, next={has_next}")
        if not has_next:
            return out, ("truncated_site_cap" if (total or 0) >= SITE_CAP_TOTAL else "complete")
        if page == max_pages:
            return out, "truncated_max_pages"
        time.sleep(pause_s)

listings, status = scrape("brand/Levi's-Women-Jeans",
                          {"sort_by": "added_desc", "size[]": "28", "price[]": "25-50", "availability": "available"},
                          max_pages=3)
print(len(listings), "listings, status:", status)
for r in listings[:3]:
    print(json.dumps(r, ensure_ascii=False))

empty, status = scrape("brand/Zzqxnotabrand-Women-Jeans")
print(len(empty), "listings for an unknown brand, status:", status)

try:   # this slug 301s to a different canonical path, so scrape() refuses it and names the target
    scrape("brand/Lululemon_Athletica-Women-Pants", {"sort_by": "added_desc"}, max_pages=1)
except RuntimeError as e:
    print("refused:", e)

try:   # robots.txt disallows /search: refused locally, nothing is requested
    scrape("search", {"query": "levis"})
except ValueError as e:
    print("refused:", e)
```

Real output (trimmed):

```
page 1: 48 rows, 48 new, total=5000, next=True
page 2: 48 rows, 48 new, total=5000, next=True
page 3: 48 rows, 48 new, total=5000, next=True
144 listings, status: truncated_max_pages
{"id": "6add680c8925d3da8fdfd464", "title": "Levis | 712 Slim Fit 28 Distress Jeans", "brand": "Levi's", "size": "US 28", "price": 30.0, "original_price": 67.0, "currency": "USD", "department": "Women", "category": "Denim", "status": "available", "url": "https://poshmark.com/listing/6add680c8925d3da8fdfd464"}
...
page 1: 0 rows, 0 new, total=0, next=False
0 listings for an unknown brand, status: complete
refused: server sent us elsewhere: asked https://poshmark.com/brand/Lululemon_Athletica-Women-Pants?sort_by=added_desc, got https://poshmark.com/brand/lululemon_athletica-Women-Pants_&_Jumpsuits?sort_by=added_desc; call scrape() again with that path if it is the page you want
refused: refusing 'search': only brand/<slug> and category/<slug> browse pages are allowed
```

`truncated_max_pages` is expected here: `max_pages=3` stopped the run while `has_next` was still true.

A row with an original price set (from `brand/lululemon_athletica-Women-Pants_&_Jumpsuits` with `sort_by=added_desc`, where 23 of 96 rows on 2 pages had one):

```
{"id": "6add6586cbbea541a1f1443a", "title": "Lululemon License to Train High-Rise Pant Army Green Casual Women’s Active Small", "brand": "lululemon athletica", "size": "US S", "price": 85.0, "original_price": 128.0, "currency": "USD", "department": "Women", "category": "Pants", "status": "available", "url": "https://poshmark.com/listing/6add6586cbbea541a1f1443a"}
```

### 2. Same data from a browser tab (when you are already driving one)

The hydrated page keeps `window.__INITIAL_STATE__`, so the browser path reads the same JSON instead of scraping tiles. `open_page` only accepts `https://poshmark.com/brand/<slug>` and `/category/<slug>` URLs, waits until the tab is on exactly the requested URL (query included) and refuses a server redirect to a different path at once.

```python
import json, re, time, urllib.parse

ALLOWED_PATH = re.compile(r"/(?:brand|category)/(?!\.\.?$)[^/?#\\]+")   # robots.txt allows these; /search etc. are disallowed

EXTRACT = r"""(() => {
  if (document.querySelector('#px-captcha, iframe[src*="captcha"]')) return {error: 'challenge on page'};
  if (document.readyState !== 'complete') return {pending: 'readyState ' + document.readyState};
  const s = window.__INITIAL_STATE__;
  if (!s) return {pending: 'no __INITIAL_STATE__ yet'};
  if (s.showCaptcha) return {error: 'captcha'};
  const mod = Object.keys(s).find(k => k.startsWith('$_') && s[k] && s[k].gridData);
  if (!mod) return {pending: 'no gridData yet'};
  const g = s[mod].gridData, data = g.data || [];
  const money = m => { const v = parseFloat((m || {}).val || '0'); return Number.isFinite(v) && v > 0 ? v : null; };
  const bad = data.find(it => !/^[0-9a-f]{24}$/.test(it.id || '') || !it.title || !money(it.price_amount));
  if (bad) return {error: `listing ${bad.id} is missing id/title/price`};
  // Titles are seller-written free text: mask any email address or phone number.
  // Same patterns as the Python block: international (+44 ..., 0049 ...), national trunk 0, North American.
  const redact = t => t.replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, '[email]')
    .replace(/(?<![\w+])(?:\+[\s.-]?|00)[1-9](?:[\s.()-]{0,2}\d){6,14}(?!\d)|(?<![\w+])0[1-9](?:[\s.()-]?\d){8,11}(?!\d)|(?<!\d)(?:1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)/g, '[phone]');
  return {
    total: (g.more || {}).total, has_next: !!(g.more || {}).is_next_max_id_present,
    rows: data.map(it => ({
      id: it.id, title: redact(it.title), brand: it.brand,
      size: (it.size_obj || {}).display_with_size_system || it.size,
      price: money(it.price_amount), original_price: money(it.original_price_amount),
      // ID-only permalink (301s to /listing/<Title-Slug>-<id>); the slug repeats the seller-written title.
      url: location.origin + '/listing/' + it.id,
    })),
  };
})()"""

def same_url(a, b):
    """Same host, path and query (order and %-encoding ignored), so page N is never read as page N-1."""
    pa, pb = urllib.parse.urlparse(a), urllib.parse.urlparse(b)
    q = lambda p: sorted(urllib.parse.parse_qsl(p.query, keep_blank_values=True))
    return (pa.netloc, urllib.parse.unquote(pa.path), q(pa)) == (pb.netloc, urllib.parse.unquote(pb.path), q(pb))

def open_page(url, first=False, settle_s=20):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.netloc != "poshmark.com" or not ALLOWED_PATH.fullmatch(urllib.parse.unquote(u.path)):
        raise ValueError(f"refusing {url}: only https://poshmark.com/brand/<slug> and /category/<slug> pages are allowed")
    new_tab(url) if first else goto_url(url)
    wait_for_load()
    want = urllib.parse.urlparse(url)
    deadline, href, data = time.monotonic() + settle_s, None, None
    while time.monotonic() < deadline:       # one deadline for the URL and state to settle
        href = js("location.href") or ""
        got = urllib.parse.urlparse(href)
        if got.netloc == want.netloc and urllib.parse.unquote(got.path) != urllib.parse.unquote(want.path):
            # pagination only changes the query, so a different path on this host is a server redirect
            raise RuntimeError(f"redirected: asked {url}, got {href}; open that URL instead if it is the page you want")
        if same_url(href, url):
            data = js(EXTRACT)
            if data and data.get("error"):
                raise RuntimeError(f"extraction failed on {href}: {data['error']}")
            if data and "rows" in data:
                return data
        time.sleep(0.5)
    raise RuntimeError(f"page did not settle on {url}: href={href} state={data and data.get('pending')}")

MAX_PAGES, SITE_CAP_TOTAL = 3, 5000
base = "https://poshmark.com/category/Men-Shoes?" + urllib.parse.urlencode(
    {"brand[]": "Nike", "sort_by": "added_desc"})
results, seen, status = [], set(), None
for page in range(1, MAX_PAGES + 1):
    url = base + (f"&max_id={page}" if page > 1 else "")
    data = open_page(url, first=(page == 1))
    new = [r for r in data["rows"] if r["id"] not in seen]
    seen.update(r["id"] for r in new)
    results.extend(new)
    print(f"page {page}: {len(data['rows'])} rows, {len(new)} new, next={data['has_next']}")
    if not data["rows"] and (data["has_next"] or data["total"]):
        raise RuntimeError(f"page {page} has 0 rows but total={data['total']}, next={data['has_next']}")
    if not data["has_next"]:
        status = "truncated_site_cap" if (data["total"] or 0) >= SITE_CAP_TOTAL else "complete"
        break
    if page == MAX_PAGES:
        status = "truncated_max_pages"
        break
    time.sleep(2)
print(len(results), "listings, status:", status)
print(json.dumps(results[:2], indent=1, ensure_ascii=False))

time.sleep(2)
try:   # this slug 301s to a different canonical path, so open_page() refuses it and names the target
    open_page("https://poshmark.com/brand/Lululemon_Athletica-Women-Pants?sort_by=added_desc")
except RuntimeError as e:
    print("refused:", e)

try:   # robots.txt disallows /search: refused before the tab navigates
    open_page("https://poshmark.com/search?query=nike")
except ValueError as e:
    print("refused:", e)
```

Real output (trimmed):

```
page 1: 48 rows, 48 new, next=True
page 2: 48 rows, 48 new, next=True
page 3: 48 rows, 48 new, next=True
144 listings, status: truncated_max_pages
[
 {
  "id": "6add6e68441b19999eb53d55",
  "title": "Nike air force 1 certified lover boy",
  "brand": "Nike",
  "size": "US 12",
  "price": 89,
  "original_price": null,
  "url": "https://poshmark.com/listing/6add6e68441b19999eb53d55"
 },
 ...
]
refused: redirected: asked https://poshmark.com/brand/Lululemon_Athletica-Women-Pants?sort_by=added_desc, got https://poshmark.com/brand/lululemon_athletica-Women-Pants_&_Jumpsuits?sort_by=added_desc; open that URL instead if it is the page you want
refused: refusing https://poshmark.com/search?query=nike: only https://poshmark.com/brand/<slug> and /category/<slug> pages are allowed
```

## URL patterns and filters (all observed)

| Pattern | Result |
|---|---|
| `/brand/<Brand>` (e.g. `/brand/Patagonia`) | 200, 48 rows, all departments |
| `/brand/<Brand>-<Dept>-<Category>` (e.g. `/brand/Levi's-Women-Jeans`) | 200, 48 rows, module `$_brand` |
| `/category/<Dept>-<Category>` (e.g. `/category/Women-Jeans`, `/category/Men-Shoes`) | 200, 48 rows, module `$_category` |
| `?max_id=N` | page N (what the site's Next button generates) |
| `?sort_by=` | values seen in the sort radio inputs: `best_match`, `added_desc` (Just In), `price_desc`, `price_asc`, `price_drop`, `like_count`, `relevance_v2` |
| `?size[]=28` | size filter, repeatable |
| `?price[]=25-50` | price bucket from the Price filter ("$25 - $50"); click other buckets in the UI and copy the URL rather than guessing their format |
| `?brand[]=Nike` | brand filter on `/category/...` pages |
| `?availability=available` | added by the UI; rows had `inventory.status == "available"` |
| Unknown brand slug, or a filter with no matches (`/brand/Patagonia?size[]=ZZ999`) | 200 with 0 rows, `total: 0`, and JSON-LD `itemListElement: 0` (not a 404), so check for empty results |
| `/brand/Lululemon_Athletica-Women-Pants?sort_by=added_desc` | 301 to `/brand/lululemon_athletica-Women-Pants_&_Jumpsuits?sort_by=added_desc` (query kept). Both blocks refuse it because the path changed and print the target; call again with that path |
| `/listing/<id>` | 301 to the canonical `/listing/<Title-Slug>-<id>` URL |

## Fields

| Output field | Source in `gridData.data[i]` | Notes |
|---|---|---|
| `id` | `id` | 24-hex listing ID, also the last segment of the listing URL |
| `title` | `title` | seller-written, may contain Unicode quotes; email addresses and phone numbers (international `+44 ...` / `00..`, national `0...`, North American with or without a leading `1`) are replaced with `[email]` / `[phone]` |
| `brand` | `brand` | display name, e.g. `"lululemon athletica"` |
| `size` | `size_obj.display_with_size_system`, fallback `size` | e.g. `"US 28"`, or multi-system like `"US 11 / UK 10 / EUR 45 / cm 29"`; `size` alone is `"28"`, and can be `"Various"` |
| `price` | `price_amount.val` (string) | also integer `price` |
| `original_price` | `original_price_amount.val` | `"0.0"` when the seller left it blank, mapped to `None` |
| `currency` | `price_amount.currency_code` | `"USD"` on poshmark.com |
| `department` | `department.display` | `"Women"`, `"Men"`, ... |
| `category` | `category` | e.g. `"Denim"`, `"Pants"` |
| `status` | `inventory.status` | `"available"` |
| `url` | built from `id`: `https://poshmark.com/listing/<id>` | 301s to the canonical `/listing/<Title-Slug>-<id>`. The slug is left out because it repeats the seller-written title with spaces turned into `-` and punctuation dropped, so `redact` would not reliably catch contact details in it |
| (page) `total` | `gridData.more.total` | capped at 5000; `0` on an empty page |
| (page) `has_next` | `gridData.more.is_next_max_id_present` | false on the last page |

Each listing object also carries seller fields (`creator_username`, `creator_full_name`, `creator_picture_url`, ...). The code above deliberately does not copy them; leave them out unless you have a reason and a basis to process personal data.

## Gotchas

- `size[]`, `price[]`, `brand[]` need the brackets URL-encoded (`size%5B%5D=28`); `urllib.parse.urlencode` does this. Brand slugs with an apostrophe (`Levi's`) work encoded as `%27`, and `&` in category slugs (`Pants_&_Jumpsuits`) works as `%26`.
- Default sort (relevance) is not stable between requests: two fetches of page 2 of `/category/Women-Jeans` (one via `max_id=2`, one via the `next_max_id` token from page 1) returned 48 rows each with zero IDs in common. Use `sort_by=added_desc` for paging. New listings arrive constantly (page 2 of Levi's women's jeans covered about 40 minutes), so a listing can shift onto the next page; the code de-duplicates by `id`.
- `more.next_max_id` is an opaque `ENC_...` token; plain `max_id=N` worked for every page tested and is what the UI uses.
- `more.total` says 5000 even for narrow filters (`size[]=28&price[]=25-50`), so it means "5000 or more", not an exact count. Page 105 is the last page (`has_next: false`); see the Quick summary for what pages past it return.
- No consent banner or login wall appeared on browse pages in the cloud browser. `state.ipCountry` was `"US"` and `state.domain` was `"us"`; Poshmark has other country sites, so check `currency` if you run from elsewhere.
- In the browser, tile counts via `[data-et-name="listing"]` returned 144 for 48 listings, and `a[href^="/listing/"]` returned 96 (two links per tile). Read `__INITIAL_STATE__` for the rows instead of counting tiles.
- In the browser, the JSON-LD `<script type="application/ld+json">` blocks are absent from the live DOM after hydration (0 in a fresh cloud browser, while a same-origin refetch of the HTML had them). Neither block reads JSON-LD.
- Size filter buttons (`#size-28`) are hidden until the Size dropdown is opened, and the choice only applies after clicking Apply. Building the URL directly is simpler.
- Pacing: 2 s between pages was used throughout with no 429 or captcha. Keep at least that. On any 403 or `showCaptcha: true` the code raises; stop and hand it to a human, do not retry or change the request to get past it. `fetch` retries only 429/5xx/network errors, all under one 120 s deadline per URL that also bounds reading the body, with no sleep after the last attempt.
- Both blocks refuse, before any request, a path or URL that is not one segment under `/brand/` or `/category/` (so `/search`, `/api`, `/listings`, `/users` and `..` tricks never go out). They also refuse a page if the browser or server ended up on a different path or query than requested, if any listing lacks a 24-hex `id`, a `title` or a finite positive `price`, or if a page has 0 rows while `total` is nonzero or `has_next` is true.

## What does not work

- `/search`, `/api/...` and `/listings` are disallowed by robots.txt for `User-agent: *`, so they were not requested.
- There is no keyword parameter used on browse pages; to approximate keyword search, pick the closest brand/category, add filters, and match on `title` locally.
- Going past the result cap: with `sort_by=added_desc`, pages 106 and later return 0 rows. The cap is site-enforced; do not reshape or split the query to get around it. Report the result as truncated.
- Sold items: the UI's `availability=available` and every row observed were available listings; sold-listing scraping was not tested.
