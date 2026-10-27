# Trulia — Listings Scraper (for-sale and rental search pages, listing key facts)

Field-tested against www.trulia.com on 2026-10-24 using a Browser Use cloud browser (plain HTTP was also tried and is blocked, see below).

robots.txt (fetched 2026-10-24) allows the paths used here for `User-agent: *`: `/{ST}/{City}/`, `/{ST}/{City}/{N}_p/`, `/for_rent/{City},{ST}/`, `/home/...`, `/building/...`; it disallows `/graphql`, `/_next`, `/search`, `/api/`, `/json/search`, and `/building/*_li` (any `/building/` URL with `_li` anywhere after it), so do not call those.

## Quick summary

- Every search and listing page is server-rendered with a Next.js `<script id="__NEXT_DATA__">` blob. Read it from the loaded page with `js(...)`, no CSS selectors needed.
- Search pages: `props.searchData.homes` has 40 listings per page, `props.searchData.totalHomes` the total (2026-10-24: San Francisco for-sale 1,041; Austin for-sale 5,634-5,636; San Francisco rentals 1,486-1,487, live totals move by a few within hours).
- Pagination is a path suffix: `/CA/San_Francisco/2_p/`, `/for_rent/San_Francisco,CA/2_p/`. Pages 1-3 had zero overlapping URLs (120 unique). Pagination links stop at page 25 (about 1,000 results per search).
- Listing pages (`/home/...` for sale, `/building/...` for rent) carry `props.homeDetails` (price, beds, baths, sqft, highlights, full "Home Details" table, last sale, floor plans) plus a JSON-LD `RealEstateListing`.
- Plain HTTP (`curl`/`http_get` with an honest UA) gets HTTP 403 from PerimeterX. Use the browser.
- The browser gets blocked too, and no pace was observed to be safe: a PerimeterX challenge at load 2 (~4 s gap), another at load 2 of a fresh browser after the code's own 15 s gap, another at load 16 of a session where every gap was 8 s or more, and a CloudFront 403 on the very first request of a fresh browser. The code below waits 15 s between loads, loads at most 12 pages per run, and on any block page (PerimeterX "Press & Hold" or CloudFront 403) stops at once and raises: no solving, no reload, no new browser or session.

## What works

### 1. Search results across pages (for sale or rent)

One run loads at most `MAX_LOADS` (12) pages, one load per page. Each page's rows are appended to `OUT` (JSON Lines, in the current directory) as soon as the page is parsed, so a block or error keeps every page already collected. Rows whose `url` is already in `OUT` are skipped, so re-reading a page on resume adds no duplicates. Every page is checked against `totalHomes`: a page before the last must hold 40 homes and the last page at least one, otherwise the run raises (a short or empty page is treated as a possible soft block, never as the end). Each page's number is appended to `PROGRESS` (`OUT` + `.pages`) once its rows are written, and the closing status is computed from that file across all runs, not from this run's page range: `COMPLETE` only when every page from 1 to the last is recorded, otherwise `PARTIAL` (prints how many pages are missing and the `START_PAGE` for the next run; resume hours later, not right away), plus `TRUNCATED` when results exceed the site's 25-page cap (a hard stop). A resumed file is stitched from runs hours apart, not one snapshot; delete `OUT` to start over (the code then discards the old `PROGRESS`).

```python
import json, math, os, time
from urllib.parse import quote, urlsplit

CITY, STATE = "Austin", "TX"   # any US city + 2-letter state
MODE = "sale"                  # "sale" or "rent"
START_PAGE = 1                 # first page of this run; set to the printed value to resume
PAGES = 2                      # pages this run, 1-MAX_LOADS; START_PAGE + PAGES - 1 must be <= 25
PAUSE_S = 15                   # gap between page loads (8 s gaps still got challenged)
MAX_LOADS = 12                 # page loads per run; a challenge came at load 16 with 8 s+ gaps
PER_PAGE = 40                  # homes on every page before the last (observed)
SITE_MAX_PAGE = 25             # the site links no page past 25; a hard stop
OUT = f"trulia_{STATE.lower()}_{CITY.lower().replace(' ', '_')}_{MODE}.jsonl"   # appended, one row per line
PROGRESS = OUT + ".pages"      # page numbers already written to OUT, one per line

if MODE not in ("sale", "rent"):
    raise ValueError("MODE must be 'sale' or 'rent'")
last_page = START_PAGE + PAGES - 1
if not 1 <= PAGES <= MAX_LOADS:
    raise ValueError(f"PAGES must be 1-{MAX_LOADS} per run; continue in a later run with START_PAGE")
if not 1 <= START_PAGE <= last_page <= SITE_MAX_PAGE:
    raise ValueError(f"pages must stay within 1-{SITE_MAX_PAGE}; pages past {SITE_MAX_PAGE} are not linked")

def search_url(city, state, mode, page):
    slug = quote(city.strip().replace(" ", "_"), safe="_-")
    base = (f"https://www.trulia.com/{state.upper()}/{slug}/" if mode == "sale"
            else f"https://www.trulia.com/for_rent/{slug},{state.upper()}/")
    return base if page == 1 else f"{base}{page}_p/"

def same_url(a, b):
    a, b = urlsplit(a), urlsplit(b)
    return (a.netloc, a.path.rstrip("/"), a.query) == (b.netloc, b.path.rstrip("/"), b.query)

def is_block_page(title):
    t = title.lower()
    return "denied" in t or "could not be satisfied" in t   # PerimeterX / CloudFront 403

_opened = []
def load_next_data(url):
    """One full page load. Raises on a redirect or a block page; never retries a challenge."""
    if _opened:
        goto_url(url)
    else:
        new_tab(url); _opened.append(url)
    wait_for_load()
    href = js("location.href")
    if not same_url(href, url):
        raise RuntimeError(f"redirected: wanted {url}, got {href}")
    raw = js("(document.getElementById('__NEXT_DATA__') || {}).textContent || ''")
    if raw:
        return json.loads(raw)["props"]
    title = js("document.title")
    if is_block_page(title):
        raise RuntimeError(f"blocked on {url} ({title}): stop, do not solve or reload, wait hours before the next run")
    raise RuntimeError(f"no __NEXT_DATA__ on {url}: {title}")

def val(d, *path):
    for p in path:
        d = d.get(p) if isinstance(d, dict) else None
    return d

def parse_home(h):
    price = h.get("price") or {}
    beds, baths = h.get("bedrooms") or {}, h.get("bathrooms") or {}
    row = {
        "address": val(h, "location", "fullLocation"),
        "price": price.get("formattedPrice"),
        "price_min": price.get("price", price.get("min")),
        "price_max": price.get("price", price.get("max")),
        "beds": beds.get("formattedValue"),
        "baths": baths.get("formattedValue"),
        "sqft": val(h, "floorSpace", "formattedDimension"),
        "type": h.get("__typename"),
        "url": "https://www.trulia.com" + h["url"] if h.get("url") else None,
    }
    missing = [k for k in ("address", "price", "url") if not row[k]]
    if missing:
        raise RuntimeError(f"listing card without {missing}: page shape changed, re-inspect __NEXT_DATA__")
    return row

seen, done = set(), set()
if os.path.exists(OUT):
    with open(OUT) as f:
        seen = {json.loads(line)["url"] for line in f if line.strip()}
    if os.path.exists(PROGRESS):
        with open(PROGRESS) as f:
            done = {int(line) for line in f if line.strip()}
elif os.path.exists(PROGRESS):
    os.remove(PROGRESS)   # OUT was deleted: start over

rows, skipped, total = [], 0, None
with open(OUT, "a") as f:
    for page in range(START_PAGE, last_page + 1):
        try:
            if page > START_PAGE:
                time.sleep(PAUSE_S)
            props = load_next_data(search_url(CITY, STATE, MODE, page))
            sd = props.get("searchData")
            if sd is None:
                raise RuntimeError("props.searchData missing: page shape changed, re-inspect __NEXT_DATA__")
            total, homes = sd.get("totalHomes"), sd.get("homes") or []
            if not isinstance(total, int):
                raise RuntimeError("searchData.totalHomes missing: page shape changed, re-inspect __NEXT_DATA__")
            end = min(SITE_MAX_PAGE, math.ceil(total / PER_PAGE))   # last page that has results
            if page > end:
                if homes:
                    raise RuntimeError(f"page {page}: {len(homes)} homes past the last page {end} (totalHomes={total})")
            elif not homes or (page < end and len(homes) != PER_PAGE):
                raise RuntimeError(f"page {page}: {len(homes)} homes, expected {PER_PAGE if page < end else '1+'} "
                                   f"(totalHomes={total}, last page {end}): short page, possibly a soft block")
            page_rows = [parse_home(h) for h in homes]
        except Exception:
            print(f"stopped at page {page}: {len(rows)} new rows from this run are in {OUT}; next run START_PAGE = {page}")
            raise
        if page > end:
            break
        new = [r for r in page_rows if r["url"] not in seen]
        seen.update(r["url"] for r in new)
        skipped += len(page_rows) - len(new)
        f.write("".join(json.dumps(r) + "\n" for r in new))
        f.flush()
        with open(PROGRESS, "a") as pf:
            pf.write(f"{page}\n")
        done.add(page)
        rows += new
        print(f"page {page}: {len(homes)} homes (totalHomes={total}), {len(new)} new rows appended to {OUT}")

end = min(SITE_MAX_PAGE, math.ceil(total / PER_PAGE))
cap = SITE_MAX_PAGE * PER_PAGE
not_read = [p for p in range(1, end + 1) if p not in done]   # from PROGRESS, all runs
print(f"{len(rows)} new rows this run, {skipped} skipped as already in {OUT}")
if not_read:
    print(f"PARTIAL: {len(not_read)} of {end} pages not read yet; next run START_PAGE = {not_read[0]}")
elif total <= cap:
    print(f"COMPLETE: all {end} result pages ({total} results) are in {OUT}")
if total > cap:
    print(f"TRUNCATED: the site links only {SITE_MAX_PAGE} pages, so at most {cap} of {total} results are reachable; this cap is a hard stop")
for r in rows[:2]:
    print(json.dumps(r))
```

Output (trimmed):

```text
page 1: 40 homes (totalHomes=5634), 40 new rows appended to trulia_tx_austin_sale.jsonl
page 2: 40 homes (totalHomes=5634), 40 new rows appended to trulia_tx_austin_sale.jsonl
80 new rows this run, 0 skipped as already in trulia_tx_austin_sale.jsonl
PARTIAL: 23 of 25 pages not read yet; next run START_PAGE = 3
TRUNCATED: the site links only 25 pages, so at most 1000 of 5634 results are reachable; this cap is a hard stop
{"address": "Cloverleaf 1657 Plan in Cloverleaf, Austin, TX 78747", "price": "$368,990+", "price_min": 368990, "price_max": null, "beds": "4 Beds", "baths": "2 Baths", "sqft": "1,657 sqft", "type": "HOME_FloorPlan", "url": "https://www.trulia.com/builder-community-plan/cloverleaf-cloverleaf-1657-402160607"}
{"address": "1900 Barton Springs Rd #2006, Austin, TX 78704", "price": "$419,000", "price_min": 419000, "price_max": 419000, "beds": "1 Bed", "baths": "1 Bath", "sqft": "887 sqft", "type": "HOME_Property", "url": "https://www.trulia.com/home/1900-barton-springs-rd-2006-austin-tx-78704-251032864"}
```

With `MODE = "rent"` and `CITY, STATE = "San Francisco", "CA"` rows look like:

```text
{"address": "1188 Mission St, San Francisco, CA 94103", "price": "$3,946 - $4,952/mo", "price_min": 3946, "price_max": 4952, "beds": "1 Bed", "baths": "1 Bath", "sqft": "450-688 sqft", "type": "HOME_RentalCommunity", "url": "https://www.trulia.com/building/1188-mission-at-trinity-place-..."}
```

### 2. One listing's key facts

Picks a live `/home/` URL from a search page first, because detail URLs go stale as homes sell.

```python
import json, time
from urllib.parse import urlsplit

SEARCH_URL = "https://www.trulia.com/CA/San_Francisco/"   # any for-sale search page
PAUSE_S = 15   # two page loads in total

def same_url(a, b):
    a, b = urlsplit(a), urlsplit(b)
    return (a.netloc, a.path.rstrip("/"), a.query) == (b.netloc, b.path.rstrip("/"), b.query)

def is_block_page(title):
    t = title.lower()
    return "denied" in t or "could not be satisfied" in t   # PerimeterX / CloudFront 403

_opened = []
def load(url):
    """One full page load. Raises on a redirect or a block page; returns (props, json_ld_list)."""
    if _opened:
        goto_url(url)
    else:
        new_tab(url); _opened.append(url)
    wait_for_load()
    href = js("location.href")
    if not same_url(href, url):
        raise RuntimeError(f"redirected: wanted {url}, got {href}")
    raw = js("(document.getElementById('__NEXT_DATA__') || {}).textContent || ''")
    if raw:
        lds = json.loads(js("JSON.stringify([...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(s => s.textContent))"))
        return json.loads(raw)["props"], [json.loads(s) for s in lds]
    title = js("document.title")
    if is_block_page(title):
        raise RuntimeError(f"blocked on {url} ({title}): stop, do not solve or reload, wait hours before the next run")
    raise RuntimeError(f"no __NEXT_DATA__ on {url}: {title}")

# 1) pick a live listing URL from a search page (detail URLs go stale when homes sell)
props, _ = load(SEARCH_URL)
homes = [h for h in (props.get("searchData") or {}).get("homes") or [] if (h.get("url") or "").startswith("/home/")]
if not homes:
    raise RuntimeError("no /home/ listings on the search page")
detail_url = "https://www.trulia.com" + homes[0]["url"]
time.sleep(PAUSE_S)

# 2) read the listing page
props, lds = load(detail_url)
hd = props.get("homeDetails")
if not hd:
    raise RuntimeError("props.homeDetails missing: page shape changed, re-inspect __NEXT_DATA__")
listing = next((d for d in lds if d.get("@type") == "RealEstateListing"), {})
me = listing.get("mainEntity") or {}

facts = {
    "url": detail_url,
    "address": (hd.get("location") or {}).get("homeFormattedAddress"),
    "neighborhood": (hd.get("location") or {}).get("neighborhoodName"),
    "status": (hd.get("currentStatus") or {}).get("label"),
    "price": (hd.get("price") or {}).get("formattedPrice"),
    "beds": (hd.get("bedrooms") or {}).get("formattedValue"),
    "baths": (hd.get("bathrooms") or {}).get("formattedValue"),
    "sqft": (hd.get("floorSpace") or {}).get("formattedDimension"),
    "lot": (hd.get("lotSize") or {}).get("formattedDimension"),
    "date_posted": listing.get("datePosted"),
    "geo": me.get("geo"),
    "photos": len(me.get("image") or []),
    "last_sold": {"price": ((hd.get("lastSold") or {}).get("soldPrice") or {}).get("formattedPrice"),
                  "date": (hd.get("lastSold") or {}).get("formattedSoldDate")},
    "highlights": {a["attribute"]["formattedName"]: a["attribute"]["formattedValue"]
                   for a in (hd.get("features") or {}).get("highlightedInfoAttributes") or []
                   if a.get("attribute")},
}
# full "Home Details" table: category -> subcategory -> name: value (agent contact block skipped)
details = {}
for cat in (hd.get("features") or {}).get("categories") or []:
    if cat.get("formattedName") == "Agent Information":
        continue
    for sub in cat.get("categories") or []:
        for a in sub.get("attributes") or []:
            if a.get("formattedName") and a.get("formattedValue"):
                details[f"{cat['formattedName']} / {sub['formattedName']} / {a['formattedName']}"] = a["formattedValue"]
facts["details_count"] = len(details)
missing = [k for k in ("address", "price", "status") if not facts[k]]
if missing:
    raise RuntimeError(f"listing page without {missing}: page shape changed, re-inspect __NEXT_DATA__")

print(json.dumps(facts, indent=1))
for k in list(details)[:12]:
    print(k, "=", details[k])
```

Output (trimmed):

```text
{
 "url": "https://www.trulia.com/home/355-chester-ave-san-francisco-ca-94132-15195820",
 "address": "355 Chester Ave, San Francisco, CA 94132",
 "neighborhood": "Ingleside Heights",
 "status": "For Sale",
 "price": "$910,000",
 "beds": "2 Beds",
 "baths": "1 Bath",
 "sqft": "1,100 sqft",
 "lot": null,
 "date_posted": "2026-10-24T23:51:23+00:00",
 "photos": 20,
 "last_sold": {"price": "$633,484", "date": "Jul 20, 2023"},
 "highlights": {"Property Type": "Single-Family Home", "Year Built": "1946", "Price/Sqft": "$827", "Parking": "1 Car Garage"},
 "details_count": 31
}
Interior Features / Beds & Baths / Number of Bedrooms = 2
Interior Features / Heating & Cooling / Heating = Central Forced Air,Fireplace(s)
Interior Features / Fireplace & Spa / Fireplace = Living Room, Wood Burning
```

### 3. Rental building floor plans

Rental search results are mostly buildings (`/building/...`). Their page has `homeDetails.floorPlans.floorPlanGroups[].plans[]` with per-plan price, beds, baths, sqft and availability.

```python
import json, time
from urllib.parse import urlsplit

RENT_SEARCH_URL = "https://www.trulia.com/for_rent/San_Francisco,CA/"
PAUSE_S = 15   # two page loads in total

def same_url(a, b):
    a, b = urlsplit(a), urlsplit(b)
    return (a.netloc, a.path.rstrip("/"), a.query) == (b.netloc, b.path.rstrip("/"), b.query)

def is_block_page(title):
    t = title.lower()
    return "denied" in t or "could not be satisfied" in t   # PerimeterX / CloudFront 403

_opened = []
def load(url):
    """One full page load. Raises on a redirect or a block page; returns props."""
    if _opened:
        goto_url(url)
    else:
        new_tab(url); _opened.append(url)
    wait_for_load()
    href = js("location.href")
    if not same_url(href, url):
        raise RuntimeError(f"redirected: wanted {url}, got {href}")
    raw = js("(document.getElementById('__NEXT_DATA__') || {}).textContent || ''")
    if raw:
        return json.loads(raw)["props"]
    title = js("document.title")
    if is_block_page(title):
        raise RuntimeError(f"blocked on {url} ({title}): stop, do not solve or reload, wait hours before the next run")
    raise RuntimeError(f"no __NEXT_DATA__ on {url}: {title}")

props = load(RENT_SEARCH_URL)
# robots.txt has "Disallow: /building/*_li", which matches "_li" anywhere after /building/
buildings = [h["url"] for h in (props.get("searchData") or {}).get("homes") or []
             if (h.get("url") or "").startswith("/building/") and "_li" not in h["url"]]
if not buildings:
    raise RuntimeError("no /building/ listings on the rent search page")
time.sleep(PAUSE_S)

url = "https://www.trulia.com" + buildings[0]
hd = load(url).get("homeDetails")
if not hd:
    raise RuntimeError("props.homeDetails missing: page shape changed, re-inspect __NEXT_DATA__")
address, price = (hd.get("location") or {}).get("homeFormattedAddress"), (hd.get("price") or {}).get("formattedPrice")
if not address or not price:
    raise RuntimeError("building page without address or price: page shape changed, re-inspect __NEXT_DATA__")
print(hd.get("name"), "|", address, "|", price)
plans = []
for g in ((hd.get("floorPlans") or {}).get("floorPlanGroups") or []):
    for p in g.get("plans") or []:
        plans.append({
            "group": g.get("title"),
            "plan": p.get("name"),
            "beds": (p.get("bedrooms") or {}).get("fullValue"),
            "baths": (p.get("bathrooms") or {}).get("fullValue"),
            "price": (p.get("priceRange") or {}).get("formattedPrice"),
            "sqft": (p.get("floorSpace") or {}).get("formattedDimension"),
            "availability": p.get("availabilityText"),
        })
print(len(plans), "plans")
for p in plans[:5]:
    print(json.dumps(p))
```

Output (trimmed):

```text
The Fitzgerald | 2095 Bryant St, San Francisco, CA 94110 | $5,450 - $5,750/mo
2 plans
{"group": "1 Bedroom (2 Floorplans, 2 Units)", "plan": "1BD, 1BTH E", "beds": "1 Bedroom", "baths": "1 Bathroom", "price": "$5,450", "sqft": "632 sqft", "availability": "Available Now"}
```

## Fields

Search card, `props.searchData.homes[i]`:

| Field | Path | Example |
|---|---|---|
| Address | `location.fullLocation` (also `streetAddress`, `city`, `stateCode`, `zipCode`, `coordinates`) | `355 Chester Ave, San Francisco, CA 94132` |
| Price text | `price.formattedPrice` | `$910,000`, `$3,946 - $4,952/mo`, `Contact for price` |
| Price number | `price.price` (`HOME_SinglePrice`) or `price.min` / `price.max` (`HOME_PriceRange`) | `910000` |
| Beds | `bedrooms.formattedValue`, `bedrooms.value` or `.min`/`.max` | `2 Beds`, `Studio-2 Beds` |
| Baths | `bathrooms.formattedValue` | `1 Bath`, `1-2 Baths` |
| Sqft | `floorSpace.formattedDimension` (can be null) | `1,100 sqft`, `450-688 sqft` |
| URL | `url` (relative) | `/home/...`, `/building/...`, `/builder-community-plan/...` |
| Kind | `__typename` | `HOME_Property`, `HOME_FloorPlan`, `HOME_RentalCommunity` |
| Status | `currentStatus.isActiveForSale` / `isActiveForRent` | `true` |
| Listed date | `activeListing.dateListed` | `2026-10-24T23:51:23+00:00` |
| Tags | `tags[].formattedName` | `NEW - 42 MIN AGO` |
| Extra | `tracking[]` key/value pairs: `zPID`, `listingNeighborhood`, `propertyType`, `listingPrice` | `single-family home` |
| Totals | `searchData.totalHomes` | `1041` |

Listing page, `props.homeDetails`: `price`, `bedrooms`, `bathrooms`, `floorSpace`, `lotSize`, `currentStatus.label`, `location.neighborhoodName`, `description.value` (free text written by the listing side that may contain agent names, phone numbers or emails, so the code does not output it), `features.highlightedInfoAttributes` (Property Type, Year Built, Price/Sqft, HOA, Parking), `features.categories` (31 name/value rows on the tested home), `lastSold.soldPrice` + `formattedSoldDate`, `floorPlans` (rentals), `metadata.typedHomeId` (`<zpid>_ZPID`). JSON-LD `RealEstateListing.mainEntity` adds `geo`, `image[]` (20 photo URLs on the tested home) and `datePosted`.

## Gotchas

- `wait_for_load()` is enough; the data is in the server HTML, not lazy-loaded. The visible cards past ~7 are lazy placeholders (`loading-property-card-N`), but `__NEXT_DATA__` already has all 40.
- Detect blocks by title, both keep `location.href` on the requested URL and have no `__NEXT_DATA__`: PerimeterX "Access to this page has been denied" (body: "Press & Hold to confirm you are a human") and CloudFront "ERROR: The request could not be satisfied" (body: "403 ERROR ... Request blocked"). The harness tab marker prefixes titles with an emoji, so match a substring.
- Pacing, as observed on 2026-10-24: ~4 s between loads got a challenge at load 2; a fresh browser running block 1 as written (15 s gap) got one at load 2; a session with every gap at 8 s or more got a challenge at load 16; a fresh browser got the CloudFront 403 on its first request and again after a 9-minute wait. So there is no known safe rate. The code uses 15 s gaps and at most 12 page loads per run. When it raises, stop the job and resume hours later (block 1 prints the `START_PAGE` to use); do not restart the browser, cycle sessions or switch IPs to clear the block.
- Pagination links stop at page 25 on both San Francisco searches (`1-40 of 1,486 Results` for rentals, 1,041 for sale), so one search yields at most ~1,000 results. Pages past 25 were not requested. Treat that cap as a hard stop: block 1 prints `TRUNCATED` when `totalHomes` exceeds it; do not reshape or split the search to get past it.
- Redirects: every URL that loaded in this run kept its exact `location.href`; no redirect was observed (a misspelled-city probe, `/TX/Austinn/`, was blocked before it resolved). The loaders raise on any mismatch of host, path or query string, so a wrong slug or a moved URL fails loudly instead of silently scraping another region. Build slugs the way the site's own links do: `/{ST}/{City_With_Underscores}/` and `/for_rent/{City_With_Underscores},{ST}/` (see the `uri` values in `secondaryNavigation`).
- Data-shape drift: `__NEXT_DATA__` is the page's internal Next.js state, not a public API. Paths such as `props.searchData.homes`, `props.homeDetails` and `__typename` values can change on any deploy. The code raises when `searchData`, `totalHomes` or `homeDetails` is missing, when a page holds fewer homes than `totalHomes` implies, or when a card or listing lacks address, price or URL; if that happens, print `js("Object.keys(JSON.parse(document.getElementById('__NEXT_DATA__').textContent).props)")` and re-map.
- Rentals: the page title counts units ("2,943 Rentals") while `totalHomes` counts buildings/listings (1,486). Prices are ranges with `min`/`max`; `HOME_EmptyPrice` means "Contact for price" (no number).
- For-sale results mix resale homes with new-construction floor plans (`HOME_FloorPlan`, price like `$368,990+`, `price.max` null). Filter on `__typename` if you only want resale.
- Personal data: search cards carry `activeListing.provider.listingAgent.name` and `broker.name`; listing pages have an "Agent Information" category in `features.categories` and agent names/phones in `lastSold.provider`, and the free-text `description.value` is written by the listing side. The code does not output any of them; keep personal contact data out of your output.
- Consent: a consent element exists in the DOM but rendered with height 0 in the US cloud browser, so nothing had to be dismissed.
- Do not switch to client-side navigation or the site's own XHR: it goes through `/graphql` and `/_next`, both disallowed by robots.txt. Full page loads only.

## What does not work

- Plain HTTP: `curl` with an honest UA against `/CA/San_Francisco/` and `/for_rent/San_Francisco,CA/` returned HTTP 403 with a PerimeterX "Access to this page has been denied" page. Changing the client identity to get past that is not allowed, so use the browser.
- `/graphql`, `/_next/data`, `/api/`, `/json/search`, `/search`: disallowed by robots.txt, not used.
- Rapid page loads (a few seconds apart) in the browser: PerimeterX "Press & Hold" challenge. Slower loads still got one: at load 16 with 8 s+ gaps, and at load 2 with a 15 s gap. The code raises on the first block page and never solves, reloads or retries it.
- Some browser sessions are refused outright: CloudFront `403 ERROR, The request could not be satisfied` on the first request, still there after a 9-minute wait. Nothing in this file gets past that; stop and try much later.
- Results past page 25 of a search: no links are offered; not requested.
