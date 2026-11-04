# Flightradar24 - Airport Boards, Flight-Number History and Registration History

Field-tested against www.flightradar24.com on 2026-11-04 using a Browser Use cloud browser, logged out. About 50 page loads; no CAPTCHA, challenge page, login wall or non-200 page.

robots.txt (read in the browser 2026-11-04, `User-agent: *`) disallows `/mobile/`, `/auth/`, `/account/`, `/redir.php`, `/aircraft-icons/sprite*`, `/assets/aircraft/*`, `/multiview/`, `/cdn-cgi/*`, `/user/delete-account`, `/blog/search/` and `/simple`; `/data/` is not disallowed (only `CCBot` and `GPTBot` get `Disallow: /`). The block reads robots.txt in the browser and refuses any path it disallows; it only opens `/data/...` pages.

## Quick summary

- **Browser only.** Plain HTTP (curl, default UA) got `200` for `/robots.txt` but `403` for `/data/flights/ba74` and `/data/airports/lhr/arrivals` (2026-11-04). Do not try to get around it.
- **Airport board** (`/data/airports/<iata>/arrivals|departures`): an Inertia.js page. The server puts all data in `<div id="app" data-page="...">` as JSON: airport (name, IATA/ICAO, timezone), delay statistics (live index, yesterday/today/tomorrow totals, delayed, cancelled) and 100 flights per page with flight number, callsign, scheduled and estimated/actual time (unix), status, other airport, airline, aircraft type, registration, gate, runway, codeshares.
- **More board pages** = the page's own "Earlier flights" / "Later flights" links (`?date=<ts>&page=-1|2...`). The block follows the hrefs it finds; it never builds them. Logged out, the chain ends about 12 h before and 12 h after the moment you load it (LHR at 23:49 UTC: 4 earlier pages back to -12.0 h, 2 later pages to +11.9 h); the last page says "To get more than 12 hours of arrivals, please create a free account".
- **Flight-number history** (`/data/flights/<number>`) and **registration history** (`/data/aircraft/<reg>`): legacy server-rendered tables (`table#tbl-datatable`). Every time cell carries `data-timestamp` (UTC) and `data-offset` (seconds), so the block returns exact local ISO times. Logged out: the last 7 days plus scheduled days ahead (the page says so).
- **Stops on the first block.** Any 403/429 or a challenge title raises `Blocked`; the run ends there.

## What works: two boards, flight history and aircraft history in one run

Self-contained; opens one background tab and closes it; 9 page loads (robots.txt, 2 per board, flight, aircraft, 2 not-found checks), each after `about:blank` and a 3 s pause. About 45 s in a cloud browser.

```python
import json, re, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BASE = "https://www.flightradar24.com"
PACE_S = 3  # pause between page loads
# Ad hosts. With ads on, the first authoring tab stalled Runtime.evaluate past 5 s and the daemon died;
# with these blocked, every load after that finished in a few seconds. The data is server-rendered, so nothing is lost.
AD_BLOCK = ["*doubleclick.net*", "*googlesyndication.com*", "*aditude*", "*prebid*", "*amazon-adsystem.com*"]

class Blocked(Exception):
    """403/429 or a challenge page. Stop the run; do not retry around it."""

def _ready(timeout=40):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            href = js("location.href.startsWith('https://www.flightradar24.com/') && document.readyState !== 'loading' ? location.href : ''")
            if href:
                return href
        except Exception:
            pass  # a busy page can stall Runtime.evaluate for a few seconds
        time.sleep(0.5)
    raise RuntimeError(f"page did not load in {timeout}s")

def _title():
    # browser-harness prefixes the attached tab's title with a horse marker unless BH_TAB_MARKER=0
    return re.sub(r"^\U0001F434\s*", "", js("document.title") or "")

def _load(path):
    """Full page load of BASE + path in this tab. Returns the final URL. Raises Blocked on 403/429/challenge."""
    if path != "/robots.txt" and not robots_allowed(path.split("?")[0]):
        raise PermissionError(f"robots.txt disallows {path}")
    cdp("Page.navigate", url="about:blank")
    time.sleep(PACE_S)
    cdp("Page.navigate", url=BASE + path)
    href = _ready()
    status = js("performance.getEntriesByType('navigation')[0]?.responseStatus || 0")
    title = _title()
    if status in (403, 429) or re.search(r"just a moment|attention required|access denied|captcha", title, re.I):
        raise Blocked(f"HTTP {status} '{title}' on {path}: stop, do not retry")
    return href

def _robots_rules():
    _load("/robots.txt")
    txt = js("document.body.innerText")
    if "User-agent" not in (txt or ""):
        raise RuntimeError("could not read robots.txt")
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

def robots_allowed(path):
    """Google-style match for User-agent: *. Longest matching rule wins, Allow wins a tie."""
    best, ok = -1, True
    for allow, pat in RULES:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best or (len(pat) == best and allow)):
            best, ok = len(pat), allow
    return ok

# ---------- airport boards (new Inertia.js pages: data in <div id="app" data-page="...">) ----------

def _props():
    raw = js("document.getElementById('app')?.dataset.page || ''")
    return json.loads(raw) if raw else {}

def _board_link(label):
    return js(f"[...document.querySelectorAll('main a')].filter(a => a.innerText.trim() === {json.dumps(label)}).map(a => a.getAttribute('href'))[0] || null")

def _board_flight(f, tz):
    t = lambda s: datetime.fromtimestamp(s, tz).isoformat(timespec="minutes") if s else None
    e, st = f["endpoint"] or {}, f["status"] or {}
    return {"flight": f["flightNumber"], "callsign": f["callsign"], "airline": (f["airline"] or {}).get("name"),
            "other_airport": e.get("iata"), "other_city": e.get("city"),
            "scheduled": t(f["scheduledTime"]), "estimated": t(f["estimatedTime"]),
            "status": st.get("name"), "status_color": st.get("color"), "diverted_to": st.get("divertedToIata"),
            "type": (f["aircraft"] or {}).get("type"), "registration": (f["aircraft"] or {}).get("registration"),
            "gate": f["gate"], "runway": f["runway"], "codeshares": [c["flightNumber"] for c in f["codeshares"] or []],
            "live": f["live"], "fr24_id": f["flightId"]}

def board(iata, kind="arrivals", earlier=0, later=0):
    """Airport arrivals/departures board. Follows the page's own 'Earlier flights' / 'Later flights'
    links up to `earlier` / `later` times (logged out, the whole board spans about 12 h each side
    of now). Times are airport-local ISO strings. Returns None if the airport page does not exist."""
    assert kind in ("arrivals", "departures")
    _load(f"/data/airports/{iata.lower()}/{kind}")
    pg = _props()
    if pg.get("component") != "Data/AirportBoard":
        return None
    p = pg["props"]
    ap, tz = p["airport"], ZoneInfo(p["airport"]["timezone"])
    raw = list(p["flights"])
    first_earlier, first_later = _board_link("Earlier flights"), _board_link("Later flights")
    for href, n, label in ((first_earlier, earlier, "Earlier flights"), (first_later, later, "Later flights")):
        for _ in range(n):
            if not href:
                break
            _load(href)
            raw += _props()["props"]["flights"]
            href = _board_link(label)
    seen, flights = set(), []
    for f in sorted(raw, key=lambda f: (f["scheduledTime"], f["id"])):
        if f["id"] not in seen:
            seen.add(f["id"])
            flights.append(_board_flight(f, tz))
    return {"airport": {k: ap[k] for k in ("name", "iata", "icao", "city", "countryName", "timezone")},
            "board": kind, "stats": p["statistics"], "flights": flights}

# ---------- flight-number and registration history (legacy pages: table#tbl-datatable) ----------

_ROWS_JS = r"""
[...document.querySelectorAll('table#tbl-datatable tbody tr.data-row')].map(r =>
  [...r.children].filter(td => td.classList.contains('hidden-xs')).map(td => {
    const a = td.querySelector('a[href^="/data/"]'), play = td.querySelector('[data-flight-hex], [data-flight]');
    // textContent, not innerText: these desktop cells are display:none when the tab's viewport is narrow
    return {text: td.textContent.replace(/\s+/g, ' ').trim(), title: td.getAttribute('title'),
            prefix: td.getAttribute('data-prefix'),
            ts: td.getAttribute('data-timestamp'), off: td.getAttribute('data-offset'),
            href: a ? a.getAttribute('href') : null, link: a ? a.textContent.trim() : null,
            hex: play ? (play.getAttribute('data-flight-hex') || play.getAttribute('data-flight')) : null};
  }))
"""

def _t(cell):
    if not cell["ts"]:
        return None
    return datetime.fromtimestamp(int(cell["ts"]), timezone(timedelta(seconds=int(cell["off"] or 0)))).isoformat(timespec="minutes")

def _history(path, col4):
    href = _load(path)
    if not href.rstrip("/").endswith(path):
        return None  # unknown registration redirects to /data/aircraft/
    rows = []
    for c in js(_ROWS_JS):
        # cells: 0 spacer, 1 date, 2 from, 3 to, 4 aircraft|flight, 5 flight time, 6 STD, 7 ATD, 8 STA, 9 colour, 10 status, 11 buttons
        ap = lambda x: {"iata": (x["link"] or "").strip("() ") or None, "name": x["title"]}
        r = {"date": c[1]["text"], "from": ap(c[2]), "to": ap(c[3]),
             "flight_time": None if c[5]["text"] in ("\u2014", "") else c[5]["text"],  # site prints U+2014 for "none"
             "std": _t(c[6]), "atd": _t(c[7]), "sta": _t(c[8]),
             "status": (c[10]["prefix"] or "").strip() or c[10]["text"], "status_time": _t(c[10]), "fr24_id": c[11]["hex"]}
        if col4 == "aircraft":
            r["type"] = c[4]["text"].split("(")[0].strip() or None
            r["registration"] = (c[4]["link"] or "").strip("() ") or None
        else:
            r["flight"] = c[4]["link"] or c[4]["text"]
        rows.append(r)
    if not rows:
        return None  # unknown flight number: HTTP 200, generic map title, empty table
    cap = js(r"(document.body.textContent.replace(/\s+/g, ' ').match(/More than \d+ days of .*? subscription\./) || [null])[0]")
    return {"title": _title(), "rows": rows, "cap_note": cap}

def flight_history(number):
    """Every leg of a flight number the page shows: logged out, the last 7 days plus scheduled days ahead."""
    return _history(f"/data/flights/{number.lower()}", "aircraft")

def aircraft_history(reg):
    """Registration's info card plus its flights (logged out: last 7 days plus scheduled)."""
    h = _history(f"/data/aircraft/{reg.lower()}", "flight")
    if h:
        h["info"] = js(r"""(() => { const o = {};
          for (const l of document.querySelectorAll('label')) {
            const s = l.parentElement.querySelector('span.details'), k = l.textContent.trim();
            if (s && !(k in o)) o[k] = s.textContent.trim() || null; }
          return o; })()""")
    return h

tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
switch_tab(tab)
try:
    cdp("Network.enable")
    cdp("Network.setBlockedURLs", urls=AD_BLOCK)
    RULES = _robots_rules()
    print("robots: /data/airports/lhr/arrivals ->", robots_allowed("/data/airports/lhr/arrivals"),
          "| /multiview/ ->", robots_allowed("/multiview/"))

    arr = board("LHR", "arrivals", earlier=1)
    print(arr["airport"])
    print("today:", arr["stats"]["today"], "| live:", arr["stats"]["live"])
    print(len(arr["flights"]), "arrivals", arr["flights"][0]["scheduled"], "->", arr["flights"][-1]["scheduled"])
    for f in arr["flights"][:3]:
        print("  ", f["scheduled"], f["flight"], "from", f["other_airport"], f["type"], f["registration"], f["status"], f["estimated"], "codeshares", len(f["codeshares"]))

    dep = board("JFK", "departures", later=1)
    print(len(dep["flights"]), "JFK departures", dep["flights"][0]["scheduled"], "->", dep["flights"][-1]["scheduled"])
    for f in dep["flights"][:2]:
        print("  ", f["scheduled"], f["flight"], "to", f["other_airport"], f["airline"], f["gate"], f["status"], f["estimated"])

    landed = next(f for f in arr["flights"] if f["status"] == "landed" and f["registration"])
    fh = flight_history(landed["flight"])
    print(fh["title"], "|", len(fh["rows"]), "rows |", fh["cap_note"])
    for r in fh["rows"][:12]:
        if r["atd"]:
            print("  ", r["date"], r["from"]["iata"], "->", r["to"]["iata"], r["type"], r["registration"], "STD", r["std"], "ATD", r["atd"], "|", r["status"], r["status_time"], r["fr24_id"])

    ah = aircraft_history(landed["registration"])
    print(ah["title"], "|", {k: ah["info"].get(k) for k in ("AIRCRAFT", "AIRLINE", "OPERATOR", "TYPE CODE", "MODE S")})
    print(len(ah["rows"]), "rows |", ah["cap_note"])
    for r in ah["rows"][:6]:
        print("  ", r["date"], r["flight"], r["from"]["iata"], "->", r["to"]["iata"], "STD", r["std"], "|", r["status"])

    print("unknown:", flight_history("zz99999"), aircraft_history("zz-zzzz"))
finally:
    close_tab(tab)
```

Output observed on 2026-11-04 (23:50 UTC, independent re-run in a fresh cloud browser):

```text
robots: /data/airports/lhr/arrivals -> True | /multiview/ -> False
{'name': 'London Heathrow Airport', 'iata': 'LHR', 'icao': 'EGLL', 'city': 'London', 'countryName': 'United Kingdom', 'timezone': 'Europe/London'}
today: {'total': 646, 'delayed': 66, 'delayedPercentage': 0.1, 'cancelled': 3, 'cancelledPercentage': 0} | live: {'index': 0.4, 'averageDelayMin': 5, 'trend': 'static'}
200 arrivals 2026-11-04T19:30+00:00 -> 2026-11-05T08:05+00:00
   2026-11-04T19:30+00:00 BA1487 from GLA A320 G-EUYE landed 2026-11-04T19:19+00:00 codeshares 7
   2026-11-04T19:30+00:00 AI133 from BLR B788 VT-ANU landed 2026-11-04T18:05+00:00 codeshares 0
   2026-11-04T19:35+00:00 BA557 from FCO A320 G-EUYX landed 2026-11-04T19:14+00:00 codeshares 1
194 JFK departures 2026-11-04T18:45-05:00 -> 2026-11-05T06:45-05:00
   2026-11-04T18:45-05:00 DL4986 to MKE Delta Connection A21 estimated 2026-11-04T18:41-05:00
   2026-11-04T18:45-05:00 B68373 to BOS JetBlue None estimated 2026-11-04T18:42-05:00
Flight history for British Airways flight BA1487 | 7 rows | More than 7 days of BA1487 history is available with an upgrade to a Silver (90 days), Gold (1 year), or Business (3 years) subscription.
   04 Nov 2026 GLA -> LHR A320 G-EUYE STD 2026-11-04T18:10+00:00 ATD 2026-11-04T18:13+00:00 | Landed 2026-11-04T19:19+00:00 426e7feb
   29 Oct 2026 GLA -> LHR A20N G-TTSD STD 2026-10-29T17:40+00:00 ATD 2026-10-29T17:41+00:00 | Landed 2026-10-29T18:38+00:00 42593833
G-EUYE - Airbus A320-232 - British Airways - Flightradar24 | {'AIRCRAFT': 'Airbus A320-232', 'AIRLINE': 'British Airways', 'OPERATOR': 'British Airways', 'TYPE CODE': 'A320', 'MODE S': '406091'}
36 rows | More than 7 days of G-EUYE history is available with an upgrade to a Silver (90 days), Gold (1 year), or Business (3 years) subscription.
   05 Nov 2026 BA487 BCN -> LHR STD 2026-11-05T19:20+01:00 | Estimated departure
   05 Nov 2026 BA486 LHR -> BCN STD 2026-11-05T15:15+00:00 | Estimated departure
   05 Nov 2026 BA551 FCO -> LHR STD 2026-11-05T12:05+01:00 | Estimated departure
   05 Nov 2026 BA550 LHR -> FCO STD 2026-11-05T07:35+00:00 | Estimated departure
   04 Nov 2026 BA1487 GLA -> LHR STD 2026-11-04T18:10+00:00 | Landed
   04 Nov 2026 BA1486 LHR -> GLA STD 2026-11-04T15:40+00:00 | Landed
unknown: None None
```

Checked against the pages: board `estimatedTime` for landed BA1487 (1793819997 = 19:19 UTC) equals the "Landed" timestamp in its flight-history row, and for departed DL5106 at JFK (15:52 -05:00) equals the ATD in its history row, so on boards `estimated` is the actual time once a flight has departed or landed. The rendered LHR arrivals board contained all 100 flight numbers and 99 of 99 registrations from the JSON.

## Fields

| Function | Source | Returned |
|---|---|---|
| `board(iata, kind, earlier, later)` | `data-page` JSON, `props.airport` / `props.statistics` / `props.flights` | `airport {name, iata, icao, city, countryName, timezone}`, `stats {live {index, averageDelayMin, trend}, yesterday/today/tomorrow {total, delayed, delayedPercentage, cancelled, cancelledPercentage}}`, `flights[]` sorted by scheduled time, deduped by id |
| board flight | `props.flights[]` | `flight, callsign, airline, other_airport` (origin on arrivals, destination on departures), `other_city, scheduled, estimated` (airport-local ISO), `status` (seen: `scheduled, estimated, delayed, canceled, departed, landed`), `status_color` (seen: green/yellow/red/gray), `diverted_to, type, registration, gate, runway, codeshares[], live, fr24_id` |
| `flight_history(number)` | `table#tbl-datatable tr.data-row` | `rows[] {date` (origin-local, as shown), `from {iata, name}, to {iata, name}, type, registration, flight_time` (h:mm, airborne legs only), `std, atd, sta` (ISO with that airport's offset), `status` (seen: `Scheduled, Estimated departure, Estimated, Landed`), `status_time, fr24_id}`, `title`, `cap_note` |
| `aircraft_history(reg)` | same table plus the info card | rows as above with `flight` in place of `type`/`registration`; `info {AIRCRAFT, AIRLINE, OPERATOR, TYPE CODE, Code, MODE S, SERIAL NUMBER (MSN), AGE}` (MSN and AGE are locked logged out: `None`) |

## Gotchas

- Board times come from unix seconds plus the airport's IANA timezone in `props.airport.timezone`; history times use each cell's own `data-offset`, so STD is origin time and STA destination time.
- Read history cells with `textContent`, not `innerText`: on `/data/flights/...` the desktop cells (`hidden-xs hidden-sm`) gave empty `innerText` in a background tab, while the same code worked on `/data/aircraft/...`. `textContent` holds the server's 24 h time ("Landed 19:19"); the page's JS rewrites the visible text to 12 h ("Landed 7:19 PM"), which is why the block takes status from `data-prefix` and the time from `data-timestamp`.
- LHR board statistics and first rows were identical in loads from 23:32 to 23:49 UTC (night curfew, few movements), while the JFK board changed between runs. `props.meta.dateModified` is the server's snapshot time (23:48:37 UTC on a 23:49 load); check it if freshness matters.
- Unknown flight number: HTTP 200, generic map title, empty table; `flight_history` returns `None`. Unknown registration: redirect to `/data/aircraft/`; `aircraft_history` returns `None`.
- Loaded around 23:30 to 23:50 UTC, the LHR board's first page started at 04:29 to 04:50 local the next morning (night curfew), so a board's "now" page can begin hours ahead; use `earlier=` for flights that already landed.
- Ads: the first authoring tab, with ads on, stalled `Runtime.evaluate` past 5 s and the cloud daemon died. With the `AD_BLOCK` hosts blocked no load stalled again. `Network.setBlockedURLs` is per tab.
- The flight page's own map loads `/aircraft-icons/sprite?...` (robots-disallowed) by itself; the block never reads those responses.
- On a 403/429 or a challenge page the block raises `Blocked`. Stop; do not retry, change UA or switch IPs.

## What does not work

- Plain HTTP to `/data/...`: 403.
- More than about 12 h of board in each direction, more than 7 days of history, KML/CSV downloads, MSN and age: logged-in or paid features, not attempted.
- `api.flightradar24.com` / `data-cloud.flightradar24.com` feeds: internal APIs, not used.
