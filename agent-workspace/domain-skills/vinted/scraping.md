# Vinted - Catalog search listings (title, price, brand, size, condition, URL)

Field-tested against www.vinted.com on 2026-10-31 using a Browser Use cloud browser (plain HTTP was also tried; results were inconsistent).

robots.txt (fetched 2026-10-31) for `User-agent: *` disallows `/checkout`, `/util`, `/apipie/`, `/admin_alert/new`, `/member/` (except about 10 specific `/member/<id>` pages) and `/inbox`, and allows everything else; this skill only loads `/catalog?search_text=...` pages. The same group sets `Content-Signal: ai-train=no, search=yes, ai-input=yes`, and the file's comments forbid using content for model training, fine-tuning, dataset creation or embedding, so use this for live lookups, not to build datasets.

## Quick summary

- **Plain HTTP is unreliable.** On 2026-10-31 `curl` got `403` for `/catalog?search_text=nike` in one test and `200` with the same payload in another; Python `urllib`'s default User-Agent got `403`, and `/api/v2/catalog/items` was `403` every time. Use the browser.
- **The rows are server-rendered.** `/catalog?search_text=<q>` is a Next.js App Router page. The search results ship inside the page's own `self.__next_f.push(...)` script tags as `"items":{"items":[...]}` followed by `"pagination":{...}`. The page does not call a catalog API after load, so the code reads those script tags instead of scraping tiles.
- **96 rows per page, `&page=N`** (the URL the site's own pager links to). `pagination` gives `current_page`, `per_page`, `total_entries`, `total_pages`.
- **Hard cap: 10 pages / 960 rows.** `nike`, `levis jeans`, `vintage dress`, `lego` and `handmade scarf` all reported `total_entries: 960, total_pages: 10`. `page=10` returned 96 rows; `page=11` returned 0 rows and no `pagination`. When `total_entries` is 960 the code returns `truncated_site_cap`.
- **Brand, size and condition are not separate JSON fields.** Each row has an `itemBox.accessibilityLabel` like `Nike sports tank, Brand: Nike, Condition: Very good, Size: S / US 4-6, 4.00 $, 4.90 $`. Brand and Size are omitted when the seller left them empty (81 of 384 sampled rows had no brand, 99 no size). The code parses that label and cross-checks it against the visible `itemBox.secondLine` (`S / US 4-6 · Very good`).
- No login wall, cookie wall or challenge appeared in about 45 page loads at 3 s or more spacing.

## What works

### 1. Browser, multi-page, with filters (main method)

```python
import json, math, re, time, urllib.parse

BASE = "https://www.vinted.com"
SITE_CAP_TOTAL = 960   # total_entries never exceeded 960 (10 pages x 96); page 11 returns 0 rows
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(
    r"(?<![\w+])(?:\+[\s.-]?|00)[1-9](?:[\s.()-]{0,2}\d){6,14}(?!\d)"   # international: +44 20 7946 0958
    r"|(?<!\d)(?:1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")  # North American: (555) 123-4567
# Label after the "<title>, " prefix. Brand and Size are left out when the seller did not set them.
LABEL = re.compile(r"(?:Brand: (?P<brand>.*?), )?Condition: (?P<condition>.*?), "
                   r"(?:Size: (?P<size>.*?), )?[\d.,]+ \$, [\d.,]+ \$")

EXTRACT = r"""(() => {
  if (document.querySelector('iframe[src*="captcha-delivery.com"]')) return {error: 'challenge on page'};
  if (document.readyState !== 'complete') return {pending: 'readyState ' + document.readyState};
  const P = 'self.__next_f.push(';
  const flight = [...document.scripts].map(s => s.textContent).filter(t => t.startsWith(P)).map(t => {
    try { const a = JSON.parse(t.slice(P.length, t.lastIndexOf(')'))); return typeof a[1] === 'string' ? a[1] : ''; }
    catch (e) { return ''; }
  }).join('');
  const key = '"items":{"items":[';
  const i = flight.indexOf(key);
  if (i < 0) return {pending: 'no catalog items in the page payload yet'};
  let j = i + key.length - 1, depth = 0, inStr = false, esc = false;   // find the matching ]
  for (; j < flight.length; j++) {
    const c = flight[j];
    if (inStr) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === '"') inStr = false; continue; }
    if (c === '"') inStr = true; else if (c === '[' || c === '{') depth++;
    else if (c === ']' || c === '}') { if (--depth === 0) break; }
  }
  const items = JSON.parse(flight.slice(i + key.length - 1, j + 1));
  const pg = flight.slice(j + 1, j + 400).match(/^,"pagination":(\{[^}]*\})/);
  return {
    pagination: pg ? JSON.parse(pg[1]) : null,
    rows: items.map(x => { const p = x.productItem || {}, b = p.itemBox || {};
      return {id: p.id, title: p.title, label: b.accessibilityLabel, second_line: b.secondLine,
              price: p.price, discounted: p.priceWithDiscount, total: p.totalItemPrice, promoted: !!p.isPromoted}; }),
  };
})()"""

def redact(text):
    """Titles are seller-written free text: mask any email address or phone number in them."""
    return PHONE.sub("[phone]", EMAIL.sub("[email]", text))

def money(m):
    try:
        v = float((m or {}).get("amount") or 0)
    except ValueError:
        return None
    return v if math.isfinite(v) and v > 0 else None

def parse_row(r):
    if not isinstance(r["id"], int) or not r["title"] or money(r["price"]) is None:
        raise RuntimeError(f"row {r['id']!r} is missing id/title/price; refusing the page")
    prefix = r["title"] + ", "
    m = LABEL.fullmatch(r["label"][len(prefix):]) if (r["label"] or "").startswith(prefix) else None
    if not m:
        raise RuntimeError(f"row {r['id']}: unexpected label {r['label']!r}")
    size, condition = m["size"], m["condition"]
    if r["second_line"] != " · ".join(x for x in (size, condition) if x):   # what the tile shows
        raise RuntimeError(f"row {r['id']}: label and tile disagree: {r['label']!r} vs {r['second_line']!r}")
    return {
        "id": r["id"],
        "title": redact(r["title"]),
        "brand": m["brand"],
        "size": size,
        "condition": condition,
        "price": money(r["price"]),
        "discounted_price": money(r["discounted"]),
        "total_price": money(r["total"]),           # price + buyer protection fee, as the tile shows
        "currency": r["price"].get("currencyCode"),
        "promoted": r["promoted"],
        # ID-only permalink; it redirects to /items/<id>-<title-slug>, and the slug repeats the seller-written title.
        "url": f"{BASE}/items/{r['id']}",
    }

def same_url(a, b):
    """Same host, path and query (order and %-encoding ignored), so page N is never read as page N-1."""
    pa, pb = urllib.parse.urlparse(a), urllib.parse.urlparse(b)
    q = lambda p: sorted(urllib.parse.parse_qsl(p.query, keep_blank_values=True))
    return (pa.netloc, urllib.parse.unquote(pa.path), q(pa)) == (pb.netloc, urllib.parse.unquote(pb.path), q(pb))

_tab = {"open": False}

def open_page(url, settle_s=25):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.netloc != "www.vinted.com" or u.path != "/catalog":
        raise ValueError(f"refusing {url}: only https://www.vinted.com/catalog?... pages are used")
    goto_url(url) if _tab["open"] else new_tab(url)
    _tab["open"] = True
    wait_for_load()
    deadline, href, data = time.monotonic() + settle_s, None, None
    while time.monotonic() < deadline:   # one deadline for the URL and the payload to settle
        href = js("location.href") or ""
        if same_url(href, url):
            data = js(EXTRACT)
            if data and data.get("error"):
                raise RuntimeError(f"{data['error']} on {href}: stop, do not retry or change the request")
            if data and "rows" in data:
                return data
        time.sleep(0.5)
    raise RuntimeError(f"page did not settle on {url}: href={href} state={data and data.get('pending')}")

def search(query, filters=None, max_pages=3, pause_s=3.0):
    """Returns (rows, status). status is "complete", "truncated_max_pages" (more pages exist)
    or "truncated_site_cap" (Vinted stops at 10 pages / 960 rows; treat as a hard stop)."""
    seen, out = set(), []
    for page in range(1, max_pages + 1):
        q = [("search_text", query)] + list((filters or {}).items()) + ([("page", page)] if page > 1 else [])
        data = open_page(f"{BASE}/catalog?" + urllib.parse.urlencode(q, doseq=True))
        pg = data["pagination"] or {}
        rows = [parse_row(r) for r in data["rows"]]
        if not rows and pg.get("total_entries"):
            raise RuntimeError(f"page {page} has 0 rows but total_entries={pg.get('total_entries')}")
        new = [r for r in rows if r["id"] not in seen]
        seen.update(r["id"] for r in new)
        out.extend(new)
        print(f"page {page}: {len(rows)} rows, {len(new)} new, total_entries={pg.get('total_entries')}, "
              f"total_pages={pg.get('total_pages')}")
        if page >= (pg.get("total_pages") or 0):
            return out, ("truncated_site_cap" if (pg.get("total_entries") or 0) >= SITE_CAP_TOTAL else "complete")
        if page == max_pages:
            return out, "truncated_max_pages"
        time.sleep(pause_s)

listings, status = search("nike", max_pages=3)
print(len(listings), "listings, status:", status)
for r in listings[:2]:
    print(json.dumps(r, ensure_ascii=False))

time.sleep(3)   # filters exactly as the site's own filter UI writes them into the URL
listings, status = search("levis jeans", {"order": "newest_first", "status_ids[]": "6",
                                          "price_to": "30", "currency": "USD"}, max_pages=1)
print(len(listings), "listings, status:", status,
      "| conditions:", sorted({r["condition"] for r in listings}),
      "| max price:", max(r["price"] for r in listings))

time.sleep(3)
listings, status = search("vintage dress", max_pages=1)
no_brand = [r for r in listings if r["brand"] is None]
print(len(listings), "listings,", len(no_brand), "without a brand")
print(json.dumps(no_brand[0] if no_brand else None, ensure_ascii=False))

time.sleep(3)
empty, status = search("zzqxqvnotathing")
print(len(empty), "listings for a nonsense query, status:", status)

try:   # robots.txt disallows /member/: refused before the tab navigates
    open_page("https://www.vinted.com/member/12345")
except ValueError as e:
    print("refused:", e)
```

Real output (trimmed):

```
page 1: 96 rows, 96 new, total_entries=960, total_pages=10
page 2: 96 rows, 89 new, total_entries=960, total_pages=10
page 3: 96 rows, 84 new, total_entries=960, total_pages=10
269 listings, status: truncated_max_pages
{"id": 10611858188, "title": "Nike Zip", "brand": "Nike", "size": "M / US 8-10", "condition": "Good", "price": 4.0, "discounted_price": null, "total_price": 4.9, "currency": "USD", "promoted": false, "url": "https://www.vinted.com/items/10611858188"}
{"id": 10611815068, "title": "Nike Dri-Fit Tshirt", "brand": "Nike", "size": "M", "condition": "Very good", "price": 5.0, "discounted_price": null, "total_price": 5.95, "currency": "USD", "promoted": true, "url": "https://www.vinted.com/items/10611815068"}
page 1: 96 rows, 96 new, total_entries=960, total_pages=10
96 listings, status: truncated_max_pages | conditions: ['New with tags'] | max price: 30.0
page 1: 96 rows, 96 new, total_entries=960, total_pages=10
96 listings, 23 without a brand
{"id": 10610445929, "title": "True vintage handmade dress", "brand": null, "size": "XXS / US 0", "condition": "Very good", "price": 10.0, "discounted_price": null, "total_price": 11.2, "currency": "USD", "promoted": false, "url": "https://www.vinted.com/items/10610445929"}
page 1: 0 rows, 0 new, total_entries=0, total_pages=1
0 listings for a nonsense query, status: complete
refused: refusing https://www.vinted.com/member/12345: only https://www.vinted.com/catalog?... pages are used
```

`truncated_max_pages` is expected for `nike`: `max_pages=3` stopped while 7 more pages existed.

## URL patterns and filters (all observed)

| Pattern | Result |
|---|---|
| `/catalog?search_text=<q>` | 200 in the browser, 96 rows, `pagination.current_page: 1` |
| `&page=N` | page N (the pager's own links). `page=10` had 96 rows, `page=11` 0 rows and no `pagination` |
| `&order=` | Sort by dropdown values: `relevance`, `price_high_to_low`, `price_low_to_high`, `newest_first` |
| `&status_ids[]=` | Condition filter: `6` New with tags, `1` New without tags, `2` Very good, `3` Good, `4` Satisfactory. With `status_ids[]=6` all 96 rows were "New with tags" |
| `&price_from=` / `&price_to=` + `&currency=USD` | Price filter; the UI adds `currency=USD`. With `price_to=30` no row was above $30 |
| `&time=<unix seconds>` | Added by the UI when a filter or sort changes; not needed for direct loads |
| `/catalog?search_text=<nonsense>` | 0 rows, `total_entries: 0, total_pages: 1` (not an error page) |
| `/items/<id>` | redirects to `/items/<id>-<title-slug>` |

Size, Brand, Color, Material and Category filters also exist in the UI (`catalog--size-filter--trigger`, etc.); pick them in the UI and copy the URL rather than guessing their ids.

## Fields

| Output field | Source in each `items.items[i].productItem` | Notes |
|---|---|---|
| `id` | `id` | integer, also the number in the item URL |
| `title` | `title` | seller-written; email addresses and phone numbers are replaced with `[email]` / `[phone]` |
| `brand` | `itemBox.accessibilityLabel` `Brand: ...` | `None` when the seller set no brand (then `itemBox.firstLine` is the title, not a brand, so do not read brand from it) |
| `size` | label `Size: ...` | e.g. `S / US 4-6`, `24M \| 2T/2`, `Other`; `None` for bags, toys and other unsized items |
| `condition` | label `Condition: ...` | `New with tags`, `New without tags`, `Very good`, `Good`, `Satisfactory` |
| `price` | `price.amount` (string) | item price the seller set |
| `discounted_price` | `priceWithDiscount.amount` | `null` on all 384 sampled rows |
| `total_price` | `totalItemPrice.amount` | price plus buyer protection fee (the tile's "incl." price) |
| `currency` | `price.currencyCode` | `USD` on www.vinted.com |
| `promoted` | `isPromoted` | 87 of 384 sampled rows were promoted ("bumped") listings mixed into the results |
| `url` | built from `id`: `https://www.vinted.com/items/<id>` | redirects to the canonical slug URL; the slug repeats the seller-written title, so it is left out |
| (page) `total_entries`, `total_pages` | `"pagination"` right after the items array | capped at 960 / 10 |

Each row also carries `user.id` (the seller), photos and a search score. The code does not copy the seller id; leave it out unless you have a reason and a basis to process personal data.

## Gotchas

- `window.__next_f` is empty after hydration (its `.map` returned nothing); read the `self.__next_f.push(...)` script tags instead, as `EXTRACT` does.
- The label format is English and `$`-specific; this skill covers www.vinted.com only. Other Vinted domains (vinted.fr, vinted.co.uk, ...) have their own robots.txt, language and currency and were not tested.
- Every query tried reported `total_entries: 960`, so 960 means "960 or more", not an exact count. Do not split or reshape the query to get past the cap; report the result as truncated.
- Pages overlap. With the default sort, consecutive `nike` pages shared 7 to 12 ids (one check: 11 shared between pages 1 and 2, only 2 of them promoted), so new listings and reshuffling push rows forward. The code de-duplicates by `id`, which is why 3 pages gave 269 rows (264 on a re-run), not 288.
- Promoted ("bumped") rows sit inside the normal result order (28 of 96 on each of two `nike` pages); filter on `promoted` if you want organic rows only.
- `EXTRACT` returns `error` on a DataDome challenge frame (`captcha-delivery.com`); the code raises and you should stop and hand it to a human, not retry or change anything to get past it. None appeared during testing at 3 s between pages.
- The code refuses any URL other than `https://www.vinted.com/catalog?...` before navigating, refuses a page whose URL differs from the one requested, and refuses a row whose label and tile text disagree.

## What does not work

- Plain HTTP: `/api/v2/catalog/items` and `urllib` on `/catalog` got 403; `curl` on `/catalog` was 403 or 200 depending on the run, so it is not a dependable path.
- Pages past 10: 0 rows.
- `/member/` profile pages are disallowed by robots.txt for `User-agent: *` and were not requested.
