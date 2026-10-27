# Realtor.com — For-sale listings and listing facts

Field-tested against www.realtor.com on 2026-10-23 using a Browser Use cloud browser.

robots.txt (checked 2026-10-23) allows `/realestateandhomes-search/<location>`, its `/pg-N` pages and `/realestateandhomes-detail/<slug>` for all user agents; it disallows `/realestateandhomes-search/*/*/pg-` (filters combined with pagination) and a few named listing slugs.

## Quick summary

- Plain HTTP is blocked (status 429 on the first request to search and listing pages); this skill uses a normal browser session.
- **Search pages** (`/realestateandhomes-search/<City_ST or ZIP>[/pg-N]`) are a React Router app. All 42 results per page, plus the total count, sit in `window.__reactRouterDataRouter.state.loaderData.srp.search.value`. That object has price, beds, baths, sqft, status text, flags, broker and the listing slug. No DOM scraping needed.
- **Listing pages** (`/realestateandhomes-detail/<slug>`) are a Next.js app. `__NEXT_DATA__` -> `props.pageProps.initialReduxState.propertyDetails` holds the full key facts (year built, HOA, price/sqft, days on MLS, lot, garage, stories, description, a categorized details list, estimate). JSON-LD (`RealEstateListing`) holds a smaller public subset.
- From an open realtor.com tab, a same-origin `fetch()` of a listing URL returned 200 with `__NEXT_DATA__` in the HTML. That gives listing facts in batches without navigating the tab.
- Pagination: `/pg-N`, 42 per page. Tested through the last page of Austin, TX (pg-167, 7,009 results, 37 on the last page) with no cap and no block. A page past the end returns `total` with 0 rows.

## What works

### 1. Search results for a city or ZIP across several pages

Run this first. It opens one tab and walks up to `MAX_PAGES` pages, reading the router loader data. It saves `realtor_listings.json` in the system temp dir, which blocks 2 and 3 read.

Each page load is checked: the block waits until the tab's URL is the requested page and its loader data is ready. A page without loader data (which includes a 429, error or challenge page) is loaded at most `TRIES` (3) times, 5 s then 10 s apart, all well under the 120 s cap block 2 uses, and then the block raises. It stops at the first short page (fewer than 42 rows), which is the real end. If it stops because of `MAX_PAGES` instead, it prints `STOPPED AT MAX_PAGES` with the count collected so far.

```python
import json, os, tempfile, time, urllib.parse

LOCATION = "Austin_TX"   # "City_ST" (spaces as hyphens, e.g. "San-Francisco_CA") or a 5-digit ZIP, e.g. "78704"
MAX_PAGES = 3            # safety cap; the block says so when it stops here
PAGE_SIZE = 42           # rows per full search page
PAUSE_S = 3              # polite pause between page loads
TRIES = 3                # loads per page before giving up

SRP_JS = r"""(() => {
  const r = window.__reactRouterDataRouter;
  const srp = r && r.state && r.state.loaderData && r.state.loaderData.srp;
  const v = srp && srp.search && srp.search.value;
  if (!v) return {error: 'no search data yet', title: document.title, url: location.href};
  return {
    url: location.href,
    total: v.total,
    rows: (v.properties || []).map(p => {
      const a = (p.location && p.location.address) || {};
      const d = p.description || {};
      const f = p.flags || {};
      return {
        property_id: p.property_id, listing_id: p.listing_id,
        address: a.line, unit: a.unit,   // line already includes the unit
        city: a.city, state: a.state_code, zip: a.postal_code,
        price: p.list_price, beds: d.beds, baths: d.baths_consolidated,
        sqft: d.sqft, lot_sqft: d.lot_sqft, type: d.type,
        status: p.status, status_text: p.statusText,
        is_pending: !!f.is_pending, is_contingent: !!f.is_contingent,
        is_foreclosure: !!f.is_foreclosure, is_new_listing: !!f.is_new_listing,
        list_date: p.list_date, lat: p.lat, lng: p.lng, broker: p.brokerageName,
        url: p.ldpSlug ? 'https://www.realtor.com/realestateandhomes-detail/' + p.ldpSlug : null
      };
    })
  };
})()"""

def search_url(location, page=1):
    base = "https://www.realtor.com/realestateandhomes-search/" + urllib.parse.quote(location, safe="")
    return base if page == 1 else f"{base}/pg-{page}"

def same_page(href, url):
    a, b = urllib.parse.urlsplit(href or ""), urllib.parse.urlsplit(url)
    norm = lambda u: urllib.parse.unquote(u.path).rstrip("/").lower()
    return a.netloc == b.netloc and norm(a) == norm(b)

def read_srp(url, wait_s=20):
    """Poll until the tab shows `url` and its loader data is ready. Returns (data or None, last seen)."""
    last, deadline = None, time.time() + wait_s
    while time.time() < deadline:
        try:
            d = js(SRP_JS) or {}
        except (TimeoutError, RuntimeError) as e:  # js() timeouts and mid-navigation errors; poll again
            d = {"error": str(e)[:200]}
        if not d.get("error") and same_page(d.get("url"), url) and isinstance(d.get("rows"), list):
            return d, d
        last = d
        time.sleep(1)
    return None, last

def load_page(url, first):
    last = None
    for attempt in range(TRIES):
        try:
            if first and attempt == 0:
                new_tab(url)
            else:
                goto_url(url)
        except TimeoutError:  # Page.navigate can outlast the IPC wait; read_srp checks the URL either way
            pass
        d, last = read_srp(url)
        if d:
            return d
        if attempt + 1 < TRIES:      # no sleep after the last load
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError(f"no search data for {url} after {TRIES} loads; last seen: {last}")

listings, seen, total, complete = [], set(), None, False
for page in range(1, MAX_PAGES + 1):
    d = load_page(search_url(LOCATION, page), first=(page == 1))
    rows = d["rows"]
    if isinstance(d.get("total"), (int, float)) and not isinstance(d.get("total"), bool):
        total = int(d["total"])
    for r in rows:
        pid = r.get("property_id")
        if pid is None:
            listings.append(r)       # no id to dedupe on; keep it
        elif pid not in seen:
            seen.add(pid)
            listings.append(r)
    print(f"page {page}: {len(rows)} rows, total={total}")
    if len(rows) < PAGE_SIZE or (total is not None and page * PAGE_SIZE >= total):
        complete = True
        break
    time.sleep(PAUSE_S)

if not complete:
    print(f"STOPPED AT MAX_PAGES={MAX_PAGES}: {len(listings)} of {total} collected; raise MAX_PAGES for the rest")
print(len(listings), "listings of", total, "(complete)" if complete else "(partial)")
for r in listings[:3]:
    print(r["address"], r["zip"], r["price"], r["beds"], r["baths"], r["sqft"], r["status_text"], r["url"])
OUT = os.path.join(tempfile.gettempdir(), "realtor_listings.json")
json.dump(listings, open(OUT, "w"), indent=1)
print("saved", OUT)
```

Real output (`LOCATION = "Austin_TX"`, trimmed):

```
page 1: 42 rows, total=7008
page 2: 42 rows, total=7008
page 3: 42 rows, total=7008
STOPPED AT MAX_PAGES=3: 126 of 7008 collected; raise MAX_PAGES for the rest
126 listings of 7008 (partial)
1704 Shelbourne Dr 78752 400000 3 2 1556 House for sale https://www.realtor.com/realestateandhomes-detail/1704-Shelbourne-Dr_Austin_TX_78752_M81029-30727
6700 Tulloch Way 78754 439999 4 3.5 3840 Pending https://www.realtor.com/realestateandhomes-detail/6700-Tulloch-Way_Austin_TX_78754_M83959-32351
6305 Leatherwood Cv 78759 720000 4 2.5 2164 House for sale https://www.realtor.com/realestateandhomes-detail/6305-Leatherwood-Cv_Austin_TX_78759_M76134-13530
saved /tmp/realtor_listings.json   (your system temp dir)
```

With `LOCATION = "78704"` and `MAX_PAGES = 12`, the same block walked the whole ZIP: pages 1-9 with 42 rows each, page 10 with 21, then it stopped on that short page and printed `399 listings of 399 (complete)`. No duplicates were dropped (9 x 42 + 21 = 399).

### 2. Key facts for each listing (batch, no tab navigation)

This needs a www.realtor.com tab (block 1 leaves one open), because `fetch()` must be same-origin. It reads the saved `realtor_listings.json`, fetches each listing's HTML from inside the page and parses `__NEXT_DATA__`.

The fetch is started in the page and polled, because one `js()` call gives up after about 5 s and a listing fetch can take longer. A 429, a 5xx, a network error or a page without listing data gets a bounded retry: at most `TRIES` (4) fetches per listing, waiting the `Retry-After` value (seconds or an HTTP date) or else 5, 10, 20 s. Waits are capped at `MAX_WAIT_S` (120 s): if the server asks for longer, the block stops the batch at once, saves what it has and raises. It never sleeps after the last try. A listing still failing after 4 tries, or a response for a different property than requested, counts as failed and the batch moves to the next listing. At the end the block saves what succeeded, then raises with the list of listings that failed, so a partial batch never looks complete.

```python
import email.utils, json, os, tempfile, time, urllib.parse

N = 5          # how many listings to enrich
PAUSE_S = 2
TRIES = 4      # fetches per listing before it counts as failed
MAX_WAIT_S = 120  # longest Retry-After or backoff sleep; a longer ask stops the batch

class WaitTooLong(Exception):
    pass

START_JS = r"""((url, key) => {
  window.__rdcFacts = window.__rdcFacts || {};
  window.__rdcFacts[key] = null;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 30000);
  fetch(url, {credentials: 'same-origin', signal: ctl.signal}).then(async res => {
    const html = await res.text();
    const out = {http_status: res.status, final_url: res.url, retry_after: res.headers.get('retry-after')};
    const m = html.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
    if (!m) return Object.assign(out, {error: 'no __NEXT_DATA__'});
    let p;
    try {
      const s = ((JSON.parse(m[1]).props || {}).pageProps || {}).initialReduxState || {};
      p = s.propertyDetails;
    } catch (e) { return Object.assign(out, {error: 'bad __NEXT_DATA__: ' + e}); }
    if (!p) return Object.assign(out, {error: 'no propertyDetails'});
    const d = p.description || {}, loc = p.location || {}, a = loc.address || {};
    const best = ((p.estimates && p.estimates.current_values) || []).find(e => e && e.isbest_homevalue);
    const seller = (p.advertisers || []).find(x => x && x.type === 'seller');
    out.facts = {
      url: p.href,
      property_id: p.property_id, listing_id: p.listing_id,
      status: p.status,
      flags: Object.entries(p.flags || {}).filter(([k, v]) => v === true).map(([k]) => k),
      list_price: p.list_price, price_per_sqft: p.price_per_sqft,
      list_date: p.list_date, last_update: p.source && p.source.last_update_date,
      days_on_mls: p.source && p.source.days_on_mls,
      address: a.line, unit: a.unit, city: a.city, state: a.state_code, zip: a.postal_code,
      county: loc.county && loc.county.name,
      neighborhoods: (loc.neighborhoods || []).map(n => n && n.name).filter(Boolean),
      type: d.type, sub_type: d.sub_type,
      beds: d.beds, baths: d.baths_consolidated, baths_full: d.baths_full, baths_half: d.baths_half,
      sqft: d.sqft, lot_sqft: d.lot_sqft, year_built: d.year_built,
      stories: d.stories, garage: d.garage,
      hoa_fee: p.hoa ? p.hoa.fee : null,
      estimate: best ? best.estimate : null,
      property_tax_rate: p.mortgage && p.mortgage.property_tax_rate,
      photo_count: p.photo_count,
      broker: seller && seller.broker ? seller.broker.name : null,
      remarks: d.text,
      details: Object.fromEntries((p.details || []).filter(c => c && c.category).map(c => [c.category, c.text]))
    };
    return out;
  }).catch(e => ({error: String(e)})).then(r => { clearTimeout(timer); window.__rdcFacts[key] = r; });
  return true;
})"""

def on_realtor():
    try:
        return urllib.parse.urlsplit(page_info().get("url", "")).hostname == "www.realtor.com"
    except (TimeoutError, RuntimeError):
        return False

def retry_after_s(value, default):
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, email.utils.parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return default

def fetch_once(url, key, wait_s=40):
    js(f"{START_JS}({json.dumps(url)}, {json.dumps(key)})")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        time.sleep(1)
        try:
            r = js(f"window.__rdcFacts && window.__rdcFacts[{json.dumps(key)}]")
        except (TimeoutError, RuntimeError):  # a slow js() round trip; poll again
            continue
        if r:
            return r
    return {"error": f"no result after {wait_s}s"}

def get_facts(row):
    last = None
    for attempt in range(TRIES):
        try:
            r = fetch_once(row["url"], f"{row.get('property_id')}-{attempt}-{time.time()}")
        except (TimeoutError, RuntimeError) as e:
            r = {"error": str(e)[:200]}
        status, f = r.get("http_status"), r.get("facts")
        if status == 200 and f:
            if row.get("property_id") is not None and f.get("property_id") != row["property_id"]:
                raise RuntimeError(f"{row['url']} returned property {f.get('property_id')}, wanted {row['property_id']}")
            return f
        last = {k: r.get(k) for k in ("http_status", "final_url", "error")}
        if isinstance(status, int) and 400 <= status < 500 and status != 429:
            break                           # 404 and friends will not fix themselves
        if status == 200 and "/realestateandhomes-detail/" not in urllib.parse.urlsplit(r.get("final_url") or "").path:
            break                           # redirected away from the listing (seen for an unknown slug)
        if attempt + 1 == TRIES:
            break                           # no retry left, so no sleep
        wait = retry_after_s(r.get("retry_after"), 5 * 2 ** attempt)
        if wait > MAX_WAIT_S:
            raise WaitTooLong(f"{row['url']}: server asked to wait {wait:.0f}s (> {MAX_WAIT_S}s); stopping. last: {last}")
        time.sleep(wait)
    raise RuntimeError(f"{row['url']}: {last}")

if not on_realtor():
    try:
        goto_url("https://www.realtor.com/")
    except TimeoutError:
        pass
    for _ in range(30):
        if on_realtor():
            break
        time.sleep(1)
    else:
        raise RuntimeError("need a www.realtor.com tab for same-origin fetch()")

listings = json.load(open(os.path.join(tempfile.gettempdir(), "realtor_listings.json")))
todo = [r for r in listings if r.get("url")][:N]
print(f"{len(todo)} listings to enrich ({sum(1 for r in listings if not r.get('url'))} saved rows have no URL)")
facts, failed, stop = [], [], None
for r in todo:
    try:
        f = get_facts(r)
    except WaitTooLong as e:
        stop = e
        print("STOPPED", e)
        break
    except RuntimeError as e:
        failed.append(str(e))
        print("FAILED", e)
    else:
        facts.append(f)
        print(f["address"], f["list_price"], f["beds"], f["baths"], f["sqft"], f["year_built"],
              "hoa", f["hoa_fee"], "dom", f["days_on_mls"], f["status"], f["flags"])
    time.sleep(PAUSE_S)
json.dump(facts, open(os.path.join(tempfile.gettempdir(), "realtor_listing_facts.json"), "w"), indent=1)
print(len(facts), "of", len(todo), "listings enriched")
if stop:
    raise stop
if failed:
    raise RuntimeError(f"{len(failed)} of {len(todo)} listings failed after retries: {failed}")
```

Real output (trimmed). `flags` shows only the flags set to true:

```
5 listings to enrich (0 saved rows have no URL)
1704 Shelbourne Dr 400000 3 2 1556 1969 hoa 0 dom 219 for_sale ['is_short_sale']
6700 Tulloch Way 439999 4 3.5 3840 2005 hoa 41 dom 19 for_sale ['is_pending']
6305 Leatherwood Cv 720000 4 2.5 2164 1984 hoa 0 dom 16 for_sale []
14100 Avery Ranch Blvd Unit 202 342900 3 3 1942 2007 hoa 385 dom 65 for_sale ['is_price_reduced']
4111 Everest Ln 510000 3 2.5 1704 1980 hoa 0 dom 33 for_sale ['is_price_reduced']
5 of 5 listings enriched
```

One saved record (remarks and details trimmed):

```
{'url': 'https://www.realtor.com/realestateandhomes-detail/6700-Tulloch-Way_Austin_TX_78754_M83959-32351', 'property_id': '8395932351', 'listing_id': '3001457163', 'status': 'for_sale', 'flags': ['is_pending'], 'list_price': 439999, 'price_per_sqft': 115, 'list_date': '2026-10-02T02:45:32Z', 'last_update': '2026-10-21T01:46:09Z', 'days_on_mls': 19, 'address': '6700 Tulloch Way', 'unit': None, 'city': 'Austin', 'state': 'TX', 'zip': '78754', 'county': 'Travis', 'neighborhoods': ['Belhaven', 'Harris Branch', 'Northeast Austin'], 'type': 'single_family', 'sub_type': None, 'beds': 4, 'baths': '3.5', 'baths_full': 3, 'baths_half': 1, 'sqft': 3840, 'lot_sqft': 8350, 'year_built': 2005, 'stories': 2, 'garage': 2, 'hoa_fee': 41, 'estimate': 438000, 'property_tax_rate': 0.02091823, 'photo_count': 11, 'broker': 'Realty Texas, LLC', 'remarks': '...', 'details': {...}}
```

Example `details` keys from one listing: `Appliances, Bedrooms, Bathrooms, Interior Features, Heating and Cooling, Land Info, Exterior and Lot Features, Garage and Parking, Homeowners Association, School Information, Amenities and Community Features, Other Property Info, Building and Construction, Utilities, Home Features`. Each value is a list of strings such as `"Annual Tax Amount: 47460"` or `"Roof: Metal"`.

### 3. One listing page in the tab (JSON-LD, public subset)

Use this when you are already on a listing page, or when you want only the schema.org subset. It navigates the tab to the first saved listing, waits until the tab's URL is that listing and its JSON-LD names the same URL, and raises if that never happens. It drops the `seller` block from the output because that block holds agent names and phone numbers.

```python
import json, os, tempfile, time, urllib.parse

listings = json.load(open(os.path.join(tempfile.gettempdir(), "realtor_listings.json")))
url = next((r["url"] for r in listings if r.get("url")), None)
if not url:
    raise RuntimeError("no saved listing has a URL; run block 1 first")

LD_JS = r"""({href: location.href, ready: document.readyState,
  lds: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent)})"""

def same_page(href, want):
    a, b = urllib.parse.urlsplit(href or ""), urllib.parse.urlsplit(want)
    norm = lambda u: urllib.parse.unquote(u.path).rstrip("/").lower()
    return a.netloc == b.netloc and norm(a) == norm(b)

def find_listing(lds, want):
    for raw in lds or []:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for item in (data if isinstance(data, list) else [data]):
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if t == "RealEstateListing" or (isinstance(t, list) and "RealEstateListing" in t):
                ref = item.get("url") or str(item.get("@id") or "").split("#")[0]
                if same_page(ref, want):
                    return item
    return None                     # no listing for this URL; never fall back to another one

def load_listing(want, tries=3, wait_s=20):
    last = None
    for attempt in range(tries):
        try:
            goto_url(want)
        except TimeoutError:        # Page.navigate can outlast the IPC wait; the URL check decides
            pass
        deadline = time.time() + wait_s
        while time.time() < deadline:
            try:
                s = js(LD_JS) or {}
            except (TimeoutError, RuntimeError) as e:
                s = {"error": str(e)[:200]}
            if same_page(s.get("href"), want) and s.get("ready") == "complete":
                item = find_listing(s.get("lds"), want)
                if item:
                    return item
            last = {k: s.get(k) for k in ("href", "ready", "error")}
            time.sleep(1)
        if attempt + 1 < tries:     # no sleep after the last load
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError(f"no RealEstateListing JSON-LD for {want}; last seen: {last}")

def first_dict(v):
    if isinstance(v, list):
        v = next((x for x in v if isinstance(x, dict)), None)
    return v if isinstance(v, dict) else {}

def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            f = float(v.replace(",", ""))
            return int(f) if f.is_integer() else f
        except ValueError:
            return None
    return None

def image_urls(v):
    out = []
    for x in (v if isinstance(v, list) else [v]):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict) and isinstance(x.get("url") or x.get("contentUrl"), str):
            out.append(x.get("url") or x.get("contentUrl"))
    return out

listing = load_listing(url)
home, offer = first_dict(listing.get("mainEntity")), first_dict(listing.get("offers"))
size = home.get("floorSize")
print({
    "name": listing.get("name"),
    "price": num(offer.get("price")),
    "availability": offer.get("availability"),
    "beds": num(home.get("numberOfBedrooms")),
    "baths": num(home.get("numberOfBathroomsTotal")),
    "sqft": num(size.get("value") if isinstance(size, dict) else size),
    "year_built": num(home.get("yearBuilt")),
    "type": home.get("@type"),
    "date_posted": listing.get("datePosted"),
    "photos": len(image_urls(home.get("photo"))),
    "summary": listing.get("description"),
})
```

Real output:

```
{'name': '1704 Shelbourne Dr, Austin, TX 78752', 'price': 400000, 'availability': 'https://schema.org/InStock', 'beds': 3, 'baths': 2, 'sqft': 1556, 'year_built': 1969, 'type': 'SingleFamilyResidence', 'date_posted': '2026-02-21T14:21:38Z', 'photos': 3, 'summary': 'Buy this 1556 sqft single family built in 1969, located in the Creekside neighborhood of Austin, TX located at 1704 Shelbourne Dr. Listed for $400,000 on Realtor.com.'}
```

JSON-LD `photo` held 3 `ImageObject`s here even though the listing has 38 photos (`photo_count` from block 2). Use `propertyDetails.photos` for the full list.

## Fields

Search row from block 1 (`loaderData.srp.search.value.properties[i]`):

| Output key | Source path | Example / notes |
|---|---|---|
| `property_id` | `property_id` | `"8102930727"`, stable property key |
| `listing_id` | `listing_id` | `"2991781467"` |
| `address`, `unit`, `city`, `state`, `zip` | `location.address.line/unit/city/state_code/postal_code` | `1704 Shelbourne Dr`, null, `Austin`, `TX`, `78752`; `line` already holds the unit (`2804 Rio Grande St Apt 208` with unit `Apt 208`, 7 of 7 unit rows on one page), so do not append `unit` again |
| `price` | `list_price` | `400000` (int, USD) |
| `beds` | `description.beds` | `3`; null on 20 of 524 rows (mostly land) |
| `baths` | `description.baths_consolidated` | string: `"2"`, `"3.5"`, `"4.5+"` |
| `sqft`, `lot_sqft` | `description.sqft`, `description.lot_sqft` | `1556`, `9561`; sqft null on 20 and lot null on 36 of 524 rows |
| `type` | `description.type` | `single_family`, `condos`, `multi_family`, `townhomes`, `land` (all values seen in 524 rows) |
| `status` | `status` | `for_sale` on 523 of 524 rows, `ready_to_build` on 1 (new-construction plan) |
| `status_text` | `statusText` | `House for sale`, `Condo for sale`, `Pending` (58 of 524), `Contingent` (6), `Foreclosure`, `Land for sale`, `Townhouse for sale`, `Multi-family home for sale`; `Mobile home for sale` also seen in a sorted Austin search |
| `is_pending`, `is_contingent`, `is_foreclosure`, `is_new_listing` | `flags.*` of the same names | booleans; null in the data becomes `false` |
| `list_date` | `list_date` | `2026-02-21T14:21:38.000000Z` |
| `lat`, `lng` | `lat`, `lng` | |
| `broker` | `brokerageName` | brokerage business name |
| `url` | `ldpSlug` | `https://www.realtor.com/realestateandhomes-detail/<ldpSlug>`; null when there is no slug |

`total` (total matches for the search, e.g. `7010`) is printed by block 1 but not stored per row.

Other search keys seen but not returned: `photos`, `primary_photo.href`, `photo_count`, `priceReducedAmount`, `openHouseLabel`, `source.id` (MLS code), `source.listing_id` (MLS number), `promotedProperties` (sponsored, kept apart from `properties`).

Listing record from block 2 (`__NEXT_DATA__` -> `props.pageProps.initialReduxState.propertyDetails`, as `p`):

| Output key | Source path |
|---|---|
| `url` | `p.href` |
| `property_id`, `listing_id`, `status` | same names |
| `flags` | names of `p.flags.*` that are `true` |
| `list_price`, `price_per_sqft`, `list_date`, `photo_count` | same names |
| `last_update`, `days_on_mls` | `source.last_update_date`, `source.days_on_mls` |
| `address`, `unit`, `city`, `state`, `zip` | `location.address.line/unit/city/state_code/postal_code` |
| `county`, `neighborhoods` | `location.county.name`, names in `location.neighborhoods[]` |
| `type`, `sub_type`, `beds`, `baths`, `baths_full`, `baths_half`, `sqft`, `lot_sqft`, `year_built`, `stories`, `garage` | `description.*` (`baths` is `baths_consolidated`, a string) |
| `hoa_fee` | `hoa.fee` |
| `estimate` | `estimates.current_values[]` entry with `isbest_homevalue` |
| `property_tax_rate` | `mortgage.property_tax_rate` |
| `broker` | `advertisers[]` entry with `type == "seller"` -> `broker.name` |
| `remarks` | `description.text` |
| `details` | `details[]` as `{category: text[]}` |

Other listing keys seen but not returned: `photos[]`, `other_listings.rdc[]` (earlier listings of the same property), `source.agents`, `consumer_advertisers`, `suppression_flags`.

Block 3 prints `name`, `price`, `availability`, `beds`, `baths`, `sqft`, `year_built`, `type`, `date_posted`, `photos` (count of `mainEntity.photo` entries, strings or `ImageObject`s) and `summary` (`description`), all from the listing's `RealEstateListing` JSON-LD.

## Gotchas

- **No HTTP shortcut.** Plain HTTP is blocked (status 429 on the first request for search and listing URLs); this skill uses a normal browser session. That session loaded every page tried, about 30 navigations in the first run with 2-3 s pauses, with no challenge page and no 429. If one does appear, the blocks retry only within fixed bounds and then raise: blocks 1 and 3 load a page with no data at most 3 times (5 s, then 10 s apart); block 2 fetches a listing at most 4 times, honoring `Retry-After` up to 120 s, and stops the batch at once if the server asks for longer. After a raise, back off; neither block changes session, identity or network to get past a 429 or challenge.
- **The DOM is lazy.** Right after load, only 8-10 `[data-testid="property-card"]` cards were rendered (two loads), next to 32-34 `property-card-skeleton` placeholders. The count varies per load. The loader data already had all 42 rows, so read that, not the cards.
- **Search JSON-LD lacks usable baths and status.** Search pages carry a `CollectionPage` -> `ItemList` of 42 `RealEstateListing` items with name, URL, price (as a string), beds, sqft, address and geo. A few items carry `numberOfBathroomsTotal` with an empty value (7 of 42 in one check); the rest have no baths key. There is no status and no total. The router loader data has all of them.
- **`__NEXT_DATA__` on search pages is a stub** (`{"props":{"pageProps":{"geo":{"area_type":"city"}}}}`). Search moved to React Router. Listing pages still use Next.js.
- **Two apps, two globals.** `window.__reactRouterDataRouter` exists on search pages only. On listing pages, use `#__NEXT_DATA__` or JSON-LD.
- **`js()` gives up after about 5 s.** In browser-harness, a slow `Runtime.evaluate` raises `RuntimeError("Runtime.evaluate timed out ...")`, and a slow `goto_url()` can raise `TimeoutError` (the daemon's IPC wait is 5 s). The blocks catch both, then decide by checking the tab's URL and data. That is also why block 2 starts each `fetch()` in the page and polls for the result instead of awaiting it inside one `js()` call.
- **Status.** For-sale searches include pending and contingent homes, and `status` stays `for_sale` for them. Read `statusText` or `flags.is_pending` / `flags.is_contingent`. The site's "Hide pending / contingent" filter chip exists, but its URL segment was not tested here.
- **`total` can move by one between pages** (7010, then 7009) because listings change live. Block 1 dedupes on `property_id` and keeps any row without one.
- **Filters and sort are URL path segments.** `/beds-3/price-na-500000` returned `total=2276`, from 7009 unfiltered. `/sby-1` and `/sby-2` changed the order, but the first rows were not strictly sorted by price, so sort client-side when order matters. Block 1 builds plain location URLs only; filters combined with `/pg-N` were not tested.
- **City slug format** is `City_ST` with hyphens for spaces (`San-Francisco_CA` gave `total=1467`). A ZIP works as is (`78704`).
- **Personal data.** Listing JSON-LD (`offers.seller.employee`) and `propertyDetails` (`source.agents`, `consumer_advertisers`) include listing agents' names, emails and phone numbers. The blocks above leave those out on purpose; keep them out of stored output.
- **Suppression flags.** Each listing has `suppression_flags` (for example `has_suppress_sold_price`, `has_suppress_ai_distribution`) set by the data provider. Check them before you republish or redistribute listing data.
- **No consent banner** appeared in the US cloud browser sessions.
- **Load time** was 2-16 s per search page. `read_srp()` polls for up to 20 s per load and `load_page()` tries 3 loads before raising.

## What does not work

- Plain HTTP (`http_get`, urllib, curl) on `www.realtor.com` search or listing URLs: blocked with HTTP 429 on the first request.
- Reading listing cards from the DOM right after load: only 8-10 of 42 render until you scroll.
- Search-page `__NEXT_DATA__`: empty stub, no listings.
- Search-page JSON-LD alone: no usable baths, no status, no total.
- Pages past the end (`/78704/pg-11` when `total=398`) return 0 rows rather than an error. Block 1 stops at the first short page, so it never requests them.
- An unknown location (`Nowhereville_ZZ`): the page loads with the title "For Sale - Realtor.com" but no search data, so block 1 raises `no search data` after its retries rather than saving an empty result.
- An unknown listing slug: `fetch()` returned 200 after a redirect to `/realestateandhomes-search/Austin_TX`, with no `propertyDetails`. Block 2 treats that as a failed listing and does not retry it.
