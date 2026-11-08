# USGS Earthquakes - Latest M4.5+ Earthquakes Near a Place (FDSN event API + real-time GeoJSON feeds)

Field-tested against earthquake.usgs.gov on 2026-11-08 using a Browser Use cloud browser (logged out) plus `curl` from a laptop. About 60 browser requests (page loads and in-page `fetch()`) and 10 curl calls in all (block 3 makes 3), all serial: every earthquake.usgs.gov data call was HTTP 200 except the deliberate 400 probes below; the non-200 pages were the 404s for earthquake.usgs.gov/robots.txt and the Feed Lifecycle Policy link, and curl's CloudFront 403 on www.usgs.gov/robots.txt. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-08): earthquake.usgs.gov/robots.txt is HTTP 404 (no rules, no named AI-agent groups); www.usgs.gov/robots.txt (read in the browser; curl gets a CloudFront 403) has only `User-agent: *` (disallows /core/, /profiles/, /admin/, /search/, /user/login/ and similar) and this skill uses no www.usgs.gov path. Terms: no ToS for the API; the USGS Copyrights and Credits page says "USGS-authored or produced data and information are considered to be in the U.S. Public Domain" and asks that credit be given; the Liability page only disclaims warranties; no AI, scraping, key or non-commercial clause.

## Quick summary

- **No scraping.** Two official, keyless JSON sources, `Access-Control-Allow-Origin: *`, `cache-control: public, max-age=60`:
  - `GET https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&eventtype=earthquake&minmagnitude=4.5&latitude=..&longitude=..&maxradiuskm=500&starttime=..&orderby=time&limit=N` - any place, any time range. `count?` takes the same parameters and returns `{"count":15,"maxAllowed":20000}` (or plain text `15` without `format=geojson`).
  - `GET https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/<level>_<period>.geojson` - prebuilt worldwide lists, level `significant`, `4.5`, `2.5`, `1.0`, `all`; period `hour`, `day`, `week`, `month`; "Updated every minute". Filter by distance yourself.
- **Which one:** the API docs say "automated applications should use Real-time GeoJSON Feeds for displaying earthquake information whenever possible". Use a feed when the window fits (past 30 days or less); use `query` for older events or "the latest N, however old". Block 2 shows both return the same 6 events for Tokyo, past week.
- **Set `starttime`.** Without it the query searches only the last 30 days (docs default `NOW - 30 days`). London: 0 events by default, latest real one 2013-11-21 with `starttime=1900-01-01`.
- **Coordinates, not names.** The API has no geocoder; pass `latitude`/`longitude`. `properties.place` is USGS's own label ("43 km E of Onagawa Chō, Japan"), the nearest named locality, not your place. Distances are not returned; block 1 computes them (haversine).
- **Errors are plain-text HTTP 400** (`maxradius and maxradiuskm can not both be specified.`, `Bad limit value "20001". Valid values are 0 <= limit <= 20000`). Add `jsonerror=true` to get a GeoJSON body with `metadata.status: 400` and HTTP 200 instead.
- **Time/area limits are "being evaluated and are not enforced yet"** (docs). The listed future rule that fits this task: `orderby=time` with `limit` of 1,000 or less has no time-range limit.

## What works

### 1. Latest M4.5+ within 500 km of several places (browser, query API)

`on_usgs_tab()` opens the API docs page (`/fdsnws/event/1/`) once and later calls reuse that tab; `fetch()` there is same-origin. `get()` returns the response text on 200, backs off on 429/5xx and otherwise raises, so a 400 never looks like "no earthquakes".

```python
import json, math, time
from datetime import datetime, timedelta, timezone

PLACES = {  # name -> (latitude, longitude); USGS takes coordinates, not place names
    "Tokyo": (35.6762, 139.6503),
    "Anchorage": (61.2181, -149.9003),
    "Los Angeles": (34.0522, -118.2437),
    "Istanbul": (41.0082, 28.9784),
    "London": (51.5074, -0.1278),
}
RADIUS_KM, MIN_MAG, N = 500, 4.5, 5
SINCE = "1900-01-01"  # without starttime the service only searches the last 30 days

API = "https://earthquake.usgs.gov/fdsnws/event/1/"
PAUSE = 1.0  # no published rate limit; keep calls serial and slow

def on_usgs_tab():
    """fetch() runs from a logged-out earthquake.usgs.gov tab (the API docs page). Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://earthquake.usgs.gov":
            return
    except Exception:
        pass
    new_tab(API)
    wait_for_load()
    if "Earthquake Catalog" not in (js("document.title") or ""):
        raise RuntimeError(f"earthquake.usgs.gov did not serve the API docs (title {js('document.title')!r}): stop, do not retry around it")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__eq = window.__eq || {}; const id = String(Math.random()).slice(2); window.__eq[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__eq[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__eq[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__eq[%s]; if (v) delete window.__eq[%s]; return v; })()"""

def get(url, tries=3, timeout=60):
    """GET url from inside the tab -> response text. Errors are a plain-text 400 page; backs off on 429/5xx, else raises."""
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] == 200:
            return r["text"]
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
        time.sleep(30)

def km(lat1, lon1, lat2, lon2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))

def utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

on_usgs_tab()
print("service version:", get(API + "version"))
for name, (lat, lon) in PLACES.items():
    where = f"latitude={lat}&longitude={lon}&maxradiuskm={RADIUS_KM}&minmagnitude={MIN_MAG}&eventtype=earthquake"
    n30 = json.loads(get(API + "count?format=geojson&" + where))["count"]  # default window: last 30 days
    d = json.loads(get(API + f"query?format=geojson&{where}&starttime={SINCE}&orderby=time&limit={N}"))
    print(f"\n{name} ({lat}, {lon}): {n30} M{MIN_MAG}+ within {RADIUS_KM} km in the last 30 days; latest {len(d['features'])}:")
    for f in d["features"]:
        p, (elon, elat, depth) = f["properties"], f["geometry"]["coordinates"]
        dist = km(lat, lon, elat, elon)
        assert dist <= RADIUS_KM + 1, (f["id"], dist)
        flags = " ".join(x for x in [p["alert"] and f"PAGER {p['alert']}", p["tsunami"] and "tsunami-flag",
                                     p["felt"] and f"felt {p['felt']}"] if x)
        print(f"  {utc(p['time'])}  M{p['mag']:.1f} {p['magType']:<4} {dist:5.0f} km  depth {depth:5.1f} km  "
              f"{p['status']:<9} {p['place']}  {flags}".rstrip())
        print(f"      {f['id']}  {p['url']}")
```

Output (from the run on 2026-11-08):

```text
service version: 2.8.4

Tokyo (35.6762, 139.6503): 15 M4.5+ within 500 km in the last 30 days; latest 5:
  2026-11-08 20:16 UTC  M4.5 mwr    363 km  depth  55.7 km  reviewed  43 km E of Onagawa Chō, Japan
      us7000twz2  https://earthquake.usgs.gov/earthquakes/eventpage/us7000twz2
  2026-11-07 16:04 UTC  M5.5 mww    200 km  depth  38.1 km  reviewed  10 km NW of Hamakita, Japan  PAGER green felt 71
      us7000twt0  https://earthquake.usgs.gov/earthquakes/eventpage/us7000twt0
  2026-11-07 11:07 UTC  M5.5 mww    171 km  depth  31.7 km  reviewed  74 km NE of Hasaki, Japan  PAGER green felt 25
      us7000twrq  https://earthquake.usgs.gov/earthquakes/eventpage/us7000twrq
  2026-11-06 10:39 UTC  M6.1 mww    237 km  depth  29.0 km  reviewed  144 km SE of Hasaki, Japan  PAGER green felt 38
      us7000twg9  https://earthquake.usgs.gov/earthquakes/eventpage/us7000twg9
  2026-11-05 18:05 UTC  M4.6 mb     295 km  depth  87.4 km  reviewed  36 km E of Watari, Japan  felt 3
      us7000twaq  https://earthquake.usgs.gov/earthquakes/eventpage/us7000twaq

Anchorage (61.2181, -149.9003): 1 M4.5+ within 500 km in the last 30 days; latest 5:
  2026-10-15 11:07 UTC  M5.6 ml     364 km  depth   4.5 km  reviewed  43 km NNW of Lake Minchumina, Alaska  felt 107
      aka2026ukynnb  https://earthquake.usgs.gov/earthquakes/eventpage/aka2026ukynnb
  2026-10-06 18:34 UTC  M5.5 ml     339 km  depth  87.6 km  reviewed  92 km NNW of Aleneva, Alaska  PAGER green felt 342
      aka2026tuxgky  https://earthquake.usgs.gov/earthquakes/eventpage/aka2026tuxgky
  2026-08-08 04:50 UTC  M5.6 ml     173 km  depth  10.0 km  reviewed  57 km WNW of Skwentna, Alaska  felt 1137
      aka2026powmkf  https://earthquake.usgs.gov/earthquakes/eventpage/aka2026powmkf
  2026-07-28 20:49 UTC  M5.0 ml     269 km  depth   5.0 km  reviewed  52 km E of Denali National Park, Alaska  felt 164
      aka2026ovufno  https://earthquake.usgs.gov/earthquakes/eventpage/aka2026ovufno
  2026-07-16 11:37 UTC  M5.2 ml     459 km  depth   8.5 km  reviewed  122 km SE of McCarthy, Alaska  felt 11
      aka2026nyxoap  https://earthquake.usgs.gov/earthquakes/eventpage/aka2026nyxoap

Los Angeles (34.0522, -118.2437): 1 M4.5+ within 500 km in the last 30 days; latest 5:
  2026-11-03 18:27 UTC  M4.9 mw     337 km  depth  15.6 km  reviewed  9 km N of Delta, B.C., MX  PAGER green felt 320
      ci41572064  https://earthquake.usgs.gov/earthquakes/eventpage/ci41572064
  2026-05-10 07:10 UTC  M4.7 mw     276 km  depth  14.5 km  reviewed  3 km WSW of Brawley, CA  PAGER green felt 203
      ci41461608  https://earthquake.usgs.gov/earthquakes/eventpage/ci41461608
  2026-04-02 08:41 UTC  M4.6 mw     488 km  depth  10.4 km  reviewed  1 km SE of Boulder Creek, CA  PAGER green felt 33078
      nc75337442  https://earthquake.usgs.gov/earthquakes/eventpage/nc75337442
  2026-01-20 01:56 UTC  M4.9 mw     192 km  depth   3.1 km  reviewed  20 km NNE of Indio, CA  PAGER green felt 8214
      ci41162719  https://earthquake.usgs.gov/earthquakes/eventpage/ci41162719
  2025-06-29 02:37 UTC  M4.5 mw     364 km  depth  11.6 km  reviewed  8 km SSE of Deep Springs, CA  PAGER green felt 139
      nc75202001  https://earthquake.usgs.gov/earthquakes/eventpage/nc75202001

Istanbul (41.0082, 28.9784): 1 M4.5+ within 500 km in the last 30 days; latest 5:
  2026-10-30 10:45 UTC  M4.7 mb     427 km  depth  10.0 km  reviewed  42 km SE of Sykiá, Greece
      us7000tu7m  https://earthquake.usgs.gov/earthquakes/eventpage/us7000tu7m
  2026-04-11 14:31 UTC  M4.8 mww    197 km  depth  10.0 km  reviewed  16 km N of Simav, Turkey  felt 1
      us6000spb7  https://earthquake.usgs.gov/earthquakes/eventpage/us6000spb7
  2026-03-25 19:08 UTC  M4.9 mww    420 km  depth  10.0 km  reviewed  7 km E of Ouranoupolis, Greece  felt 55
      us7000s7l9  https://earthquake.usgs.gov/earthquakes/eventpage/us7000s7l9
  2026-03-09 06:21 UTC  M5.0 mww    323 km  depth  10.0 km  reviewed  13 km W of Gözler, Turkey  felt 6
      us7000s33s  https://earthquake.usgs.gov/earthquakes/eventpage/us7000s33s
  2026-01-23 21:24 UTC  M4.9 mww    209 km  depth   8.9 km  reviewed  10 km ESE of Sındırgı, Turkey  felt 8
      us7000rrq9  https://earthquake.usgs.gov/earthquakes/eventpage/us7000rrq9

London (51.5074, -0.1278): 0 M4.5+ within 500 km in the last 30 days; latest 5:
  2013-11-21 09:53 UTC  M4.5 mb     467 km  depth   4.0 km  reviewed  1 km WSW of Plescop, France  felt 10
      usb000l3gp  https://earthquake.usgs.gov/earthquakes/eventpage/usb000l3gp
  2008-02-27 00:56 UTC  M4.8 mb     211 km  depth  18.4 km  reviewed  1 km NNE of Market Rasen, United Kingdom  felt 13655
      usp000g02w  https://earthquake.usgs.gov/earthquakes/eventpage/usp000g02w
  2007-04-28 07:18 UTC  M4.6 mb      92 km  depth  10.0 km  reviewed  1 km WNW of Lympne, United Kingdom  felt 201
      usp000fase  https://earthquake.usgs.gov/earthquakes/eventpage/usp000fase
  2002-09-22 23:53 UTC  M4.8 mb     178 km  depth   9.4 km  reviewed  2 km ESE of Wombourn, United Kingdom
      usp000bcxg  https://earthquake.usgs.gov/earthquakes/eventpage/usp000bcxg
  2002-07-22 05:45 UTC  M4.8 mb     439 km  depth  17.2 km  reviewed  2 km ENE of Haanrade, Netherlands
      usp000b8j3  https://earthquake.usgs.gov/earthquakes/eventpage/usp000b8j3
```

### 2. Same task from the real-time feed, checked against the query API (browser)

The feed is the whole world (82 M4.5+ events in the past week); keep the earthquakes within the radius. The last call asks the query API for the same window, ending at the feed's build time, and diffs the event IDs.

```python
import json, math, time
from datetime import datetime, timezone

LAT, LON, NAME = 35.6762, 139.6503, "Tokyo"
RADIUS_KM = 500
FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"  # M4.5+, past 7 days, rebuilt every minute
API = "https://earthquake.usgs.gov/fdsnws/event/1/"

def on_usgs_tab():
    try:
        if js("location.origin") == "https://earthquake.usgs.gov":
            return
    except Exception:
        pass
    new_tab("https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php")  # the feed docs page
    wait_for_load()
    if "GeoJSON" not in (js("document.title") or ""):
        raise RuntimeError(f"earthquake.usgs.gov did not serve the feed docs (title {js('document.title')!r}): stop")

START_JS = """(() => { window.__eq = window.__eq || {}; const id = String(Math.random()).slice(2); window.__eq[id] = null;
  fetch(%s, {credentials: 'omit'}).then(async r => { window.__eq[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__eq[id] = {status: 0, text: String(e)}; }); return id; })()"""
POLL_JS = """(() => { const v = window.__eq[%s]; if (v) delete window.__eq[%s]; return v; })()"""

def get_json(url, timeout=60):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{url}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(1.0)
    if r["status"] != 200:
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
    return json.loads(r["text"])

def km(lat1, lon1, lat2, lon2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))

iso = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

on_usgs_tab()
feed = get_json(FEED)
m = feed["metadata"]
print(f"{m['title']}: {m['count']} events worldwide, generated {iso(m['generated'])} UTC")
near = sorted(((km(LAT, LON, f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]), f) for f in feed["features"]
               if f["properties"]["type"] == "earthquake"  # the feed also carries other event types
               and km(LAT, LON, f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]) <= RADIUS_KM),
              key=lambda x: -x[1]["properties"]["time"])
print(f"within {RADIUS_KM} km of {NAME}: {len(near)}")
for d, f in near:
    p = f["properties"]
    print(f"  {iso(p['time'])}  M{p['mag']:.1f} {p['magType']:<4} {d:4.0f} km  {p['type']:<10} {p['place']}  ({f['id']})")

# Same window through the query API, ending at the feed's build time, to show the two agree.
oldest = min(f["properties"]["time"] for f in feed["features"])
q = get_json(API + f"query?format=geojson&minmagnitude=4.5&eventtype=earthquake&latitude={LAT}&longitude={LON}&maxradiuskm={RADIUS_KM}"
             f"&starttime={iso(oldest)}&endtime={iso(m['generated'])}&orderby=time")
a, b = {f["id"] for _, f in near}, {f["id"] for f in q["features"]}
print(f"query API, same window: {len(b)} events; only in feed {sorted(a - b)}, only in query {sorted(b - a)}")
```

Output (from the run on 2026-11-08):

```text
USGS Magnitude 4.5+ Earthquakes, Past Week: 82 events worldwide, generated 2026-11-08T23:47:25 UTC
within 500 km of Tokyo: 6
  2026-11-08T20:16:30  M4.5 mwr   363 km  earthquake 43 km E of Onagawa Chō, Japan  (us7000twz2)
  2026-11-07T16:04:35  M5.5 mww   200 km  earthquake 10 km NW of Hamakita, Japan  (us7000twt0)
  2026-11-07T11:07:43  M5.5 mww   171 km  earthquake 74 km NE of Hasaki, Japan  (us7000twrq)
  2026-11-06T10:39:27  M6.1 mww   237 km  earthquake 144 km SE of Hasaki, Japan  (us7000twg9)
  2026-11-05T18:05:43  M4.6 mb    295 km  earthquake 36 km E of Watari, Japan  (us7000twaq)
  2026-11-03T05:40:18  M4.8 mwr    90 km  earthquake 6 km S of Asahi, Japan  (us7000tv3q)
query API, same window: 6 events; only in feed [], only in query []
```

### 3. Same API with curl (no browser)

curl's default User-Agent got HTTP 200 on earthquake.usgs.gov (www.usgs.gov answered curl with a CloudFront 403, but this skill never calls it).

```bash
LAT=34.0522; LON=-118.2437   # Los Angeles
Q="https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&eventtype=earthquake&minmagnitude=4.5&latitude=$LAT&longitude=$LON&maxradiuskm=500&starttime=1900-01-01&orderby=time&limit=3"
curl -sS --fail "$Q" | python3 -c '
import json, sys
from datetime import datetime, timezone
d = json.load(sys.stdin)
m = d["metadata"]
print(m["title"], "| api", m["api"], "| limit", m.get("limit"), "| count", m.get("count"), "| features", len(d["features"]))
for f in d["features"]:
    p, c = f["properties"], f["geometry"]["coordinates"]
    t = datetime.fromtimestamp(p["time"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(t, "M%.1f" % p["mag"], p["magType"], p["place"], "| lat %.3f lon %.3f depth %.1f km" % (c[1], c[0], c[2]), "|", f["id"])
'
sleep 1
echo "$(curl -sS "https://earthquake.usgs.gov/fdsnws/event/1/count?eventtype=earthquake&minmagnitude=4.5&latitude=$LAT&longitude=$LON&maxradiuskm=500&starttime=2026-01-01") M4.5+ within 500 km since 2026-01-01"
sleep 1
curl -sS -o /dev/null -w 'both maxradius and maxradiuskm: HTTP %{http_code}\n' "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude=$LAT&longitude=$LON&maxradiuskm=500&maxradius=3"
```

Output (from the run on 2026-11-08):

```text
USGS Earthquakes | api 2.8.4 | limit 3 | count None | features 3
2026-11-03 18:27 UTC M4.9 mw 9 km N of Delta, B.C., MX | lat 32.431 lon -115.180 depth 15.6 km | ci41572064
2026-05-10 07:10 UTC M4.7 mw 3 km WSW of Brawley, CA | lat 32.971 lon -115.562 depth 14.5 km | ci41461608
2026-04-02 08:41 UTC M4.6 mw 1 km SE of Boulder Creek, CA | lat 37.116 lon -122.112 depth 10.4 km | nc75337442
4 M4.5+ within 500 km since 2026-01-01
both maxradius and maxradiuskm: HTTP 400
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `id` | feature | event ID, network prefix + code (`us7000twz2`, `ci41572064`, `aka2026ukynnb`) |
| `geometry.coordinates` | feature | `[longitude, latitude, depth_km]`: longitude first |
| `mag`, `magType` | properties | `mww`, `mwr`, `mw`, `mb`, `ml`, ...; Californian `ci` events carry unrounded values (`4.8869503562808`) |
| `place`, `title` | properties | USGS label of the nearest locality; `title` = `M 4.9 - 9 km N of Delta, B.C., MX` |
| `time`, `updated` | properties | epoch **milliseconds**, UTC |
| `tz` | properties | `null` in every record checked; compute local time yourself |
| `url`, `detail` | properties | event page; `detail` is a GeoJSON URL with all products |
| `status` | properties | `automatic` or `reviewed`; filter with `reviewstatus=` |
| `alert` | properties | PAGER level `green`/`yellow`/`orange`/`red` or `null`; filter with `alertlevel=` / `minalertlevel=` |
| `tsunami` | properties | integer flag, `0` or `1` |
| `felt`, `cdi`, `mmi`, `sig` | properties | Did You Feel It? report count, max community intensity, ShakeMap max intensity, significance |
| `ids`, `sources`, `types` | properties | comma-wrapped lists: `,ew1793730460,ci41572064,us7000tvs2,` = one event known under three network IDs; `types` lists products (`shakemap`, `losspager`, `dyfi`, `moment-tensor`, ...) |
| `type` | properties | `earthquake` or another event type; the docs: `eventtype=earthquake` "will filter non-earthquake events" |
| `metadata.count` | collection | present without `limit`; with `limit` the metadata has `limit` and `offset` instead (block 3: `count None`) |
| `metadata.generated`, `metadata.api` | collection | ms timestamp of the build; query API 2.8.4, feeds 2.8.2 on 2026-11-08 |

## Gotchas

- **Not every event is an earthquake.** Without `eventtype=earthquake` the API also returns other types: 554 M4.5+ events since 1900 are typed `nuclear explosion` (2026-11-08). The blocks filter on it; the feeds cannot, so block 2 checks `properties.type`.
- **Default window is 30 days** for both `query` and `count`. Anchorage: `count` said 1 (Oct 15) while the latest-5 list with `starttime=1900-01-01` also showed Oct 6, July and August events.
- **`minmagnitude` is inclusive.** The docs say "larger than", but M4.5 events come back for `minmagnitude=4.5` (Tokyo us7000twz2, London 2013).
- **`nodata=404` does not change GeoJSON.** No match is HTTP 200 with `"features":[]` and `count: 0`, with or without `nodata`.
- **`maxradius` is degrees, `maxradiuskm` is km;** sending both is a 400. `maxradiuskm` max is 20001.6.
- **One event, several IDs.** `ids` lists network aliases; dedupe on `id` and treat any alias as the same event if you merge sources.
- **60 s cache.** Query and feed responses send `cache-control: public, max-age=60`, and feeds are "Updated every minute"; check `metadata.generated` for the snapshot time.
- **`count` output format** is plain text unless `format=geojson` is set.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks match on substrings of the title only.

## What does not work

- **Place names:** no `place=` or geocoding parameter. Bring coordinates.
- **Feed Lifecycle Policy:** linked from every feed page (`/earthquakes/feed/policy.php`) but HTTP 404 on 2026-11-08.
- **Not tested:** `detail` GeoJSON products beyond listing their names, ATOM/KML/CSV/QuakeML formats, `updatedafter` polling, `offset` paging past 20,000, rate limiting (no limit is published; never provoked).
