# Rotten Tomatoes — Movie/TV Pages and Browse Lists

Field-tested against www.rottentomatoes.com on 2026-10-23 using plain HTTP (Python urllib) and a Browser Use cloud browser.

robots.txt (checked 2026-10-23) has no rule for `/m/`, `/tv/`, `/browse/` or `/cnapi/browse/` (the paths this skill uses) and disallows `/search` for all user agents.

## Quick summary

- **No browser needed for data.** Every title page (`/m/<slug>`, `/tv/<slug>`, `/tv/<slug>/s05`) ships the full scorecard as embedded JSON (`<script id="media-scorecard-json">`), plus one schema.org JSON-LD block and a server-rendered "Movie Info" list. Plain urllib with its default `Python-urllib/3.x` User-Agent returned HTTP 200 for all of them.
- **Browse lists** (`/browse/<list>/<filters>`) are paginated by the same JSON endpoint the "Load more" button calls: `GET /cnapi/browse/<list>/<filters>?after=<endCursor>`, 30 items per page, cursor in `pageInfo`. 5 pages (150 unique titles) of one list in a row worked, ~0.2-1.1 s per call.
- Browse items carry title, URL, Tomatometer, Popcornmeter, certified flags and a release-date string. Review counts, rating, genre, dates and cast come from the title page, so a full scrape is "browse, then one request per title".
- The browser is only a fallback. Close the app-promo modal before clicking; do not click the consent banner's "Continue", it reloads the page.
- This skill does not use `/search`. Start from browse lists or known `/m/` and `/tv/` URLs.

## What works

### 1. Browse 2+ pages, then enrich each title (plain HTTP, no browser)

Runs as one script, inside browser-harness or as plain `python3` (standard library only). `rt_get` fetches with retry, `rt_browse` pages the list, `rt_title` parses one title page, `rt_cast` gets the full cast from `/cast-and-crew`.

```python
import re, json, time, gzip, email.utils, html as htmllib
import urllib.parse, urllib.request, urllib.error

BASE = "https://www.rottentomatoes.com"
# No User-Agent override: urllib sends its own truthful "Python-urllib/3.x", which got HTTP 200 on every URL below.
HDRS = {"Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip"}
RETRY_CODES = {429, 500, 502, 503, 504}
MAX_WAIT = 120.0  # longest sleep we accept; a longer Retry-After stops the run instead
TITLE_TYPES = {"Movie", "TVSeries", "TVSeason"}

def _retry_after(v):
    """Retry-After header as seconds: delta-seconds or an HTTP-date. None if absent/unparseable."""
    v = (v or "").strip()
    if v.isdigit():
        return float(v)
    try:
        return max(0.0, email.utils.parsedate_to_datetime(v).timestamp() - time.time())
    except (TypeError, ValueError, IndexError):
        return None

def rt_get(url, tries=4, timeout=20):
    """GET -> (final_url, text). Retries 429/5xx and network errors with backoff, then raises.
    Any other HTTP error (404 for a bad slug or list) raises at once, and so does a
    Retry-After longer than MAX_WAIT. Never sleeps after the last attempt."""
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                return r.geturl(), data.decode()
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES or i == tries - 1:
                raise
            wait = _retry_after(e.headers.get("Retry-After"))
        except OSError:  # URLError, socket timeout, connection reset
            if i == tries - 1:
                raise
            wait = None
        if wait is not None and wait > MAX_WAIT:
            raise RuntimeError(f"{url}: server asked to wait {wait:.0f}s (> {MAX_WAIT:.0f}s); stopping")
        time.sleep(min(MAX_WAIT, wait if wait is not None else 2.0 * 2 ** i))

def _script_json(page, attr):
    """Parse the first <script ...attr...>{JSON object}</script> block, or None."""
    m = re.search(r'<script[^>]*%s[^>]*>(.*?)</script>' % attr, page, re.S)
    try:
        j = json.loads(m.group(1)) if m else None
    except ValueError:
        return None
    return j if isinstance(j, dict) else None

def _title_ld(page):
    """The JSON-LD object describing this title (@type Movie/TVSeries/TVSeason), else {}."""
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            j = json.loads(m.group(1))
        except ValueError:
            continue
        for o in (j if isinstance(j, list) else [j]):
            if isinstance(o, dict) and o.get("@type") in TITLE_TYPES:
                return o
    return {}

def _d(v):    return v if isinstance(v, dict) else {}
def _s(v):    return (v.strip() or None) if isinstance(v, str) else None
def _b(v):    return v if isinstance(v, bool) else None

def _int(v):
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        return None
    try:
        return int(str(v).replace(",", "").strip())
    except ValueError:
        return None

def _strs(v):
    if isinstance(v, str):
        v = [v]
    return [x.strip() for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []

def _names(people):
    if isinstance(people, dict):
        people = [people]
    return [p["name"] for p in (people if isinstance(people, list) else [])
            if isinstance(p, dict) and isinstance(p.get("name"), str)]

def _text(s):
    return htmllib.unescape(re.sub(r"<[^>]+>", "", re.sub(r"\s+", " ", s or ""))).strip()

def rt_title(url):
    """Full record for one /m/<slug>, /tv/<slug> or /tv/<slug>/sNN page.
    Raises if the page has neither the scorecard JSON nor a title JSON-LD block."""
    final_url, page = rt_get(urllib.parse.urljoin(BASE, url))
    ld = _title_ld(page)
    sc = _script_json(page, r'id="media-scorecard-json"') or {}
    if not ld and not sc:
        raise LookupError(f"no title data on {final_url}")
    hero = _d((_script_json(page, r'id="media-hero-json"') or {}).get("content"))
    info = {}  # "Movie Info" / "Series Info" list: label -> [values]
    for m in re.finditer(r'data-qa="item-label">(.*?)</rt-text>\s*</dt>\s*<dd[^>]*>(.*?)</dd>', page, re.S):
        info[_text(m.group(1))] = [_text(v) for v in re.findall(r'data-qa="item-value"[^>]*>(.*?)</rt-', m.group(2), re.S)]
    first = lambda k: (info.get(k) or [None])[0]
    crit, aud = _d(sc.get("criticsScore")), _d(sc.get("audienceScore"))
    top = _d(_d(sc.get("overlay")).get("criticsTop"))
    rating_detail = first("Rating")
    return {
        "url": final_url,                                  # after redirects
        "type": ld.get("@type"),                           # Movie | TVSeries | TVSeason
        "title": _text(_s(hero.get("title")) or _s(ld.get("name"))) or None,
        "tomatometer": _int(crit.get("score")),            # None until enough reviews
        "tomatometer_reviews": _int(crit.get("reviewCount")),
        "tomatometer_avg": _s(crit.get("averageRating")),  # "8.60" (out of 10)
        "certified_fresh": _b(crit.get("certified")),
        "top_critics_score": _int(top.get("score")),
        "top_critics_reviews": _int(top.get("reviewCount")),
        "popcornmeter": _int(aud.get("score")),
        "popcornmeter_type": _s(aud.get("scoreType")),     # VERIFIED | ALL
        "audience_ratings": _s(aud.get("bandedRatingCount")),  # "10,000+ Verified Ratings"
        "audience_reviews": _int(aud.get("reviewCount")),  # absent on TV series pages
        "rating": _s(ld.get("contentRating")) or (rating_detail or "").split(" (")[0] or None,
        "rating_detail": rating_detail,                    # "R (Nudity|Language|Some Sexuality)"
        "genres": _strs(ld.get("genre")) or info.get("Genre") or [],
        "release_date": first("Release Date (Theaters)") or first("Release Date"),
        "streaming_date": first("Release Date (Streaming)"),
        "first_date": _s(ld.get("dateCreated")),           # ISO YYYY-MM-DD
        "runtime": first("Runtime"),
        "seasons": _int(ld.get("numberOfSeasons")),
        "network": first("Network"),
        "box_office": first("Box Office (Gross USA)"),
        "directors": _names(ld.get("director")),
        "cast": _names(ld.get("actor")),                   # top-billed only, 0-5 names
    }

def rt_cast(url):
    """Full cast list from /cast-and-crew: [{name, character}].
    Raises if the page has no cast-and-crew cards at all (markup change, or a title with no credits)."""
    final_url, page = rt_get(urllib.parse.urljoin(BASE, url).rstrip("/") + "/cast-and-crew")
    cards = re.findall(r'<cast-and-crew-card(.*?)</cast-and-crew-card>', page, re.S)
    if not cards:
        raise LookupError(f"no <cast-and-crew-card> on {final_url}")
    out = []
    for card in cards:
        role = re.search(r'data-role="([^"]*)"', card)
        if not role or "cast" not in role.group(1).split(","):
            continue
        name = re.search(r'slot="title"[^>]*>(.*?)</rt-text>', card, re.S)
        char = re.search(r'slot="characters"[^>]*>(.*?)</rt-text>', card, re.S)
        out.append({"name": _text(name.group(1)) if name else None,
                    "character": _text(char.group(1)) if char else None})
    return out

def rt_browse(vanity, filters="sort:popular", max_pages=2, delay=1.5):
    """Browse list via the endpoint behind "Load more", 30 items per page.
    Returns (rows, complete). complete is False when max_pages stopped it while the API
    still said hasNextPage. A failed page raises (after rt_get's retries); it never ends the list."""
    base = (f"{BASE}/cnapi/browse/{urllib.parse.quote(vanity, safe='')}/"
            f"{urllib.parse.quote(filters, safe=':~,')}")
    rows, seen, after = [], set(), None
    for _ in range(max_pages):
        url = base
        if after:  # unquote first so a cursor copied as "Mjk%3D" is not double-encoded
            url += "?after=" + urllib.parse.quote(urllib.parse.unquote(after), safe="")
        _, body = rt_get(url)
        d = json.loads(body)
        items = _d(d.get("grid")).get("list")
        if not isinstance(items, list):
            raise LookupError(f"no grid.list in {url}")
        for it in items:
            if not isinstance(it, dict):
                continue
            key = _s(it.get("emsId")) or _s(it.get("mediaUrl"))
            if key in seen:
                continue  # duplicate across pages; rows with no id are always kept
            if key:
                seen.add(key)
            c, a = _d(it.get("criticsScore")), _d(it.get("audienceScore"))
            media = _s(it.get("mediaUrl"))
            rows.append({
                "ems_id": _s(it.get("emsId")),
                "title": _s(it.get("title")),
                "url": urllib.parse.urljoin(BASE, media) if media else None,
                "type": _s(it.get("type")),
                "tomatometer": _int(c.get("score")),
                "certified_fresh": _b(c.get("certified")),
                "popcornmeter": _int(a.get("score")),
                "release_text": _s(it.get("releaseDateText")),  # "Opened Oct 16, 2026", "Streaming Oct 13, 2026"
            })
        pi = _d(d.get("pageInfo"))
        if not pi.get("hasNextPage"):
            return rows, True
        after = _s(pi.get("endCursor"))
        if not after:
            raise LookupError(f"hasNextPage is true but no endCursor in {url}")
        time.sleep(delay)
    return rows, False

# Browse 2 pages (60 titles) of Certified Fresh movies streaming at home
rows, complete = rt_browse("movies_at_home", "critics:certified_fresh~sort:popular", max_pages=2)
print(len(rows), "titles,", len({r["url"] for r in rows}), "unique urls, complete list:", complete)
if not complete:
    print("stopped at max_pages=2; the list has more pages")
print(json.dumps(rows[0]) if rows else "no rows")

# Enrich the first 5 with their title pages (review counts, rating, genre, dates, cast)
todo, failed = rows[:5], []
time.sleep(1.5)  # rt_browse does not sleep after its last page
for i, r in enumerate(todo):
    if not r["url"]:
        failed.append((r["title"], "no url"))
        continue
    try:
        d = rt_title(r["url"])
        print(json.dumps({k: d[k] for k in ("title", "tomatometer", "tomatometer_reviews", "popcornmeter",
                                            "audience_ratings", "rating", "genres", "release_date", "cast")}))
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise  # blocked, or still rate limited after rt_get's retries: stop the run and back off
        failed.append((r["url"], repr(e)[:80]))  # e.g. 404 for a removed title
    except (OSError, LookupError, ValueError) as e:  # network error after retries, no data
        failed.append((r["url"], repr(e)[:80]))
    finally:
        if i < len(todo) - 1:
            time.sleep(1.5)  # after every attempted request, failed ones included; not after the last
print("enriched", len(todo) - len(failed), "of", len(todo), "| failed:", failed)

# A movie, a TV series and a TV season directly, plus a full cast list (1.5 s before each request)
for u in ["/m/oppenheimer_2023", "/tv/the_bear", "/tv/the_bear/s05"]:
    time.sleep(1.5)
    print(json.dumps(rt_title(u)))
time.sleep(1.5)
cast = rt_cast("/m/oppenheimer_2023")
print(len(cast), "cast members", cast[:2])
```

Real output (trimmed; people's names, which the code returns as plain strings, replaced with `<name>`):

```text
60 titles, 60 unique urls, complete list: False
stopped at max_pages=2; the list has more pages
{"ems_id": "5b44daa8-5b70-3a2b-b009-0052edcfc114", "title": "Tenzing", "url": "https://www.rottentomatoes.com/m/tenzing", "type": "Movie", "tomatometer": 98, "certified_fresh": true, "popcornmeter": 91, "release_text": "Streaming Oct 16, 2026"}
{"title": "Tenzing", "tomatometer": 98, "tomatometer_reviews": 58, "popcornmeter": 91, "audience_ratings": "100+ Ratings", "rating": "PG", "genres": ["Drama", "Adventure"], "release_date": "Oct 9, 2026, Limited", "cast": ["<name>", "<name>", "<name>", "<name>", "<name>"]}
{"title": "Buddy", "tomatometer": 88, "tomatometer_reviews": 138, "popcornmeter": 76, "audience_ratings": "1,000+ Verified Ratings", "rating": "R", "genres": ["Horror", "Comedy", "Mystery & Thriller", "Fantasy"], "release_date": "Aug 28, 2026, Wide", "cast": ["<name>", "<name>", "<name>"]}
...
enriched 5 of 5 | failed: []
{"url": "https://www.rottentomatoes.com/m/oppenheimer_2023", "type": "Movie", "title": "Oppenheimer", "tomatometer": 93, "tomatometer_reviews": 510, "tomatometer_avg": "8.60", "certified_fresh": true, "top_critics_score": 95, "top_critics_reviews": 87, "popcornmeter": 91, "popcornmeter_type": "VERIFIED", "audience_ratings": "10,000+ Verified Ratings", "audience_reviews": 6023, "rating": "R", "rating_detail": "R (Nudity|Language|Some Sexuality)", "genres": ["Biography", "History", "Drama"], "release_date": "Jul 21, 2023, Wide", "streaming_date": "Nov 21, 2023", "first_date": "2023-07-21", "runtime": "3h 0m", "seasons": null, "network": null, "box_office": "$330.0M", "directors": ["<name>"], "cast": ["<name>", "<name>", "<name>", "<name>", "<name>"]}
{"url": "https://www.rottentomatoes.com/tv/the_bear", "type": "TVSeries", "title": "The Bear", "tomatometer": 93, "tomatometer_reviews": 469, "tomatometer_avg": "8.30", "certified_fresh": false, "top_critics_score": 93, "top_critics_reviews": 182, "popcornmeter": 79, "popcornmeter_type": "ALL", "audience_ratings": "10,000+ Ratings", "audience_reviews": null, "rating": "TV-MA", "rating_detail": "TV-MA", "genres": ["Comedy", "Drama"], "release_date": "Jun 23, 2022", "streaming_date": null, "first_date": "2022-06-23", "runtime": null, "seasons": 5, "network": "Hulu", "box_office": null, "directors": ["<name>"], "cast": ["<name>", "<name>", "<name>", "<name>"]}
{"url": "https://www.rottentomatoes.com/tv/the_bear/s05", "type": "TVSeason", "title": "Season 5 – The Bear", "tomatometer": 96, "tomatometer_reviews": 83, "tomatometer_avg": "8.10", "certified_fresh": true, "top_critics_score": 97, "top_critics_reviews": 33, "popcornmeter": 85, "popcornmeter_type": "ALL", "audience_ratings": "250+ Ratings", "audience_reviews": 156, "rating": "TV-MA", "rating_detail": "TV-MA", "genres": ["Comedy", "Drama"], "release_date": "Jun 25, 2026", "streaming_date": null, "first_date": "2026-06-25", "runtime": null, "seasons": null, "network": "Hulu", "box_office": null, "directors": ["<name>"], "cast": ["<name>", "<name>", "<name>", "<name>"]}
31 cast members [{'name': '<name>', 'character': '<name>'}, {'name': '<name>', 'character': '<name>'}]
```

The failure paths were checked against a local mock server the same day: a 429 with `Retry-After: 1` and a 503 with an HTTP-date `Retry-After` were each retried once and then succeeded; a 429 with `Retry-After: 300` made `rt_get` raise after 1 request with no sleep; a server that always returned 500 made `rt_get` raise `HTTPError 500` after its tries; a browse page that kept failing made `rt_browse` raise instead of returning the rows it already had; a row with `emsId: null` was kept.

**List names and filters.** The path after `/browse/` on the site is exactly what `/cnapi/browse/` takes. Observed working: `movies_in_theaters/sort:popular`, `movies_at_home/critics:certified_fresh~sort:popular`, `movies_coming_soon/sort:popular`, `tv_series_browse/sort:popular`, `tv_series_browse/genres:comedy~sort:newest`. Multiple filters are joined with `~`. To get a filter string, set the filters on the site's browse page and copy the path. An unknown list name returns HTTP 404.

### 2. Browser fallback (same data from the live DOM, "Load more" pagination)

Use this path when you want the rendered page in a normal browser session; it reads the same public, logged-out pages a visitor sees, at a human pace. It is not a way around a block. A 429 on the HTTP path gets only the bounded retry in `rt_get` (see Pacing): at most 4 tries, honoring `Retry-After` up to 120 s, then it raises. A 403, challenge or captcha on either path, or a 429 in the browser, is not retried: stop, record it and back off, and do not switch paths, sessions or networks to get past it. It works in a background tab (`new_tab` does not foreground Chrome; nothing here calls `activate_tab`).

```python
import json, time

def is_harness_timeout(e):
    """js() re-raises a slow Runtime.evaluate as RuntimeError("Runtime.evaluate timed out; ...");
    cdp() raises a TimeoutError subclass. Anything else (a JS exception) is a real error."""
    return isinstance(e, TimeoutError) or (isinstance(e, RuntimeError) and "timed out" in str(e))

def js_retry(expr, tries=3):
    """js() that retries harness timeouts (slow daemon round trip on a busy cloud browser)."""
    for i in range(tries):
        try:
            return js(expr)
        except (TimeoutError, RuntimeError) as e:
            if not is_harness_timeout(e) or i == tries - 1:
                raise
            time.sleep(1)

def open_page(url, ready_selector, first=False, timeout=30):
    """Navigate, then wait until location.href is THIS url, its document is complete, and
    ready_selector exists. Checking the URL stops us reading the previous page's readyState."""
    new_tab(url) if first else goto_url(url)
    want = url.split("#")[0].split("?")[0].rstrip("/")
    check = ("(() => location.href.split('#')[0].split('?')[0].replace(/\\/$/, '') === %s"
             " && document.readyState === 'complete' && !!document.querySelector(%s))()"
             % (json.dumps(want), json.dumps(ready_selector)))
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if js(check):
                return
        except (TimeoutError, RuntimeError) as e:
            if not is_harness_timeout(e):
                raise
        time.sleep(0.5)
    raise RuntimeError(f"{url} not ready ({ready_selector}): {json.dumps(page_info())}")

def click_button(name):
    """Click the first rendered button whose accessible name equals `name` (case-insensitive)."""
    for n in cdp("Accessibility.getFullAXTree")["nodes"]:
        if n.get("ignored") or n.get("role", {}).get("value") != "button":
            continue
        if str(n.get("name", {}).get("value", "")).strip().lower() != name.lower():
            continue
        bid = n.get("backendDOMNodeId")
        try:
            cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=bid)
            q = cdp("DOM.getBoxModel", backendNodeId=bid)["model"]["content"]
        except RuntimeError:
            continue  # node exists but is not rendered
        click_at_xy(sum(q[0::2]) / 4, sum(q[1::2]) / 4)
        return True
    return False

PROMO_CLOSE = """(() => { const b = document.querySelector('rt-app-modal-content [data-rtappmanager="btnClose:click"]');
  if (!b || !b.checkVisibility()) return null; const r = b.getBoundingClientRect();
  return r.width ? [r.x + r.width / 2, r.y + r.height / 2] : null })()"""

def close_app_promo(settle=2.0):
    """Close the app-promo modal if it is showing. True = closed, False = not showing.
    Do NOT click the consent banner's "Continue" (id onetrust-accept-btn-handler):
    it accepts the terms and reloads the page, wiping anything already read."""
    time.sleep(settle)  # the modal appears shortly after load, not on every page view
    xy = js_retry(PROMO_CLOSE)
    if not xy:
        return False
    click_at_xy(*xy)
    for _ in range(10):
        time.sleep(0.3)
        if not js_retry(PROMO_CLOSE):
            return True
    raise RuntimeError("app promo did not close")

# Title page: read the embedded JSON from the DOM
open_page("https://www.rottentomatoes.com/m/oppenheimer_2023", "#media-scorecard-json", first=True)
rec = js_retry("""(() => {
const j = el => { try { return el ? JSON.parse(el.textContent) : null } catch (e) { return null } };
const ld = [...document.querySelectorAll('script[type="application/ld+json"]')].map(j)
  .find(o => o && ['Movie', 'TVSeries', 'TVSeason'].includes(o['@type'])) || {};
const sc = j(document.getElementById('media-scorecard-json')) || {};
const c = sc.criticsScore || {}, a = sc.audienceScore || {};
return {url: location.href, title: ld.name || null, tomatometer: c.score || null, reviews: c.reviewCount ?? null,
        popcornmeter: a.score || null, audience: a.bandedRatingCount || null,
        rating: ld.contentRating || null, genres: ld.genre || [], released: ld.dateCreated || null,
        cast: (Array.isArray(ld.actor) ? ld.actor : []).map(p => p && p.name).filter(Boolean)};
})()""")
print(json.dumps(rec))

# Browse page: read tiles, press "Load more" at most MAX_CLICKS times
TILE = 'a[data-qa="discovery-media-list-item-caption"]'
TILES = """
return [...document.querySelectorAll('a[data-qa="discovery-media-list-item-caption"]')].map(a => ({
  title: a.querySelector('[data-qa="discovery-media-list-item-title"]')?.textContent.trim() || null,
  url: a.href || null,
  tomatometer: a.querySelector('[slot="criticsScore"]')?.textContent.trim() || null,
  popcornmeter: a.querySelector('[slot="audienceScore"]')?.textContent.trim() || null,
  date: a.querySelector('[data-qa="discovery-media-list-item-start-date"]')?.textContent.trim() || null}));
"""

def wait_more(before, secs=10):
    """Poll until the tile count grows past `before`; return the latest tiles either way."""
    tiles = []
    for _ in range(int(secs / 0.5)):
        time.sleep(0.5)
        tiles = js_retry(TILES) or []
        if len(tiles) > before:
            break
    return tiles

open_page("https://www.rottentomatoes.com/browse/movies_in_theaters/sort:popular", TILE)
print("app promo closed:", close_app_promo())
tiles = js_retry(TILES) or []
print("page 1:", len(tiles), "tiles")
MAX_CLICKS, clicks, end_of_list = 2, 0, False
while clicks < MAX_CLICKS:
    before = len(tiles)
    if not click_button("Load more"):
        end_of_list = True  # no button rendered: the list is exhausted
        break
    tiles = wait_more(before)
    if len(tiles) <= before:  # the promo can open late and swallow the click: close it, try once more
        close_app_promo(settle=0)
        if click_button("Load more"):
            tiles = wait_more(before)
    if len(tiles) <= before:
        raise RuntimeError(f"Load more added no tiles ({before} stayed {len(tiles)}): {json.dumps(page_info())}")
    clicks += 1
    print("after Load more:", len(tiles), "tiles")
    time.sleep(1.5)
if not end_of_list:
    print(f"stopped at MAX_CLICKS={MAX_CLICKS}; list not exhausted")
seen, rows = set(), []
for t in tiles:  # dedupe by url; tiles without a url are kept
    if t.get("url") in seen:
        continue
    if t.get("url"):
        seen.add(t["url"])
    rows.append(t)
print("rows:", len(rows), "| url now:", js_retry("location.href"))
print(rows[0] if rows else None)
```

Real output from a fresh cloud browser (people's names replaced with `<name>`):

```text
{"url": "https://www.rottentomatoes.com/m/oppenheimer_2023", "title": "Oppenheimer (2023)", "tomatometer": "93", "reviews": 510, "popcornmeter": "91", "audience": "10,000+ Verified Ratings", "rating": "R", "genres": ["Biography", "History", "Drama"], "released": "2023-07-21", "cast": ["<name>", "<name>", "<name>", "<name>", "<name>"]}
app promo closed: True
page 1: 28 tiles
after Load more: 58 tiles
after Load more: 88 tiles
stopped at MAX_CLICKS=2; list not exhausted
rows: 88 | url now: https://www.rottentomatoes.com/browse/movies_in_theaters/sort:popular?page=3
{'title': 'You Can See Everything', 'url': 'https://www.rottentomatoes.com/m/you_can_see_everything', 'tomatometer': '98%', 'popcornmeter': '97%', 'date': 'Opened Oct 16, 2026'}
```

## Fields

`rt_title(url)` returns exactly these keys (example values from the Oppenheimer / The Bear output above):

| Key | Source | Example / note |
|---|---|---|
| url | final URL after redirects | `"https://www.rottentomatoes.com/m/oppenheimer_2023"` |
| type | JSON-LD `@type` | `"Movie"`, `"TVSeries"`, `"TVSeason"` |
| title | `media-hero-json` `.content.title`, else JSON-LD `name` (which adds the year) | `"Oppenheimer"` |
| tomatometer | `media-scorecard-json` `.criticsScore.score` (a string on the page) | `93`; `None` until enough reviews |
| tomatometer_reviews | `.criticsScore.reviewCount` | `510` |
| tomatometer_avg | `.criticsScore.averageRating` | `"8.60"` (string, out of 10) |
| certified_fresh | `.criticsScore.certified` | `true` / `false` |
| top_critics_score, top_critics_reviews | `.overlay.criticsTop.score` / `.reviewCount` | `95`, `87` |
| popcornmeter | `.audienceScore.score` | `91` |
| popcornmeter_type | `.audienceScore.scoreType` | `"VERIFIED"` on movies, `"ALL"` on TV |
| audience_ratings | `.audienceScore.bandedRatingCount` | `"10,000+ Verified Ratings"` |
| audience_reviews | `.audienceScore.reviewCount` | `6023`; `None` on TV series |
| rating | JSON-LD `contentRating`, else Movie Info "Rating" before ` (` | `"R"`, `"TV-MA"` |
| rating_detail | Movie Info "Rating" | `"R (Nudity\|Language\|Some Sexuality)"` |
| genres | JSON-LD `genre`, else Movie Info "Genre" | `["Biography", "History", "Drama"]` |
| release_date | Movie Info "Release Date (Theaters)" (movies) or "Release Date" (TV) | `"Jul 21, 2023, Wide"`, `"Jun 23, 2022"` |
| streaming_date | Movie Info "Release Date (Streaming)" | `"Nov 21, 2023"`; `None` on TV |
| first_date | JSON-LD `dateCreated` | `"2023-07-21"` |
| runtime | Movie Info "Runtime" | `"3h 0m"`; `None` on TV |
| seasons | JSON-LD `numberOfSeasons` | `5` on a series; `None` on movies and seasons |
| network | Movie Info "Network" | `"Hulu"`; `None` on movies |
| box_office | Movie Info "Box Office (Gross USA)" | `"$330.0M"` |
| directors | JSON-LD `director[].name` | 1 name in each example |
| cast | JSON-LD `actor[].name` | top-billed only: 5, 4 and 4 names above; 0-5 across 12 in-theater titles |

`rt_browse(...)` returns `(rows, complete)`. Each row has exactly: `ems_id` (`emsId`), `title`, `url` (absolute, from `mediaUrl`), `type` (`"Movie"`), `tomatometer`, `certified_fresh`, `popcornmeter`, `release_text` (`releaseDateText`). `complete` is `True` only when the API said `hasNextPage: false`. Paging uses `pageInfo` `{"endCursor": "Mjk=", "hasNextPage": true}`, 30 items per page.

`rt_cast(url)` returns `[{"name", "character"}]`: 31 cast entries out of 37 `<cast-and-crew-card>` elements for Oppenheimer (the other 6 are crew, `data-role="all,crew"`).

The browser block's `rec` has `url, title, tomatometer, reviews, popcornmeter, audience, rating, genres, released, cast` (scores stay strings, `title` is the JSON-LD name with the year). Each tile has `title, url, tomatometer, popcornmeter, date` (scores as shown, `"98%"`).

## Gotchas

- **Missing scores are normal.** On `movies_coming_soon` page 1, 11 of 30 items had no Tomatometer and 26 no Popcornmeter (`"audienceScore": {"scorePercent": ""}`). On the title page `score` is absent and `bandedRatingCount` reads `"0 Verified Ratings"`. The `_int` helper turns these into `None`.
- **TV vs movie differences.** TV series pages label scores "Avg. Tomatometer"/"Avg. Popcornmeter", use `scoreType: "ALL"`, and have no exact `audienceScore.reviewCount`. The date label is "Release Date" (not "Release Date (Theaters)"). TV season pages (`/tv/<slug>/s05`) have no JSON-LD `contentRating`, so `rating` falls back to the Movie Info value, and the hero title contains an HTML entity (`Season 5 &ndash; The Bear`), unescaped by `_text`.
- **Browse HTML vs JSON page size.** The server-rendered browse page shows 28 tiles and a `pageInfo` script with `endCursor: "Mjc="`, but `/cnapi/browse/` returns 30 per page (`endCursor: "Mjk="`). Do not mix cursors between the two. `?page=2` on the HTML URL returned 56 cumulative tiles, but its JSON-LD `ItemList` stopped at 50 positions, so do not rely on the HTML JSON-LD for long lists.
- **Cursors** decode to a 0-based offset (`MA==` = 0, `Mjk=` = 29). Treat them as opaque and pass `endCursor` back. The raw `Mjk=`, the encoded `Mjk%3D`, and `quote(unquote(...), safe="")` of either all returned HTTP 200 and the same next cursor (`NTk=`); `rt_browse` unquotes first so a cursor copied from a URL is not double-encoded. A filter path with a comma (`genres:comedy,drama~sort:popular`) worked both raw and with the comma as `%2C`.
- **Truncation is explicit.** `rt_browse` returns `complete=False` (and the example prints it) when `max_pages` stops it while `hasNextPage` is still true. A page that fails after retries raises; it is never treated as the end of the list. The browser block raises if "Load more" adds no tiles after a promo-close retry, and prints when it stops at `MAX_CLICKS`.
- **Consent banner: leave it alone.** A fresh browser shows a OneTrust notice at the bottom ("This site is now part of Versant. By continuing, you agree to our Terms...") with a "Continue" button (`id="onetrust-accept-btn-handler"`). Clicking it accepts the terms and **reloads the page**: `performance.timeOrigin` changed and `document.readyState` went back to `loading` within 0.4 s. In a cold run, the tile read right after that click returned 0 tiles and the script exited with no data. With the banner still showing, "Load more" clicks worked (28 -> 58 tiles), so the browser block never clicks it.
- **App-promo modal blocks clicks.** An app-promo modal (`<rt-app-modal-content>`, close button `aria-label="Close"`, `data-rtappmanager="btnClose:click"`) did not appear on the first page view of a fresh browser but did appear on the second. While it was open, `elementFromPoint` at the "Load more" button returned the modal and the click added nothing (28 tiles stayed 28). Closing it does not reload the page. `close_app_promo()` clicks that exact element (`rt-app-modal-content [data-rtappmanager="btnClose:click"]`, an `<action-icon>`) only if it is visible, then confirms it went away; it never clicks some other "Close" button.
- **Load more updates the URL.** Each click appends 30 tiles in place and rewrites the URL to `?page=2`, `?page=3` via history (same `timeOrigin`, no reload).
- **Confirm the page before reading it.** Right after `goto_url` from the title page to a browse page, `location.href` was already the new URL but `readyState` was `loading`, then `interactive`; `wait_for_load()` alone only checks `readyState`, which can still be the old document's. `open_page()` waits for the requested URL, `complete`, and a page-specific selector together, and raises with `page_info()` instead of reading 0 tiles. Match AX button names case-insensitively.
- **Browser call timeouts.** A slow `cdp` round trip raises a `TimeoutError` subclass, but `js` re-raises a timed-out `Runtime.evaluate` as `RuntimeError("Runtime.evaluate timed out; ...")`, so `except TimeoutError` alone misses it. `is_harness_timeout` accepts both; `open_page` and `js_retry` retry only those and re-raise real JS errors; other code lets them raise.
- **Region redirects.** Bare `https://rottentomatoes.com/` redirects to `https://www.rottentomatoes.com/`. Title, browse and `/cnapi/` URLs returned HTTP 200 with no redirect from both vantage points used, but both were in the US (the site's OneTrust geolocation reported `"country":"US"` for the cloud browser and for the plain-HTTP network). Behavior from other countries was not tested; check `location.href` in the browser, or the `url` key `rt_title` returns (the final URL after redirects), if you run elsewhere.
- **Selector drift.** The `data-qa="item-label"`/`item-value` and `cast-and-crew-card` markup are server-rendered web components. The embedded JSON (`media-scorecard-json`, JSON-LD) is the more stable source; prefer it when a field exists in both.
- **Pacing.** About 45 HTTP requests at 1-1.5 s spacing returned no 429s or challenges. No published rate limit was found, so keep at least ~1 s between requests. `rt_get` retries 429/500/502/503/504 and network errors up to 4 tries, honoring `Retry-After` (seconds or HTTP-date) up to `MAX_WAIT` (120 s) or else backing off 2, 4, 8 s, then raises. A `Retry-After` above 120 s raises at once instead of sleeping, and there is no sleep after the last attempt. In `rt_browse` that raise ends the run; in the enrich loop of block 1 a 403, or a 429 whose retries ran out, ends the run; a title that failed with any other HTTP error (such as a 404) or with network or 5xx errors after its retries is recorded in `failed`, and the loop goes on to the next title after the same 1.5 s wait as a success. The over-120 s raise (`RuntimeError`) is not caught and also ends the run.
- **User-Agent.** The HTTP block sends urllib's own truthful `Python-urllib/3.x` (no override), which got HTTP 200 on title, browse and `/cnapi/` URLs. It uses its own `rt_get` rather than the harness `http_get`, because `http_get` sends a browser-style `Mozilla/5.0` UA and does not retry.

## What does not work

- `/napi/browse/...` (an older endpoint name) returns HTTP 404. Use `/cnapi/browse/...`.
- `/cnapi/browse/<unknown_list>/...` returns HTTP 404.
- Removed or wrong slugs (`/m/<bad_slug>`) return HTTP 404 (`urllib.error.HTTPError`, not retried); catch and skip.
- Full cast is not on the main title page (JSON-LD has at most the top 5 names, sometimes 0); it needs the extra `/cast-and-crew` request.
- Exact audience rating counts are not exposed for TV series, only banded text like `"10,000+ Ratings"`.
- No 403, 429, challenge or captcha was seen on 2026-10-23 on either path. A 429 or 5xx on the HTTP path gets the bounded `rt_get` retry above (at most 4 tries, `Retry-After` honored up to 120 s, then it raises); anything else (a 403, challenge, captcha, or a 429 in the browser) means stop and back off. Neither block changes its client identity, session or network to get past it.
