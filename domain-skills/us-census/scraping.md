# U.S. Census Bureau API — Data Extraction

`https://api.census.gov/data` — official U.S. demographic, economic, and housing statistics. **No browser needed.** All endpoints return JSON via `http_get`. **No API key required** for most use; a free key removes a daily rate cap.

## Do this first

**Fetch all states — no key needed, works immediately.**

```python
import json

# All-state population, median income, and median age (2022 ACS 5-year estimates)
raw = http_get(
    "https://api.census.gov/data/2022/acs/acs5"
    "?get=NAME,B01003_001E,B19013_001E,B01002_001E"
    "&for=state:*"
)
data = json.loads(raw)

# First row is always the header
headers = data[0]   # ['NAME', 'B01003_001E', 'B19013_001E', 'B01002_001E', 'state']
rows    = data[1:]  # [['Alabama', '5028092', '59609', '39.3', '01'], ...]

records = [dict(zip(headers, row)) for row in rows]
for r in records[:3]:
    print(r['NAME'], 'pop:', r['B01003_001E'], 'median_income:', r['B19013_001E'])
# Alabama pop: 5028092 median_income: 59609
# Alaska  pop: 734821  median_income: 86370
# Arizona pop: 7172282 median_income: 73450
```

All values are returned as **strings** — cast to `int()` or `float()` as needed.

---

## Response format

Every endpoint returns a 2-D JSON array. Row 0 = column headers. Rows 1..N = data.

```python
data = json.loads(raw)
headers = data[0]          # ['NAME', 'B01003_001E', 'state']
rows    = data[1:]         # [['Alabama', '5028092', '01'], ...]

# Convert to list of dicts
records = [dict(zip(headers, row)) for row in rows]

# Or convert to a DataFrame (if pandas available)
# import pandas as pd
# df = pd.DataFrame(data[1:], columns=data[0])
```

The geographic FIPS code columns (e.g. `state`, `county`, `tract`) are always appended to the right of the requested variables.

---

## Geographic hierarchy

Supported `for=` targets (from coarsest to finest):

| Geography | `for=` clause | `in=` filter needed? |
|---|---|---|
| Nation | `us:1` | No |
| State | `state:*` or `state:06` | No |
| County | `county:*` | Optional `in=state:XX` |
| Congressional district | `congressional+district:*` | `in=state:XX` |
| Place (city/town) | `place:*` | `in=state:XX` |
| ZCTA (ZIP code area) | `zip+code+tabulation+area:94102` | No |
| Census tract | `tract:*` | `in=state:XX&in=county:YYY` |
| Block group | `block+group:*` | `in=state:XX&in=county:YYY&in=tract:ZZZZZZ` |

```python
# County-level: all counties in California (state FIPS 06)
raw = http_get(
    "https://api.census.gov/data/2022/acs/acs5"
    "?get=NAME,B01003_001E,B19013_001E"
    "&for=county:*&in=state:06"
)
data = json.loads(raw)
# headers: ['NAME', 'B01003_001E', 'B19013_001E', 'state', 'county']
# 58 counties

# ZCTA (ZIP code area)
raw = http_get(
    "https://api.census.gov/data/2022/acs/acs5"
    "?get=NAME,B01003_001E"
    "&for=zip+code+tabulation+area:94102"
)
# headers: ['NAME', 'B01003_001E', 'zip code tabulation area']

# Census tract (requires state + county in 'in' clause)
raw = http_get(
    "https://api.census.gov/data/2022/acs/acs5"
    "?get=NAME,B01003_001E"
    "&for=tract:*&in=state:06&in=county:001"
)
# Alameda County tracts — 379 tracts

# Block group (requires state + county + tract)
raw = http_get(
    "https://api.census.gov/data/2022/acs/acs5"
    "?get=NAME,B01003_001E"
    "&for=block+group:*&in=state:06&in=county:001&in=tract:400100"
)
```

---

## Datasets (survey × year)

### ACS 5-Year (most common — full geographic coverage)

```
https://api.census.gov/data/{year}/acs/acs5?get=...
```

Available years: 2009 – 2024. Covers all geographies down to block group.

### ACS 1-Year (faster updates, fewer geographies)

```
https://api.census.gov/data/{year}/acs/acs1?get=...
```

Available years: 2005 – 2022. Only covers areas with population > 65,000. ACS1 has ~42 counties in California vs ~58 for ACS5.

### Decennial Census (exact counts, not estimates)

```
https://api.census.gov/data/2020/dec/pl?get=NAME,P1_001N&for=state:*
# Also: 2010, 2000, 1990
```

Decennial variables use `P` prefix instead of `B`.

### County Business Patterns (employment + establishments)

```
https://api.census.gov/data/2021/cbp?get=NAME,ESTAB,EMP,PAYANN&for=state:*&NAICS2017=72
# NAICS2017=72 = Accommodation and Food Services
```

### List all 1,776+ available datasets

```python
raw = http_get("https://api.census.gov/data.json")
catalog = json.loads(raw)
for d in catalog['dataset'][:10]:
    print(d['c_vintage'], d['c_dataset'], d['title'][:60])
```

---

## Common variable codes (ACS)

Variables follow the pattern `B{group}_{sequence}E` (E = Estimate, M = Margin of Error).

### Demographics

| Variable | Description |
|---|---|
| `B01003_001E` | Total population |
| `B01002_001E` | Median age |
| `B02001_002E` | White alone |
| `B02001_003E` | Black or African American alone |
| `B02001_004E` | American Indian and Alaska Native alone |
| `B02001_005E` | Asian alone |
| `B02001_006E` | Native Hawaiian and Other Pacific Islander alone |
| `B02001_007E` | Some other race alone |
| `B03001_003E` | Hispanic or Latino (any race) |
| `B05001_006E` | Not a U.S. citizen |

### Income & Poverty

| Variable | Description |
|---|---|
| `B19013_001E` | Median household income (past 12 months) |
| `B19025_001E` | Aggregate household income |
| `B17001_002E` | Population below poverty level |
| `B19001_001E` | Total households (income distribution base) |

### Housing

| Variable | Description |
|---|---|
| `B25001_001E` | Total housing units |
| `B25003_002E` | Owner-occupied housing units |
| `B25003_003E` | Renter-occupied housing units |
| `B25035_001E` | Median year structure built |
| `B25064_001E` | Median gross rent |
| `B25071_001E` | Median gross rent as % of household income |
| `B25077_001E` | Median home value |

### Education

| Variable | Description |
|---|---|
| `B15003_022E` | Population 25+: Bachelor's degree |
| `B15003_023E` | Population 25+: Master's degree |
| `B15003_025E` | Population 25+: Doctorate degree |
| `B14001_002E` | School enrollment: nursery/preschool |
| `B14001_007E` | School enrollment: undergraduate college |

### Employment

| Variable | Description |
|---|---|
| `B23025_004E` | Civilian labor force: employed |
| `B23025_005E` | Civilian labor force: unemployed |
| `B08303_001E` | Travel time to work: total |
| `B08006_017E` | Means of transport: public transit |
| `B08006_019E` | Means of transport: worked from home |

### Look up any variable

```python
raw = http_get("https://api.census.gov/data/2022/acs/acs5/variables.json")
variables = json.loads(raw)['variables']
print(len(variables))  # 28,193 variables for ACS 2022

# Look up a specific code
v = variables['B19013_001E']
print(v['label'])   # Estimate!!Median household income...
print(v['group'])   # B19013

# Search by label keyword
matches = [(k, v['label']) for k, v in variables.items()
           if 'median' in v.get('label', '').lower() and k.endswith('001E')]
for code, label in matches[:5]:
    print(code, ':', label)
```

---

## State FIPS codes (partial)

```
01=Alabama  02=Alaska   04=Arizona  05=Arkansas 06=California
08=Colorado 09=Connecticut 10=Delaware 11=DC  12=Florida
13=Georgia  15=Hawaii   16=Idaho    17=Illinois 18=Indiana
19=Iowa     20=Kansas   21=Kentucky 22=Louisiana 23=Maine
36=New York 48=Texas    51=Virginia 53=Washington 72=Puerto Rico
```

Note: FIPS codes skip numbers (03, 07, 11 = DC, etc.). Use `for=state:*` to enumerate all.

---

## End-to-end pattern: multi-county population table

```python
import json

def census_get(year, dataset, variables, geo_for, geo_in=None, api_key=None):
    """Fetch Census data, return list of dicts. All values are strings."""
    params = f"get=NAME,{','.join(variables)}&for={geo_for}"
    if geo_in:
        params += f"&in={geo_in}"
    if api_key:
        params += f"&key={api_key}"
    url = f"https://api.census.gov/data/{year}/{dataset}?{params}"
    raw = http_get(url)
    data = json.loads(raw)
    headers = data[0]
    return [dict(zip(headers, row)) for row in data[1:]]

# All counties in Texas
records = census_get(
    year=2022,
    dataset="acs/acs5",
    variables=["B01003_001E", "B19013_001E", "B25077_001E"],
    geo_for="county:*",
    geo_in="state:48",
)

# Sort by population descending
records.sort(key=lambda r: int(r['B01003_001E']), reverse=True)

for r in records[:5]:
    pop     = int(r['B01003_001E'])
    income  = int(r['B19013_001E']) if r['B19013_001E'] != '-666666666' else None
    home_val= int(r['B25077_001E']) if r['B25077_001E'] != '-666666666' else None
    print(f"{r['NAME']}: pop={pop:,}  income=${income:,}  home=${home_val:,}")
# Harris County, Texas:     pop=4,731,145  income=$62,474  home=$225,500
# Dallas County, Texas:     pop=2,618,148  income=$60,085  home=$238,700
# Tarrant County, Texas:    pop=2,117,665  income=$72,826  home=$255,600
```

---

## Rate limits & API key

- **Without key**: 500 requests/day (per IP). Sufficient for most scripting tasks.
- **With free key**: Higher limit (undocumented, ~1,000+/day). Required for heavy batch use.

Get a free key at `https://api.census.gov/data/key_signup.html` (instant, email only).

Add `&key=YOUR_KEY` to any query URL:
```python
url = "https://api.census.gov/data/2022/acs/acs5?get=NAME,B01003_001E&for=state:*&key=YOUR_KEY"
```

---

## Parallel bulk fetch (all counties nationwide)

```python
import json
from concurrent.futures import ThreadPoolExecutor

# All 50 states (FIPS 01-56, non-contiguous)
STATE_FIPS = [
    '01','02','04','05','06','08','09','10','11','12','13','15','16','17','18',
    '19','20','21','22','23','24','25','26','27','28','29','30','31','32','33',
    '34','35','36','37','38','39','40','41','42','44','45','46','47','48','49',
    '50','51','53','54','55','56'
]

def fetch_state_counties(fips):
    raw = http_get(
        f"https://api.census.gov/data/2022/acs/acs5"
        f"?get=NAME,B01003_001E,B19013_001E,B25077_001E"
        f"&for=county:*&in=state:{fips}"
    )
    data = json.loads(raw)
    headers = data[0]
    return [dict(zip(headers, row)) for row in data[1:]]

with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_state_counties, STATE_FIPS))

all_counties = [rec for state in results for rec in state]
print(len(all_counties))  # ~3,200 counties
```

---

## Gotchas

**All values are strings.** `row['B01003_001E']` is `'5028092'`, not `5028092`. Always cast: `int(r['B01003_001E'])` or `float(r['B01002_001E'])`.

**Special sentinel values signal missing/suppressed data — never cast them blindly.**

| Sentinel | Meaning |
|---|---|
| `-666666666` | Not applicable (geography doesn't have this variable) |
| `-555555555` | Not available (estimate unavailable for this area) |
| `-333333333` | Unreliable estimate (sampling error too large) |
| `-222222222` | Doesn't apply / data withheld |

Always guard:
```python
val = r['B19013_001E']
income = int(val) if int(val) > 0 else None
```

**First row is always headers.** `data[0]` is `['NAME', 'B01003_001E', 'state']`. `data[1:]` is the actual records. Forgetting this causes every `int()` cast to fail.

**Variable limit: 49 per request** (plus `NAME` = 50 columns total). Requesting 50+ variables returns HTTP 400 with no message body. Batch into chunks of 49:
```python
CHUNK = 49
for i in range(0, len(all_vars), CHUNK):
    chunk = all_vars[i:i+CHUNK]
    raw = http_get(f"...?get=NAME,{','.join(chunk)}&for=...")
```

**ACS1 only covers large geographies.** The 1-year estimates skip counties and tracts below ~65,000 population. Use ACS5 for complete county/tract/block-group coverage.

**Geographic FIPS codes are appended to the right**, not necessarily where you expect. When you request `?get=NAME,B01003_001E&for=county:*&in=state:06`, the response headers are `['NAME','B01003_001E','state','county']` — the geo columns (`state`, `county`) are always last. Use `dict(zip(headers, row))` rather than positional indexing.

**`E` = Estimate, `M` = Margin of Error.** Variable `B01003_001E` is the estimate; `B01003_001M` is its 90% margin of error. State-level `_001M` often returns `-555555555` (unreliable at that aggregate level). For subnational geographies, the MOE is meaningful.

**SSL certificate failure on macOS Python 3.11+.** The `http_get` helper in `helpers.py` may raise `CERTIFICATE_VERIFY_FAILED`. Fix for development:
```python
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```
Or install `certifi` and pass its CA bundle.

**Invalid API key returns empty body (HTTP 400), not a JSON error.** If you pass `&key=BADKEY`, the server returns HTTP 400 with an empty body — `json.loads(raw)` raises `JSONDecodeError`. Omit the key entirely if you don't have a valid one; keyless access works fine.

**`for=all counties` is not valid syntax.** Use `for=county:*` (with an asterisk), not `for=county:all`.

**Decennial variables differ from ACS.** Decennial 2020 uses `P1_001N` for total population (not `B01003_001E`). The two surveys have separate variable namespaces.

**Year is "vintage" — specifies which survey edition, not the data collection year.** `2022/acs/acs5` refers to the 5-year estimates ending in 2022 (covering 2018–2022).
