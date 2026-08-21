# Overpass API — OSM Spatial Query Engine

`https://overpass-api.de` — read-only query engine over the full OpenStreetMap planet. No auth required, fully public. **Never use the browser — everything is a direct HTTP call.**

Two public endpoints (use FR mirror when main is slow):
- **Main**: `https://overpass-api.de/api/interpreter`
- **FR mirror**: `https://overpass.openstreetmap.fr/api/interpreter` — usually more responsive

**Do not use `http_get` without overriding `User-Agent`** — its default `Mozilla/5.0` is blocked with HTTP 403. Pass `headers={"User-Agent": "browser-harness/1.0"}` on every call.

---

## Fastest path: POST a QL query, get JSON

```python
import json, urllib.parse, urllib.request, gzip
from helpers import http_get  # http_get is GET-only; use urllib for POST

OVERPASS = "https://overpass.openstreetmap.fr/api/interpreter"

def overpass_post(query: str) -> list[dict]:
    """POST an Overpass QL query. Returns elements list. Raises on HTML error."""
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS, data=data, method="POST",
        headers={
            "User-Agent": "browser-harness/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip",
        }
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    body = body.decode()
    if not body.startswith("{"):
        raise RuntimeError(f"Overpass error (HTML): {body[:300]}")
    return json.loads(body)["elements"]

# Cafes in lower Manhattan bbox (south_lat, west_lon, north_lat, east_lon)
cafes = overpass_post(
    '[out:json][timeout:25]; node["amenity"="cafe"](40.70,-74.02,40.73,-73.97); out body 10;'
)
# cafes[0] == {'type': 'node', 'id': ..., 'lat': 40.7033, 'lon': -74.0141, 'tags': {'amenity': 'cafe', 'name': 'Starbucks', ...}}
for c in cafes:
    print(c["tags"].get("name", "?"), c["lat"], c["lon"])
# Starbucks      40.7033 -74.0141
# 9th St Espresso 40.7251 -73.9778
# Think Coffee   40.7254 -73.9924
```

---

## GET form (simpler, subject to URL length limits)

Use `http_get` when the query is short enough. For complex multi-statement QL, use POST.

```python
import json, urllib.parse
from helpers import http_get

UA = {"User-Agent": "browser-harness/1.0"}
OVERPASS = "https://overpass.openstreetmap.fr/api/interpreter"

def overpass_get(query: str) -> list[dict]:
    url = f"{OVERPASS}?data={urllib.parse.quote(query)}"
    raw = http_get(url, headers=UA)
    if not raw.startswith("{"):
        raise RuntimeError(f"Overpass error (HTML): {raw[:200]}")
    return json.loads(raw)["elements"]

# Same query via GET — confirmed working 2026-04-19
cafes = overpass_get('[out:json][timeout:25]; node["amenity"="cafe"](40.728,-73.990,40.730,-73.988); out body 5;')
# cafes[0] == {'type': 'node', 'id': ..., 'lat': 40.7298, 'lon': -73.9895, 'tags': {'name': 'The Bean', ...}}
```

---

## Example queries (all confirmed 2026-04-19)

### Bbox search — cafes, ATMs, restaurants

```python
# ATMs in Manhattan
atms = overpass_post(
    '[out:json][timeout:25]; node["amenity"="atm"](40.70,-74.02,40.80,-73.93); out body 10;'
)
# atms[0]['tags'].get('operator') == 'Bank of America'

# Restaurants within 300m radius of Times Square (around filter)
rests = overpass_post(
    '[out:json][timeout:25]; node["amenity"="restaurant"](around:300,40.7580,-73.9855); out body 10;'
)
# rests[0]['tags'] == {'name': 'Hard Rock Cafe', 'cuisine': 'american', ...}

# Multiple AND filters: cafes with outdoor seating
cafes = overpass_post(
    '[out:json][timeout:25]; node["amenity"="cafe"]["outdoor_seating"="yes"](40.70,-74.02,40.73,-73.97); out body 10;'
)
# cafes[0]['tags']['outdoor_seating'] == 'yes'
```

### Count query — how many results exist

```python
# Count pharmacies in London bbox (no element data returned)
r = overpass_post(
    '[out:json][timeout:25]; node["amenity"="pharmacy"](51.45,-0.15,51.55,0.0); out count;'
)
# r is a list with one element: {'type': 'count', 'id': 0, 'tags': {'nodes': '169', 'ways': '0', 'relations': '0', 'total': '169'}}
count = int(r[0]["tags"]["total"])  # 169
```

### Regex and case-insensitive filters

```python
# Regex match on tag value — any cafe OR coffee amenity
r = overpass_post(
    '[out:json][timeout:25]; node["amenity"~"cafe|coffee"](40.72,-73.99,40.73,-73.98); out body 5;'
)

# Case-insensitive name search — anything containing "star"
r = overpass_post(
    '[out:json][timeout:25]; node["name"~"star",i](40.75,-73.99,40.76,-73.97); out body 5;'
)
# r[0]['tags']['name'] == 'Starbucks'
```

### Key existence and negation

```python
# Nodes that have a phone tag (any value)
r = overpass_post(
    '[out:json][timeout:25]; node["phone"](48.860,2.300,48.862,2.310); out body 5;'
)
# r[0]['tags']['phone'] == '+33 1 45 51 56 74'

# Cafes WITHOUT a name tag
r = overpass_post(
    '[out:json][timeout:25]; node["amenity"="cafe"][!"name"](48.855,2.295,48.862,2.310); out body 5;'
)
# r[0]['tags'] == {'amenity': 'cafe', 'indoor_seating': 'yes', 'outdoor_seating': 'yes'}
```

### Node + way union with center coordinates

```python
# Banks as both nodes AND ways — get lat/lon for both via "out center"
r = overpass_post(
    '[out:json][timeout:25]; '
    '(node["amenity"="bank"](40.725,-73.995,40.735,-73.985);'
    ' way["amenity"="bank"](40.725,-73.995,40.735,-73.985););'
    'out center 10;'
)
for el in r:
    if el["type"] == "node":
        lat, lon = el["lat"], el["lon"]
    else:  # way — has 'center' dict, not top-level lat/lon
        lat, lon = el["center"]["lat"], el["center"]["lon"]
    print(el["tags"].get("name", "?"), lat, lon)
# Citizens Bank  40.7292 -73.9875
# Citibank       40.7304 -73.9928
```

### nwr shorthand (node + way + relation in one statement)

```python
# Any element type matching the filter — use when you don't know if data is stored as node, way, or relation
r = overpass_post(
    '[out:json][timeout:25]; nwr["amenity"="cafe"](40.728,-73.990,40.730,-73.988); out center 5;'
)
# Bryant Park stored as a way — nwr finds it where node[] would miss it:
r = overpass_post(
    '[out:json][timeout:25]; nwr["name"="Bryant Park"](40.750,-73.990,40.755,-73.982); out center 3;'
)
# r[0] == {'type': 'way', 'id': 22727025, 'center': {'lat': 40.7536, 'lon': 40.7536}, 'tags': {'name': 'Bryant Park', ...}}
```

### Way with full polygon geometry

```python
# out geom returns the full node list with lat/lon for each (for ways)
r = overpass_post(
    '[out:json][timeout:25]; way["amenity"="cafe"](48.855,2.295,48.870,2.320); out geom 2;'
)
el = r[0]
# el keys: ['type', 'id', 'bounds', 'nodes', 'geometry', 'tags']
# el['geometry'] == [{'lat': 48.8659, 'lon': 2.3154}, {'lat': 48.8659, 'lon': 2.3152}, ...]
# el['bounds']   == {'minlat': 48.8659, 'minlon': 2.3152, 'maxlat': 48.8661, 'maxlon': 2.3154}
centroid_lat = sum(g["lat"] for g in el["geometry"]) / len(el["geometry"])
```

### Relations (routes, boundaries)

```python
# NYC subway route relations
r = overpass_post(
    '[out:json][timeout:25]; relation["type"="route"]["route"="subway"](40.73,-74.00,40.75,-73.97); out body 5;'
)
# r[0] == {'type': 'relation', 'id': ..., 'members': [...], 'tags': {'name': 'NYCS - 1 Train: ...', 'ref': '1', ...}}
# members list: [{'type': 'way', 'ref': 12345, 'role': ''}, ...]  — no geometry unless out geom used
```

---

## Response structure

```python
# Full response from overpass_post(query_raw) before slicing ["elements"]:
{
    "version": 0.6,
    "generator": "Overpass API 0.7.62.7 375dc00a",
    "osm3s": {
        "timestamp_osm_base": "2026-04-19T01:26:37Z",
        "copyright": "The data included in this document is from www.openstreetmap.org. The data is made available under ODbL."
    },
    "elements": [...]  # ← this is what overpass_post() returns
}

# Node element (out body):
{"type": "node", "id": 308684349, "lat": 48.8609068, "lon": 2.3015143,
 "tags": {"amenity": "cafe", "name": "Café de l'Alma", "phone": "+33 1 45 51 56 74"}}

# Way element (out center):
{"type": "way", "id": 338411946,
 "center": {"lat": 48.8660087, "lon": 2.3153233},
 "nodes": [3454913623, ...],   # node IDs forming the polygon
 "tags": {"amenity": "cafe", "name": "Café 1902"}}

# Way element (out geom): adds 'geometry' and 'bounds', no separate node fetching needed
{"type": "way", ..., "bounds": {"minlat": ..., "minlon": ..., "maxlat": ..., "maxlon": ...},
 "geometry": [{"lat": 48.8659, "lon": 2.3154}, ...]}

# Relation element (out body):
{"type": "relation", "id": 123,
 "members": [{"type": "way", "ref": 456, "role": "outer"}, ...],
 "tags": {"type": "route", "route": "subway", "name": "..."}}

# out meta adds: version, timestamp, changeset, user, uid
{"type": "node", ..., "version": 7, "timestamp": "2025-08-04T18:29:16Z", "user": "osm_user1234", ...}

# out tags (no geometry at all — fastest for tag-only operations):
{"type": "node", "id": 308684349, "tags": {...}}

# out count:
{"type": "count", "id": 0, "tags": {"nodes": "169", "ways": "0", "relations": "0", "total": "169"}}
```

---

## QL syntax reference

```
[out:json][timeout:25]           # Required header: JSON output, 25s server timeout
[out:xml][timeout:25]            # XML output (starts with <?xml ...) — not JSON parseable
[maxsize:52428800]               # Optional: 50MB result cap (default: server decides)

# Filters (all combinable):
node["amenity"="cafe"](bbox);           # exact tag match
node["amenity"~"cafe|restaurant"](bbox); # regex match on value
node["name"~"Star",i](bbox);            # case-insensitive regex
node["phone"](bbox);                    # key exists (any value)
node[!"name"](bbox);                    # key does NOT exist
node["amenity"="cafe"]["wifi"="yes"](bbox); # AND: multiple filters

# Spatial filters:
(south_lat, west_lon, north_lat, east_lon)   # bbox — latitude FIRST
(around:RADIUS_METERS, LAT, LON)             # radius — lat before lon
# Note: bbox order differs from GeoJSON [west, south, east, north]

# Element types:
node[...](filter);    # point elements
way[...](filter);     # polygons/lines — no direct lat/lon; use out center or out geom
relation[...](filter); # groups of elements (routes, boundaries)
nwr[...](filter);      # shorthand: node + way + relation

# Union (combine multiple type queries):
(node["amenity"="cafe"](bbox); way["amenity"="cafe"](bbox););out center 20;

# Output modifiers:
out body N;    # type + id + lat/lon (nodes) + tags, limit N results
out tags N;    # type + id + tags only (no geometry — fastest)
out center N;  # for ways/relations: adds 'center' dict {lat, lon} — most useful
out geom N;    # for ways: adds 'geometry' list [{lat,lon},...] and 'bounds' — full polygon
out meta N;    # adds version, timestamp, user, uid, changeset to each element
out count;     # returns count summary only, no element data
```

---

## Rate limits and status check

```python
import urllib.request, gzip
from helpers import http_get

# Check quota remaining before heavy queries
raw = http_get("https://overpass-api.de/api/status", headers={"User-Agent": "browser-harness/1.0"})
print(raw)
# Connected as: 1657779650
# Current time: 2026-04-19T01:24:58Z
# Announced endpoint: gall.openstreetmap.de/
# Rate limit: 2
# 2 slots available now.
# Currently running queries (pid, space limit, time limit, start time):
```

Rate model: **2 concurrent query slots per IP**, not 2/s. Sequential queries run immediately. A 3rd simultaneous query returns an HTML error page (HTTP 200 with HTML body).

```python
import time

def overpass_post_with_retry(query: str, max_retries: int = 3) -> list[dict]:
    import json, urllib.parse, urllib.request, gzip
    OVERPASS = "https://overpass.openstreetmap.fr/api/interpreter"
    for attempt in range(max_retries):
        data = urllib.parse.urlencode({"data": query}).encode()
        req = urllib.request.Request(
            OVERPASS, data=data, method="POST",
            headers={"User-Agent": "browser-harness/1.0",
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Accept-Encoding": "gzip"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
        body = body.decode()
        if body.startswith("{"):
            return json.loads(body)["elements"]
        if "rate_limited" in body or "too busy" in body or "timeout" in body.lower():
            time.sleep(2 ** attempt * 10)  # 10s, 20s, 40s
            continue
        raise RuntimeError(f"Overpass error: {body[:200]}")
    raise RuntimeError("Overpass: exceeded max retries")
```

---

## Gotchas

**`http_get` default UA (`Mozilla/5.0`) is blocked.** Both main and FR instances return HTTP 403. Always pass `headers={"User-Agent": "browser-harness/1.0"}`. Confirmed: `browser-harness/1.0` → 200.

**Error responses are HTML with HTTP 200.** Rate-limit and busy errors return `Content-Type: text/html` with HTTP status 200 — not 4xx/5xx. Always check `body.startswith("{")` before JSON parsing.

**bbox order is `(south, west, north, east)` — latitude first.** This is the opposite of GeoJSON `[west, south, east, north]`. The `around:` filter uses `(around:METERS, LAT, LON)` — lat before lon. Nominatim `boundingbox` field is `[south, north, west, east]` — different again; reorder to feed into Overpass: `f"({bb[0]},{bb[2]},{bb[1]},{bb[3]})"`.

**`out body` on ways gives NO lat/lon** — ways are polygons with node ID lists, not points. Use `out center` to get a centroid `{"lat": ..., "lon": ...}` dict, or `out geom` for the full polygon vertex list. `out body 10` on a way-only query will return elements with no `lat`/`lon` keys — always check `el.get("lat")` before using.

**`out N` limits total results.** Without a limit, large bboxes can return tens of thousands of elements and hit the 512MB memory cap, returning a `maxsize` error (HTML). Default safe limit: `out 50` for exploration, `out 500` for bulk. Omitting the number entirely means unlimited — avoid on wide queries.

**`nwr` is the correct shorthand, not `(node; way; relation;)`.** Use `nwr["amenity"="park"](bbox)` when you don't know if OSM stores the feature as a node, way, or relation. Many parks, buildings, and named places are ways or relations, not nodes.

**Area queries by name are unreliable in plain QL.** `area["name"="Berlin"]` often returns 0 results due to how Overpass caches area derivations. Prefer bbox or `around:` filters. For area-based queries, use the numeric area ID: `area(3600062422)` (relation ID + 3,600,000,000 for relations).

**Relation `members` have no geometry with `out body`.** Relation elements list member refs (`{'type': 'way', 'ref': 12345, 'role': 'outer'}`). To get actual geometry for relation members, use `out geom` — but this significantly increases response size and query time.

**`http_get` POST workaround.** `helpers.http_get` only supports GET. For complex queries that exceed URL length limits (roughly 2000 chars encoded), use `urllib.request.Request` with `method="POST"` as shown in the `overpass_post()` function above.

**`name` tag is the local-language name.** In Paris, `name` is French; in Tokyo, Japanese. For English names use `name:en` — but that tag is often absent. Never assume `name` is in English.

**Sequential calls are fine; concurrent calls are limited.** Run multiple queries in a loop with no sleep between them — they run sequentially and each completes before the next starts. Only concurrent (threaded/async) calls consume multiple slots.
