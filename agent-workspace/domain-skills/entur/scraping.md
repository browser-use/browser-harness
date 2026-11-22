# Entur via api.entur.io - Get the Next Departures (Line, Destination, Expected Time, Delay, Platform) From a Norwegian Stop by Name, or Plan a Trip Between Two Places (Geocoder v3 + Journey Planner v3 GraphQL, no key, ET-Client-Name header)

Field-tested against api.entur.io and developer.entur.no on 2026-11-21 (US Pacific afternoon; 00:17-00:28 UTC on 22 November, which was 01:17-01:28 on Sunday 22 November in Norway) using a fresh Browser Use cloud browser (logged out; one session, 00:24-00:26 UTC) plus Python `urllib` and `curl` from a Linux machine. 15 browser page loads (1 in block 1's first run, 7 in each of block 2's two runs) and 53 in-page `fetch()` calls (blocks 1 and 2 ran twice each), 19 urllib calls (block 3 ran 6 times: 2 early runs, 1 refused run with a placeholder client name that made no call, and the 3 runs below) and 67 curl calls (43 while exploring, 27 of them to api.entur.io and 16 to the docs, robots, licence and RFC pages; 24 in three runs of block 4), all serial and at least 1 s apart. Every API call sent `ET-Client-Name` with Browser Use's own value, except four deliberate unidentified probes: one Geocoder and one Journey Planner call by curl, and the same pair in block 2's first run. Every API call was HTTP 200 except the deliberate HTTP 400 probes (Geocoder focus parameters) and the HTTP 404 robots.txt answers. curl timed Geocoder v3 answers at 0.21-0.65 s, departure boards and other GraphQL lookups at 0.21-0.66 s and trip searches at 0.71-1.55 s. No 429, no challenge, no key, no login, no cookie. The outputs below are the second runs of blocks 1 and 2 (00:26 and 00:25 UTC, after the rate-limit header comments changed), block 3's final three runs (00:26 UTC) and block 4's third run (00:27 UTC). An independent verifier re-ran all four blocks verbatim on 2026-11-22 00:32-00:35 UTC (a second fresh cloud browser, urllib, curl): every block ran, and only the live boards (Jernbanetorget, the next Trondheim S departures, the next Bergen tram) changed. The verifier then made blocks 2 and 4 refuse a missing, malformed or example client name, as blocks 1 and 3 do, and re-ran all four at 00:38-00:39 UTC with the same results.

robots.txt (checked 2026-11-22 UTC, curl, the cloud browser and block 3): https://api.entur.io/robots.txt answers HTTP 404 with an empty body, and https://developer.entur.no/robots.txt answers HTTP 404 with the portal's HTML page, so neither host has robots rules or named AI-agent groups. RFC 9309 (section 2.3.1.3) says that when robots.txt is unavailable (4xx) "the crawler MAY access any resources on the server", so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider may fetch every path this skill uses (block 3 checks all 11 agents on every run and stops if api.entur.io ever publishes rules that disallow one). The licence page's host https://data.norge.no/robots.txt has one `User-agent: *` group (disallows `/api/`, `/_next/`, `/admin/`, `/internal/` and `/*?`, `Crawl-delay: 1`), which does not cover `/nlod/en/2.0`. Terms: https://developer.entur.no/terms-of-service ("Last modified on October 21, 2026"; 0 changed lines against the copy read on 2026-11-20) says "All API requests must include an ET-Client-Name header identifying your application, not you personally" and "Applications without this header will operate at lower rate limits and may be subject to restrictions if usage is unreasonable". Not permitted: "Attempting to circumvent rate limiting or traffic shaping measures.", "Using fake or randomly generated values in the ET-Client-Name header." and "Impersonating traffic from another application or organisation." The data is under the Norwegian Licence for Open Government Data, NLOD 2.0 (https://data.norge.no/nlod/en/2.0): "NLOD permits free reuse for any purpose, including commercial use, subject to attribution requirements", with "State that the data originates from Entur.", "Link to the applicable licence.", "Indicate if you have modified the data." and "Do not present the attribution in a way that implies Entur endorses your product or service.", default text "Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS". Getting started (https://developer.entur.no/docs/getting-started) marks the public transport data APIs "Available to everyone. No partnership agreement required." and asks for the header "in the form `<company>-<application>` (lowercase, no spaces)". No AI/ML, scraping, crawling, robot or non-commercial wording on the terms, getting-started, rate-limiting or Geocoder migration pages (block 2 checks the quotes and scans for the words). Partner APIs (OAuth) are out of scope. Naming: this skill writes "Entur" in plain text, shows no Entur logo, and is not affiliated with or endorsed by Entur AS; every block prints the NLOD attribution and says what it changed.

**Set your own client name before running anything.** Every block reads `ET_CLIENT_NAME` from the environment and refuses to run without a `<company>-<application>` value (for example `acme-departureboard` for Acme's departure board). It also refuses the example values from Entur's docs and this page. The terms forbid fake, random or borrowed values, and the runs here used Browser Use's own value, which you must not reuse. Without the header, Entur gives you much lower limits.

## Quick summary

- **No scraping needed.** Two open endpoints, JSON, no key, one required header. Stop name to id: `GET https://api.entur.io/geocoder/v3/autocomplete?q=Bergen%20stasjon&layers=stopPlace&limit=5&lang=en` -> GeoJSON features with `properties.id` (`NSR:StopPlace:59983`), `names.display`, `stopPlaceRole`, `transportModes`. Departures and trips: `POST https://api.entur.io/journey-planner/v3/graphql` with `{"query": ..., "variables": ...}`, using `stopPlace(id) { estimatedCalls(numberOfDepartures: n) {...} }` for a departure board and `trip(from: {place | coordinates}, to: ..., dateTime, numTripPatterns, pageCursor)` for a journey. Both send `Access-Control-Allow-Origin: *` and allow the `ET-Client-Name` header, so `fetch()` works from any https page.
- **Answers (block 1, 22 November 2026, 00:26 UTC = 01:26 Sunday in Norway):** the next departure from **Oslo S** is **FLY1 to Oslo Lufthavn at 04:40 from platform 13**, then every 20 minutes (nothing runs earlier that night). **Bergen stasjon:** **L4 to Arna at 01:57 from platform 1**, then 02:27, 05:42, and R40 to Voss at 07:04. **Jernbanetorget (Oslo):** tram 18 to Storo-Grefsen st. at 01:27, bus 1N to Ullerntoppen at 01:28, and tram 15 to Kjelsås at 01:30, which was 5 minutes late. **Trip Oslo S -> Bergen stasjon** (Sunday morning): first found **07:40 -> 10:59**, FLY1 to the airport, the 08:55 flight, then airport bus FB50 (3 h 19 min). **Karl Johans gate 22, Oslo -> Trondheim S on Monday 23 Nov from 08:00** (block 3): **09:33 -> 12:48**, bus 37 to Jernbanetorget, FLY2 to the airport, the 10:50 flight, then bus 311 (3 h 14 min).
- **Pick the stop carefully.** Several stops can share a name. "Flesland" matched a place and a stop in Karmøy before the Bergen one, and "Oslo S" is two stop ids: `NSR:StopPlace:59872`, the multimodal parent the Geocoder returns, and `NSR:StopPlace:337`, its rail child, also called "Oslo S". Blocks 1 and 3 take an exact name match first and print the other hits, so check `names.display` (the locality).
- **No trip is not an error.** At night, `trip` came back with `tripPatterns: []`, `routingErrors: [{code: "noTransitConnectionInSearchWindow"}]` and a `nextPageCursor`. The search window was set by the server (200-510 minutes seen). The blocks follow the cursor, at most 3 pages, or you can pass `dateTime`.
- **Rate limits (Journey Planner docs):** 1,000 requests a minute and 200 a second for clients identified by `ET-Client-Name`, 500 and 150 for trip requests. Without the header the limits are 60 and 20, and 30 and 2 for trips. The responses report the Journey Planner limits per 2-minute window (`rate-limit-allowed: 2000`, `1000` for trips, `rate-limit-range: PT2M`) and the Geocoder per minute (`1000`, or `600` without the header). On a 429, retry a spike-arrest violation (it carries `Spike-Allowed`) after a short pause. On a quota 429, wait until `Rate-Limit-Expiry-Time`, never sooner. The blocks do exactly that, once, and run serially at 1 call a second. In the browser these headers are hidden from `fetch()`.

## What works

### 1. Departure boards by stop name, and trips between two places (browser)

`on_entur_tab()` opens one logged-out developer.entur.no page. The API answers `Access-Control-Allow-Origin: *`, so any https page would do. `call()` returns parsed JSON on HTTP 200 and raises on a GraphQL `errors` list, which arrives with HTTP 200. It waits once and then raises: 60 s on a 429, because the browser cannot read `Spike-Allowed` or `Rate-Limit-Expiry-Time` (the code uses them where they are visible), and 10 s on 5xx or a network error. Each stop costs 2 calls (Geocoder, Journey Planner). Each trip costs 2 Geocoder calls and 1 to 3 Journey Planner calls, one per page of search window. The run below made 14. To ask about other stops or trips, edit `STOPS` and `TRIPS`.

```python
import json, os, re, time
from datetime import datetime, timezone
from urllib.parse import urlencode

# Entur's terms: every request sends ET-Client-Name "identifying your application, not you personally",
# as "<company>-<application>" (lowercase, no spaces); "fake or randomly generated values" are not permitted.
# Put your own company and app name in ET_CLIENT_NAME. There is deliberately no default.
CLIENT = os.environ.get("ET_CLIENT_NAME", "").strip()
DOC_EXAMPLES = {"company-application", "yourcompany-yourapp", "my_company-my_app", "forsen_utvikling-infoplakat", "entur-developerdocs",
                "brakar-journeyplanner", "fosen_utvikling-infoplakat", "fosen_utvikling-departureboard", "acme-departureboard"}
if not re.fullmatch(r"[a-z0-9_]+-[a-z0-9_.-]+", CLIENT) or CLIENT in DOC_EXAMPLES:
    raise SystemExit("Set ET_CLIENT_NAME to '<company>-<application>' for your own app (lowercase, no spaces); "
                     "Entur's terms forbid fake, random or borrowed values.")

GEO = "https://api.entur.io/geocoder/v3/autocomplete"
JP = "https://api.entur.io/journey-planner/v3/graphql"
PAUSE = 1.0   # serial, 1 call a second: far under the documented 1,000 a minute (500 for trip requests)

STOPS = ["Oslo S", "Bergen stasjon", "Jernbanetorget"]                       # departure boards by stop name
TRIPS = [("Oslo S", "Bergen stasjon"), ("Karl Johans gate 22, Oslo", "Trondheim")]   # trips between two places

DEPARTURES = """query($id: String!, $n: Int!) { stopPlace(id: $id) { id name
  estimatedCalls(numberOfDepartures: $n) { realtime cancellation aimedDepartureTime expectedDepartureTime
    quay { publicCode } destinationDisplay { frontText }
    serviceJourney { line { publicCode name transportMode } } } } }"""
TRIP = """query($from: Location!, $to: Location!, $n: Int!, $cursor: String) {
  trip(from: $from, to: $to, numTripPatterns: $n, pageCursor: $cursor) {
    routingErrors { code description } nextPageCursor metadata { searchWindowUsed }
    tripPatterns { expectedStartTime expectedEndTime duration
      legs { mode expectedStartTime expectedEndTime realtime fromPlace { name } toPlace { name }
        line { publicCode name } fromEstimatedCall { destinationDisplay { frontText } } } } } }"""

def on_entur_tab():
    """Any https page works (the API answers Access-Control-Allow-Origin: * and allows the ET-Client-Name
    header); a developer.entur.no page keeps the tab on Entur's own site."""
    try:
        if js("location.origin") == "https://developer.entur.no":
            return
    except Exception:
        pass
    new_tab("https://developer.entur.no/terms-of-service")
    wait_for_load()
    if js("location.origin") != "https://developer.entur.no":
        raise RuntimeError(f"developer.entur.no did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__e = window.__e || {}; const id = String(Math.random()).slice(2); window.__e[id] = null;
  const a = %s;
  fetch(a.url, {method: a.body ? 'POST' : 'GET', headers: a.headers, body: a.body, credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__e[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__e[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__e[%s]; if (v) delete window.__e[%s]; return v; })()"""

calls = []
def fetch(url, body=None):
    headers = {"ET-Client-Name": CLIENT, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    rid = json.dumps(js(START_JS % json.dumps({"url": url, "headers": headers, "body": body})))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    calls.append((r["status"], round(time.time() - t0, 2)))
    time.sleep(PAUSE)
    return r

def expiry_wait(h):
    """Seconds until Rate-Limit-Expiry-Time ('Sun Nov 22 2026 00:20:47 GMT-0000 (GMT)'), else 60. In a browser the
    Rate-Limit-* and Spike-* headers are not exposed to fetch() (no Access-Control-Expose-Headers), so it is 60."""
    m = re.search(r"\w{3} (\w{3} \d{1,2} \d{4} \d{2}:\d{2}:\d{2})", h.get("rate-limit-expiry-time", ""))
    if not m:
        return 60
    t = datetime.strptime(m.group(1), "%b %d %Y %H:%M:%S").replace(tzinfo=timezone.utc)
    return max(1, int((t - datetime.now(timezone.utc)).total_seconds()) + 1)

def call(url, body=None):
    """One request -> parsed JSON. Entur's rate-limit page: retry a spike-arrest 429 (it carries Spike-Allowed)
    conservatively; never retry a quota 429 before Rate-Limit-Expiry-Time. One wait on 429/5xx/network error,
    over 120 s stops. GraphQL errors come back as HTTP 200 with an `errors` list: raised here."""
    for attempt in range(2):
        r = fetch(url, body)
        s, h = r["status"], r["headers"]
        if attempt == 0 and s in (0, 429, 500, 502, 503, 504):
            wait = 2 if (s == 429 and "spike-allowed" in h) else expiry_wait(h) if s == 429 else 10
            if wait > 120:
                raise RuntimeError(f"{url}: HTTP 429, quota resets in {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if s != 200:
        raise RuntimeError(f"{url}: HTTP {s} {' '.join(r['text'].split())[:160]!r}; stopping")
    d = json.loads(r["text"])
    if d.get("errors"):
        raise RuntimeError(f"GraphQL errors (HTTP 200): {[e.get('message') for e in d['errors']]}")
    return d

def geocode(text, stops_only):
    """Geocoder v3 autocomplete -> features. stops_only keeps the stopPlace layer (NSR ids for departures)."""
    p = {"q": text, "limit": 5, "lang": "en"}
    if stops_only:
        p["layers"] = "stopPlace"
    feats = call(GEO + "?" + urlencode(p))["features"]
    if not feats:
        raise RuntimeError(f"Geocoder found nothing for {text!r}")
    return feats

def pick(text, feats):
    """Exact name match first (case-insensitive), else the geocoder's first hit."""
    for f in feats:
        if f["properties"]["names"]["default"].lower() == text.lower():
            return f
    return feats[0]

def as_location(f):
    """Stop places and groups of stop places go in as {place: id}; anything else (address, street, POI, place
    name) as coordinates. GeoJSON is [lon, lat]."""
    p = f["properties"]
    if p["layer"] in ("stopPlace", "groupOfStopPlaces"):
        return {"place": p["id"], "name": p["names"]["display"]}
    lon, lat = f["geometry"]["coordinates"]
    return {"coordinates": {"latitude": lat, "longitude": lon}, "name": p["names"]["display"]}

def hhmm(iso):            # '2026-11-22T07:40:00+01:00' -> '07:40' (Norwegian local time, offset in the string)
    return iso[11:16]

def mins(a, b):
    return round((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 60)

on_entur_tab()
now = datetime.now(timezone.utc)
print(f"Entur Journey Planner v3 + Geocoder v3, checked {now:%Y-%m-%d %H:%M} UTC")

for name in STOPS:
    feats = geocode(name, stops_only=True)
    f = pick(name, feats)
    p = f["properties"]
    print(f"\n{name!r} -> {p['id']} {p['names']['display']} ({p.get('stopPlaceRole')}; "
          f"{', '.join(sorted({m['mode'] for m in p.get('transportModes', [])}))}); "
          f"other hits: {[x['properties']['names']['display'] for x in feats if x is not f][:3]}")
    sp = call(JP, json.dumps({"query": DEPARTURES, "variables": {"id": p["id"], "n": 6}}))["data"]["stopPlace"]
    if sp is None:
        raise RuntimeError(f"Journey Planner does not know {p['id']}: stop")
    for c in sp["estimatedCalls"]:
        line = c["serviceJourney"]["line"]
        late = mins(c["aimedDepartureTime"], c["expectedDepartureTime"])
        state = "CANCELLED" if c["cancellation"] else (f"{late:+d} min" if late else "on time") if c["realtime"] else "timetable"
        print(f"  {hhmm(c['expectedDepartureTime'])}  {line['transportMode']:<5} {line['publicCode'] or line['name']:<6} "
              f"{c['destinationDisplay']['frontText']:<24} platform {c['quay']['publicCode'] or '-':<3} "
              f"(aimed {hhmm(c['aimedDepartureTime'])}, {state})")

for a, b in TRIPS:
    fa, fb = pick(a, geocode(a, False)), pick(b, geocode(b, False))
    la, lb = as_location(fa), as_location(fb)
    print(f"\ntrip {la['name']} ({fa['properties']['layer']}) -> {lb['name']} ({fb['properties']['layer']})")
    cursor, pages = None, 0
    while True:
        t = call(JP, json.dumps({"query": TRIP, "variables": {"from": la, "to": lb, "n": 3, "cursor": cursor}}))["data"]["trip"]
        pages += 1
        if t["tripPatterns"] or not t["nextPageCursor"] or pages == 3:
            break
        print(f"  page {pages}: no trip in the {t['metadata']['searchWindowUsed']} min search window "
              f"({[e['code'] for e in t['routingErrors']]}); next page")
        cursor = t["nextPageCursor"]
    if not t["tripPatterns"]:
        print(f"  no trip found: {t['routingErrors']}")
    for tp in t["tripPatterns"]:
        legs = [l for l in tp["legs"] if l["mode"] != "foot"]
        print(f"  {hhmm(tp['expectedStartTime'])} -> {hhmm(tp['expectedEndTime'])} "
              f"({tp['expectedStartTime'][:10]}, {tp['duration'] // 3600} h {tp['duration'] % 3600 // 60:02d} min, "
              f"{len(legs) - 1} change{'s' if len(legs) != 2 else ''})")
        for l in legs:
            ln = l["line"] or {}
            dest = (l["fromEstimatedCall"] or {}).get("destinationDisplay") or {}
            print(f"     {hhmm(l['expectedStartTime'])} {l['mode']:<5} {ln.get('publicCode') or ln.get('name') or '':<10} "
                  f"{l['fromPlace']['name']} -> {l['toPlace']['name']} {hhmm(l['expectedEndTime'])}"
                  f"{' (towards ' + dest['frontText'] + ')' if dest.get('frontText') else ''}")

print(f"\n{len(calls)} API calls, statuses {sorted({s for s, _ in calls})}, "
      f"{min(t for _, t in calls):.2f}-{max(t for _, t in calls):.2f} s each")
print("Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS "
      "(https://data.norge.no/nlod/en/2.0). Times are Norwegian local time as Entur sends them; layout changed.")
```

Output (from the run on 2026-11-22, 00:26 UTC; the first run at 00:24 UTC gave the same stops, departures and trips, apart from the live Jernbanetorget board):

```text
Entur Journey Planner v3 + Geocoder v3, checked 2026-11-22 00:26 UTC

'Oslo S' -> NSR:StopPlace:59872 Oslo S, Oslo (parent; bus, rail); other hits: ['Oslo lufthavn, Ullensaker', 'Scandic Oslo Airport, Nannestad']
  04:40  rail  FLY1   Oslo Lufthavn            platform 13  (aimed 04:40, on time)
  05:00  rail  FLY1   Oslo Lufthavn            platform 13  (aimed 05:00, on time)
  05:20  rail  FLY1   Oslo Lufthavn            platform 13  (aimed 05:20, on time)
  05:40  rail  FLY1   Oslo Lufthavn            platform 13  (aimed 05:40, on time)
  06:00  rail  FLY1   Oslo Lufthavn            platform 13  (aimed 06:00, on time)
  06:20  rail  FLY1   Oslo Lufthavn            platform 13  (aimed 06:20, on time)

'Bergen stasjon' -> NSR:StopPlace:59983 Bergen stasjon, Bergen (parent; bus, rail); other hits: ['Arna stasjon, Bergen', 'Garnes stasjon, Bergen', 'Midtun stasjon, Bergen']
  01:57  rail  L4     Arna                     platform 1   (aimed 01:57, on time)
  02:27  rail  L4     Arna                     platform 1   (aimed 02:27, on time)
  05:42  rail  L4     Arna                     platform 1   (aimed 05:42, on time)
  07:04  rail  R40    Voss                     platform 2   (aimed 07:04, on time)
  07:27  rail  L4     Arna                     platform 1   (aimed 07:27, on time)
  07:57  rail  L4     Arna                     platform 1   (aimed 07:57, on time)

'Jernbanetorget' -> NSR:StopPlace:58366 Jernbanetorget, Oslo (parent; bus, metro, tram); other hits: []
  01:27  tram  18     Storo-Grefsen st.        platform E   (aimed 01:27, timetable)
  01:28  bus   1N     Ullerntoppen             platform G   (aimed 01:28, on time)
  01:29  bus   37     Nydalen                  platform A   (aimed 01:29, timetable)
  01:30  bus   70N    Bjørndal                 platform D   (aimed 01:30, on time)
  01:30  tram  15     Kjelsås                  platform C   (aimed 01:25, +5 min)
  01:30  bus   12N    Majorstuen               platform A   (aimed 01:28, +3 min)

trip Oslo S, Oslo (stopPlace) -> Bergen stasjon, Bergen (stopPlace)
  page 1: no trip in the 270 min search window (['noTransitConnectionInSearchWindow']); next page
  07:40 -> 10:59 (2026-11-22, 3 h 19 min, 2 changes)
     07:40 rail  FLY1       Oslo S -> Oslo lufthavn stasjon 08:02 (towards Oslo Lufthavn)
     08:55 air   Oslo-Bergen Oslo lufthavn -> Bergen lufthavn 09:59 (towards Bergen)
     10:30 bus   FB50       Bergen lufthavn -> Bergen busstasjon 10:55 (towards Ring - Bergen sentrum - Bergen lufthavn Flesland)
  07:34 -> 10:59 (2026-11-22, 3 h 25 min, 2 changes)
     07:34 rail  RE10       Oslo S -> Oslo lufthavn stasjon 07:57 (towards Lillehammer)
     08:55 air   Oslo-Bergen Oslo lufthavn -> Bergen lufthavn 09:59 (towards Bergen)
     10:30 bus   FB50       Bergen lufthavn -> Bergen busstasjon 10:55 (towards Ring - Bergen sentrum - Bergen lufthavn Flesland)
  07:40 -> 11:09 (2026-11-22, 3 h 29 min, 2 changes)
     07:40 rail  FLY1       Oslo S -> Oslo lufthavn stasjon 08:02 (towards Oslo Lufthavn)
     08:55 air   Oslo-Bergen Oslo lufthavn -> Bergen lufthavn 09:59 (towards Bergen)
     10:26 tram  1          Bergen lufthavn -> Nonneseter 11:08 (towards Bergen sentrum)

trip Karl Johans gate 22, Oslo (address) -> Trondheim, Trondheim (groupOfStopPlaces)
  page 1: no trip in the 200 min search window (['noTransitConnectionInSearchWindow']); next page
  08:47 -> 12:07 (2026-11-22, 3 h 20 min, 2 changes)
     09:00 rail  FLY1       Oslo S -> Oslo lufthavn stasjon 09:22 (towards Oslo Lufthavn)
     10:10 air   Oslo-Trondheim Oslo lufthavn -> Trondheim lufthavn 11:10 (towards Trondheim)
     11:30 bus   FB73       Trondheim lufthavn -> Prinsens gate 12:07 (towards Flybuss Ekspress Trondheim)
  08:40 -> 12:07 (2026-11-22, 3 h 27 min, 2 changes)
     08:54 rail  R12        Oslo S -> Oslo lufthavn stasjon 09:17 (towards Eidsvoll)
     10:10 air   Oslo-Trondheim Oslo lufthavn -> Trondheim lufthavn 11:10 (towards Trondheim)
     11:30 bus   FB73       Trondheim lufthavn -> Prinsens gate 12:07 (towards Flybuss Ekspress Trondheim)
  08:21 -> 12:07 (2026-11-22, 3 h 46 min, 2 changes)
     08:34 rail  RE10       Oslo S -> Oslo lufthavn stasjon 08:57 (towards Lillehammer)
     10:10 air   Oslo-Trondheim Oslo lufthavn -> Trondheim lufthavn 11:10 (towards Trondheim)
     11:30 bus   FB73       Trondheim lufthavn -> Prinsens gate 12:07 (towards Flybuss Ekspress Trondheim)

14 API calls, statuses [200], 0.34-1.69 s each
Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS (https://data.norge.no/nlod/en/2.0). Times are Norwegian local time as Entur sends them; layout changed.
```

### 2. robots.txt, the terms and docs quotes, and what the APIs do with mistakes (browser)

7 page loads and 11 in-page `fetch()` calls in the same tab. The developer portal renders client-side, so `page()` waits until the first quote appears before reading `textContent`.

```python
import json, os, re, time

CLIENT = os.environ.get("ET_CLIENT_NAME", "").strip()   # your own '<company>-<application>' (see block 1)
DOC_EXAMPLES = {"company-application", "yourcompany-yourapp", "my_company-my_app", "forsen_utvikling-infoplakat", "entur-developerdocs",
                "brakar-journeyplanner", "fosen_utvikling-infoplakat", "fosen_utvikling-departureboard", "acme-departureboard"}
if not re.fullmatch(r"[a-z0-9_]+-[a-z0-9_.-]+", CLIENT) or CLIENT in DOC_EXAMPLES:
    raise SystemExit("Set ET_CLIENT_NAME to '<company>-<application>' for your own app (lowercase, no spaces); "
                     "Entur's terms forbid fake, random or borrowed values.")
GEO = "https://api.entur.io/geocoder"
JP = "https://api.entur.io/journey-planner/v3/graphql"

START_JS = """(() => { window.__e = window.__e || {}; const id = String(Math.random()).slice(2); window.__e[id] = null;
  const a = %s;
  fetch(a.url, {method: a.body ? 'POST' : 'GET', headers: a.headers, body: a.body, credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__e[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__e[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__e[%s]; if (v) delete window.__e[%s]; return v; })()"""

def raw(url, body=None, ident=True):
    """One in-page request -> {status, headers, text}. No retries: this block only inspects answers."""
    h = {"Accept": "application/json"}
    if ident:
        h["ET-Client-Name"] = CLIENT
    if body is not None:
        h["Content-Type"] = "application/json"
    rid = json.dumps(js(START_JS % json.dumps({"url": url, "headers": h, "body": body})))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1.0)
    return r

def page(url, wait_for=None):
    """Load a page; the developer portal renders client-side, so wait (up to 15 s) for a phrase to appear."""
    goto_url(url)
    wait_for_load()
    t0 = time.time()
    while True:
        txt = js("(document.body || document.documentElement).textContent || ''") or ""
        if not wait_for or wait_for in " ".join(txt.split()) or time.time() - t0 > 15:
            break
        time.sleep(0.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.contentType"), js("location.href"), " ".join(txt.split())

# 1) robots.txt on both hosts
for url in ("https://api.entur.io/robots.txt", "https://developer.entur.no/robots.txt"):
    st, ct, href, txt = page(url)
    print(f"{url.split('//')[1]:<32} HTTP {st} {ct}, 'User-agent' in it: {'user-agent' in txt.lower()}; text starts {txt[:60]!r}")

# 2) terms and docs, rendered as a reader sees them
for url, needles in (
    ("https://developer.entur.no/terms-of-service", [
        "header identifying your application, not you personally",
        "Applications without this header will operate at lower rate limits",
        "Attempting to circumvent rate limiting or traffic shaping measures.",
        "Using fake or randomly generated values in the ET-Client-Name header.",
        "Impersonating traffic from another application or organisation.",
        "NLOD permits free reuse for any purpose, including commercial use",
        "State that the data originates from Entur.",
        "Indicate if you have modified the data.",
        "Do not present the attribution in a way that implies Entur endorses your product or service.",
        "Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS",
        "Last modified on October 21, 2026"]),
    ("https://developer.entur.no/docs/getting-started", [
        "Available to everyone. No partnership agreement required.",
        "in the form <company>-<application> (lowercase, no spaces)",
        "Requests without this header may be rate limited or blocked."]),
    ("https://developer.entur.no/docs/open-services/journey-planner/rate-limiting", [
        "Non-identified consumers",
        "Consumers identified with ET-Client-Name",
        "Clients should NOT implement a retry policy for quota violations",
        "wait at least until the time indicated by Rate-Limit-Expiry-Time"]),
    ("https://developer.entur.no/docs/open-services/geocoder/migration-v2-v3", [
        "was deprecated as of 12.06.2026",
        "Errors come back as HTTP 4xx with an application/problem+json body"]),
):
    st, ct, href, flat = page(url, wait_for=needles[0])
    for n in needles:
        print(f"{href.split('//')[1][:52]:<52} {'found' if n in flat else 'MISSING'}: {n[:72]!r}")
    if "rate-limiting" in url:
        rows = js("[...document.querySelectorAll('table tr')].map(r => [...r.cells].map(c => c.innerText.trim()).join(' | '))")
        for row in rows:
            print(f"{'':<52} table: {row}")
    bad = [w for w in ("scrap", "crawl", "artificial intelligence", "machine learning", "non-commercial",
                       "noncommercial", "robot") if w in flat.lower()]
    print(f"{href.split('//')[1][:52]:<52} words scrap/crawl/AI/ML/non-commercial/robot: {bad or 'none'}")

page("https://developer.entur.no/terms-of-service", wait_for="Terms of service")   # any https origin works (CORS *)
print()

def brief(r, n=120):
    return f"HTTP {r['status']} {r['headers'].get('content-type', '?')}: {' '.join(r['text'].split())[:n]}"

gql = lambda q, v=None: json.dumps({"query": q, "variables": v or {}})
for label, args in (
    ("GraphQL typo (field 'nam')          ", (JP, gql('{ stopPlace(id: "NSR:StopPlace:59872") { nam } }'))),
    ("unknown stop id                     ", (JP, gql('{ stopPlace(id: "NSR:StopPlace:99999999") { id name } }'))),
    ("stop id without NSR prefix          ", (JP, gql('{ stopPlace(id: "59872") { id name } }'))),
    ("337 (the docs' Nationaltheatret id) ", (JP, gql('{ a: stopPlace(id: "NSR:StopPlace:337") { id name parent { id name } } '
                                                     'b: stopPlace(id: "NSR:StopPlace:58404") { id name } }'))),
    ("geocoder v3, focus lat without lon  ", (f"{GEO}/v3/autocomplete?q=Oslo%20S&lat=59.9",)),
    ("geocoder v3, empty q, no filter     ", (f"{GEO}/v3/autocomplete?q=",)),
    ("geocoder v1 (deprecated 12.06.2026) ", (f"{GEO}/v1/autocomplete?text=Oslo%20S&size=1&layers=venue",)),
):
    print(f"{label} {brief(raw(*args), 150)}")

# Rate-limit headers are not exposed to in-page fetch() (no Access-Control-Expose-Headers): only safelisted ones show
r = raw(f"{GEO}/v3/autocomplete?q=Oslo%20S&limit=1")
print(f"geocoder headers visible to fetch(): {sorted(r['headers'])}")

# A trip at night: an empty list with a routing error and a cursor, not an HTTP error
TRIP = """query($c: String) { trip(from: {place: "NSR:StopPlace:59872"}, to: {place: "NSR:StopPlace:59983"},
  numTripPatterns: 1, pageCursor: $c) { routingErrors { code } nextPageCursor metadata { searchWindowUsed }
  tripPatterns { expectedStartTime } } }"""
t = json.loads(raw(JP, gql(TRIP))["text"])["data"]["trip"]
print(f"trip Oslo S -> Bergen stasjon now: {len(t['tripPatterns'])} patterns, errors {[e['code'] for e in t['routingErrors']]}, "
      f"window {t['metadata']['searchWindowUsed']} min, cursor {'yes' if t['nextPageCursor'] else 'no'}")
if not t["tripPatterns"] and t["nextPageCursor"]:
    t2 = json.loads(raw(JP, gql(TRIP, {"c": t["nextPageCursor"]}))["text"])["data"]["trip"]
    print(f"  next page: {[p['expectedStartTime'] for p in t2['tripPatterns']]}, window {t2['metadata']['searchWindowUsed']} min")
r = raw(JP, gql('{ serverInfo { version otpSerializationVersionId } }'))
h = r["headers"]
print(f"journey planner headers visible to fetch(): {sorted(h)}; {brief(r, 90)}")
```

Output (from the run on 2026-11-22, 00:25 UTC; the first run at 00:24 UTC compared rate-limit headers with and without the client name, found them hidden from `fetch()`, and was changed to list the visible headers instead):

```text
api.entur.io/robots.txt          HTTP 404 text/html, 'User-agent' in it: False; text starts 'This api.entur.io page can’t be found No webpage was found f'
developer.entur.no/robots.txt    HTTP 404 text/html, 'User-agent' in it: False; text starts '((e, i, s, u, m, a, l, h) => { let d = document.documentElem'
developer.entur.no/terms-of-service                  found: 'header identifying your application, not you personally'
developer.entur.no/terms-of-service                  found: 'Applications without this header will operate at lower rate limits'
developer.entur.no/terms-of-service                  found: 'Attempting to circumvent rate limiting or traffic shaping measures.'
developer.entur.no/terms-of-service                  found: 'Using fake or randomly generated values in the ET-Client-Name header.'
developer.entur.no/terms-of-service                  found: 'Impersonating traffic from another application or organisation.'
developer.entur.no/terms-of-service                  found: 'NLOD permits free reuse for any purpose, including commercial use'
developer.entur.no/terms-of-service                  found: 'State that the data originates from Entur.'
developer.entur.no/terms-of-service                  found: 'Indicate if you have modified the data.'
developer.entur.no/terms-of-service                  found: 'Do not present the attribution in a way that implies Entur endorses your'
developer.entur.no/terms-of-service                  found: 'Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengel'
developer.entur.no/terms-of-service                  found: 'Last modified on October 21, 2026'
developer.entur.no/terms-of-service                  words scrap/crawl/AI/ML/non-commercial/robot: none
developer.entur.no/docs/getting-started              found: 'Available to everyone. No partnership agreement required.'
developer.entur.no/docs/getting-started              found: 'in the form <company>-<application> (lowercase, no spaces)'
developer.entur.no/docs/getting-started              found: 'Requests without this header may be rate limited or blocked.'
developer.entur.no/docs/getting-started              words scrap/crawl/AI/ML/non-commercial/robot: none
developer.entur.no/docs/open-services/journey-planne found: 'Non-identified consumers'
developer.entur.no/docs/open-services/journey-planne found: 'Consumers identified with ET-Client-Name'
developer.entur.no/docs/open-services/journey-planne found: 'Clients should NOT implement a retry policy for quota violations'
developer.entur.no/docs/open-services/journey-planne found: 'wait at least until the time indicated by Rate-Limit-Expiry-Time'
                                                     table: Level | Trip-request Quota | Trip-request Spike Arrest | Other-request Quota | Other-request Spike Arrest
                                                     table: Non-identified consumers | 30 | 2 | 60 | 20
                                                     table: Consumers identified with ET-Client-Name | 500 | 150 | 1000 | 200
                                                     table: Entur Partners | custom | custom | custom | custom
developer.entur.no/docs/open-services/journey-planne words scrap/crawl/AI/ML/non-commercial/robot: none
developer.entur.no/docs/open-services/geocoder/migra found: 'was deprecated as of 12.06.2026'
developer.entur.no/docs/open-services/geocoder/migra found: 'Errors come back as HTTP 4xx with an application/problem+json body'
developer.entur.no/docs/open-services/geocoder/migra words scrap/crawl/AI/ML/non-commercial/robot: none

GraphQL typo (field 'nam')           HTTP 200 application/json: {"errors":[{"message":"Validation error (FieldUndefined@[stopPlace/nam]) : Field 'nam' in type 'StopPlace' is undefined","locations":[{"line":1,"colum
unknown stop id                      HTTP 200 application/json: {"data":{"stopPlace":null}}
stop id without NSR prefix           HTTP 200 application/json: {"data":{"stopPlace":null}}
337 (the docs' Nationaltheatret id)  HTTP 200 application/json: {"data":{"a":{"id":"NSR:StopPlace:337","name":"Oslo S","parent":{"id":"NSR:StopPlace:59872","name":"Oslo S"}},"b":{"id":"NSR:StopPlace:58404","name":"
geocoder v3, focus lat without lon   HTTP 400 application/problem+json: {"status":400,"title":"Bad Request","detail":"Invalid parameters. Focus parameters (lat, lon, radius, weight) form a bundle: lat and lon must both be 
geocoder v3, empty q, no filter      HTTP 200 application/json: {"type":"FeatureCollection","features":[],"metadata":{"query":{"text":"","limit":10,"lang":"no"},"resultCount":0,"timestamp":"2026-11-22T00:25:50.2659
geocoder v1 (deprecated 12.06.2026)  HTTP 200 application/json: {"geocoding":{"version":"0.2","attribution":"http://pelias.mapzen.com/v1/attribution","engine":{"name":"Photon","author":"Komoot","version":"1.2.0"},"
geocoder headers visible to fetch(): ['cache-control', 'content-type', 'expires', 'pragma']
trip Oslo S -> Bergen stasjon now: 0 patterns, errors ['noTransitConnectionInSearchWindow'], window 270 min, cursor yes
  next page: ['2026-11-22T07:40:00+01:00'], window 510 min
journey planner headers visible to fetch(): ['cache-control', 'content-length', 'content-type', 'expires', 'pragma']; HTTP 200 application/json: {"data":{"serverInfo":{"version":"2.11.0-entur-97","otpSerializationVersionId":"EN-0252"}}
```

### 3. The same with Python urllib, as a command-line tool: robots check for every agent, departures, trips with a departure time (no browser)

Standard library only. It runs with `python3 -I`. Save it as `entur.py`. It makes 3 calls for a departure board (robots.txt, Geocoder, Journey Planner) and 4 to 6 for a trip (1 to 3 Journey Planner pages). Times are converted to Europe/Oslo. `--at` takes a Norwegian local time. `call()` follows Entur's retry policy: on a spike-arrest 429, retry after 2 s; on a quota 429, wait until `Rate-Limit-Expiry-Time` and stop if that is over 120 s; on 5xx, retry once after 10 s.

```python
"""Entur departures and trips from the command line (Python standard library only).

  ET_CLIENT_NAME=yourcompany-yourapp python3 entur.py departures "Trondheim S" [-n 8]
  ET_CLIENT_NAME=yourcompany-yourapp python3 entur.py trip "Bergen stasjon" "Bergen lufthavn" [--at 2026-11-23T08:00]
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

CLIENT = os.environ.get("ET_CLIENT_NAME", "").strip()
DOC_EXAMPLES = {"company-application", "yourcompany-yourapp", "my_company-my_app", "forsen_utvikling-infoplakat", "entur-developerdocs",
                "brakar-journeyplanner", "fosen_utvikling-infoplakat", "fosen_utvikling-departureboard", "acme-departureboard"}
if not re.fullmatch(r"[a-z0-9_]+-[a-z0-9_.-]+", CLIENT) or CLIENT in DOC_EXAMPLES:
    sys.exit("Set ET_CLIENT_NAME to '<company>-<application>' for your own app (lowercase, no spaces); "
             "Entur's terms forbid fake, random or borrowed values.")

GEO = "https://api.entur.io/geocoder/v3/autocomplete"
JP = "https://api.entur.io/journey-planner/v3/graphql"
OSLO = ZoneInfo("Europe/Oslo")
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
PATHS = ["/geocoder/v3/autocomplete", "/journey-planner/v3/graphql"]
NLOD = ("Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS "
        "(https://data.norge.no/nlod/en/2.0)")
calls = []
_last = [0.0]

def http(url, body=None):
    """-> (status, headers, text). Serial, at least 1 s apart."""
    time.sleep(max(0.0, _last[0] + 1.0 - time.time()))
    h = {"ET-Client-Name": CLIENT, "Accept": "application/json"}
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body.encode() if body else None, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = (r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode())
    except urllib.error.HTTPError as e:
        out = (e.code, {k.lower(): v for k, v in e.headers.items()}, e.read().decode(errors="replace"))
    except (urllib.error.URLError, TimeoutError) as e:
        out = (0, {}, str(e))
    _last[0] = time.time()
    calls.append((url.split("?")[0].split("/")[-1] or url, out[0], round(time.time() - t0, 2), out[1].get("rate-limit-available")))
    return out

def expiry_wait(h):
    """Seconds until Rate-Limit-Expiry-Time ('Sun Nov 22 2026 00:20:47 GMT-0000 (GMT)'), else 60."""
    m = re.search(r"\w{3} (\w{3} \d{1,2} \d{4} \d{2}:\d{2}:\d{2})", h.get("rate-limit-expiry-time", ""))
    if not m:
        return 60
    t = datetime.strptime(m.group(1), "%b %d %Y %H:%M:%S").replace(tzinfo=timezone.utc)
    return max(1, int((t - datetime.now(timezone.utc)).total_seconds()) + 1)

def call(url, body=None):
    """-> parsed JSON. Spike-arrest 429 (Spike-Allowed header): retry once after 2 s. Quota 429: wait until
    Rate-Limit-Expiry-Time, once, and stop if that is over 120 s. 5xx or network error: once after 10 s.
    GraphQL errors arrive as HTTP 200 with an `errors` list: raised."""
    for attempt in range(2):
        s, h, text = http(url, body)
        if attempt == 0 and s in (0, 429, 500, 502, 503, 504):
            wait = 2 if (s == 429 and "spike-allowed" in h) else expiry_wait(h) if s == 429 else 10
            if wait > 120:
                sys.exit(f"{url}: HTTP 429, quota resets in {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if s != 200:
        sys.exit(f"{url}: HTTP {s} {' '.join(text.split())[:200]!r}")
    d = json.loads(text)
    if d.get("errors"):
        sys.exit(f"GraphQL errors (HTTP 200): {[e.get('message') for e in d['errors']]}")
    return d

def robots_ok():
    """RFC 9309: a 4xx robots.txt means no rules. If api.entur.io ever publishes one, check every agent."""
    s, _, text = http("https://api.entur.io/robots.txt")
    if 400 <= s < 500:
        print(f"robots.txt api.entur.io: HTTP {s}, no rules; all {len(AGENTS)} agents allowed on {PATHS}")
        return
    if s != 200:
        sys.exit(f"robots.txt: HTTP {s}; try later")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    bad = [(a, p) for a in AGENTS for p in PATHS if not rp.can_fetch(a, "https://api.entur.io" + p)]
    if bad:
        sys.exit(f"robots.txt now disallows {bad}: stop")
    print(f"robots.txt api.entur.io: HTTP 200, all {len(AGENTS)} agents allowed on {PATHS}")

def geocode(text, stops_only):
    p = {"q": text, "limit": 5, "lang": "en"}
    if stops_only:
        p["layers"] = "stopPlace"
    feats = call(GEO + "?" + urlencode(p))["features"]
    if not feats:
        sys.exit(f"Geocoder found nothing for {text!r}")
    for f in feats:                                   # exact name first, else the geocoder's first hit
        if f["properties"]["names"]["default"].lower() == text.lower():
            return f, feats
    return feats[0], feats

def location(f):
    p = f["properties"]
    if p["layer"] in ("stopPlace", "groupOfStopPlaces"):
        return {"place": p["id"], "name": p["names"]["display"]}
    lon, lat = f["geometry"]["coordinates"]           # GeoJSON order
    return {"coordinates": {"latitude": lat, "longitude": lon}, "name": p["names"]["display"]}

def local(iso):
    return datetime.fromisoformat(iso).astimezone(OSLO)

def departures(name, n):
    f, feats = geocode(name, True)
    p = f["properties"]
    print(f"{name!r} -> {p['id']} {p['names']['display']} ({p.get('stopPlaceRole')}); "
          f"next {n} departures, Norwegian time:")
    q = """query($id: String!, $n: Int!) { stopPlace(id: $id) { name estimatedCalls(numberOfDepartures: $n) {
      realtime cancellation aimedDepartureTime expectedDepartureTime quay { publicCode }
      destinationDisplay { frontText } serviceJourney { line { publicCode name transportMode } } } } }"""
    sp = call(JP, json.dumps({"query": q, "variables": {"id": p["id"], "n": n}}))["data"]["stopPlace"]
    if sp is None:
        sys.exit(f"Journey Planner does not know {p['id']}")
    rows = []
    for c in sp["estimatedCalls"]:
        ln = c["serviceJourney"]["line"]
        e, a = local(c["expectedDepartureTime"]), local(c["aimedDepartureTime"])
        late = round((e - a).total_seconds() / 60)
        state = "cancelled" if c["cancellation"] else ("real-time" if c["realtime"] else "timetable")
        rows.append((e.strftime("%a %H:%M"), ln["transportMode"], ln["publicCode"] or ln["name"],
                     c["destinationDisplay"]["frontText"], c["quay"]["publicCode"] or "-", f"{late:+d}", state))
    print("  expected   mode   line    destination                        platform  delay_min  status")
    for r in rows:
        print(f"  {r[0]:<10} {r[1]:<6} {r[2]:<7} {r[3]:<34} {r[4]:<9} {r[5]:<10} {r[6]}")

def trip(a, b, at):
    (fa, _), (fb, _) = geocode(a, False), geocode(b, False)
    la, lb = location(fa), location(fb)
    print(f"trip {la['name']} [{fa['properties']['layer']}] -> {lb['name']} [{fb['properties']['layer']}]"
          f"{', leaving after ' + at.isoformat() if at else ', leaving now'}:")
    q = """query($from: Location!, $to: Location!, $at: DateTime, $c: String) {
      trip(from: $from, to: $to, numTripPatterns: 3, dateTime: $at, pageCursor: $c) {
        routingErrors { code } nextPageCursor
        tripPatterns { expectedStartTime expectedEndTime duration
          legs { mode expectedStartTime expectedEndTime fromPlace { name } toPlace { name } line { publicCode name } } } } }"""
    v = {"from": la, "to": lb, "at": at.isoformat() if at else None, "c": None}
    for page in range(3):                             # an empty window (night) is not an error: follow the cursor
        t = call(JP, json.dumps({"query": q, "variables": v}))["data"]["trip"]
        if t["tripPatterns"] or not t["nextPageCursor"]:
            break
        print(f"  (no trip in this search window, {[e['code'] for e in t['routingErrors']]}; next page)")
        v["c"] = t["nextPageCursor"]
    if not t["tripPatterns"]:
        print(f"  no trip: {[e['code'] for e in t['routingErrors']]}")
    for tp in t["tripPatterns"]:
        ride = [l for l in tp["legs"] if l["mode"] != "foot"]
        s, e = local(tp["expectedStartTime"]), local(tp["expectedEndTime"])
        print(f"  {s:%a %H:%M} -> {e:%H:%M}  {tp['duration'] // 3600} h {tp['duration'] % 3600 // 60:02d} min  "
              + "  >  ".join(f"{l['mode']} {(l['line'] or {}).get('publicCode') or (l['line'] or {}).get('name') or ''} "
                             f"{l['fromPlace']['name']} {local(l['expectedStartTime']):%H:%M}-{local(l['expectedEndTime']):%H:%M} "
                             f"{l['toPlace']['name']}" for l in ride))

ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
d = sub.add_parser("departures"); d.add_argument("stop"); d.add_argument("-n", type=int, default=8)
t = sub.add_parser("trip"); t.add_argument("origin"); t.add_argument("destination")
t.add_argument("--at", help="local Norwegian time, e.g. 2026-11-23T08:00")
args = ap.parse_args()

print(f"Entur, checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
robots_ok()
if args.cmd == "departures":
    departures(args.stop, args.n)
else:
    at = datetime.fromisoformat(args.at) if args.at else None
    trip(args.origin, args.destination, at.replace(tzinfo=OSLO) if at and at.tzinfo is None else at)
print(f"{len(calls)} calls: " + ", ".join(f"{n} {s} {t}s" for n, s, t, _ in calls)
      + f"; rate-limit-available after the last: {calls[-1][3]}")
print(NLOD + "; layout and time zone conversion by this script.")
```

Output (three runs on 2026-11-22, 00:26 UTC; `rate-limit-available` counts down the shared 2-minute window, which this session's earlier calls had already used):

```text
$ python3 -I entur.py departures "Trondheim S"
Entur, checked 2026-11-22 00:26 UTC
robots.txt api.entur.io: HTTP 404, no rules; all 11 agents allowed on ['/geocoder/v3/autocomplete', '/journey-planner/v3/graphql']
'Trondheim S' -> NSR:StopPlace:59977 Trondheim S, Trondheim (parent); next 8 departures, Norwegian time:
  expected   mode   line    destination                        platform  delay_min  status
  Sun 01:33  bus    4101    Fannrem                            11        +0         timetable
  Sun 01:36  bus    116     Stjørdal via Brattøra-Hommelvik    13        +0         timetable
  Sun 02:33  bus    4101    Fannrem                            11        +0         timetable
  Sun 02:36  bus    116     Stjørdal via Brattøra-Sveberg      13        +0         timetable
  Sun 03:36  bus    116     Stjørdal via Brattøra-Hommelvik    13        +0         timetable
  Sun 06:24  bus    2       Lund via Kolstad-Heimdal           10        +0         timetable
  Sun 06:47  bus    2       Strindheim via Lade                13        +0         timetable
  Sun 06:54  bus    2       Lund via Kolstad-Heimdal           10        +0         timetable
3 calls: robots.txt 404 0.19s, autocomplete 200 0.63s, graphql 200 0.62s; rate-limit-available after the last: 1985
Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS (https://data.norge.no/nlod/en/2.0); layout and time zone conversion by this script.

$ python3 -I entur.py trip "Bergen stasjon" "Bergen lufthavn"
Entur, checked 2026-11-22 00:26 UTC
robots.txt api.entur.io: HTTP 404, no rules; all 11 agents allowed on ['/geocoder/v3/autocomplete', '/journey-planner/v3/graphql']
trip Bergen stasjon, Bergen [stopPlace] -> Bergen lufthavn, Bergen [stopPlace], leaving now:
  Sun 01:30 -> 02:13  0 h 43 min  tram 1 Nonneseter 01:31-02:13 Bergen lufthavn
  Sun 01:45 -> 02:28  0 h 43 min  tram 1 Nonneseter 01:46-02:28 Bergen lufthavn
  Sun 02:00 -> 02:43  0 h 43 min  tram 1 Nonneseter 02:01-02:43 Bergen lufthavn
4 calls: robots.txt 404 0.19s, autocomplete 200 0.21s, autocomplete 200 0.2s, graphql 200 0.52s; rate-limit-available after the last: 995
Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS (https://data.norge.no/nlod/en/2.0); layout and time zone conversion by this script.

$ python3 -I entur.py trip "Karl Johans gate 22, Oslo" "Trondheim S" --at 2026-11-23T08:00
Entur, checked 2026-11-22 00:26 UTC
robots.txt api.entur.io: HTTP 404, no rules; all 11 agents allowed on ['/geocoder/v3/autocomplete', '/journey-planner/v3/graphql']
trip Karl Johans gate 22, Oslo [address] -> Trondheim S, Trondheim [stopPlace], leaving after 2026-11-23T08:00:00+01:00:
  Mon 09:33 -> 12:48  3 h 14 min  bus 37 Wessels plass 09:37-09:42 Jernbanetorget  >  rail FLY2 Oslo S 09:50-10:09 Oslo lufthavn stasjon  >  air Oslo-Trondheim Oslo lufthavn 10:50-11:45 Trondheim lufthavn  >  bus 311 Trondheim lufthavn 12:15-12:48 Trondheim S
  Mon 09:37 -> 12:48  3 h 10 min  rail FLY2 Oslo S 09:50-10:09 Oslo lufthavn stasjon  >  air Oslo-Trondheim Oslo lufthavn 10:50-11:45 Trondheim lufthavn  >  bus 311 Trondheim lufthavn 12:15-12:48 Trondheim S
  Mon 08:39 -> 12:48  4 h 08 min  metro 3 Stortinget 08:44-08:52 Helsfyr  >  coach VY190 Helsfyr T 08:57-09:30 Oslo lufthavn  >  air Oslo-Trondheim Oslo lufthavn 10:50-11:45 Trondheim lufthavn  >  bus 311 Trondheim lufthavn 12:15-12:48 Trondheim S
4 calls: robots.txt 404 0.19s, autocomplete 200 0.2s, autocomplete 200 0.2s, graphql 200 1.75s; rate-limit-available after the last: 994
Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS (https://data.norge.no/nlod/en/2.0); layout and time zone conversion by this script.
```

### 4. curl: stop search, departures, a trip at a set time, headers, mistakes

```bash
#!/usr/bin/env bash
# Set your own '<company>-<application>' first (Entur's terms: no fake, random or borrowed values):
#   export ET_CLIENT_NAME=yourcompany-yourapp
set -u
: "${ET_CLIENT_NAME:?set ET_CLIENT_NAME to <company>-<application> for your own app}"
case "$ET_CLIENT_NAME" in
  company-application|yourcompany-yourapp|my_company-my_app|forsen_utvikling-infoplakat|entur-developerdocs|brakar-journeyplanner|fosen_utvikling-infoplakat|fosen_utvikling-departureboard|acme-departureboard)
    echo "ET_CLIENT_NAME is an example value; use your own app's name" >&2; exit 1;;
esac
[[ "$ET_CLIENT_NAME" =~ ^[a-z0-9_]+-[a-z0-9_.-]+$ ]] || { echo "ET_CLIENT_NAME must be <company>-<application>, lowercase, no spaces" >&2; exit 1; }
C=(curl -sS --max-time 30 -H "ET-Client-Name: $ET_CLIENT_NAME")
JP=https://api.entur.io/journey-planner/v3/graphql
# 1. stop name -> NSR id (Geocoder v3; layers=stopPlace keeps stops only)
"${C[@]}" "https://api.entur.io/geocoder/v3/autocomplete?q=Bergen%20stasjon&layers=stopPlace&limit=3&lang=en" \
  | python3 -c 'import json, sys
for f in json.load(sys.stdin)["features"]:
    p = f["properties"]; print(p["id"], "|", p["names"]["display"], "|", p.get("stopPlaceRole"), "|", f["geometry"]["coordinates"])'
sleep 1
# 2. next 5 departures from Bergen stasjon (expected and aimed time, line, destination, platform)
"${C[@]}" -X POST "$JP" -H 'Content-Type: application/json' -d '{"query":"query($id: String!) { stopPlace(id: $id) { name estimatedCalls(numberOfDepartures: 5) { expectedDepartureTime aimedDepartureTime realtime cancellation quay { publicCode } destinationDisplay { frontText } serviceJourney { line { publicCode transportMode } } } } }","variables":{"id":"NSR:StopPlace:59983"}}' \
  | python3 -c 'import json, sys
d = json.load(sys.stdin)
if d.get("errors"): sys.exit(d["errors"])
for c in d["data"]["stopPlace"]["estimatedCalls"]:
    l = c["serviceJourney"]["line"]
    print(c["expectedDepartureTime"], l["transportMode"], l["publicCode"], c["destinationDisplay"]["frontText"], "platform", c["quay"]["publicCode"], "aimed", c["aimedDepartureTime"][11:16], "realtime" if c["realtime"] else "timetable", "CANCELLED" if c["cancellation"] else "")'
sleep 1
# 3. trip Oslo S -> Trondheim S, Monday 08:00 Norwegian time, two options
"${C[@]}" -X POST "$JP" -H 'Content-Type: application/json' -d '{"query":"{ trip(from: {place: \"NSR:StopPlace:59872\"}, to: {place: \"NSR:StopPlace:59977\"}, dateTime: \"2026-11-23T08:00:00+01:00\", numTripPatterns: 2) { routingErrors { code } tripPatterns { expectedStartTime expectedEndTime duration legs { mode line { publicCode } fromPlace { name } toPlace { name } } } } }"}' \
  | python3 -c 'import json, sys
t = json.load(sys.stdin)["data"]["trip"]; print("routingErrors", t["routingErrors"])
for p in t["tripPatterns"]:
    legs = [" ".join([l["mode"], (l["line"] or {}).get("publicCode") or "", l["fromPlace"]["name"] + "-" + l["toPlace"]["name"]])
            for l in p["legs"] if l["mode"] != "foot"]
    print(p["expectedStartTime"], "->", p["expectedEndTime"], p["duration"] // 60, "min |", " > ".join(legs))'
sleep 1
# 4. headers: quota for identified clients, CORS open, nothing cacheable
"${C[@]}" -D - -o /dev/null -X POST "$JP" -H 'Content-Type: application/json' -d '{"query":"{ serverInfo { version } }"}' | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|access-control-allow-origin|rate-limit-[a-z-]+|spike-[a-z]+|retry-after):)'
sleep 1
# 5. mistakes: GraphQL errors are HTTP 200 with an errors list; unknown ids are null; Geocoder errors are problem+json
T=$(mktemp)
for body in '{"query":"{ stopPlace(id: \"NSR:StopPlace:59983\") { nam } }"}' '{"query":"{ stopPlace(id: \"NSR:StopPlace:99999999\") { name } }"}'; do
  "${C[@]}" -o "$T" -w '%{http_code} ' -X POST "$JP" -H 'Content-Type: application/json' -d "$body"; head -c 170 "$T"; echo; sleep 1
done
"${C[@]}" -o "$T" -w '%{http_code} %{content_type} ' "https://api.entur.io/geocoder/v3/autocomplete?q=Bergen&lon=5.3"; cat "$T"; echo
rm -f "$T"
sleep 1
# 6. no robots rules on the API host
curl -sS -o /dev/null -w 'api.entur.io/robots.txt: HTTP %{http_code}, %{size_download} bytes\n' https://api.entur.io/robots.txt
echo "Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS (https://data.norge.no/nlod/en/2.0). Accessed $(date -u '+%d %B %Y %H:%M') UTC."
```

Output (from the run on 2026-11-22, 00:27 UTC):

```text
NSR:StopPlace:59983 | Bergen stasjon, Bergen | parent | [5.333511, 60.390434]
NSR:StopPlace:398 | Arna stasjon, Bergen | standalone | [5.46609, 60.420097]
NSR:StopPlace:59169 | Garnes stasjon, Bergen | standalone | [5.470124, 60.446715]
2026-11-22T01:57:00+01:00 rail L4 Arna platform 1 aimed 01:57 realtime 
2026-11-22T02:27:00+01:00 rail L4 Arna platform 1 aimed 02:27 realtime 
2026-11-22T05:42:00+01:00 rail L4 Arna platform 1 aimed 05:42 realtime 
2026-11-22T07:04:00+01:00 rail R40 Voss platform 2 aimed 07:04 realtime 
2026-11-22T07:27:00+01:00 rail L4 Arna platform 1 aimed 07:27 realtime 
routingErrors []
2026-11-23T08:00:00+01:00 -> 2026-11-23T11:04:00+01:00 184 min | rail FLY1 Oslo S-Oslo lufthavn stasjon > air  Oslo lufthavn-Trondheim lufthavn > bus FB73 Trondheim lufthavn-Gildheim > bus 70 Gildheim-Trondheim S
2026-11-23T08:00:00+01:00 -> 2026-11-23T11:08:00+01:00 188 min | rail FLY1 Oslo S-Oslo lufthavn stasjon > air  Oslo lufthavn-Trondheim lufthavn > bus 311 Trondheim lufthavn-Trondheim S
HTTP/2 200 
content-type: application/json
cache-control: no-cache, no-store, max-age=0, must-revalidate
rate-limit-allowed: 2000
rate-limit-used: 2
rate-limit-available: 1998
rate-limit-range: PT2M
rate-limit-expiry-time: Sun Nov 22 2026 00:29:09 GMT-0000 (GMT)
access-control-allow-origin: *
200 {"errors":[{"message":"Validation error (FieldUndefined@[stopPlace/nam]) : Field 'nam' in type 'StopPlace' is undefined","locations":[{"line":1,"column":42}],"extensions"
200 {"data":{"stopPlace":null}}
400 application/problem+json {"status":400,"title":"Bad Request","detail":"Invalid parameters. Focus parameters (lat, lon, radius, weight) form a bundle: lat and lon must both be set when any is provided"}
api.entur.io/robots.txt: HTTP 404, 0 bytes
Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS (https://data.norge.no/nlod/en/2.0). Accessed 22 November 2026 00:27 UTC.
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| Geocoder v3 `features[].properties.id` | `NSR:StopPlace:59983`, `NSR:GroupOfStopPlaces:10`, `KVE:PostalAddress:285717926`, `KVE:PlaceName:303660` | NSR ids work as `stopPlace(id:)` and `trip(from: {place:})`. Groups of stop places ("Trondheim") also work as `place`. Use addresses and place names as coordinates |
| `properties.layer` | `stopPlace`, `groupOfStopPlaces`, `address`, `street`, `poi`, `place` | `layers=stopPlace` keeps stops only. Without a `layers` filter, addresses are hidden unless the query has a digit or `sources=kartverket-matrikkelenadresse` (migration guide). `street` is from the guide's table: on 2026-11-22 "Karl Johans gate" (no digit) returned the street as `layer: address` with `KVE:TopographicPlace` ids |
| `properties.names` | `{default, display, label?}` | `display` adds the locality ("Bergen stasjon, Bergen"). `label` is a colloquial name ("Gardermoen" for Oslo lufthavn, "Værnes" for Trondheim lufthavn) |
| `properties.stopPlaceRole` | `parent`, `child`, `standalone` | the default `multimodal=parent` hides children such as 337 |
| `properties.transportModes`, `stopPlaceTypes`, `fareZones` | `[{mode: "rail"}, {mode: "bus", subMode: "railReplacementBus"}]`, `["onstreetBus", "railStation"]`, `["RUT:FareZone:4"]` | |
| `geometry.coordinates` | `[lon, lat]` | GeoJSON order. `trip` wants `{latitude, longitude}` |
| `metadata` | `{query, resultCount, timestamp}` | |
| `estimatedCalls[]` | `aimedDepartureTime`, `expectedDepartureTime` (`2026-11-22T04:40:00+01:00`), `realtime`, `cancellation`, `quay.publicCode` (platform), `destinationDisplay.frontText`, `serviceJourney.line.{publicCode, name, transportMode}` | local time with offset (`+01:00` in winter). `realtime: false` means timetable only. `quay.publicCode` can be a letter (`N`, `C`), empty (`""`) or `null` |
| `trip.tripPatterns[]` | `expectedStartTime`, `expectedEndTime`, `duration` (seconds), `legs[]` | legs include `foot` legs (walks between stops). The blocks print only the rides |
| `legs[]` | `mode` (`rail`, `bus`, `coach`, `tram`, `metro`, `air`, `foot`, ...), `line.{publicCode, name}`, `fromPlace.name`, `toPlace.name`, `expectedStartTime`, `expectedEndTime`, `fromEstimatedCall.destinationDisplay.frontText` | flights have `publicCode: null` and the route as `name` ("Oslo-Bergen") |
| `trip.routingErrors[]`, `nextPageCursor`, `metadata.searchWindowUsed` | `noTransitConnectionInSearchWindow`, an opaque cursor, minutes | an empty result is HTTP 200 with a routing error |
| `serverInfo` | `{"version": "2.11.0-entur-97", "otpSerializationVersionId": "EN-0252"}` | Entur's OpenTripPlanner build on the day |
| response headers | `rate-limit-allowed`, `rate-limit-used`, `rate-limit-available`, `rate-limit-range` (`PT2M` or `"per-minute"`), `rate-limit-expiry-time` (`Sun Nov 22 2026 00:29:09 GMT-0000 (GMT)`), `cache-control: no-cache, no-store, max-age=0, must-revalidate`, `access-control-allow-origin: *` | `Spike-Allowed` and `Spike-Range` appear only on a spike-arrest 429 (docs). There is no `Access-Control-Expose-Headers`, so a browser sees only `cache-control`, `content-type`, `expires`, `pragma` (and `content-length` on GraphQL) |

## Gotchas

- **ET-Client-Name is yours to choose, not to copy.** Format `<company>-<application>`, lowercase, no spaces. The terms forbid fake or random values and impersonating another application. Without the header, the Journey Planner granted 120 requests per 2 minutes instead of 2,000, and the Geocoder 600 a minute instead of 1,000 (one curl probe each). The terms page says throttling or blocking is most likely caused by "missing or invalid client identification".
- **Use Geocoder v3.** The migration guide says "Geocoder v1/v2 was deprecated as of 12.06.2026". `/geocoder/v1/autocomplete?text=` and `/v2/` still answered HTTP 200 on 2026-11-22, in the old Pelias shape (`name`, `label`, `layer: "venue"`). v3 renames `text` to `q`, `size` to `limit`, the `venue` layer to `stopPlace`, and `focus.point.lat` to `lat`. Old `sources` values match nothing or the wrong data, without an error.
- **The docs' example id is not Nationaltheatret.** The migration guide's sample shows `NSR:StopPlace:337` as "Nationaltheatret". The live API calls 337 "Oslo S" (the rail child of 59872), and the Geocoder returned `NSR:StopPlace:58404` for "Nationaltheatret" (curl, while exploring). Always look the id up.
- **Same name, different places.** "Flesland" returned `KVE:PlaceName:303660` and `NSR:StopPlace:28298` (both in Karmøy) before `NSR:StopPlace:31685` (Bergen). The early block 3 run planned a 4 h 19 min coach trip to the Karmøy one. Check `names.display`, use the full name ("Bergen lufthavn"), or bias with `lat`/`lon`. `lat` without `lon` is HTTP 400 `application/problem+json` ("Focus parameters (lat, lon, radius, weight) form a bundle").
- **GraphQL mistakes are HTTP 200.** A misspelt field gives `{"errors": [{"message": "Validation error (FieldUndefined@[stopPlace/nam]) ...", "extensions": {"classification": "ValidationError"}}]}`. An unknown or prefix-less id (`59872`) gives `{"data": {"stopPlace": null}}`. Check `errors` and `null` yourself, as the blocks do.
- **Night and the search window.** `trip` with no `dateTime` searches from now in a server-chosen window (270 minutes for Oslo S -> Bergen at 01:20). An empty window returns `[]` plus `nextPageCursor`. Pass that as `pageCursor`, set `dateTime`, or set `searchWindow` in minutes (`720` returned trips in one call during exploration).
- **Trips may start or end at a nearby stop.** Oslo S -> Bergen stasjon ended with airport bus FB50 to Bergen busstasjon, or tram 1 to Nonneseter, then a walk. Bergen stasjon -> Bergen lufthavn started with a walk to the tram at Nonneseter. The walks are `foot` legs. Keep them if you show a full itinerary.
- **The fastest option may fly.** Oslo -> Bergen and Oslo -> Trondheim came back as train + flight + bus combinations. To restrict modes, filter the GraphQL query; that is not tested here.
- **Times.** Entur sends ISO 8601 times with the Norwegian offset (`+01:00` until the end of March, `+02:00` in summer). Delays are `expected - aimed` and the times carry seconds, so an "01:24" departure that was due at 01:20 can be 5 minutes late after rounding. `realtime: false` means the time is from the timetable, with no live prediction.
- **Rate-limit headers.** Journey Planner reports 2-minute windows (`PT2M`): 2,000 for ordinary queries and 1,000 for trips, which is the documented 1,000 and 500 a minute. `rate-limit-available` is a running count for the whole window, not per process: block 3's first run already read 1985 after the earlier scripts' calls. Never retry a quota 429 before `Rate-Limit-Expiry-Time` (docs).
- **Nothing is cacheable.** Every answer is `no-cache, no-store`. Departures are live, so ask when you need them, not on a tight loop.
- **Privacy.** The terms say Entur logs IP addresses, request paths and the `ET-Client-Name` value and keeps the logs 14 months. The Journey Planner page says Entur keeps anonymised data about searches. If your users' trips pass through your app, telling them is your job (GDPR, per the same pages).
- **Old portal.** developer.entur.org pages say "Entur's developer portal has moved to developer.entur.no". Use the new portal. Any page there is also Markdown if you add `.md`, and `https://developer.entur.no/llms.txt` indexes them.
- **Credit and no logo.** Show "Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS" (English: "Contains data under the Norwegian licence for Open Government data (NLOD) distributed by Entur AS") with a link to https://data.norge.no/nlod/en/2.0. Say if you changed the data, use no Entur logo, and do not suggest Entur endorses your app.
- **Tab marker.** The harness sets the tab title to a horse emoji. The blocks check `location.origin` and the page text, not the title.

## What does not work

- **No header, a placeholder header, or someone else's name**: allowed by the server at much lower limits, but against the terms. The blocks refuse to start.
- **Geocoder v1/v2 parameters on v3** (`text=`, `size=`, `layers=venue`): use `q`, `limit`, `layers=stopPlace`. v1/v2 themselves are deprecated.
- **Reading rate-limit headers from a browser `fetch()`**: they are not exposed. Use urllib or curl if you need them.
- **Partner endpoints** (sales, ticketing): OAuth 2.0 and a partner agreement. Out of scope.
- **Not tested:** a 429 (never provoked; the limits above are from the docs and headers), the `modes` and `whiteListed` filters on `trip`, `searchWindow` in the blocks (tested only while exploring), `situations` (disruption messages), the Geocoder `/v3/reverse` and `/v3/place` endpoints, the vehicle-positions, mobility and real-time SIRI/GTFS-RT feeds, and summer-time (`+02:00`) answers.
