# Nominatim — Geocoding API

`https://nominatim.openstreetmap.org` — OpenStreetMap's geocoding service. Pure HTTP, no auth, no browser needed. Rate limit: **1 req/s**.

> **See also**: `openstreetmap/scraping.md` for Overpass API (spatial queries, POI lookup by tag). This skill focuses exclusively on Nominatim.

---

## Do this first

Always pass `headers={"User-Agent": "browser-harness/1.0"}`. The default `Mozilla/5.0` is blocked. Use `format=jsonv2` (not `json`) — it replaces `class` with `category` and matches the reverse geocode field naming. All calls return JSON, no parsing gymnastics needed.

```python
import json, urllib.parse
from helpers import http_get

UA    = {"User-Agent": "browser-harness/1.0"}
BASE  = "https://nominatim.openstreetmap.org"

def geocode(query: str, limit: int = 5) -> list[dict]:
    """Forward geocode. Returns [] when nothing found — never raises."""
    raw = http_get(f"{BASE}/search?q={urllib.parse.quote(query)}&format=jsonv2&limit={limit}&addressdetails=1", headers=UA)
    return json.loads(raw)

results = geocode("Times Square, NYC")
r = results[0]
# r['lat']          == '40.7570095'     ← STRING — always convert: float(r['lat'])
# r['lon']          == '-73.9859724'    ← STRING
# r['name']         == 'Times Square'
# r['display_name'] == 'Times Square, Manhattan Community Board 5, Manhattan, New York County, New York, 10036, United States'
# r['category']     == 'highway'        ← was 'class' in format=json
# r['type']         == 'pedestrian'
# r['addresstype']  == 'road'
# r['place_rank']   == 26
# r['importance']   == 0.599...         ← float 0–1, higher = more notable
# r['osm_type']     == 'relation'
# r['osm_id']       == 14942838
# r['boundingbox']  == ['40.7558313', '40.7591362', '-73.9870666', '-73.9845108']
#                       south_lat        north_lat    west_lon       east_lon  ← note non-obvious order
# r['address']['city']         == 'New York'
# r['address']['state']        == 'New York'
# r['address']['postcode']     == '10036'
# r['address']['country_code'] == 'us'
```

---

## All four query modes

### 1. Forward geocode — free-text

```python
raw = http_get(
    f"{BASE}/search?q=Eiffel+Tower&format=jsonv2&limit=3&addressdetails=1",
    headers=UA
)
results = json.loads(raw)  # [] when nothing found
lat = float(results[0]['lat'])
lon = float(results[0]['lon'])

# Useful optional params:
# &addressdetails=1       → adds 'address' dict to each result
# &extratags=1            → adds 'extratags': website, wikidata, opening_hours, fee, etc.
# &namedetails=1          → adds 'namedetails': name:en, name:de, name:fr, etc. (~40 languages)
# &countrycodes=fr,de     → restrict to countries (ISO 3166-1 alpha-2, comma-separated)
# &viewbox=W,S,E,N&bounded=1  → restrict to bounding box; bbox order: lon_min,lat_min,lon_max,lat_max
# &accept-language=es     → localized name/display_name in response (also works as HTTP header)
# &limit=N                → max results (default 10, max 50)
```

### 2. Reverse geocode — lat/lon to address

```python
raw = http_get(
    f"{BASE}/reverse?lat=40.7580&lon=-73.9855&format=jsonv2",
    headers=UA
)
result = json.loads(raw)
# Returns a single dict (not a list)
# result['address']['road']         == '7th Avenue'
# result['address']['commercial']   == 'Times Square'
# result['address']['city']         == 'New York'
# result['address']['postcode']     == '10019'
# result['address']['country_code'] == 'us'

# address dict is always included in /reverse (no &addressdetails=1 needed)

# Optional: &zoom=N  — controls granularity of the returned address
# zoom=0  → country, zoom=5  → state, zoom=10 → city,
# zoom=14 → suburb, zoom=16 → street, zoom=18 → building (default)

# zoom=10 example (Manhattan, not 7th Ave):
raw10 = http_get(f"{BASE}/reverse?lat=40.7580&lon=-73.9855&format=jsonv2&zoom=10", headers=UA)
r10 = json.loads(raw10)
# r10['name']        == 'Manhattan'
# r10['addresstype'] == 'suburb'
```

### 3. Structured search — field-based (avoids ambiguous free-text)

```python
raw = http_get(
    f"{BASE}/search?street=1600+Pennsylvania+Ave+NW&city=Washington&state=DC&country=US&format=jsonv2&limit=1",
    headers=UA
)
result = json.loads(raw)[0]
# result['name']         == 'White House'
# result['place_rank']   == 30
# result['category']     == 'office'
# result['display_name'] == 'White House, 1600, Pennsylvania Avenue Northwest, ...'

# Supported structured params:
# street=     → house number + street name
# city=
# county=
# state=
# country=    → country name or ISO code
# postalcode=
# (mix and match — more fields = more precise)
```

### 4. Lookup by OSM ID — convert OSM IDs to geocoded places

```python
# Prefix: N=node, W=way, R=relation
raw = http_get(
    f"{BASE}/lookup?osm_ids=R175905,W5013364&format=jsonv2",
    headers=UA
)
results = json.loads(raw)
# results[0]['name']     == 'New York'    (R175905 = NYC relation)
# results[1]['name']     == 'Tour Eiffel' (W5013364 = Eiffel Tower way)

# - Up to 50 IDs per call: osm_ids=R175905,N123456,W789
# - Nonexistent IDs are silently omitted from the response (check len)
# - Always include &addressdetails=1 if you need the address dict
```

---

## Optional params that add data to any response

| Param | Effect | Notes |
|-------|--------|-------|
| `&addressdetails=1` | Adds `address` dict | Required for /search; always present in /reverse |
| `&extratags=1` | Adds `extratags` dict | OSM tags: website, wikidata, opening_hours, fee, height, etc. |
| `&namedetails=1` | Adds `namedetails` dict | All name:XX language variants (~40 for major landmarks) |
| `&polygon_geojson=1` | Adds `geojson` field | Full boundary geometry (Polygon or MultiPolygon); can be large |
| `&accept-language=XX` | Localizes name/display_name | ISO 639-1 code; also works as HTTP `Accept-Language` header |

```python
# Polygon boundary — useful for city/country outlines
raw = http_get(
    f"{BASE}/search?q=Times+Square,+NYC&format=jsonv2&limit=1&polygon_geojson=1",
    headers=UA
)
r = json.loads(raw)[0]
geo = r['geojson']
# geo['type']        == 'MultiPolygon'
# geo['coordinates'] == [[[[-73.987, 40.756], [-73.986, 40.757], ...]]] ← [lon, lat] GeoJSON order

# English name for any place
raw = http_get(
    f"{BASE}/search?q=Eiffel+Tower&format=jsonv2&limit=1&namedetails=1",
    headers=UA
)
r = json.loads(raw)[0]
en_name = r['namedetails'].get('name:en', r['name'])
# en_name == 'Eiffel Tower'  (r['name'] would be 'Tour Eiffel' — local language)
```

---

## Response field reference

| Field | Type | Notes |
|-------|------|-------|
| `place_id` | int | Internal Nominatim ID — ephemeral, do NOT store long-term |
| `osm_type` | str | `"node"`, `"way"`, or `"relation"` |
| `osm_id` | int | Stable OSM element ID — use `osm_type/osm_id` as a stable key |
| `lat` | **str** | Always a string — convert with `float(r['lat'])` |
| `lon` | **str** | Always a string — convert with `float(r['lon'])` |
| `display_name` | str | Full comma-separated address string |
| `name` | str | Short local-language name (`'Tour Eiffel'`, not `'Eiffel Tower'`) |
| `category` | str | OSM key: `"highway"`, `"boundary"`, `"amenity"`, `"office"`, etc. (`jsonv2` only; `"class"` in `format=json`) |
| `type` | str | OSM tag value: `"pedestrian"`, `"administrative"`, `"restaurant"`, etc. |
| `addresstype` | str | Semantic category: `"city"`, `"road"`, `"suburb"`, `"office"`, etc. |
| `place_rank` | int | Hierarchy: 4=country, 8=state, 12-16=city, 19=suburb, 26=street, 30=POI/building |
| `importance` | float | 0–1 relevance score (Wikipedia-derived); higher = more globally notable |
| `boundingbox` | list[str] | `[south_lat, north_lat, west_lon, east_lon]` — all strings; note unusual order |
| `licence` | str | ODbL attribution — include in any user-facing output |

**`place_rank` reference (confirmed 2026-04-18)**:

| place_rank | addresstype | Example |
|---|---|---|
| 4 | country | United States |
| 8 | state | California |
| 16 | city | Los Angeles |
| 19 | suburb | Hollywood |
| 26 | road | Times Square (as street) |
| 30 | any POI | White House, restaurant, park |

---

## Batch geocoding pattern (rate-limit safe)

```python
import json, time, urllib.parse
from helpers import http_get

UA   = {"User-Agent": "browser-harness/1.0"}
BASE = "https://nominatim.openstreetmap.org"

def geocode_one(query: str) -> dict | None:
    raw = http_get(
        f"{BASE}/search?q={urllib.parse.quote(query)}&format=jsonv2&limit=1&addressdetails=1",
        headers=UA
    )
    results = json.loads(raw)
    return results[0] if results else None

places = [
    "Eiffel Tower, Paris",
    "Big Ben, London",
    "Colosseum, Rome",
    "Sagrada Familia, Barcelona",
]

geocoded = []
for place in places:
    result = geocode_one(place)
    if result:
        geocoded.append({
            "query": place,
            "lat": float(result['lat']),
            "lon": float(result['lon']),
            "name": result['name'],
            "country": result['address'].get('country'),
        })
    time.sleep(1)  # REQUIRED: 1 req/s limit

# geocoded[0] == {'query': 'Eiffel Tower, Paris', 'lat': 48.8582..., 'lon': 2.2945...,
#                  'name': 'Tour Eiffel', 'country': 'France'}
```

---

## Complete working example

```python
import json, time, urllib.parse
from helpers import http_get

UA   = {"User-Agent": "browser-harness/1.0"}
BASE = "https://nominatim.openstreetmap.org"

# 1. Forward geocode
raw = http_get(
    f"{BASE}/search?q=White+House,+Washington+DC&format=jsonv2&limit=1&addressdetails=1&extratags=1",
    headers=UA
)
place = json.loads(raw)[0]
lat, lon = float(place['lat']), float(place['lon'])
print(f"{place['name']}: ({lat:.4f}, {lon:.4f})")
# White House: (38.8976, -77.0366)
print(f"OSM ref: {place['osm_type']}/{place['osm_id']}")
# OSM ref: relation/19761182
print(f"Website: {place['extratags'].get('website', 'n/a')}")
# Website: https://www.whitehouse.gov

time.sleep(1)  # enforce rate limit between calls

# 2. Reverse geocode with zoom
raw = http_get(f"{BASE}/reverse?lat={lat}&lon={lon}&format=jsonv2&zoom=10", headers=UA)
city_result = json.loads(raw)
print(f"City level: {city_result['display_name']}")
# City level: Washington, District of Columbia, United States

time.sleep(1)

# 3. Lookup by OSM ID with English name
raw = http_get(
    f"{BASE}/lookup?osm_ids=R175905&format=jsonv2&namedetails=1&addressdetails=1",
    headers=UA
)
nyc = json.loads(raw)[0]
print(f"NYC local: {nyc['name']} | English: {nyc['namedetails'].get('name:en', nyc['name'])}")
# NYC local: New York | English: New York
print(f"Bounding box: S={nyc['boundingbox'][0]}, N={nyc['boundingbox'][1]}, W={nyc['boundingbox'][2]}, E={nyc['boundingbox'][3]}")
# Bounding box: S=40.4765780, N=40.9176300, W=-74.2588430, E=-73.7002330

time.sleep(1)

# 4. Structured search with polygon
raw = http_get(
    f"{BASE}/search?city=Paris&country=France&format=jsonv2&limit=1&polygon_geojson=1",
    headers=UA
)
paris = json.loads(raw)[0]
bb = paris['boundingbox']
# IMPORTANT: Nominatim boundingbox order: [south, north, west, east]
# Overpass bbox needs: (south, west, north, east) — requires reordering
overpass_bbox = f"{bb[0]},{bb[2]},{bb[1]},{bb[3]}"  # south,west,north,east
print(f"Paris Overpass bbox: {overpass_bbox}")
# Paris Overpass bbox: 48.8155755,2.2241220,48.9021560,2.4697602
```

---

## Gotchas

**`python-requests` User-Agent returns HTTP 403.** Nominatim blocks `python-requests/*`, `Wget/*`, and any other generic library UA. `Mozilla/5.0` is also blocked by the stricter public instance. `browser-harness/1.0` (or any descriptive app-style string) returns 200. Confirmed: `python-requests/2.31.0` → 403; `browser-harness/1.0` → 200.

**`lat`/`lon` are strings, not floats.** Every Nominatim response returns coordinates as strings: `"40.7570095"`. Always convert: `float(r['lat'])`. Contrast with Overpass, where `lat`/`lon` are native Python floats.

**`/reverse` at open ocean/Null Island returns `{"error": "Unable to geocode"}`.** This is the only case where `/reverse` returns an error dict instead of a result. Check for `"error"` key before accessing other fields. For coordinates over land, `/reverse` always returns the nearest feature — it never returns `[]`.

**`/search` returns `[]` on no match, `/reverse` returns `{"error": ...}` on failure.** They have different empty-case shapes. Guard both: `results = json.loads(raw); if not results: ...` for search; `if 'error' in json.loads(raw): ...` for reverse.

**`boundingbox` order is `[south, north, west, east]` — not `[west, south, east, north]`.** This is unique to Nominatim and differs from both GeoJSON (`[west, south, east, north]`) and Overpass (`south, west, north, east`). When converting to Overpass: `f"({bb[0]},{bb[2]},{bb[1]},{bb[3]})"` (south, west, north, east).

**`format=json` uses `class`, `format=jsonv2` uses `category`.** Prefer `jsonv2` — it matches the `/reverse` field naming and is the documented stable format. The `openstreetmap/scraping.md` examples use `format=json`; this skill uses `format=jsonv2` throughout.

**`name` field is always the local-language name.** For the Eiffel Tower, `name == 'Tour Eiffel'`, not `'Eiffel Tower'`. Use `&namedetails=1` and access `namedetails.get('name:en', name)` to reliably get the English name.

**`place_id` is ephemeral.** Do not store `place_id` for future lookups. Use `osm_type + osm_id` as a stable reference (e.g., `relation/175905` for New York City). Even `osm_id` can theoretically change if the OSM geometry is remapped, but it's far more stable than `place_id`.

**Structured search (`?street=&city=`) is pickier than free-text.** `?street=1600+Pennsylvania+Ave&city=Washington&country=US` returns multiple PA-Ave matches across the US. Add `&state=DC` to narrow to Washington DC. Free-text `?q=1600+Pennsylvania+Ave+NW,+Washington+DC` often resolves better for well-known addresses.

**Rate limit is 1 req/s — enforce it with `time.sleep(1)`.** The public instance does not return HTTP 429; it returns 403 or silently drops requests when overloaded. Rapid bursts of 3–5 requests may succeed, but sustained scraping without sleep will trigger a ban. For bulk geocoding use `time.sleep(1)` between every call — no exceptions.

**`&polygon_geojson=1` geometry can be large.** A country boundary polygon for the US or France can be thousands of coordinate pairs and hundreds of KB. Only request it when you actually need the outline. For just the bounding box, use `boundingbox`.

**Lookup endpoint silently drops invalid OSM IDs.** `?osm_ids=R175905,N999999999999` returns only one result (the valid one). Always check `len(results)` matches the number of IDs you sent.

**`&accept-language=XX` localizes both `name` and `display_name`.** Passing `&accept-language=de` returns `'Eiffelturm'` and a fully German display name. This works as either a query param or an HTTP header. When scraping multilingual data, omit this param to get the native OSM name.
