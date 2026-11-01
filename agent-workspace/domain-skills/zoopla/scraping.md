# Zoopla - For-sale listings (area search pages and listing details)

Field-tested against www.zoopla.co.uk on 2026-11-01 using a Browser Use cloud browser, logged out (plain HTTP was also tried and is blocked, see below).

robots.txt (fetched 2026-11-01) allows `/for-sale/property/<area>/`, its `?pn=<n>` pages and `/for-sale/details/<id>/` for `User-agent: *`; it disallows `/search/`, `/*q=`, `/*?rpn=*`, `/*?qpn=`, `/*radius=`, `/api/*`, `/ajax`, `/graph`, `/*/details/map/*`, `*/details/print/`, `*/details/photos/`, `*/stations/`, `*/local-info/`, `/*/contact` and `/for-sale/<type>/auction/*`, so do not call those.

## Quick summary

- Zoopla is a Next.js App Router site. There is no `__NEXT_DATA__`; the page data is streamed in inline `<script>self.__next_f.push([1, "..."])</script>` tags (React Server Components "flight" rows). Read those script tags with `js(...)`, join the strings and parse the rows in Python. No CSS selectors needed.
- Search pages (`/for-sale/property/bristol/`, `/for-sale/property/london/islington/`, `/for-sale/property/bs8/`): one object holds `regularListingsFormatted` (25 listings per page), `featuredListingsFormatted` (3 paid slots), and `pagination` (`pageNumber`, `pageNumberMax`, `totalResults`).
- Pagination is `?pn=2`, `?pn=3` ... `pageNumberMax` never went past 40, so one search reaches at most 1,000 listings (Bristol: 3,643 results, `pageNumberMax` 40).
- Detail pages (`/for-sale/details/<id>/`) carry a `ListingData` object: price + qualifier, beds/baths/receptions, tenure, full postcode, agent branch, key features, price-drop dates, size, coordinates. A JSON-LD `RealEstateListing` has price, beds and baths too (no agent).
- Plain HTTP gets a Cloudflare "Just a moment..." page (HTTP 403), even for `robots.txt`. In the browser, 38 page loads at least 5 s apart got no challenge. The code stops at once on a challenge page and never solves, reloads or retries it.

## What works

### 1. Area search, across pages

One full page load per results page, 8 s apart. Each page is checked: the URL must not redirect, `pagination.pageNumber` must match the requested page, and every page before the last must hold 25 listings (a short or empty page raises as a possible soft block, never counts as the end). `scrape_area()` reports why it stopped: `last_page`, `max_pages` (your limit; more pages exist) or `zoopla_page_cap` (page 40 reached and `totalResults` is larger, a hard stop).

```python
import html, json, math, re, time
from urllib.parse import urlsplit

AREAS = [("bristol", 2), ("bs8", 10)]   # (area slug as in /for-sale/property/<slug>/, max pages this run)
PAUSE_S = 8                             # gap between page loads
PER_PAGE = 25                           # regular listings on every page before the last (observed)
SITE_MAX_PAGE = 40                      # pagination.pageNumberMax never exceeded 40 (1,000 listings)
BAD_SEGMENTS = {"stations", "local-info", "map", "add", "edit", "contact", "print", "photos"}   # robots.txt

def search_url(area, page):
    area = area.strip("/").lower()
    if not re.fullmatch(r"[a-z0-9-]+(/[a-z0-9-]+)*", area) or BAD_SEGMENTS & set(area.split("/")):
        raise ValueError(f"bad area slug {area!r}")
    base = f"https://www.zoopla.co.uk/for-sale/property/{area}/"
    return base if page == 1 else f"{base}?pn={page}"   # ?pn= is allowed; ?rpn= / ?qpn= / q= are not

def rsc_rows(flight):
    """Split a Next.js RSC flight string into {row_id: value}. 'T' rows are text with a hex byte length."""
    b, rows, pos = flight.encode("utf-8"), {}, 0
    row_re = re.compile(rb"([0-9a-f]+):")
    while pos < len(b):
        m = row_re.match(b, pos)
        if not m:
            nl = b.find(b"\n", pos)
            pos = len(b) if nl < 0 else nl + 1
            continue
        rid, pos = m.group(1).decode(), m.end()
        if b[pos:pos + 1] == b"T":
            comma = b.index(b",", pos)
            size = int(b[pos + 1:comma], 16)
            rows[rid] = b[comma + 1:comma + 1 + size].decode("utf-8", "replace")
            pos = comma + 1 + size
            continue
        nl = b.find(b"\n", pos)
        nl = len(b) if nl < 0 else nl
        body = b[pos:nl].decode("utf-8", "replace")
        pos = nl + 1
        try:
            rows[rid] = json.loads(body) if body[:1] in "[{" else body
        except ValueError:
            rows[rid] = body
    return rows

def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)

_opened = []
def load_flight(url):
    """One full page load -> parsed RSC rows. Raises on a redirect or a Cloudflare challenge; never retries one."""
    if _opened:
        goto_url(url)
    else:
        new_tab(url); _opened.append(url)
    wait_for_load()
    state = json.loads(js("JSON.stringify({href: location.href, title: document.title})"))
    if any(t in state["title"].lower() for t in ("just a moment", "attention required", "access denied")):
        raise RuntimeError(f"Cloudflare challenge on {url}: stop, do not solve or reload, wait hours before the next run")
    a, b = urlsplit(state["href"]), urlsplit(url)
    if (a.netloc, a.path, a.query) != (b.netloc, b.path, b.query):
        raise RuntimeError(f"redirected: wanted {url}, got {state['href']} (unknown area slugs redirect to /search/, which robots.txt disallows)")
    pushes = json.loads(js("JSON.stringify([...document.scripts].map(s => s.textContent).filter(t => t.startsWith('self.__next_f.push(')))"))
    parts = [json.loads(p[len("self.__next_f.push("):p.rindex(")")]) for p in pushes]
    return rsc_rows("".join(x[1] for x in parts if len(x) > 1 and isinstance(x[1], str)))

def search_data(rows):
    for v in rows.values():
        for o in walk(v):
            if isinstance(o.get("regularListingsFormatted"), list) and isinstance(o.get("pagination"), dict):
                return o
    raise RuntimeError("no regularListingsFormatted in the page's RSC data: page shape changed, re-inspect")

def deref(rows, v):
    """Resolve an RSC back-reference such as '$7d:props:featuredProperties:0:branch'."""
    if not (isinstance(v, str) and re.fullmatch(r"\$[0-9a-f]+(:[^:]+)*", v)):
        return v
    rid, *path = v[1:].split(":")
    o = rows.get(rid)
    for p in path:
        if isinstance(o, list) and o[:1] == ["$"] and p == "props":
            o = o[3]   # a React element row: ["$", type, key, props]
        elif isinstance(o, list):
            o = o[int(p)]
        elif isinstance(o, dict):
            o = o.get(p)
        else:
            return None
    return o

def to_row(rows, x):
    branch = deref(rows, x.get("branch")) or {}
    feats = {f.get("iconId"): f.get("content") for f in deref(rows, x.get("features")) or [] if isinstance(f, dict)}
    uri = (deref(rows, x.get("listingUris")) or {}).get("detail")
    row = {
        "id": x.get("listingId"),
        "address": x.get("address"),
        "price": x.get("priceUnformatted"),
        "price_text": " ".join(s for s in (x.get("priceTitle"), x.get("price")) if s),
        "beds": feats.get("bed"),
        "baths": feats.get("bath"),
        "receptions": feats.get("chair"),
        "sqft": feats.get("area"),
        "type": x.get("propertyType"),
        "title": x.get("title"),
        "agent": branch.get("name"),
        "branch_id": branch.get("branchId"),
        "listed": x.get("publishedOn"),
        "flag": x.get("flag"),
        "under_offer": x.get("underOffer"),
        "summary": html.unescape(x.get("summaryDescription") or ""),
        "url": "https://www.zoopla.co.uk" + uri if uri else None,
    }
    missing = [k for k in ("id", "address", "url") if not row[k]]
    if missing:
        raise RuntimeError(f"listing card without {missing}: page shape changed, re-inspect")
    return row

def scrape_area(area, max_pages):
    rows, seen, total, last, stopped = [], set(), None, None, "max_pages"
    for page in range(1, min(max_pages, SITE_MAX_PAGE) + 1):
        if page > 1:
            time.sleep(PAUSE_S)
        flight = load_flight(search_url(area, page))
        sd = search_data(flight)
        pg = sd["pagination"]
        if pg.get("pageNumber") != page:
            raise RuntimeError(f"asked for page {page}, page data says {pg.get('pageNumber')}")
        total, last = pg.get("totalResults"), pg.get("pageNumberMax")
        listings = sd["regularListingsFormatted"]
        if not listings or (page < last and len(listings) != PER_PAGE):
            raise RuntimeError(f"page {page}: {len(listings)} listings, expected {PER_PAGE if page < last else '1+'} (possible soft block)")
        for x in listings:
            r = to_row(flight, x)
            if r["id"] not in seen:
                seen.add(r["id"]); rows.append(r)
        if page >= last:
            stopped = "zoopla_page_cap" if total > last * PER_PAGE else "last_page"
            break
    return {"area": area, "total_results": total, "pages_max": last, "stopped": stopped, "rows": rows}

for i, (area, max_pages) in enumerate(AREAS):
    if i:
        time.sleep(PAUSE_S)
    res = scrape_area(area, max_pages)
    print(area, "| total", res["total_results"], "| pages", res["pages_max"], "| stopped", res["stopped"], "| rows", len(res["rows"]))
    for r in res["rows"][:2]:
        print(json.dumps({k: v for k, v in r.items() if k != "summary"}, ensure_ascii=False))
```

Output observed on 2026-11-01:

```text
bristol | total 3643 | pages 40 | stopped max_pages | rows 50
{"id": "71129298", "address": "\"The Gilder\" at Stillwell Road, Cribbs Causeway, Almondsbury, Bristol BS10", "price": 460000, "price_text": "£460,000", "beds": 4, "baths": null, "receptions": null, "sqft": null, "type": "semi_detached", "title": "4 bed semi-detached house for sale", "agent": "Bellway - Berwick Green", "branch_id": 159215, "listed": "30th Oct 2026", "flag": "Just added", "under_offer": false, "url": "https://www.zoopla.co.uk/new-homes/details/71129298/"}
{"id": "73091249", "address": "\"The Jeweller\" at Stillwell Road, Cribbs Causeway, Almondsbury, Bristol BS10", "price": 675000, "price_text": "£675,000", "beds": 4, "baths": null, "receptions": null, "sqft": null, "type": "detached", "title": "4 bed detached house for sale", "agent": "Bellway - Berwick Green", "branch_id": 159215, "listed": "30th Oct 2026", "flag": "Just added", "under_offer": false, "url": "https://www.zoopla.co.uk/new-homes/details/73091249/"}
bs8 | total 229 | pages 10 | stopped last_page | rows 229
{"id": "73753592", "address": "The Avenue, Clifton BS8", "price": 560000, "price_text": "£560,000", "beds": 3, "baths": 2, "receptions": 1, "sqft": 1094, "type": "flat", "title": "3 bed flat for sale", "agent": "Elephant Estate Agents, Bristol", "branch_id": 63847, "listed": "20th Jul 2026", "flag": "Back to market", "under_offer": false, "url": "https://www.zoopla.co.uk/for-sale/details/73753592/"}
{"id": "73215714", "address": "Oakfield Road, Clifton, Bristol BS8", "price": 429000, "price_text": "Guide price £429,000", "beds": 2, "baths": 2, "receptions": 1, "sqft": null, "type": "flat", "title": "2 bed flat for sale", "agent": "Howard", "branch_id": 104989, "listed": "18th May 2026", "flag": "Back to market", "under_offer": false, "url": "https://www.zoopla.co.uk/for-sale/details/73215714/"}
```

BS8 is a complete run: 10 pages, 229 unique rows = `totalResults` 229. The whole script took 106 s (12 page loads).

### 2. One listing's details

Picks live `/for-sale/details/` ids from a search page first (detail URLs go stale as homes sell), then reads each detail page. `get_listing()` returns `None` when Zoopla redirects the detail URL elsewhere (removed listing).

```python
import html, json, re, time
from urllib.parse import urlsplit

SEARCH_AREA = "bs8"   # any /for-sale/property/<slug>/ area; detail URLs go stale, so ids are picked live
PAUSE_S = 8           # gap between page loads

def rsc_rows(flight):
    """Split a Next.js RSC flight string into {row_id: value}. 'T' rows are text with a hex byte length."""
    b, rows, pos = flight.encode("utf-8"), {}, 0
    row_re = re.compile(rb"([0-9a-f]+):")
    while pos < len(b):
        m = row_re.match(b, pos)
        if not m:
            nl = b.find(b"\n", pos)
            pos = len(b) if nl < 0 else nl + 1
            continue
        rid, pos = m.group(1).decode(), m.end()
        if b[pos:pos + 1] == b"T":
            comma = b.index(b",", pos)
            size = int(b[pos + 1:comma], 16)
            rows[rid] = b[comma + 1:comma + 1 + size].decode("utf-8", "replace")
            pos = comma + 1 + size
            continue
        nl = b.find(b"\n", pos)
        nl = len(b) if nl < 0 else nl
        body = b[pos:nl].decode("utf-8", "replace")
        pos = nl + 1
        try:
            rows[rid] = json.loads(body) if body[:1] in "[{" else body
        except ValueError:
            rows[rid] = body
    return rows

def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)

_opened = []
def load_flight(url):
    """One full page load -> (final_url, RSC rows, JSON-LD list). Raises on a Cloudflare challenge; never retries one."""
    if _opened:
        goto_url(url)
    else:
        new_tab(url); _opened.append(url)
    wait_for_load()
    state = json.loads(js("JSON.stringify({href: location.href, title: document.title})"))
    if any(t in state["title"].lower() for t in ("just a moment", "attention required", "access denied")):
        raise RuntimeError(f"Cloudflare challenge on {url}: stop, do not solve or reload, wait hours before the next run")
    pushes = json.loads(js("JSON.stringify([...document.scripts].map(s => s.textContent).filter(t => t.startsWith('self.__next_f.push(')))"))
    parts = [json.loads(p[len("self.__next_f.push("):p.rindex(")")]) for p in pushes]
    lds = json.loads(js("JSON.stringify([...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(s => s.textContent))"))
    return state["href"], rsc_rows("".join(x[1] for x in parts if len(x) > 1 and isinstance(x[1], str))), [json.loads(s) for s in lds]

def d(x):
    return x if isinstance(x, dict) else {}

def get_listing(listing_id):
    """Detail page -> dict, or None when Zoopla redirects away (removed listing)."""
    url = f"https://www.zoopla.co.uk/for-sale/details/{listing_id}/"
    href, rows, lds = load_flight(url)
    if urlsplit(href).path != urlsplit(url).path:
        print(f"{listing_id}: redirected to {href}, listing not available")
        return None
    ld = next((x for x in lds if x.get("@type") == "RealEstateListing"), {})
    for v in rows.values():
        for o in walk(v):
            if o.get("__typename") == "ListingData" and isinstance(o.get("pricing"), dict) and isinstance(o.get("counts"), dict):
                break
        else:
            continue
        break
    else:
        raise RuntimeError(f"no ListingData in the RSC data of {url}: page shape changed, re-inspect")
    if str(o.get("listingId")) != str(listing_id):
        raise RuntimeError(f"asked for {listing_id}, page data is for {o.get('listingId')}")
    desc = o.get("detailedDescription")
    if isinstance(desc, str) and re.fullmatch(r"\$[0-9a-f]+", desc):
        desc = rows.get(desc[1:])   # long text sits in its own 'T' row
    at, pr, br, cnt = d(o.get("adTargeting")), d(o.get("pricing")), d(o.get("branchV2")), d(o.get("counts"))
    return {
        "id": o.get("listingId"),
        "url": url,
        "title": o.get("title"),
        "address": o.get("displayAddress"),
        "postcode": " ".join(x for x in (at.get("outcode"), at.get("incode")) if x),
        "price": pr.get("internalValue"),
        "price_text": " ".join(x for x in (pr.get("priceQualifierLabel"), pr.get("label")) if x),
        "ld_price": d(ld.get("offers")).get("price"),
        "beds": cnt.get("numBedrooms"),
        "baths": cnt.get("numBathrooms"),
        "receptions": cnt.get("numLivingRooms"),
        "type": o.get("propertyType"),
        "tenure": at.get("tenure"),
        "agent": br.get("branchName"),
        "branch_id": br.get("branchId"),
        "published": o.get("publishedOn"),
        "status": d(o.get("statusSummary")).get("label"),
        "size_sqft": d(o.get("ingested")).get("sizeSqft"),
        "size_source": d(o.get("ingested")).get("sizeSource"),
        "coords": d(d(o.get("location")).get("coordinates")),
        "key_features": [html.unescape(x) for x in d(o.get("features")).get("bullets") or [] if isinstance(x, str)],
        "price_changes": d(o.get("priceHistory")).get("priceChanges"),
        "description_chars": len(desc) if isinstance(desc, str) else None,
    }

# 1) pick live /for-sale/details/ ids from a search page
href, rows, _ = load_flight(f"https://www.zoopla.co.uk/for-sale/property/{SEARCH_AREA}/")
sd = next((o for v in rows.values() for o in walk(v) if isinstance(o.get("regularListingsFormatted"), list)), None)
if sd is None:
    raise RuntimeError(f"no search data on {href}")
ids = [x["listingId"] for x in sd["regularListingsFormatted"]
       if d(x.get("listingUris")).get("detail", "").startswith("/for-sale/details/")][:2]

# 2) read each detail page, plus one removed id
for lid in ids + ["1"]:
    time.sleep(PAUSE_S)
    item = get_listing(lid)
    if item:
        print(json.dumps(item, ensure_ascii=False))
```

Output observed on 2026-11-01:

```text
{"id": "73753592", "url": "https://www.zoopla.co.uk/for-sale/details/73753592/", "title": "3 bed flat for sale", "address": "The Avenue, Clifton BS8", "postcode": "BS8 3GE", "price": 560000, "price_text": "£560,000", "ld_price": 560000, "beds": 3, "baths": 2, "receptions": 1, "type": "flat", "tenure": null, "agent": "Elephant Estate Agents, Bristol", "branch_id": 63847, "published": "2026-07-20T08:43:30", "status": "Back to market", "size_sqft": 1094, "size_source": "structured_data", "coords": {"latitude": 51.465324, "longitude": -2.620291}, "key_features": ["Spacious three-bedroom Clifton apartment", "Private balcony with leafy outlook", "Designated gated parking space", "Three well-proportioned bedrooms", "Principal bedroom with en suite shower room", "Generous sitting and dining room", "Separate fitted kitchen with integrated appliances", "Beautifully maintained communal gardens", "Moments from The Downs", "Short walk to Clifton Village and Whiteladies Road"], "price_changes": null, "description_chars": 2552}
{"id": "73215714", "url": "https://www.zoopla.co.uk/for-sale/details/73215714/", "title": "2 bed flat for sale", "address": "Oakfield Road, Clifton, Bristol BS8", "postcode": "BS8 2BG", "price": 429000, "price_text": "Guide price £429,000", "ld_price": 429000, "beds": 2, "baths": 2, "receptions": 1, "type": "flat", "tenure": "leasehold", "agent": "Howard", "branch_id": 104989, "published": "2026-05-18T08:27:42", "status": "Back to market", "size_sqft": 979, "size_source": "comparables_epc", "coords": {"latitude": 51.461224, "longitude": -2.609827}, "key_features": ["A delightful and beautifully presented two double bedroom top floor flat", "Excellent location situated just off Whiteladies Road.", "Open plan living space with views from two elevations", "Principal bedroom with en-suite", "Generous second bedroom", "Open outlook to the rear over the covered reservoir", "Communal bike storeage", "No onward chain."], "price_changes": [{"isPriceDrop": true, "priceChangeDate": "2026-10-30T08:51:29"}], "description_chars": 2738}
1: redirected to https://www.zoopla.co.uk/overseas/, listing not available
```

## Fields

Search card, `regularListingsFormatted[i]`:

| Key | Source | Example |
|---|---|---|
| `id` | `listingId` (string) | `"73753592"` |
| `address` | `address` (street, area, outcode) | `"Oakfield Road, Clifton, Bristol BS8"` |
| `price` | `priceUnformatted` (int GBP) | `429000` |
| `price_text` | `priceTitle` + `price` | `"Guide price £429,000"`, `"Offers over £285,000"`, `"£560,000"` |
| `beds`, `baths`, `receptions`, `sqft` | `features[]` by `iconId`: `bed`, `bath`, `chair`, `area` | `2`, `2`, `1`, `485`; missing icons give `null` |
| `type`, `title` | `propertyType`, `title` | `"flat"`, `"2 bed flat for sale"` |
| `agent`, `branch_id` | `branch.name`, `branch.branchId` | `"Howard"`, `104989` |
| `listed` | `publishedOn` | `"18th May 2026"` (label in `publishedOnLabel`: "Listed on") |
| `flag`, `under_offer` | `flag`, `underOffer` | `"Just added"`, `"Back to market"`, `false` |
| `summary` | `summaryDescription`, HTML-unescaped | first ~150 chars of the description |
| `url` | `listingUris.detail` | `/for-sale/details/<id>/` or `/new-homes/details/<id>/` |

Also on each card: `pos.lat/lng`, `priceDrop`, `tags[].content` ("Freehold", "Chain free"), `displayType` (`standard`, `premium`, `premium_plus`), `image.src`, `gallery[]`, `numberOfImages`, `sizeSource`.

Detail page, `ListingData`:

| Key | Source | Example |
|---|---|---|
| `address`, `title`, `type` | `displayAddress`, `title`, `propertyType` | `"The Avenue, Clifton BS8"` |
| `postcode` | `adTargeting.outcode` + `adTargeting.incode` | `"BS8 3GE"` |
| `price`, `price_text` | `pricing.internalValue`, `pricing.priceQualifierLabel` + `pricing.label` | `429000`, `"Guide price £429,000"` |
| `ld_price` | JSON-LD `RealEstateListing.offers.price` | `429000` (matched `price` on both tested listings) |
| `beds`, `baths`, `receptions` | `counts.numBedrooms/numBathrooms/numLivingRooms` | `2`, `2`, `1` |
| `tenure` | `adTargeting.tenure` | `"leasehold"`, `"freehold"`, `null` |
| `agent`, `branch_id` | `branchV2.branchName`, `branchV2.branchId` | `"Howard"`, `104989` |
| `published`, `status` | `publishedOn`, `statusSummary.label` | `"2026-05-18T08:27:42"`, `"Back to market"` |
| `size_sqft`, `size_source` | `ingested.sizeSqft`, `ingested.sizeSource` | `979`, `"comparables_epc"` |
| `coords` | `location.coordinates` | `{"latitude": 51.46, "longitude": -2.61}` |
| `key_features` | `features.bullets`, HTML-unescaped | `["Principal bedroom with en-suite", ...]` |
| `price_changes` | `priceHistory.priceChanges` | `[{"isPriceDrop": true, "priceChangeDate": "2026-10-30T08:51:29"}]` (dates only, no old price) |
| `description_chars` | length of `detailedDescription` (HTML, often in its own `T` row) | `2738` |

Also in `ListingData`: `additionalNtsInfo` (water, heating, broadband, parking: mostly "Ask agent"), `epc.image`, `floorPlan.image`, `propertyImage[].filename` (photos at `https://lid.zoocdn.com/645/430/<filename>`), `adTargeting` (`priceMin/priceMax` band, `chainFree`, `listingCondition`, `regionName`).

## Gotchas

- **Reading the RSC rows.** Join the second element of every `self.__next_f.push([1, "..."])` call. Rows are `<hex id>:<json>\n`, except `T` rows: `<id>:T<hex byte length>,<text>` with no newline after the text, so `rsc_rows()` slices those by UTF-8 byte length. A naive split on newlines breaks on them.
- **Back-references.** Repeated objects are sent as strings like `"$7d:props:featuredProperties:0:branch"`. `featuredListingsFormatted` cards used them for `branch`, `features` and `listingUris`; `deref()` in block 1 resolves them. On a detail page the same `ListingData` appears several times; only one copy has dict-valued `pricing` and `counts`, which is the one block 2 reads.
- **`self.__next_f` is empty after hydration** (`length` 0 in this run). Read the inline script tags instead, as the code does.
- **Unknown area slugs redirect to `/search/?q=...`**, which robots.txt disallows (`/for-sale/property/notarealplace-xyz/` did). The loader raises on any redirect; take slugs from Zoopla's own links (breadcrumbs, the JSON-LD `BreadcrumbList`, or `seoAccordions` in the search data). Outcode slugs such as `bs8` and nested ones such as `london/islington` work.
- **Removed listing:** `/for-sale/details/1/` redirected (HTTP 200) to `/overseas/`. `get_listing()` returns `None` on any detail redirect.
- **Featured slots.** Each page also has 3 paid `featuredListingsFormatted` cards, not counted in `totalResults`. A featured card can repeat a regular one (BS8 page 1: 1 of 3 did; Bristol page 1: none). Block 1 returns regular cards only, which add up to `totalResults` (BS8: 229 = 229).
- **New homes in for-sale results.** Some regular cards link to `/new-homes/details/<id>/` (developer plots); they often have only a `bed` icon, so `baths` is `null`. Block 2 reads `/for-sale/details/` only.
- **Size can be an estimate.** `sizeSource` was `structured_data`, `text_derived`, `floorplan_derived`, `comparables_epc`, `comparables_survey` or missing; the `comparables_*` values are Zoopla estimates, not the agent's figure.
- **Do not pass `q=`, `radius=`, `search_source=facets`, `include_sold=` or `keywords=` parameters** (robots.txt), and do not call `/api/` or `/graph...` directly. Filters beyond the path were not used here.
- **Challenge check.** `window._cf_chl_opt` exists on normal pages too, so it is not a challenge signal; the code checks the title ("Just a moment", "Attention Required", "Access denied"). If it raises, stop the job and resume hours later. Do not restart the browser, cycle sessions or switch IPs.
- **Pacing.** 38 full page loads in one cloud browser session, at least 5 s apart (8 s inside the code), got no challenge. Keep 8 s between loads and do not run many in parallel.
- **Agent phone numbers** are in `branch.phone` / `branchV2.redirectPhone`; the code does not output them.
- **No clicks needed.** Nothing had to be dismissed or clicked to read the scripts.

## What does not work

- Plain HTTP: `curl` with an honest UA got HTTP 403 with a Cloudflare "Just a moment..." page for `/for-sale/property/bristol/` and for `/robots.txt`. Changing client identity to get past it is not allowed, so use the browser.
- `__NEXT_DATA__`: not present (App Router).
- More than 40 pages of one search: `pageNumberMax` stays at 40. Treat it as a hard stop; do not split or reshape the search to get past it.
- `/search/`, `/api/*`, `/graph`, map, print, photos and contact pages: disallowed by robots.txt, not used.
