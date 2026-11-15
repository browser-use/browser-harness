# Rightmove — Scrape for-sale and to-rent listings

Field-tested against www.rightmove.co.uk on 2026-10-23 using a Browser Use cloud browser and plain HTTP (`urllib`).

robots.txt (checked 2026-10-23) allows `/property-for-sale/find.html`, `/property-to-rent/find.html` and `/properties/<id>` for all user agents; `los.rightmove.co.uk/robots.txt` answered HTTP 401 (no file served).

## Quick summary

- Search result pages (`/property-for-sale/find.html`, `/property-to-rent/find.html`) are Next.js pages. Every listing on the page is in `<script id="__NEXT_DATA__">` at `props.pageProps.searchResults.properties`. A plain HTTP GET gets it, no browser needed.
- A free-text place ("Bristol", "Camden Town", "BS8") must first be turned into a `locationIdentifier` like `REGION^219` or `OUTCODE^295` with the public typeahead endpoint `https://los.rightmove.co.uk/typeahead`.
- 24 organic listings per page plus 1 "featured" slot (25 objects). Paginate with `index=0, 24, 48 ...`. Hard cap: 42 pages / `index=984` (about 1,000 listings) even when `resultCount` is higher. The code below reports when it hits that cap.
- Property pages (`/properties/<id>`) embed `window.__PAGE_MODEL`, a flattened JSON graph. Decode it to get key features, full description, tenure, council tax band, nearest stations and (for rentals) deposit / furnishing / available date. Plain HTTP to property pages is blocked (status 429); this skill reads them in a normal browser session.
- Plain-HTTP requests (typeahead and search pages only) send a truthful client User-Agent naming this skill. An HTTP 403/429 whose body says the service is "for the use of Rightmove Group Limited only" is an access block: `fetch()` stops and raises. Back off; do not retry or change the client to get past it.
- In the browser the same two payloads are readable with `js(...)`. The OneTrust cookie dialog appears but does not block reading them.

## What works

### 1. Location lookup + paginated listings (plain HTTP, no browser)

Plain Python, runs with `python3` or inside `browser-harness`. `scrape()` returns why it stopped: `last_page` (a successful page had no `next`), `max_pages` (your limit, more pages exist) or `rightmove_page_cap` (page 42 reached, `resultCount` is larger). Failed requests are retried, then raise; they never look like the end of the results.

```python
import re, json, time, gzip, email.utils, urllib.parse, urllib.request, urllib.error
from datetime import timezone

HEADERS = {
    "User-Agent": "browser-harness-rightmove-skill/1.0 (+https://github.com/browser-use/browser-harness)",  # truthful client UA
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip",
}
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_WAIT = 120  # seconds; a longer Retry-After stops instead of sleeping
PER_PAGE, MAX_INDEX = 24, 984  # Rightmove serves at most 42 pages per search
CHANNEL_PATHS = {"buy": "property-for-sale", "rent": "property-to-rent"}

def _retry_after(value):
    """Retry-After is either seconds or an HTTP-date. Returns seconds or None."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, dt.timestamp() - time.time())

def _decode(body, headers):
    if headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)
    return body.decode("utf-8", "replace")

def fetch(url, accept="text/html", tries=4):
    """GET -> (status, final_url, text). Retries 429/5xx/network errors with backoff, then raises.
    Raises at once on a 403/429 "Rightmove Group Limited only" access block or a Retry-After over MAX_WAIT.
    Other HTTP errors (400, 404, 410) are returned for the caller to handle."""
    last = None
    for attempt in range(tries):
        wait = None
        try:
            req = urllib.request.Request(url, headers={**HEADERS, "Accept": accept})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.geturl(), _decode(r.read(), r.headers)
        except urllib.error.HTTPError as e:
            body = _decode(e.read(), e.headers)
            if e.code in (403, 429) and "for the use of Rightmove Group Limited only" in body:
                raise RuntimeError(f"HTTP {e.code} access block on {url}; stop and back off, do not retry")
            if e.code not in RETRY_STATUS:
                return e.code, url, body
            last, wait = f"HTTP {e.code}", _retry_after(e.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = repr(e)
        if attempt == tries - 1:
            break  # no sleep after the final attempt
        delay = wait if wait is not None else 2 * 2 ** attempt
        if delay > MAX_WAIT:
            raise RuntimeError(f"{url}: server asked to wait {delay:.0f}s (over {MAX_WAIT}s); stopping")
        time.sleep(delay)
    raise RuntimeError(f"giving up on {url} after {tries} tries: {last}")

def _norm(s):
    return " ".join(re.sub(r"[^\w\s]", " ", s or "").lower().split())

def find_location(query):
    """Free text -> list of (locationIdentifier, displayName), best first. Punctuation breaks the endpoint (HTTP 400)."""
    url = "https://los.rightmove.co.uk/typeahead?" + urllib.parse.urlencode({"query": _norm(query), "limit": 10, "exclude": "STREET"})
    status, _, text = fetch(url, accept="application/json")  # without this Accept you get XML
    if status != 200:
        raise RuntimeError(f"typeahead HTTP {status} for {query!r}")
    return [(f"{m['type']}^{m['id']}", m.get("displayName")) for m in json.loads(text).get("matches") or []]

def pick_location(query):
    """First typeahead match whose displayName starts with the query. Raises instead of guessing."""
    matches = find_location(query)
    for loc_id, name in matches:
        if _norm(name).startswith(_norm(query)):
            return loc_id, name
    raise LookupError(f"no Rightmove location starting with {query!r}; candidates: {matches}")

def search_page(location_id, channel="buy", index=0, **filters):
    """One results page. None if Rightmove redirected to /page-not-found (unknown location or index past 984)."""
    if channel not in CHANNEL_PATHS:
        raise ValueError(f"channel must be 'buy' or 'rent', got {channel!r}")
    path = CHANNEL_PATHS[channel]
    params = {"locationIdentifier": location_id, "index": index, **filters}
    url = f"https://www.rightmove.co.uk/{path}/find.html?" + urllib.parse.urlencode(params)  # ^ -> %5E
    status, final_url, html = fetch(url)
    if status != 200:
        raise RuntimeError(f"HTTP {status} for {url}")
    if urllib.parse.urlparse(final_url).path == "/page-not-found":
        return None
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError(f"no __NEXT_DATA__ on {final_url} (blocked or layout changed)")
    sr = json.loads(m.group(1))["props"]["pageProps"]["searchResults"]
    sp = sr.get("searchParameters") or {}
    if sp.get("index") != str(index) or sp.get("locationIdentifier") != location_id:
        raise RuntimeError(f"asked for {location_id} index {index}, got {sp.get('locationIdentifier')} index {sp.get('index')}")
    return sr

def _d(x):
    return x if isinstance(x, dict) else {}

def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None

def _text(x):
    return " ".join(x.split()) if isinstance(x, str) else None

def to_row(p):
    price = _d(p.get("price"))
    dps = price.get("displayPrices") if isinstance(price.get("displayPrices"), list) else []
    dp = _d(dps[0]) if dps else {}
    pid = p.get("id")
    return {
        "id": pid,
        "address": _text(p.get("displayAddress")),
        "price": _num(price.get("amount")),
        "price_text": " ".join(x for x in [dp.get("displayPriceQualifier"), dp.get("displayPrice")] if isinstance(x, str) and x),
        "frequency": price.get("frequency"),
        "beds": _num(p.get("bedrooms")),
        "baths": _num(p.get("bathrooms")),
        "type": p.get("propertySubType"),
        "agent": _d(p.get("customer")).get("branchDisplayName"),
        "added_or_reduced": p.get("addedOrReduced"),
        "first_visible": p.get("firstVisibleDate"),
        "featured": p.get("featuredProperty"),
        "url": f"https://www.rightmove.co.uk/properties/{pid}" if pid is not None else None,
    }

def _count(x):
    s = str(x or "").replace(",", "")
    return int(s) if s.isdigit() else None

def scrape(query, channel="buy", max_pages=2, **filters):
    loc_id, name = pick_location(query)
    rows, seen, total, pages, stopped = [], set(), None, 0, "max_pages"
    for n in range(max_pages):
        index = n * PER_PAGE
        if index > MAX_INDEX:
            stopped = "rightmove_page_cap"
            break
        sr = search_page(loc_id, channel, index=index, **filters)
        if sr is None:
            raise RuntimeError(f"{loc_id} index {index} redirected to /page-not-found")
        pages += 1
        total = _count(sr.get("resultCount"))
        props = sr.get("properties") or []
        for p in props:
            pid = p.get("id")
            if pid is not None and pid in seen:  # featured listings also show up organically on other pages
                continue
            if pid is not None:
                seen.add(pid)
            rows.append(to_row(p))
        has_next = bool(_d(sr.get("pagination")).get("next"))
        if not has_next:
            capped = index == MAX_INDEX and total is not None and total > MAX_INDEX + PER_PAGE
            stopped = "rightmove_page_cap" if capped else "last_page"
            break
        if not props:
            raise RuntimeError(f"empty page at index {index} but pagination says there is more")
        time.sleep(1.5)  # polite pacing
    return {"location": name, "location_id": loc_id, "result_count": total,
            "pages": pages, "stopped": stopped, "rows": rows}

for query, channel, max_pages, filters in [
    ("Bristol", "buy", 2, {"sortType": 6, "minBedrooms": 2, "maxPrice": 400000}),
    ("Camden Town", "rent", 20, {}),
]:
    res = scrape(query, channel=channel, max_pages=max_pages, **filters)
    print(res["location"], res["location_id"], "results:", res["result_count"], "pages:", res["pages"],
          "stopped:", res["stopped"], "rows:", len(res["rows"]))
    for r in res["rows"][:2]:
        print(r)
```

Real output (trimmed):

```
Bristol REGION^219 results: 1994 pages: 2 stopped: max_pages rows: 50
{'id': 94594029, 'address': 'Bowden Place, Downend', 'price': 285000, 'price_text': '£285,000', 'frequency': 'not specified', 'beds': 2, 'baths': 1, 'type': 'End of Terrace', 'agent': 'Ocean, Downend', 'added_or_reduced': 'Added yesterday', 'first_visible': '2026-10-22T09:59:03Z', 'featured': True, 'url': 'https://www.rightmove.co.uk/properties/94594029'}
{'id': 94681503, 'address': 'St. Georges Avenue, St. George', 'price': 345000, 'price_text': '£345,000', 'frequency': 'not specified', 'beds': 3, 'baths': 2, 'type': 'Semi-Detached', 'agent': 'Boardwalk, covering Bristol and surrounding areas', 'added_or_reduced': 'Added today', ...
Camden Town, North West London REGION^85262 results: 297 pages: 13 stopped: last_page rows: 297
{'id': 94627404, 'address': 'Arlington Road, London, NW1', 'price': 2200, 'price_text': '£2,200 pcm', 'frequency': 'monthly', 'beds': 1, 'baths': None, 'type': 'Apartment', 'agent': 'The Chant Group, Bank', ...
{'id': 94455528, 'address': 'Engine House Way, Lansdowne House, NW1', 'price': 4750, 'price_text': '£4,750 pcm', 'frequency': 'monthly', 'beds': 2, 'baths': 2, 'type': 'Flat', 'agent': 'Austin Homes London, London', ...
```

Camden Town shows a complete run: 13 pages, 297 unique rows = `resultCount`. A separate run of `scrape("Bristol", "buy", max_pages=50)` (unfiltered, 3,748 results) fetched 42 pages in 98 s and stopped with `rightmove_page_cap` and 1,038 unique rows.

### 2. Property page: key features and details (browser)

Plain-HTTP requests to property pages got HTTP 429 with a notice that the API "is for the use of Rightmove Group Limited only", so this skill reads property pages in a normal browser session. Self-contained. `get_property()` returns `None` only when the page answered 404/410 (removed listing); anything else unexpected raises.

```python
import json, time, html as htmllib, urllib.parse

def _is_timeout(e):
    return isinstance(e, TimeoutError) or "timed out" in str(e)

def retry_browser(fn, *args, tries=3):
    """Browser calls can time out on a slow cloud browser: TimeoutError, or RuntimeError('... timed out ...')."""
    for attempt in range(tries):
        try:
            return fn(*args)
        except (TimeoutError, RuntimeError) as e:
            if not _is_timeout(e) or attempt == tries - 1:
                raise
            time.sleep(2)

def open_and_confirm(url, check_js, first=False, timeout=30):
    """Navigate, then poll check_js until it returns 'ok' (True) or 'not_found' (False)."""
    retry_browser(new_tab if first else goto_url, url)
    if first:
        activate_tab(current_tab())  # a hidden background tab stalled in the cloud browser
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = retry_browser(js, check_js)
        if state in ("ok", "not_found"):
            return state == "ok"
        time.sleep(0.5)
    raise TimeoutError(f"{url} not confirmed after {timeout}s; tab is at {retry_browser(js, 'location.href')}")

def search_check(location_id, index):
    return f"""(() => {{
      if (location.pathname === '/page-not-found') return 'not_found';
      const s = document.getElementById('__NEXT_DATA__');
      if (!s) return 'wait';
      const sp = JSON.parse(s.textContent)?.props?.pageProps?.searchResults?.searchParameters || {{}};
      return sp.index === {json.dumps(str(index))} && sp.locationIdentifier === {json.dumps(location_id)} ? 'ok' : 'wait';
    }})()"""

def property_check(property_id):
    return f"""(() => {{
      if (location.pathname !== {json.dumps(f'/properties/{property_id}')}) return 'wait';
      const nav = performance.getEntriesByType('navigation')[0];
      if (nav && [404, 410].includes(nav.responseStatus)) return 'not_found';
      return window.__PAGE_MODEL ? 'ok' : 'wait';
    }})()"""

def decode_page_model(pm):
    """window.__PAGE_MODEL = {"data": "<json array>", "encoding": "on"}.
    Every value inside an object/array is an index into that array; resolve recursively."""
    arr = json.loads(pm["data"])
    memo = {}
    def r(i):
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(arr):
            return None
        if i in memo:
            return memo[i]
        v = arr[i]
        if isinstance(v, dict):
            out = memo[i] = {}
            out.update({k: r(x) for k, x in v.items()})
        elif isinstance(v, list):
            out = memo[i] = []
            out.extend(r(x) for x in v)
        else:
            out = v
        return out
    return r(0)

def _d(x):
    return x if isinstance(x, dict) else {}

def _station(s):
    s = _d(s)
    dist = s.get("distance")
    return (s.get("name"), round(dist, 2) if isinstance(dist, (int, float)) and not isinstance(dist, bool) else None, s.get("unit"))

def get_property(property_id, first=False):
    """Decoded property page, or None if the listing is gone (404/410)."""
    url = f"https://www.rightmove.co.uk/properties/{property_id}"
    if not open_and_confirm(url, property_check(property_id), first=first):
        return None
    pm = json.loads(retry_browser(js, "JSON.stringify(window.__PAGE_MODEL)"))
    pd = _d(_d(decode_page_model(pm)).get("propertyData"))
    if str(pd.get("id")) != str(property_id):
        raise RuntimeError(f"asked for {property_id}, page model is for {pd.get('id')}")
    addr = _d(pd.get("address"))
    return {
        "id": pd.get("id"),
        "address": " ".join((addr.get("displayAddress") or "").split()),
        "postcode": " ".join(x for x in [addr.get("outcode"), addr.get("incode")] if isinstance(x, str) and x),
        "price": _d(pd.get("prices")).get("primaryPrice"),
        "beds": pd.get("bedrooms"),
        "baths": pd.get("bathrooms"),
        "type": pd.get("propertySubType"),
        "tenure": _d(pd.get("tenure")).get("tenureType"),
        "council_tax_band": _d(pd.get("livingCosts")).get("councilTaxBand"),
        "key_features": [htmllib.unescape(k) for k in pd.get("keyFeatures") or [] if isinstance(k, str)],  # may be empty
        "added": _d(pd.get("listingHistory")).get("listingUpdateReason"),
        "agent": _d(pd.get("customer")).get("branchDisplayName"),
        "stations": [_station(s) for s in pd.get("nearestStations") or []],
        "description_html": _d(pd.get("text")).get("description"),
        "lettings": pd.get("lettings"),  # deposit / let type / furnishing for rentals, None for sales
    }

def first_ids(path, location_id, n=2, first=False):
    url = f"https://www.rightmove.co.uk/{path}/find.html?" + urllib.parse.urlencode({"locationIdentifier": location_id, "index": 0})
    if not open_and_confirm(url, search_check(location_id, 0), first=first):
        raise RuntimeError(f"{url} redirected to /page-not-found")
    sr = json.loads(retry_browser(js, "document.getElementById('__NEXT_DATA__').textContent"))["props"]["pageProps"]["searchResults"]
    return [p["id"] for p in sr.get("properties") or [] if p.get("id") is not None and not p.get("featuredProperty")][:n]

ids = first_ids("property-for-sale", "REGION^219", first=True)
time.sleep(1.5)
ids += first_ids("property-to-rent", "REGION^85262") + [1]  # 1 = a removed id
for pid in ids:
    time.sleep(1.5)
    prop = get_property(pid)
    if prop is None:
        print(pid, "listing not available (404/410)")
        continue
    print({k: v for k, v in prop.items() if k != "description_html"})
    print(len(prop["description_html"] or ""), "chars of description HTML")
```

Real output (trimmed):

```
{'id': '94488843', 'address': 'Discreet property in this area - Call for details', 'postcode': 'BS9 1LJ', 'price': '£3,750,000', 'beds': 6, 'baths': 4, 'type': 'Detached', 'tenure': 'FREEHOLD', 'council_tax_band': 'H', 'key_features': [], 'added': 'Added on 19/10/2026', 'agent': 'Goodman & Lilley, Henleaze', 'stations': [('Sea Mills Station', 0.75, 'miles'), ('Clifton Down Station', 1.57, 'miles'), ('Redland Station', 1.76, 'miles')], 'lettings': None}
304 chars of description HTML
{'id': '173429669', 'address': 'Clifton, Bristol, BS8', 'postcode': 'BS8 3EW', 'price': '£3,250,000', 'beds': 6, 'baths': 4, 'type': 'Semi-Detached', 'tenure': 'FREEHOLD', 'council_tax_band': 'H', 'key_features': ['Elegant circa 5400 sq. ft semi-detached family house', 'Gated off-street parking for three to five vehicles', ...
5095 chars of description HTML
{'id': '94455528', 'address': 'Engine House Way, Lansdowne House, NW1', 'postcode': 'NW1 8BT', 'price': '£4,750 pcm', 'beds': 2, 'baths': 2, 'type': 'Flat', 'tenure': None, 'council_tax_band': None, 'key_features': ['Fully Furnished', 'Private Balcony', '2 beds | 2 baths', 'Available now'], 'added': 'Reduced today', 'agent': 'Austin Homes London, London', 'stations': [('Chalk Farm Station', 0.22, 'miles'), ...], 'lettings': {'letAvailableDate': 'Ask agent', 'deposit': 5596, 'minimumTermInMonths': None, 'letType': 'Long term', 'furnishType': 'Furnished'}}
1302 chars of description HTML
{'id': '94452012', 'address': 'Camden Road, Holloway, N7', 'postcode': 'N7 0DN', 'price': '£1,900 pcm', 'beds': 1, 'baths': 1, 'type': 'Flat', 'tenure': None, 'council_tax_band': 'C', ... 'lettings': {'letAvailableDate': '03/12/2026', 'deposit': 2192, 'minimumTermInMonths': 12, 'letType': 'Long term', 'furnishType': 'Furnished'}}
849 chars of description HTML
1 listing not available (404/410)
```

### 3. Same data through the browser

Use this when you are already driving a tab. Pagination is by URL, no clicking needed. The first `new_tab()` is followed by one `activate_tab()`: in a fresh cloud browser a hidden background tab stalled (see Gotchas).

Each navigation is confirmed before parsing: a search page counts as loaded only when its `__NEXT_DATA__` echoes the requested `index` and `locationIdentifier`, and a property page only when `location.pathname` is `/properties/<id>` and the decoded id matches. That stops the code from reading the previous page. Browser calls that time out are retried.

```python
import json, time, urllib.parse

def _is_timeout(e):
    return isinstance(e, TimeoutError) or "timed out" in str(e)

def retry_browser(fn, *args, tries=3):
    """Browser calls can time out on a slow cloud browser: TimeoutError, or RuntimeError('... timed out ...')."""
    for attempt in range(tries):
        try:
            return fn(*args)
        except (TimeoutError, RuntimeError) as e:
            if not _is_timeout(e) or attempt == tries - 1:
                raise
            time.sleep(2)

def open_and_confirm(url, check_js, first=False, timeout=30):
    """Navigate, then poll check_js until it returns 'ok' (True) or 'not_found' (False)."""
    retry_browser(new_tab if first else goto_url, url)
    if first:
        activate_tab(current_tab())  # a hidden background tab stalled in the cloud browser
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = retry_browser(js, check_js)
        if state in ("ok", "not_found"):
            return state == "ok"
        time.sleep(0.5)
    raise TimeoutError(f"{url} not confirmed after {timeout}s; tab is at {retry_browser(js, 'location.href')}")

def search_check(location_id, index):
    return f"""(() => {{
      if (location.pathname === '/page-not-found') return 'not_found';
      const s = document.getElementById('__NEXT_DATA__');
      if (!s) return 'wait';
      const sp = JSON.parse(s.textContent)?.props?.pageProps?.searchResults?.searchParameters || {{}};
      return sp.index === {json.dumps(str(index))} && sp.locationIdentifier === {json.dumps(location_id)} ? 'ok' : 'wait';
    }})()"""

def property_check(property_id):
    return f"""(() => {{
      if (location.pathname !== {json.dumps(f'/properties/{property_id}')}) return 'wait';
      const nav = performance.getEntriesByType('navigation')[0];
      if (nav && [404, 410].includes(nav.responseStatus)) return 'not_found';
      return window.__PAGE_MODEL ? 'ok' : 'wait';
    }})()"""

def decode_page_model(pm):
    arr = json.loads(pm["data"])
    memo = {}
    def r(i):
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(arr):
            return None
        if i in memo:
            return memo[i]
        v = arr[i]
        if isinstance(v, dict):
            out = memo[i] = {}
            out.update({k: r(x) for k, x in v.items()})
        elif isinstance(v, list):
            out = memo[i] = []
            out.extend(r(x) for x in v)
        else:
            out = v
        return out
    return r(0)

def _d(x):
    return x if isinstance(x, dict) else {}

base = "https://www.rightmove.co.uk/property-to-rent/find.html?"
location_id = "REGION^219"
params = {"locationIdentifier": location_id, "maxBedrooms": 2}
rows, seen, stopped = [], set(), "max_pages"
for n in range(2):
    index = n * 24
    if not open_and_confirm(base + urllib.parse.urlencode({**params, "index": index}), search_check(location_id, index), first=(n == 0)):
        raise RuntimeError(f"index {index} redirected to /page-not-found")
    sr = json.loads(retry_browser(js, "document.getElementById('__NEXT_DATA__').textContent"))["props"]["pageProps"]["searchResults"]
    for p in sr.get("properties") or []:
        pid = p.get("id")
        if pid is not None and pid in seen:
            continue
        if pid is not None:
            seen.add(pid)
        dps = _d(p.get("price")).get("displayPrices")
        dp = _d(dps[0]) if isinstance(dps, list) and dps else {}
        rows.append((pid, " ".join((p.get("displayAddress") or "").split()), dp.get("displayPrice"),
                     p.get("bedrooms"), p.get("propertySubType"), _d(p.get("customer")).get("branchDisplayName"), p.get("addedOrReduced")))
    pg = _d(sr.get("pagination"))
    print("page", pg.get("page"), "of", pg.get("total"), "| results", sr.get("resultCount"))
    if not pg.get("next"):
        stopped = "last_page"
        break
    time.sleep(1.5)
print(len(rows), "rows, stopped:", stopped)
for r in rows[:3]:
    print(r)

if rows and rows[0][0] is not None:
    pid = rows[0][0]
    time.sleep(1.5)
    if not open_and_confirm(f"https://www.rightmove.co.uk/properties/{pid}", property_check(pid)):
        raise RuntimeError(f"property {pid} answered 404/410")
    pd = _d(decode_page_model(json.loads(retry_browser(js, "JSON.stringify(window.__PAGE_MODEL)"))).get("propertyData"))
    if str(pd.get("id")) != str(pid):
        raise RuntimeError(f"asked for {pid}, page model is for {pd.get('id')}")
    print(pd.get("id"), _d(pd.get("prices")).get("primaryPrice"), pd.get("keyFeatures"), pd.get("lettings"))
```

Real output (trimmed):

```
page 1 of 42 | results 1,142
page 2 of 42 | results 1,142
50 rows, stopped: max_pages
(91003179, 'Back Room, Oldbury Court Road, Fishponds', '£825 pcm', 1, 'House Share', 'Goldsmith Property, Covering Bristol', 'Reduced on 28/09/2026')
(94680672, 'Westbourne Place, Clifton, Bristol, BS8', '£1,295 pcm', 1, 'Flat', 'OpenRent, London', 'Reduced today')
(94679040, 'Princess Victoria Street, Clifton, Bristol, BS8', '£1,790 pcm', 2, 'Apartment', 'CJ Hole, Bishopston', 'Added today')
91003179 £825 pcm [] {'letAvailableDate': 'Now', 'deposit': 900, 'minimumTermInMonths': None, 'letType': 'Long term', 'furnishType': 'Furnished'}
```

## Fields

Example 1, `scrape()` returns `{"location", "location_id", "result_count", "pages", "stopped", "rows"}`. Each row:

| Key | Source in `searchResults.properties[i]` | Example |
|---|---|---|
| `id` | `id` (int) | `88550319` |
| `address` | `displayAddress`, whitespace collapsed | `"Parson Street, Bedminster, Bristol, BS3"`, `"Engine House Way, Lansdowne House, NW1"` (street + area + outcode at most) |
| `price` | `price.amount` (int GBP, per `frequency`) | `342500`; `1673` with frequency `"weekly"` for a `"£7,250 pcm"` rental |
| `price_text` | `price.displayPrices[0]` qualifier + price | `"£342,500"`, `"£4,750 pcm"` |
| `frequency` | `price.frequency` | `"not specified"` (sale), `"monthly"` or `"weekly"` (rent) |
| `beds`, `baths` | `bedrooms`, `bathrooms` | `3`, `1` |
| `type` | `propertySubType` | `"Terraced"`, `"Flat"` |
| `agent` | `customer.branchDisplayName` | `"CJ Hole, Southville"` |
| `added_or_reduced` | `addedOrReduced` | `"Added on 15/05/2026"`, `"Reduced today"` (dd/mm/yyyy) |
| `first_visible` | `firstVisibleDate` | `"2026-05-15T15:36:54Z"` |
| `featured` | `featuredProperty` | `true` on the 1 paid slot per page |
| `url` | built from `id` | `https://www.rightmove.co.uk/properties/88550319` |

Example 2, `get_property()` returns (from decoded `__PAGE_MODEL` -> `propertyData`):

| Key | Source | Example |
|---|---|---|
| `id` | `id` (string here) | `"94455528"` |
| `address` | `address.displayAddress` | `"Engine House Way, Lansdowne House, NW1"` |
| `postcode` | `address.outcode` + `address.incode` | `"NW1 8BT"` |
| `price` | `prices.primaryPrice` | `"£350,000"`, `"£4,750 pcm"` |
| `beds`, `baths`, `type` | `bedrooms`, `bathrooms`, `propertySubType` | `2`, `2`, `"Flat"` |
| `tenure` | `tenure.tenureType` | `"FREEHOLD"`, `None` on rentals |
| `council_tax_band` | `livingCosts.councilTaxBand` | `"H"`, can be `None` |
| `key_features` | `keyFeatures`, HTML-unescaped | `["Fully Furnished", "Private Balcony", ...]`, may be `[]` |
| `added` | `listingHistory.listingUpdateReason` | `"Added on 19/10/2026"` |
| `agent` | `customer.branchDisplayName` | `"Austin Homes London, London"` |
| `stations` | `nearestStations[]` as `(name, miles, unit)` | `("Chalk Farm Station", 0.22, "miles")` |
| `description_html` | `text.description` | HTML string |
| `lettings` | `lettings` | `{"letAvailableDate", "deposit", "minimumTermInMonths", "letType", "furnishType"}`, `None` for sales |

Example 3 rows are tuples `(id, address, display price, beds, property sub type, agent, added_or_reduced)` from the same `properties[i]` fields; the last line prints `propertyData.id`, `prices.primaryPrice`, `keyFeatures`, `lettings`.

Other fields seen in the payloads but not returned by the code: `searchResults.location.displayName`, `searchResults.searchParameters` (echo of the applied filters), per listing `location.latitude/longitude`, `propertyImages.images[].srcUrl`, `letAvailableDate`, `tenure.tenureType`, `listingUpdate`, `summary`; per property page `features.parking`, `features.garden`.

## URL parameters (observed)

| Parameter | Values seen | Effect |
|---|---|---|
| `locationIdentifier` | `REGION^219`, `REGION^85262`, `OUTCODE^295`, `STATION^1712` | From typeahead `type^id`. URL-encode `^` as `%5E` (`urlencode` does it). `STATION^...` searches default to `radius=0.5` (miles) |
| `index` | `0, 24, ... 984` | Page offset. `1008` and above redirect to `/page-not-found` |
| `sortType` | `2` (for-sale default, highest price first), `6` (rent default, most recent first) | |
| `minBedrooms`, `maxBedrooms`, `maxPrice` | `2`, `400000` | Applied server-side: Bristol for sale went from 3,748 to 1,991 results with `minBedrooms=2&maxPrice=400000` |

## Gotchas

- **Access block.** Plain-HTTP requests to property pages returned HTTP 429 with a body saying the API "is for the use of Rightmove Group Limited only". That is an access block, not a rate limit: example 1's `fetch()` raises on a 403/429 with that text instead of retrying, and property pages are read in the browser (examples 2 and 3). The same sentence also appears inside normal property-page payloads, so only treat it as a block on a 403/429.
- **Retry-After.** Example 1's `fetch()` honours `Retry-After` (seconds or HTTP-date) up to 120 s and raises if the server asks for longer. It never sleeps after the last attempt.
- **Channel.** `search_page()` and `scrape()` accept only `channel="buy"` or `"rent"`; anything else raises `ValueError`.
- **Typeahead rejects punctuation.** `query=Clifton, Bristol` returned HTTP 400; `Clifton Bristol` worked. The helper strips punctuation first.
- **Typeahead returns XML unless you send `Accept: application/json`.**
- **Ambiguous places.** `Clifton` returns Clifton in Bristol, Nottingham, York and more; `Camden Town` returns the London region first, then the station and Camden Town in Gosport. `pick_location()` takes the top-ranked match whose name starts with your query and raises if none does; print `location` and check it, or pass a longer query ("Clifton Nottingham").
- **Pagination cap.** `pagination.total` never exceeded 42 pages. Page 42 (`index=984`) has no `pagination.next` even when `resultCount` is 3,748, which is why `scrape()` compares `resultCount` with 1,008 to tell the cap from a real last page. `index=1008` redirects to `https://www.rightmove.co.uk/page-not-found` with HTTP 200 and no `__NEXT_DATA__`. An unknown `locationIdentifier` does the same.
- **Featured slot repeats.** Each page has one `featuredProperty: true` listing. For Camden Town rentals, all 4 featured ids on pages 1-4 also appeared as normal results on another of those pages; Bristol and Manchester for-sale pages 1-4 had no repeats. Dedupe by `id`.
- **Rental `price.amount` is per `price.frequency`, not always monthly.** One Camden listing had `amount: 1673`, `frequency: "weekly"` and display price `"£7,250 pcm"`. Normalise with `frequency` before comparing rents.
- **Removed listings answer HTTP 410 Gone** (`/properties/1`). The 410 page still has a `__PAGE_MODEL`, so `property_check()` reads the status from `performance.getEntriesByType('navigation')[0].responseStatus` first.
- **`__PAGE_MODEL` is not plain JSON of the property.** It is `{"data": "<string>", "encoding": "on"}` where `data` is a JSON array and every value in an object or array is an index into that array. The decoder above resolves it. There is no `window.PAGE_MODEL` (without underscores) on the current pages.
- **Background tab stalls.** In a fresh cloud browser, a search page in a hidden `new_tab()` stayed at `readyState` `"interactive"` for 15 s or more (one 30 s wait for `"complete"` timed out), then `Runtime.evaluate` started timing out. After `activate_tab(current_tab())` the same pages reached `"complete"` within about 5 s. Examples 2 and 3 activate their tab once, retry timed-out browser calls, and confirm each page by its payload instead of waiting for `readyState`.
- **Cookie dialog.** "Choose your cookies" (OneTrust) covers the page in the browser. Reading `__NEXT_DATA__` / `__PAGE_MODEL` works without clicking it; click "Reject all" only if you need screenshots or clicks.
- **No JSON-LD.** Property pages have no `application/ld+json`, so do not look for it.
- **Display addresses are partial** (street, area, outcode). The property page adds `incode`, giving the full postcode.
- **Pacing.** 42 consecutive search pages with a 1.5 s sleep all returned 200 with data, no 429 or challenge seen. Keep 1-2 s between requests and do not run many in parallel.

## What does not work

- `https://www.rightmove.co.uk/typeAhead/uknostreet/...` (older lookup path) returned the "We couldn't find the place you were looking for" HTML.
- Going past page 42 of any search (see Gotchas). `index=1008` and above redirect to `/page-not-found`.
- Plain HTTP to property pages: blocked (status 429, body says the API "is for the use of Rightmove Group Limited only"). This skill uses a normal browser session for them.
- Saved searches, alerts, "Save" and agent contact forms need an account; not covered here.
