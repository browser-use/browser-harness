# NOAA Tides & Currents - High and Low Tides Today at a US Station (CO-OPS Data API)

Field-tested against api.tidesandcurrents.noaa.gov on 2026-11-09 (about 18:20 New York time) using a Browser Use cloud browser (logged out) plus `curl` and Python urllib from a laptop. About 20 browser requests and 35 plain HTTP calls, all serial at 2 s or more spacing: every data call was HTTP 200 except the deliberate missing-datum 400; no 429, no challenge, no key, no login.

robots.txt (checked 2026-11-09): api.tidesandcurrents.noaa.gov/robots.txt answers HTTP 403 `{"message":"Forbidden"}` to both curl and the cloud browser, so no file is served (RFC 9309: a 4xx means no rules); tidesandcurrents.noaa.gov/robots.txt is HTTP 404. No named AI-agent groups. Terms: the CO-OPS disclaimer (tidesandcurrents.noaa.gov/disclaimers.html) says "The information on government servers are in the public domain, unless specifically annotated otherwise, and may be used freely by the public", "shall not be modified in content and then presented as official government material", and "NOS requests that attribution be given whenever NOS material is reproduced and re-disseminated"; the API docs ask for sleeps between calls (per-customer throttling) and an `application` name; no key, no AI, scraping or non-commercial clause.

## Quick summary

- **No scraping.** `GET https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today&station=<id>&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&application=<your app>&format=json` returns the day's high (`H`) and low (`L`) tides with heights. `Access-Control-Allow-Origin: *`, `Cache-Control: no-cache, no-store, must-revalidate, max-age=0`.
- **Check the station ID.** The Battery, NYC is **8518750**. 8454000 is Providence, RI (its 2026-11-09 tides: L 00:11, H 07:40, L 12:53, H 20:00; The Battery: L 01:40, H 07:44, L 14:18, H 20:07). Block 2 checks names through the metadata API.
- **Station by name:** `GET /mdapi/prod/webapi/stations.json?type=tidepredictions` lists all 3,502 prediction stations (2 MB): `id`, `name` (`NEW YORK (The Battery)`), `state`, `lat`, `lng`, `type` (`R` 1,260 reference, `S` 2,242 subordinate). `/mdapi/prod/webapi/stations/<id>.json` gives one, with `name` `The Battery`.
- **`datum` is required** for predictions (HTTP 400 without it). `MLLW` is the chart datum tide tables use.
- **`time_zone=lst_ldt`** = station local time with daylight saving. `date=today` is the day in the time zone you ask for: with `gmt` The Battery's 2026-11-09 was H 00:27, L 06:40, H 12:44, L 19:18 (UTC), a different set of tides.
- **Most errors are HTTP 200** with `{"error": {"message": ...}}`. Check for the key; block 1 raises on it.
- **Range:** `begin_date=YYYYMMDD&end_date=YYYYMMDD` instead of `date`. Docs: high/low predictions up to 10 years per call, other intervals 1 year (on 2026-11-09 hourly predictions for 2025-09-01 to 2026-10-31, 14 months, still returned all 10,224 rows; do not rely on it).

## What works

### 1. Today's high and low tides at The Battery, plus where the water is now (browser)

Self-contained. Finds the station by name, gets today's high/low predictions, then compares the last 6-minute observation with the 6-minute prediction for the same minute. `fetch()` runs same-origin from the API docs page. `get_json()` raises on the API's HTTP-200 error objects and backs off on 429/5xx.

```python
import json, time, urllib.parse

PLACE, STATE = "battery", "NY"  # a substring of the station name, and its state; "NEW YORK (The Battery)" is CO-OPS 8518750
DATUM, UNITS = "MLLW", "english"  # MLLW = chart datum (heights in feet above mean lower low water)

HOST = "https://api.tidesandcurrents.noaa.gov"
DATA = HOST + "/api/prod/datagetter"
META = HOST + "/mdapi/prod/webapi/"
APP = "browser-harness-skill"  # the docs ask automated users to name themselves in `application`
PAUSE = 2.0  # the docs ask for sleeps between calls (throttling per customer, no published number)

def on_coops_tab():
    """fetch() runs from a logged-out tab on the API docs page, same origin as datagetter and mdapi. Reuse it if already there."""
    try:
        if js("location.origin") == HOST:
            return
    except Exception:
        pass
    new_tab(HOST + "/api/prod/")
    wait_for_load()
    if "CO-OPS Data Retrieval API" not in (js("document.title") or ""):
        raise RuntimeError(f"api.tidesandcurrents.noaa.gov did not serve the API docs (title {js('document.title')!r}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__co = window.__co || {}; const id = String(Math.random()).slice(2); window.__co[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__co[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__co[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__co[%s]; if (v) delete window.__co[%s]; return v; })()"""

def get_json(url, tries=3, timeout=90):
    """GET url from inside the tab -> parsed JSON. CO-OPS reports most bad requests as HTTP 200 with {"error": {"message": ...}}
    (missing datum is a 400), so both raise. Backs off 30 s on 429/5xx."""
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] == 200:
            d = json.loads(r["text"])
            if "error" in d:
                raise RuntimeError(f"{url}: {d['error']['message'].strip()}")
            return d
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
        time.sleep(30)

def data(**params):
    return get_json(DATA + "?" + urllib.parse.urlencode({**params, "units": UNITS, "application": APP, "format": "json"}))

on_coops_tab()

# 1. Station by name: 3,502 prediction stations (R = harmonic reference, S = subordinate; S gives high/low only)
stations = get_json(META + "stations.json?type=tidepredictions")["stations"]
hits = [s for s in stations if PLACE.lower() in s["name"].lower() and s["state"] == STATE]
print(f"{len(stations)} prediction stations; {PLACE!r} in {STATE}: {[(s['id'], s['name'], s['type']) for s in hits]}")
if len(hits) != 1:
    raise SystemExit("pick one station ID from the list above")
st = hits[0]
meta = get_json(META + f"stations/{st['id']}.json")["stations"][0]
print(f"station {meta['id']} {meta['name']}, {meta['state']} ({meta['lat']:.4f}, {meta['lng']:.4f}) tz {meta['timezone']} DST {meta['observedst']}")

# 2. Today's high and low tides, station local time (lst_ldt). date=today is the day in the time_zone you ask for.
hilo = data(date="today", station=st["id"], product="predictions", datum=DATUM, time_zone="lst_ldt", interval="hilo")["predictions"]
print(f"\nhigh/low tide predictions, {hilo[0]['t'][:10]} local, feet above {DATUM}:")
for p in hilo:
    print(f"  {'High' if p['type'] == 'H' else 'Low ':<4}  {p['t'][11:]}  {float(p['v']):5.2f} ft")

# 3. Is the water where it should be right now? Last observation of the past hour (6-min, preliminary) vs the 6-min prediction.
obs = data(range=1, station=st["id"], product="water_level", datum=DATUM, time_zone="lst_ldt")["data"][-1]
now = obs["t"]
if now[:10] != hilo[0]["t"][:10]:
    raise RuntimeError(f"latest observation is from {now}, not today ({hilo[0]['t'][:10]}): sensor gap or stale answer; stopping")
pred6 = {p["t"]: float(p["v"]) for p in data(date="today", station=st["id"], product="predictions", datum=DATUM,
                                                 time_zone="lst_ldt", interval="6")["predictions"]}
print(f"\nobserved {now} local: {float(obs['v']):.2f} ft (quality {obs['q']}: p = preliminary); predicted {pred6[now]:.2f} ft; "
      f"difference {float(obs['v']) - pred6[now]:+.2f} ft")
nxt = next((p for p in hilo if p["t"] > now), None)
print("next today:", f"{'high' if nxt['type'] == 'H' else 'low'} tide at {nxt['t'][11:]} ({float(nxt['v']):.2f} ft)" if nxt else "none left today")
print("page for people:", f"https://tidesandcurrents.noaa.gov/noaatidepredictions.html?id={st['id']}")
```

Output (from the run on 2026-11-09, 23:23 UTC):

```text
3502 prediction stations; 'battery' in NY: [('8518750', 'NEW YORK (The Battery)', 'R')]
station 8518750 The Battery, NY (40.7006, -74.0142) tz EST DST True

high/low tide predictions, 2026-11-09 local, feet above MLLW:
  Low   01:40   0.17 ft
  High  07:44   5.58 ft
  Low   14:18   0.04 ft
  High  20:07   4.55 ft

observed 2026-11-09 18:18 local: 3.34 ft (quality p: p = preliminary); predicted 3.73 ft; difference -0.39 ft
next today: high tide at 20:07 (4.55 ft)
page for people: https://tidesandcurrents.noaa.gov/noaatidepredictions.html?id=8518750
```

### 2. Several stations, with a name check, and the error shapes (plain HTTP, no browser)

Python standard library only, truthful User-Agent, 12 calls at 2 s spacing.

```python
import json, time, urllib.error, urllib.parse, urllib.request

# Station IDs are easy to mix up: 8454000 is Providence, RI, not New York. Check the name the API returns.
STATIONS = {"8518750": "The Battery", "8454000": "Providence", "8443970": "Boston", "9414290": "San Francisco"}

UA = {"User-Agent": "browser-harness-skill/1.0 (Python urllib)"}
HOST = "https://api.tidesandcurrents.noaa.gov"
PAUSE = 2.0  # the docs ask for sleeps between calls

def call(url):
    """GET -> (HTTP status, parsed JSON). Waits 30 s on 429/5xx, then stops."""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                status, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read()
        time.sleep(PAUSE)
        if status not in (429, 500, 502, 503, 504) or attempt == 2:
            return status, json.loads(body)
        time.sleep(30)

def tides(station, **extra):
    q = {"date": "today", "station": station, "product": "predictions", "datum": "MLLW", "time_zone": "lst_ldt",
         "interval": "hilo", "units": "english", "application": "browser-harness-skill", "format": "json", **extra}
    q = {k: v for k, v in q.items() if v is not None}  # pass datum=None to drop it
    return call(HOST + "/api/prod/datagetter?" + urllib.parse.urlencode(q))

for sid, expect in STATIONS.items():
    _, m = call(HOST + f"/mdapi/prod/webapi/stations/{sid}.json")
    name = f"{m['stations'][0]['name']}, {m['stations'][0]['state']}"
    status, d = tides(sid)
    if status != 200 or "error" in d:
        raise RuntimeError(f"{sid}: HTTP {status} {d}")
    row = "  ".join(f"{p['type']} {p['t'][11:]} {float(p['v']):5.2f}" for p in d["predictions"])
    print(f"{sid} {name:<18} {'ok ' if expect in name else 'NOT ' + expect}  {d['predictions'][0]['t'][:10]}  {row}")

# Errors: only a missing datum is an HTTP error; the rest are HTTP 200 with an "error" object
print()
for label, sid, extra in [("no datum", "8518750", {"datum": None}), ("unknown station", "9999999", {}),
                          ("subordinate station, hourly", "8518695", {"interval": "h"}),
                          ("subordinate station, hilo", "8518695", {})]:
    status, d = tides(sid, **extra)
    print(f"{label:<28} HTTP {status}  " + (d["error"]["message"].strip() if "error" in d else f"{len(d['predictions'])} predictions"))
```

Output (from the run on 2026-11-09, 23:24 UTC):

```text
8518750 The Battery, NY    ok   2026-11-09  L 01:40  0.17  H 07:44  5.58  L 14:18  0.04  H 20:07  4.55
8454000 Providence, RI     ok   2026-11-09  L 00:11  0.06  H 07:40  5.13  L 12:53  0.20  H 20:00  4.27
8443970 Boston, MA         ok   2026-11-09  L 04:38  0.88  H 10:49 10.46  L 17:12 -0.09  H 23:26  9.28
9414290 San Francisco, CA  ok   2026-11-09  L 04:25  2.68  H 10:35  6.19  L 17:24 -0.54

no datum                     HTTP 400  Wrong Datum: Datum cannot be null or empty  ***station=8518750
unknown station              HTTP 200  No Predictions data was found. Please make sure the Datum input is valid.
subordinate station, hourly  HTTP 200  No Predictions data was found. Please make sure the Datum input is valid.
subordinate station, hilo    HTTP 200  4 predictions
```

### 3. The next 7 days of tides as CSV (curl)

```bash
ST=8518750   # The Battery, NY
BEGIN=$(TZ=America/New_York date +%Y%m%d)
END=$(TZ=America/New_York date -v+6d +%Y%m%d 2>/dev/null || TZ=America/New_York date -d '+6 days' +%Y%m%d)   # BSD or GNU date
curl -sS --fail "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?begin_date=$BEGIN&end_date=$END&station=$ST&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&application=browser-harness-skill&format=csv" \
  | awk -F, 'NR==1 {next} {split($1, a, " "); if (a[1] != d) {if (d) print line; d = a[1]; line = d} line = line sprintf("  %s %s %5.2f", $3, a[2], $2)} END {print line}'
```

Output (from the run on 2026-11-09, 23:24 UTC):

```text
2026-11-09  L 01:40  0.17  H 07:44  5.58  L 14:18  0.04  H 20:07  4.55
2026-11-10  L 02:19  0.33  H 08:21  5.46  L 15:00  0.11  H 20:47  4.36
2026-11-11  L 02:57  0.50  H 08:58  5.26  L 15:40  0.25  H 21:30  4.15
2026-11-12  L 03:33  0.70  H 09:38  5.02  L 16:19  0.43  H 22:17  3.95
2026-11-13  L 04:08  0.91  H 10:20  4.77  L 16:58  0.64  H 23:09  3.79
2026-11-14  L 04:41  1.13  H 11:08  4.55  L 17:41  0.82
2026-11-15  H 00:02  3.70  L 05:19  1.33  H 11:59  4.38  L 18:31  0.95
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `t` | predictions, data | `YYYY-MM-DD HH:MM` in the `time_zone` asked for; no zone suffix |
| `v` | predictions, data | height as a string, feet (`english`) or metres (`metric`) above `datum`; can be negative (Boston L -0.09) |
| `type` | predictions (`interval=hilo`) | `H` or `L`; 3 or 4 per day, a day can start with either (2026-11-15 starts `H 00:02`) |
| `metadata` | water_level | `{id, name, lat, lon}`; predictions have no metadata |
| `s` | water_level | sigma, standard deviation of the 1-second samples |
| `f` | water_level | flags `O,F,R,L`: count of samples outside 3 sigma, flat tolerance, rate of change, max/min expected exceeded |
| `q` | water_level | `p` preliminary, `v` verified |
| `type` | stations.json | `R` harmonic reference station (any interval), `S` subordinate (high/low only, `reference_id` points at its reference) |

## Gotchas

- **Wrong station ID still returns plausible tides.** 8454000 (Providence, RI) answers like any NY station would. Confirm `name` from `/mdapi/prod/webapi/stations/<id>.json`.
- **Subordinate stations do high/low only.** `interval=h` on 8518695 (East 41st Street, NYC) is HTTP 200 `No Predictions data was found. Please make sure the Datum input is valid.`, the same message as an unknown station. The message blames the datum either way.
- **`date=latest` and `date=recent` answer each other's question.** Docs: `latest` = last point within 18 min, `recent` = last 3 days. On 2026-11-09, 8 alternating calls from the browser: `latest` gave the 720-point 3-day series 2 of 4 times, `recent` gave a single point 1 of 4 times; 3 of 3 `recent` calls from Python urllib gave a single point. Block 1 uses `range=1` (9 or 10 points, correct in every call that day), takes the last point and checks its date.
- **Predictions are astronomical.** Observed water at The Battery was 0.39 ft below prediction at 18:18; wind and pressure move it. Use `product=water_level` for what is happening.
- **No published rate limit.** The docs: CO-OPS throttles "the quantity / volume of data queries received from a singular customer" and recommends "sleep statements" between calls. The blocks sleep 2 s.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; block 1 matches a substring of the title only.

## What does not work

- **robots.txt on the API host:** HTTP 403 JSON, not a file. Nothing to follow; the API is the documented official access path.
- **The tidesandcurrents.noaa.gov HTML pages** (`/noaatidepredictions.html?id=8518750`, HTTP 200) are for people; link them, read data from the API.
- **Not tested:** currents (`currents`, `currents_predictions`), meteorological products, `datum` other than MLLW, rate limits (never provoked).
