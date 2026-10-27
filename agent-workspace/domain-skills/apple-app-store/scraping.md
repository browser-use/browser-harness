# Apple App Store — App Details and Search Results

Field-tested against apps.apple.com and itunes.apple.com on 2026-10-23 using a Browser Use cloud browser (and plain HTTP).

robots.txt (checked 2026-10-23): itunes.apple.com disallows `/search*` for all user agents and has no rule that matches `/lookup` (its `/*/lookup?` rule needs a path segment before `lookup`), so it allows the Lookup API; apps.apple.com does not disallow `/<country>/app/` pages and disallows `*/search?*`. This skill calls Apple's documented public iTunes Search API (https://performance-partners.apple.com/search-api, checked 2026-10-23), which documents both `itunes.apple.com/search` and `itunes.apple.com/lookup`. It uses `itunes.apple.com/search` as that documented API even though robots.txt, which is written for crawlers, disallows `/search*`. None of its code blocks request the apps.apple.com search pages.

## Quick summary

- Use the public **iTunes Search/Lookup API** first. No key, no cookies, JSON out:
  - `https://itunes.apple.com/search?term=...&entity=software&country=us&limit=200` - up to 200 apps per query.
  - `https://itunes.apple.com/lookup?id=ID1,ID2,...&country=us` - many app IDs per call (also `bundleId=` and developer `id=` + `entity=software`).
- One API record already has name, developer, average rating, ratings count, price, category, size in bytes, current version, current-version release date and its release notes.
- The app page (`https://apps.apple.com/us/app/id<ID>`) adds what the API lacks: 5-to-1 star histogram, top-chart rank, the new age rating (13+, 9+), and the **25 most recent versions** with dates and notes. It is server-rendered JSON in `<script id="serialized-server-data">`, readable with a plain HTTP GET (status 200).
- In a browser the SPA removes that script after hydration, so re-fetch the page HTML from inside the tab (block 4).
- Search has **no working pagination**: `offset` does not page, `limit` caps at 200. A search result is Apple's top list for that term, not every matching app. Separate topics are separate terms; dedupe their overlap by `trackId`.
- Apple's Search API docs state a limit of about 20 calls per minute. The code below sleeps 3 s between calls, retries 429/5xx and network errors with backoff (honoring `Retry-After` as seconds or HTTP-date), stops and raises if the server asks for more than 120 s, and raises on 403 or any other failure. It never returns a failed call as an empty result.
- Plain HTTP uses a truthful `Python-urllib/3.x` User-Agent. Both hosts answered it with HTTP 200 today.

## What works

### 1. Search apps (3 terms x up to 200 results, deduped)

Plain Python, no browser needed.

```python
import email.utils, json, sys, time, urllib.error, urllib.parse, urllib.request

UA = f"Python-urllib/{sys.version_info.major}.{sys.version_info.minor}"  # truthful client UA
RETRY = {429, 500, 502, 503, 504}  # 403 and other statuses are not retried
MAX_WAIT = 120  # longest backoff this code sleeps; a longer Retry-After stops the run

def retry_after(e, default):
    """Seconds to wait: Retry-After as seconds or HTTP-date, else the default backoff."""
    v = ((getattr(e, "headers", None) or {}).get("Retry-After") or "").strip()
    if v.isdigit():
        return int(v)
    if v:
        try:
            return max(0, email.utils.parsedate_to_datetime(v).timestamp() - time.time())
        except (TypeError, ValueError):
            pass
    return default

def fetch(url, retries=4):
    """GET url and return the body text. None only for HTTP 404. Retries 429/5xx and network
    errors with capped backoff, then raises: a failed call never looks like an empty result."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in RETRY or attempt == retries - 1:
                raise
            wait = retry_after(e, 15 * (attempt + 1))
            if wait > MAX_WAIT:
                raise RuntimeError(f"{url}: server asked to wait {wait:.0f} s (> {MAX_WAIT} s); stopping") from e
            time.sleep(wait)
        except OSError:  # URLError, timeouts, connection resets
            if attempt == retries - 1:
                raise
            time.sleep(15 * (attempt + 1))

def itunes(path, params):
    """GET https://itunes.apple.com/<path>?<params> and return the parsed JSON object."""
    url = f"https://itunes.apple.com/{path}?" + urllib.parse.urlencode(params)  # quotes every value, '/' included
    body = fetch(url)
    data = json.loads(body) if body else None
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise RuntimeError(f"unexpected iTunes response from {url}")
    return data

def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

def text(v):
    return v if isinstance(v, str) else None

def to_row(r):
    size = r.get("fileSizeBytes")
    size = int(size) if isinstance(size, str) and size.isdigit() else num(size)
    rating = num(r.get("averageUserRating"))
    return {
        "id": num(r.get("trackId")),
        "name": text(r.get("trackName")),
        "developer": text(r.get("artistName")),
        "rating": round(rating, 2) if rating is not None else None,
        "ratings_count": num(r.get("userRatingCount")),
        "price": num(r.get("price")),
        "price_label": text(r.get("formattedPrice")),
        "currency": text(r.get("currency")),
        "category": text(r.get("primaryGenreName")),
        "size_mb": round(size / 1e6, 1) if size is not None else None,
        "version": text(r.get("version")),
        "version_date": text(r.get("currentVersionReleaseDate")),
        "release_notes": (text(r.get("releaseNotes")) or "")[:200],
        "first_release": text(r.get("releaseDate")),
        "bundle_id": text(r.get("bundleId")),
        "url": (text(r.get("trackViewUrl")) or "").split("?")[0],
    }

def search_apps(term, country="us", limit=200, entity="software"):
    data = itunes("search", {"term": term, "country": country, "entity": entity, "limit": limit})
    if len(data["results"]) >= limit:
        print(f"WARNING: {term!r} hit the limit={limit} cap; Apple serves no more, so this list is truncated")
    return [to_row(r) for r in data["results"] if r.get("wrapperType") == "software"]

terms = ["habit tracker", "budget planner", "meditation"]
apps = {}
for t in terms:
    rows = search_apps(t)
    print(f"{t!r}: {len(rows)} apps")
    for row in rows:
        key = row["id"] if row["id"] is not None else ("no-id", row["name"], row["developer"])
        apps.setdefault(key, row)  # rows without an id are kept, not merged
    time.sleep(3)  # polite pacing between calls

print("unique apps:", len(apps))
top = sorted(apps.values(), key=lambda a: a["ratings_count"] or 0, reverse=True)[:5]
for a in top:
    print(a["name"], "|", a["developer"], "|", a["rating"], "|", a["ratings_count"], "|",
          a["price_label"], "|", a["category"], "|", a["size_mb"], "MB |", a["version"], a["version_date"])
print(json.dumps(top[0], indent=1))
```

Output:

```
'habit tracker': 193 apps
'budget planner': 192 apps
'meditation': 192 apps
unique apps: 577
Intuit Credit Karma | Credit Karma, Inc. | 4.84 | 7768217 | Free | Finance | 290.1 MB | 26.43 2026-10-20T17:51:18Z
Calm | Calm.com | 4.77 | 1989542 | Free | Health & Fitness | 178.9 MB | 7.3 2026-10-08T20:43:45Z
Microsoft Excel | Microsoft Corporation | 4.75 | 1478514 | Free | Productivity | 462.4 MB | 2.115 2026-10-19T04:02:35Z
Headspace: Sleep & Meditation | Headspace Inc. | 4.84 | 973796 | Free | Health & Fitness | 450.8 MB | 8.37.0 2026-10-20T00:13:27Z
Finch: Self-Care Pet | Finch Care Public Benefit Corporation | 4.95 | 766844 | Free | Health & Fitness | 508.4 MB | 3.73.230 2026-10-22T20:58:35Z
{
 "id": 519817714,
 "name": "Intuit Credit Karma",
 "developer": "Credit Karma, Inc.",
 "rating": 4.84,
 "ratings_count": 7768217,
 "price": 0.0,
 "price_label": "Free",
 "currency": "USD",
 "category": "Finance",
 "size_mb": 290.1,
 "version": "26.43",
 "version_date": "2026-10-20T17:51:18Z",
 "release_notes": "Thanks for using Intuit Credit Karma! Our app is regularly updated to make it easier for you to track your financial progress. This version includes a number of performance improvements and squashes a",
 "first_release": "2012-07-18T07:00:00Z",
 "bundle_id": "com.creditkarma.mobile",
 "url": "https://apps.apple.com/us/app/intuit-credit-karma/id519817714"
}
```

### 2. Look up app IDs in bulk, by bundle ID, by developer, per storefront

```python
import email.utils, json, sys, time, urllib.error, urllib.parse, urllib.request

UA = f"Python-urllib/{sys.version_info.major}.{sys.version_info.minor}"  # truthful client UA
RETRY = {429, 500, 502, 503, 504}  # 403 and other statuses are not retried
MAX_WAIT = 120  # longest backoff this code sleeps; a longer Retry-After stops the run

def retry_after(e, default):
    v = ((getattr(e, "headers", None) or {}).get("Retry-After") or "").strip()
    if v.isdigit():
        return int(v)
    if v:
        try:
            return max(0, email.utils.parsedate_to_datetime(v).timestamp() - time.time())
        except (TypeError, ValueError):
            pass
    return default

def fetch(url, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in RETRY or attempt == retries - 1:
                raise
            wait = retry_after(e, 15 * (attempt + 1))
            if wait > MAX_WAIT:
                raise RuntimeError(f"{url}: server asked to wait {wait:.0f} s (> {MAX_WAIT} s); stopping") from e
            time.sleep(wait)
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(15 * (attempt + 1))

def itunes(path, params):
    url = f"https://itunes.apple.com/{path}?" + urllib.parse.urlencode(params)
    body = fetch(url)
    data = json.loads(body) if body else None
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise RuntimeError(f"unexpected iTunes response from {url}")
    return data

def lookup_ids(app_ids, country="us", chunk=100):
    """Return {trackId: raw_result}. Missing/removed IDs are simply absent; compare against the input."""
    if not isinstance(chunk, int) or isinstance(chunk, bool) or not 1 <= chunk <= 100:
        raise ValueError("chunk must be an integer from 1 to 100 (lookup silently drops IDs past about 210 per call)")
    out = {}
    app_ids = [int(i) for i in app_ids]
    for i in range(0, len(app_ids), chunk):
        batch = app_ids[i:i + chunk]
        data = itunes("lookup", {"id": ",".join(map(str, batch)), "country": country})
        for r in data["results"]:
            if r.get("wrapperType") == "software" and isinstance(r.get("trackId"), int):
                out[r["trackId"]] = r
        time.sleep(3)
    return out

# 1) Many IDs: take the IDs of the top "productivity" search hits
hits = itunes("search", {"term": "productivity", "entity": "software", "country": "us", "limit": 200})["results"]
ids = [r["trackId"] for r in hits if isinstance(r.get("trackId"), int)]
ids.append(1)  # an ID that does not exist
time.sleep(3)
found = lookup_ids(ids)
print(f"requested {len(ids)} ids, got {len(found)}; missing: {[i for i in ids if i not in found]}")

# 2) Single app, all detail fields
app = lookup_ids([389801252]).get(389801252)
if app is None:
    raise SystemExit("app 389801252 not found in this storefront")
print({k: app.get(k) for k in ("trackName", "artistName", "averageUserRating", "userRatingCount",
      "formattedPrice", "primaryGenreName", "fileSizeBytes", "version", "currentVersionReleaseDate",
      "contentAdvisoryRating", "minimumOsVersion")})

# 3) By bundle ID
res = itunes("lookup", {"bundleId": "com.burbn.instagram", "country": "us"})["results"]
print("bundleId ->", [(r.get("trackId"), r.get("trackName")) for r in res])
time.sleep(3)

# 4) Every app from a developer (artistId comes from any app's 'artistId')
dev = itunes("lookup", {"id": app["artistId"], "entity": "software", "country": "us", "limit": 200})["results"]
artist = next((r for r in dev if r.get("wrapperType") == "artist"), {})
print("developer:", artist.get("artistName"), "->", [r.get("trackName") for r in dev if r.get("wrapperType") == "software"][:8])
time.sleep(3)

# 5) Paid app, priced per storefront
for cc in ("us", "gb", "de"):
    r = itunes("lookup", {"id": 963034692, "country": cc})["results"]
    print(cc, [(x.get("trackName"), x.get("price"), x.get("currency"), x.get("formattedPrice")) for x in r])
    time.sleep(3)
```

Output:

```
requested 182 ids, got 181; missing: [1]
{'trackName': 'Instagram', 'artistName': 'Instagram, Inc.', 'averageUserRating': 4.69069, 'userRatingCount': 29626506, 'formattedPrice': 'Free', 'primaryGenreName': 'Photo & Video', 'fileSizeBytes': '660901888', 'version': '452.0.0', 'currentVersionReleaseDate': '2026-10-19T12:27:02Z', 'contentAdvisoryRating': '12+', 'minimumOsVersion': '16.3'}
bundleId -> [(389801252, 'Instagram')]
developer: Instagram, Inc. -> ['Instagram', 'Threads', 'Edits: Video Editor', 'Instants, an Instagram app']
us [('Streaks', 5.99, 'USD', '$5.99')]
gb [('Streaks', 5.99, 'GBP', '£5.99')]
de [('Streaks', 6.99, 'EUR', '6,99\xa0€')]
```

### 3. App page extras: star histogram, chart rank, age rating, version history (plain HTTP)

```python
import email.utils, json, re, sys, time, urllib.error, urllib.request

UA = f"Python-urllib/{sys.version_info.major}.{sys.version_info.minor}"  # truthful client UA
RETRY = {429, 500, 502, 503, 504}  # 403 and other statuses are not retried
MAX_WAIT = 120  # longest backoff this code sleeps; a longer Retry-After stops the run

def retry_after(e, default):
    v = ((getattr(e, "headers", None) or {}).get("Retry-After") or "").strip()
    if v.isdigit():
        return int(v)
    if v:
        try:
            return max(0, email.utils.parsedate_to_datetime(v).timestamp() - time.time())
        except (TypeError, ValueError):
            pass
    return default

def fetch(url, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in RETRY or attempt == retries - 1:
                raise
            wait = retry_after(e, 15 * (attempt + 1))
            if wait > MAX_WAIT:
                raise RuntimeError(f"{url}: server asked to wait {wait:.0f} s (> {MAX_WAIT} s); stopping") from e
            time.sleep(wait)
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(15 * (attempt + 1))

def first(v):
    return v[0] if isinstance(v, list) and v and isinstance(v[0], dict) else {}

def obj(v):
    return v if isinstance(v, dict) else {}

def app_page(app_id, country="us"):
    """Extras only the web page has. None if the app does not exist (HTTP 404); raises on anything else odd."""
    url = f"https://apps.apple.com/{country}/app/id{app_id}"
    html = fetch(url)
    if html is None:
        return None
    m = re.search(r'<script type="application/json" id="serialized-server-data">(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError(f"{url}: no serialized-server-data in the page")
    page = obj(first(obj(json.loads(m.group(1))).get("data")).get("data"))
    lockup = obj(page.get("lockup"))
    if str(lockup.get("adamId")) != str(app_id):
        raise RuntimeError(f"{url}: page is for app {lockup.get('adamId')!r}, not {app_id}")
    sm = obj(page.get("shelfMapping"))
    badges = {b.get("key"): obj(b.get("content"))
              for b in obj(sm.get("informationRibbon")).get("items") or [] if isinstance(b, dict)}
    info = {a.get("title"): a.get("summary")
            for a in obj(sm.get("information")).get("items") or [] if isinstance(a, dict)}
    ratings = first(obj(sm.get("productRatings")).get("items"))
    counts = ratings.get("ratingCounts") if isinstance(ratings.get("ratingCounts"), list) else []
    vh = first(obj(obj(obj(sm.get("mostRecentVersion")).get("seeAllAction")).get("pageData")).get("shelves"))
    return {
        "id": app_id,
        "incomplete": page.get("isIncomplete"),  # Apple's own flag; False on every page tested
        "name": lockup.get("title"),
        "subtitle": lockup.get("subtitle"),
        "rating": ratings.get("ratingAverage"),
        "ratings_count": ratings.get("totalNumberOfRatings"),
        "stars_5_to_1": [round(x) for x in counts if isinstance(x, (int, float))],
        "chart_rank": badges.get("chartPosition", {}).get("position"),
        "age_rating": badges.get("contentRating", {}).get("contentRating"),
        "size": info.get("Size"),
        "category": info.get("Category"),
        "in_app_purchases": info.get("In-App Purchases"),
        "versions": [{"version": v.get("primarySubtitle"), "date": v.get("secondarySubtitle"),
                      "notes": (v.get("text") or "")[:120] if isinstance(v.get("text"), str) else ""}
                     for v in vh.get("items") or [] if isinstance(v, dict)],
    }

for app_id in [389801252, 963034692, 1438388363, 1]:  # Instagram, Streaks (paid), a habit app, a bad ID
    d = app_page(app_id)
    if d is None:
        print(app_id, "-> None (HTTP 404, no such app)")
        continue
    vs = d.pop("versions")
    print(json.dumps(d, ensure_ascii=False))
    print("   versions embedded:", len(vs), "(Apple embeds at most 25)", vs[:1])
    time.sleep(3)
```

Output:

```
{"id": 389801252, "incomplete": false, "name": "Instagram", "subtitle": "Videos, creators & friends", "rating": 4.7, "ratings_count": 29628829, "stars_5_to_1": [25414205, 2006941, 698494, 276272, 1232917], "chart_rank": "2", "age_rating": "13+", "size": "660.9 MB", "category": "Photo & Video", "in_app_purchases": "Yes"}
   versions embedded: 25 (Apple embeds at most 25) [{'version': '452.0.0', 'date': 'Mon Oct 19 2026 12:27:02 GMT+0000 (Coordinated Universal Time)', 'notes': 'Performance optimizations and stability improvements for a smoother, more reliable experience.'}]
{"id": 963034692, "incomplete": false, "name": "Streaks", "subtitle": "Habit Tracker & To-Do List", "rating": 4.8, "ratings_count": 27354, "stars_5_to_1": [24212, 2095, 503, 177, 367], "chart_rank": "1", "age_rating": "4+", "size": "275.9 MB", "category": "Health & Fitness", "in_app_purchases": null}
   versions embedded: 25 (Apple embeds at most 25) [{'version': '11.5.2', 'date': 'Sun Oct 18 2026 09:27:30 GMT+0000 (Coordinated Universal Time)', 'notes': 'STREAKS 11.5:\n\n* New: Refreshed design for buttons on the main screen\n* New: Halloween 2026 theme\n* New: Improvements to'}]
{"id": 1438388363, "incomplete": false, "name": "Habit Tracker", "subtitle": "Goal Tracker & ADHD Planner", "rating": 4.8, "ratings_count": 148205, "stars_5_to_1": [130227, 10908, 3574, 1094, 2402], "chart_rank": "138", "age_rating": "9+", "size": "316.6 MB", "category": "Productivity", "in_app_purchases": "Yes"}
   versions embedded: 25 (Apple embeds at most 25) [{'version': '2.15.6', 'date': 'Thu Oct 22 2026 22:11:24 GMT+0000 (Coordinated Universal Time)', 'notes': '- support iOS 27\n- fix bugs\n----- Beta Tester needed -----\nIf you want to help us to test new version, contact us: inner'}]
1 -> None (HTTP 404, no such app)
```

### 4. Same extras from inside a browser tab

Use this when you are already driving a tab. The rendered DOM no longer contains `#serialized-server-data` (the SPA removes it after hydration; `document.getElementById` returned null on all 3 test pages), so the snippet re-fetches the requested app URL in-page and parses it. The fetch is started in the page and polled, so no single `js()` call waits on a 1 MB download. `open_app` waits until the tab's own URL shows the requested app ID (as a whole number, so `/id3106` does not match `/id310633997`) before anything is read, so a previous page's ready state is never used. It runs in the background tab; it never calls `activate_tab`.

```python
import json, re, time

def browser_timeout(e):
    # cdp/IPC timeouts raise TimeoutError; js() wraps a timed-out Runtime.evaluate in RuntimeError("... timed out ...")
    return isinstance(e, TimeoutError) or (isinstance(e, RuntimeError) and "timed out" in str(e))

def open_app(app_id, first_tab, timeout=30):
    """Navigate, then wait until location.href is the requested app and the document is complete."""
    url = f"https://apps.apple.com/us/app/id{app_id}"
    new_tab(url) if first_tab else goto_url(url)
    deadline, last = time.time() + timeout, None
    while time.time() < deadline:
        try:
            state = js("[location.href, document.readyState]")
            if state and re.search(rf"/id{app_id}(?!\d)", state[0]) and state[1] == "complete":
                return state[0]
        except Exception as e:
            if not browser_timeout(e):
                raise
            last = e
        time.sleep(0.5)
    raise TimeoutError(f"tab never reached app {app_id} (last browser timeout: {last})")

EXTRACT = r"""(async (url, appId) => {
  const res = await fetch(url, {credentials: 'omit'});
  if (!res.ok) return {status: res.status};
  const doc = new DOMParser().parseFromString(await res.text(), 'text/html');
  const el = doc.getElementById('serialized-server-data');
  if (!el) return {status: res.status, error: 'no serialized-server-data'};
  const page = JSON.parse(el.textContent).data?.[0]?.data || {};
  if (String(page.lockup?.adamId) !== appId) return {status: res.status, error: 'wrong app ' + page.lockup?.adamId};
  const sm = page.shelfMapping || {};
  const badge = k => (sm.informationRibbon?.items || []).find(b => b?.key === k)?.content || {};
  const info = Object.fromEntries((sm.information?.items || []).map(a => [a?.title, a?.summary]));
  const r = sm.productRatings?.items?.[0] || {};
  const vh = sm.mostRecentVersion?.seeAllAction?.pageData?.shelves?.[0]?.items || [];
  return {status: res.status, incomplete: page.isIncomplete ?? null, name: page.lockup?.title ?? null,
          rating: r.ratingAverage ?? null, ratings_count: r.totalNumberOfRatings ?? null,
          stars_5_to_1: (Array.isArray(r.ratingCounts) ? r.ratingCounts : []).filter(x => typeof x === 'number').map(Math.round),
          chart_rank: badge('chartPosition').position ?? null, age_rating: badge('contentRating').contentRating ?? null,
          size: info['Size'] ?? null, category: info['Category'] ?? null, versions: vh.length,
          latest: vh[0]?.primarySubtitle ?? null, latest_date: vh[0]?.secondarySubtitle ?? null};
})"""

def extract_in_tab(app_id, retries=3, timeout=45):
    """Page extras for app_id via an in-page fetch. None on HTTP 404; retries 429/5xx and browser timeouts
    with backoff (no sleep after the last try), then raises. 403 and other statuses raise at once."""
    url, out = f"https://apps.apple.com/us/app/id{app_id}", None
    for attempt in range(retries):
        js(f"window.__bhApp = null; ({EXTRACT})({json.dumps(url)}, {json.dumps(str(app_id))})"
           ".then(r => { window.__bhApp = r; }, e => { window.__bhApp = {error: String(e)}; }); true")
        deadline, out = time.time() + timeout, None
        while time.time() < deadline and out is None:
            time.sleep(1)
            try:
                out = js("window.__bhApp")
            except Exception as e:
                if not browser_timeout(e):
                    raise
        status = (out or {}).get("status")
        if out is not None and status == 200 and "error" not in out:
            return out
        if status == 404:
            return None
        if out is not None and status not in (429, 500, 502, 503, 504) and "status" in out:
            raise RuntimeError(f"app {app_id}: {out}")  # e.g. wrong app or missing embedded data
        if attempt < retries - 1:
            time.sleep(15 * (attempt + 1))  # 429/5xx, fetch error or poll timeout: back off and retry
    raise RuntimeError(f"app {app_id}: in-page fetch still failing after {retries} tries: {out}")

for n, app_id in enumerate([310633997, 1586435171]):  # WhatsApp, Actions
    href = open_app(app_id, first_tab=(n == 0))
    print(app_id, href, json.dumps(extract_in_tab(app_id), ensure_ascii=False))
    time.sleep(3)
```

Output:

```
310633997 https://apps.apple.com/us/app/whatsapp-messenger/id310633997 {"status": 200, "incomplete": false, "name": "WhatsApp Messenger", "rating": 4.7, "ratings_count": 18827914, "stars_5_to_1": [15891698, 1461031, 570089, 256170, 648926], "chart_rank": "2", "age_rating": "13+", "size": "411.3 MB", "category": "Social Networking", "versions": 25, "latest": "26.41.75", "latest_date": "Thu Oct 22 2026 15:42:36 GMT+0000 (Coordinated Universal Time)"}
1586435171 https://apps.apple.com/us/app/actions/id1586435171 {"status": 200, "incomplete": false, "name": "Actions", "rating": 4.8, "ratings_count": 515, "stars_5_to_1": [469, 20, 8, 1, 17], "chart_rank": null, "age_rating": "4+", "size": "29.1 MB", "category": "Utilities", "versions": 25, "latest": "4.2.0", "latest_date": "Mon Jun 08 2026 18:27:36 GMT+0000 (Coordinated Universal Time)"}
```

## Fields

Block 1 row (`to_row`, built from an API record with `wrapperType == "software"`). Any field whose API value is missing or the wrong type comes back `None` (`release_notes` and `url` come back `""`).

| Key | API field | Notes |
|---|---|---|
| `id` | `trackId` | int, the `id<N>` in store URLs |
| `name` | `trackName` | |
| `developer` | `artistName` | `artistId` (raw) feeds the developer lookup |
| `rating` | `averageUserRating` | float rounded to 2 places, e.g. 4.69 (page shows 4.7) |
| `ratings_count` | `userRatingCount` | int |
| `price` | `price` | float, 0.0 for free |
| `price_label` | `formattedPrice` | localized ("Free", "£5.99", "6,99 €") |
| `currency` | `currency` | |
| `category` | `primaryGenreName` | |
| `size_mb` | `fileSizeBytes` | API sends a **string** of bytes; cast to int, / 1e6 |
| `version` | `version` | |
| `version_date` | `currentVersionReleaseDate` | ISO 8601 UTC, date of `version` |
| `release_notes` | `releaseNotes` | first 200 chars; absent on a few percent of hits (7 of 193 and 9 of 190 in two runs) |
| `first_release` | `releaseDate` | |
| `bundle_id` | `bundleId` | |
| `url` | `trackViewUrl` | query string stripped |

Block 2 prints raw API records. Raw fields it reads: `trackId`, `trackName`, `artistName`, `artistId`, `averageUserRating`, `userRatingCount`, `formattedPrice`, `price`, `currency`, `primaryGenreName`, `fileSizeBytes`, `version`, `currentVersionReleaseDate`, `contentAdvisoryRating`, `minimumOsVersion`. Other raw fields on the record: `sellerName`, `genres`, `description`, `screenshotUrls`, `artworkUrl512`, `languageCodesISO2A`, `supportedDevices`, `userRatingCountForCurrentVersion`.

Block 3 (`app_page`) keys, from app page `serialized-server-data` -> `data[0].data`:

| Key | Path |
|---|---|
| `id` | the requested ID (checked against `lockup.adamId`) |
| `incomplete` | `isIncomplete` |
| `name` / `subtitle` | `lockup.title` / `lockup.subtitle` |
| `rating` / `ratings_count` | `shelfMapping.productRatings.items[0].ratingAverage` / `totalNumberOfRatings` |
| `stars_5_to_1` | `shelfMapping.productRatings.items[0].ratingCounts` (floats, rounded) |
| `chart_rank` | `shelfMapping.informationRibbon.items[key="chartPosition"].content.position` (string; `None` if not charting) |
| `age_rating` | `shelfMapping.informationRibbon.items[key="contentRating"].content.contentRating` |
| `size`, `category`, `in_app_purchases` | `shelfMapping.information.items[]` where `title` is `Size`, `Category`, `In-App Purchases` -> `summary` (`None` if the row is absent) |
| `versions[]` | `shelfMapping.mostRecentVersion.seeAllAction.pageData.shelves[0].items[]` -> `version` = `primarySubtitle`, `date` = `secondarySubtitle` (date string), `notes` = first 120 chars of `text` |

Block 4 (`extract_in_tab`) keys: `status` (HTTP status of the in-page fetch), `incomplete`, `name`, `rating`, `ratings_count`, `stars_5_to_1`, `chart_rank`, `age_rating`, `size`, `category` (same paths as block 3), `versions` (count only), `latest` / `latest_date` (`primarySubtitle` / `secondarySubtitle` of the newest version).

The `information` items also carry `Seller`, `Compatibility`, `Languages`, `Age Rating` and `Copyright`. JSON-LD `script#software-application` on the same page also has `name`, `offers.price`, `aggregateRating.ratingValue/reviewCount`, `author.name`, `genre`.

## Gotchas

- **`offset` does not paginate search.** For "habit tracker", `limit=50&offset=50` returned 48 apps, of which 45 (one run) and 48 (another run) were already on the `limit=50` page. Ordering also shifts between runs and between `limit` values (in one run `limit=50` was a prefix of `limit=200`, in another it was not). Always ask for `limit=200` once per term.
- `limit` caps at 200 (`limit=500` returned 171 for "photo editor"). Typical full queries returned 171 to 193 apps. Without `limit` you get far fewer (38 to 39 for "photo editor" across runs).
- **Lookup silently truncates around 210 IDs.** 250 IDs returned 209-210 results with no error. 100, 150 and 200 IDs returned every ID, or all but one in another run (an app that was no longer available drops out the same way the bad ID `1` does). Chunk at 100; block 2 refuses chunks outside 1 to 100.
- Unknown IDs return HTTP 200 with `{"resultCount": 0, "results": []}` on the API and HTTP 404 on the app page. Blocks 3 and 4 return `None` for that 404; every other failure raises.
- `country` changes currency and price (Streaks: $5.99 US, £5.99 GB, 6,99 € DE) and the result language. Results differ per storefront.
- Developer lookup returns an `artist` record first; filter `wrapperType == "software"`.
- `entity=iPadSoftware` adds nothing: for "photo editor" with `limit=200` it returned 170 results, all `kind: "software"` (vs 175 for `entity=software`). `entity=macSoftware` returned 138, mixing 47 `mac-software` and 91 `software`. Default to `entity=software`; use `macSoftware` only for Mac apps and filter on `kind`.
- Age ratings disagree: the API still says `contentAdvisoryRating: "12+"` for Instagram while the page shows `13+` (Apple's newer scale). Take the page value if age rating matters.
- Version history dates on the page are JS `Date.toString()` strings ("Mon Oct 19 2026 12:27:02 GMT+0000 ..."), not ISO. The API's `currentVersionReleaseDate` is ISO.
- Only the 25 most recent versions are embedded (all 5 apps tested had exactly 25). Older versions are not on the page, so 25 means "maybe more", not "all".
- `https://apps.apple.com/us/app/id<ID>` works without the slug and redirects to the slugged URL. Match the tab URL on `/id<ID>`, not on the exact URL you navigated to.
- No consent banner or login wall appeared on US app pages.
- Plain HTTP with the truthful `Python-urllib/3.x` User-Agent got HTTP 200 from itunes.apple.com and apps.apple.com today.

## What does not work

- **Web search page** for scale: `https://apps.apple.com/us/iphone/search?term=...` rendered only **11** apps in the browser and scrolling 6 times loaded no more. A plain HTTP GET returns HTTP 200 (about 560 KB) whose `serialized-server-data` holds the same 11 app IDs, so the page is capped at 11 either way (two earlier GETs the same day got HTTP 429 instead, so expect intermittent rate limiting and back off). `/us/search?term=...` returns **404**. Use the API search instead.
- Reading `#serialized-server-data` from the rendered DOM in a browser: it is gone after hydration (use block 3 or block 4).
- Unlimited search depth: no parameter returned more than 200 apps for one term.
