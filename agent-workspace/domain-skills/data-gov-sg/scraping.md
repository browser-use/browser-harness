# data.gov.sg via api-open.data.gov.sg - Get Singapore's Current Conditions for an Area: 2-hour Weather Forecast by Town, Latest Air Temperature and Rainfall at the Nearest Station, Current PSI and PM2.5 by Region (JSON API, no key)

Field-tested against api-open.data.gov.sg and data.gov.sg on 2026-11-20 (US Pacific afternoon; 23:52 UTC on Nov 20 to 00:09 UTC on Nov 21, which was 07:52-08:09 on Saturday 21 November in Singapore) using a fresh Browser Use cloud browser (logged out; one session, 23:53-00:06 UTC) plus Python `urllib` and `curl` from a Linux machine. 58 browser page loads (54 on data.gov.sg hosts; 4 on www.haze.gov.sg before its terms were read, see below) and 74 in-page `fetch()` calls (block 1 ran twice, block 2 four times), 37 urllib calls (27 to the API, 10 robots.txt) and 18 curl calls (10 to the API, 8 robots.txt), all serial, at most 5 API calls in any 10 s. Every API call was HTTP 200 except the deliberate HTTP 400 and 404 probes and the HTTP 403 answers to Python's default User-Agent (see Gotchas). The 13 timed urllib calls took 0.22-0.30 s each. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-20, curl, the cloud browser and `urllib.robotparser`): https://api-open.data.gov.sg/robots.txt answers HTTP 404 with a JSON body (`"Route not found"`), so the API host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources". https://data.gov.sg/robots.txt is `User-agent: *` / `Allow: /` and nothing else. https://guide.data.gov.sg/robots.txt is `User-agent: *`, `Content-Signal: ai-train=yes, search=yes, ai-input=yes` and `Allow` lines only. None of the three names an AI agent, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`, and every path this skill uses is allowed for all 11 agents (block 3). https://api.data.gov.sg/robots.txt (the older v1 host: carpark, taxi, v1 weather) answers HTTP 403 `{"message":"Forbidden"}` to every client tried, so its rules cannot be read and this skill does not use that host. Terms: the Terms of Use at https://data.gov.sg/privacy-and-terms say in section 2 "The use of Datasets on The Website is wholly governed by the Singapore Open Data Licence. Access to datasets via application programming interfaces (APIs) is governed by the API Terms of Service" and "The terms below, including that on intellectual property, do not cover Datasets"; section 9 ("no part of The Website may be reproduced or reused for any commercial purposes whatsoever without our prior written permission") covers the website itself, not the data. The API Terms of Service on the same page: "You can use, access, call, command, query or request the API, whether commercially or non-commercially", "You shall not mis-present or mask your API Client's identity when Using the API", "You shall not interfere with or disrupt the API or the servers or networks providing the API", and "Your right to Use APIs may be subject to additional terms, including limitations on Use, found on the individual pages of each API" (the API pages this skill uses say "Free forever for personal or commercial use, under the Open Data Licence." and list the rate limits, block 2). The Singapore Open Data Licence version 1.0 (https://data.gov.sg/open-data-licence): "You can use, access, download, copy, distribute, transmit, modify and adapt the datasets, or any derived analyses or applications, whether commercially or non-commercially", you must include "a conspicuous notice acknowledging the source of the datasets and including a link to the most recent version of this Licence", and "You must not use the datasets in a way that suggests any official status or that an Agency endorses you or your Use of the datasets"; it grants no rights over "patents, trademarks and design rights". No AI/ML, scraping, automated-access or non-commercial clause in any of them. Naming: this skill says "data.gov.sg" in plain text, prints the licence's attribution line with the dataset names and the licence link, uses no government crest or logo, and is not affiliated with or endorsed by data.gov.sg, Open Government Products or NEA. The data comes from NEA (National Environment Agency), as each dataset page says. Slug `data-gov-sg`.

**Not for safety decisions.** These are automated readings and short forecasts. The air temperature dataset page says "There could be instances when there are gaps in the data due to technical problems. The data is subject to correction subsequently if necessary." For haze health advice use NEA's own advisories.

## Quick summary

- **No scraping.** One GET per dataset, no key, no parameters: `GET https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast` -> `{"code": 0, "data": {"area_metadata": [{"name": "Ang Mo Kio", "label_location": {"latitude": 1.375, "longitude": 103.839}}, ...47], "items": [{"update_timestamp": "2026-11-21T07:36:49+08:00", "valid_period": {"start": ..., "end": ..., "text": "7.30 am to 9.30 am"}, "forecasts": [{"area": "Ang Mo Kio", "forecast": "Cloudy"}, ...]}]}, "errorMsg": ""}` (6 KB). Same pattern for `air-temperature`, `rainfall`, `relative-humidity`, `wind-speed` (stations plus one reading each), `psi`, `pm25` (5 regions), `twenty-four-hr-forecast` and `uv`. `Access-Control-Allow-Origin: *`.
- **Answer (block 1, 2026-11-21 08:05 SGT; block 3 at 08:07 shows the same PSI and PM2.5):** **Tampines**: 2-hour forecast **Light Rain** (7.30-9.30 am), **27.4 deg C** at Paya Lebar Meteorological Station (4.6 km away, 07:58), **0 mm** in the 5 minutes to 07:55 at Tampines Avenue 5 (0.1 km), east region **24-hr PSI 38**, **1-hr PM2.5 9 µg/m3** (08:00). **Jurong West**: Cloudy, 26.8 deg C at Nanyang Avenue (2.7 km), 0 mm, west PSI 55, PM2.5 7. **Marina Bay** (1.2834, 103.8607 -> area "City"): Cloudy, 27.1 deg C at Scotts Road (4.0 km), 0 mm at Marina Barrage, south PSI 43, PM2.5 3. All five regions were in NEA's "0 - 100 Good to Moderate" PSI band and PM2.5 "Band 1 (Normal)".
- **Two naming styles.** `two-hr-forecast` is snake_case (`area_metadata`, `label_location`, `update_timestamp`, `valid_period`); every other endpoint here is camelCase (`regionMetadata`, `labelLocation`, `updatedTimestamp`, `stationId`, `readingType`, `validPeriod`). The PSI and PM2.5 API notes on data.gov.sg say `region_metadata`; the response (and the schema on the same page) says `regionMetadata`.
- **Nearest, not "in".** Station readings come as a station list plus values keyed by `stationId`; there are about 17 temperature stations (one answer at 08:14 SGT listed 16) and 87 rain gauges, so the nearest thermometer can be several km away (Tampines -> Paya Lebar, 4.6 km). PSI and PM2.5 come for 5 regions (north, south, east, west, central) with one label point each and no boundaries; the blocks take the nearest label and print the distance. There is no national value.
- **Rate limit: 6 calls per 10 s without a key** ("The rate limits are reset every 10 seconds", 429 when exceeded; 12 with a dev key, 30 with a prod key; guide.data.gov.sg API Rate Limits). No rate-limit headers and no `Cache-Control` or `ETag` came back. Blocks 1 and 2 wait 2.1 s after each call; block 3 allows at most 5 calls in any 10 s and keeps a 60 s disk cache. All wait 10 s once on 429, 5xx or a network error and stop after that. Send a User-Agent: Python's default one gets HTTP 403.

## What works

### 1. Places as a person names them -> 2-hour forecast, nearest temperature and rain gauge, PSI and PM2.5 for the region (browser)

`on_dgs_tab()` opens the logged-out licence page on data.gov.sg (the page the attribution line links to); the API sends `Access-Control-Allow-Origin: *`, so `fetch()` from there needs no credentials. `get()` returns the `data` object on HTTP 200 with `"code": 0`, waits 10 s once on 429/500/502/503/504 or a network error and otherwise raises. 5 API calls, 2.1 s apart (about 11 s). A place is a forecast area name in any case, or `(latitude, longitude)`; a near miss prints the closest names instead of guessing.

```python
import difflib, json, math, time
from datetime import datetime, timedelta, timezone

# Places as a person gives them: a 2-hour-forecast area name (any case) or (latitude, longitude).
PLACES = ["Tampines", "jurong west", "Toa Payo", (1.2834, 103.8607)]   # the last one is Marina Bay

SITE = "https://data.gov.sg"
API = "https://api-open.data.gov.sg/v2/real-time/api/"
PAUSE = 2.1   # keyless limit: 6 calls per 10 s for v2 real-time APIs (guide.data.gov.sg, API Rate Limits); stay at 5
SGT = timezone(timedelta(hours=8))   # every timestamp in these answers carries +08:00
LICENCE = SITE + "/open-data-licence"
DATASETS = {"two-hr-forecast": "2-hour Weather Forecast", "air-temperature": "Air Temperature across Singapore",
            "rainfall": "Rainfall across Singapore", "psi": "Pollutant Standards Index (PSI)", "pm25": "PM2.5"}

def on_dgs_tab():
    """A logged-out data.gov.sg page (the licence, which the attribution line links to); the API sends
    Access-Control-Allow-Origin: *, so fetch() from here works without credentials."""
    try:
        if js("location.href").startswith(LICENCE):
            return
    except Exception:
        pass
    new_tab(LICENCE)
    wait_for_load()
    for _ in range(30):
        if "Singapore Open Data Licence" in (js("document.body ? document.body.innerText : ''") or ""):
            return
        time.sleep(1)
    raise RuntimeError(f"data.gov.sg did not show the licence page (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def get(name):
    """One real-time API -> its "data" object. Waits 10 s once on 429/5xx or a network error (the limit window
    resets every 10 s); raises on anything else, including a body whose "code" is not 0."""
    url = API + name
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(10)
            continue
        break
    body = json.loads(r["text"]) if "json" in r["headers"].get("content-type", "") else None
    if r["status"] != 200 or not body or body.get("code") != 0:
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:150]!r}; stopping")
    return body["data"]

def km(a, b):
    """Great-circle distance between two (lat, lon) points."""
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))

def ts(s):
    return datetime.fromisoformat(s)   # '2026-11-21T07:30:00+08:00' -> aware datetime

def nearest_reading(d, at):
    """Station readings: stations live in d["stations"], values in d["readings"][0]["data"] by stationId.
    Only stations that reported in the newest reading count."""
    newest = d["readings"][0]
    vals = {x["stationId"]: x["value"] for x in newest["data"]}
    st = [s for s in d["stations"] if s["id"] in vals]
    s = min(st, key=lambda s: km(at, (s["location"]["latitude"], s["location"]["longitude"])))
    return s, vals[s["id"]], km(at, (s["location"]["latitude"], s["location"]["longitude"])), ts(newest["timestamp"])

# NEA's bands as shown on www.haze.gov.sg on 2026-11-20 (seen once while exploring; its terms forbid robots, so no block fetches it)
def psi_band(v):
    return "Good to Moderate" if v <= 100 else "Unhealthy" if v <= 200 else "Very Unhealthy" if v <= 300 else "Hazardous"
def pm25_band(v):
    return "Band 1 (Normal)" if v <= 55 else "Band 2 (Elevated)" if v <= 150 else "Band 3 (High)" if v <= 250 else "Band 4 (Very High)"

on_dgs_tab()
fc = get("two-hr-forecast")       # snake_case: area_metadata, label_location, update_timestamp, valid_period
temp = get("air-temperature")     # camelCase: stationId, readingType, readingUnit
rain = get("rainfall")
psi = get("psi")                  # camelCase: regionMetadata, labelLocation, updatedTimestamp
pm = get("pm25")
now = datetime.now(SGT)

areas = {a["name"]: (a["label_location"]["latitude"], a["label_location"]["longitude"]) for a in fc["area_metadata"]}
item = fc["items"][0]
by_area = {f["area"]: f["forecast"] for f in item["forecasts"]}
if set(by_area) != set(areas):
    raise RuntimeError(f"forecast areas {len(by_area)} != area_metadata {len(areas)}: stop")
regions = {r["name"]: (r["labelLocation"]["latitude"], r["labelLocation"]["longitude"]) for r in psi["regionMetadata"]}
p, q = psi["items"][0], pm["items"][0]
vp = item["valid_period"]
print(f"data.gov.sg real-time weather and air quality, checked {now:%Y-%m-%d %H:%M} SGT ({now.astimezone(timezone.utc):%H:%M} UTC)")
print(f"2-hour forecast {vp['text']} (issued {ts(item['update_timestamp']):%H:%M}); {len(areas)} areas; "
      f"temperature {temp['readingType']!r} in {temp['readingUnit']}; rainfall {rain['readingType']!r} in {rain['readingUnit']}")

lower = {n.lower(): n for n in areas}
for place in PLACES:
    if isinstance(place, tuple):
        at = place
        area = min(areas, key=lambda n: km(at, areas[n]))
        head = f"{place[0]:.4f}, {place[1]:.4f} -> nearest forecast area label: {area} ({km(at, areas[area]):.1f} km)"
    else:
        area = lower.get(place.strip().lower())
        if not area:
            print(f"\n{place!r}: not a 2-hour forecast area; closest names {difflib.get_close_matches(place.title(), areas, 3, 0.6)}")
            continue
        at = areas[area]
        head = f"{place!r} -> {area} (area label {at[0]:.3f}, {at[1]:.3f})"
    print("\n" + head)
    print(f"  2-hour forecast   {by_area[area]}")
    for label, d, unit in (("air temperature", temp, " deg C"), ("rainfall", rain, " mm in 5 min")):
        s, v, dist, t = nearest_reading(d, at)
        age = (now - t).total_seconds() / 60
        print(f"  {label:<17} {v}{unit} at {s['name']} ({s['id']}, {dist:.1f} km), {t:%H:%M}"
              + (f"  STALE: {age:.0f} min old" if age > 30 else ""))
    reg = min(regions, key=lambda r: km(at, regions[r]))
    v, w = p["readings"]["psi_twenty_four_hourly"][reg], q["readings"]["pm25_one_hourly"][reg]
    print(f"  region {reg:<10} 24-hr PSI {v} {psi_band(v)}, 1-hr PM2.5 {w} µg/m3 {pm25_band(w)}; "
          f"hour {ts(p['timestamp']):%H:%M}, nearest of {len(regions)} region labels ({km(at, regions[reg]):.1f} km)")

hr = p["readings"]["psi_twenty_four_hourly"]
print(f"\nall regions, 24-hr PSI at {ts(p['timestamp']):%H:%M}: " + ", ".join(f"{r} {hr[r]}" for r in sorted(hr))
      + f"; 1-hr PM2.5 at {ts(q['timestamp']):%H:%M}: " + ", ".join(f"{r} {q['readings']['pm25_one_hourly'][r]}" for r in sorted(hr)))
print(f"Contains information from {', '.join(DATASETS.values())} accessed on {now:%d %B %Y} from data.gov.sg which is made "
      f"available under the terms of the Singapore Open Data Licence version 1.0 {LICENCE}")
```

Output (from the second run on 2026-11-21, 08:05 SGT, 00:05 UTC; the first run at 07:57 SGT gave the same areas, stations and regions with the 07:00 PSI hour):

```text
data.gov.sg real-time weather and air quality, checked 2026-11-21 08:05 SGT (00:05 UTC)
2-hour forecast 7.30 am to 9.30 am (issued 07:36); 47 areas; temperature 'DBT 1M F' in deg C; rainfall 'TB1 Rainfall 5 Minute Total F' in mm

'Tampines' -> Tampines (area label 1.345, 103.944)
  2-hour forecast   Light Rain
  air temperature   27.4 deg C at Paya Lebar Meteorological Station (S06, 4.6 km), 07:58
  rainfall          0 mm in 5 min at Tampines Avenue 5 (S84, 0.1 km), 07:55
  region east       24-hr PSI 38 Good to Moderate, 1-hr PM2.5 9 µg/m3 Band 1 (Normal); hour 08:00, nearest of 5 region labels (1.4 km)

'jurong west' -> Jurong West (area label 1.340, 103.705)
  2-hour forecast   Cloudy
  air temperature   26.8 deg C at Nanyang Avenue (S44, 2.7 km), 07:58
  rainfall          0 mm in 5 min at Jurong West Street 73 (S228, 0.9 km), 07:55
  region west       24-hr PSI 55 Good to Moderate, 1-hr PM2.5 7 µg/m3 Band 1 (Normal); hour 08:00, nearest of 5 region labels (2.0 km)

'Toa Payo': not a 2-hour forecast area; closest names ['Toa Payoh']

1.2834, 103.8607 -> nearest forecast area label: City (2.1 km)
  2-hour forecast   Cloudy
  air temperature   27.1 deg C at Scotts Road (S111, 4.0 km), 07:58
  rainfall          0 mm in 5 min at Marina Barrage (S108, 1.1 km), 07:55
  region south      24-hr PSI 43 Good to Moderate, 1-hr PM2.5 3 µg/m3 Band 1 (Normal); hour 08:00, nearest of 5 region labels (4.7 km)

all regions, 24-hr PSI at 08:00: central 45, east 38, north 38, south 43, west 55; 1-hr PM2.5 at 08:00: central 14, east 9, north 9, south 3, west 7
Contains information from 2-hour Weather Forecast, Air Temperature across Singapore, Rainfall across Singapore, Pollutant Standards Index (PSI), PM2.5 accessed on 21 November 2026 from data.gov.sg which is made available under the terms of the Singapore Open Data Licence version 1.0 https://data.gov.sg/open-data-licence
```

### 2. robots.txt, the terms and dataset pages, what the nine endpoints return, `?date=` and mistakes (browser)

11 page loads and 16 in-page `fetch()` calls (about 34 s of API pacing) in the same tab. The API notes on the dataset pages sit in the page's embedded JSON and a panel that `innerText` skipped, so the block reads `textContent` and matches the notes as written there (with backticks).

```python
import json, re, time
from datetime import datetime, timedelta, timezone

API = "https://api-open.data.gov.sg/v2/real-time/api/"
PAUSE = 2.1   # keyless: 6 calls per 10 s; this block makes 16 API calls, about 34 s
SGT = timezone(timedelta(hours=8))

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(path):
    """One in-page GET of API + path -> {status, headers, text}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(API + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def page(url, needles=()):
    goto_url(url)
    wait_for_load()
    txt = ""
    for _ in range(30):   # data.gov.sg pages are a JavaScript app: wait until every needle shows (or 30 s)
        # textContent, not innerText: the API notes sit in a panel that innerText skipped (hidden at this window size)
        txt = js("(document.body || document.documentElement).textContent || ''") or ""
        flat = " ".join(txt.split())
        if all(" ".join(n.split()) in flat for n in needles):
            break
        time.sleep(1)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("location.href"), txt

# 1. robots.txt (api.data.gov.sg is the older v1 host; this skill does not use it)
for host in ("data.gov.sg", "api-open.data.gov.sg", "guide.data.gov.sg", "api.data.gov.sg"):
    st, href, txt = page(f"https://{host}/robots.txt")
    ua = [l.strip() for l in txt.splitlines() if l.lower().startswith("user-agent")]
    dis = [l.split(":", 1)[1].strip() for l in txt.splitlines() if l.lower().startswith("disallow")]
    print(f"{host + '/robots.txt':<32} HTTP {st}: " + (f"user-agent lines {ua}, Disallow {dis}, "
          f"other lines {[l.strip() for l in txt.splitlines() if l.strip() and not l.lower().startswith(('user-agent', 'disallow', 'allow', 'sitemap'))]}"
          if ua else f"no robots rules: {' '.join(txt.split())[:80]!r}"))

# 2. Terms, licence, rate limits, and what the dataset pages say. The API notes (field names, forecast values) show in the
#    side panel of the API list (?resultId=), where only textContent has them; the /datasets/<id>/view page shows them too.
for url, needles in (
    ("https://data.gov.sg/privacy-and-terms", [
        "Access to datasets via application programming interfaces (APIs) is governed by the",
        "The terms below, including that on intellectual property, do not cover Datasets",
        "no part of The Website may be reproduced or reused for any commercial purposes whatsoever",
        "You can use, access, call, command, query or request the API, whether commercially or non-commercially",
        "Your right to Use APIs may be subject to additional terms, including limitations on Use, found on the individual pages of each API",
        "You shall not mis-present or mask your API Client’s identity when Using the API",
        "You shall not interfere with or disrupt the API or the servers or networks providing the API"]),
    ("https://data.gov.sg/open-data-licence", [
        "whether commercially or non-commercially",
        "a conspicuous notice acknowledging the source of the datasets and including a link to the most recent version of this Licence",
        "which is made available under the terms of the Singapore Open Data Licence version 1.0",
        "You must not use the datasets in a way that suggests any official status",
        "and patents, trademarks and design rights"]),
    ("https://guide.data.gov.sg/developer-guide/api-overview/api-rate-limits.md", [
        "the following rate limits represent the number of API calls that can be made every 10 seconds",
        "you will receive a `429` status error",
        "v2 Realtime API</a></td><td>6</td><td>12</td><td>30</td>"]),
    ("https://data.gov.sg/datasets?formats=API&resultId=d_fe37906a0182569d891506e815e819b7", [
        "Pollutant Standards Index (PSI)", "Updated every 15 minutes", "Unit of measure for readings is `PSI Value`",
        "Free forever for personal or commercial use, under the Open Data Licence.",
        # the API notes (still in the page's embedded JSON) say region_metadata; the schema beside them, and the API, say regionMetadata
        "The `region_metadata` field in the response provides longitude/latitude information", "regionMetadata"]),
    ("https://data.gov.sg/datasets?formats=API&resultId=d_3f9e064e25005b0e42969944ccaf2e7a", [
        "2-hour Weather Forecast", "Updated every 30 minutes", "Ad-hoc updates may also occur outside the standard cadence",
        "Forecasts are valid for two hours", "Heavy Thundery Showers with Gusty Winds",
        "Free forever for personal or commercial use, under the Open Data Licence."]),
    ("https://data.gov.sg/datasets/d_66b77726bbae1b33f218db60ff5861f0/view", [
        "Air Temperature across Singapore", "Minute-by-minute air temperature readings", "Updated every 5 minutes",
        "There could be instances when there are gaps in the data due to technical problems"]),
):
    st, href, txt = page(url, needles)
    flat = " ".join(txt.split())
    for n in needles:
        print(f"{href.split('//')[1][:46]:<46} HTTP {st}: {'found' if ' '.join(n.split()) in flat else 'MISSING'}: {n[:66]!r}")
goto_url("https://data.gov.sg/open-data-licence")   # stay on data.gov.sg; the API allows any origin
wait_for_load()
print()

# 3. What the nine endpoints really return: field casing, sizes, headers
for name in ("two-hr-forecast", "twenty-four-hr-forecast", "air-temperature", "rainfall", "relative-humidity",
             "wind-speed", "uv", "psi", "pm25"):
    r = raw(name)
    b = json.loads(r["text"])
    d = b["data"]
    lists = {k: len(v) for k, v in d.items() if isinstance(v, list)}
    extra = {k: d[k] for k in ("readingType", "readingUnit") if k in d}
    print(f"{name:<24} HTTP {r['status']} code {b['code']} {len(r['text']):>6} chars  data keys {sorted(d)}  lists {lists} {extra or ''}")
    if name in ("psi", "pm25"):
        print(f"{'':<24} readings keys {sorted(d['items'][0]['readings'])[:4]}{'...' if len(d['items'][0]['readings']) > 4 else ''}; "
              f"regions {sorted(d['items'][0]['readings'][next(iter(d['items'][0]['readings']))])} (no 'national')")
    if name == "two-hr-forecast":
        print(f"{'':<24} item keys {sorted(d['items'][0])}; forecast values now {sorted({f['forecast'] for f in d['items'][0]['forecasts']})}")
h = r["headers"]
print("response headers (pm25):", {k: h[k] for k in sorted(h) if k in ("content-type", "cache-control", "etag", "last-modified",
      "access-control-allow-origin", "retry-after") or k.startswith("x-ratelimit")})

# 4. ?date= filters, pagination, and mistakes
today = datetime.now(SGT)
day = f"{today:%Y-%m-%d}"
r = json.loads(raw(f"psi?date={day}")["text"])["data"]
print(f"\npsi?date={day}: {len(r['items'])} hourly items {r['items'][-1]['timestamp'][11:16]}..{r['items'][0]['timestamp'][11:16]} "
      f"(order: {'newest first' if r['items'][0]['timestamp'] > r['items'][-1]['timestamp'] else 'oldest first'}), "
      f"paginationToken {'present' if r.get('paginationToken') else 'absent'}")
y = (today - timedelta(days=1)).strftime("%Y-%m-%d")
t1 = json.loads(raw(f"air-temperature?date={y}")["text"])["data"]
ts1 = [x["timestamp"][11:16] for x in t1["readings"]]
print(f"air-temperature?date={y}: page 1 has {len(ts1)} readings {ts1[0]}..{ts1[-1]}, paginationToken {len(t1.get('paginationToken') or '')} chars")
t2 = json.loads(raw(f"air-temperature?date={y}&paginationToken={t1['paginationToken']}")["text"])["data"]
ts2 = [x["timestamp"][11:16] for x in t2["readings"]]
print(f"  page 2 has {len(ts2)} readings {ts2[0]}..{ts2[-1]}; minutes per reading step {sorted({int(a[3:]) - int(b[3:]) for a, b in zip(ts1, ts1[1:]) if a[:2] == b[:2]})}")
at = (today - timedelta(hours=3)).strftime("%Y-%m-%dT%H:00:00")
f3 = json.loads(raw(f"two-hr-forecast?date={at}")["text"])["data"]["items"]
print(f"two-hr-forecast?date={at}: {len(f3)} item, valid {f3[0]['valid_period']['text']!r}, updated {f3[0]['update_timestamp']}")
for label, path in (("date=21-11-2026      ", "two-hr-forecast?date=21-11-2026"),
                    ("misspelled endpoint  ", "two-hr-forcast"),
                    ("v1 path on v2 host   ", "environment/air-temperature")):
    r = raw(path)
    print(f"{label} HTTP {r['status']} {r['headers'].get('content-type')}: {' '.join(r['text'].split())[:150]}")
```

Output (from the fourth run on 2026-11-21, 08:04 SGT; the first three runs found the same endpoint shapes and errors and were used to fix the page needles):

```text
data.gov.sg/robots.txt           HTTP 200: user-agent lines ['User-agent: *'], Disallow [], other lines []
api-open.data.gov.sg/robots.txt  HTTP 404: no robots rules: '{"code":28,"name":"NOT_FOUND","data":null,"errorMsg":"Route not found"}'
guide.data.gov.sg/robots.txt     HTTP 200: user-agent lines ['User-agent: *'], Disallow [], other lines ['Content-Signal: ai-train=yes, search=yes, ai-input=yes']
api.data.gov.sg/robots.txt       HTTP 403: no robots rules: '{"message":"Forbidden"}'
data.gov.sg/privacy-and-terms                  HTTP 200: found: 'Access to datasets via application programming interfaces (APIs) i'
data.gov.sg/privacy-and-terms                  HTTP 200: found: 'The terms below, including that on intellectual property, do not c'
data.gov.sg/privacy-and-terms                  HTTP 200: found: 'no part of The Website may be reproduced or reused for any commerc'
data.gov.sg/privacy-and-terms                  HTTP 200: found: 'You can use, access, call, command, query or request the API, whet'
data.gov.sg/privacy-and-terms                  HTTP 200: found: 'Your right to Use APIs may be subject to additional terms, includi'
data.gov.sg/privacy-and-terms                  HTTP 200: found: 'You shall not mis-present or mask your API Client’s identity when '
data.gov.sg/privacy-and-terms                  HTTP 200: found: 'You shall not interfere with or disrupt the API or the servers or '
data.gov.sg/open-data-licence                  HTTP 200: found: 'whether commercially or non-commercially'
data.gov.sg/open-data-licence                  HTTP 200: found: 'a conspicuous notice acknowledging the source of the datasets and '
data.gov.sg/open-data-licence                  HTTP 200: found: 'which is made available under the terms of the Singapore Open Data'
data.gov.sg/open-data-licence                  HTTP 200: found: 'You must not use the datasets in a way that suggests any official '
data.gov.sg/open-data-licence                  HTTP 200: found: 'and patents, trademarks and design rights'
guide.data.gov.sg/developer-guide/api-overview HTTP 200: found: 'the following rate limits represent the number of API calls that c'
guide.data.gov.sg/developer-guide/api-overview HTTP 200: found: 'you will receive a `429` status error'
guide.data.gov.sg/developer-guide/api-overview HTTP 200: found: 'v2 Realtime API</a></td><td>6</td><td>12</td><td>30</td>'
data.gov.sg/datasets?formats=API&resultId=d_fe HTTP 200: found: 'Pollutant Standards Index (PSI)'
data.gov.sg/datasets?formats=API&resultId=d_fe HTTP 200: found: 'Updated every 15 minutes'
data.gov.sg/datasets?formats=API&resultId=d_fe HTTP 200: found: 'Unit of measure for readings is `PSI Value`'
data.gov.sg/datasets?formats=API&resultId=d_fe HTTP 200: found: 'Free forever for personal or commercial use, under the Open Data L'
data.gov.sg/datasets?formats=API&resultId=d_fe HTTP 200: found: 'The `region_metadata` field in the response provides longitude/lat'
data.gov.sg/datasets?formats=API&resultId=d_fe HTTP 200: found: 'regionMetadata'
data.gov.sg/datasets?formats=API&resultId=d_3f HTTP 200: found: '2-hour Weather Forecast'
data.gov.sg/datasets?formats=API&resultId=d_3f HTTP 200: found: 'Updated every 30 minutes'
data.gov.sg/datasets?formats=API&resultId=d_3f HTTP 200: found: 'Ad-hoc updates may also occur outside the standard cadence'
data.gov.sg/datasets?formats=API&resultId=d_3f HTTP 200: found: 'Forecasts are valid for two hours'
data.gov.sg/datasets?formats=API&resultId=d_3f HTTP 200: found: 'Heavy Thundery Showers with Gusty Winds'
data.gov.sg/datasets?formats=API&resultId=d_3f HTTP 200: found: 'Free forever for personal or commercial use, under the Open Data L'
data.gov.sg/datasets/d_66b77726bbae1b33f218db6 HTTP 200: found: 'Air Temperature across Singapore'
data.gov.sg/datasets/d_66b77726bbae1b33f218db6 HTTP 200: found: 'Minute-by-minute air temperature readings'
data.gov.sg/datasets/d_66b77726bbae1b33f218db6 HTTP 200: found: 'Updated every 5 minutes'
data.gov.sg/datasets/d_66b77726bbae1b33f218db6 HTTP 200: found: 'There could be instances when there are gaps in the data due to te'

two-hr-forecast          HTTP 200 code 0   5960 chars  data keys ['area_metadata', 'items']  lists {'area_metadata': 47, 'items': 1} 
                         item keys ['forecasts', 'timestamp', 'update_timestamp', 'valid_period']; forecast values now ['Cloudy', 'Light Rain']
twenty-four-hr-forecast  HTTP 200 code 0   1537 chars  data keys ['records']  lists {'records': 1} 
air-temperature          HTTP 200 code 0   2671 chars  data keys ['readingType', 'readingUnit', 'readings', 'stations']  lists {'stations': 17, 'readings': 1} {'readingType': 'DBT 1M F', 'readingUnit': 'deg C'}
rainfall                 HTTP 200 code 0  12570 chars  data keys ['readingType', 'readingUnit', 'readings', 'stations']  lists {'stations': 87, 'readings': 1} {'readingType': 'TB1 Rainfall 5 Minute Total F', 'readingUnit': 'mm'}
relative-humidity        HTTP 200 code 0   2669 chars  data keys ['readingType', 'readingUnit', 'readings', 'stations']  lists {'stations': 17, 'readings': 1} {'readingType': 'RH 1M F', 'readingUnit': 'percentage'}
wind-speed               HTTP 200 code 0   2631 chars  data keys ['readingType', 'readingUnit', 'readings', 'stations']  lists {'stations': 17, 'readings': 1} {'readingType': 'Wind Speed AVG(S)10M M1M', 'readingUnit': 'knots'}
uv                       HTTP 200 code 0    211 chars  data keys ['records']  lists {'records': 1} 
psi                      HTTP 200 code 0   1442 chars  data keys ['items', 'regionMetadata']  lists {'regionMetadata': 5, 'items': 1} 
                         readings keys ['co_eight_hour_max', 'co_sub_index', 'no2_one_hour_max', 'o3_eight_hour_max']...; regions ['central', 'east', 'north', 'south', 'west'] (no 'national')
pm25                     HTTP 200 code 0    619 chars  data keys ['items', 'regionMetadata']  lists {'regionMetadata': 5, 'items': 1} 
                         readings keys ['pm25_one_hourly']; regions ['central', 'east', 'north', 'south', 'west'] (no 'national')
response headers (pm25): {'content-type': 'application/json; charset=utf-8'}

psi?date=2026-11-21: 9 hourly items 00:00..08:00 (order: newest first), paginationToken absent
air-temperature?date=2026-11-20: page 1 has 25 readings 23:59..23:35, paginationToken 88 chars
  page 2 has 25 readings 23:34..23:09; minutes per reading step [1]
two-hr-forecast?date=2026-11-21T05:00:00: 1 item, valid '5.00 am to 7.00 am', updated 2026-11-21T05:06:44+08:00
date=21-11-2026       HTTP 400 application/json; charset=utf-8: {"code":4,"name":"ERROR_PARAMS","data":null,"errorMsg":"Invalid date format. Date format must be YYYY-MM-DD (2024-06-01) or YYYY-MM-DDTHH:mm:ss (2024-
misspelled endpoint   HTTP 404 application/json; charset=utf-8: {"code":28,"name":"NOT_FOUND","data":null,"errorMsg":"Route not found"}
v1 path on v2 host    HTTP 404 application/json; charset=utf-8: {"code":28,"name":"NOT_FOUND","data":null,"errorMsg":"Route not found"}
```

In a browser, `fetch()` only sees the response headers that CORS exposes (here `content-type`); block 4 shows the full set.

### 3. Island-wide view with Python urllib: robots check for every agent, 24-hour outlook, all 47 areas, humidity, wind and UV, air quality so far today, 60 s cache (no browser)

Sends a descriptive User-Agent (the API ToS: do not mask your client's identity). An API key is optional: put it in `DATA_GOV_SG_API_KEY` and it goes out as `x-api-key`; the block never prints it. 7 API calls on an empty cache; 8.8 s in all went to waiting for the 10 s window.

```python
import hashlib, json, math, os, sys, time, urllib.error, urllib.request, urllib.robotparser
from collections import defaultdict
from datetime import datetime, timedelta, timezone

PLACE = "Tampines"   # a 2-hour forecast area name, for the humidity and wind lines
API = "https://api-open.data.gov.sg/v2/real-time/api/"
UA = "data-gov-sg-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"   # API ToS: do not mask your client's identity
KEY = os.environ.get("DATA_GOV_SG_API_KEY")   # optional: sent as x-api-key for higher limits; never printed
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
WINDOW, MAX_CALLS = 10.0, 5   # keyless: 6 calls per 10 s ("reset every 10 seconds"); keep one spare
CACHE_DIR = "~/.cache/data-gov-sg-skill"
CACHE = os.path.expanduser(CACHE_DIR)
FRESH = 60    # the API sends no Cache-Control or ETag; readings change every 1-15 min, forecasts every 30 min
SGT = timezone(timedelta(hours=8))
LICENCE = "https://data.gov.sg/open-data-licence"
calls, stats = [], {"net": 0, "cache": 0, "bytes": 0, "waited": 0.0}

def get(path):
    """API + path -> the "data" object. Disk copy reused for 60 s. At most 5 calls in any 10 s. Waits 10 s once on
    429/5xx or a network error (the limit window resets every 10 s); exits on anything else or a non-zero "code"."""
    f = os.path.join(CACHE, hashlib.sha256(path.encode()).hexdigest())
    try:
        if time.time() - os.path.getmtime(f) < FRESH:
            stats["cache"] += 1
            return json.load(open(f))["data"]
    except (OSError, ValueError):
        pass
    hdr = {"User-Agent": UA, "Accept": "application/json"}
    if KEY:
        hdr["x-api-key"] = KEY
    for attempt in range(2):
        while len(calls) >= MAX_CALLS and time.time() - calls[-MAX_CALLS] < WINDOW:
            w = WINDOW - (time.time() - calls[-MAX_CALLS]) + 0.05
            stats["waited"] += w
            time.sleep(w)
        calls.append(time.time())
        try:
            with urllib.request.urlopen(urllib.request.Request(API + path, headers=hdr), timeout=30) as r:
                raw = r.read()
            body = json.loads(raw)
            if body.get("code") != 0:
                sys.exit(f"{path}: code {body.get('code')} {body.get('errorMsg')!r}")
            stats["net"] += 1
            stats["bytes"] += len(raw)
            os.makedirs(CACHE, exist_ok=True)
            open(f, "wb").write(raw)
            return body["data"]
        except urllib.error.HTTPError as e:
            msg = " ".join(e.read().decode(errors="replace").split())[:150]
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(10)
                continue
            sys.exit(f"HTTP {e.code} {path}: {msg}")
        except OSError as e:   # DNS, refused connection, timeout, reset
            if attempt == 0:
                time.sleep(10)
                continue
            sys.exit(f"{path}: {e}")

def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))

def nearest(d, at):
    """Newest station reading nearest to `at`, among stations that reported."""
    vals = {x["stationId"]: x["value"] for x in d["readings"][0]["data"]}
    s = min((s for s in d["stations"] if s["id"] in vals),
            key=lambda s: km(at, (s["location"]["latitude"], s["location"]["longitude"])))
    return s, vals[s["id"]], km(at, (s["location"]["latitude"], s["location"]["longitude"]))

# robots.txt, fetched with our User-Agent: RobotFileParser.read() sends "Python-urllib/3.x", which api-open.data.gov.sg
# answers with HTTP 403 (read as disallow-all). With UA it is 404: no rules (RFC 9309 section 2.3.1.3, the same rule
# read() applies to a 4xx other than 401/403). api.data.gov.sg (v1) answers 403 to every agent: not used here.
for host, paths in (("https://api-open.data.gov.sg", ["/v2/real-time/api/two-hr-forecast", "/v2/real-time/api/psi",
                                                       "/v2/real-time/api/air-temperature?date=2026-11-20"]),
                    ("https://data.gov.sg", ["/open-data-licence", "/privacy-and-terms", "/datasets"]),
                    ("https://guide.data.gov.sg", ["/developer-guide/api-overview/api-rate-limits.md"]),
                    ("https://api.data.gov.sg", ["/v1/environment/air-temperature"])):
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    try:
        with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
            st = r.status
            rp.parse(r.read().decode("utf-8", "replace").splitlines())
    except urllib.error.HTTPError as e:
        st = e.code
        rp.disallow_all = e.code in (401, 403)
        rp.allow_all = 400 <= e.code < 500 and not rp.disallow_all
    time.sleep(1)
    for p in paths:
        ok = all(rp.can_fetch(a, host + p) for a in AGENTS)
        print(f"{host[8:]:<21} robots.txt HTTP {st}  {p:<52} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
        if not ok and "api.data.gov.sg" not in host:
            sys.exit("robots.txt now disallows a path this skill uses: stop")

now = datetime.now(SGT)
day = f"{now:%Y-%m-%d}"
print(f"\ndata.gov.sg, checked {now:%Y-%m-%d %H:%M} SGT" + (" with an API key" if KEY else " without an API key"))

# 1. 24-hour outlook (camelCase) and the period running now, per region
rec = get("twenty-four-hr-forecast")["records"][0]
g = rec["general"]
print(f"24-hour forecast {g['validPeriod']['text']}: {g['forecast']['text']}, {g['temperature']['low']}-{g['temperature']['high']} {g['temperature']['unit']}, "
      f"humidity {g['relativeHumidity']['low']}-{g['relativeHumidity']['high']}%, wind {g['wind']['direction']} "
      f"speed {g['wind']['speed']['low']}-{g['wind']['speed']['high']} (no unit in the response) (issued {rec['updatedTimestamp'][11:16]})")
for per in rec["periods"]:
    t0, t1 = datetime.fromisoformat(per["timePeriod"]["start"]), datetime.fromisoformat(per["timePeriod"]["end"])
    tag = "  <- now" if t0 <= now < t1 else ""
    print(f"  {per['timePeriod']['text']:<28} " + ", ".join(f"{r} {v['text']}" for r, v in sorted(per["regions"].items())) + tag)

# 2. Every 2-hour forecast area, grouped by forecast (snake_case)
fc = get("two-hr-forecast")
it = fc["items"][0]
groups = defaultdict(list)
for x in it["forecasts"]:
    groups[x["forecast"]].append(x["area"])
end = datetime.fromisoformat(it["valid_period"]["end"])
print(f"\n2-hour forecast {it['valid_period']['text']} for {len(it['forecasts'])} areas (issued {it['update_timestamp'][11:16]}"
      + (f"; EXPIRED at {end:%H:%M}, the next one is late" if now > end else "") + "):")
for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    print(f"  {k:<18} {len(v):>2}: {', '.join(v[:8])}{' ...' if len(v) > 8 else ''}")

# 3. Humidity, wind and UV at PLACE
areas = {a["name"]: (a["label_location"]["latitude"], a["label_location"]["longitude"]) for a in fc["area_metadata"]}
at = areas[PLACE]
rh, ws = get("relative-humidity"), get("wind-speed")
s1, v1, d1 = nearest(rh, at)
s2, v2, d2 = nearest(ws, at)
uv = max(get("uv")["records"][0]["index"], key=lambda x: x["hour"])   # one entry per hour so far; take the newest
print(f"\n{PLACE}: relative humidity {v1}% at {s1['name']} ({d1:.1f} km, {rh['readings'][0]['timestamp'][11:16]}); "
      f"wind {v2} knots = {v2 * 1.852:.0f} km/h at {s2['name']} ({d2:.1f} km); UV index {uv['value']} for the hour from {uv['hour'][11:16]} (island-wide)")

# 4. Air quality so far today: ?date=YYYY-MM-DD gives every hourly item of that day, newest first
psi = get(f"psi?date={day}")
pm = get(f"pm25?date={day}")
if psi.get("paginationToken") or pm.get("paginationToken"):
    print("  (more pages exist; this block reads page 1 only)")
print(f"\nair quality {day}, {len(psi['items'])} hourly PSI items {psi['items'][-1]['timestamp'][11:16]}..{psi['items'][0]['timestamp'][11:16]}:")
print(f"  {'region':<8} {'24-hr PSI now':>13} {'range today':>11} {'1-hr PM2.5 now':>15} {'max today':>9}")
for reg in sorted(psi["items"][0]["readings"]["psi_twenty_four_hourly"]):
    p = [x["readings"]["psi_twenty_four_hourly"][reg] for x in psi["items"]]
    q = [x["readings"]["pm25_one_hourly"][reg] for x in pm["items"]]
    print(f"  {reg:<8} {p[0]:>13} {f'{min(p)}-{max(p)}':>11} {q[0]:>15} {max(q):>9}")

# 5. Ask again inside 60 s: answered from disk
n = dict(stats)
get("two-hr-forecast")
get(f"psi?date={day}")
print(f"\nrepeat within 60 s: {stats['net'] - n['net']} calls, {stats['cache'] - n['cache']} disk hits")
print(f"totals: {stats['net']} API calls ({stats['bytes']:,} bytes), {stats['cache']} disk hits, {stats['waited']:.1f} s waited for the 10 s window, cache {CACHE_DIR}")
print(f"Contains information from 24-hour Weather Forecast, 2-hour Weather Forecast, Relative Humidity across Singapore, "
      f"Wind Speed across Singapore, Ultraviolet Index (UVI), Pollutant Standards Index (PSI), PM2.5 accessed on {now:%d %B %Y} "
      f"from data.gov.sg which is made available under the terms of the Singapore Open Data Licence version 1.0 {LICENCE}")
```

Output (from the second run on 2026-11-21, 08:07 SGT, empty cache; the first run a minute earlier, before the UV line picked the newest hour by time, printed the same lines except 8.9 s waited):

```text
api-open.data.gov.sg  robots.txt HTTP 404  /v2/real-time/api/two-hr-forecast                    allowed for all 11 agents
api-open.data.gov.sg  robots.txt HTTP 404  /v2/real-time/api/psi                                allowed for all 11 agents
api-open.data.gov.sg  robots.txt HTTP 404  /v2/real-time/api/air-temperature?date=2026-11-20    allowed for all 11 agents
data.gov.sg           robots.txt HTTP 200  /open-data-licence                                   allowed for all 11 agents
data.gov.sg           robots.txt HTTP 200  /privacy-and-terms                                   allowed for all 11 agents
data.gov.sg           robots.txt HTTP 200  /datasets                                            allowed for all 11 agents
guide.data.gov.sg     robots.txt HTTP 200  /developer-guide/api-overview/api-rate-limits.md     allowed for all 11 agents
api.data.gov.sg       robots.txt HTTP 403  /v1/environment/air-temperature                      DISALLOWED for all 11 agents

data.gov.sg, checked 2026-11-21 08:07 SGT without an API key
24-hour forecast 6 AM 21 Nov to 6 AM 22 Nov: Thundery Showers, 25-33 Degrees Celsius, humidity 60-95%, wind NE speed 10-20 (no unit in the response) (issued 05:41)
  6 am to Midday 21 Nov        central Light Rain, east Light Rain, north Light Rain, south Light Rain, west Light Rain  <- now
  Midday to 6 pm 21 Nov        central Light Rain, east Light Rain, north Light Rain, south Light Rain, west Thundery Showers
  6 pm 21 Nov to 6 am 22 Nov   central Cloudy, east Cloudy, north Cloudy, south Cloudy, west Cloudy

2-hour forecast 8.00 am to 10.00 am for 47 areas (issued 08:06):
  Cloudy             36: Ang Mo Kio, Bedok, Bishan, Boon Lay, Bukit Batok, Bukit Merah, Bukit Panjang, Bukit Timah ...
  Light Rain         11: Changi, Pasir Ris, Paya Lebar, Pulau Tekong, Pulau Ubin, Punggol, Seletar, Sembawang ...

Tampines: relative humidity 90.7% at Paya Lebar Meteorological Station (4.6 km, 08:03); wind 0.9 knots = 2 km/h at Paya Lebar Meteorological Station (4.6 km); UV index 0 for the hour from 07:00 (island-wide)

air quality 2026-11-21, 9 hourly PSI items 00:00..08:00:
  region   24-hr PSI now range today  1-hr PM2.5 now max today
  central             45       45-53              14        14
  east                38       38-47               9        16
  north               38       38-49               9         9
  south               43       43-51               3         8
  west                55       55-58               7         9

repeat within 60 s: 0 calls, 2 disk hits
totals: 7 API calls (24,775 bytes), 2 disk hits, 8.8 s waited for the 10 s window, cache ~/.cache/data-gov-sg-skill
Contains information from 24-hour Weather Forecast, 2-hour Weather Forecast, Relative Humidity across Singapore, Wind Speed across Singapore, Ultraviolet Index (UVI), Pollutant Standards Index (PSI), PM2.5 accessed on 21 November 2026 from data.gov.sg which is made available under the terms of the Singapore Open Data Licence version 1.0 https://data.gov.sg/open-data-licence
```

### 4. curl one-liners, headers, User-Agent and mistakes

```bash
B=https://api-open.data.gov.sg/v2/real-time/api
# --retry 1 retries once on a timeout or HTTP 408, 429, 500, 502, 503 or 504, 10 s later (the limit window resets every 10 s)
C="curl -sS --compressed --max-time 30 --retry 1 --retry-delay 10 -A data-gov-sg-skill-example/1.0"
AREA="Bukit Timah"
# 2-hour forecast for one area (snake_case fields)
$C --fail "$B/two-hr-forecast" | AREA="$AREA" python3 -c 'import json, os, sys
it = json.load(sys.stdin)["data"]["items"][0]
f = {x["area"]: x["forecast"] for x in it["forecasts"]}
print(os.environ["AREA"], "->", f[os.environ["AREA"]], "|", it["valid_period"]["text"], "| issued", it["update_timestamp"])'
sleep 2
# latest 24-hr PSI and 1-hr PM2.5 by region (camelCase fields; no "national" key)
$C --fail "$B/psi" | python3 -c 'import json, sys
i = json.load(sys.stdin)["data"]["items"][0]; print("PSI 24h", i["timestamp"], i["readings"]["psi_twenty_four_hourly"])'
sleep 2
$C --fail "$B/pm25" | python3 -c 'import json, sys
i = json.load(sys.stdin)["data"]["items"][0]; print("PM2.5 1h", i["timestamp"], i["readings"]["pm25_one_hourly"])'
sleep 2
# the forecast that was valid at 06:00 SGT today (date-time filter, SGT, no offset in the parameter)
$C --fail "$B/two-hr-forecast?date=$(TZ=Asia/Singapore date +%Y-%m-%d)T06:00:00" | python3 -c 'import json, sys
it = json.load(sys.stdin)["data"]["items"][0]; print("at 06:00:", it["valid_period"]["text"], "issued", it["update_timestamp"])'
sleep 2
# headers: JSON, CORS open, no Cache-Control, no ETag, no rate-limit headers
$C -D - -o /dev/null "$B/air-temperature" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|content-encoding|cache-control|etag|last-modified|access-control-allow-origin|retry-after|x-ratelimit[a-z-]*):)'
sleep 2
# User-Agent: Python's default one is refused
for ua in "Python-urllib/3.12" "curl/8.5.0"; do
  curl -sS --max-time 30 -o /dev/null -A "$ua" -w "UA $ua: HTTP %{http_code}\n" "$B/uv"; sleep 2
done
# mistakes are JSON with a "code"
$C -w ' <- HTTP %{http_code}\n' "$B/psi?date=2026-13-01"
sleep 2
$C -w ' <- HTTP %{http_code}\n' "$B/two-hr-forcast"
sleep 2
$C -w ' <- HTTP %{http_code}\n' "$B/psi?date=2014-01-01"
echo "Contains information from 2-hour Weather Forecast, Pollutant Standards Index (PSI), PM2.5, Air Temperature across Singapore and Ultraviolet Index (UVI) accessed on $(TZ=Asia/Singapore date '+%d %B %Y') from data.gov.sg which is made available under the terms of the Singapore Open Data Licence version 1.0 https://data.gov.sg/open-data-licence"
```

Output (from the run on 2026-11-21, 08:08 SGT):

```text
Bukit Timah -> Cloudy | 8.00 am to 10.00 am | issued 2026-11-21T08:06:51+08:00
PSI 24h 2026-11-21T08:00:00+08:00 {'north': 38, 'south': 43, 'west': 55, 'east': 38, 'central': 45}
PM2.5 1h 2026-11-21T08:00:00+08:00 {'north': 9, 'south': 3, 'west': 7, 'east': 9, 'central': 14}
at 06:00: 6.00 am to 8.00 am issued 2026-11-21T06:06:52+08:00
HTTP/2 200 
content-type: application/json; charset=utf-8
access-control-allow-origin: *
content-encoding: br
UA Python-urllib/3.12: HTTP 403
UA curl/8.5.0: HTTP 200
{"code":4,"name":"ERROR_PARAMS","data":null,"errorMsg":"Invalid date value. Date format must be YYYY-MM-DD (2024-06-01) or YYYY-MM-DDTHH:mm:ss (2024-06-01T08:30:00)."} <- HTTP 400
{"code":28,"name":"NOT_FOUND","data":null,"errorMsg":"Route not found"} <- HTTP 404
{"code":17,"name":"REAL_TIME_API_DATA_NOT_FOUND","data":null,"errorMsg":"Data not found"} <- HTTP 404
Contains information from 2-hour Weather Forecast, Pollutant Standards Index (PSI), PM2.5, Air Temperature across Singapore and Ultraviolet Index (UVI) accessed on 21 November 2026 from data.gov.sg which is made available under the terms of the Singapore Open Data Licence version 1.0 https://data.gov.sg/open-data-licence
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| every answer | `{"code": 0, "data": {...}, "errorMsg": ""}` | errors keep the shape with `"data": null`: `code` 4 `ERROR_PARAMS` (HTTP 400), 28 `NOT_FOUND` (unknown route, HTTP 404), 17 `REAL_TIME_API_DATA_NOT_FOUND` (no data for that date, HTTP 404) |
| `two-hr-forecast` | `area_metadata[]` (`name`, `label_location.latitude/longitude`), `items[0]` (`timestamp`, `update_timestamp`, `valid_period.start/end/text`, `forecasts[]` of `{area, forecast}`) | 47 areas, one label point each; `forecast` is text from the list on the dataset page (23 values from "Fair" to "Heavy Thundery Showers with Gusty Winds"); seen: Cloudy, Light Rain |
| `air-temperature`, `rainfall`, `relative-humidity`, `wind-speed` | `stations[]` (`id`, `deviceId`, `name`, `location.latitude/longitude`), `readings[0]` (`timestamp`, `data[]` of `{stationId, value}`), `readingType`, `readingUnit` | 17 / 87 / 17 / 17 stations (the list can shrink: air temperature and humidity listed 16 at 08:14 SGT, 17 again at 08:18); units `deg C`, `mm`, `percentage`, `knots`; rainfall `readingType` is "TB1 Rainfall 5 Minute Total F" (mm in the last 5 minutes); `id` equalled `deviceId` for every temperature and rainfall station |
| `psi` | `regionMetadata[]` (`name`, `labelLocation`), `items[0]` (`date`, `timestamp`, `updatedTimestamp`, `readings`) | `readings` has 12 keys, each `{north, south, east, west, central}`: `psi_twenty_four_hourly`, `pm25_twenty_four_hourly`, `pm10_twenty_four_hourly`, `so2_twenty_four_hourly`, `no2_one_hour_max`, `co_eight_hour_max`, `o3_eight_hour_max` and 5 `*_sub_index`; key order differed between the latest answer and a `?date=YYYY-MM-DDTHH:mm:ss` answer (alphabetical there) |
| `pm25` | same shape as `psi`, `readings.pm25_one_hourly` | µg/m3; hourly; the 08:00 value was out by 08:05 SGT |
| `twenty-four-hr-forecast` | `records[0]` (`date`, `updatedTimestamp`, `general` {`forecast.code/text`, `temperature`, `relativeHumidity`, `wind.direction`, `wind.speed.low/high`, `validPeriod`}, `periods[]` {`timePeriod`, `regions.{central,east,north,south,west}.code/text`}) | 3 periods (6 am to midday, midday to 6 pm, 6 pm to 6 am); `wind.speed` has no unit field |
| `uv` | `records[0].index[]` of `{hour, value}` | island-wide, hourly; 0 at 07:00 |
| `?date=YYYY-MM-DD` | every reading of that SGT day, newest first, plus `paginationToken` when more exist | air temperature: 25 readings a page, one a minute; PSI: one page (9 hourly items by 08:00) |
| `?date=YYYY-MM-DDTHH:mm:ss` | the item in force at that SGT moment | no offset in the parameter |
| timestamps | ISO 8601 with `+08:00` | the `date` parameter and `date` fields are SGT dates |
| response headers | `content-type: application/json; charset=utf-8`, `access-control-allow-origin: *`, `content-encoding: br` | no `Cache-Control`, `ETag`, `Last-Modified` or rate-limit headers; served through Cloudflare |

## Gotchas

- **Python's default User-Agent is refused.** `Python-urllib/3.12` got HTTP 403 from the API (`/uv`) and from api-open's robots.txt, so `RobotFileParser.read()` would report every path as disallowed. `curl/8.5.0` (curl's default here) and a descriptive User-Agent got 200 (robots.txt: 404, no rules). Block 3 fetches robots.txt itself and passes it to `parse()`.
- **Field casing differs by endpoint**, and the docs disagree with the API: `two-hr-forecast` uses `area_metadata`/`label_location`/`update_timestamp`; `psi` and `pm25` use `regionMetadata`/`labelLocation`/`updatedTimestamp` although their notes say `region_metadata`. Read keys per endpoint; never share one parser.
- **Regions are points.** `regionMetadata` gives one label location per region (north 1.41803, 103.82; south 1.29587, 103.82; east, west and central at latitude 1.35735) and no boundary. Nearest label is an approximation near region edges (Marina Bay was 4.7 km from the south label). There is no `national` reading (the PSI and PM2.5 schemas on data.gov.sg list only the 5 regions, and so did every answer); NEA's haze site shows "Overall Singapore" as a range such as "39 - 55".
- **Rainfall is a 5-minute total.** `value` 0 means no rain in the last 5 minutes at that gauge, not a dry day. For a sum over a longer window, page through `?date=` (288 readings a day).
- **`?date=` pages are small.** A day of air temperature is 1,440 one-minute readings at 25 a page, about 58 calls or 2 minutes at the keyless limit. Follow `paginationToken` only as far as you need; it was absent when one page held the whole day (PSI).
- **Forecasts land a few minutes late.** The 8.00-10.00 am forecast was issued at 08:06:51 and the 6.00-8.00 am one at 06:06:52, so at 08:05 the API still served 7.30-9.30 am. The dataset page adds "Ad-hoc updates may also occur outside the standard cadence". Compare `valid_period.end` with the clock (block 3 flags an expired one).
- **Station sets differ and readings can be missing.** Temperature, humidity and wind have about 17 stations, rainfall 87, and a station can drop out of the list between answers (16 for temperature and humidity at 08:14 SGT); the blocks pick the nearest station that has a value in the newest reading and print its distance and time.
- **Singapore time.** Timestamps carry `+08:00`, and `?date=` takes an SGT date or time without an offset. At 00:05 UTC on Nov 21 it was already Nov 21 in Singapore: build "today" in `+08:00`, not UTC.
- **Units.** Station wind speed is in knots (`readingUnit`); the 24-hour forecast's `wind.speed` has no unit field, so the blocks print it bare. Temperature and humidity in the 24-hour forecast carry `unit` ("Degrees Celsius", "Percentage").
- **No caching headers.** Nothing tells a client how long an answer is good for. The datasets say "Updated every 30 minutes" (2-hour forecast), "every 5 minutes" (temperature, rainfall) and "every 15 minutes" (PSI, PM2.5); block 3 keeps answers for 60 s, which is plenty.
- **Band labels come from NEA's haze site, seen once while exploring.** www.haze.gov.sg showed "PSI Value Air Quality Descriptor 0 - 100 Good to Moderate 101 - 200 Unhealthy 201 - 300 Very Unhealthy 301 and above Hazardous" and 1-hr PM2.5 "Band 1 (Normal) (0 - 55 µg/m3)", "Band 2 (Elevated) (56 - 150 µg/m3)", Band 3 (High), "Band 4 (Very High) (251 and above µg/m3)". Its Terms of Use say you will not "use any robot, spider, other automatic device, or manual process to monitor or copy any pages within this Site", so no block fetches that site (the 4 exploratory page loads happened before its terms were read); use the data.gov.sg API instead.
- **Credit, no crest, no official look.** Print "Contains information from <dataset names> accessed on <date> from data.gov.sg which is made available under the terms of the Singapore Open Data Licence version 1.0" with https://data.gov.sg/open-data-licence (every block does), use no government crest or logo, and do not present the output as an official forecast or advisory.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.href` and page text, not the title.

## What does not work

- **api.data.gov.sg (v1)**: its robots.txt answers HTTP 403, so it cannot be checked; v1 paths on the v2 host (`/v2/real-time/api/environment/air-temperature`) are HTTP 404 `"Route not found"`. Use the v2 endpoints above.
- **Other date formats**: `?date=21-11-2026` is HTTP 400 "Invalid date format"; `?date=2026-13-01` is HTTP 400 "Invalid date value"; `?date=2014-01-01` (before the data starts; the PSI dataset lists "Feb 2016 to Nov 2026") is HTTP 404 `REAL_TIME_API_DATA_NOT_FOUND`.
- **`innerText` on the API list panel** (`/datasets?formats=API&resultId=...`): the API notes did not show in `innerText` at the cloud browser's window size; `textContent` has them (the `/datasets/<id>/view` page shows them in `innerText`).
- **Not tested:** a 429 (never provoked), API keys and their higher limits, the other real-time APIs (wind direction, 4-day forecast, lightning, WBGT, flood alerts, radar images), following `paginationToken` past page 2, and the dataset download and datastore search APIs.
