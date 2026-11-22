# SMHI Open Data - Get the Next 48 Hours of Hourly Temperature, Wind and Precipitation for a Swedish Town by Coordinates, Plus the Active SMHI Weather Warnings That Cover It (Point Forecast, Observations and Impact-Based Warnings JSON APIs, no key)

Field-tested against SMHI's open-data APIs on 2026-11-21 (US Pacific afternoon; 23:26-23:57 UTC) using a fresh Browser Use cloud browser (logged out; one session, 23:26-23:38 UTC) plus Python `urllib` and `curl` from a Linux machine. 44 browser page loads (19 while reading the docs site, 12 in each of block 2's two runs, 1 in block 1's first run) and 34 in-page `fetch()` calls (blocks 1 and 2 ran twice each), 47 curl calls (30 while exploring, 12 in block 4, 5 polls of `createdtime.json` five minutes apart) and 35 urllib calls (block 3 ran 5 times: twice with an empty cache, twice warm, once with its forecast entry expired by hand), all serial and at least 1 s apart. Every call was HTTP 200 except the deliberate probes below: HTTP 404 (robots.txt on all four opendata hosts, a point outside the forecast area, a coordinate with 7 decimals, the retired `pmp3g/version/2` forecast, a closed station's latest hour), HTTP 304 (conditional GETs on the warnings list) and eight in-browser `fetch()` calls (four in each block 2 run) that CORS blocked. curl timed 27 answers at 0.51-1.00 s. No 429, no challenge, no key, no login, no cookie. Block 1's output below is its second run (23:36 UTC), block 2's its second (23:37 UTC, after relabelling four probes), block 3's its fourth (empty cache, after a caching fix) and fifth (warm), block 4's its first. An independent verifier re-ran all four blocks verbatim on 2026-11-21 23:58 to 2026-11-22 00:06 UTC (a second fresh cloud browser, urllib, curl): every block ran; only the forecast run (created 23:49:46), its numbers and the Varnish error IDs changed. After review on 2026-11-22, the blocks gained small fixes (a closing source line in blocks 2 and 4, an exact 48-step check, a guard for an hour with no CORE reading, a fixed tie-break) and re-ran at 00:59-01:02 UTC (a new cloud browser, urllib, curl); the source lines in the outputs of blocks 2 and 4 come from those runs, and nothing else changed except the live forecast. A second review (in the browser-use.com sync) made blocks 1 and 3 skip `parameter.json`'s `missingValue` 9999 (shown as `-`, `n/a` or an empty CSV cell, with a count of hours without a value; a missing precipitation type does not count toward "mostly") and say in every source line what was changed; block 1 re-ran at 01:57 UTC in a new cloud browser and block 3 at 01:53 UTC (urllib), the same output apart from the live forecast, and the source lines in the outputs of blocks 1 and 3 now read as those runs printed them. With 9999 put into some hours by hand, both printed the gaps instead of 9999 (block 1's missing-precipitation-type fix, made after its browser run, was checked at 02:02 UTC with the same code and live forecasts fetched by urllib, not in a browser).

robots.txt (checked 2026-11-21, curl, the cloud browser and block 3): https://opendata-download-metfcst.smhi.se/robots.txt, https://opendata-download-metobs.smhi.se/robots.txt and https://opendata-download-warnings.smhi.se/robots.txt answer HTTP 404 (a Varnish error page), and https://opendata.smhi.se/robots.txt (the docs site) HTTP 404 too. RFC 9309 treats an unavailable (4xx) robots.txt as no restrictions, so every agent, including GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider, may fetch every path this skill uses (block 3 checks all 11 agents on every path on every run and stops if a host ever publishes rules that disallow one). https://www.smhi.se/robots.txt (the terms page's host) has only a `User-agent: *` group, which disallows image, bookmark and cart actions, printable pages, contact, state, session, profiling, PDF-properties and preview query URLs plus `/funktioner/*` and `/dokumentation/*`, not `/data/om-smhis-data/villkor-for-anvandning`; there are no named AI-agent groups on any SMHI host checked. Terms: "Villkor för användning av SMHIs öppna data" https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning ("Uppdaterad 15 juni 2026"; the API docs say the API "is published under these Terms and conditions") say "Med våra öppna data följer licensvillkoren Creative commons Erkännande 4.0 SE" (Creative Commons Attribution 4.0 SE) and "Detta är tillåtet även för kommersiella ändamål. Du ska ange SMHI som källa och även ange om du har ändrat i licensmaterialet." (commercial use is allowed; name SMHI as the source and say if you changed the material). For impact-based warnings: "Användningen är även tillåten för kommersiella ändamål. Informationen får inte ändras och källan till informationen skall alltid anges." (commercial use allowed; the information must not be changed and the source must always be given). Usage rules on the same page: "Du ska endast använda dokumenterade API:er." (use only documented APIs), "Undvik t.ex. massnedladdning där man hämtar prognosdata för ett stort antal orter vid ett och samma tillfälle. Undvik även att hämta samma data fler gånger." (avoid mass downloads such as forecasts for many places at once, and avoid fetching the same data more than once), "Utnyttja möjligheten till tidsbegränsad cachning av data enligt våra metadata och eventuella klient-cache-direktiv." (use time-limited caching according to SMHI's metadata and cache directives) and "SMHI förbehåller sig rätten att blockera enskilda IP-adresser alternativt helt stänga av tjänster vid uppenbart missbruk." (SMHI may block IP addresses on obvious abuse). No AI/ML, scraping, crawling, robot or non-commercial wording on the page (block 2 checks the quotes and scans for the words). Services the docs mark as keyed and charged are out of scope; every endpoint here is keyless. Naming: this skill writes "SMHI" (Sveriges meteorologiska och hydrologiska institut, Swedish Meteorological and Hydrological Institute) in plain text and shows no SMHI logo; it is not affiliated with or endorsed by SMHI. Every block's output names SMHI as the source and says what was changed; warning text is printed exactly as SMHI publishes it.

## Quick summary

- **No scraping needed.** `GET https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1/geotype/point/lon/{lon}/lat/{lat}/data.json` -> `{"createdTime", "referenceTime", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "timeSeries": [{"time", "intervalParametersStartTime", "data": {"air_temperature": 1.6, "wind_speed": 6.1, "wind_speed_of_gust": 12.6, "precipitation_amount_mean": 0.5, ...}}, ...]}`: 84 steps, about 10 days, 70 KB with all 24 parameters (4.8 KB gzip); `?parameters=a,b,c` and `?timeseries=n` cut it down. Warnings for all of Sweden: `GET https://opendata-download-warnings.smhi.se/ibww/api/version/1/warning.json` (140 KB, 41 KB gzip), each warning area with a GeoJSON polygon; test "is my point inside" yourself. Latest observations: `opendata-download-metobs.smhi.se/api/version/1.0/parameter/{p}/station-set/all/period/latest-hour/data.json` (every station, one call). JSON, `Access-Control-Allow-Origin: *`, no key. The old `pmp3g/version/2` forecast is retired (HTTP 404).
- **Answers (block 1, 21 November 2026, 23:36 UTC, forecast created 23:20 UTC):** **Stockholm** 0.4 to 2.5 C, wind up to 9.4 m/s with gusts to 17.7 m/s, 17.5 mm in 44 of the next 48 hours (rain and wet snow, snow on the night to Monday); **Uppsala** -0.4 to 1.7 C, 25.5 mm, mostly snow; **Göteborg** -2.4 to 2.0 C, dry; **Kiruna** -9.1 to -4.0 C, dry. SMHI warnings: a **yellow warning for snow and wind, "Parts of eastern Svealand"**, 21 Nov 22:00 to 23 Nov 15:00 UTC, covers Stockholm and Uppsala; **"Risk for water shortage - Groundwater" messages** cover Uppsala län and Västra Götalands län (Göteborg) until further notice; nothing covers Kiruna.
- **Hourly for about 2.5 days, then 3, 6 and 12 h steps.** The 23:00 UTC run was hourly to 24 Nov 12:00 UTC (61 steps), then coarser, to 2 Dec 00:00. Precipitation is the total since `intervalParametersStartTime`, so a 12-hour step holds 12 hours of rain. All times are UTC; the blocks check that every step inside 48 hours is one hour long.
- **"For that area" means point in polygon.** `warning.json` lists every warning area in the country (21 today, county areas for water shortage, a drawn area for the snow warning, sea districts for wind at sea); `affectedAreas` names counties, not towns. Blocks 1 and 3 test the town's coordinates against each area's Polygon/MultiPolygon and keep areas that overlap the next 48 hours (`approximateEnd` missing = continues indefinitely).
- **Load and cache rules come from the terms, not a rate limit.** No number is published and no rate-limit headers were seen. The forecast and `createdtime.json` say `Cache-Control: max-age=3600`; latest-hour observations `max-age=600`; the warnings list has an `ETag` (HTTP 304 on repeat). Block 3 reuses a fresh copy without a call, asks `createdtime.json` (77 bytes) before downloading a stale forecast again, and sends `If-None-Match` for warnings. One town at a time, serial, 1 s apart; no grid-wide downloads.

## What works

### 1. Towns by coordinates -> next 48 hours, hourly, plus the SMHI warnings whose area contains each town (browser)

`on_docs_tab()` opens the logged-out "Get Point Forecast" docs page on opendata.smhi.se and `fetch()` calls the API hosts cross-origin (they send `Access-Control-Allow-Origin: *`). `get()` returns parsed JSON on HTTP 200, waits once on 429/5xx or a network error and otherwise raises. The polygon test runs inside the page, so only the matching warning areas come back, not 140 KB of polygons. 1 `fetch()` for the warnings and 1 per town: 5 in all. One town gets the full hourly table; the others get 6-hour digests of the same hourly rows.

```python
import email.utils, json, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TOWNS = [("Stockholm", 59.3293, 18.0686), ("Uppsala", 59.8586, 17.6389),
         ("Göteborg", 57.7089, 11.9746), ("Kiruna", 67.8558, 20.2253)]  # (name, lat, lon) WGS84, town centres
HOURS = 48
HOURLY_FOR = "Stockholm"  # print every hour for this town; 6-hour digests for the others
DOCS = "https://opendata.smhi.se/metfcst/snow1gv1/get_point_forecast"
FCST = "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1"
WARN = "https://opendata-download-warnings.smhi.se/ibww/api/version/1/warning.json"
PARAMS = ["air_temperature", "wind_speed", "wind_speed_of_gust", "wind_from_direction", "precipitation_amount_mean",
          "probability_of_precipitation", "predominant_precipitation_type_at_surface", "symbol_code"]
PTYPE = {0: "-", 1: "rain", 2: "thunderstorm", 3: "freezing rain", 4: "mixed/ice", 5: "snow", 6: "wet snow",
         7: "rain and snow", 8: "ice pellets", 9: "graupel", 10: "hail", 11: "drizzle", 12: "freezing drizzle"}
PAUSE = 1.0  # SMHI: no unnecessary load, no mass downloads; one town at a time, serial
LOCAL = ZoneInfo("Europe/Stockholm")
MISSING = 9999  # parameter.json: missingValue of every snow1g parameter (no value for that hour)

def on_docs_tab():
    """fetch() from a logged-out SMHI open-data docs page (the API hosts send Access-Control-Allow-Origin: *)."""
    try:
        if js("location.href").startswith(DOCS) and "Get Point Forecast" in js("document.body.innerText"):
            return
    except Exception:
        pass
    new_tab(DOCS)
    wait_for_load()
    for _ in range(20):  # the docs site renders in the browser
        if "intervalParametersStartTime" in (js("document.body ? document.body.innerText : ''") or ""):
            return
        time.sleep(0.5)
    raise RuntimeError(f"SMHI docs page did not render (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll. `pick` runs in the page on the parsed JSON,
# so only what is needed comes back (warning.json is ~140 KB, mostly polygons).
START_JS = """(() => { window.__s = window.__s || {}; const id = String(Math.random()).slice(2); window.__s[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { let text = await r.text();
      if (r.ok && %s) text = JSON.stringify((%s)(JSON.parse(text)));
      window.__s[id] = {status: r.status, type: r.headers.get('content-type') || '', retry: r.headers.get('retry-after'),
                        age: r.headers.get('age'), text}; })
    .catch(e => { window.__s[id] = {status: 0, type: '', retry: null, age: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__s[%s]; if (v) delete window.__s[%s]; return v; })()"""
# warning areas whose GeoJSON polygon contains a town (ray casting, lon/lat), without the polygons themselves
PICK_WARN = """(ws => { const pts = %s;
  const inRing = (x, y, r) => { let c = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const [xi, yi] = r[i], [xj, yj] = r[j];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
  const inPoly = (x, y, p) => inRing(x, y, p[0]) && !p.slice(1).some(h => inRing(x, y, h));
  const inGeom = (x, y, g) => g.type === 'Polygon' ? inPoly(x, y, g.coordinates)
      : g.type === 'MultiPolygon' ? g.coordinates.some(p => inPoly(x, y, p)) : null;
  const out = [];
  for (const w of ws) for (const a of w.warningAreas) {
    const g = a.area && (a.area.geometry || a.area);
    const hits = pts.map(([lon, lat], i) => g && inGeom(lon, lat, g) ? i : -1).filter(i => i >= 0);
    const unknown = !g || inGeom(0, 0, g) === null;
    if (hits.length || unknown) { const {area, ...rest} = a;
      out.push({id: w.id, event: w.event, descriptions: w.descriptions || [], area: rest, hits, unknown}); } }
  return {count: ws.length, areas: ws.reduce((n, w) => n + w.warningAreas.length, 0), out}; })"""

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def get(url, pick=None):
    """-> parsed JSON on HTTP 200. Waits once on 429/5xx or a network error (Retry-After, else 30 s; over 120 s
    stops). Raises on anything else (404 = retired API, a bad coordinate or out of the forecast area)."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % (json.dumps(url), "true" if pick else "false", pick or "null")))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer after 60s")
            time.sleep(0.2)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = retry_wait(r["retry"], 30)
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] != 200 or "json" not in r["type"]:
        raise RuntimeError(f"{url}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"])

def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def mostly(wet):
    kinds = [PTYPE.get(x["predominant_precipitation_type_at_surface"], "?") for x in wet
             if x["predominant_precipitation_type_at_surface"] != MISSING]   # a missing type does not vote
    return max(dict.fromkeys(kinds), key=kinds.count) if kinds else "-"   # ties: the type seen first

def compass(deg):
    return "-" if deg == MISSING else ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][round(deg / 45) % 8]

def agg(rows, key, fn):
    """fn over the hours that have a value ('n/a' when none has); missingValue 9999 is never a temperature."""
    v = [x[key] for x in rows if x[key] != MISSING]
    return format(fn(v), ".1f") if v else "n/a"

def cell(v, width, spec=""):
    return f"{'-':>{width}}" if v == MISSING else f"{v:>{width}{spec}}"

on_docs_tab()
now = datetime.now(timezone.utc)
end = now + timedelta(hours=HOURS)
print(f"SMHI open data, checked {now:%Y-%m-%d %H:%M} UTC; window {now:%d %b %H:%M} to {end:%d %b %H:%M} UTC")

warn = get(WARN, PICK_WARN % json.dumps([[round(lon, 6), round(lat, 6)] for _, lat, lon in TOWNS]))
for name, lat, lon in TOWNS:
    url = f"{FCST}/geotype/point/lon/{round(lon, 6)}/lat/{round(lat, 6)}/data.json?parameters={','.join(PARAMS)}"
    f = get(url)  # ~70 KB with all 24 parameters, less with parameters=
    glon, glat = f["geometry"]["coordinates"]
    rows = [t for t in f["timeSeries"] if now < utc(t["time"]) <= end]
    steps = {(utc(t["time"]) - utc(t["intervalParametersStartTime"])).seconds // 3600 for t in rows}
    if steps != {1} or len(rows) != HOURS:  # the forecast is hourly for ~2.5 days, then 3, 6 and 12 h steps
        raise RuntimeError(f"{name}: {len(rows)} steps of {sorted(steps)} h inside {HOURS} h, not {HOURS} hourly ones; stopping")
    d = [t["data"] for t in rows]
    wet = [x for x in d if 0 < x["precipitation_amount_mean"] != MISSING]
    gaps = {k: n for k in PARAMS if (n := sum(x.get(k) == MISSING for x in d))}
    print(f"\n{name} ({lat}, {lon}) -> grid point ({glat}, {glon}); forecast created {f['createdTime']}, "
          f"{len(rows)} hourly steps {rows[0]['time'][5:16]} to {rows[-1]['time'][5:16]} UTC")
    print(f"  temperature {agg(d, 'air_temperature', min)} to {agg(d, 'air_temperature', max)} C; wind up to "
          f"{agg(d, 'wind_speed', max)} m/s, gusts {agg(d, 'wind_speed_of_gust', max)} m/s; precipitation "
          f"{agg(d, 'precipitation_amount_mean', sum)} mm (ensemble mean) in {len(wet)} wet hours, mostly {mostly(wet)}"
          + (f"; hours without a value (9999, skipped): {gaps}" if gaps else ""))
    if name == HOURLY_FOR:
        print(f"  {'UTC':<11} {'local':<5} {'temp':>5} {'wind':>9} {'gust':>5} {'mm':>4} {'P%':>4}  type")
        for t, x in zip(rows, d):
            print(f"  {t['time'][5:16].replace('T', ' ')} {utc(t['time']).astimezone(LOCAL):%H:%M} {cell(x['air_temperature'], 5, '.1f')} "
                  f"{compass(x['wind_from_direction']):>2} {cell(x['wind_speed'], 4, '.1f')}  {cell(x['wind_speed_of_gust'], 5, '.1f')} "
                  f"{cell(x['precipitation_amount_mean'], 4, '.1f')} {cell(x['probability_of_precipitation'], 4)}  "
                  f"{'n/a' if x['predominant_precipitation_type_at_surface'] == MISSING else PTYPE.get(x['predominant_precipitation_type_at_surface'], '?')}")
    else:
        for i in range(0, len(rows), 6):
            b = d[i:i + 6]
            print(f"  {rows[i]['time'][5:13].replace('T', ' ')}h+6: {agg(b, 'air_temperature', min):>5} to "
                  f"{agg(b, 'air_temperature', max):>5} C, wind <= {agg(b, 'wind_speed', max):>4} m/s "
                  f"(gust {agg(b, 'wind_speed_of_gust', max):>4}), {agg(b, 'precipitation_amount_mean', sum):>4} mm")

print(f"\nSMHI warnings: {warn['count']} warnings, {warn['areas']} warning areas in all; areas containing a town:")
active = 0
for w in warn["out"]:
    a = w["area"]
    if w["unknown"]:
        print(f"  warning {w['id']}: area without a Polygon/MultiPolygon, check by hand: {a.get('areaName')}")
        continue
    start, stop = utc(a["approximateStart"]), utc(a["approximateEnd"]) if a.get("approximateEnd") else None
    if start > end or (stop and stop <= now):
        continue  # not active in the window
    active += 1
    towns = ", ".join(TOWNS[i][0] for i in w["hits"])
    print(f"  [{towns}] {a['warningLevel']['en']} ({a['warningLevel']['code']}): {a['eventDescription']['en']} "
          f"[{w['event']['code']}]; area {a.get('areaName', {}).get('en') or a.get('areaName', {}).get('sv')}; "
          f"from {a['approximateStart']} to {a.get('approximateEnd') or 'further notice'}; published {a['published']}"
          + ("" if a["normalProbability"] else "; LOWER PROBABILITY"))
    for desc in w.get("descriptions", []) + a.get("descriptions", []):  # SMHI's text, printed as published
        print(f"      {desc['title']['en']}: {desc['text'].get('en') or desc['text'].get('sv')}")
none = [t[0] for i, t in enumerate(TOWNS) if not any(i in w["hits"] for w in warn["out"])]
print(f"  {active} active warning areas; no warning area covers: {', '.join(none) or '-'}")
print(f"\nSource: SMHI (Swedish Meteorological and Hydrological Institute) open data, CC BY 4.0 SE, accessed "
      f"{now:%d %B %Y %H:%M} UTC. Changes: forecast cut to {HOURS} hourly steps and {len(PARAMS)} parameters, summed "
      f"and rounded, missing values (9999) skipped, local time added. Warnings: SMHI's own English text, unaltered.")
```

Output (from the second run on 2026-11-21, 23:36 UTC; the forecast run is the 23:20 one from the first run at 23:31, see Gotchas on the browser cache):

```text
SMHI open data, checked 2026-11-21 23:36 UTC; window 21 Nov 23:36 to 23 Nov 23:36 UTC

Stockholm (59.3293, 18.0686) -> grid point (59.33036, 18.077207); forecast created 2026-11-21T23:20:14Z, 48 hourly steps 11-22T00:00 to 11-23T23:00 UTC
  temperature 0.4 to 2.5 C; wind up to 9.4 m/s, gusts 17.7 m/s; precipitation 17.5 mm (ensemble mean) in 44 wet hours, mostly rain
  UTC         local  temp      wind  gust   mm   P%  type
  11-22 00:00 01:00   1.6  N  6.1   12.6  0.5  100  rain
  11-22 01:00 02:00   1.6 NW  6.6   14.1  0.8  100  rain
  11-22 02:00 03:00   1.7  N  8.8   16.1  0.8  100  rain
  11-22 03:00 04:00   1.7  N  9.0   16.8  0.7  100  wet snow
  11-22 04:00 05:00   1.7  N  8.9   16.9  0.6  100  rain
  11-22 05:00 06:00   1.8  N  8.1   16.3  0.6  100  rain
  11-22 06:00 07:00   1.7  N  8.0   14.9  0.6  100  rain
  11-22 07:00 08:00   1.3  N  5.0   14.5  0.6  100  wet snow
  11-22 08:00 09:00   1.6  N  8.2   15.0  0.7  100  wet snow
  11-22 09:00 10:00   1.6  N  8.9   16.3  0.6  100  wet snow
  11-22 10:00 11:00   1.6  N  9.1   16.7  0.5  100  wet snow
  11-22 11:00 12:00   1.6  N  9.2   16.8  0.5  100  wet snow
  11-22 12:00 13:00   1.6  N  9.3   17.5  0.4  100  rain
  11-22 13:00 14:00   1.6  N  9.4   17.4  0.4  100  wet snow
  11-22 14:00 15:00   1.6  N  9.1   17.7  0.5  100  wet snow
  11-22 15:00 16:00   1.6  N  8.4   17.0  0.4  100  wet snow
  11-22 16:00 17:00   1.7  N  8.0   15.6  0.5  100  rain
  11-22 17:00 18:00   1.9  N  8.9   16.5  0.5   93  rain
  11-22 18:00 19:00   1.6  N  7.5   16.2  0.5   93  rain
  11-22 19:00 20:00   1.6  N  8.0   14.5  0.5   93  rain
  11-22 20:00 21:00   1.5  N  7.7   16.6  0.3   83  rain
  11-22 21:00 22:00   1.6  N  9.2   16.9  0.3   70  rain
  11-22 22:00 23:00   1.5  N  8.0   16.9  0.3   73  wet snow
  11-22 23:00 00:00   1.5  N  8.0   15.2  0.2   50  rain
  11-23 00:00 01:00   1.4  N  7.7   14.7  0.2   63  snow
  11-23 01:00 02:00   1.4  N  8.3   15.2  0.3   67  snow
  11-23 02:00 03:00   1.4  N  8.1   15.7  0.2   67  snow
  11-23 03:00 04:00   1.3  N  7.7   15.0  0.3   73  snow
  11-23 04:00 05:00   1.2  N  7.3   14.0  0.3   80  snow
  11-23 05:00 06:00   0.6 NW  6.0   13.5  0.4   93  snow
  11-23 06:00 07:00   0.4 NW  7.0   13.3  0.4   93  snow
  11-23 07:00 08:00   0.4 NW  6.3   13.4  0.4   93  snow
  11-23 08:00 09:00   0.6 NW  6.0   12.6  0.4   93  snow
  11-23 09:00 10:00   0.9 NW  5.1   11.3  0.3  100  snow
  11-23 10:00 11:00   1.2  N  4.9    9.6  0.3   93  snow
  11-23 11:00 12:00   1.7  N  4.8    9.2  0.3   90  wet snow
  11-23 12:00 13:00   2.2  N  5.4    9.9  0.3   93  rain
  11-23 13:00 14:00   1.9  N  5.2    9.7  0.3   97  rain
  11-23 14:00 15:00   1.9  N  5.1   10.4  0.2   63  rain
  11-23 15:00 16:00   1.9  N  5.2    9.5  0.2   73  rain
  11-23 16:00 17:00   1.9  N  5.2    9.4  0.1   57  rain
  11-23 17:00 18:00   2.3  N  6.9   12.9  0.1   60  rain
  11-23 18:00 19:00   2.4  N  6.9   12.9  0.1   47  rain
  11-23 19:00 20:00   2.5  N  7.2   13.1  0.1   33  rain
  11-23 20:00 21:00   2.4  N  7.2   13.4  0.0   20  rain
  11-23 21:00 22:00   2.4  N  7.4   13.5  0.0   13  rain
  11-23 22:00 23:00   2.4  N  7.1   13.5  0.0   10  rain
  11-23 23:00 00:00   2.2  N  6.6   12.9  0.0   13  rain

Uppsala (59.8586, 17.6389) -> grid point (59.85689, 17.635448); forecast created 2026-11-21T23:20:14Z, 48 hourly steps 11-22T00:00 to 11-23T23:00 UTC
  temperature -0.4 to 1.7 C; wind up to 10.5 m/s, gusts 18.9 m/s; precipitation 25.5 mm (ensemble mean) in 48 wet hours, mostly snow
  11-22 00h+6:   0.8 to   1.1 C, wind <=  9.3 m/s (gust 16.6),  5.0 mm
  11-22 06h+6:   0.6 to   1.1 C, wind <= 10.1 m/s (gust 18.1),  3.6 mm
  11-22 12h+6:   0.7 to   1.2 C, wind <= 10.5 m/s (gust 18.9),  3.6 mm
  11-22 18h+6:   0.5 to   1.3 C, wind <= 10.1 m/s (gust 17.8),  1.4 mm
  11-23 00h+6:  -0.4 to   0.5 C, wind <=  9.6 m/s (gust 16.9),  2.4 mm
  11-23 06h+6:  -0.3 to   1.1 C, wind <=  7.9 m/s (gust 14.4),  5.5 mm
  11-23 12h+6:   1.1 to   1.5 C, wind <=  8.2 m/s (gust 14.7),  2.9 mm
  11-23 18h+6:   1.0 to   1.7 C, wind <=  7.7 m/s (gust 14.1),  1.1 mm

Göteborg (57.7089, 11.9746) -> grid point (57.71662, 11.979698); forecast created 2026-11-21T23:20:14Z, 48 hourly steps 11-22T00:00 to 11-23T23:00 UTC
  temperature -2.4 to 2.0 C; wind up to 5.4 m/s, gusts 9.3 m/s; precipitation 0.0 mm (ensemble mean) in 0 wet hours, mostly -
  11-22 00h+6:  -0.5 to   0.3 C, wind <=  3.9 m/s (gust  6.5),  0.0 mm
  11-22 06h+6:  -0.8 to   1.7 C, wind <=  5.1 m/s (gust  8.7),  0.0 mm
  11-22 12h+6:  -0.2 to   2.0 C, wind <=  5.4 m/s (gust  9.3),  0.0 mm
  11-22 18h+6:  -1.1 to  -0.4 C, wind <=  5.2 m/s (gust  8.7),  0.0 mm
  11-23 00h+6:  -2.2 to  -1.2 C, wind <=  4.7 m/s (gust  8.7),  0.0 mm
  11-23 06h+6:  -2.4 to   0.2 C, wind <=  4.4 m/s (gust  7.9),  0.0 mm
  11-23 12h+6:  -0.8 to   0.3 C, wind <=  5.2 m/s (gust  8.9),  0.0 mm
  11-23 18h+6:  -1.7 to  -0.3 C, wind <=  4.8 m/s (gust  8.7),  0.0 mm

Kiruna (67.8558, 20.2253) -> grid point (67.845071, 20.231692); forecast created 2026-11-21T23:20:14Z, 48 hourly steps 11-22T00:00 to 11-23T23:00 UTC
  temperature -9.1 to -4.0 C; wind up to 7.0 m/s, gusts 11.6 m/s; precipitation 0.0 mm (ensemble mean) in 0 wet hours, mostly -
  11-22 00h+6:  -5.8 to  -4.0 C, wind <=  7.0 m/s (gust 11.6),  0.0 mm
  11-22 06h+6:  -5.2 to  -4.5 C, wind <=  4.5 m/s (gust  8.9),  0.0 mm
  11-22 12h+6:  -5.8 to  -4.8 C, wind <=  5.6 m/s (gust  9.5),  0.0 mm
  11-22 18h+6:  -6.4 to  -5.7 C, wind <=  4.2 m/s (gust  8.0),  0.0 mm
  11-23 00h+6:  -5.4 to  -4.5 C, wind <=  3.4 m/s (gust  5.7),  0.0 mm
  11-23 06h+6:  -6.2 to  -5.6 C, wind <=  3.9 m/s (gust  6.2),  0.0 mm
  11-23 12h+6:  -9.1 to  -6.4 C, wind <=  3.6 m/s (gust  6.0),  0.0 mm
  11-23 18h+6:  -8.7 to  -7.3 C, wind <=  3.8 m/s (gust  5.7),  0.0 mm

SMHI warnings: 11 warnings, 21 warning areas in all; areas containing a town:
  [Göteborg] Message (MESSAGE): Risk for water shortage - Groundwater [WATER_SHORTAGE]; area Västra Götalands län; from 2026-05-25T22:00:00.000Z to further notice; published 2026-11-03T10:05:20.015Z
      Description of incident: Low groundwater levels.
      What should I think about?: Users of municipal water should be aware that the municipality may impose restrictions and encourage water-saving measures.
Low water levels may have a negative impact on plant and animal life in agriculture and in nature.
Those receiving water from private or shared wells should be considerate of their water consumption, as low groundwater levels may reduce abstraction capacity and deteriorate water quality.
  [Uppsala] Message (MESSAGE): Risk for water shortage - Groundwater [WATER_SHORTAGE]; area Uppsala län; from 2026-07-06T22:00:00.000Z to further notice; published 2026-10-12T15:11:29.334Z
      Description of incident: Low groundwater levels.
      What should I think about?: Users of municipal water should be aware that the municipality may impose restrictions and encourage water-saving measures.
Those receiving water from private or shared wells should be considerate of their water consumption, as low groundwater levels may reduce abstraction capacity and deteriorate water quality.
Low water levels may have a negative impact on plant and animal life in agriculture and in nature.
  [Stockholm, Uppsala] Yellow (YELLOW): Snow and wind [SNOW]; area Parts of eastern Svealand; from 2026-11-21T22:00:00.469Z to 2026-11-23T15:00:00.801Z; published 2026-11-21T18:27:47.698Z
      What happens?: From night to Sunday, snowfall is expected, which can be heavy at times. This is in combination with fresh northerly winds with strong or very strong gusts on the coast. The snowfall is expected to temporarily subside during Sunday afternoon and evening, and then start up again during the night to Monday. Until Monday afternoon, 5-15 cm of fresh snow is expected. Most of the snow is expected in the northern part. Along the coast, it will probably be mostly rain. The temperature will stay around zero degrees.
      Description of incident: From night to Sunday snowfall combined with wind that may cause traffic difficulties.
      What should I think about?: Travel times may increase due to drifting snow, slippery roads, poor visibility and blowing snow behind vehicles. Allow more time for your journey and adjust your speed to road conditions and visibility.
It can be difficult to travel due to snow on roads, traffic accidents or vehicles that are stuck.
There is a risk of delays or cancelled departures in public transport.
At temperatures close to zero degrees, there is a risk of disturbances in electricity and telecommunications networks in areas with overhead lines.
      Comments: Local variations are expected to be large and it is also uncertain how much rain there will be in the precipitation, which means that the snow amounts are also uncertain.
      Where?: Parts of eastern Svealand
  3 active warning areas; no warning area covers: Kiruna

Source: SMHI (Swedish Meteorological and Hydrological Institute) open data, CC BY 4.0 SE, accessed 21 November 2026 23:36 UTC. Changes: forecast cut to 48 hourly steps and 8 parameters, summed and rounded, missing values (9999) skipped, local time added. Warnings: SMHI's own English text, unaltered.
```

### 2. robots.txt, the terms quotes, the docs quotes, and what the APIs do with mistakes (browser)

12 page loads (5 robots.txt files, the terms page, 5 docs pages, back to the start page) and 12 in-page `fetch()` calls in the same tab. The docs site renders in the browser, so `page()` waits for a phrase before reading it.

```python
import json, re, time

FCST = "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1"
OBS = "https://opendata-download-metobs.smhi.se/api/version/1.0"
WARN = "https://opendata-download-warnings.smhi.se/ibww"
DOCS = "https://opendata.smhi.se"
TERMS = "https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning"

START_JS = """(() => { window.__s = window.__s || {}; const id = String(Math.random()).slice(2); window.__s[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__s[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__s[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__s[%s]; if (v) delete window.__s[%s]; return v; })()"""

def raw(url):
    """One in-page GET, no retries: inspection only. 1 s after each call."""
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1)
    return r

def page(url, wait_for=None):
    """Load a page; the docs site renders in the browser, so wait for a phrase."""
    goto_url(url)
    wait_for_load()
    for _ in range(20):
        txt = js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""
        if not wait_for or wait_for in txt:
            break
        time.sleep(0.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, " ".join(txt.replace("’", "'").split())

for host in ("opendata-download-metfcst.smhi.se", "opendata-download-metobs.smhi.se",
             "opendata-download-warnings.smhi.se", "opendata.smhi.se", "www.smhi.se"):
    st, txt = page(f"https://{host}/robots.txt")
    agents = sorted(set(re.findall(r"(?i)user-agent:\s*(\S+)", txt)))
    print(f"robots.txt {host:<35} HTTP {st}: user-agent groups {agents or 'none'}; {txt[:70]!r}")

st, txt = page(TERMS, "Villkor för data")
for needle in ("Uppdaterad 15 juni 2026",
               "Med våra öppna data följer licensvillkoren Creative commons Erkännande 4.0 SE.",
               "Detta är tillåtet även för kommersiella ändamål. Du ska ange SMHI som källa och även ange om du har ändrat i licensmaterialet.",
               "Användningen är även tillåten för kommersiella ändamål. Informationen får inte ändras och källan till informationen skall alltid anges.",
               "Du ska endast använda dokumenterade API:er.",
               "Undvik t.ex. massnedladdning där man hämtar prognosdata för ett stort antal orter vid ett och samma tillfälle. Undvik även att hämta samma data fler gånger.",
               "Utnyttja möjligheten till tidsbegränsad cachning av data enligt våra metadata och eventuella klient-cache-direktiv.",
               "SMHI förbehåller sig rätten att blockera enskilda IP-adresser alternativt helt stänga av tjänster vid uppenbart missbruk."):
    print(f"terms HTTP {st}: {'found' if needle in txt else 'MISSING'}: {needle[:100]!r}")
words = r"skrap|scrap|crawl|robot|\bAI\b|artificiell|maskininlärning|machine learning|icke-kommersiell|non-commercial"
print(f"terms page words /{words}/: {sorted(set(re.findall(words, txt, re.I))) or 'none'}")

for path, needles in (
    ("/metfcst/snow1gv1/get_point_forecast", ["At the beginning of the forecast, the interval is one hour. Later in the forecast, the time interval increases (eg 3, 6 and 12 h)."]),
    ("/metfcst/snow1gv1/parameters", ["If there is no precipitation, the value of the precipitation_frozen_part parameter will be -9.",
                                      "Maximum total precipitation amount of ensemble members with non-zero precipitation."]),
    ("/metfcst/snow1gv1/geographic_area", ["If the point is outside of the valid are, you will get a HTTP 400 - FIELD POINT OUT OF BOUNDS.",
                                           "up to six decimal places. Otherwise the API will return HTTP 404 - Not found."]),
    ("/warnings/objects", ["If this is missing, it means that the warning area continues indefinitely."]),
    ("/metobs/common", ["only use data returned in combination with the HTTP status code 200"]),
):
    st, txt = page(DOCS + path, needles[0][:30])
    for needle in needles:
        print(f"docs {path:<38} {'found' if needle in txt else 'MISSING'}: {needle[:90]!r}")
print()

def brief(r):
    out = f"HTTP {r['status']} {r['type'].split(';')[0] or '-'} {len(r['text']):,} chars"
    if "json" not in r["type"] or r["status"] != 200:
        return out + f" {' '.join(r['text'].split())[:60]!r}"
    d = json.loads(r["text"])
    if isinstance(d, list):
        return out + f" list of {len(d)}"
    if "timeSeries" in d:
        return out + f" {len(d['timeSeries'])} steps, grid point {d['geometry']['coordinates']}, first {d['timeSeries'][0]['data']}"
    if d.get("type") == "Polygon":
        xs, ys = zip(*d["coordinates"][0])
        return out + f" Polygon, lon {min(xs):.2f}..{max(xs):.2f}, lat {min(ys):.2f}..{max(ys):.2f}"
    if "parameter" in d and isinstance(d["parameter"], list):
        return out + f" {len(d['parameter'])} parameters, missingValue {sorted({p['missingValue'] for p in d['parameter']})}"
    if "station" in d and isinstance(d["station"], list):
        return out + f" {len(d['station'])} stations, {sum(1 for s in d['station'] if s.get('value'))} with a value"
    if "value" in d:
        return out + f" station {d['station']['name']!r}, value {d['value']}"
    return out + " " + json.dumps(d, ensure_ascii=False)[:110]

page(DOCS + "/metfcst/snow1gv1/get_point_forecast", "Get Point Forecast")  # fetch() from a docs page
for label, url in (
    ("created time                    ", f"{FCST}/createdtime.json"),
    ("parameters                      ", f"{FCST}/parameter.json"),
    ("forecast area polygon           ", f"{FCST}/geotype/polygon.json"),
    ("point, timeseries=1, 2 params   ", f"{FCST}/geotype/point/lon/16.158/lat/58.5812/data.json?timeseries=1&parameters=air_temperature,wind_speed"),
    ("point, lon/lat swapped          ", f"{FCST}/geotype/point/lon/59.3293/lat/18.0686/data.json"),
    ("point, 7 decimals (404, no CORS)", f"{FCST}/geotype/point/lon/18.0686123/lat/59.3293/data.json"),
    ("old pmp3g v2 (404, no CORS)     ", "https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/18.0686/lat/59.3293/data.json"),
    ("warnings entry point (no CORS)  ", f"{WARN}/api/version/1.json"),
    ("warnings test set 2 (no CORS)   ", f"{WARN}/test/test_2.json"),
    ("obs: temperature, all stations  ", f"{OBS}/parameter/1/station-set/all/period/latest-hour/data.json"),
    ("obs: Stockholm temperature      ", f"{OBS}/parameter/1/station/98230/period/latest-hour/data.json"),
    ("obs: closed station, latest hour", f"{OBS}/parameter/1/station/154860/period/latest-hour/data.json"),
):
    print(f"{label} {brief(raw(url))}")  # status 0 = the browser blocked an answer without Access-Control-Allow-Origin
print("\nSource: SMHI open data (CC BY 4.0 SE); answers shortened to the fields shown.")
```

Output (from the second run, 2026-11-21 23:37 UTC; the first run at 23:32 printed the same apart from four probe labels):

```text
robots.txt opendata-download-metfcst.smhi.se   HTTP 404: user-agent groups none; 'Error 404 Not Found Not Found Guru Meditation: XID: 4939184664 Varnish'
robots.txt opendata-download-metobs.smhi.se    HTTP 404: user-agent groups none; 'Error 404 Not Found Not Found Guru Meditation: XID: 5058240175 Varnish'
robots.txt opendata-download-warnings.smhi.se  HTTP 404: user-agent groups none; 'Error 404 Not Found Not Found Guru Meditation: XID: 5042387949 Varnish'
robots.txt opendata.smhi.se                    HTTP 404: user-agent groups none; 'Not Found The requested URL was not found on this server.'
robots.txt www.smhi.se                         HTTP 200: user-agent groups ['*']; 'User-agent: * Disallow: /imagedescription.action2 Disallow: /checkouti'
terms HTTP 200: found: 'Uppdaterad 15 juni 2026'
terms HTTP 200: found: 'Med våra öppna data följer licensvillkoren Creative commons Erkännande 4.0 SE.'
terms HTTP 200: found: 'Detta är tillåtet även för kommersiella ändamål. Du ska ange SMHI som källa och även ange om du har '
terms HTTP 200: found: 'Användningen är även tillåten för kommersiella ändamål. Informationen får inte ändras och källan til'
terms HTTP 200: found: 'Du ska endast använda dokumenterade API:er.'
terms HTTP 200: found: 'Undvik t.ex. massnedladdning där man hämtar prognosdata för ett stort antal orter vid ett och samma '
terms HTTP 200: found: 'Utnyttja möjligheten till tidsbegränsad cachning av data enligt våra metadata och eventuella klient-'
terms HTTP 200: found: 'SMHI förbehåller sig rätten att blockera enskilda IP-adresser alternativt helt stänga av tjänster vi'
terms page words /skrap|scrap|crawl|robot|\bAI\b|artificiell|maskininlärning|machine learning|icke-kommersiell|non-commercial/: none
docs /metfcst/snow1gv1/get_point_forecast   found: 'At the beginning of the forecast, the interval is one hour. Later in the forecast, the tim'
docs /metfcst/snow1gv1/parameters           found: 'If there is no precipitation, the value of the precipitation_frozen_part parameter will be'
docs /metfcst/snow1gv1/parameters           found: 'Maximum total precipitation amount of ensemble members with non-zero precipitation.'
docs /metfcst/snow1gv1/geographic_area      found: 'If the point is outside of the valid are, you will get a HTTP 400 - FIELD POINT OUT OF BOU'
docs /metfcst/snow1gv1/geographic_area      found: 'up to six decimal places. Otherwise the API will return HTTP 404 - Not found.'
docs /warnings/objects                      found: 'If this is missing, it means that the warning area continues indefinitely.'
docs /metobs/common                         found: 'only use data returned in combination with the HTTP status code 200'

created time                     HTTP 200 application/json 77 chars {"createdTime": "2026-11-21T23:20:14Z", "referenceTime": "2026-11-21T23:00:00Z"}
parameters                       HTTP 200 application/json 4,027 chars 24 parameters, missingValue [9999]
forecast area polygon            HTTP 200 application/json 88,728 chars Polygon, lon -18.12..54.24, lat 49.77..75.23
point, timeseries=1, 2 params    HTTP 200 application/json 290 chars 1 steps, grid point [16.158549, 58.577821], first {'air_temperature': 1.0, 'wind_speed': 6.4}
point, lon/lat swapped           HTTP 404 text/plain 32 chars 'Requested point is out of bounds'
point, 7 decimals (404, no CORS) HTTP 0 - 26 chars 'TypeError: Failed to fetch'
old pmp3g v2 (404, no CORS)      HTTP 0 - 26 chars 'TypeError: Failed to fetch'
warnings entry point (no CORS)   HTTP 0 - 26 chars 'TypeError: Failed to fetch'
warnings test set 2 (no CORS)    HTTP 0 - 26 chars 'TypeError: Failed to fetch'
obs: temperature, all stations   HTTP 200 application/json 60,208 chars 233 stations, 184 with a value
obs: Stockholm temperature       HTTP 200 application/json 1,506 chars station 'Stockholm-Observatoriekullen A', value [{'date': 1795302000000, 'value': '1.2', 'quality': 'G'}]
obs: closed station, latest hour HTTP 404 text/html 710 chars '<!doctype html><html lang="en"><head><title>HTTP Status 404 '

Source: SMHI open data (CC BY 4.0 SE); answers shortened to the fields shown.
```

### 3. One town with Python urllib: robots check for every agent, a 48-hour CSV, the latest observations nearby, warnings for the point (cache that follows SMHI's metadata, no browser)

Pass `NAME LAT LON` on the command line (default Uppsala). 8 calls with an empty cache: 3 robots.txt, the forecast (7 parameters, 25 KB), 3 latest-hour observation sets (temperature, wind, hourly precipitation; every station in one call each, 44-60 KB) and the warnings list. The CSV ends with a source-and-changes line, as the licence asks. A warm run skips everything that is still fresh: the forecast for an hour (`max-age=3600`), observations while their observation hour is the current UTC hour, and warnings by `ETag`. Just after the hour turns, before SMHI publishes the new hour, observations are downloaded again (verifier warm run at 00:06 UTC: 7 calls, the three sets re-fetched with 23:00 still the newest hour). When the forecast is stale it first asks `createdtime.json` whether a new run exists (run 3 forced this path by expiring the cache entry: `[cache (createdtime.json unchanged)]` with one 77-byte call instead of 25 KB).

```python
import csv, email.utils, gzip, hashlib, json, math, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

NAME, LAT, LON = (sys.argv[1], float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) == 4 else ("Uppsala", 59.8586, 17.6389)
HOURS = 48
UA = "smhi-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
FCST = "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1"
OBS = "https://opendata-download-metobs.smhi.se/api/version/1.0"
WARN = "https://opendata-download-warnings.smhi.se/ibww/api/version/1/warning.json"
PARAMS = "air_temperature,wind_speed,wind_speed_of_gust,wind_from_direction,precipitation_amount_mean,probability_of_precipitation,predominant_precipitation_type_at_surface"
OBS_PARAMS = {1: "air temperature C", 4: "wind speed m/s (10 min mean)", 7: "precipitation mm (last hour)"}
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/smhi-skill"
CACHE = os.path.expanduser(CACHE_DIR)
OUT = f"smhi-{NAME.lower()}-48h.csv"  # in the current directory
PAUSE = 1.0  # serial; SMHI asks for no unnecessary load
MISSING = 9999  # parameter.json: missingValue of every snow1g parameter (no value for that hour)
calls = []

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def http(url, headers=None, ok=(200,)):
    """GET with gzip -> (status, headers, body). Statuses in `ok` (and 304) are returned. Waits once on 429/5xx or a
    network error (Retry-After, else 30 s; over 120 s exits); exits on anything else."""
    for attempt in range(2):
        time.sleep(PAUSE)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                calls.append((r.status, url))
                return r.status, r.headers, gzip.decompress(body) if r.headers.get("Content-Encoding") == "gzip" else body
        except urllib.error.HTTPError as e:
            calls.append((e.code, url))
            if e.code == 304 or e.code in ok:
                return e.code, e.headers, b""
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                wait = retry_wait(e.headers.get("Retry-After"), 30)
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:160]}")
        except OSError as e:
            if attempt == 0:
                time.sleep(30)
                continue
            sys.exit(f"{url}: {e}")

def cache_file(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")

def load(url):
    try:
        with open(cache_file(url)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None

def save(url, entry):
    os.makedirs(CACHE, exist_ok=True)
    with open(cache_file(url), "w") as fh:
        json.dump(entry, fh)

def fresh_until(h):
    """Cache-Control max-age minus Age -> epoch seconds the answer may be reused until (0 if not cacheable)."""
    m = re.search(r"max-age=(\d+)", h.get("Cache-Control") or "")
    return time.time() + int(m[1]) - int(h.get("Age") or 0) if m else 0

def cached(url, validate=None):
    """-> (data, how). Reuses a fresh copy without a call; else revalidates (ETag -> 304, or `validate(old)` says the
    data has not changed); else downloads. SMHI: honour cache metadata, do not fetch the same data again."""
    old = load(url)
    if old and time.time() < old["until"]:
        return old["data"], "cache (fresh)"
    if old and validate and (why := validate(old["data"])):
        return old["data"], f"cache ({why})"
    st, h, body = http(url, {"If-None-Match": old["etag"]} if old and old.get("etag") else None)
    if st == 304:
        old["until"] = fresh_until(h)
        save(url, old)
        return old["data"], "HTTP 304"
    data = json.loads(body)
    save(url, {"etag": h.get("ETag"), "until": fresh_until(h), "data": data})
    return data, f"HTTP {st}, {len(body):,} bytes unzipped"

# robots.txt groups and RFC 9309 matching (longest pattern wins, Allow on a tie); a 4xx robots.txt means no rules
def robots_groups(text):
    groups, agents, in_rules = {}, [], False
    for line in text.splitlines():
        k, _, v = line.split("#")[0].partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            agents, in_rules = (agents if not in_rules else []) + [v.lower()], False
            for a in agents:
                groups.setdefault(a, [])
        elif k in ("allow", "disallow") and agents:
            in_rules = True
            for a in agents:
                if v:
                    groups[a].append((k == "allow", v))
    return groups

def allowed(groups, agent, path):
    rules = groups.get(agent.lower(), groups.get("*", []))
    hits = [(len(p), ok) for ok, p in rules
            if re.match(re.escape(p.rstrip("$")).replace(r"\*", ".*") + ("$" if p.endswith("$") else ""), path)]
    return max(hits, default=(0, True))[1]

def km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))

def inside(lon, lat, geom):
    def ring(r):
        c = False
        for (xi, yi), (xj, yj) in zip(r, r[-1:] + r[:-1]):
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                c = not c
        return c
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"] if geom["type"] == "MultiPolygon" else None
    if polys is None:
        return None
    return any(ring(p[0]) and not any(ring(h) for h in p[1:]) for p in polys)

utc = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
now = datetime.now(timezone.utc)
lat, lon = round(LAT, 6), round(LON, 6)  # more than 6 decimals is HTTP 404
point = f"{FCST}/geotype/point/lon/{lon}/lat/{lat}/data.json?parameters={PARAMS}"
used = {"opendata-download-metfcst.smhi.se": [point.split(".se", 1)[1], "/api/category/snow1g/version/1/createdtime.json"],
        "opendata-download-metobs.smhi.se": ["/api/version/1.0/parameter/1/station-set/all/period/latest-hour/data.json"],
        "opendata-download-warnings.smhi.se": ["/ibww/api/version/1/warning.json"]}

# 1) robots.txt for every host and path used, for every agent
for host, paths in used.items():
    st, _, body = http(f"https://{host}/robots.txt", ok=(200, 404))
    groups = robots_groups(body.decode(errors="replace")) if st == 200 else {}
    bad = [(a, p) for a in AGENTS for p in paths if st == 200 and not allowed(groups, a, p)]
    print(f"robots.txt {host}: HTTP {st}" + (" (no rules: RFC 9309 treats 4xx as allow-all)" if 400 <= st < 500 else "")
          + f"; {len(paths)} path(s) x {len(AGENTS)} agents: {len(paths) * len(AGENTS) - len(bad)} allowed")
    if bad or st >= 500:
        sys.exit("robots.txt disallows (or could not be read for) a path this skill uses: stop")

# 2) forecast: reuse while fresh (max-age=3600); when stale, refetch only if createdtime.json moved
def same_run(old):  # 77-byte check instead of the whole forecast again
    ct = json.loads(http(f"{FCST}/createdtime.json")[2])
    return "createdtime.json unchanged" if ct["createdTime"] == old["createdTime"] else None
f, how_f = cached(point, same_run)
rows = [t for t in f["timeSeries"] if now < utc(t["time"]) <= now + timedelta(hours=HOURS)]
if len(rows) != HOURS or {(utc(t["time"]) - utc(t["intervalParametersStartTime"])).seconds for t in rows} != {3600}:
    sys.exit(f"forecast has {len(rows)} steps inside the window, not {HOURS} hourly ones: stop")
glon, glat = f["geometry"]["coordinates"]
print(f"\n{NAME} ({LAT}, {LON}) -> grid point ({glat}, {glon}), {km(LAT, LON, glat, glon):.1f} km away; "
      f"forecast created {f['createdTime']} [{how_f}]")
with open(OUT, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["time_utc", "air_temperature_c", "wind_speed_ms", "wind_gust_ms", "wind_from_deg", "precip_mm", "precip_probability_pct", "precip_type_code"])
    for t in rows:
        x = t["data"]
        w.writerow([t["time"]] + ["" if v == MISSING else v for v in (
            x["air_temperature"], x["wind_speed"], x["wind_speed_of_gust"], x["wind_from_direction"],
            x["precipitation_amount_mean"], x["probability_of_precipitation"], x["predominant_precipitation_type_at_surface"])])
    w.writerow([f"# Source: SMHI open data (CC BY 4.0 SE), snow1g forecast created {f['createdTime']}, grid point {glat},{glon}. "
                f"Changed: {len(rows)} hourly steps and 7 of 24 parameters kept; precipitation kg/m2 written as mm; "
                f"missing values (9999) left empty."])
d = [t["data"] for t in rows]
val = lambda k: [x[k] for x in d if x[k] != MISSING]   # hours that have a value
span = lambda k, fn: fn(val(k)) if val(k) else "n/a"
pr = val("precipitation_amount_mean")
gaps = {k: n for k in PARAMS.split(",") if (n := sum(x[k] == MISSING for x in d))}
print(f"  {len(rows)} hourly rows {rows[0]['time']} .. {rows[-1]['time']} -> {OUT}")
print(f"  temperature {span('air_temperature', min)} .. {span('air_temperature', max)} C, "
      f"max wind {span('wind_speed', max)} m/s (gust {span('wind_speed_of_gust', max)}), "
      + (f"precipitation {sum(pr):.1f} mm in {sum(v > 0 for v in pr)} hours" if pr else "precipitation n/a")
      + (f"; hours without a value (9999, skipped): {gaps}" if gaps else ""))

# 3) latest observation from the nearest CORE station per parameter (one call for all stations; max-age=600)
print("  latest observations (nearest CORE station with a value):")
for p, label in OBS_PARAMS.items():
    # the CDN often serves these with Age > max-age, so also keep a copy whose hour is the current one: no newer exists
    o, how_o = cached(f"{OBS}/parameter/{p}/station-set/all/period/latest-hour/data.json",
                      lambda old: "same observation hour" if old["updated"] // 1000 >= int(now.timestamp()) // 3600 * 3600 else None)
    st = [s for s in o["station"] if s.get("value") and s["measuringStations"] == "CORE"]  # or ?measuringStations=core (lower case; CORE is ignored)
    if not st:
        print(f"    {label:<30} no CORE station has a value this hour [{how_o}]")
        continue
    s = min(st, key=lambda s: km(LAT, LON, s["latitude"], s["longitude"]))
    v = s["value"][-1]
    print(f"    {label:<30} {v['value']:>5} at {s['name']} ({km(LAT, LON, s['latitude'], s['longitude']):.0f} km), "
          f"{datetime.fromtimestamp(v['date'] / 1000, timezone.utc):%H:%M} UTC, quality {v['quality']} [{how_o}]")

# 4) warnings: whole national list (ETag -> 304), keep areas whose polygon contains the point and that overlap the window
ws, how_w = cached(WARN)
hits = []
for wn in ws:
    for a in wn["warningAreas"]:
        g = a.get("area") or {}
        g = g.get("geometry", g)
        ins = inside(LON, LAT, g) if g.get("type") else None
        end = a.get("approximateEnd")
        if ins is None:
            print(f"  warning {wn['id']}: area geometry {g.get('type')} not checked, read it yourself")
        elif ins and utc(a["approximateStart"]) <= now + timedelta(hours=HOURS) and (not end or utc(end) > now):
            hits.append((wn, a))
print(f"\nSMHI warnings [{how_w}]: {len(ws)} in Sweden, {len(hits)} for this point")
for wn, a in hits:
    print(f"  {a['warningLevel']['code']:<8} {a['eventDescription']['en']} | {a.get('areaName', {}).get('en') or a.get('areaName', {}).get('sv')}"
          f" | {a['approximateStart']} -> {a.get('approximateEnd') or 'until further notice'} | id {wn['id']}/{a['id']}")
print(f"\ncalls this run: {len(calls)} ({', '.join(f'{s}' for s, _ in calls) or 'none'}); cache {CACHE_DIR}")
print(f"Source: SMHI open data (CC BY 4.0 SE). Changed: forecast cut to {HOURS} hourly steps and 7 of 24 parameters, "
      f"shown as min/max/sum with missing values (9999) skipped; observations from the nearest CORE station only. "
      f"Warnings as published by SMHI.")
```

Output (from the fourth run on 2026-11-21, 23:35 UTC, empty cache):

```text
robots.txt opendata-download-metfcst.smhi.se: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); 2 path(s) x 11 agents: 22 allowed
robots.txt opendata-download-metobs.smhi.se: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); 1 path(s) x 11 agents: 11 allowed
robots.txt opendata-download-warnings.smhi.se: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); 1 path(s) x 11 agents: 11 allowed

Uppsala (59.8586, 17.6389) -> grid point (59.85689, 17.635448), 0.3 km away; forecast created 2026-11-21T23:20:14Z [HTTP 200, 25,066 bytes unzipped]
  48 hourly rows 2026-11-22T00:00:00Z .. 2026-11-23T23:00:00Z -> smhi-uppsala-48h.csv
  temperature -0.4 .. 1.7 C, max wind 10.5 m/s (gust 18.9), precipitation 25.5 mm in 48 hours
  latest observations (nearest CORE station with a value):
    air temperature C                0.4 at Uppsala Aut (1 km), 23:00 UTC, quality G [HTTP 200, 60,382 bytes unzipped]
    wind speed m/s (10 min mean)     4.3 at Uppsala Aut (1 km), 23:00 UTC, quality G [HTTP 200, 49,338 bytes unzipped]
    precipitation mm (last hour)     0.7 at Uppsala Aut (1 km), 23:00 UTC, quality G [HTTP 200, 44,181 bytes unzipped]

SMHI warnings [HTTP 200, 140,445 bytes unzipped]: 11 in Sweden, 2 for this point
  MESSAGE  Risk for water shortage - Groundwater | Uppsala län | 2026-07-06T22:00:00.000Z -> until further notice | id 3257/10252
  YELLOW   Snow and wind | Parts of eastern Svealand | 2026-11-21T22:00:00.469Z -> 2026-11-23T15:00:00.801Z | id 3402/10811

calls this run: 8 (404, 404, 404, 200, 200, 200, 200, 200); cache ~/.cache/smhi-skill
Source: SMHI open data (CC BY 4.0 SE). Changed: forecast cut to 48 hourly steps and 7 of 24 parameters, shown as min/max/sum with missing values (9999) skipped; observations from the nearest CORE station only. Warnings as published by SMHI.
```

The fifth run, 13 seconds later (warm cache, same UTC hour): 4 calls instead of 8.

```text
robots.txt opendata-download-metfcst.smhi.se: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); 2 path(s) x 11 agents: 22 allowed
robots.txt opendata-download-metobs.smhi.se: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); 1 path(s) x 11 agents: 11 allowed
robots.txt opendata-download-warnings.smhi.se: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); 1 path(s) x 11 agents: 11 allowed

Uppsala (59.8586, 17.6389) -> grid point (59.85689, 17.635448), 0.3 km away; forecast created 2026-11-21T23:20:14Z [cache (fresh)]
  48 hourly rows 2026-11-22T00:00:00Z .. 2026-11-23T23:00:00Z -> smhi-uppsala-48h.csv
  temperature -0.4 .. 1.7 C, max wind 10.5 m/s (gust 18.9), precipitation 25.5 mm in 48 hours
  latest observations (nearest CORE station with a value):
    air temperature C                0.4 at Uppsala Aut (1 km), 23:00 UTC, quality G [cache (same observation hour)]
    wind speed m/s (10 min mean)     4.3 at Uppsala Aut (1 km), 23:00 UTC, quality G [cache (same observation hour)]
    precipitation mm (last hour)     0.7 at Uppsala Aut (1 km), 23:00 UTC, quality G [cache (same observation hour)]

SMHI warnings [HTTP 304]: 11 in Sweden, 2 for this point
  MESSAGE  Risk for water shortage - Groundwater | Uppsala län | 2026-07-06T22:00:00.000Z -> until further notice | id 3257/10252
  YELLOW   Snow and wind | Parts of eastern Svealand | 2026-11-21T22:00:00.469Z -> 2026-11-23T15:00:00.801Z | id 3402/10811

calls this run: 4 (404, 404, 404, 304); cache ~/.cache/smhi-skill
Source: SMHI open data (CC BY 4.0 SE). Changed: forecast cut to 48 hourly steps and 7 of 24 parameters, shown as min/max/sum with missing values (9999) skipped; observations from the nearest CORE station only. Warnings as published by SMHI.
```

### 4. curl, headers and mistakes

```bash
F=https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1
O=https://opendata-download-metobs.smhi.se/api/version/1.0
W=https://opendata-download-warnings.smhi.se/ibww/api/version/1/warning.json
UA='smhi-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# when was the current forecast made? (77 bytes; poll this, not the forecast)
curl -sS --fail -A "$UA" "$F/createdtime.json"; echo
sleep 1
# Malmö, next 6 hours, 4 parameters (precipitation is the sum since intervalParametersStartTime)
curl -sS --fail --compressed -A "$UA" "$F/geotype/point/lon/13.0038/lat/55.605/data.json?timeseries=6&parameters=air_temperature,wind_speed,wind_speed_of_gust,precipitation_amount_mean" \
  | python3 -c 'import sys, json
d = json.load(sys.stdin); print("grid point", d["geometry"]["coordinates"], "created", d["createdTime"])
for t in d["timeSeries"]: x = t["data"]; print(" ", t["time"], x["air_temperature"], "C", x["wind_speed"], "m/s gust", x["wind_speed_of_gust"], x["precipitation_amount_mean"], "mm")'
sleep 1
# forecast headers: cacheable for an hour, CORS open, no ETag
curl -sS --compressed -A "$UA" -D - -o /dev/null "$F/geotype/point/lon/13.0038/lat/55.605/data.json?timeseries=1" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|expires|etag|age|access-control-allow-origin|retry-after|x-ratelimit-[a-z]+):)'
sleep 1
# warnings: whole country in one list; areas carry GeoJSON polygons; ETag gives 304 on repeat
H=$(mktemp); T=$(mktemp)
curl -sS --compressed -A "$UA" -D "$H" -o "$T" -w 'warning.json -> HTTP %{http_code}, %{size_download} bytes gzip\n' "$W"
python3 -c 'import sys, json
ws = json.load(open(sys.argv[1]))
for w in ws:
    for a in w["warningAreas"]:
        print(" ", w["id"], a["warningLevel"]["code"], a["eventDescription"]["en"], "|", (a.get("areaName") or {}).get("en") or (a.get("areaName") or {}).get("sv"), "|", a["approximateStart"][:16], "->", (a.get("approximateEnd") or "open")[:16], "|", a["area"]["geometry"]["type"])' "$T" | head -n 6
E=$(tr -d '\r' < "$H" | sed -n 's/^etag: //Ip')
sleep 1
curl -sS --compressed -A "$UA" -H "If-None-Match: $E" -o /dev/null -w 'same with If-None-Match -> HTTP %{http_code}, %{size_download} bytes\n' "$W"
sleep 1
# latest hourly temperature at Stockholm-Observatoriekullen A (station 98230); dates are Unix milliseconds
curl -sS --fail --compressed -A "$UA" "$O/parameter/1/station/98230/period/latest-hour/data.json" \
  | python3 -c 'import sys, json, datetime as dt
d = json.load(sys.stdin); v = d["value"][-1]
print(d["station"]["name"], v["value"], d["parameter"]["unit"], dt.datetime.fromtimestamp(v["date"] / 1000, dt.timezone.utc).isoformat(), "quality", v["quality"])'
sleep 1
# mistakes
curl -sS -A "$UA" -o "$T" -w 'lon/lat swapped -> HTTP %{http_code} %{content_type}: ' "$F/geotype/point/lon/59.3293/lat/18.0686/data.json"; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o /dev/null -w '7 decimals -> HTTP %{http_code} %{content_type}\n' "$F/geotype/point/lon/18.0686123/lat/59.3293/data.json"; sleep 1
curl -sS -A "$UA" -o /dev/null -w 'retired pmp3g/version/2 -> HTTP %{http_code}\n' "https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/18.0686/lat/59.3293/data.json"; sleep 1
curl -sS -A "$UA" -o /dev/null -w 'closed station, latest hour -> HTTP %{http_code}\n' "$O/parameter/1/station/154860/period/latest-hour/data.json"; sleep 1
curl -sS -o /dev/null -w "curl's default User-Agent -> HTTP %{http_code}\n" "$F/createdtime.json"
echo "Source: SMHI open data (CC BY 4.0 SE), accessed $(date -u '+%d %B %Y %H:%M') UTC; forecast and observation cut to the fields shown, first 6 warning areas, warning titles as published by SMHI."
rm -f "$H" "$T"
```

Output (from the first run on 2026-11-21, 23:36 UTC; a new forecast run, created 23:34, had arrived):

```text
{"createdTime":"2026-11-21T23:34:15Z","referenceTime":"2026-11-21T23:15:00Z"}
grid point [12.984395, 55.614259] created 2026-11-21T23:34:15Z
  2026-11-22T00:00:00Z 4.3 C 7.9 m/s gust 11.8 0.0 mm
  2026-11-22T01:00:00Z 4.4 C 8.3 m/s gust 12.9 0.0 mm
  2026-11-22T02:00:00Z 3.3 C 6.7 m/s gust 12.4 0.0 mm
  2026-11-22T03:00:00Z 3.2 C 7.2 m/s gust 11.0 0.0 mm
  2026-11-22T04:00:00Z 3.0 C 7.5 m/s gust 11.5 0.0 mm
  2026-11-22T05:00:00Z 2.9 C 7.9 m/s gust 12.2 0.0 mm
HTTP/2 200 
expires: Sun, 22 Nov 2026 00:36:16 GMT
cache-control: max-age=3600,public
content-type: application/json
age: 0
access-control-allow-origin: *
warning.json -> HTTP 200, 40758 bytes gzip
  3122 MESSAGE Risk for water shortage - Groundwater and watercourses | Skåne län | 2026-04-20T22:00 -> open | Polygon
  3156 MESSAGE Risk for water shortage - Watercourses | Kronobergs län | 2026-05-04T22:00 -> open | Polygon
  3157 MESSAGE Risk for water shortage - Groundwater and watercourses | Blekinge län | 2026-05-04T22:00 -> open | Polygon
  3180 MESSAGE Risk for water shortage - Groundwater and watercourses | Kalmar län | 2026-05-18T22:00 -> open | MultiPolygon
  3181 MESSAGE Risk for water shortage - Groundwater and watercourses | Jönköpings län | 2026-05-18T22:00 -> open | Polygon
  3195 MESSAGE Risk for water shortage - Groundwater | Västra Götalands län | 2026-05-25T22:00 -> open | Polygon
same with If-None-Match -> HTTP 304, 0 bytes
Stockholm-Observatoriekullen A 1.2 celsius 2026-11-21T23:00:00+00:00 quality G
lon/lat swapped -> HTTP 404 text/plain: Requested point is out of bounds
7 decimals -> HTTP 404 text/html; charset=utf-8
retired pmp3g/version/2 -> HTTP 404
closed station, latest hour -> HTTP 404
curl's default User-Agent -> HTTP 200
Source: SMHI open data (CC BY 4.0 SE), accessed 22 November 2026 00:59 UTC; forecast and observation cut to the fields shown, first 6 warning areas, warning titles as published by SMHI.
```

## Fields

| Field | Value | Notes |
|---|---|---|
| `createdTime`, `referenceTime` | `2026-11-21T23:20:14Z`, `2026-11-21T23:00:00Z` | when the run was made and when it starts; runs seen at 23:20 (reference 23:00) and 23:34 (reference 23:15); five polls 23:36-23:56 found a third run at 23:49:46 (reference 23:30), so about every 15 minutes |
| `geometry.coordinates` | `[18.077207, 59.33036]` | the nearest grid point, lon first; not your input |
| `timeSeries[].time`, `.intervalParametersStartTime` | ISO UTC | valid time; precipitation and its probability cover the interval since the start time (1 h at first, later 3, 6, 12 h) |
| `air_temperature` | `1.6` | C at 2 m |
| `wind_speed`, `wind_speed_of_gust`, `wind_from_direction` | `6.1`, `12.6`, `343` | m/s at 10 m, instantaneous gust (docs unit "m s**-1"), degrees the wind comes from |
| `precipitation_amount_mean` | `0.5` | kg/m2 (= mm) over the interval, mean of the ensemble; also `_median`, `_mean_deterministic`, `_min`, `_max` |
| `probability_of_precipitation` | `100` | % chance of at least 0.1 mm in the interval (`parameter.json`: "Propability of precipitation of at least 0.1 mm") |
| `predominant_precipitation_type_at_surface` | `0`-`12` | 0 none, 1 rain, 2 thunderstorm, 3 freezing rain, 4 mixed/ice, 5 snow, 6 wet snow, 7 rain and snow, 8 ice pellets, 9 graupel, 10 hail, 11 drizzle, 12 freezing drizzle (parameters page) |
| `precipitation_frozen_part` | `21`, or `-9` | percent frozen; `-9` when there is no precipitation |
| `symbol_code` | `1`-`27` | weather symbol, 1 clear sky ... 27 heavy snowfall (parameters page) |
| other parameters | | `relative_humidity`, `air_pressure_at_mean_sea_level`, `visibility_in_air`, `thunderstorm_probability`, `probability_of_frozen_precipitation`, four cloud covers in oktas, `cloud_base_altitude`, `cloud_top_altitude`; `parameter.json` lists all 24 with units and `missingValue` 9999 |
| warning `id`, `event.{sv,en,code}`, `event.mhoClassification` | `3402`, `Snow`, `SNOW`, `MET` | one warning can have many areas (`WIND_SEA` 3403 had 11) |
| `warningAreas[].warningLevel.code` | `RED`, `ORANGE`, `YELLOW`, `MESSAGE` | MESSAGE is e.g. a risk, such as water shortage |
| `warningAreas[].eventDescription.en`, `.areaName.{sv,en}` | `Snow and wind`, `Parts of eastern Svealand` | `areaName` can be Swedish only (`Skåne län`) |
| `warningAreas[].approximateStart`, `.approximateEnd`, `.published` | ISO UTC with milliseconds | no `approximateEnd` = continues indefinitely |
| `warningAreas[].area.geometry` | GeoJSON Polygon or MultiPolygon, EPSG:4326 | lon, lat order |
| `warningAreas[].affectedAreas[]` | `{"id": 1, "sv": "Stockholms län", "en": "Stockholm County"}` | counties and sea districts |
| `warningAreas[].descriptions[]` | `{"title": {"sv", "en", "code"}, "text": {"sv", "en"}}` | codes `HAPPENS`, `INCIDENT`, `AFFECT`, `COMMENTS`, `WHERE`, ...; print as is |
| observation `station[]` (station-set) | `name`, `latitude`, `longitude`, `measuringStations` (`CORE`/`ADDITIONAL`), `value[]` | `value[].date` is Unix milliseconds, `value[].value` a string (`"1.2"`), `quality` `G` ("controlled and approved") or `Y` ("Suspicious or aggregated values. Roughly controlled archive data and uncontrolled real-time data.", data docs); `G` on 486 and `Y` on 16 of the 502 values in the three 23:00 UTC latest-hour sets |
| forecast headers | `Content-Type: application/json`, `Cache-Control: max-age=3600,public`, `Expires`, `Access-Control-Allow-Origin: *` | no `ETag`; `Last-Modified` is the time of the answer |
| warnings headers | `ETag: W/"2249d-..."`, `Access-Control-Allow-Origin: *` | no `Cache-Control`; `If-None-Match` gives HTTP 304 |

## Gotchas

- **`pmp3g/version/2` is gone.** Older tutorials and libraries use `/api/category/pmp3g/version/2/...`; it now answers HTTP 404 (a Varnish error page). Use `snow1g/version/1`, whose parameters have long names (`air_temperature`, not `t`) and sit directly in `data`, not in a `parameters` list.
- **Out-of-area points are HTTP 404, not 400.** The docs say "HTTP 400 - FIELD POINT OUT OF BOUNDS"; swapping lon and lat (lon 59.33, lat 18.07) got HTTP 404 `text/plain` "Requested point is out of bounds". More than six decimals is HTTP 404 with an HTML body. Round to 6 decimals and put longitude first in the path. The forecast area's outline (`geotype/polygon.json`) spans lon -18.12..54.24, lat 49.77..75.23, so all of Sweden is inside.
- **You get the nearest grid point.** Stockholm 59.3293, 18.0686 -> 59.33036, 18.077207 (about 0.5 km); Uppsala 0.3 km away. Report the grid point if precision matters.
- **Steps grow after about 2.5 days.** 61 hourly steps, then 3, 6 and 12 h. The precipitation of a longer step is the sum over that step; dividing by hours gives an average rate, not hourly values.
- **`precipitation_amount_min` can be larger than the mean.** Min and max are taken only over ensemble members "with non-zero precipitation" (parameters page). Stockholm's last step (12 h to 2 Dec 00:00) had min 0.8, mean 0.2, median 0.0, max 1.5 mm. Use `_mean` or `_median` for totals.
- **`precipitation_frozen_part` is `-9` when it is dry.** 6 of Stockholm's 84 steps in the 23:20 run (3 in the 23:49 run). Treat it as "no precipitation", not as a percentage.
- **New forecast runs come more often than the cache allows.** Runs were created at 23:20 (reference 23:00), 23:34 (reference 23:15) and 23:49 (reference 23:30), about every 15 minutes (five polls of `createdtime.json`, 23:36-23:56 UTC), but every forecast answer says `max-age=3600`. Inside that hour the run you hold is allowed by SMHI's metadata; to see a newer one, check `createdtime.json` with a client that does not cache it.
- **The browser caches the forecast and `createdtime.json` for an hour.** `fetch()` uses the browser's HTTP cache, and both answers say `max-age=3600`. Block 1's second run (23:36) and block 2's second run (23:37) still printed the 23:20 run, while curl at 23:36 already got the 23:34 run. That is cache-friendly by design; date the output by `createdTime`, not by the clock.
- **Some answers have no CORS header.** The forecast, `warning.json` and the observation API send `Access-Control-Allow-Origin: *`, but the Varnish 404 pages, the warnings entry point `ibww/api/version/1.json` and the test sets `ibww/test/test_N.json` do not, so an in-browser `fetch()` of them fails with "Failed to fetch" (status 0) although curl gets HTTP 200 or 404. Block 1 treats status 0 as a network error, waits 30 s once, then stops.
- **Warnings are national; you do the geography.** `affectedAreas` lists counties ("Stockholm County") or sea districts, and a drawn area can cover only parts of them ("Parts of eastern Svealand"). Match the town's coordinates against `area.geometry`. Sea-district areas (all 11 areas of `WIND_SEA` 3403) do not contain land towns.
- **Water-shortage messages last for months.** The `MESSAGE`-level "Risk for water shortage" areas started between 20 April and 20 July 2026 and have no `approximateEnd`. Show the level, so a message is not read as a storm warning.
- **Warning text must not be edited.** The licence says the information must not be changed and the source always given. The blocks print `descriptions[].text` exactly as published, newlines included, in SMHI's own English (`en`) or Swedish (`sv`) field; do not paraphrase, translate or shorten it, and add "Source: SMHI". `areaName` sometimes has no `en` (`{"sv": "Skåne län"}`).
- **Latest observations: Age is often above max-age.** The CDN served the all-stations temperature set with `Cache-Control: max-age=600` and `Age: 691`, so a strict client finds it stale at once and would download it again on every run. Block 3 keeps a copy whose observation hour (`updated`) is the current hour, since no newer value exists yet.
- **`measuringStations` is case-sensitive.** The docs give the values `core`, `additional` or `all` for the parameter level and station sets. `?measuringStations=core` returned only the 222 CORE stations of the all-stations temperature set, `additional` the 11 others, but `?measuringStations=CORE` (upper case) was silently ignored and returned all 233 (curl, verifier, 2026-11-22 00:03 UTC). Block 3 downloads the full set once, caches it, and filters on each station's `measuringStations` field; CORE stations are quality-checked by SMHI, ADDITIONAL are not (docs introduction).
- **Different stations measure different things.** 233 stations report temperature, 182 wind and 168 hourly precipitation; not all have a value every hour (184, 179 and 139 did at 23:00 UTC). Pick the nearest station per parameter, as block 3 does.
- **A closed station's latest hour is HTTP 404.** Station 154860 (Abelvattnet Aut, `active: false`) for temperature. The station list `parameter/1.json` (1,008 stations, 234 active) has `active`.
- **Forecast answers have no ETag.** `If-Modified-Since` with the previous `Last-Modified` got HTTP 200 and the full body again (`Last-Modified` is the time of the answer). Use `Expires`/`max-age` and `createdtime.json` instead.
- **Tab marker.** The harness may set the tab title to a horse emoji; the blocks check the URL and the page text, not the title.

## What does not work

- **The retired `pmp3g/version/2` forecast API**: HTTP 404.
- **Forecasts for many places at once**: the terms ask to avoid mass downloads of forecasts for many places at the same time. The documented multipoint forecast (`geotype/multipoint/time/{time}/parameter/{p}/data.json`, one parameter at one time for every grid point; `geotype/multipoint.json` is the static grid-point list) was not used or tested; this skill fetches one point per town.
- **Warnings by town name or municipality**: there is no such filter; use the polygons.
- **Timezone-aware times from the API**: everything is UTC; block 1 adds Europe/Stockholm local time and says so in its source line.
- **Not tested:** the 429 response (never provoked), CAP XML warnings (`ibww/api/version/1/cap.xml`), warning metadata endpoints, `times.json`, the multipoint forecast, other forecast products (fire risk, analysis, radar, lightning), observation periods other than `latest-hour`, CSV/XML formats, and anything the docs mark as keyed.
