# GeoNames — Scraping & Data Extraction

`geonames.org` — geographic names database covering 11 million place names, postal codes, countries, timezones, and admin divisions. **Two access paths: free bulk TSV downloads (no key) or JSON API (requires free registered username).**

## Which approach to use

| Need | Use |
|------|-----|
| One-off lookup (place name, postal code, timezone) | API with registered username |
| Bulk data for a country or all cities | Bulk TSV downloads — no key, no rate limit |
| Offline / embedded use | Bulk downloads |

The `demo` username is **exhausted** (20,000 daily credit cap shared across all demo users). Always register a free account at `https://www.geonames.org/login` and use your own username. Registration is instant and free.

---

## Path A — Bulk TSV downloads (no API key, no rate limit)

All files at `https://download.geonames.org/export/dump/` are open (CC-BY 4.0), updated daily, served as gzip-compressed zip archives. **Use `http_get` with the Content-Encoding header handled automatically by the helper.**

### Download and parse a single country's places

```python
import io, zipfile, csv
from helpers import http_get

# Download country zip — two-letter ISO code
raw = http_get("https://download.geonames.org/export/dump/US.zip")
# http_get decompresses gzip transfer encoding; zip archive is still intact
z = zipfile.ZipFile(io.BytesIO(raw.encode("latin-1")))

# File inside zip is named XX.txt (same as the country code)
COLS = [
    "geonameid", "name", "asciiname", "alternatenames",
    "latitude", "longitude", "feature_class", "feature_code",
    "country_code", "cc2", "admin1_code", "admin2_code",
    "admin3_code", "admin4_code", "population", "elevation",
    "dem", "timezone", "modification_date",
]

with z.open("US.txt") as f:
    reader = csv.DictReader(
        io.TextIOWrapper(f, encoding="utf-8"),
        fieldnames=COLS,
        delimiter="\t",
    )
    for row in reader:
        if row["feature_class"] == "P" and int(row["population"] or 0) > 100_000:
            print(row["name"], row["population"], row["timezone"])
            # New York City 8336817 America/New_York
            # Los Angeles 3979576 America/Los_Angeles
            # Chicago 2720546 America/Chicago

# feature_class == "P"  → populated places
# feature_class == "A"  → administrative division
# feature_class == "H"  → hydrographic (rivers, lakes)
# feature_class == "T"  → mountain, hill, rock
# feature_class == "S"  → spot / building / farm
```

### Pre-filtered city files (faster — no parsing full country dump)

```python
import io, zipfile, csv
from helpers import http_get

# Four sizes available:
#   cities500.zip   ~185,000 cities (pop > 500)
#   cities1000.zip  ~130,000 cities (pop > 1000)
#   cities5000.zip   ~50,000 cities (pop > 5000)
#   cities15000.zip  ~25,000 cities (pop > 15000 or capital)

raw = http_get("https://download.geonames.org/export/dump/cities15000.zip")
z = zipfile.ZipFile(io.BytesIO(raw.encode("latin-1")))

COLS = [
    "geonameid", "name", "asciiname", "alternatenames",
    "latitude", "longitude", "feature_class", "feature_code",
    "country_code", "cc2", "admin1_code", "admin2_code",
    "admin3_code", "admin4_code", "population", "elevation",
    "dem", "timezone", "modification_date",
]

cities = []
with z.open("cities15000.txt") as f:
    reader = csv.DictReader(
        io.TextIOWrapper(f, encoding="utf-8"),
        fieldnames=COLS,
        delimiter="\t",
    )
    for row in reader:
        cities.append({
            "id":          int(row["geonameid"]),
            "name":        row["name"],
            "lat":         float(row["latitude"]),
            "lon":         float(row["longitude"]),
            "country":     row["country_code"],
            "population":  int(row["population"] or 0),
            "timezone":    row["timezone"],
            "feature":     row["feature_code"],  # PPLC=capital, PPL=city, PPLA=admin center
        })

# Confirmed: 26,817 cities in cities15000.txt (2026-04-18)
print(len(cities))   # 26817
print(cities[0])
# {'id': 3040051, 'name': 'les Escaldes', 'lat': 42.50729, 'lon': 1.53414,
#  'country': 'AD', 'population': 15853, 'timezone': 'Europe/Andorra', 'feature': 'PPLA'}
```

### Country metadata (no zip — plain TSV, skip comment lines)

```python
import csv, io
from helpers import http_get

raw = http_get("https://download.geonames.org/export/dump/countryInfo.txt")
COLS = [
    "iso", "iso3", "iso_numeric", "fips", "country", "capital",
    "area_sqkm", "population", "continent", "tld", "currency_code",
    "currency_name", "phone", "postal_format", "postal_regex",
    "languages", "geonameid", "neighbours", "fips_equiv",
]

countries = []
for line in raw.splitlines():
    if line.startswith("#") or not line.strip():
        continue
    row = dict(zip(COLS, line.split("\t")))
    countries.append(row)

# Lookup by ISO code
by_iso = {c["iso"]: c for c in countries}
us = by_iso["US"]
print(us["country"], us["capital"], us["population"])
# United States Washington 327167434
print(us["languages"])    # en-US,es-US,haw,fr
print(us["neighbours"])   # CA,MX,CU
# Confirmed output (2026-04-18)
```

### Postal codes — country-specific or all countries

```python
import io, zipfile, csv
from helpers import http_get

# Single country: https://download.geonames.org/export/zip/US.zip
# All countries:  https://download.geonames.org/export/zip/allCountries.zip (~28 MB)

POSTAL_COLS = [
    "country_code", "postal_code", "place_name",
    "admin_name1", "admin_code1",
    "admin_name2", "admin_code2",
    "admin_name3", "admin_code3",
    "latitude", "longitude", "accuracy",
]

raw = http_get("https://download.geonames.org/export/zip/US.zip")
z = zipfile.ZipFile(io.BytesIO(raw.encode("latin-1")))

with z.open("US.txt") as f:
    reader = csv.DictReader(
        io.TextIOWrapper(f, encoding="utf-8"),
        fieldnames=POSTAL_COLS,
        delimiter="\t",
    )
    by_zip = {row["postal_code"]: row for row in reader}

row = by_zip["10001"]
print(row["place_name"], row["admin_name1"], row["latitude"], row["longitude"])
# New York City New York 40.7484 -73.9967
# Confirmed output (2026-04-18)
```

### Admin1 (state/province) reference table

```python
from helpers import http_get

raw = http_get("https://download.geonames.org/export/dump/admin1CodesASCII.txt")
# Format: "US.NY\tNew York\tNew York\t5128638"
admin1 = {}
for line in raw.splitlines():
    if not line.strip():
        continue
    code, name, ascii_name, geoname_id = line.split("\t")
    admin1[code] = {"name": name, "ascii": ascii_name, "id": geoname_id}

print(admin1["US.NY"])   # {'name': 'New York', 'ascii': 'New York', 'id': '5128638'}
print(admin1["GB.ENG"])  # {'name': 'England', 'ascii': 'England', 'id': '6269131'}
# Confirmed (2026-04-18)
```

---

## Path B — JSON API (requires registered username)

Register free at `https://www.geonames.org/login`. You get 20,000 credits/day. Each call costs 1–4 credits depending on endpoint.

All API endpoints use `http_get` — fully static JSON responses, no browser needed.

```python
USERNAME = "your_geonames_username"   # set once, reuse everywhere
```

### Search for places by name

```python
import json
from helpers import http_get

data = json.loads(http_get(
    f"http://api.geonames.org/searchJSON"
    f"?q=New+York&maxRows=5&username={USERNAME}"
))
# data['totalResultsCount']  — total matches
# data['geonames']           — list of place dicts

for place in data["geonames"]:
    print(place["name"], place["countryCode"], place["lat"], place["lng"], place["population"])
# New York City US 40.71427 -74.00597 8336817
# New York US 43.00035 -75.49990 19274244   (the state)
# Confirmed structure — status 18 (demo exhausted) when tested; structure from API docs
```

### Postal code lookup

```python
import json
from helpers import http_get

data = json.loads(http_get(
    f"http://api.geonames.org/postalCodeSearchJSON"
    f"?postalcode=10001&country=US&username={USERNAME}"
))
result = data["postalCodes"][0]
print(result["placeName"], result["lat"], result["lng"])
# New York City 40.74844 -73.99656
```

### Reverse geocode — nearest place to lat/lon

```python
import json
from helpers import http_get

data = json.loads(http_get(
    f"http://api.geonames.org/findNearbyPlaceNameJSON"
    f"?lat=40.71&lng=-74.01&username={USERNAME}"
))
place = data["geonames"][0]
print(place["name"], place["adminName1"], place["distance"])
# Manhattan New York 0.57   (distance in km)
```

### Timezone for lat/lon

```python
import json
from helpers import http_get

data = json.loads(http_get(
    f"http://api.geonames.org/timezoneJSON"
    f"?lat=40.71&lng=-74.01&username={USERNAME}"
))
print(data["timezoneId"])   # America/New_York
print(data["gmtOffset"])    # -5
print(data["dstOffset"])    # -4
```

### Country info

```python
import json
from helpers import http_get

data = json.loads(http_get(
    f"http://api.geonames.org/countryInfoJSON"
    f"?country=US&username={USERNAME}"
))
info = data["geonames"][0]
print(info["countryName"], info["capital"], info["population"])
# United States Washington 327167434
```

---

## Parallel bulk download with ThreadPoolExecutor

```python
import io, zipfile, csv
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

POSTAL_COLS = [
    "country_code", "postal_code", "place_name",
    "admin_name1", "admin_code1", "admin_name2", "admin_code2",
    "admin_name3", "admin_code3", "latitude", "longitude", "accuracy",
]

def fetch_postal(cc):
    """Fetch and parse postal codes for a two-letter country code."""
    try:
        raw = http_get(f"https://download.geonames.org/export/zip/{cc}.zip")
        z = zipfile.ZipFile(io.BytesIO(raw.encode("latin-1")))
        with z.open(f"{cc}.txt") as f:
            reader = csv.DictReader(
                io.TextIOWrapper(f, encoding="utf-8"),
                fieldnames=POSTAL_COLS,
                delimiter="\t",
            )
            return list(reader)
    except Exception:
        return []

countries = ["US", "GB", "DE", "FR", "CA"]
with ThreadPoolExecutor(max_workers=3) as ex:
    results = dict(zip(countries, ex.map(fetch_postal, countries)))

for cc, rows in results.items():
    print(cc, len(rows), "postal codes")
# US 41483
# GB 2673
# DE 16476
# FR 51542
# CA 1645
```

---

## API endpoint reference

| Endpoint | Purpose | Key params |
|----------|---------|-----------|
| `/searchJSON` | Search by name | `q`, `country`, `featureClass`, `maxRows` |
| `/postalCodeSearchJSON` | Postal code lookup | `postalcode`, `country` |
| `/findNearbyPlaceNameJSON` | Reverse geocode | `lat`, `lng`, `radius` |
| `/timezoneJSON` | Timezone for coords | `lat`, `lng` |
| `/countryInfoJSON` | Country metadata | `country` |
| `/getJSON` | Lookup by geonameid | `geonameId` |
| `/findNearbyJSON` | Features near coords | `lat`, `lng`, `featureClass`, `featureCode` |

All endpoints: `http://api.geonames.org/<endpoint>?..&username=<u>`

---

## Bulk download file reference

| URL | Contents | Size | Key |
|-----|---------|------|-----|
| `.../dump/XX.zip` | All features for country XX | varies | none |
| `.../dump/allCountries.zip` | All features worldwide | 399 MB | none |
| `.../dump/cities500.zip` | Cities pop > 500 (~185k) | 13 MB | none |
| `.../dump/cities1000.zip` | Cities pop > 1000 (~130k) | 10 MB | none |
| `.../dump/cities5000.zip` | Cities pop > 5000 (~50k) | 5.3 MB | none |
| `.../dump/cities15000.zip` | Cities pop > 15000 (~25k) | 3.1 MB | none |
| `.../dump/countryInfo.txt` | Country metadata (plain TSV) | 31 KB | none |
| `.../dump/admin1CodesASCII.txt` | State/province names | 148 KB | none |
| `.../dump/admin2Codes.txt` | County/district names | 2.3 MB | none |
| `.../dump/timeZones.txt` | Timezone offsets per country | small | none |
| `.../zip/XX.zip` | Postal codes for country XX | varies | none |
| `.../zip/allCountries.zip` | All postal codes worldwide | ~28 MB | none |

---

## Gotchas

**`demo` username is always exhausted.** The shared `demo` account hits its 20,000-credit daily cap within minutes. It returns `{"status": {"message": "the daily limit of 20000 credits for demo has been exceeded...", "value": 18}}` — not an HTTP error, just a JSON status body. For any real work, register a free personal account.

**API errors come back as HTTP 200 with a `status` key.** There is no HTTP 4xx/5xx for auth errors or quota exhaustion. Always check `if "status" in data` before accessing `data["geonames"]` or `data["postalCodes"]`.

**`http_get` returns a `str`, not `bytes`.** The bulk zip files are binary. The workaround is `raw.encode("latin-1")` before passing to `zipfile.ZipFile` — latin-1 is a lossless round-trip for arbitrary bytes through Python's str layer.

**`csv.DictReader` with `fieldnames` skips no header.** The TSV files have no header row — pass `fieldnames=COLS` explicitly. Without it, the first data row becomes the header and is silently lost.

**`population` and `elevation` fields can be empty strings.** Always guard: `int(row["population"] or 0)`. Elevation is frequently empty for small places.

**`alternatenames` column is a long comma-separated string, not a list.** It includes transliterations in many scripts (Arabic, Chinese, Cyrillic, etc.) and can be several KB per row. Split with `row["alternatenames"].split(",")` if you need individual names.

**Country zip files include a `readme.txt` entry.** When iterating `zipfile.namelist()`, skip `readme.txt`; only `XX.txt` contains data.

**Postal code zips for CA, NL, GB only contain the first part of the code.** Full Canadian postal codes are in `CA_full.csv.zip` (different filename and CSV not TSV format). Full UK codes are in `GB_full.csv.zip`.

**`accuracy` field in postal codes is 1–6.** `1` = estimated from neighboring codes; `4` = matched to geonameid; `6` = centroid of addresses. Many non-US/non-EU postal codes are `1` — treat lat/lng as approximate (±5 km).

**Admin1 codes are FIPS, not ISO for most countries.** Exceptions: US, CH, BE, ME use ISO codes. `US.NY` is New York (ISO), but most countries use FIPS subdivision codes which differ from ISO 3166-2.

**`feature_code` distinguishes capital from city.** `PPLC` = national capital, `PPLA` = first-order admin center (state capital), `PPLA2`/`PPLA3` = smaller admin centers, `PPL` = populated place. Filter by `feature_code` to get only capitals.

**Rate limit for the API is per username, not per IP.** Each free account gets 20,000 credits/day; credit cost varies (search = 1, nearby = 1, hierarchy = 4). Exceeding returns status value `18` in the JSON body — no HTTP error is raised.
