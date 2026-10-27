# Apartments.com — Rental listings and floor plans

Field-tested against www.apartments.com on 2026-10-23 using a Browser Use cloud browser.

robots.txt (checked 2026-10-23 in the browser) allows the city search pages (`/austin-tx/`, `/austin-tx/2/`) and property pages this skill uses for all user agents; it disallows only `/mymedia/` and a few query parameters (`?ssk`, `?gclid`, `?rs`, ...).

## Quick summary

- Plain HTTP is blocked (status 403 "Access Denied" from the Akamai edge, `/robots.txt` included); this skill uses a normal browser session.
- In a browser, logged out, city search pages render fully server-side: **40 property cards per page**, no consent banner, no scrolling needed. Pagination is plain URLs: `/austin-tx/`, `/austin-tx/2/`, ... `/austin-tx/18/`.
- Every search is capped at **700 results = 18 pages** (17 x 40 + 20), even when the title says "27,813 Rentals". Asking for `/austin-tx/19/` redirects to page 1. The skill reads what the site serves and stops there.
- Each card carries a `data-listing-share-lines` JSON array (street, city line, beds, baths, rent) plus a phone in `phone-data`. The code keeps the phone only for non-single-home tiers (see "Personal data"). Card amenities only exist on some ad tiers.
- Property pages have a JSON-LD `RealEstateListing` node (phone, address, geo, rent low/high, rating, amenities, pets) and a server-rendered floor-plan grid with every unit, its base rent and total monthly price.
- The CDN blocks the whole browser session after sustained crawling. Observed: about 40 page loads plus same-origin `fetch()` calls in 25 minutes, then every request (pages and fetch) returned "Access Denied". Keep at least 5 s between page loads and stop on the first "Access Denied".

## What works

### 1. City search, 2+ pages of listings

Runs as-is with browser-harness helpers. Change `CITY` to any slug the site uses in its own URLs.

`open_page` only returns once the tab's own URL is the requested page and the document is complete and rendered, so it never parses the previous page. (A fresh tab once reported the right URL and `readyState` "complete" with an empty body for a moment, so URL and ready state alone are not enough.) It retries navigation timeouts with backoff, raises `Blocked` on the first "Access Denied" (retrying does not help, see below), and raises if the site redirects elsewhere. Each page's card count is checked against the site's "Showing 41-80 of 700" line, and stopping at `MAX_PAGES` is printed, so a partial crawl never looks complete.

```python
import json, os, re, tempfile, time

CITY = "austin-tx"   # slug from the site URL: austin-tx, chicago-il, houses/austin-tx
MAX_PAGES = 3        # safety cap; the site serves at most 18 pages (700 results) per search
PAUSE = 5            # seconds between page loads; see "Rate limits" below
TRIES = 3            # navigation attempts per page
MAX_BACKOFF = 120    # never sleep longer than this between attempts

class Blocked(Exception):
    pass

def _norm(u):
    return (u or "").split("#")[0].split("?")[0].rstrip("/")

def open_page(url, first=False):
    """Navigate, then return only when THIS url is the loaded, complete document."""
    want, here = _norm(url), None
    for attempt in range(1, TRIES + 1):
        before = "" if first and attempt == 1 else None
        if before is None:
            try:
                before = _norm(js("location.href"))
            except (TimeoutError, RuntimeError):
                pass
        try:
            if first and attempt == 1:
                new_tab(url)
            else:
                goto_url(url)
        except TimeoutError as e:  # browser-harness IPC timeouts subclass TimeoutError
            print(f"navigation timed out ({e}); attempt {attempt}/{TRIES}")
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                s = js("({href: location.href, ready: document.readyState, title: document.title,"
                       " rendered: !!document.querySelector('link[rel=canonical]') && document.body?.childElementCount > 0})")
            except (TimeoutError, RuntimeError):  # js() reports timeouts and mid-navigation errors as RuntimeError
                s = None
            if isinstance(s, dict):
                if "Access Denied" in str(s.get("title")):
                    raise Blocked(f"CDN returned Access Denied for {url}; stop and retry much later")
                here = _norm(s.get("href"))
                if s.get("ready") == "complete" and s.get("rendered"):
                    if here == want:
                        return
                    if before is not None and here != before and not here.startswith(("about:", "chrome:")):
                        raise RuntimeError(f"{url} redirected to {here}")
            time.sleep(0.5)
        print(f"{url} not loaded within 30 s; attempt {attempt}/{TRIES}")
        if attempt < TRIES:
            time.sleep(min(PAUSE * attempt, MAX_BACKOFF))
    raise RuntimeError(f"could not load {url} after {TRIES} attempts (tab is at {here})")

EXTRACT = r"""
(() => {
  const clean = v => (typeof v === 'string' && v.replace(/\s+/g, ' ').trim()) || null;
  // .reinforcement = a repeat of an earlier card inserted mid-list; not counted in "Showing N"
  const rows = [...document.querySelectorAll('article.placard[data-listingid]:not(.reinforcement)')].map(a => {
    const q = s => a.querySelector(s);
    const txt = s => clean(q(s)?.textContent);
    let share = [];
    try {
      const v = JSON.parse(q('[data-listing-share-lines]')?.dataset.listingShareLines || '[]');
      if (Array.isArray(v)) share = v;
    } catch (e) {}
    const rentLine = clean(share[7]) || '';
    const tier = ([...a.classList].find(c => c.startsWith('tmpl-')) || '').replace('tmpl-', '') || null;
    // basic-io / premiumplus are single homes, often individual landlords: do not collect their phone
    const personal = ['basic-io', 'premiumplus'].includes(tier);
    return {
      listing_id: a.dataset.listingid || null,
      tier,
      name: txt('.property-title'),
      address: clean(q('.property-address')?.getAttribute('title'))
               || clean(q('[data-listing-address]')?.dataset.listingAddress)
               || [share[2], share[3]].map(clean).filter(Boolean).join(', ') || null,
      beds: clean(share[5]),
      baths: clean(share[6]),
      rent: rentLine.replace(/^Total Monthly Price:\s*/, '') || null,
      rent_includes_fees: rentLine.startsWith('Total Monthly Price'),
      rent_by_bed: [...a.querySelectorAll('.bedRentBox')].map(b => ({
        beds: clean(b.querySelector('.bedTextBox')?.textContent),
        rent: clean(b.querySelector('.priceTextBox')?.textContent)})),
      phone: personal ? null : clean(q('.phone-link')?.getAttribute('phone-data')),
      amenities: txt('.property-amenities'),
      url: q('a.property-link[href]')?.href.split(/[?#]/)[0] || null,
    };
  });
  return {title: document.title,
          summary: clean(document.querySelector('.searchResults')?.textContent),
          next: document.querySelector('#paging a.next')?.href || null,
          rows};
})()
"""
SUMMARY = re.compile(r"Showing (\d+)(?:-(\d+))? of ([\d,]+) Results? - Page (\d+) of (\d+)")

listings, seen, repeats = [], set(), 0
url, page = f"https://www.apartments.com/{CITY}/", 1
while True:
    open_page(url, first=(page == 1))
    time.sleep(2)
    res = js(EXTRACT)
    if not isinstance(res, dict) or not isinstance(res.get("rows"), list):
        raise RuntimeError(f"extractor returned nothing on {url}")
    rows, summary = res["rows"], res.get("summary") or ""
    m = SUMMARY.search(summary)
    if m:
        expected = int(m[2]) - int(m[1]) + 1 if m[2] else int(m[1])
        total, page_no, pages_total = int(m[3].replace(",", "")), int(m[4]), int(m[5])
    elif page == 1 and not res.get("next") and (rows or re.search(r"- 0 Rentals", str(res.get("title")))):
        # small searches have one page and no "Showing ..." line
        expected, total, page_no, pages_total = len(rows), len(rows), 1, 1
    else:
        raise RuntimeError(f"no results summary on {url} (title: {res.get('title')})")
    if page_no != page or len(rows) != expected:
        raise RuntimeError(f"{url}: page {page_no} with {len(rows)} cards, expected page {page} with {expected}")
    print(page, summary or "(single page, no pager)", len(rows))
    for r in rows:
        if r["listing_id"] is not None and r["listing_id"] in seen:
            repeats += 1
            continue
        seen.add(r["listing_id"])
        listings.append(r)
    if page >= pages_total:
        print(f"complete: all {pages_total} pages, {total} results")
        if total == 700:
            print("700 is the site's per-search cap; it serves no results past it")
        break
    if page >= MAX_PAGES:
        print(f"stopped at MAX_PAGES={MAX_PAGES}: {pages_total - page} of {pages_total} pages not fetched")
        break
    nxt = res.get("next")
    if not isinstance(nxt, str) or not nxt:
        raise RuntimeError(f"no Next link on page {page} of {pages_total}")
    url, page = nxt, page + 1
    time.sleep(PAUSE)

print(len(listings), "unique listings,", repeats, "repeated across pages")
print(json.dumps(listings[:1], indent=1))
out = os.path.join(tempfile.gettempdir(), "apartments_" + CITY.replace("/", "_") + ".json")
json.dump(listings, open(out, "w"), indent=1)
print("saved", out)
```

Output observed on a fresh cloud browser (trimmed). The same code over `kerrville-tx` with `MAX_PAGES = 5` printed `complete: all 2 pages, 65 results` with address, beds, rent and url on 65/65; `alpine-tx` printed `(single page, no pager) 4`; and `open_page("https://www.apartments.com/austin-tx/19/")` raised `RuntimeError: ... redirected to https://www.apartments.com/austin-tx`.

```text
1 Showing 40 of 700 Results - Page 1 of 18 40
2 Showing 41-80 of 700 Results - Page 2 of 18 40
3 Showing 81-120 of 700 Results - Page 3 of 18 40
stopped at MAX_PAGES=3: 15 of 18 pages not fetched
120 unique listings, 0 repeated across pages
[
 {
  "listing_id": "4v6169l",
  "tier": "diamond",
  "name": "Ellwood at Lake Travis",
  "address": "7655 N Ranch Road 620, Austin, TX 78726",
  "beds": "1 - 3 bd",
  "baths": "1 - 2 ba",
  "rent": "$1,111 - $2,518",
  "rent_includes_fees": true,
  "rent_by_bed": [{"beds": "1 Bed", "rent": "$1,111+"}, {"beds": "2 Beds", "rent": "$1,249+"}, {"beds": "3 Beds", "rent": "$1,753+"}],
  "phone": "7372379124",
  "amenities": "Pets Allowed, Fitness Center, Pool, Walk-In Closets, Clubhouse, Stainless Steel Appliances, Business Center",
  "url": "https://www.apartments.com/ellwood-at-lake-travis-austin-tx/4v6169l/"
 }
]
```

An earlier version of the same extractor, run with `goto_url` over all 18 Austin pages at about 4.5 s per page, returned 700 unique listings: name, address, beds, baths, phone and url on 700/700, a dollar rent on 697/700 (the other 3 say "Call for Rent"), amenities on 295/700 (only the `diamond` tier shows them on the card). `CITY = "chicago-il"`, 2 pages: 80/80 on every field. Result order shifts between sessions (Edison Austin was first in one run, Ellwood at Lake Travis in the next), so dedupe on `listing_id`, not position.

### 2. One property: details and floor plans

Pass a `url` from step 1, or leave `PROPERTY_URL = None` to take the first card of the city page. `open_page` is the same helper as in step 1, repeated so the block runs on its own.

```python
import json, re, time

CITY = "austin-tx"
PROPERTY_URL = None   # e.g. a listing "url" from the search step; None = first result on the city page
PAUSE = 5
TRIES = 3
MAX_BACKOFF = 120

class Blocked(Exception):
    pass

def _norm(u):
    return (u or "").split("#")[0].split("?")[0].rstrip("/")

def open_page(url, first=False):
    """Navigate, then return only when THIS url is the loaded, complete document."""
    want, here = _norm(url), None
    for attempt in range(1, TRIES + 1):
        before = "" if first and attempt == 1 else None
        if before is None:
            try:
                before = _norm(js("location.href"))
            except (TimeoutError, RuntimeError):
                pass
        try:
            if first and attempt == 1:
                new_tab(url)
            else:
                goto_url(url)
        except TimeoutError as e:
            print(f"navigation timed out ({e}); attempt {attempt}/{TRIES}")
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                s = js("({href: location.href, ready: document.readyState, title: document.title,"
                       " rendered: !!document.querySelector('link[rel=canonical]') && document.body?.childElementCount > 0})")
            except (TimeoutError, RuntimeError):
                s = None
            if isinstance(s, dict):
                if "Access Denied" in str(s.get("title")):
                    raise Blocked(f"CDN returned Access Denied for {url}; stop and retry much later")
                here = _norm(s.get("href"))
                if s.get("ready") == "complete" and s.get("rendered"):
                    if here == want:
                        return
                    if before is not None and here != before and not here.startswith(("about:", "chrome:")):
                        raise RuntimeError(f"{url} redirected to {here}")
            time.sleep(0.5)
        print(f"{url} not loaded within 30 s; attempt {attempt}/{TRIES}")
        if attempt < TRIES:
            time.sleep(min(PAUSE * attempt, MAX_BACKOFF))
    raise RuntimeError(f"could not load {url} after {TRIES} attempts (tab is at {here})")

if not PROPERTY_URL:
    open_page(f"https://www.apartments.com/{CITY}/", first=True)
    time.sleep(2)
    href = js("document.querySelector('article.placard[data-listingid] a.property-link[href]')?.href || null")
    if not isinstance(href, str) or not href:
        raise RuntimeError("no listing card on the city page: " + str(page_info().get("title")))
    PROPERTY_URL = href.split("?")[0].split("#")[0]
    time.sleep(PAUSE)
    open_page(PROPERTY_URL)
else:
    open_page(PROPERTY_URL, first=True)
time.sleep(2)

PROPERTY = r"""
(() => {
  const str = v => (typeof v === 'string' && v.replace(/\s+/g, ' ').trim()) || null;
  const num = v => (typeof v === 'number' && isFinite(v)) ? v
                 : (typeof v === 'string' && v.trim() !== '' && isFinite(+v)) ? +v : null;
  const obj = v => (v && typeof v === 'object' && !Array.isArray(v)) ? v : {};
  const one = v => obj(Array.isArray(v) ? v[0] : v);
  // 1) JSON-LD: the first node whose @type includes RealEstateListing (top level or in @graph)
  let listing = null;
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    let d;
    try { d = JSON.parse(s.textContent); } catch (e) { continue; }
    for (const top of [].concat(d)) {
      for (const n of [].concat(obj(top)['@graph'] || top)) {
        if (!listing && [].concat(obj(n)['@type'] || []).includes('RealEstateListing')) listing = obj(n);
      }
    }
  }
  listing = listing || {};
  const me = one(listing.mainEntity);
  const a = me.address;
  const address = typeof a === 'string' ? str(a)
    : [a?.streetAddress, a?.addressLocality, a?.addressRegion, a?.postalCode].map(str).filter(Boolean).join(', ') || null;
  const geo = one(me.geo), offers = one(listing.offers), rating = one(listing.aggregateRating);
  // 2) Floor plans: the "all" tab holds every plan once; per-bed tabs repeat them
  const root = document.querySelector('[data-tab-content-id="all"]') || document;
  const seen = new Set();
  const plans = [...root.querySelectorAll('.pricingGridItem')].map(g => {
    const key = g.querySelector('.priceGridModelWrapper')?.dataset.rentalkey || null;
    if (key && seen.has(key)) return null;
    if (key) seen.add(key);
    const t = s => str(g.querySelector(s)?.textContent);
    return {
      rental_key: key,
      plan: t('.modelName'),
      rent: t('.rentLabel'),
      details: [...g.querySelectorAll('.detailsTextWrapper > span')].map(s => str(s.textContent)).filter(Boolean),
      availability: t('.availability'),
      units: [...g.querySelectorAll('li.unitContainer')].map(u => ({
        unit: u.dataset.unit || null,
        beds: u.dataset.beds || null, baths: u.dataset.baths || null,
        base_rent: u.dataset.maxrent || null,
        price: u.dataset.applynowPrice || null,
        specs: u.dataset.applynowSpecs || null,
      })),
    };
  }).filter(Boolean);
  // Phone only for apartment communities; single homes (SingleFamilyResidence etc.) are often individual landlords
  const propertyType = str([].concat(me['@type'] || [])[0]);
  return {
    url: location.href.split(/[?#]/)[0],
    name: str(listing.name) || str(document.querySelector('h1')?.textContent),
    property_type: propertyType,
    phone: propertyType === 'ApartmentComplex' ? str(listing.telephone) : null,
    address,
    lat: num(geo.latitude), lon: num(geo.longitude),
    rent_low: num(offers.lowPrice), rent_high: num(offers.highPrice),
    rating: num(rating.ratingValue),
    rating_count: num(rating.ratingCount),
    pets_allowed: typeof me.petsAllowed === 'boolean' ? me.petsAllowed : str(me.petsAllowed),
    amenities_jsonld: [].concat(me.amenityFeature || []).map(f => typeof f === 'string' ? str(f) : str(obj(f).name)).filter(Boolean),
    amenities_page: [...new Set([...document.querySelectorAll('#amenitiesSection li')].map(e => str(e.textContent)).filter(Boolean))],
    floor_plans: plans,
  };
})()
"""

prop = js(PROPERTY)
if not isinstance(prop, dict) or not prop.get("name"):
    raise RuntimeError("property extractor returned nothing on " + PROPERTY_URL)
print(json.dumps({k: v for k, v in prop.items() if k != "floor_plans"}, indent=1))
plans = prop["floor_plans"]
print(len(plans), "floor plans,", sum(len(p["units"]) for p in plans), "listed units")
for p in plans:
    print(p["plan"], "|", p["rent"], "|", " / ".join(p["details"]), "|", p["availability"])
# Completeness: a plan that says "N Available units" must list N unit rows
short = [(p["plan"], m[1], len(p["units"])) for p in plans
         for m in [re.match(r"(\d+) Available units?", p["availability"] or "")]
         if m and int(m[1]) != len(p["units"])]
if short:
    raise RuntimeError(f"unit grid incomplete (plan, stated, listed): {short}")
print("unit rows match every plan's stated available count")
```

Output observed (first Austin result at run time, trimmed):

```text
{
 "url": "https://www.apartments.com/ellwood-at-lake-travis-austin-tx/4v6169l/",
 "name": "Ellwood at Lake Travis",
 "property_type": "ApartmentComplex",
 "phone": "+1-737-237-9124",
 "address": "7655 N Ranch Road 620, Austin, TX, 78726",
 "lat": 30.40643,
 "lon": -97.85038,
 "rent_low": 951,
 "rent_high": 2358,
 "rating": null,
 "rating_count": null,
 "pets_allowed": true,
 "amenities_jsonld": ["Pool", "Fitness Center", "Clubhouse", "Recycling", "Business Center", "Grill", "Pet Care", "Conference Rooms"],
 "amenities_page": ["Package Service", "Wi-Fi", "Maintenance on site", "Property Manager on Site", ...]
}
49 floor plans, 79 listed units
A2 Lake | $1,111 Total Monthly Price | 1 Bed / 1 Bath / 683 Sq Ft / $250 Deposit | 1 Available unit
A1 Lake | Starting at $1,143 Total Monthly Price | 1 Bed / 1 Bath / 644 Sq Ft / $250 Deposit | 2 Available units
...
C1 Canyon Renovated | Starting at $1,918 Total Monthly Price | 3 Beds / 2 Baths / 1,341 Sq Ft / $250 Deposit | 3 Available units
A4 Lake | Call for Rent | 1 Bed / 1 Bath / 775 Sq Ft | None
...
unit rows match every plan's stated available count
```

The per-plan "N Available units" counts matched the listed `units` rows on every plan (Ellwood 79, Edison Austin 68), so the unit grid is complete without clicking anything; the last check raises if that ever stops being true. Each `units` row looks like `{"unit": "1421", "beds": "0", "baths": "1", "base_rent": "1295", "price": "$1,541", "specs": "Studio • 1 Bath • 517 Sq Ft • Available Now"}` (Edison Austin, 25 plans / 68 units).

## Fields

Search card (step 1):

| Field | Source | Notes |
|---|---|---|
| `listing_id` | `article.placard[data-listingid]` | Stable id, also the last path segment of the property URL |
| `tier` | `tmpl-*` class on the card | Ad tier. Seen: `diamond`, `platinum`, `gold`, `platinum-propres`, `silver-propres`, `premiumplus`, `basic-io`. Results are grouped by tier: Austin pages 1-2 were all `diamond`, page 10 all `platinum`, page 18 all `gold` (295 / 259 / 145 + 1 `platinum-propres` over 700) |
| `name` | `.property-title` | For single homes (`basic-io`, `premiumplus`) the name is the street address |
| `address` | `.property-address[title]`, else `[data-listing-address]`, else share-lines `[2]`, `[3]` | Full one-line address. `basic-io` cards have no `.property-address` element (Kerrville: 13/65 cards had it), but all 65 carried `data-listing-address` |
| `beds`, `baths` | `data-listing-share-lines[5]`, `[6]` | e.g. `"Studio - 2 bd"`, `"1 - 2.5 ba"` |
| `rent` | `data-listing-share-lines[7]` | `"$1,243 - $2,257"`, `"$2,300"` or `"Call for Rent"` |
| `rent_includes_fees` | prefix `Total Monthly Price:` | True when the site shows rent plus required monthly fees instead of base rent |
| `rent_by_bed` | `.bedRentBox` | List of `{beds, rent}`: per-bedroom "from" price as shown on the card |
| `phone` | `.phone-link[phone-data]` | Digits only. Set to null for `basic-io` and `premiumplus` (single homes, see "Personal data"). Present on all 700 Austin apartment search results |
| `amenities` | `.property-amenities` | Comma string, tier-dependent: all `diamond`, no `platinum`/`gold` in Austin; 72/80 on 2 pages of `/houses/austin-tx/` |
| `url` | first `a.property-link[href]` | Canonical property URL, query and hash stripped |

Property page (step 2):

| Field | Source | Notes |
|---|---|---|
| `url` | `location.href` | Query and hash stripped |
| `name` | JSON-LD `name`, else `h1` | |
| `property_type` | JSON-LD `mainEntity.@type` | `ApartmentComplex` for communities; a `premiumplus` house page had `SingleFamilyResidence` |
| `phone` | JSON-LD `telephone` | `+1-737-...` format. Only kept when `property_type` is `ApartmentComplex`; null otherwise (house pages carry a phone too, often an individual landlord's) |
| `address`, `lat`, `lon` | JSON-LD `mainEntity.address`, `.geo` | `lat`/`lon` are numbers or null |
| `rent_low`, `rent_high` | JSON-LD `offers` (`AggregateOffer`) | Numbers, USD. Looks like base rent: Ellwood showed `951` here vs `$1,111` "Total Monthly Price" on the card |
| `rating`, `rating_count` | JSON-LD `aggregateRating` | May be null |
| `pets_allowed` | JSON-LD `mainEntity.petsAllowed` | Boolean when present |
| `amenities_jsonld` | JSON-LD `amenityFeature[].name` | Short list (4 and 8 names on the two pages read) |
| `amenities_page` | `#amenitiesSection li` | Full list, deduped |
| `floor_plans[].rental_key` | `.priceGridModelWrapper[data-rentalkey]` | Plan id used for dedupe; null plans are kept |
| `floor_plans[].plan/rent/details/availability` | `[data-tab-content-id="all"] .pricingGridItem` | `rent` is text like `"Starting at $1,541 Total Monthly Price"` or `"Call for Rent"`; `details` is a list like `["1 Bed", "1 Bath", "683 Sq Ft", "$250 Deposit"]` |
| `floor_plans[].units[]` | `li.unitContainer` data attributes | `unit` number, `beds`, `baths`, `base_rent` (`data-maxrent`), `price` (`data-applynow-price`, includes required fees when the property shows total monthly price), `specs` with move-in date. All strings |

JSON-LD `mainEntity.containsPlace` also lists units with bedrooms, bathrooms and square feet, but no prices.

## Gotchas

- **CDN block (Akamai).** Plain HTTP is 403. In the browser, the session got "Access Denied" (title `Access Denied`, an `errors.edgesuite.net` reference) after sustained crawling, and same-origin `fetch()` from the page returned 403 too once that happened. `open_page` checks the title on every load and raises `Blocked` on the first one.
- **Rate limits.** 18 consecutive page navigations at about 4.5 s spacing worked. The block came later in the session after extra rapid `fetch()` calls at 2 s spacing. Keep at least 5 s between loads and keep total volume modest.
- **700-result cap.** Every search URL stops at page 18 even for 27,813 Austin rentals. The site does not serve results past it; this skill does not try to work around it.
- **Filter slugs keep the cap.** `/austin-tx/2-bedrooms/` and `/austin-tx/under-1500/` load with their own titles but still say "Showing 40 of 700 Results".
- **Small searches have no pager.** `/alpine-tx/` showed 4 cards with no "Showing ..." line and no Next link; the code treats that as one complete page. `/marfa-tx/` had 0 cards.
- **Card layout differs by tier.** Name, url, `data-listing-address` and the share-lines array (street, city line, beds, baths, rent) were present on all tiers seen; the `.property-address` element, phone, amenities and the "Total Monthly Price" label vary (`basic-io` single-home cards have no `.property-address`). The share-lines array is the most uniform source on the card, so the code reads beds/baths/rent from it instead of tier-specific markup.
- **Repeated "featured" card.** `/houses/austin-tx/` page 1 had 41 `article.placard` nodes for "Showing 40": the diamond listing appeared again mid-list as a `featured-unit reinforcement` card with a different tier class. The extractor skips `.reinforcement`.
- **Floor-plan tabs repeat plans.** The property page has tabs `all`, `bed0`, `bed1`, `bed2`... with the same plans again (Edison Austin: 50 `.pricingGridItem` nodes, 25 unique in `all`). Read only the `all` tab and dedupe by `data-rentalkey`.
- **No lazy loading needed.** All 40 cards and every floor-plan unit are in the initial HTML; no scrolling or "show more" clicks were required.
- **No consent or cookie banner** appeared on the search page screenshot, and nothing had to be dismissed before extraction.
- **Personal data.** Single-home listings (`basic-io`, `premiumplus`) are often posted by individual landlords; their phone numbers are personal data. The search extractor returns `phone: null` for those tiers, and the property extractor keeps the phone only on `ApartmentComplex` pages.

## What does not work

- Plain HTTP (`http_get`, curl, requests) on any apartments.com URL, including `/robots.txt`: HTTP 403 "Access Denied" from the edge.
- Paging past the cap: `/austin-tx/19/` redirects to `/austin-tx/`.
- Continuing after a block: once "Access Denied" appeared, the next pages and in-page `fetch()` calls in the same session were also 403, and a single page load about 12 minutes later was still "Access Denied". On a block, stop and back off; do not retry in a loop.
- Bursts of same-origin `fetch()` calls for other search pages (2 s spacing) were followed shortly by the session block. Plain page navigation at about 4.5 s spacing held up for a full 18-page crawl, so the code above uses it.
