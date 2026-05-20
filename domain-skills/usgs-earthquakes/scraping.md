# USGS Earthquake Hazards Program API

`https://earthquake.usgs.gov` — completely free, no authentication, no API key. Two distinct interfaces: the **Feed API** (static pre-built snapshots, fastest) and the **Query API** (flexible filtering, historical data).

No browser needed. All calls are plain HTTP GETs handled by `http_get`.

---

## Fastest path: recent earthquakes via Feed API

Pick a feed and call it directly. Results are cached server-side and return in well under 1 second.

```python
import json
from helpers import http_get

# All earthquakes in the past hour
raw = http_get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson")
data = json.loads(raw)

print(data['metadata'])
# {'generated': 1776559120000, 'url': '...', 'title': 'USGS All Earthquakes, Past Hour',
#  'status': 200, 'api': '2.3.0', 'count': 13}

for feature in data['features']:
    props = feature['properties']
    coords = feature['geometry']['coordinates']  # [lon, lat, depth_km]
    lon, lat, depth_km = coords[0], coords[1], coords[2]
    print(f"M{props['mag']} at {props['place']} | depth {depth_km}km | id={feature['id']}")
```

---

## Feed URL patterns

All 20 combinations work. Replace `{mag}` and `{window}`:

```
https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{mag}_{window}.geojson
```

| `{mag}` | Threshold |
|---------|-----------|
| `all` | No lower bound |
| `1.0` | M1.0+ |
| `2.5` | M2.5+ |
| `4.5` | M4.5+ |
| `significant` | Significant events (high impact, large sig score) |

| `{window}` | Time range |
|------------|------------|
| `hour` | Past 1 hour |
| `day` | Past 24 hours |
| `week` | Past 7 days |
| `month` | Past 30 days |

Approximate event counts (verified 2026-04):

| Feed | Approx count |
|------|-------------|
| `all_hour` | ~5–30 |
| `all_day` | ~240 |
| `all_week` | ~1,700 |
| `all_month` | ~11,500 |
| `2.5_week` | ~370 |
| `4.5_day` | ~25 |
| `significant_month` | ~8 |

`all_month` transfers a few MB of JSON — parse it once, don't poll it repeatedly.

---

## GeoJSON structure

Every feed and query response is a GeoJSON `FeatureCollection`:

```python
{
  "type": "FeatureCollection",
  "metadata": {
    "generated": 1776559120000,   # ms epoch, when the feed was generated
    "url": "https://...",
    "title": "USGS All Earthquakes, Past Hour",
    "status": 200,
    "api": "2.3.0",
    "count": 13                   # total features in this response
  },
  "bbox": [-179.6701, -32.4116, 10, 161.575, 51.42, 198.753],
                # [minLon, minLat, minDepth, maxLon, maxLat, maxDepth]
  "features": [...]
}
```

Each `feature`:

```python
{
  "type": "Feature",
  "id": "hv74938567",             # event ID, network-prefixed
  "geometry": {
    "type": "Point",
    "coordinates": [-155.394165039062, 19.0879993438721, 45.2900009155273]
    #               ^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^
    #               longitude (E=+)      latitude (N=+)      depth in km
  },
  "properties": {
    "mag":       1.78,            # Richter/moment magnitude; can be None for unreviewed
    "magType":   "md",            # magnitude method: mww, mw, ml, md, mb, ...
    "place":     "15 km SE of Pāhala, Hawaii",
    "time":      1776558489040,   # ms since Unix epoch (UTC) — divide by 1000 for seconds
    "updated":   1776558697000,   # ms epoch of last update
    "tz":        None,            # deprecated, always None
    "url":       "https://earthquake.usgs.gov/earthquakes/eventpage/hv74938567",
    "detail":    "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=hv74938567&format=geojson",
    "felt":      None,            # number of "Did You Feel It?" reports; None if none
    "cdi":       None,            # max reported intensity (DYFI), 1-10; None if no reports
    "mmi":       None,            # max estimated ShakeMap intensity; None if not computed
    "alert":     None,            # PAGER alert level: "green"/"yellow"/"orange"/"red"/None
    "status":    "automatic",     # "automatic" or "reviewed"
    "tsunami":   0,               # 1 if tsunami message issued, else 0 (integer, not bool)
    "sig":       49,              # significance 0-1000 (combines mag, felt reports, PAGER)
    "net":       "hv",            # network that authored the event
    "code":      "74938567",      # network-specific event code
    "ids":       ",hv74938567,",  # all associated IDs (comma-delimited with leading/trailing commas)
    "sources":   ",hv,",          # networks contributing data
    "types":     ",origin,phase-data,",  # product types available
    "nst":       8,               # number of seismic stations used
    "dmin":      0.1488,          # min distance to station (degrees)
    "rms":       0.05,            # root-mean-square travel time residual (seconds)
    "gap":       282,             # largest azimuthal gap (degrees); >180 = poorly constrained
    "type":      "earthquake",    # event type: "earthquake", "quarry blast", "ice quake", etc.
    "title":     "M 1.8 - 15 km SE of Pāhala, Hawaii"
  }
}
```

---

## Critical gotchas

**Coordinates are [longitude, latitude, depth] — NOT [lat, lon].**

```python
coords = feature['geometry']['coordinates']
lon     = coords[0]   # longitude (west is negative)
lat     = coords[1]   # latitude  (south is negative)
depth_km = coords[2]  # depth in kilometers below surface
```

**Time is milliseconds since epoch, not seconds.**

```python
import datetime
props = feature['properties']
dt = datetime.datetime.fromtimestamp(props['time'] / 1000, tz=datetime.timezone.utc)
# props['time'] = 1776558489040  →  dt = 2026-04-19T12:28:09.040000+00:00
```

**`mag` can be `None`.** Automatic detections may not have a computed magnitude yet.

```python
mags = [f['properties']['mag'] for f in data['features'] if f['properties']['mag'] is not None]
```

**`tsunami` is an integer (0 or 1), not a boolean.** `if props['tsunami']:` works, but `props['tsunami'] == True` does not.

**`ids` has leading and trailing commas.** To get a clean list:

```python
ids = props['ids'].strip(',').split(',')  # ['hv74938567']
```

**`gap` > 180 means the hypocenter location is unreliable.** The azimuthal gap is the largest angle between adjacent stations; high values indicate poor station coverage.

---

## Query API

Use when you need historical data, filtering by geography, or a specific event.

Base URL: `https://earthquake.usgs.gov/fdsnws/event/1/query`

Always include `format=geojson`. Response structure is identical to feeds, with additional `limit` and `offset` in `metadata`.

### Parameters reference

| Parameter | Type | Description |
|-----------|------|-------------|
| `starttime` | ISO datetime or date | Start of time window (UTC). `2024-01-01` or `2024-01-01T07:00:00` |
| `endtime` | ISO datetime or date | End of time window (default: now) |
| `minmagnitude` | float | Lower magnitude bound (inclusive) |
| `maxmagnitude` | float | Upper magnitude bound (inclusive) |
| `mindepth` | float | Min depth in km |
| `maxdepth` | float | Max depth in km |
| `latitude` | float | Center latitude for radius search |
| `longitude` | float | Center longitude for radius search |
| `maxradiuskm` | float | Radius in km (use with lat/lon) |
| `maxradius` | float | Radius in degrees (use with lat/lon, alternative to maxradiuskm) |
| `minlatitude` | float | Rectangle south boundary |
| `maxlatitude` | float | Rectangle north boundary |
| `minlongitude` | float | Rectangle west boundary |
| `maxlongitude` | float | Rectangle east boundary |
| `limit` | int | Max results per response; hard max is **20000** (400 if over) |
| `offset` | int | 1-based offset for pagination (default: 1) |
| `orderby` | string | `time` (default, newest first), `time-asc`, `magnitude`, `magnitude-asc` |
| `eventid` | string | Fetch a single event by ID |

### Date range + magnitude

```python
import json
from helpers import http_get

raw = http_get(
    "https://earthquake.usgs.gov/fdsnws/event/1/query"
    "?format=geojson"
    "&starttime=2024-01-01"
    "&endtime=2024-01-07"
    "&minmagnitude=5.0"
    "&limit=10"
)
data = json.loads(raw)
print(data['metadata'])
# {'generated': ..., 'limit': 10, 'offset': 1, 'count': 10, ...}

for f in data['features']:
    p = f['properties']
    print(f"M{p['mag']} {p['place']}")
# M5.5 southern East Pacific Rise
# M5.5 31 km NNW of Pisco, Peru
# ...
```

### Largest earthquakes in a month

```python
import json
from helpers import http_get

raw = http_get(
    "https://earthquake.usgs.gov/fdsnws/event/1/query"
    "?format=geojson"
    "&starttime=2024-01-01"
    "&endtime=2024-01-31"
    "&minmagnitude=6.0"
    "&orderby=magnitude"
    "&limit=5"
)
data = json.loads(raw)
for f in data['features']:
    p = f['properties']
    print(f"M{p['mag']} — {p['place']}")
# M7.5 — 2024 Noto Peninsula, Japan Earthquake
# M7.0 — 128 km WNW of Aykol, China
# M6.7 — 93 km SE of Sarangani, Philippines
# M6.6 — 123 km NW of Tarauacá, Brazil
# M6.5 — 70 km W of Tarauacá, Brazil
```

### Radius search (nearest events to a point)

```python
import json
from helpers import http_get

# Earthquakes within 100 km of San Francisco, M3+
raw = http_get(
    "https://earthquake.usgs.gov/fdsnws/event/1/query"
    "?format=geojson"
    "&latitude=37.7"
    "&longitude=-122.4"
    "&maxradiuskm=100"
    "&minmagnitude=3.0"
    "&limit=10"
    "&orderby=time"
)
data = json.loads(raw)
for f in data['features']:
    p = f['properties']
    g = f['geometry']['coordinates']
    print(f"M{p['mag']} depth={g[2]}km — {p['place']}")
```

### Bounding box (rectangle) search

```python
import json
from helpers import http_get

# Western US, Jan 2024, M3+
raw = http_get(
    "https://earthquake.usgs.gov/fdsnws/event/1/query"
    "?format=geojson"
    "&starttime=2024-01-01"
    "&endtime=2024-01-31"
    "&minlatitude=30"
    "&maxlatitude=50"
    "&minlongitude=-130"
    "&maxlongitude=-110"
    "&minmagnitude=3.0"
    "&limit=20"
)
data = json.loads(raw)
print(f"{len(data['features'])} events")
```

### Depth filter (deep earthquakes)

```python
import json
from helpers import http_get

# Deep-focus earthquakes (> 100 km), M5+
raw = http_get(
    "https://earthquake.usgs.gov/fdsnws/event/1/query"
    "?format=geojson"
    "&starttime=2024-01-01"
    "&endtime=2024-01-07"
    "&minmagnitude=5.0"
    "&mindepth=100"
    "&limit=10"
)
data = json.loads(raw)
for f in data['features']:
    p = f['properties']
    depth = f['geometry']['coordinates'][2]
    print(f"M{p['mag']} depth={depth}km — {p['place']}")
# M5.7 depth=197km — 125 km W of Houma, Tonga
# M5.0 depth=137km — Banda Sea
```

### Offset pagination (> 20,000 results)

The Query API hard-caps at `limit=20000` per request (HTTP 400 if exceeded). For large windows, paginate with `offset`:

```python
import json
from helpers import http_get

def query_all(starttime, endtime, minmagnitude=0.0):
    """Paginate through all matching events."""
    results = []
    offset = 1
    limit = 10000
    while True:
        raw = http_get(
            f"https://earthquake.usgs.gov/fdsnws/event/1/query"
            f"?format=geojson"
            f"&starttime={starttime}"
            f"&endtime={endtime}"
            f"&minmagnitude={minmagnitude}"
            f"&orderby=time-asc"
            f"&limit={limit}"
            f"&offset={offset}"
        )
        data = json.loads(raw)
        batch = data['features']
        results.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return results
```

---

## Count endpoint

Returns a plain integer count (no features). Use to check result size before fetching.

```python
from helpers import http_get
import json

# Plain text response (default)
count_txt = http_get(
    "https://earthquake.usgs.gov/fdsnws/event/1/count"
    "?starttime=2024-01-01"
    "&endtime=2024-12-31"
    "&minmagnitude=6.0"
)
print(count_txt.strip())  # "99"

# JSON response (includes maxAllowed)
count_json = http_get(
    "https://earthquake.usgs.gov/fdsnws/event/1/count"
    "?format=geojson"
    "&starttime=2024-01-01"
    "&endtime=2024-01-31"
    "&minmagnitude=5.0"
)
obj = json.loads(count_json)
print(obj)  # {"count": 132, "maxAllowed": 20000}
```

---

## Event detail (full metadata)

The `detail` property in each feature is the full-detail URL. Fetch it for origin products, ShakeMap, moment tensor, phase data, PAGER, etc.

```python
import json
from helpers import http_get

# Method 1: use detail URL from feed/query feature
feature_detail_url = "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us6000m0xl&format=geojson"
raw = http_get(feature_detail_url)
detail = json.loads(raw)

# detail is a single Feature (not FeatureCollection)
print(detail['type'])          # "Feature"
print(detail['id'])            # "us6000m0xl"

p = detail['properties']
print(p['mag'])                # 7.5
print(p['status'])             # "reviewed"
print(list(p['products'].keys()))
# ['dyfi', 'earthquake-name', 'finite-fault', 'general-text', 'ground-failure',
#  'impact-link', 'impact-text', 'internal-origin', 'losspager', 'moment-tensor',
#  'origin', 'phase-data', 'shakemap']

# Method 2: fetch from the short detail URL in feed properties
# feed_feature['properties']['detail'] is already the right URL
```

### Extracting origin product properties

```python
origin = p['products']['origin'][0]  # list, take first (preferred)
op = origin['properties']
print(op['depth'])              # "10" (strings, not numbers)
print(op['latitude'])           # "37.4874"
print(op['longitude'])          # "137.2710"
print(op['num-phases-used'])    # "284"
print(op['standard-error'])     # "0.55"
print(op['azimuthal-gap'])      # "36"
print(op['review-status'])      # "reviewed"
```

All values inside product `properties` dicts are **strings**, including numeric ones. Cast as needed.

---

## Catalogs and contributors (XML)

These endpoints return XML, not JSON:

```python
from helpers import http_get

catalogs_xml = http_get("https://earthquake.usgs.gov/fdsnws/event/1/catalogs")
# <?xml version="1.0"?><Catalogs><Catalog>ak</Catalog><Catalog>ci</Catalog>...

contributors_xml = http_get("https://earthquake.usgs.gov/fdsnws/event/1/contributors")
# <?xml version="1.0"?><Contributors><Contributor>ak</Contributor>...

# Parse with stdlib
import xml.etree.ElementTree as ET
root = ET.fromstring(catalogs_xml)
catalogs = [c.text for c in root.findall('Catalog')]
# ['20', '38457511', '=c', 'aacse', 'ak', 'at', 'atlas', 'av', 'ci', 'hv', ...]

root2 = ET.fromstring(contributors_xml)
contributors = [c.text for c in root2.findall('Contributor')]
# ['admin', 'ak', 'at', 'atlas', 'av', 'ci', 'ew', 'hv', 'nc', 'nm', ...]
```

Network codes: `ak`=Alaska, `ci`=Southern California, `hv`=Hawaii, `nc`=Northern California, `us`=USGS national network, `uw`=Pacific Northwest.

---

## Feed vs Query API

| | Feed API | Query API |
|---|---------|-----------|
| URL pattern | `/feed/v1.0/summary/{mag}_{window}.geojson` | `/fdsnws/event/1/query?format=geojson&...` |
| Speed | Very fast (pre-cached, CDN) | Slower (live DB query) |
| Data freshness | Updated every 1–5 minutes | Real-time |
| Time windows | Fixed: hour/day/week/month | Any range back to 1900s |
| Filtering | Only by magnitude tier | Full filtering |
| Pagination | None (full result) | `limit`+`offset` |
| Max events | ~11,500 (all_month) | 20,000 per request |
| Use for | Dashboards, monitoring, latest data | Historical analysis, specific regions |

---

## Rate limits and best practices

No documented rate limit. The USGS operates the API as a public service. Practical guidance:

- Feed API: poll at most once per minute — feeds update every 1–5 minutes
- Query API: space requests by at least 1 second for bulk operations
- Do not fetch `all_month` in a tight loop — it's ~11K events and several MB
- Use `2.5_week` or `4.5_day` for monitoring; use Query API for historical analysis
- The `count` endpoint is cheap — use it before large paginated queries to estimate total records

---

## Common patterns

### Convert epoch ms to datetime

```python
import datetime

ms_epoch = 1776558489040
dt = datetime.datetime.fromtimestamp(ms_epoch / 1000, tz=datetime.timezone.utc)
# datetime.datetime(2026, 4, 19, 12, 28, 9, 40000, tzinfo=datetime.timezone.utc)
dt.isoformat()  # '2026-04-19T12:28:09.040000+00:00'
```

### Filter significant events from a feed

```python
import json
from helpers import http_get

raw = http_get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson")
data = json.loads(raw)

# Events with tsunami flag, M5+, or high significance score
notable = [
    f for f in data['features']
    if (f['properties']['mag'] or 0) >= 5.0
    or f['properties']['tsunami'] == 1
    or f['properties']['sig'] >= 600
]
print(f"{len(notable)} notable events this week")
```

### Check if event is well-constrained

```python
def is_well_located(feature):
    props = feature['properties']
    gap = props.get('gap')
    nst = props.get('nst')
    return (
        props['status'] == 'reviewed'
        and gap is not None and gap < 180
        and nst is not None and nst >= 10
    )
```

### Bulk fetch for a region using threading

```python
import json
from helpers import http_get
from concurrent.futures import ThreadPoolExecutor

def fetch_month(year, month):
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    raw = http_get(
        f"https://earthquake.usgs.gov/fdsnws/event/1/query"
        f"?format=geojson"
        f"&starttime={year}-{month:02d}-01"
        f"&endtime={year}-{month:02d}-{last_day}"
        f"&minmagnitude=4.5"
        f"&limit=20000"
    )
    return json.loads(raw)['features']

# Fetch 6 months in parallel (be respectful — small pool)
months = [(2024, m) for m in range(1, 7)]
with ThreadPoolExecutor(max_workers=3) as pool:
    all_results = list(pool.map(lambda ym: fetch_month(*ym), months))
events = [e for batch in all_results for e in batch]
print(f"Total M4.5+ events H1 2024: {len(events)}")
```
