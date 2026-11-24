# Digitraffic (Fintraffic) via rata.digitraffic.fi - List the Next Trains Departing Helsinki Central (HKI) or Any Finnish Station, With Scheduled vs Live Estimated Time, Track, Destination and Cancellations (REST JSON, no key, gzip required)

Field-tested against rata.digitraffic.fi and www.digitraffic.fi on 2026-11-23 (US Pacific afternoon; 23:55 UTC on 23 November to 00:02 UTC on 24 November, which was 01:55-02:02 on Tuesday 24 November in Helsinki) using a fresh Browser Use cloud browser (logged out; one session, 23:57-00:01 UTC) plus Python `urllib` and `curl` from a Linux machine. 12 browser page loads (1 smoke test, 1 in block 1's first run, 5 in each of block 2's two runs) and 16 in-page `fetch()` calls (3 in each run of block 1, 5 in each run of block 2), 19 urllib calls (block 3: 3 commands in its first run, 5 in its second, one of them refused before any call) and 36 curl calls (22 while exploring the API, the OpenAPI document and a full day of trains, 7 in each of block 4's two runs), all serial and at least 1 s apart. Every API call sent `Digitraffic-User: BrowserUse/domain-skills` except the deliberate anonymous ones (one curl call while exploring, the 3 calls of block 3's `Pasila` run, and the no-gzip call in each run of block 4), which answered the same way. Every call was HTTP 200 except the deliberate probes: HTTP 406 without `Accept-Encoding: gzip`, HTTP 400 for `departing_trains=abc` and `train_categories=Night`, HTTP 404 for www.digitraffic.fi/robots.txt and `/api/v1/swagger.json`, HTTP 403 for `/swagger/rata-api.json` and a 302 from `/api-docs/rata-api.json` to the Finnish docs page. curl timed live-train answers at 0.50-0.85 s and the station list at 0.51 s; one whole day of trains (`/api/v1/trains/2026-11-23`, 1,792 trains) took 4.20 s for 918 KB of gzip (21 MB of JSON). No 429, no challenge, no key, no login, no cookie. The outputs below are the second runs of blocks 1 to 4 (00:00-00:01 UTC on 24 November); the first runs (23:57-00:00 UTC) gave the same departures and the same block 2 output. It was 02:00 at night in Finland, so the Helsinki board shows the first morning trains with timetable times only; live estimates appear on trains already running (the Tampere board). An independent verifier re-ran all four blocks verbatim on 2026-11-24 00:03-00:04 UTC (a second fresh cloud browser, urllib, curl): every block ran, and the departures, tracks, estimates and block 2 lines were identical; only call timings and block 4's access time changed. After a code review, blocks 2, 3 and 4 changed and re-ran on 2026-11-24 between 00:28 and 00:36 UTC (browser blocks in a new cloud browser); the outputs shown for them come from those runs. A second review round changed block 3 again; its re-run at 00:44 UTC printed the same apart from times. A website review changed block 3's `--to` path (it asks again with a larger limit when the category filter leaves fewer than `-n`); its re-run of the five commands shown, at 01:45 UTC, printed the same apart from times and one HKI train that had left by then.

robots.txt (checked 2026-11-23/24 UTC, curl, the cloud browser and block 3): https://rata.digitraffic.fi/robots.txt is `User-agent: *` / `Allow: /` with no named agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider may fetch every API path this skill uses (block 2 checks these 11 agents with Python's `urllib.robotparser`; block 3 checks the same 11 plus its own User-Agent before every API call and stops if the file ever disallows one; block 4 reads it before any API call). https://www.digitraffic.fi/robots.txt answers HTTP 404 with the site's "404 - Page not found." page, so the docs host has no rules; RFC 9309 (section 2.3.1.3) says a 4xx robots.txt means "the crawler MAY access any resources on the server". Terms: https://www.digitraffic.fi/en/terms-of-service/ (0 changed lines against the copy read on 2026-11-21): "Fintraffic’s open data is licensed under the Creative Commons 4.0 By license. It gives the right to distribute, remix, tweak, and build upon our data, even commercially, as long as you credit the source for the original creation." Attribution: "you must give appropriate credit, provide a link to the license, and indicate if changes were made"; "If the material has beem modified, it must be accompanied with a notice describing the modification and a hyperlink to the website of the original material" (spelling as on the page); the example credit line is "Source: Fintraffic / digitraffic.fi, license CC 4.0 BY". The railway page https://www.digitraffic.fi/en/railway-traffic/ says (under its GTFS and NeTEx feed sections) "Data is licensed under Creative Commons Attribution 4.0 International", and the API's own OpenAPI document (https://rata.digitraffic.fi/swagger/openapi.json) names the licence "Creative Commons 4.0 BY" and links the terms. The instructions page https://www.digitraffic.fi/en/support/instructions/: "The Digitraffic-User header should include an identifiable user party and/or application. Using the header increases the amount of requests you can make.", "Don’t send any PII (personally identifiable information) via the headers!" and "The use of compression is mandatory on all interfaces except for weather camera images." No AI/ML, scraping, crawling, robot or non-commercial wording on the terms, instructions or railway pages (block 2 checks the quotes and scans for the words). Naming: this skill writes "Digitraffic (Fintraffic)" in plain text, shows no Fintraffic logo, is not affiliated with or endorsed by Fintraffic, and blocks 1, 3 and 4 (the ones that show train data) print the CC BY 4.0 credit line with a link to the licence and what it changed.

**Set your own `Digitraffic-User` value.** Every block reads `DIGITRAFFIC_USER` from the environment, for example `acme/departure-board 1.0` for Acme's departure board (a party and/or app name, no personal data). It is optional: without it the calls are anonymous and fall under the 60 requests a minute limit; on 2026-11-23 anonymous calls also returned HTTP 200. The blocks refuse the example values from Digitraffic's docs (`Junamies/FoobarApp 1.0`, `Fintraffic`, ...). The runs here used Browser Use's own value, which you should not reuse.

## Quick summary

- **No scraping needed.** One open endpoint, JSON, no key, gzip required. Next departures: `GET https://rata.digitraffic.fi/api/v1/live-trains/station/HKI?departing_trains=10&arrived_trains=0&arriving_trains=0&departed_trains=0&include_nonstopping=false&train_categories=Long-distance,Commuter` -> a list of trains, each with every stop in `timeTableRows`; take the row with `stationShortCode == "HKI"` and `type == "DEPARTURE"` for `scheduledTime`, `liveEstimateTime`, `differenceInMinutes`, `commercialTrack` and `cancelled`; the destination is the last row's station. Station names to codes: `GET /api/v1/metadata/stations` (563 entries, 215 with passenger traffic). Trains between two stations: `GET /api/v1/live-trains/station/HKI/TPE?limit=5`. Send `Accept-Encoding: gzip` (HTTP 406 without it) and a `Digitraffic-User` header. `Access-Control-Allow-Origin: *`, so `fetch()` works from any https page.
- **Answers (24 November 2026, 00:00 UTC = 02:00 Tuesday in Helsinki):** the next departures from **Helsinki asema (HKI)** were **HV 10101 (line V) to Kerava at 03:37 from track 4**, then **HL 8601 (P, ring line via the airport, Lentoasema) at 04:18 from track 19**, HL 9619 (R) to Riihimäki at 04:20 from track 8, HV 10045 (V) to Kirkkonummi at 04:23 from track 13; none cancelled, none with a live estimate yet (they had not started). **Helsinki -> Tampere:** IC 35 (to Rovaniemi) at 05:03 from track 9, arriving 06:53; HL 9621 (R) at 05:10, arriving 07:35. **Tampere asema** had live estimates on the running night trains: PYO 273 to Rovaniemi at 02:37, estimate 02:37 (+0 min).
- **Ask only for departures.** The station endpoint defaults to 5 arrived, 5 arriving, 5 departed and 5 departing trains. Without the four counts, block 2's call got 18 trains: 5 still to depart, 6 already gone, 7 that only arrive at HKI, and the 18 included on-track machines and shunting moves. Set the other three to 0 and `train_categories=Long-distance,Commuter` to drop work trains.
- **Sort it yourself.** The list comes in train-number order, not departure order. Times are UTC (`2026-11-24T01:37:00.000Z`); the OpenAPI document says times are ISO 8601 "with "Zulu" zero offset from UTC unless otherwise specified". Convert to Europe/Helsinki.
- **Rate limits (instructions page):** 60 requests a minute per IP for the "General restriction" without `Digitraffic-User`; "You can make more requests when the header is set" (no number published). Over the limit the API answers HTTP 429. The responses carry no rate-limit headers, only `cache-control: max-age=30, public`, and "Most of the caches are one minute long", so polling faster than every 30 s returns the same data. The blocks run serially at 1 call a second; block 1 stops on a 429, block 3 waits 60 s once and then stops.

## What works

### 1. Next departures by station code or name (browser)

`on_digitraffic_tab()` opens one logged-out www.digitraffic.fi page. The API answers `Access-Control-Allow-Origin: *` and allows the `Digitraffic-User` header, so any https page would do. The browser sends `Accept-Encoding: gzip` itself (scripts cannot set it), which the API requires. `call()` returns parsed JSON on HTTP 200, stops on a 429 and waits 10 s once on 5xx or a network error. The station list costs 1 call and each station 1 more; the run below made 3. To ask about other stations, edit `STATIONS` and `N`.

```python
import json, os, time
from datetime import datetime, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

API = "https://rata.digitraffic.fi/api/v1"
HEL = ZoneInfo("Europe/Helsinki")
PAUSE = 1.0   # serial, 1 call a second: under the 60 a minute Digitraffic allows without the header
N = 10        # departures per station
STATIONS = ["HKI", "Tampere"]   # station short codes or names, as in /metadata/stations

# Digitraffic asks for a Digitraffic-User header naming your party and/or app (no personal data); it raises
# your request limit. Set DIGITRAFFIC_USER to your own value. Without it the calls are anonymous (60 a minute).
USER = os.environ.get("DIGITRAFFIC_USER", "").strip()
DOC_EXAMPLES = {"junamies/foobarapp 1.0", "trainguy/foobarapp 1.0", "fintraffic", "liikennetilanne",
                "fintraffic/liikennetilanne", "dt/tester"}
if USER.lower() in DOC_EXAMPLES:
    raise SystemExit("DIGITRAFFIC_USER is an example from Digitraffic's docs; use your own app's name")

def on_digitraffic_tab():
    """Any https page works (rata.digitraffic.fi answers Access-Control-Allow-Origin: * and allows the
    Digitraffic-User header); the logged-out railway docs page keeps the tab on Digitraffic's own site."""
    try:
        if js("location.origin") == "https://www.digitraffic.fi":
            return
    except Exception:
        pass
    new_tab("https://www.digitraffic.fi/en/railway-traffic/")
    wait_for_load()
    if js("location.origin") != "https://www.digitraffic.fi":
        raise RuntimeError(f"www.digitraffic.fi did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it. The browser itself sends
# Accept-Encoding: gzip (scripts cannot set it), which the API requires.
START_JS = """(() => { window.__d = window.__d || {}; const id = String(Math.random()).slice(2); window.__d[id] = null;
  const a = %s;
  fetch(a.url, {headers: a.headers, credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__d[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__d[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__d[%s]; if (v) delete window.__d[%s]; return v; })()"""

calls = []
def call(path, params=None):
    """GET -> parsed JSON. 429: stop (the limit is per minute; wait a minute). 5xx or network error: one retry
    after 10 s. Anything else that is not HTTP 200 stops."""
    url = API + path + ("?" + urlencode(params) if params else "")
    headers = {"Accept": "application/json"}
    if USER:
        headers["Digitraffic-User"] = USER
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps({"url": url, "headers": headers})))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer after 60s")
            time.sleep(0.2)
        calls.append((r["status"], round(time.time() - t0, 2), len(r["text"])))
        time.sleep(PAUSE)
        if attempt == 0 and r["status"] in (0, 500, 502, 503, 504):
            time.sleep(10)
            continue
        break
    if r["status"] == 429:
        raise RuntimeError(f"{url}: HTTP 429 (request limit); wait a minute before trying again")
    if r["status"] != 200:
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"])

def local(iso):                     # '2026-11-24T01:37:00.000Z' -> Helsinki time
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(HEL)

on_digitraffic_tab()
print(f"Digitraffic rail API, checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC "
      f"({datetime.now(HEL):%a %d %b %H:%M} in Helsinki); Digitraffic-User {'set' if USER else 'not set'}")

stations = call("/metadata/stations")
by_code = {s["stationShortCode"]: s for s in stations}
def find_station(q):
    """Short code (HKI) first, then the Finnish name, with or without ' asema' (station)."""
    if q.upper() in by_code:
        return by_code[q.upper()]
    hits = [s for s in stations if s["passengerTraffic"] and s["stationName"].lower() in (q.lower(), q.lower() + " asema")]
    if not hits:
        raise RuntimeError(f"no passenger station called {q!r} in /metadata/stations")
    return hits[0]
name = lambda code: by_code[code]["stationName"] if code in by_code else code

for q in STATIONS:
    st = find_station(q)
    code = st["stationShortCode"]
    trains = call(f"/live-trains/station/{code}", {
        "departing_trains": N, "arrived_trains": 0, "arriving_trains": 0, "departed_trains": 0,
        "include_nonstopping": "false", "train_categories": "Long-distance,Commuter"})
    rows = []
    for t in trains:
        tt = t["timeTableRows"]
        dep = [r for r in tt if r["stationShortCode"] == code and r["type"] == "DEPARTURE" and r["trainStopping"]]
        if not dep:                                   # this train only arrives here
            continue
        r = dep[0]
        last = tt[-1]["stationShortCode"]
        dest = name(last)
        if last == code:                              # Helsinki ring lines I and P start and end at HKI
            dest += " (ring via Lentoasema)" if any(x["stationShortCode"] == "LEN" for x in tt) else " (loop)"
        line = t["commuterLineID"] or ""
        label = f"{t['trainType']} {t['trainNumber']}" + (f" ({line})" if line else "")
        live = r.get("liveEstimateTime")
        if t["cancelled"] or r["cancelled"]:
            state = "CANCELLED" + (" (whole train)" if t["cancelled"] else " (this stop)")
        elif r.get("actualTime"):
            state = f"departed {local(r['actualTime']):%H:%M}"
        elif live:
            state = f"live estimate {r.get('differenceInMinutes', 0):+d} min"
        else:
            state = "no live estimate yet (timetable)"
        rows.append((local(live or r["scheduledTime"]), local(r["scheduledTime"]), local(live) if live else None,
                     r["commercialTrack"] or "-", label, dest, state))
    rows.sort(key=lambda x: x[0])                    # the API returns trains in train-number order, not by time
    print(f"\n{q!r} -> {code} {st['stationName']} ({st['latitude']:.4f}, {st['longitude']:.4f}); "
          f"{len(trains)} trains returned, {len(rows)} departing; Helsinki time:")
    print(f"  {'sched':<6} {'live':<6} track  {'train':<14} {'destination':<38} status")
    for _, sched, live, track, label, dest, state in rows:
        print(f"  {sched:%H:%M}  {(f'{live:%H:%M}' if live else '-'):<6} {track:<6} {label:<14} {dest:<38} {state}")

print(f"\n{len(calls)} API calls, statuses {sorted({s for s, _, _ in calls})}, "
      f"{min(t for _, t, _ in calls):.2f}-{max(t for _, t, _ in calls):.2f} s each")
print("Source: Fintraffic / digitraffic.fi, license CC 4.0 BY (https://creativecommons.org/licenses/by/4.0/). "
      "Changed: departures picked and sorted, times converted from UTC to Helsinki time, station codes replaced by names.")
```

Output (from the run on 2026-11-24, 00:00 UTC; the first run at 23:57 UTC gave the same departures and estimates):

```text
Digitraffic rail API, checked 2026-11-24 00:00 UTC (Tue 24 Nov 02:00 in Helsinki); Digitraffic-User set

'HKI' -> HKI Helsinki asema (60.1714, 24.9414); 10 trains returned, 10 departing; Helsinki time:
  sched  live   track  train          destination                            status
  03:37  -      4      HV 10101 (V)   Kerava asema                           no live estimate yet (timetable)
  04:18  -      19     HL 8601 (P)    Helsinki asema (ring via Lentoasema)   no live estimate yet (timetable)
  04:20  -      8      HL 9619 (R)    Riihimäki asema                        no live estimate yet (timetable)
  04:23  -      13     HV 10045 (V)   Kirkkonummi                            no live estimate yet (timetable)
  04:33  -      17     HL 8405 (L)    Kirkkonummi                            no live estimate yet (timetable)
  04:36  -      4      HL 8804 (I)    Helsinki asema (ring via Lentoasema)   no live estimate yet (timetable)
  04:41  -      3      HL 9005 (K)    Kerava asema                           no live estimate yet (timetable)
  04:48  -      18     HL 8605 (P)    Helsinki asema (ring via Lentoasema)   no live estimate yet (timetable)
  04:51  -      3      HL 8806 (I)    Helsinki asema (ring via Lentoasema)   no live estimate yet (timetable)
  05:01  -      3      HL 9013 (K)    Kerava asema                           no live estimate yet (timetable)

'Tampere' -> TPE Tampere asema (61.4982, 23.7735); 10 trains returned, 10 departing; Helsinki time:
  sched  live   track  train          destination                            status
  02:37  02:37  1      PYO 273        Rovaniemi                              live estimate +0 min
  03:45  03:45  1      PYO 266        Helsinki asema                         live estimate +0 min
  04:10  04:10  1      PYO 264        Helsinki asema                         live estimate +0 min
  05:04  -      3      IC 160         Helsinki asema                         no live estimate yet (timetable)
  05:30  -      3      HL 1705 (M)    Nokia                                  no live estimate yet (timetable)
  05:45  -      1      IC 162         Helsinki asema                         no live estimate yet (timetable)
  05:50  -      2      PYO 904        Turku satama                           no live estimate yet (timetable)
  06:00  -      5      IC 477         Pori                                   no live estimate yet (timetable)
  06:08  06:08  3      PYO 274        Helsinki asema                         live estimate +0 min
  06:22  -      1      IC 166         Helsinki asema                         no live estimate yet (timetable)

3 API calls, statuses [200], 0.70-1.46 s each
Source: Fintraffic / digitraffic.fi, license CC 4.0 BY (https://creativecommons.org/licenses/by/4.0/). Changed: departures picked and sorted, times converted from UTC to Helsinki time, station codes replaced by names.
```

### 2. robots.txt, the terms and instructions quotes, and what the API does with mistakes (browser)

5 page loads and 5 in-page `fetch()` calls in the same tab. robots.txt is read as page text and checked with `urllib.robotparser` for all 11 agents. The 406 for a missing gzip header cannot be shown here, because the browser always sends it; block 4 shows it.

```python
import json, os, time, urllib.robotparser

API = "https://rata.digitraffic.fi/api/v1"
USER = os.environ.get("DIGITRAFFIC_USER", "").strip()   # your own value (see block 1); empty = anonymous
if USER.lower() in {"junamies/foobarapp 1.0", "trainguy/foobarapp 1.0", "fintraffic", "liikennetilanne",
                    "fintraffic/liikennetilanne", "dt/tester"}:
    raise SystemExit("DIGITRAFFIC_USER is an example from Digitraffic's docs; use your own party/app name")
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]

START_JS = """(() => { window.__d = window.__d || {}; const id = String(Math.random()).slice(2); window.__d[id] = null;
  const a = %s;
  fetch(a.url, {headers: a.headers, credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__d[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__d[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__d[%s]; if (v) delete window.__d[%s]; return v; })()"""

def raw(url):
    """One in-page GET -> {status, headers, text}. No retries: this block only inspects answers."""
    h = {"Accept": "application/json"}
    if USER:
        h["Digitraffic-User"] = USER
    rid = json.dumps(js(START_JS % json.dumps({"url": url, "headers": h})))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1.0)
    return r

def page(url, wait_for=None):
    """Load a page and return (HTTP status, content type, final URL, flattened text); waits up to 15 s for a phrase."""
    goto_url(url)
    wait_for_load()
    t0 = time.time()
    while True:
        txt = js("(document.body || document.documentElement).innerText || ''") or ""
        if not wait_for or wait_for in " ".join(txt.split()) or time.time() - t0 > 15:
            break
        time.sleep(0.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.contentType"), js("location.href"), txt

# 1) robots.txt on the API host and the docs host, checked for every agent on the paths the skill uses
for host, paths in (("rata.digitraffic.fi", ["/api/v1/live-trains/station/HKI", "/api/v1/metadata/stations"]),
                    ("www.digitraffic.fi", ["/en/terms-of-service/", "/en/support/instructions/", "/en/railway-traffic/"])):
    st, ct, href, txt = page(f"https://{host}/robots.txt")
    if st == 200 and ct.startswith("text/plain"):
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(txt.splitlines())
        bad = [(a, p) for a in AGENTS for p in paths if not rp.can_fetch(a, f"https://{host}{p}")]
        named = [l for l in txt.splitlines() if l.lower().startswith("user-agent") and l.split(":", 1)[1].strip() != "*"]
        print(f"{host}/robots.txt HTTP {st} {ct}: {' / '.join(l for l in txt.splitlines() if l.strip())!r}; "
              f"named agent groups: {named or 'none'}; disallowed for the {len(AGENTS)} agents: {bad or 'none'}")
    else:
        print(f"{host}/robots.txt HTTP {st} {ct}: no robots rules (RFC 9309: 4xx = no restrictions); "
              f"text starts {' '.join(txt.split())[:40]!r}")

# 2) terms, instructions and the railway page, as a reader sees them
for url, needles in (
    ("https://www.digitraffic.fi/en/terms-of-service/", [
        "Fintraffic’s open data is licensed under the Creative Commons 4.0 By license.",
        "even commercially, as long as you credit the source for the original creation",
        "you must give appropriate credit, provide a link to the license, and indicate if changes were made",
        "If the material has beem modified, it must be accompanied with a notice describing the modification",
        "Source: Fintraffic / digitraffic.fi, license CC 4.0 BY"]),
    ("https://www.digitraffic.fi/en/support/instructions/", [
        "The Digitraffic-User header should include an identifiable user party and/or application.",
        "Using the header increases the amount of requests you can make.",
        "Don’t send any PII (personally identifiable information) via the headers!",
        "The use of compression is mandatory on all interfaces except for weather camera images.",
        "If compression is not allowed in the request, the service returns error code",
        "The restrictions listed in the table below are for request without the Digitraffic-User header.",
        "Most of the caches are one minute long."]),
    ("https://www.digitraffic.fi/en/railway-traffic/", [
        "Which trains are departing and arriving next from a specific station?",
        "Data is licensed under Creative Commons Attribution 4.0 International"]),
):
    st, ct, href, txt = page(url, wait_for=needles[0])
    flat = " ".join(txt.split())
    short = href.split("//")[1][:44]
    for n in needles:
        print(f"{short:<44} {'found' if n in flat else 'MISSING'}: {n[:80]!r}")
    if "instructions" in url:
        rows = js("[...document.querySelectorAll('table tr')].map(r => [...r.cells].map(c => c.innerText.trim()).join(' | '))")
        for row in rows:
            print(f"{'':<44} table: {row}")
    bad = [w for w in ("scrap", "crawl", "artificial intelligence", "machine learning", "non-commercial",
                       "noncommercial", "robot") if w in flat.lower()]
    print(f"{short:<44} words scrap/crawl/AI/ML/non-commercial/robot: {bad or 'none'}")

# 3) what the API does with mistakes and defaults (fetch from the docs page; the API sends CORS *)
def brief(r, n=110):
    return f"HTTP {r['status']} {r['headers'].get('content-type', '?')}: {' '.join(r['text'].split())[:n]}"
only_dep = "departing_trains=5&arrived_trains=0&arriving_trains=0&departed_trains=0"
print()
for label, url in (
    ("unknown station XYZ             ", f"{API}/live-trains/station/XYZ?{only_dep}"),
    ("lower-case hki                  ", f"{API}/live-trains/station/hki?{only_dep}"),
    ("departing_trains=abc            ", f"{API}/live-trains/station/HKI?departing_trains=abc"),
    ("unknown train category 'Night'  ", f"{API}/live-trains/station/HKI?{only_dep}&train_categories=Night"),
):
    print(f"{label} {brief(raw(url))}")

r = raw(f"{API}/live-trains/station/HKI")        # all defaults: 5 arrived, 5 arriving, 5 departed, 5 departing
d = json.loads(r["text"])
kinds = {}
for t in d:
    rows = [x for x in t["timeTableRows"] if x["stationShortCode"] == "HKI"]
    dep = [x for x in rows if x["type"] == "DEPARTURE"]
    k = ("no departure here (arriving only)" if not dep else
         "already departed" if dep[0].get("actualTime") else "still to depart")
    kinds.setdefault(k, []).append(f"{t['trainType']}{t['trainNumber']}/{t['trainCategory']}")
print(f"defaults (no query): {len(d)} trains; " + "; ".join(f"{k}: {len(v)}" for k, v in kinds.items()))
print(f"  categories: {sorted({t['trainCategory'] for t in d})}; first in the list: "
      f"{d[0]['trainType']} {d[0]['trainNumber']} (sorted by train number, not by time)")
print(f"headers visible to fetch(): {sorted(r['headers'])}")
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:32 UTC, in a new cloud browser; the 23:58 and 00:00 UTC runs printed the same lines):

```text
rata.digitraffic.fi/robots.txt HTTP 200 text/plain: 'User-agent: * / Allow: /'; named agent groups: none; disallowed for the 11 agents: none
www.digitraffic.fi/robots.txt HTTP 404 text/html: no robots rules (RFC 9309: 4xx = no restrictions); text starts '--- permalink: /404.html --- 404 - Page '
www.digitraffic.fi/en/terms-of-service/      found: 'Fintraffic’s open data is licensed under the Creative Commons 4.0 By license.'
www.digitraffic.fi/en/terms-of-service/      found: 'even commercially, as long as you credit the source for the original creation'
www.digitraffic.fi/en/terms-of-service/      found: 'you must give appropriate credit, provide a link to the license, and indicate if'
www.digitraffic.fi/en/terms-of-service/      found: 'If the material has beem modified, it must be accompanied with a notice describi'
www.digitraffic.fi/en/terms-of-service/      found: 'Source: Fintraffic / digitraffic.fi, license CC 4.0 BY'
www.digitraffic.fi/en/terms-of-service/      words scrap/crawl/AI/ML/non-commercial/robot: none
www.digitraffic.fi/en/support/instructions/  found: 'The Digitraffic-User header should include an identifiable user party and/or app'
www.digitraffic.fi/en/support/instructions/  found: 'Using the header increases the amount of requests you can make.'
www.digitraffic.fi/en/support/instructions/  found: 'Don’t send any PII (personally identifiable information) via the headers!'
www.digitraffic.fi/en/support/instructions/  found: 'The use of compression is mandatory on all interfaces except for weather camera '
www.digitraffic.fi/en/support/instructions/  found: 'If compression is not allowed in the request, the service returns error code'
www.digitraffic.fi/en/support/instructions/  found: 'The restrictions listed in the table below are for request without the Digitraff'
www.digitraffic.fi/en/support/instructions/  found: 'Most of the caches are one minute long.'
                                             table: Target / interface | Max requests / min | Key
                                             table: General restriction | 60 | IP
                                             table: MQTT | 5 | IP
                                             table: Weather camera images | 60 | IP
                                             table: tie/meri.digitraffic.fi V1-interfaces | 60 | IP
                                             table: infra- and jeti-api | 30 | IP
www.digitraffic.fi/en/support/instructions/  words scrap/crawl/AI/ML/non-commercial/robot: none
www.digitraffic.fi/en/railway-traffic/       found: 'Which trains are departing and arriving next from a specific station?'
www.digitraffic.fi/en/railway-traffic/       found: 'Data is licensed under Creative Commons Attribution 4.0 International'
www.digitraffic.fi/en/railway-traffic/       words scrap/crawl/AI/ML/non-commercial/robot: none

unknown station XYZ              HTTP 200 application/json: []
lower-case hki                   HTTP 200 application/json: [{"commuterLineID":"P","runningCurrently":false,"cancelled":false,"version":293816840701,"timetableType":"REGU
departing_trains=abc             HTTP 400 application/json: {"errorMessage":"Invalid format for parameter. Target type: Integer, parameter: abc","code":"PARAMETER_WRONG_T
unknown train category 'Night'   HTTP 400 application/json: {"errorMessage":"No recognized train categories given","code":"ILLEGAL_ARGUMENT_EXCEPTION","queryString":"depa
defaults (no query): 18 trains; still to depart: 5; already departed: 6; no departure here (arriving only): 7
  categories: ['Commuter', 'On-track machines', 'Shunting']; first in the list: HL 8601 (sorted by train number, not by time)
headers visible to fetch(): ['cache-control', 'content-type']
```

### 3. The same with Python urllib, as a command-line tool: robots check for every agent, departures, trains to a second station (no browser)

Standard library only. It runs with `python3 -I`. Save it as `digitraffic.py`. Each run makes 3 calls: robots.txt, the station list and the departures; with `--to`, up to 2 more when the category filter leaves fewer than `-n` trains (the limit grows 4x each time). `urllib` does not decompress, so `http()` sends `Accept-Encoding: gzip` and gunzips the body itself. `--to` uses the station-to-station endpoint and adds the arrival time there. On a 429 it waits 60 s once (the limits are per minute) and then stops; on 5xx it retries once after 10 s.

```python
"""Next train departures from a Finnish station, with live estimates, track and cancellations
(Digitraffic rail API, Python standard library only).

  export DIGITRAFFIC_USER='<your party>/<your app>'   # optional; raises your limit; no personal data
  python3 digitraffic.py HKI [-n 10] [--commuter | --long-distance]
  python3 digitraffic.py Helsinki --to Tampere [-n 5]
"""
import argparse, gzip, json, os, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

HOST = "https://rata.digitraffic.fi"
API = HOST + "/api/v1"
HEL = ZoneInfo("Europe/Helsinki")
USER = os.environ.get("DIGITRAFFIC_USER", "").strip()
DOC_EXAMPLES = {"junamies/foobarapp 1.0", "trainguy/foobarapp 1.0", "fintraffic", "liikennetilanne",
                "fintraffic/liikennetilanne", "dt/tester"}
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider", "digitraffic-skill-example"]  # last = this script's UA
UA = "digitraffic-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
CREDIT = "Source: Fintraffic / digitraffic.fi, license CC 4.0 BY (https://creativecommons.org/licenses/by/4.0/)"
if USER.lower() in DOC_EXAMPLES:
    sys.exit("DIGITRAFFIC_USER is an example from Digitraffic's docs; use your own party/app name")
calls = []
_last = [0.0]

def http(url):
    """-> (status, headers, text). Serial, at least 1 s apart. Sends Accept-Encoding: gzip (mandatory: HTTP 406
    without it) and gunzips the body itself, since urllib does not."""
    time.sleep(max(0.0, _last[0] + 1.0 - time.time()))
    h = {"Accept-Encoding": "gzip", "Accept": "application/json", "User-Agent": UA}
    if USER:
        h["Digitraffic-User"] = USER
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
            status, hdrs, body = r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        status, hdrs, body = e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
    except (urllib.error.URLError, TimeoutError) as e:
        status, hdrs, body = 0, {}, str(e).encode()
    _last[0] = time.time()
    size = len(body)
    if hdrs.get("content-encoding") == "gzip":
        body = gzip.decompress(body)
    calls.append((url[len(HOST):].split("?")[0], status, round(time.time() - t0, 2), size, len(body)))
    return status, hdrs, body.decode("utf-8", errors="replace")

def call(path, params=None):
    """-> parsed JSON. Checks the exact path against robots.txt first. 429: wait 60 s once (the limits are per minute), then stop. 5xx or network error: one retry
    after 10 s. 406 means the gzip header was lost. Any other non-200 stops."""
    url = API + path + ("?" + urlencode(params) if params else "")
    bad = [a for a in AGENTS if RP and not RP.can_fetch(a, url)]
    if bad:
        sys.exit(f"robots.txt disallows {path} for {bad}: stop")
    for attempt in range(2):
        s, h, text = http(url)
        if attempt == 0 and s in (0, 429, 500, 502, 503, 504):
            time.sleep(60 if s == 429 else 10)
            continue
        break
    if s != 200:
        sys.exit(f"{url}: HTTP {s} {' '.join(text.split())[:200]!r}")
    return json.loads(text)

RP = None   # parsed robots.txt; call() checks every request path against it

def robots_load():
    """rata.digitraffic.fi/robots.txt is 'User-agent: * / Allow: /' today. A 4xx other than 429 = no rules;
    429, 5xx or no answer = rules unknown, so stop."""
    global RP
    s, _, text = http(HOST + "/robots.txt")
    if 400 <= s < 500 and s != 429:
        print(f"robots.txt rata.digitraffic.fi: HTTP {s}, no rules")
        return
    if s != 200:
        sys.exit(f"robots.txt: HTTP {s}; rules unknown, try later")
    RP = urllib.robotparser.RobotFileParser()
    RP.parse(text.splitlines())
    print(f"robots.txt rata.digitraffic.fi: HTTP 200; each API path is checked for all {len(AGENTS)} agents before its call")

def local(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(HEL)

ap = argparse.ArgumentParser()
ap.add_argument("station", help="short code (HKI) or Finnish station name (Helsinki, Tampere, Pasila)")
ap.add_argument("--to", help="only trains that stop at this station later (code or name)")
ap.add_argument("-n", type=int, default=10)
g = ap.add_mutually_exclusive_group()
g.add_argument("--commuter", action="store_true")
g.add_argument("--long-distance", action="store_true")
args = ap.parse_args()
if args.n < 1:
    ap.error("-n must be 1 or more")

print(f"Digitraffic rail, checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC; "
      f"Digitraffic-User {'set' if USER else 'not set (anonymous: 60 requests a minute)'}")
robots_load()
stations = call("/metadata/stations")
by_code = {s["stationShortCode"]: s for s in stations}

def station(q):
    if q.upper() in by_code:
        return by_code[q.upper()]
    hits = [s for s in stations if s["passengerTraffic"] and s["stationName"].lower() in (q.lower(), q.lower() + " asema")]
    if not hits:
        near = [s["stationName"] for s in stations if s["passengerTraffic"] and s["stationName"].lower().startswith(q.lower()[:4])]
        sys.exit(f"no passenger station {q!r}; similar names: {near[:8]}")
    return hits[0]

frm = station(args.station)
code = frm["stationShortCode"]
cats = "Commuter" if args.commuter else "Long-distance" if args.long_distance else "Long-distance,Commuter"

def pick(trains):
    """-> one row per train in the chosen categories that stops to depart at `code`."""
    rows = []
    for t in trains:
        row = departure(t)
        if row:
            rows.append(row)
    return rows

def departure(t):
    tt = t["timeTableRows"]
    if t["trainCategory"] not in cats.split(","):
        return None
    i = next((k for k, r in enumerate(tt) if r["stationShortCode"] == code and r["type"] == "DEPARTURE"
              and r["trainStopping"]), None)
    if i is None:
        return None
    r = tt[i]
    last = tt[-1]["stationShortCode"]
    dest = by_code.get(last, {}).get("stationName", last)
    if last == code:
        dest += " (ring via Lentoasema)" if any(x["stationShortCode"] == "LEN" for x in tt) else " (loop)"
    arr = ""
    if to:
        a = next((x for x in tt[i:] if x["stationShortCode"] == to["stationShortCode"] and x["type"] == "ARRIVAL"), None)
        arr = f"{local(a.get('liveEstimateTime') or a['scheduledTime']):%H:%M}" if a else "?"
    live = r.get("liveEstimateTime")
    if t["cancelled"] or r["cancelled"]:
        status = "CANCELLED" + ("" if t["cancelled"] else " at this stop")
    elif r.get("actualTime"):
        status = f"departed {local(r['actualTime']):%H:%M}"
    elif live:
        status = f"live {r.get('differenceInMinutes', 0):+d} min"
    else:
        status = "timetable"
    train = f"{t['trainType']} {t['trainNumber']}" + (f" {t['commuterLineID']}" if t["commuterLineID"] else "")
    return (local(live or r["scheduledTime"]), local(r["scheduledTime"]), live and local(live),
            r["commercialTrack"] or "-", train, dest, arr, status, t["operatorShortCode"])

note = ""
if args.to:
    to = station(args.to)
    # limit counts every train, other categories too. Ask for 20 spares; if the category filter leaves fewer
    # than -n and the API filled the whole limit, ask again with 4x the limit (at most 3 calls in all)
    path, limit = f"/live-trains/station/{quote(code)}/{quote(to['stationShortCode'])}", args.n + 20
    for ask in range(3):
        trains = call(path, {"limit": limit})
        rows = pick(trains)
        if len(rows) >= args.n or len(trains) < limit:
            break
        if ask < 2:
            limit *= 4
    if len(rows) < args.n:
        note = (f" (only {len(rows)} {cats} trains among the {len(trains)} the API returned"
                + (")" if len(trains) < limit else f"; stopped after 3 calls at limit={limit})"))
    title = f"{code} {frm['stationName']} -> {to['stationShortCode']} {to['stationName']}"
else:
    to = None
    trains = call(f"/live-trains/station/{quote(code)}", {
        "departing_trains": args.n, "arrived_trains": 0, "arriving_trains": 0, "departed_trains": 0,
        "include_nonstopping": "false", "train_categories": cats})
    rows = pick(trains)
    title = f"{code} {frm['stationName']} ({cats})"

rows.sort(key=lambda x: x[0])
rows = rows[:args.n]

print(f"{title}: next {len(rows)} departures, Helsinki time{note}")
print(f"  {'day':<4}{'sched':<6} {'est':<6} {'track':<6}{'train':<14}{'destination':<38}" + ("arr   " if to else "") + "status")
for _, s, e, track, train, dest, arr, status, op in rows:
    print(f"  {s:%a} {s:%H:%M}  {(f'{e:%H:%M}' if e else '-'):<6} {track:<6}{train:<14}{dest:<38}"
          + (f"{arr:<6}" if to else "") + status)
print(f"{len(calls)} calls: " + ", ".join(f"{p} {s} {t}s {z / 1024:.1f} KB" for p, s, t, z, _ in calls))
print(CREDIT + "; departures picked, sorted and converted to Helsinki time by this script.")
```

Output (five commands, re-run on 2026-11-24 after the code-review fixes, 00:30 UTC; the `Pasila` run had `DIGITRAFFIC_USER` empty, so it was anonymous, and the last one was refused before any call; the 00:00 UTC runs listed the same trains). With `--to` the block asks for 20 spare trains, filters categories, then keeps `-n`: `Helsinki --to Tampere --commuter -n 3` gave HL 9621, HL 9635 and HL 9649, where `limit=3` (checked at 00:36 UTC) returns IC 35, HL 9621 and IC 21, only one of them a commuter train. If the filter still leaves fewer than `-n` and the API filled the limit, it asks again with 4x the limit: at 01:44 UTC `Helsinki --to Tampere --commuter -n 8` got 6 of 8 from `limit=28`, then all 8 from `limit=112` (4 calls; the version before this change printed 6). When the API runs out first, the header says so, e.g. `(only 10 Commuter trains among the 42 the API returned)` for `-n 25`:

```text
$ python3 -I digitraffic.py HKI
Digitraffic rail, checked 2026-11-24 00:30 UTC; Digitraffic-User set
robots.txt rata.digitraffic.fi: HTTP 200; each API path is checked for all 12 agents before its call
HKI Helsinki asema (Long-distance,Commuter): next 10 departures, Helsinki time
  day sched  est    track train         destination                           status
  Tue 03:37  -      4     HV 10101 V    Kerava asema                          timetable
  Tue 04:18  -      19    HL 8601 P     Helsinki asema (ring via Lentoasema)  timetable
  Tue 04:20  -      8     HL 9619 R     Riihimäki asema                       timetable
  Tue 04:23  -      13    HV 10045 V    Kirkkonummi                           timetable
  Tue 04:33  -      17    HL 8405 L     Kirkkonummi                           timetable
  Tue 04:36  -      4     HL 8804 I     Helsinki asema (ring via Lentoasema)  timetable
  Tue 04:41  -      3     HL 9005 K     Kerava asema                          timetable
  Tue 04:48  -      18    HL 8605 P     Helsinki asema (ring via Lentoasema)  timetable
  Tue 04:51  -      3     HL 8806 I     Helsinki asema (ring via Lentoasema)  timetable
  Tue 05:01  -      3     HL 9013 K     Kerava asema                          timetable
3 calls: /robots.txt 200 0.07s 0.0 KB, /api/v1/metadata/stations 200 0.24s 14.7 KB, /api/v1/live-trains/station/HKI 200 0.29s 4.3 KB
Source: Fintraffic / digitraffic.fi, license CC 4.0 BY (https://creativecommons.org/licenses/by/4.0/); departures picked, sorted and converted to Helsinki time by this script.

$ python3 -I digitraffic.py Helsinki --to Tampere -n 5
Digitraffic rail, checked 2026-11-24 00:30 UTC; Digitraffic-User set
robots.txt rata.digitraffic.fi: HTTP 200; each API path is checked for all 12 agents before its call
HKI Helsinki asema -> TPE Tampere asema: next 5 departures, Helsinki time
  day sched  est    track train         destination                           arr   status
  Tue 05:03  -      9     IC 35         Rovaniemi                             06:53 timetable
  Tue 05:10  -      8     HL 9621 R     Tampere asema                         07:35 timetable
  Tue 06:20  -      8     IC 21         Oulu asema                            07:58 timetable
  Tue 07:00  -      9     IC 155        Pieksämäki asema                      08:53 timetable
  Tue 07:10  -      10    HL 9635 R     Tampere asema                         09:25 timetable
3 calls: /robots.txt 200 0.06s 0.0 KB, /api/v1/metadata/stations 200 0.09s 14.7 KB, /api/v1/live-trains/station/HKI/TPE 200 0.46s 31.0 KB
Source: Fintraffic / digitraffic.fi, license CC 4.0 BY (https://creativecommons.org/licenses/by/4.0/); departures picked, sorted and converted to Helsinki time by this script.

$ python3 -I digitraffic.py Tamper
Digitraffic rail, checked 2026-11-24 00:30 UTC; Digitraffic-User set
robots.txt rata.digitraffic.fi: HTTP 200; each API path is checked for all 12 agents before its call
no passenger station 'Tamper'; similar names: ['Tampere asema']

$ DIGITRAFFIC_USER= python3 -I digitraffic.py Pasila --long-distance -n 4
Digitraffic rail, checked 2026-11-24 00:30 UTC; Digitraffic-User not set (anonymous: 60 requests a minute)
robots.txt rata.digitraffic.fi: HTTP 200; each API path is checked for all 12 agents before its call
PSL Pasila asema (Long-distance): next 4 departures, Helsinki time
  day sched  est    track train         destination                           status
  Tue 05:09  -      3     IC 35         Rovaniemi                             timetable
  Tue 05:32  -      8     IC 941        Turku satama                          timetable
  Tue 06:00  -      4     S 61          Kuopio asema                          timetable
  Tue 06:21  06:21  6     PYO 266       Helsinki asema                        live +0 min
3 calls: /robots.txt 200 0.06s 0.0 KB, /api/v1/metadata/stations 200 0.1s 14.7 KB, /api/v1/live-trains/station/PSL 200 0.37s 7.9 KB
Source: Fintraffic / digitraffic.fi, license CC 4.0 BY (https://creativecommons.org/licenses/by/4.0/); departures picked, sorted and converted to Helsinki time by this script.

$ DIGITRAFFIC_USER="Junamies/FoobarApp 1.0" python3 -I digitraffic.py HKI
DIGITRAFFIC_USER is an example from Digitraffic's docs; use your own party/app name
```

### 4. curl: station codes, departures, the 406 without gzip, headers, mistakes

```bash
#!/usr/bin/env bash
# Optional: export DIGITRAFFIC_USER='<your party>/<your app>' (no personal data); it raises your request limit.
set -euo pipefail
case "${DIGITRAFFIC_USER:-}" in
  "Junamies/FoobarApp 1.0"|"Trainguy/FoobarApp 1.0"|Fintraffic|Liikennetilanne|Fintraffic/Liikennetilanne|DT/Tester)
    echo "DIGITRAFFIC_USER is an example from Digitraffic's docs; use your own party/app name" >&2; exit 1;;
esac
C=(curl -sS --max-time 30 --compressed)           # --compressed sends Accept-Encoding: gzip (mandatory) and unzips
[ -n "${DIGITRAFFIC_USER:-}" ] && C+=(-H "Digitraffic-User: $DIGITRAFFIC_USER")
R=https://rata.digitraffic.fi/api/v1
T=$(mktemp)
# 0. robots.txt on the API host first: a 4xx other than 429 = no rules; stop if it disallows the API paths
code=$(curl -sS --max-time 30 -o "$T" -w '%{http_code}' https://rata.digitraffic.fi/robots.txt)
echo "robots.txt HTTP $code: $(tr '\n' ' ' < "$T")"
python3 -c 'import sys, urllib.robotparser
code, text = int(sys.argv[1]), open(sys.argv[2]).read()
if code != 200 and not (400 <= code < 500 and code != 429): sys.exit("robots.txt rules unknown: stop")
rp = urllib.robotparser.RobotFileParser(); rp.parse(text.splitlines() if code == 200 else [])
paths = ("/api/v1/metadata/stations", "/api/v1/live-trains/station/HKI")
if not all(rp.can_fetch(a, "https://rata.digitraffic.fi" + p) for a in ("*", "curl") for p in paths): sys.exit("robots.txt disallows the API: stop")
print("robots: API paths allowed")' "$code" "$T"
sleep 1
# 1. station names -> short codes (Finnish names; "asema" = station)
"${C[@]}" --fail "$R/metadata/stations" | python3 -c 'import json, sys
s = json.load(sys.stdin); print(len(s), "stations,", sum(x["passengerTraffic"] for x in s), "with passenger traffic")
for x in s:
    if x["stationShortCode"] in ("HKI", "PSL", "LEN", "TPE", "TKU"):
        print(x["stationShortCode"], "|", x["stationName"], "|", x["latitude"], x["longitude"])'
sleep 1
# 2. next 8 passenger departures from Helsinki (HKI): scheduled vs live time, track, destination, cancellations
"${C[@]}" --fail "$R/live-trains/station/HKI?departing_trains=8&arrived_trains=0&arriving_trains=0&departed_trains=0&include_nonstopping=false&train_categories=Long-distance,Commuter" \
  | python3 -c 'import json, sys
from datetime import datetime
from zoneinfo import ZoneInfo
loc = lambda z: datetime.fromisoformat(z.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Helsinki")).strftime("%H:%M")
out = []
for t in json.load(sys.stdin):
    for r in t["timeTableRows"]:
        if r["stationShortCode"] == "HKI" and r["type"] == "DEPARTURE":
            out.append((r.get("liveEstimateTime") or r["scheduledTime"], loc(r["scheduledTime"]),
                        loc(r["liveEstimateTime"]) if "liveEstimateTime" in r else "-", r["commercialTrack"],
                        t["trainType"] + str(t["trainNumber"]) + (" " + t["commuterLineID"] if t["commuterLineID"] else ""),
                        t["timeTableRows"][-1]["stationShortCode"], "CANCELLED" if t["cancelled"] or r["cancelled"] else "ok"))
for o in sorted(out):
    print("sched", o[1], "est", o[2], "track", o[3], o[4], "->", o[5], o[6])'
sleep 1
# 3. gzip is mandatory: the same request without Accept-Encoding
curl -sS --max-time 30 -o "$T" -w 'no gzip: HTTP %{http_code} ' "$R/live-trains/station/HKI?departing_trains=1"; cat "$T"; echo
sleep 1
# 4. response headers: short public cache, CORS open, no rate-limit headers
"${C[@]}" -D - -o /dev/null "$R/live-trains/station/HKI?departing_trains=1&arrived_trains=0&arriving_trains=0&departed_trains=0" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|content-encoding|cache-control|access-control-allow-origin|retry-after|x-ratelimit[a-z-]*|ratelimit[a-z-]*):)'
sleep 1
# 5. mistakes: an unknown station is an empty list (HTTP 200), a bad number is HTTP 400 JSON
for q in "XYZ?departing_trains=3" "HKI?departing_trains=abc"; do
  "${C[@]}" -o "$T" -w "$q: HTTP %{http_code} " "$R/live-trains/station/$q"; head -c 120 "$T"; echo; sleep 1
done
rm -f "$T"
echo "Source: Fintraffic / digitraffic.fi, license CC 4.0 BY (https://creativecommons.org/licenses/by/4.0/). Accessed $(date -u '+%d %B %Y %H:%M') UTC. Changed: fields picked, times converted from UTC to Helsinki time."
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:30 UTC; robots.txt is now read first; the rest matches the 23:59 and 00:00 UTC runs apart from the access time):

```text
robots.txt HTTP 200: User-agent: * Allow: /
robots: API paths allowed
563 stations, 215 with passenger traffic
HKI | Helsinki asema | 60.171356 24.941444
LEN | Lentoasema | 60.315732 24.968343
PSL | Pasila asema | 60.198689 24.933521
TPE | Tampere asema | 61.498236 23.773454
TKU | Turku asema | 60.456488 22.260867
sched 03:37 est - track 4 HV10101 V -> KE ok
sched 04:18 est - track 19 HL8601 P -> HKI ok
sched 04:20 est - track 8 HL9619 R -> RI ok
sched 04:23 est - track 13 HV10045 V -> KKN ok
sched 04:33 est - track 17 HL8405 L -> KKN ok
sched 04:36 est - track 4 HL8804 I -> HKI ok
sched 04:41 est - track 3 HL9005 K -> KE ok
sched 04:48 est - track 18 HL8605 P -> HKI ok
no gzip: HTTP 406 Use of gzip compression is required with Accept-Encoding: gzip header.
HTTP/2 200
content-type: application/json
content-encoding: gzip
access-control-allow-origin: *
cache-control: max-age=30, public
XYZ?departing_trains=3: HTTP 200 []
HKI?departing_trains=abc: HTTP 400 {"errorMessage":"Invalid format for parameter. Target type: Integer, parameter: abc","code":"PARAMETER_WRONG_TYPE","quer
Source: Fintraffic / digitraffic.fi, license CC 4.0 BY (https://creativecommons.org/licenses/by/4.0/). Accessed 24 November 2026 00:30 UTC. Changed: fields picked, times converted from UTC to Helsinki time.
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `/metadata/stations[]` | `stationShortCode` (`HKI`), `stationName` (`Helsinki asema`), `stationUICCode` (`1`), `latitude`, `longitude`, `passengerTraffic`, `type`, `countryCode` | 563 entries on 2026-11-23: 456 `STATION`, 64 `STOPPING_POINT`, 43 `TURNOUT_IN_THE_OPEN_LINE`. Names are Finnish ("asema" = station; some have no suffix, such as `Kirkkonummi`, `Lentoasema`). There is no search endpoint: match names yourself |
| train | `trainNumber`, `departureDate` (`2026-11-24`), `trainType` (`IC`, `HL`, `HV`, `PYO`, `S`, ...), `trainCategory`, `commuterLineID` (`P`, `I`, `K`, ... or `""`), `operatorShortCode` (`vr` for 1,753 of 1,792 trains on 2026-11-23), `runningCurrently`, `cancelled`, `timetableType` (`REGULAR`, `ADHOC`), `version` | `trainCategory` values from `/metadata/train-categories`: Long-distance, Commuter, Cargo, Locomotive, Test drive, On-track machines, Shunting |
| `timeTableRows[]` | `stationShortCode`, `type` (`ARRIVAL` / `DEPARTURE`), `scheduledTime`, `liveEstimateTime`, `differenceInMinutes`, `actualTime`, `commercialTrack` (`"19"`), `cancelled`, `trainStopping`, `commercialStop`, `estimateSource` (`LIIKE_AUTOMATIC`, `LIIKE_USER`), `unknownDelay`, `causes[]`, `stopSector` | one row per arrival and per departure at every point on the route, including pass-through points (`trainStopping: false`). Times are UTC with milliseconds. `actualTime` appears once the train has left |
| `causes[]` | `{categoryCode: "M", detailedCategoryCode: "M1", ...}` | delay cause codes; names in `/metadata/cause-category-codes` (not used here) |
| response headers | `content-type: application/json`, `content-encoding: gzip`, `cache-control: max-age=30, public`, `access-control-allow-origin: *` | no rate-limit headers. A browser `fetch()` sees `cache-control` and `content-type` |
| errors | `{"errorMessage": "...", "code": "PARAMETER_WRONG_TYPE" / "ILLEGAL_ARGUMENT_EXCEPTION", "queryString": "..."}` | HTTP 400. HTTP 406 without gzip is plain text: "Use of gzip compression is required with Accept-Encoding: gzip header." |

## Gotchas

- **gzip or HTTP 406.** "The use of compression is mandatory on all interfaces except for weather camera images." Without `Accept-Encoding: gzip` the answer is HTTP 406 with a 70-byte text body. `curl --compressed` and browsers send it; Python `urllib` does not, and does not unzip either (block 3 does both).
- **Default counts mix arrivals and past trains.** `departing_trains`, `departed_trains`, `arriving_trains` and `arrived_trains` all default to 5 (OpenAPI document). Set the three you do not want to 0. The `minutes_before_departure`-style parameters only filter when "all time limit parameters" are set (OpenAPI description); this skill uses counts instead.
- **Filter the rows yourself.** `timeTableRows` lists every stop of the whole route (42 rows for one Kirkkonummi commuter train). Take `stationShortCode == <yours>` and `type == "DEPARTURE"`. A train can be in the list and still have no departure at your station (it ends there).
- **Times are UTC, docs elsewhere say Finnish time.** The REST answers end in `Z`. Helsinki is UTC+2 in winter and UTC+3 in summer. The SIRI feed on the same host is different: its docs say "Times are in Finnish time."
- **No live estimate until the train has started its run.** `liveEstimateTime` and `differenceInMinutes` appear once the train is running (`runningCurrently: true`), even hours before your station: at 02:06 in Helsinki (verifier, 00:06 UTC), all 4 running night trains on the Tampere board had one (PYO 274 four hours before its 06:08 Tampere departure), while none of the 16 not yet started trains on the HKI and Tampere boards did. In the whole day of 2026-11-23 (1,792 trains, read at 23:56 UTC) 4,285 of 73,080 rows had a `liveEstimateTime`; past rows have `actualTime` instead. Show `scheduledTime` with "timetable" when it is missing.
- **Cancellations sit on the train and on each row.** `cancelled: true` on the train means the whole run is cancelled; `cancelled: true` on a row means that stop only. On 2026-11-23, 98 trains were cancelled in full and 27 in part, and the only two cancelled HKI departures were shunting moves (`SAA 60068`, `W 64491`), which `train_categories=Long-distance,Commuter` removes. A cancelled train stays in the list; check both flags, as blocks 1 and 3 do.
- **Ring lines end where they start.** Commuter lines I and P leave HKI, run via the airport (`LEN`, Lentoasema) and come back to HKI, so the last row says HKI. Blocks 1 and 3 print "Helsinki asema (ring via Lentoasema)".
- **Unknown station = empty list.** `/live-trains/station/XYZ` is HTTP 200 `[]`, not an error. Look the code up in `/metadata/stations` first. Lower-case `hki` also worked.
- **The station-to-station summary is reversed.** The OpenAPI summary for `/live-trains/station/{departure_station}/{arrival_station}` reads "Return trains that run from {arrival_station} to {departure_station}", but `/HKI/TPE` returned trains from Helsinki to Tampere (IC 35 at 05:03, arriving 06:53).
- **Caching.** `cache-control: max-age=30, public` behind CloudFront; the instructions say most caches last a minute. Polling more often wastes your limit.
- **Digitraffic-User without personal data.** The instructions ask for a party and/or app name and say not to send names or email addresses. To be contacted about heavy use, they ask you to sign up at https://www.digitraffic.fi/en/sign-up-your-application/ (not done here).
- **Credit and no logo.** Show "Source: Fintraffic / digitraffic.fi, license CC 4.0 BY" with a link to https://creativecommons.org/licenses/by/4.0/ and say what you changed (sorting, time zone, names). Use no Fintraffic logo and do not suggest Fintraffic endorses your app.
- **Tab marker.** The harness sets the tab title to a horse emoji. The blocks check `location.origin` and the page text, not the title.

## What does not work

- **Requests without `Accept-Encoding: gzip`**: HTTP 406.
- **A station search by name on the API**: there is none; filter `/metadata/stations`.
- **`/api/v1/swagger.json`**: HTTP 404. The OpenAPI document is at `/swagger/openapi.json`; `/swagger/rata-api.json` is HTTP 403.
- **Not tested:** a 429 (never provoked; the limits above are from the instructions page), the GraphQL endpoint, the SIRI, GTFS and NeTEx feeds, MQTT, train compositions, passenger-information messages, `minutes_before_departure`-style time filters, summer time (UTC+3) answers and a daytime board with live delays at HKI.
