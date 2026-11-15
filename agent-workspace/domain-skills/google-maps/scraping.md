# Google Maps — Scraping places from a search

Field-tested against www.google.com/maps on 2026-10-23 using a Browser Use cloud browser and plain HTTP (Python `urllib`, no browser).

robots.txt (checked 2026-10-23) allows /maps/search/, /maps/place/ and /search?*tbm=map for all user agents; it disallows the rest of /search.

## Quick summary

- **Best source: the `/search?tbm=map` JSON the page itself loads.** The logged-out search page HTML (`/maps/search/<query>`) contains a `<link href="/search?tbm=map&...">` preload URL. Fetching it returns JSON with 20 places per page, including name, rating, review count, categories, full address, phone, website, lat/lng, place_id and the full weekly hours. Paging is an `!8i<offset>` token in the `pb` parameter. No browser needed.
- Observed: "coffee shops in Austin TX" -> 9 requests (offsets 0-160, 2 s apart) -> 175 result rows in the run that counted them -> **150 to 175 unique places** across nine runs (175 in the run shown below: 145 with a phone, 167 with a website, 168 with weekly hours; an earlier run gave 156 with 130 / 149 / 149); offset 180 returned an empty list. The unique count varies because pages can overlap by a different amount each run (see Gotchas). "plumbers in Houston TX" gave 200 unique places from 10 pages, "pizza in Chicago IL" 153 from 8.
- **Browser fallback: scroll the results feed** (`div[role=feed]`) and read the cards. Card-level fields only (name, rating, reviews, category, short address, open status, place_id, lat/lng). The feed only lazy-loads in a visible tab, so bringing the tab to the front is an explicit opt-in (`FOREGROUND = True`); left hidden it stopped at 6-12 cards. With the tab visible: 120 cards = 111, 112 and 116 unique places in three runs (coffee shops in Austin TX, reached "You've reached the end of the list"; the feed repeats some places, so the code dedupes by place_id), 108 cards (bookstores in Portland OR, end reached), 78 (pizza in Chicago IL, feed stopped loading without the end message).
- **Phone, website, hours for one place in the browser:** open `https://www.google.com/maps/place/?q=place_id:<id>` and read `[data-item-id]` elements.
- Every logged-out session showed "You're seeing a limited view of Google Maps". Search, paging and place pages still worked; review text was not tried.

## What works

### 1. All fields via the tbm=map JSON (plain Python, no browser)

Runs as-is with `python3` or inside `browser-harness` (standard library only).

```python
import gzip, html, json, os, re, tempfile, time, urllib.error, urllib.parse, urllib.request

HEADERS = {
    "User-Agent": "browser-harness-skill-example",   # a truthful client UA was enough; no browser UA needed
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
}

def get(url, tries=3):
    for i in range(tries):                            # retry transient errors with backoff, then raise
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                return data.decode("utf-8")
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:   # ConnectionError covers resets mid-read
            if getattr(e, "code", None) in (403, 429):   # blocked or rate-limited: stop, never retry
                raise RuntimeError(f"blocked: HTTP {e.code} on {url}; stop and back off") from e
            if i == tries - 1:
                raise
            time.sleep(2 ** (i + 1))

def at(o, *path):
    """Safe nested index: at(p, 4, 7) -> p[4][7] or None."""
    for i in path:
        if not isinstance(o, list) or i >= len(o):
            return None
        o = o[i]
    return o

def parse_place(p):
    hours = {}
    for day in at(p, 203, 0) or []:
        slots = [s[0] for s in (at(day, 3) or []) if s and s[0]]
        if at(day, 0):
            hours[day[0]] = ", ".join(slots).replace(" ", " ").replace(" ", " ")
    pid = at(p, 78)
    web = at(p, 7, 0)
    if web and web.startswith("/url?"):               # non-browser UAs get a /url?q=<site> redirect: unwrap it
        web = urllib.parse.parse_qs(urllib.parse.urlsplit(web).query).get("q", [web])[0]
    ftid = at(p, 10) or ""
    cid = str(int(ftid.split(":")[1], 16)) if ":" in ftid else None
    return {
        "name": at(p, 11),
        "rating": at(p, 4, 7),
        "reviews": at(p, 4, 8),
        "category": at(p, 13, 0),
        "categories": at(p, 13) or [],
        "address": at(p, 39),
        "neighborhood": at(p, 14),
        "phone": at(p, 178, 0, 0),
        "phone_e164": at(p, 178, 0, 3),
        "website": web,
        "lat": at(p, 9, 2),
        "lng": at(p, 9, 3),
        "place_id": pid,
        "cid": cid,
        "maps_url": f"https://www.google.com/maps/place/?q=place_id:{pid}" if pid else None,
        "open_now": (at(p, 203, 1, 4, 0) or "").replace(" ", " ") or None,
        "hours": hours,
    }

def search_places(query, max_results=200, pause=2.0):
    q = urllib.parse.quote_plus(query)
    page = get(f"https://www.google.com/maps/search/{q}?hl=en&gl=us")
    m = re.search(r'<link href="(/search\?tbm=map[^"]+)"', page)
    if not m:
        raise RuntimeError("no /search?tbm=map preload link (consent page or layout change?)")
    base = "https://www.google.com" + html.unescape(m.group(1))
    # page-size token: served percent-encoded (%217i20) on 2026-10-23; accept a literal !7i20 too
    size = next((t for t in ("%217i20", "!7i20") if t in base), None)
    if not size:
        raise RuntimeError("no !7i20 page-size token in the preload URL; cannot page")
    bang = "%21" if size.startswith("%") else "!"
    places, offset = {}, 0
    while len(places) < max_results:
        url = base if offset == 0 else base.replace(size, f"{size}{bang}8i{offset}", 1)
        raw = get(url)
        d = json.loads(raw[raw.index("\n") + 1:])          # strip the )]}' guard line
        rows = at(d, 64) or []
        if not rows:
            break                                         # past the last page
        before = len(places)
        for r in rows:
            p = at(r, 1)
            if not p or not at(p, 11):                    # defensive: skip any row without a named place
                continue
            place = parse_place(p)
            places.setdefault(place["place_id"] or place["name"], place)
        if len(places) == before:                         # paging token ignored: fail instead of looping on page 1
            raise RuntimeError(f"offset {offset} added no new places")
        offset += 20
        time.sleep(pause)
    return list(places.values())[:max_results]

places = search_places("coffee shops in Austin TX")
print(len(places), "places")
print(json.dumps(places[:2], indent=1, ensure_ascii=False))
print("with phone:", sum(1 for p in places if p["phone"]),
      "with website:", sum(1 for p in places if p["website"]),
      "with hours:", sum(1 for p in places if p["hours"]))
out = os.path.join(tempfile.gettempdir(), "google_maps_places.json")   # temp dir, not the cwd
with open(out, "w", encoding="utf-8") as f:
    json.dump(places, f, indent=1, ensure_ascii=False)
print("saved", out)
```

Observed output (trimmed):

```text
175 places
[
 {
  "name": "Jo's Coffee – South Congress",
  "rating": 4.4,
  "reviews": 2004,
  "category": "Coffee shop",
  "categories": ["Coffee shop", "Cafe", "Takeout Restaurant", "Sandwich shop"],
  "address": "1300 S Congress Ave, Austin, TX 78704",
  "neighborhood": "Bouldin Creek",
  "phone": "(512) 852-2300",
  "phone_e164": "+15128522300",
  "website": "https://www.joscoffee.com/south-congress-jos",
  "lat": 30.2510458,
  "lng": -97.7493717,
  "place_id": "ChIJ1S_Bov20RIYRe7MiR8tYawY",
  "cid": "462561016830669691",
  "maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJ1S_Bov20RIYRe7MiR8tYawY",
  "open_now": "Open · Closes 7 PM",
  "hours": {"Friday": "7 AM–7 PM", "Saturday": "7 AM–7 PM", "Sunday": "7 AM–7 PM", ...}
 },
 { "name": "Epoch Coffee", ... }
]
with phone: 145 with website: 167 with hours: 168
saved <temp dir>/google_maps_places.json
```

The JSON file goes to the system temp dir (`tempfile.gettempdir()`), not the current directory; change `out` to keep it elsewhere.

How the pieces fit (all observed in this run):

- The response starts with a `)]}'` guard line; JSON starts after the first newline.
- `d[64]` is the result list. Each row is `[meta, place]` with a 260-element `place` list. All 528 rows over 3 queries (27 pages) were places; no sponsored or empty rows appeared. The code still skips any row without a place name, in case ads show up for other queries.
- The preload URL already contains `!7i20` (page size), percent-encoded as `%217i20` in the served HTML. The page's own scroll requests add `!8i20`, `!8i40`, ... so the code inserts `!8i<offset>` right after `!7i20`, in whichever encoding the URL uses. If the token is missing, or a page adds no new places (offset ignored), it raises instead of re-reading page 1.
- `get()` retries a failed request (URL errors, connection resets, timeouts) twice (2 s, then 4 s) and then raises, so a transient error never silently ends the list early. HTTP 403 or 429 means blocked or rate-limited: `get()` raises at once without retrying; stop and back off.
- User-Agent: the Python default, `curl/8.7.1` and `browser-harness-skill-example` all got the preload link and 20 rows per page. Non-browser UAs get each website as a `/url?q=<site>&...` redirect, which `parse_place` unwraps.
- Pages can overlap, so dedupe by `place_id`, not by name (chains such as "Epoch Coffee" have several locations with the same name).
- `hours` keys start with today (the run was on a Friday, so `Friday` came first).

### 2. Browser: scroll the results feed and read the cards

Use this when you want exactly what the UI shows, or as a fallback if the JSON layout changes. No phone or website on the cards.

```python
import json, re, time, urllib.parse

query = "coffee shops in Austin TX"
# Opt-in: the feed only lazy-loads in a visible tab (a hidden tab stopped at 6-12 cards).
# True brings this tab to the front of the browser. Leave False on someone's own Chrome
# unless they agreed to it; method 1 needs no tab at all.
FOREGROUND = False
tid = new_tab()            # blank tab first
if FOREGROUND:
    activate_tab(tid)      # make it visible BEFORE loading the search
goto_url("https://www.google.com/maps/search/" + urllib.parse.quote_plus(query) + "?hl=en")
wait_for_load()
wait(3)

def try_js(expr):
    try:
        return js(expr)
    except RuntimeError:     # js() raised "Runtime.evaluate timed out" once while a batch of cards rendered
        return None

COUNT = "document.querySelectorAll('div[role=feed] a[href*=\"/maps/place/\"]').length"
last, stalls, stop = 0, 0, "scroll cap (80) reached"
for _ in range(80):
    try_js("(()=>{const f=document.querySelector('div[role=feed]'); if(f) f.scrollTop=f.scrollHeight})()")
    time.sleep(2)
    n = try_js(COUNT) or last
    if try_js("(document.querySelector('div[role=feed]')||{innerText:''}).innerText.includes('end of the list')"):
        stop = "end of the list"
        break
    stalls = stalls + 1 if n == last else 0
    if stalls >= 8:          # ~16 s with no new cards: the feed stopped loading
        stop = "feed stalled, PARTIAL list" + ("" if FOREGROUND else " (hidden tab: set FOREGROUND = True)")
        break
    last = n
print("stopped:", stop)

cards = js(r"""[...document.querySelectorAll('div[role=feed] a[href*="/maps/place/"]')].map(a => {
  const card = a.parentElement;
  const star = card.querySelector('[role=img][aria-label*="stars"]');
  return {name: a.getAttribute('aria-label'), href: a.href,
          stars: star ? star.getAttribute('aria-label') : null,
          lines: card.innerText.split('\n').map(s => s.trim()).filter(Boolean)};
})""") or []

places = {}                  # the feed repeats some places: key by place_id, fall back to the URL
for c in cards:
    m = re.match(r"([\d.]+) stars?\s*([\d,]*)", c["stars"] or "")
    info = next((l for l in c["lines"] if " · " in l and not l.startswith(("Open", "Closed"))), "")
    parts = [s.strip() for s in info.split("·") if s.strip() and not s.strip().startswith("")]
    status = next((l for l in c["lines"] if l.startswith(("Open", "Closed", "Temporarily", "Permanently"))), None)
    pid = re.search(r"!19s(ChIJ[\w-]+)", c["href"])
    ll = re.search(r"!3d(-?[\d.]+)!4d(-?[\d.]+)", c["href"])
    maps_url = c["href"].split("?")[0]
    places.setdefault(pid.group(1) if pid else maps_url, {
        "name": c["name"],
        "rating": float(m.group(1)) if m else None,
        "reviews": int(m.group(2).replace(",", "")) if m and m.group(2) else None,
        "category": parts[0] if parts else None,
        "address": parts[-1] if len(parts) > 1 else None,
        "status": status.replace(" ", " ") if status else None,
        "place_id": pid.group(1) if pid else None,
        "lat": float(ll.group(1)) if ll else None,
        "lng": float(ll.group(2)) if ll else None,
        "maps_url": maps_url,
    })
places = list(places.values())
print(len(cards), "cards ->", len(places), "unique places")
print(json.dumps(places[:2], indent=1, ensure_ascii=False))
```

Observed output as written (`FOREGROUND = False`, hidden tab), trimmed:

```text
stopped: feed stalled, PARTIAL list (hidden tab: set FOREGROUND = True)
6 cards -> 6 unique places
[ ... same card fields as below ... ]
```

Observed output with `FOREGROUND = True`, trimmed:

```text
stopped: end of the list
120 cards -> 116 unique places
[
 {
  "name": "Jo's Coffee – South Congress",
  "rating": 4.4,
  "reviews": 2004,
  "category": "Coffee shop",
  "address": "1300 S Congress Ave",
  "status": "Open · Closes 7 PM",
  "place_id": "ChIJ1S_Bov20RIYRe7MiR8tYawY",
  "lat": 30.2510458,
  "lng": -97.7493717,
  "maps_url": "https://www.google.com/maps/place/Jo%27s+Coffee+%E2%80%93+South+Congress/data=!4m7!3m6!1s0x8644b4fda2c12fd5:0x66b58cb4722b37b!8m2!3d30.2510458!4d-97.7493717!16s%2Fm%2F020z01l!19sChIJ1S_Bov20RIYRe7MiR8tYawY"
 },
 ...
]
```

`stopped:` always says why the loop ended, so a partial list is never silent. Card anatomy observed: the link `a[href*="/maps/place/"]` has `aria-label` = place name; the rating is `[role=img]` with `aria-label` like `4.9 stars 432 Reviews`; card text lines are name, `4.9(432)`, `Coffee shop · <accessibility icon> · 3908 Avenue B`, an optional one-line description, then `Open · Closes 2 PM`. The card address is the street only (no city/ZIP). In an earlier 112-place run, all 112 unique places had name, rating, reviews, category, address, place_id and lat/lng; 6 had no open/closed line, so `status` is `None` for those. The 120 cards held 8 repeated place_ids (for example "Brother Friend Coffee South" and "Epoch Coffee" appeared twice), which the `setdefault` on place_id removes.

### 3. Browser: phone, website, address and weekly hours for one place

```python
import json

def place_details(place_id):
    goto_url(f"https://www.google.com/maps/place/?q=place_id:{place_id}&hl=en")
    wait_for_load()
    wait(3)
    return js(r"""(() => {
      const item = sel => document.querySelector(`[data-item-id${sel}]`);
      const label = (el, prefix) => el ? (el.getAttribute('aria-label') || '').replace(prefix, '').trim() : null;
      const phone = item('^="phone:tel:"');
      const site = item('="authority"');
      return {
        name: (document.querySelector('h1') || {}).innerText || null,
        address: label(item('="address"'), 'Address:'),
        phone: label(phone, 'Phone:'),
        website: site ? site.href : null,
        hours: [...document.querySelectorAll('[aria-label$="Copy open hours"]')]
                 .map(e => e.getAttribute('aria-label').replace(', Copy open hours', '').replace(/ /g, ' ')),
      };
    })()""")

tid = new_tab()
for pid in ["ChIJ1S_Bov20RIYRe7MiR8tYawY", "ChIJP8p2kJC1RIYR2qrGoXZtZCk"]:
    print(json.dumps(place_details(pid), indent=1, ensure_ascii=False))
    wait(2)
```

Observed output (trimmed):

```text
{
 "name": "Jo's Coffee – South Congress",
 "address": "1300 S Congress Ave, Austin, TX 78704",
 "phone": "(512) 852-2300",
 "website": "https://www.joscoffee.com/south-congress-jos",
 "hours": ["Friday, 7 AM to 7 PM", "Saturday, 7 AM to 7 PM", ...]
}
{
 "name": "Terrible Love Coffee",
 "address": "3908 Avenue B, Austin, TX 78751",
 "phone": null,
 "website": "http://terriblelovecoffee.com/",
 "hours": ["Friday, 7:30 AM to 2 PM", ...]
}
```

`phone: null` matches the JSON source: that place lists no phone. Place-page `[data-item-id]` values seen: `address`, `authority` (website link), `phone:tel:+1...`, `oloc` (plus code).

## Fields

| Field | JSON path (method 1) | Browser source | Example |
|---|---|---|---|
| name | `p[11]` | card link `aria-label`, place `h1` | `Jo's Coffee – South Congress` |
| rating | `p[4][7]` | `[role=img]` aria `4.4 stars 2,004 Reviews` | `4.4` |
| reviews | `p[4][8]` | same aria label | `2004` |
| category / categories | `p[13]` | first ` · ` part of card line | `["Coffee shop", "Cafe", ...]` |
| address (full) | `p[39]` (`p[18]` = name + address) | `[data-item-id=address]` aria | `1300 S Congress Ave, Austin, TX 78704` |
| neighborhood | `p[14]` | - | `Bouldin Creek` |
| phone | `p[178][0][0]`, E.164 at `p[178][0][3]` | `[data-item-id^="phone:tel:"]` aria | `(512) 852-2300` |
| website | `p[7][0]` (a `/url?q=<site>` redirect for non-browser UAs), domain at `p[7][1]` | `a[data-item-id=authority]` href | `https://www.joscoffee.com/...` |
| lat / lng | `p[9][2]`, `p[9][3]` | `!3d` / `!4d` in card href | `30.2510458, -97.7493717` |
| place_id | `p[78]` | `!19s` in card href | `ChIJ1S_Bov20RIYRe7MiR8tYawY` |
| cid | 2nd hex half of `p[10]` | `!1s0x...:0x...` in card href | `462561016830669691` |
| open now | `p[203][1][4][0]` | card status line | `Open · Closes 7 PM` |
| weekly hours | `p[203][0][i]` = `[day, n, [y,m,d], [[text, ...]], ...]` | `[aria-label$="Copy open hours"]` | `Friday: 7 AM–7 PM` |
| timezone | `p[30]` | - | `America/Chicago` |

`https://www.google.com/maps/place/?q=place_id:<place_id>` opened the matching place page in the browser (checked for two places).

## Gotchas

- **The feed needs a visible tab, and that is opt-in.** `new_tab()` opens a hidden tab so the user's view is not changed; there the feed loaded 5-12 cards and never requested more. `Emulation.setFocusEmulationEnabled`, overriding `document.visibilityState`, and mouse-wheel input (timed out in the hidden tab) did not help. Calling `activate_tab()` after the search had loaded did not recover the page either; creating the tab, activating it, then navigating (`FOREGROUND = True` in method 2) reached 108 and 120 cards. Only set it when taking the foreground is acceptable (for example an isolated cloud browser); otherwise use method 1.
- **The feed can stop early with no end message.** "pizza in Chicago IL" stopped at 78 cards after 3 `tbm=map` requests, spinner still showing. Detect stalls by card count, as the code does. Method 1 does not depend on the feed.
- **Logged-out "limited view".** Every session showed "You're seeing a limited view of Google Maps. See more". Search results, paging and place pages still worked.
- **No consent banner** was shown to the US cloud browser or to plain HTTP from a US network with `hl=en`. A request from an EU IP was not tested; if the search HTML has no `/search?tbm=map` link, method 1 raises instead of returning garbage.
- **Results repeat, in both methods.** JSON pages can overlap: for "coffee shops in Austin TX", 175 rows held 158 unique place_ids in one run (overlaps of 1, 7 and 3 between some consecutive pages, mostly in the last pages), while "pizza in Chicago IL" (153 rows) and "plumbers in Houston TX" (200 rows) had no repeats. The browser feed also repeats cards (120 cards, 112 unique). Always dedupe by place_id and report the unique count.
- **Positional JSON, no field names.** The indices above are what Google served on 2026-10-23. If they drift, find the new index by searching a parsed place for a known value (e.g. the phone string) rather than guessing. `at()` returns `None` instead of crashing when an index is missing.
- **Sponsored rows** were not seen in `d[64]` in this run (0 of 528 rows). If one appears without a place name, the code skips it.
- **`js()` can time out.** One feed run raised `Runtime.evaluate timed out` while a batch of cards rendered; method 2 wraps its polling calls in `try_js` so a slow poll counts as a stall instead of crashing.
- **Narrow, unicode spaces.** Hours and status strings use U+202F (narrow no-break space) before AM/PM; the code replaces it with a normal space.
- **Pacing.** The runs used 2 s between JSON pages and 2 s between feed scrolls, with no blocks or errors over about 150 plain HTTP requests, 20 browser searches and 9 place-page loads. No rate limit was hit, so none is documented here; keep the pauses.
- A "Help us improve Google Maps" survey card appeared in the bottom right of the map. It did not block the feed and needed no action.

## What does not work

- **The search HTML alone has no results.** `http_get`/`urllib` on `/maps/search/<query>` returned about 213 KB of app shell with no place names in it; the results only come from the `/search?tbm=map` request.
- **Scrolling a background tab** (see Gotchas): stuck at 5-12 cards, also with focus emulation or a faked `visibilityState`.
- **Price level** was not found: `p[4][2]` was `null` and no `$`-prefixed string appeared in any of the 40 place arrays checked (page 1 of two queries), so it is not in the fields table.
- **Phone and website are not on the result cards** in the browser; use method 1 or method 3.
