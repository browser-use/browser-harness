# Ticketmaster - Events by keyword or category (name, date, venue, event URL)

Field-tested against www.ticketmaster.com on 2026-11-01 using a Browser Use cloud browser (US exit IP), logged out. No CAPTCHA, queue or block page appeared in about 40 page loads at 2 s or more spacing.

robots.txt (read in the browser on 2026-11-01, `User-agent: *`) has no rule matching `/search?q=`, `/discover/...` or `/<slug>/event/<id>`, and disallows `/*event/*?preselect`, `/*event/*&preselect`, `/search*searchVariant=`, `/search*f_discoAiSearch=`, `/json/search/event/*`, `/api/ismds/event`, `*did=` and the checkout, member and queue paths; this skill only opens `/search?q=...&sort=...`, `/discover/...` and plain event URLs, and checks every URL against the file before loading it.

## Quick summary

- **Every list page ships its first 20 events in `__NEXT_DATA__`.** `/search?q=<kw>` has `searchEvents(...)`, `/discover/<category>` has `categoryEvents(...)`, `/discover/<city>` has `cityEvents(...)`, all under `props.pageProps.initialReduxState.api.queries`. Each event has `title`, `id`, `url`, `dates.startDate` (UTC), `timeZone` and `venue` (`name`, `city`, `state`, address, lat/long).
- **More pages = the page's own "More Events" button.** Clicking it makes the page fetch `/api/search/events?...&page=N` (search), `/api/search/events/category/<id>?page=N` (category) or `/api/search/events/city?page=N...` (city), 20 events each, same shape. The block clicks the button and reads that response through CDP `Network` events; it never requests those URLs itself.
- **Filters are plain URL parameters** written by the page's own controls: `sort=relevance|date` on search; `classificationId=<sub-genre id>` and `startDate=YYYY-MM-DD&endDate=YYYY-MM-DD` on `/discover/...` (the "This Weekend" button wrote exactly that).
- **Event pages** come in two builds (`/globalevent/[eventId]` and `/naevent/[eventId]` in `__NEXT_DATA__.page`); both ship one schema.org Event JSON-LD block with name, local start time, venue and address, so the block reads that.
- **Many list rows are partner events** (10 of 20 on `/discover/chicago`: TicketWeb, hotel packages) whose `url` points off-site; `on_ticketmaster` is `False` for them and `event_details()` refuses them.

## What works: search, category, city and event pages in one run

Self-contained; opens one tab (robots.txt first, then every page in the same tab) and closes it at the end. About 1-3 minutes in a cloud browser (48 s on 2026-11-01).

```python
import json, re, time
from datetime import datetime
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

BASE = "https://www.ticketmaster.com"

# robots.txt, group "User-agent: *", Google-style matching: longest pattern wins, Allow wins a tie.
# Read in the browser tab: plain urllib got HTTP 403 for robots.txt (curl got 200), and this skill does not change its UA.
_TAB = []

def _robots_rules():
    new_tab(BASE + "/robots.txt")
    _TAB.append(current_tab())
    wait_for_load()
    txt = js("document.body.innerText")
    if "User-agent" not in (txt or ""):
        raise RuntimeError("could not read robots.txt; stop")
    rules, in_star, prev_ua = [], False, False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            in_star = (in_star and prev_ua) or v == "*"
            prev_ua = True
            continue
        prev_ua = False
        if in_star and k in ("allow", "disallow") and v:
            rules.append((k == "allow", v))
    return rules

RULES = _robots_rules()

def robots_allowed(path):
    best_len, ok = -1, True
    for allow, pat in RULES:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best_len or (len(pat) == best_len and allow)):
            best_len, ok = len(pat), allow
    return ok

def _path(url):
    u = urlparse(url)
    return u.path + ("?" + u.query if u.query else "")

def open_page(path):
    """Open an allowed www.ticketmaster.com page and return its __NEXT_DATA__ (the state the page ships in its HTML)."""
    if not robots_allowed(path):
        raise PermissionError(f"robots.txt disallows {path}")
    goto_url(BASE + path)   # the tab opened for robots.txt
    deadline = time.time() + 30
    while time.time() < deadline:
        try:   # event pages can keep the main thread busy for >5 s, so a single evaluate may time out
            raw = js("(() => { const s = document.getElementById('__NEXT_DATA__');"
                     " return document.readyState !== 'loading' && s ? s.textContent : null })()")
            href = js("location.href")
        except RuntimeError:
            raw = None
        if raw:
            final = _path(href.split("#")[0])
            if not robots_allowed(final):
                raise PermissionError(f"{path} redirected to disallowed {final}")
            return json.loads(raw)
        time.sleep(1)
    info = page_info()
    raise RuntimeError(f"no page state on {info['url']} ({info['title']!r}); a queue, block or challenge page? "
                       "Stop here, do not retry around it.")

def _row(e):
    d, v = e.get("dates") or {}, e.get("venue") or {}
    start, tz = d.get("startDate"), e.get("timeZone")
    local = None
    if start and tz and not e.get("tba"):
        local = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))
    url = e.get("url") or ""
    return {
        "id": e.get("id"),
        "name": e.get("title"),
        "local_date": local.strftime("%Y-%m-%d") if local else None,
        "local_time": local.strftime("%H:%M") if local and d.get("dateDisplay") == "showDateTime" else None,
        "date_display": d.get("dateDisplay"),   # showDateTime has a time; other values show the date only
        "start_utc": start,
        "time_zone": tz,
        "venue": v.get("name"),
        "city": v.get("city"),
        "state": v.get("state"),
        "country": v.get("countryCode"),
        "url": url,
        # Partner events (TicketWeb, hotel packages, ...) link off-site; only www.ticketmaster.com/.../event/<id> is an event page here.
        "on_ticketmaster": urlparse(url).netloc == "www.ticketmaster.com" and "/event/" in url,
        "status": ("cancelled" if e.get("cancelled") else "postponed" if e.get("postponed")
                   else "rescheduled" if e.get("rescheduled") else "sold_out" if e.get("soldOut") else "listed"),
    }

LIST_KEYS = ("searchEvents(", "categoryEvents(", "cityEvents(")

def _first_page(nd):
    q = nd["props"]["pageProps"]["initialReduxState"]["api"]["queries"]
    hits = [(k, v["data"]) for k, v in q.items() if k.startswith(LIST_KEYS) and v.get("data")]
    if len(hits) != 1:
        raise RuntimeError(f"expected one event list in the page state, found {[k for k, _ in hits]}")
    return hits[0]

def _retry(fn, tries=6):
    """Ad-heavy pages can keep the tab busy for a few seconds; a CDP call then times out. Retry a few times."""
    for i in range(tries):
        try:
            return fn()
        except (RuntimeError, TimeoutError):
            if i == tries - 1:
                raise
            time.sleep(2)

def _more_events_button():
    for n in _retry(lambda: cdp("Accessibility.getFullAXTree")["nodes"]):
        if (n.get("role") or {}).get("value") == "button" and (n.get("name") or {}).get("value") == "More Events":
            return n["backendDOMNodeId"]
    return None

def _click_more_and_read(timeout=20):
    """Click the page's own "More Events" button and return the JSON the page itself fetches for it."""
    node = None
    for _ in range(8):   # the button renders after hydration
        node = _more_events_button()
        if node:
            break
        time.sleep(1)
    if node is None:
        return None
    _retry(lambda: cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=node))
    q = _retry(lambda: cdp("DOM.getBoxModel", backendNodeId=node)["model"]["content"])
    drain_events()
    click_at_xy(sum(q[0::2]) / 4, sum(q[1::2]) / 4)
    rid, deadline = None, time.time() + timeout
    while time.time() < deadline:
        for ev in drain_events():
            p = ev.get("params") or {}
            if ev.get("method") == "Network.responseReceived" and p["response"]["url"].startswith(BASE + "/api/search/events"):
                if p["response"]["status"] != 200 or not robots_allowed(_path(p["response"]["url"])):
                    raise RuntimeError(f"More Events got {p['response']['status']} for {p['response']['url']}; stop here")
                rid = p["requestId"]
            elif rid and ev.get("method") == "Network.loadingFinished" and p.get("requestId") == rid:
                return json.loads(_retry(lambda: cdp("Network.getResponseBody", requestId=rid)["body"]))
        time.sleep(0.2)
    raise RuntimeError("More Events was clicked but no event list response arrived")

def list_events(path, max_pages=1, pause_s=2.0):
    """Events from a /search?q=... or /discover/... page: page 1 from the page state, later pages through the
    page's own "More Events" button (20 per page). Returns (rows, total, status)."""
    nd = open_page(path)
    _retry(lambda: cdp("Network.enable"))
    key, data = _first_page(nd)
    total, rows, seen = data.get("total"), [], set()
    for page in range(1, max_pages + 1):
        new = [r for r in map(_row, data.get("events") or []) if r["id"] not in seen]
        seen.update(r["id"] for r in new)
        rows.extend(new)
        if len(seen) >= (total or 0):
            return rows, total, "complete"
        if page == max_pages:
            return rows, total, "truncated_max_pages"
        time.sleep(pause_s)
        data = _click_more_and_read()
        if data is None:
            return rows, total, "no_more_button"

def search(keyword, sort="relevance", max_pages=1):
    """Keyword search. sort: relevance | date (the page's own Sort by options)."""
    return list_events("/search?" + urlencode({"q": keyword, "sort": sort}), max_pages)

def discover(category, classification_id=None, start_date=None, end_date=None, max_pages=1):
    """Category pages: concerts | sports | arts-theater | family, or a city slug such as new-york-city.
    classification_id = a sub-genre id from the category menu; dates as YYYY-MM-DD (what the page's date filter writes)."""
    params = {k: v for k, v in (("classificationId", classification_id), ("startDate", start_date),
                                 ("endDate", end_date)) if v}
    return list_events(f"/discover/{category}" + ("?" + urlencode(params) if params else ""), max_pages)

def event_details(url):
    """Name, date, venue and status from an event page (/.../event/<id>). Refuses non-Ticketmaster URLs."""
    u = urlparse(url)
    if u.netloc != "www.ticketmaster.com" or "/event/" not in u.path or u.query:
        raise ValueError(f"not a plain www.ticketmaster.com event URL: {url}")
    nd = open_page(u.path)
    # Two page builds exist (__NEXT_DATA__.page "/globalevent/[eventId]" with eventInfo, "/naevent/[eventId]" with
    # edpData); both ship one schema.org Event JSON-LD block, so read that.
    lds = json.loads(js("JSON.stringify([...document.querySelectorAll('script[type=\"application/ld+json\"]')]"
                        ".map(s => { try { return JSON.parse(s.textContent) } catch (e) { return null } }))"))
    ev = next((x for x in lds if isinstance(x, dict) and x.get("startDate") and x.get("location")), None)
    if not ev:
        raise RuntimeError(f"no Event JSON-LD on {page_info()['url']}")
    loc, addr = ev.get("location") or {}, (ev.get("location") or {}).get("address") or {}
    perf = ev.get("performer") or []
    return {
        "id": u.path.rstrip("/").rsplit("/", 1)[-1],
        "name": ev.get("name"),
        "start_local": ev.get("startDate"),     # venue-local wall time, no offset: "2026-11-01T18:15"
        "status": (ev.get("eventStatus") or "").rsplit("/", 1)[-1] or None,   # EventScheduled, EventCancelled, ...
        "venue": loc.get("name"),
        "address": ", ".join(str(x).strip() for x in (addr.get("streetAddress"), addr.get("addressLocality"),
                                                      addr.get("addressRegion"), addr.get("postalCode")) if x),
        "performers": [p.get("name") for p in (perf if isinstance(perf, list) else [perf]) if isinstance(p, dict)],
        "availability": ((ev.get("offers") or {}).get("availability") or "").rsplit("/", 1)[-1] or None,
        "page_build": nd.get("page"),
        "url": page_info()["url"],
    }

def show(r):
    when = f"{r['local_date']} {r['local_time'] or ''}".strip()
    return f"{when} | {r['name'][:60]} | {r['venue']}, {r['city']} {r['state'] or ''} | {r['url']}"

# 1. Keyword search, sorted by date, 2 pages (page 2 via the page's own "More Events" button)
rows, total, status = search("jazz", sort="date", max_pages=2)
print("search jazz:", len(rows), "of", total, status)
for r in rows[:3] + rows[20:22]:
    print("  ", show(r))
time.sleep(2)

# 2. Category page with a sub-genre and the date filter (Country concerts, next Saturday-Sunday)
from datetime import date, timedelta
sat = date.today() + timedelta(days=(5 - date.today().weekday()) % 7 or 7)
rows2, total2, status2 = discover("concerts", classification_id="KnvZfZ7vAv6",
                                  start_date=sat.isoformat(), end_date=(sat + timedelta(days=1)).isoformat(), max_pages=2)
print(f"discover concerts/Country {sat}..{sat + timedelta(days=1)}:", len(rows2), "of", total2, status2)
for r in rows2[:3]:
    print("  ", show(r))
time.sleep(2)

# 3. City page
rows3, total3, status3 = discover("chicago")
print("discover chicago:", len(rows3), "of", total3, status3, "| off-site:", sum(not r["on_ticketmaster"] for r in rows3))
time.sleep(2)

# Check: most on-site event URLs end in the venue-local date (MM-DD-YYYY); it must equal local_date.
# The rest are slug-less /event/<discovery id> URLs with no date in them.
from collections import Counter
dated = [r for r in rows + rows2 + rows3
         if r["on_ticketmaster"] and r["local_date"] and re.search(r"-\d\d-\d\d-\d{4}/event/", r["url"])]
slug_ok = sum(f"-{r['local_date'][5:7]}-{r['local_date'][8:10]}-{r['local_date'][:4]}/event/" in r["url"] for r in dated)
print("slug date == local_date:", slug_ok, "of", len(dated), "| date_display:", Counter(r["date_display"] for r in rows + rows2 + rows3))
time.sleep(2)

# 4. Event pages: the first two on-site search results, plus one slug-less /event/<discovery id> URL if listed
picks = [r for r in rows if r["on_ticketmaster"]][:2]
picks += [r for r in rows2 + rows3 if r["on_ticketmaster"] and urlparse(r["url"]).path.startswith("/event/")][:1]
for r in picks:
    d = event_details(r["url"])
    print(json.dumps(d, ensure_ascii=False))
    print("   list row said:", r["local_date"], r["local_time"], "| page says:", d["start_local"])
    time.sleep(2)

# 5. A query with no results
print("nonsense query:", search("zzqxqvnotathing")[1:])

# 6. Disallowed paths are refused before the tab navigates
for p in ("/search?q=jazz&searchVariant=ai", "/json/search/event/foo", "/some-show/event/0B00653E2B2EC4EE?preselect=1"):
    print("allowed?", p, robots_allowed(p))

close_tab(_TAB[0])   # the one tab this block opened
```

Output observed on 2026-11-01 (trimmed):

```text
search jazz: 40 of 3889 truncated_max_pages
   2026-10-31 21:00 | Halloween with Sally Baby's Silver Dollars | Snug Harbor Jazz Bistro, New Orleans LA | https://www.ticketweb.com/event/halloween-with-sally-babys-silver-snug-harbor-jazz-bistro-tickets/14410584
   2026-11-01 15:00 | Fresh Takes On Jazz: Ava Preston | Mickey's Black Box, Lititz PA | https://www.ticketmaster.com/fresh-takes-on-jazz-ava-preston-lititz-pennsylvania-11-01-2026/event/0200651B00735077
   2026-11-01 18:00 | Johnny Britt "You Are Beautiful" Tour | Humphreys Backstage Live, San Diego CA | https://www.ticketmaster.com/johnny-britt-you-are-beautiful-tour-san-diego-california-11-01-2026/event/0A0065159E4494E2
discover concerts/Country 2026-11-07..2026-11-08: 40 of 108 truncated_max_pages
   2026-11-06 20:00 | Saddle Up: Country Grammar | Diamondback Music Hall, Belleville MI | https://www.ticketweb.com/event/saddle-up-country-grammar-diamondback-music-hall-tickets/14407284
   2026-11-07 12:30 | BACKSTAGE NASHVILLE! DAYTIME HIT SONGWRITERS SHOW featuring  | 3rd and Lindsley, Nashville TN | https://www.ticketweb.com/event/backstage-nashville-daytime-hit-songwriters-3rd-and-lindsley-tickets/14637713
discover chicago: 20 of 2425 truncated_max_pages | off-site: 10
slug date == local_date: 32 of 32 | date_display: Counter({'showDateTime': 100})
{"id": "0200651B00735077", "name": "Fresh Takes On Jazz: Ava Preston", "start_local": "2026-11-01T15:00", "status": "EventScheduled", "venue": "Mickey's Black Box", "address": "101 Rock Lititz Blvd, Lititz, PA, 17543", "performers": [], "availability": null, "page_build": "/naevent/[eventId]", "url": "https://www.ticketmaster.com/fresh-takes-on-jazz-ava-preston-lititz-pennsylvania-11-01-2026/event/0200651B00735077"}
   list row said: 2026-11-01 15:00 | page says: 2026-11-01T15:00
{"id": "010064CB19BF6123", "name": "Huntertones", "start_local": "2026-11-01T19:30:00", "status": "EventScheduled", "venue": "Jimmy's Jazz and Blues Club", "address": "135 Congress Street, Portsmouth, NH, 03801", "performers": ["Huntertones"], "availability": "InStock", "page_build": "/globalevent/[eventId]", "url": "https://www.ticketmaster.com/huntertones-portsmouth-new-hampshire-11-01-2026/event/010064CB19BF6123"}
   list row said: 2026-11-01 19:30 | page says: 2026-11-01T19:30:00
{"id": "Z7r9jZ1AAZd8O", "name": "Jon Pardi w/ Alexandra Kay", "start_local": "2026-11-07T17:30", "status": "EventScheduled", "venue": "Round Rock Amp", "address": "3701 N IH 35, Round Rock, TX, 78665", "performers": [], "availability": null, "page_build": "/naevent/[eventId]", "url": "https://www.ticketmaster.com/event/Z7r9jZ1AAZd8O"}
   list row said: 2026-11-07 17:30 | page says: 2026-11-07T17:30
nonsense query: (0, 'complete')
allowed? /search?q=jazz&searchVariant=ai False
allowed? /json/search/event/foo False
allowed? /some-show/event/0B00653E2B2EC4EE?preselect=1 False
```

## URL patterns (all observed)

| URL | Page state key | Notes |
|---|---|---|
| `/search?q=<kw>` | `searchEvents({"keyword":..,"page":0,"sort":"relevance"})` | `total` = all matches (310 for `taylor`, 3889 for `jazz`) |
| `/search?q=<kw>&sort=date` | `searchEvents({...,"sort":"date"})` | soonest first; includes events that started earlier today or yesterday |
| `/discover/concerts`, `/discover/sports`, `/discover/arts-theater`, `/discover/family` | `categoryEvents({"categoryId":..,"page":0})` | the four top menu categories (`headerConfig(undefined).data.categories`) |
| `/discover/<category>?classificationId=<id>` | `categoryEvents({"categoryId":"<id>",...})` | sub-genre; ids are in `categoryInfoV2(...).data.minor` and the menu's `subCategories` (Country = `KnvZfZ7vAv6`) |
| `...&startDate=YYYY-MM-DD&endDate=YYYY-MM-DD` | `categoryEvents({...,"startDate","endDate"})` | the page's date filter; works on direct load |
| `/discover/<city>` (`new-york-city`, `chicago`, ...) | `cityEvents({"cities":..,"stateCodes":..})` | 23 city slugs in `headerConfig(undefined).data.cities` |
| `/<slug>-<MM-DD-YYYY>/event/<16 hex>` | `eventInfo` or `edpData` | Ticketmaster-hosted event page |
| `/event/<discovery id>` (e.g. `Z7r9jZ1AAZd8O`) | `edpData` | slug-less event page, same JSON-LD |

## Fields

| Output field | Source | Notes |
|---|---|---|
| `id` | `events[i].id` | 16 hex chars, a discovery id such as `Z7r9jZ1AAZd8O`, or a partner id (`14720223`) |
| `name` | `title` | |
| `local_date`, `local_time` | `dates.startDate` converted with `timeZone` | `startDate` is UTC (`...Z`) or has an offset (`-05:00`); every on-site URL with a date in its slug matched (32/32) |
| `date_display` | `dates.dateDisplay` | all 100 rows sampled were `showDateTime` |
| `venue`, `city`, `state`, `country` | `venue.name/city/state/countryCode` | `venue` also has `addressLineOne`, `code` (ZIP), `latitude`, `longitude`, `url` |
| `url`, `on_ticketmaster` | `url` | off-site rows link to ticketweb.com or travel.ticketmaster.com |
| `status` | `cancelled`, `postponed`, `rescheduled`, `soldOut` | `listed` when none is set |
| event page `start_local` | JSON-LD `startDate` | venue-local, no offset; the two builds format it differently (`T15:00` vs `T19:30:00`) |
| event page `status`, `availability` | JSON-LD `eventStatus`, `offers.availability` | `offers` was missing on the `/naevent/` pages tried |

## Gotchas

- Category and city lists are sorted by start date and begin with long-running listings that started months ago (season tickets, museum passes, hotel packages; on 2026-11-01 the first `/discover/concerts` row was a tribute show dated 2025-11-21). Filter on `local_date` if you want upcoming events only.
- `total` was exactly 10000 for `/discover/concerts`, `/discover/sports` and `/discover/new-york-city`; it looks like a display cap, so read 10000 as "10000 or more".
- The date filter is not strict local dates: `startDate=2026-11-07` returned a 2026-11-06 20:00 event in Michigan (01:00 UTC on 11-07) and multi-day listings that started earlier. Re-check `local_date` yourself.
- Search rows carry a `local` flag, but it is not a distance signal: on 2026-11-01 all 20 first-page rows for `taylor`, `jazz` and `comedy` had `local: true`, with venues in NJ, DC, MI, CA, UT, AZ and more.
- The "PROMOTED" card shown between search results is an ad slot and is not in `searchEvents`; the code never sees it.
- Ad-heavy pages sometimes keep the tab busy for over 5 s, so single CDP calls (`DOM.getBoxModel`, `Runtime.evaluate`) time out; the block retries them. Close other heavy tabs in the same browser.
- If a page has no `__NEXT_DATA__` (a queue, block or challenge page), the code raises. Stop there; do not retry, switch IP or change the request to get around it.

## What does not work

- Plain `urllib` with its default User-Agent got HTTP 403 for `/robots.txt` (curl got 200), so the block reads robots.txt in the browser tab instead of changing its User-Agent.
- `/api/ismds/event` (seat and price availability) and `/json/search/event/*` are robots-disallowed; this skill does not request them. Event pages load the former themselves; the block does not read it.
- Event URLs with `?preselect=` and search URLs with `searchVariant=` or `f_discoAiSearch=` (the AI search) are robots-disallowed and refused by `robots_allowed()`.
- Partner rows (TicketWeb, travel.ticketmaster.com) are other sites with their own robots.txt; `event_details()` refuses them.
