# U.S. Census Bureau Geocoder (geocoding.geo.census.gov) - Turn a US Street Address into Coordinates Plus Its County, Census Tract and Congressional District Codes (REST API, no key)

Field-tested against geocoding.geo.census.gov on 2026-11-16 (US Pacific afternoon; the logged runs were 2026-11-16 23:48 to 2026-11-17 00:00 UTC) using two fresh Browser Use cloud browser sessions (logged out) plus Python `urllib` and `curl` from a Linux machine. 10 browser page loads (geocoder JSON pages, robots.txt twice, the geocoder home page, the API terms page twice) and 63 in-page `fetch()` calls, 75 curl calls (4 of them robots.txt, 5 of them batch files of 3 or 4 addresses) and 14 urllib calls (4 of them robots.txt, 2 of them batch files of 6 addresses), plus 2 curl downloads of the FAQ and user guide PDFs from www2.census.gov, all serial at about 1 s spacing: every call was HTTP 200 except the deliberate HTTP 400 and 404 probes below and the HTTP 404 of robots.txt. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-16, curl, the cloud browser and `urllib.robotparser`): https://geocoding.geo.census.gov/robots.txt answers HTTP 404 with a Tomcat page titled `HTTP Status 404 - Not Found`, so the host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources", and Python's parser treats it as allow-all for GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider on the `/geocoder/geographies/...` and `/geocoder/locations/...` paths used here (block 3 checks all 11 agents). Terms: the geocoder pages link no terms of their own (the home page has 37 links, none to terms of use; its footer lists Information Quality, Data Linkage Infrastructure, Data Protection and Privacy Policy, Accessibility, FOIA, Inspector General and No FEAR Act; cloud browser 2026-11-16), so this skill follows the Census Bureau API Terms of Service (https://www.census.gov/data/developers/about/terms-of-service.html, "Page Last Revised - April 14, 2026", read in the cloud browser by block 2). It says you "may use the Census Bureau API to develop a service or service to search, display, analyze, retrieve, view and otherwise "get" information from Census Bureau data"; users "will not use these data, alone or in combination with any other Census or non-Census data, to identify any individual person, household, business or other entity"; services "should display the following notice prominently within the application: "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.""; "You may not use the Census Bureau name, or the like to imply endorsement"; you "may not modify or falsely represent content accessed through the API and still claim the source is the Census Bureau"; and use that tries to "exceed or circumvent these limits" may be "temporarily or permanently blocked". No AI/ML, scraping, automated-access or non-commercial clause. Naming: "U.S. Census Bureau Geocoder" as plain text with the required notice, no Census Bureau logo or seal. This skill is not affiliated with or endorsed by the Census Bureau.

**Required notice (print it with every answer, as the blocks do):** "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau." Name the benchmark and vintage you used.

**Use:** geocode places and addresses to statistical geography. Do not use the results, alone or combined with other data, to identify a person, household or business (API terms, above).

## Quick summary

- **No scraping.** `GET https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=1600+Pennsylvania+Ave+NW%2C+Washington%2C+DC+20500&benchmark=Public_AR_Current&vintage=Current_Current&format=json` returns the matched address, `x`/`y` and every geography layer for it. `/geocoder/geographies/coordinates?x=<lon>&y=<lat>&...` gives the layers for a point; `/geocoder/locations/onelineaddress?...` gives only the match and coordinates (no `vintage`). `/geocoder/geographies/addressbatch` takes a CSV of up to 10,000 addresses. JSON (CSV for batch), no key.
- **Answer, 1600 Pennsylvania Ave NW, Washington, DC 20500 (run 2026-11-16 23:58 UTC):** matched `1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500`, **x -77.035189, y 38.898703**; county **11001** District of Columbia; census tract **11001980000** (Census Tract 9800); congressional district **1198** "Delegate District (at Large)" in the layer `120th Congressional Districts`; 2020 block **110019800001034**. 20 W 34th St, New York, NY 10001 -> ZIP corrected to 10118, county 36061 New York County, tract **36061007600**, district **3612** (NY-12).
- **Never take `addressMatches[0]` blindly.** "1600 Pennsylvania Ave, Washington, DC" (no NW) returns **2** matches with **SE first** (ZIP 20003, 5.0 km from the NW match by the returned coordinates). "1 Calle Fortaleza, San Juan, PR 00901" returns 4 matches for `1 CALLE E` in 4 other ZIPs. Blocks 1 and 3 refuse more than one candidate.
- **A single match can still be the wrong street.** "200 N Spring St, Los Angeles, CA 90012" (Los Angeles City Hall) came back as one `Non_Exact` match on **200 S SPRING ST**. Typos ("Pensylvania") and a wrong ZIP (90210) are silently corrected. The blocks print the matched address and flag a changed direction, street spelling or ZIP.
- **Silent failures are HTTP 200:** no match is `addressMatches: []`; swapped `x`/`y` or a point outside coverage is `geographies: {}`; leaving out `format=json` returns the HTML web form. Loud ones are HTTP 400 JSON: `{"errors":["Benchmark must be specified"],"status":"400"}`, `Vintage must be specified`, `Invalid benchmark in request`, `Invalid vintage in request`.
- **Coverage:** "only geocodes addresses that are within the United States, Puerto Rico, and the U.S. Island Areas" (geocoder home page). Coordinates are "interpolated, or approximated" along TIGER address ranges (Census documentation page), so they are a point on the street segment, not a rooftop.
- **Rate limit:** none published (the API doc, the FAQ PDF and the user guide PDF give the 10,000-address batch cap but no request rate). The API terms reserve the right to limit or block. All blocks are serial with 1 s pauses and wait 60 s once on 429/500/502/503/504.

## What works

### 1. Address -> coordinates, county, tract, congressional district and block (browser)

`on_geo_tab()` opens one logged-out geocoding.geo.census.gov JSON page (the benchmark list), so `fetch()` is same-origin: the server sends `Access-Control-Allow-Origin` only for census.gov origins. `get()` returns parsed JSON on HTTP 200, waits 60 s once on 429/500/502/503/504 and otherwise raises. Layers are found by pattern because their names carry the vintage (`120th Congressional Districts`, `2020 Census Blocks`). 6 `fetch()` calls for 5 addresses and 1 point.

```python
import json, re, time, urllib.parse
from datetime import datetime, timezone

ADDRESSES = [  # one US street address per line: number + street, then city/state/ZIP
    "1600 Pennsylvania Ave NW, Washington, DC 20500",
    "20 W 34th St, New York, NY 10001",
    "200 N Spring St, Los Angeles, CA 90012",  # Los Angeles City Hall
    "1600 Pennsylvania Ave, Washington, DC",   # no NW/SE: two streets match
    "123 Nowhere Rd, Faketown, ZZ 00000",      # no such address
]
POINTS = [(-73.985241, 40.748656)]  # (x = longitude, y = latitude) -> geographies only

SITE = "https://geocoding.geo.census.gov"
GEO = SITE + "/geocoder"
BENCH, VINTAGE = "Public_AR_Current", "Current_Current"  # both required on /geographies (HTTP 400 without)
PAUSE = 1.0  # no published rate limit; the API terms say abusive use can be blocked. Stay serial.
NOTICE = "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."

def on_geo_tab():
    """CORS is allowed only for census.gov origins, so fetch() runs from a geocoding.geo.census.gov page. Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(GEO + "/benchmarks?format=json")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"benchmarkName":"Public_AR_Current"' not in body:
        raise RuntimeError(f"geocoder did not serve its benchmark list (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__g[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def get(path, timeout=90, **params):
    """GET from inside the tab -> parsed JSON. Waits 60 s once on 429/500/502/503/504 or a network error, raises
    on anything else (400 = {"errors": ["Benchmark must be specified"], "status": "400"} and similar)."""
    url = GEO + path + "?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        if r["status"] != 200 or "json" not in (r["type"] or ""):
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['text'][:200]!r}; stopping")
        return json.loads(r["text"])

DIRS = {"N": "N", "S": "S", "E": "E", "W": "W", "NE": "NE", "NW": "NW", "SE": "SE", "SW": "SW", "NORTH": "N",
        "SOUTH": "S", "EAST": "E", "WEST": "W", "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW"}

def dirs(street):
    """Direction words in the street part (before the first comma), normalised: '200 North Spring St' -> {'N'}."""
    return {DIRS[w] for w in re.findall(r"[A-Z]+", street.split(",")[0].upper()) if w in DIRS}

def layer(geos, pattern):
    """The one feature in the layer whose name matches pattern. Layer names carry the vintage
    ("120th Congressional Districts", "2020 Census Blocks"), so match by pattern, never by exact key."""
    keys = [k for k in geos if re.search(pattern, k)]
    if len(keys) != 1 or len(geos[keys[0]]) != 1:
        raise RuntimeError(f"expected one layer and one feature for {pattern!r}, got {[(k, len(geos[k])) for k in keys]}")
    return keys[0], geos[keys[0]][0]

def describe(geos, indent="    "):
    _, st = layer(geos, r"^States$")
    _, co = layer(geos, r"^Counties$")
    _, tr = layer(geos, r"^Census Tracts$")
    cd_name, cd = layer(geos, r"^\d+(st|nd|rd|th) Congressional Districts$")
    bl_name, bl = layer(geos, r"Census Blocks$")
    print(f"{indent}state  {st['STUSAB']} (FIPS {st['GEOID']})")
    print(f"{indent}county {co['GEOID']} {co['NAME']}")
    print(f"{indent}tract  {tr['GEOID']} {tr['NAME']}")
    print(f"{indent}house  {cd['GEOID']} {cd['NAME']} ({cd_name}, CDSESSN {cd['CDSESSN']})")
    print(f"{indent}block  {bl['GEOID']} ({bl_name})")
    return tr["GEOID"]

on_geo_tab()
now = datetime.now(timezone.utc)
for addr in ADDRESSES:
    d = get("/geographies/onelineaddress", address=addr, benchmark=BENCH, vintage=VINTAGE)
    m = d["result"]["addressMatches"]
    print(f"{addr!r}")
    if not m:
        print("  NO MATCH (HTTP 200, addressMatches []): check number, street, direction, city or ZIP\n")
        continue
    if len(m) > 1:
        print(f"  {len(m)} CANDIDATES, not picking one: add the missing part (direction, ZIP) and ask again")
        for c in m:
            print(f"    {c['matchedAddress']}  x {c['coordinates']['x']:.6f} y {c['coordinates']['y']:.6f}")
        print()
        continue
    c = m[0]
    a = c["addressComponents"]
    print(f"  matched {c['matchedAddress']}")
    print(f"    x {c['coordinates']['x']:.6f}  y {c['coordinates']['y']:.6f}  (interpolated on TIGER line "
          f"{c['tigerLine']['tigerLineId']} side {c['tigerLine']['side']}, range {a['fromAddress']}-{a['toAddress']})")
    zin = re.findall(r"\b\d{5}\b", addr)
    if zin and zin[-1] != a["zip"]:
        print(f"    note: input ZIP {zin[-1]} came back as {a['zip']}")
    if not re.search(r"\b" + re.escape(a["streetName"]) + r"\b", addr.upper()):
        print(f"    note: matched street {a['streetName']!r} is not spelled that way in the input")
    if dirs(addr) != dirs(c["matchedAddress"]):
        print(f"    CHECK: input direction {sorted(dirs(addr))} came back as {sorted(dirs(c['matchedAddress']))}: "
              f"this may be a different street; verify before using these codes")
    describe(c["geographies"])
    print()

for x, y in POINTS:
    d = get("/geographies/coordinates", x=x, y=y, benchmark=BENCH, vintage=VINTAGE)
    geos = d["result"]["geographies"]
    print(f"point x {x} y {y}")
    if not geos:
        print("  NO GEOGRAPHY (HTTP 200, geographies {}): x/y swapped, or outside the US, Puerto Rico and Island Areas")
        continue
    describe(geos)

print(f"\nSource: U.S. Census Bureau Geocoder, benchmark {BENCH}, vintage {VINTAGE}, accessed {now:%d %B %Y %H:%M} UTC. "
      f"{NOTICE}")
```

Output (from the run on 2026-11-16, 23:58 UTC):

```text
'1600 Pennsylvania Ave NW, Washington, DC 20500'
  matched 1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500
    x -77.035189  y 38.898703  (interpolated on TIGER line 76225813 side L, range 1600-1648)
    state  DC (FIPS 11)
    county 11001 District of Columbia
    tract  11001980000 Census Tract 9800
    house  1198 Delegate District (at Large) (120th Congressional Districts, CDSESSN 120)
    block  110019800001034 (2020 Census Blocks)

'20 W 34th St, New York, NY 10001'
  matched 20 W 34TH ST, NEW YORK, NY, 10118
    x -73.985241  y 40.748656  (interpolated on TIGER line 59653429 side L, range 2-98)
    note: input ZIP 10001 came back as 10118
    state  NY (FIPS 36)
    county 36061 New York County
    tract  36061007600 Census Tract 76
    house  3612 Congressional District 12 (120th Congressional Districts, CDSESSN 120)
    block  360610076001001 (2020 Census Blocks)

'200 N Spring St, Los Angeles, CA 90012'
  matched 200 S SPRING ST, LOS ANGELES, CA, 90012
    x -118.245594  y 34.051623  (interpolated on TIGER line 141618119 side L, range 200-298)
    CHECK: input direction ['N'] came back as ['S']: this may be a different street; verify before using these codes
    state  CA (FIPS 06)
    county 06037 Los Angeles County
    tract  06037207306 Census Tract 2073.06
    house  0634 Congressional District 34 (120th Congressional Districts, CDSESSN 120)
    block  060372073061000 (2020 Census Blocks)

'1600 Pennsylvania Ave, Washington, DC'
  2 CANDIDATES, not picking one: add the missing part (direction, ZIP) and ask again
    1600 PENNSYLVANIA AVE SE, WASHINGTON, DC, 20003  x -76.982768 y 38.879387
    1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500  x -77.035189 y 38.898703

'123 Nowhere Rd, Faketown, ZZ 00000'
  NO MATCH (HTTP 200, addressMatches []): check number, street, direction, city or ZIP

point x -73.985241 y 40.748656
    state  NY (FIPS 36)
    county 36061 New York County
    tract  36061007600 Census Tract 76
    house  3612 Congressional District 12 (120th Congressional Districts, CDSESSN 120)
    block  360610076001001 (2020 Census Blocks)

Source: U.S. Census Bureau Geocoder, benchmark Public_AR_Current, vintage Current_Current, accessed 16 November 2026 23:58 UTC. This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.
```

### 2. robots.txt, the terms page, benchmarks, vintages and query mistakes (browser)

3 page loads and 23 in-page `fetch()` calls. Run after block 1 or on its own.

```python
import json, re, time, urllib.parse

SITE = "https://geocoding.geo.census.gov"
GEO = SITE + "/geocoder"
TOS = "https://www.census.gov/data/developers/about/terms-of-service.html"
NOTICE = "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."

START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__g[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def raw(path, **params):
    """One in-page GET -> {status, type, text}. No retries: this block only inspects answers."""
    url = GEO + path + "?" + urllib.parse.urlencode(params)
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{path}: no answer after 90s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r

def brief(r):
    out = f"HTTP {r['status']} {r['type'].split(';')[0]:<16}"
    if "json" not in r["type"]:
        t = re.search(r"<title>([^<]*)", r["text"], re.I)
        return out + f" {len(r['text']):,} chars, <title> {t[1].strip() if t else None!r}"
    d = json.loads(r["text"])
    if "errors" in d:
        return out + f" {d}"
    res = d["result"]
    if "addressMatches" in res:
        m = res["addressMatches"]
        out += f" {len(m)} match(es) " + str([x["matchedAddress"] for x in m])
        g = m[0].get("geographies") if len(m) == 1 else None
        return out + (" + " + ", ".join(k for k in g if "Congressional" in k or "Block" in k) if g else "")
    g = res["geographies"]
    return out + (f" geographies {{}} for x {res['input']['location']['x']} y {res['input']['location']['y']}" if not g
                  else f" {len(g)} layers: " + ", ".join(k for k in g if "Congressional" in k or "Block" in k))

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.body ? document.body.innerText : ''") or ""

try:
    here = js("location.origin")
except Exception:
    here = None
if here != SITE:  # never navigate a tab from another task: open our own
    new_tab("about:blank")

st, txt = page(SITE + "/robots.txt")
print(f"robots.txt HTTP {st}: {' '.join(txt.split()).replace(chr(0x2013), '-')[:60]!r}")  # the page title has an en dash
st, txt = page(TOS)
rev = re.search(r"Page Last Revised - ([A-Za-z]+ \d+, \d{4})", txt)
print(f"API terms HTTP {st}, last revised {rev[1] if rev else 'NOT FOUND'}; required notice on page: {NOTICE in txt}; "
      f"'identify any individual person, household, business' on page: "
      f"{'identify any individual person, household, business' in txt}")
st, txt = page(GEO + "/benchmarks?format=json")  # back on the geocoder origin for same-origin fetch()
print("benchmarks:", [b["benchmarkName"] + ("*" if b["isDefault"] else "") for b in json.loads(txt)["benchmarks"]])
v = json.loads(raw("/vintages", benchmark="Public_AR_Current", format="json")["text"])["vintages"]
print("vintages for Public_AR_Current:", [x["vintageName"] + ("*" if x["isDefault"] else "") for x in v])
print()

WH = "1600 Pennsylvania Ave NW, Washington, DC 20500"
OK = {"benchmark": "Public_AR_Current", "vintage": "Current_Current", "format": "json"}
for label, path, params in (
    ("White House, geographies          ", "/geographies/onelineaddress", {"address": WH, **OK}),
    ("no benchmark                      ", "/geographies/onelineaddress", {"address": WH, "vintage": "Current_Current", "format": "json"}),
    ("no vintage                        ", "/geographies/onelineaddress", {"address": WH, "benchmark": "Public_AR_Current", "format": "json"}),
    ("benchmark 'Current'               ", "/geographies/onelineaddress", {**OK, "address": WH, "benchmark": "Current"}),
    ("vintage from another benchmark    ", "/geographies/onelineaddress", {**OK, "address": WH, "vintage": "Census2020_Census2020"}),
    ("no format=json                    ", "/geographies/onelineaddress", {"address": WH, "benchmark": "Public_AR_Current", "vintage": "Current_Current"}),
    ("vintage Census2020_Current        ", "/geographies/onelineaddress", {**OK, "address": WH, "vintage": "Census2020_Current"}),
    ("locations (no vintage needed)     ", "/locations/onelineaddress", {"address": WH, "benchmark": "Public_AR_Current", "format": "json"}),
    ("typo 'Pensylvania'                ", "/locations/onelineaddress", {**OK, "address": "1600 Pensylvania Ave NW, Washington, DC 20500"}),
    ("wrong ZIP 90210                   ", "/locations/onelineaddress", {**OK, "address": "1600 Pennsylvania Ave NW, Washington, DC 90210"}),
    ("no direction (NW/SE)              ", "/locations/onelineaddress", {**OK, "address": "1600 Pennsylvania Ave, Washington, DC"}),
    ("with 'Apt 2'                      ", "/locations/onelineaddress", {**OK, "address": "1600 Pennsylvania Ave NW Apt 2, Washington, DC 20500"}),
    ("no house number                   ", "/locations/onelineaddress", {**OK, "address": "Pennsylvania Ave NW, Washington, DC 20500"}),
    ("ZIP only                          ", "/locations/onelineaddress", {**OK, "address": "20500"}),
    ("PO Box                            ", "/locations/onelineaddress", {**OK, "address": "PO Box 100, Washington, DC 20500"}),
    ("'1 Calle Fortaleza, San Juan, PR' ", "/locations/onelineaddress", {**OK, "address": "1 Calle Fortaleza, San Juan, PR 00901"}),
    ("'63 Calle Fortaleza, San Juan, PR'", "/locations/onelineaddress", {**OK, "address": "63 Calle Fortaleza, San Juan, PR 00901"}),
    ("Canada (24 Sussex Dr, Ottawa)     ", "/locations/onelineaddress", {**OK, "address": "24 Sussex Dr, Ottawa, ON K1M 1M4"}),
    ("coordinates x=lon y=lat           ", "/geographies/coordinates", {**OK, "x": -77.035189, "y": 38.898703}),
    ("coordinates swapped               ", "/geographies/coordinates", {**OK, "x": 38.898703, "y": -77.035189}),
    ("coordinates mid-Atlantic          ", "/geographies/coordinates", {**OK, "x": -40, "y": 30}),
    ("coordinates on /locations         ", "/locations/coordinates", {**OK, "x": -77.035189, "y": 38.898703}),
):
    print(f"{label} {brief(raw(path, **params))}")
```

Output (from the run on 2026-11-16, 23:55 UTC):

```text
robots.txt HTTP 404: 'HTTP Status 404 - Not Found'
API terms HTTP 200, last revised April 14, 2026; required notice on page: True; 'identify any individual person, household, business' on page: True
benchmarks: ['Public_AR_Current*', 'Public_AR_ACS2026', 'Public_AR_LUCA*', 'Public_AR_Census2020']
vintages for Public_AR_Current: ['Current_Current*', 'Census2010_Current', 'ACS2017_Current', 'ACS2018_Current', 'ACS2019_Current', 'Census2020_Current', 'ACS2021_Current', 'ACS2022_Current', 'ACS2023_Current', 'ACS2024_Current', 'ACS2025_Current', 'ACS2026_Current']

White House, geographies           HTTP 200 application/json 1 match(es) ['1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500'] + 120th Congressional Districts, 2020 Census Blocks
no benchmark                       HTTP 400 application/json {'errors': ['Benchmark must be specified'], 'status': '400'}
no vintage                         HTTP 400 application/json {'errors': ['Vintage must be specified'], 'status': '400'}
benchmark 'Current'                HTTP 400 application/json {'errors': ['Invalid benchmark in request'], 'status': '400'}
vintage from another benchmark     HTTP 400 application/json {'errors': ['Invalid vintage in request'], 'status': '400'}
no format=json                     HTTP 200 text/html        37,575 chars, <title> 'Census Geocoder'
vintage Census2020_Current         HTTP 200 application/json 1 match(es) ['1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500'] + 116th Congressional Districts, Census Blocks
locations (no vintage needed)      HTTP 200 application/json 1 match(es) ['1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500']
typo 'Pensylvania'                 HTTP 200 application/json 1 match(es) ['1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500']
wrong ZIP 90210                    HTTP 200 application/json 1 match(es) ['1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500']
no direction (NW/SE)               HTTP 200 application/json 2 match(es) ['1600 PENNSYLVANIA AVE SE, WASHINGTON, DC, 20003', '1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500']
with 'Apt 2'                       HTTP 200 application/json 1 match(es) ['1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500']
no house number                    HTTP 200 application/json 0 match(es) []
ZIP only                           HTTP 200 application/json 0 match(es) []
PO Box                             HTTP 200 application/json 0 match(es) []
'1 Calle Fortaleza, San Juan, PR'  HTTP 200 application/json 4 match(es) ['1 CALLE E, SAN JUAN, PR, 00915', '1 CALLE E, SAN JUAN, PR, 00924', '1 CALLE E, SAN JUAN, PR, 00925', '1 CALLE E, SAN JUAN, PR, 00926']
'63 Calle Fortaleza, San Juan, PR' HTTP 200 application/json 1 match(es) ['63 CLL DE LA FORTALEZA, SAN JUAN, PR, 00901']
Canada (24 Sussex Dr, Ottawa)      HTTP 200 application/json 0 match(es) []
coordinates x=lon y=lat            HTTP 200 application/json 10 layers: 120th Congressional Districts, 2020 Census Blocks
coordinates swapped                HTTP 200 application/json geographies {} for x 38.898703 y -77.035189
coordinates mid-Atlantic           HTTP 200 application/json geographies {} for x -40.0 y 30.0
coordinates on /locations          HTTP 404 application/json {'errors': ["Requested resource wasn't found on the server."], 'status': '404'}
```

### 3. Batch file with Python urllib, then the district for each match, robots check for every agent (no browser)

The batch answer gives state, county, tract and block codes but no congressional district ("Batch geoLookup only includes state, county, tract, and block code", API doc), so the block asks `/geographies/coordinates` once per match and checks that its tract agrees with the batch row. 1 batch call plus 4 lookups.

```python
import csv, io, json, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser, uuid

SITE = "https://geocoding.geo.census.gov"
GEO = SITE + "/geocoder"
UA = "census-geocoder-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
BENCH, VINTAGE = "Public_AR_Current", "Current_Current"
NOTICE = "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."
ROWS = [  # Unique ID, Street address, City, State, ZIP (empty fields stay as empty columns). Up to 10,000 per file.
    ("1", "1600 Pennsylvania Ave NW", "Washington", "DC", "20500"),
    ("2", "20 W 34th St", "New York", "NY", "10001"),
    ("3", "233 S Wacker Dr", "Chicago", "IL", "60606"),
    ("4", "200 N Spring St", "Los Angeles", "CA", "90012"),
    ("5", "1600 Pennsylvania Ave", "Washington", "DC", ""),
    ("6", "123 Nowhere Rd", "Faketown", "ZZ", "00000"),
]

DIRS = {"N": "N", "S": "S", "E": "E", "W": "W", "NE": "NE", "NW": "NW", "SE": "SE", "SW": "SW", "NORTH": "N",
        "SOUTH": "S", "EAST": "E", "WEST": "W", "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW"}

def dirs(street):
    """Direction words in the street part (before the first comma), normalised: '200 North Spring St' -> {'N'}."""
    return {DIRS[w] for w in re.findall(r"[A-Z]+", street.split(",")[0].upper()) if w in DIRS}

def http(req, timeout=300):
    """urlopen with one 60 s wait on 429/500/502/503/504 or a network error; exits on anything else."""
    for attempt in range(2):
        time.sleep(1.0)  # no published rate limit; abusive use can be blocked (API terms). Stay serial.
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.headers.get("Content-Type", ""), r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"HTTP {e.code} {req.full_url}: {e.read().decode()[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{req.full_url}: {e}")

def batch(rows):
    """POST a CSV to /geographies/addressbatch -> {id: row}. The answer is CSV with no header; a matched row has
    12 columns (id, input, Match, Exact|Non_Exact, matched address, "lon,lat", TIGER line id, side,
    state, county, tract, block), No_Match and Tie rows stop after column 3."""
    if len(rows) > 10000:
        sys.exit("the batch limit is 10,000 addresses per file: split it")
    f = io.StringIO()
    csv.writer(f).writerows(rows)
    b = uuid.uuid4().hex
    parts = [(None, "benchmark", BENCH), (None, "vintage", VINTAGE), ("addresses.csv", "addressFile", f.getvalue())]
    body = b"".join(
        f"--{b}\r\nContent-Disposition: form-data; name=\"{n}\"".encode()
        + (f"; filename=\"{fn}\"\r\nContent-Type: text/csv".encode() if fn else b"")
        + b"\r\n\r\n" + v.encode() + b"\r\n" for fn, n, v in parts) + f"--{b}--\r\n".encode()
    req = urllib.request.Request(GEO + "/geographies/addressbatch", data=body, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": f"multipart/form-data; boundary={b}"})
    ctype, text = http(req)
    if not ctype.startswith("text/plain"):
        sys.exit(f"batch answered {ctype!r}, not CSV: {text[:200]!r}")
    out = {r[0]: r for r in csv.reader(io.StringIO(text)) if r}
    if set(out) != {r[0] for r in rows}:
        sys.exit(f"batch returned ids {sorted(out)} for {len(rows)} rows: stop")
    return out

def geographies(x, y):
    """/geographies/coordinates -> {layer name: feature}. Batch rows carry no congressional district; this does."""
    q = urllib.parse.urlencode({"x": x, "y": y, "benchmark": BENCH, "vintage": VINTAGE, "format": "json"})
    ctype, text = http(urllib.request.Request(f"{GEO}/geographies/coordinates?{q}", headers={"User-Agent": UA}))
    g = json.loads(text)["result"]["geographies"]
    if not g:
        sys.exit(f"no geography at x {x} y {y}: swapped, or outside the US, Puerto Rico and Island Areas")
    return {k: v[0] for k, v in g.items() if v}

# robots.txt: the host answers 404. RobotFileParser.read() treats a 4xx other than 401/403 as "allow all"
# (RFC 9309, section 2.3.1.3: unavailable robots.txt, the crawler MAY access any resources).
rp = urllib.robotparser.RobotFileParser(SITE + "/robots.txt")
try:
    urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30)
    print("robots.txt now exists: read it before going on")
except urllib.error.HTTPError as e:
    print(f"robots.txt: HTTP {e.code}")
rp.read()
for p in ["/geocoder/geographies/addressbatch", "/geocoder/geographies/coordinates?x=0&y=0",
          "/geocoder/geographies/onelineaddress?address=x", "/geocoder/locations/onelineaddress?address=x"]:
    ok = all(rp.can_fetch(a, SITE + p) for a in AGENTS)
    print(f"robots {p:<48} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
    if not ok:
        sys.exit("robots.txt now disallows a path this skill uses: stop")
print()

t0 = time.time()
res = batch(ROWS)
print(f"1 batch call, {len(ROWS)} rows, {time.time() - t0:.1f} s")
counts = {}
for rid, *_ in ROWS:
    r = res[rid]
    counts[r[2]] = counts.get(r[2], 0) + 1
    if r[2] != "Match":
        print(f"  {rid} {r[1]!r}: {r[2]}" + (" (more than one candidate: add the direction or ZIP)" if r[2] == "Tie" else ""))
        continue
    if len(r) != 12:
        sys.exit(f"row {rid} has {len(r)} columns, expected 12: the CSV layout changed")
    x, y = map(float, r[5].split(","))
    state, county, tract, block = r[8:12]
    g = geographies(x, y)
    cd = [(k, v) for k, v in g.items() if k.endswith("Congressional Districts")]
    if len(cd) != 1 or g["Census Tracts"]["GEOID"] != state + county + tract:
        sys.exit(f"row {rid}: coordinates lookup disagrees with the batch row: stop")
    print(f"  {rid} {r[1]!r}: {r[3]} -> {r[4]}")
    if dirs(r[1]) != dirs(r[4]):
        print(f"      CHECK: direction {sorted(dirs(r[1]))} came back as {sorted(dirs(r[4]))}: maybe a different street")
    print(f"      x {x:.6f} y {y:.6f}  county {state}{county}  tract {state}{county}{tract}  block "
          f"{state}{county}{tract}{block}  house {cd[0][1]['GEOID']} ({cd[0][1]['NAME']}, {cd[0][0]})")
print(f"  totals {counts}")
print(f"\nSource: U.S. Census Bureau Geocoder, benchmark {BENCH}, vintage {VINTAGE}. {NOTICE}")
```

Output (from the run on 2026-11-16, 23:57 UTC):

```text
robots.txt: HTTP 404
robots /geocoder/geographies/addressbatch               allowed for all 11 agents
robots /geocoder/geographies/coordinates?x=0&y=0        allowed for all 11 agents
robots /geocoder/geographies/onelineaddress?address=x   allowed for all 11 agents
robots /geocoder/locations/onelineaddress?address=x     allowed for all 11 agents

1 batch call, 6 rows, 1.5 s
  1 '1600 Pennsylvania Ave NW, Washington, DC, 20500': Exact -> 1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500
      x -77.035189 y 38.898703  county 11001  tract 11001980000  block 110019800001034  house 1198 (Delegate District (at Large), 120th Congressional Districts)
  2 '20 W 34th St, New York, NY, 10001': Non_Exact -> 20 W 34TH ST, NEW YORK, NY, 10118
      x -73.985241 y 40.748656  county 36061  tract 36061007600  block 360610076001001  house 3612 (Congressional District 12, 120th Congressional Districts)
  3 '233 S Wacker Dr, Chicago, IL, 60606': Exact -> 233 S WACKER DR, CHICAGO, IL, 60606
      x -87.636602 y 41.878920  county 17031  tract 17031839100  block 170318391002008  house 1707 (Congressional District 7, 120th Congressional Districts)
  4 '200 N Spring St, Los Angeles, CA, 90012': Non_Exact -> 200 S SPRING ST, LOS ANGELES, CA, 90012
      CHECK: direction ['N'] came back as ['S']: maybe a different street
      x -118.245594 y 34.051623  county 06037  tract 06037207306  block 060372073061000  house 0634 (Congressional District 34, 120th Congressional Districts)
  5 '1600 Pennsylvania Ave, Washington, DC, ': Tie (more than one candidate: add the direction or ZIP)
  6 '123 Nowhere Rd, Faketown, ZZ, 00000': No_Match
  totals {'Match': 4, 'Tie': 1, 'No_Match': 1}

Source: U.S. Census Bureau Geocoder, benchmark Public_AR_Current, vintage Current_Current. This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.
```

### 4. curl

```bash
G=https://geocoding.geo.census.gov/geocoder
P='benchmark=Public_AR_Current&vintage=Current_Current&format=json'
# address -> matched address, x/y, county, tract, congressional district (benchmark AND vintage are required)
curl -sS --fail -G "$G/geographies/onelineaddress?$P" --data-urlencode "address=1600 Pennsylvania Ave NW, Washington, DC 20500" \
  | python3 -c 'import json,sys; m=json.load(sys.stdin)["result"]["addressMatches"]; print(len(m), "match"); g=m[0]["geographies"]; print(m[0]["matchedAddress"], m[0]["coordinates"]); [print(" ", k, g[k][0]["GEOID"], g[k][0]["NAME"]) for k in g if k in ("Counties","Census Tracts") or k.endswith("Congressional Districts")]'
sleep 1
# point -> geographies (x = longitude first)
curl -sS --fail "$G/geographies/coordinates?x=-73.985241&y=40.748656&$P" \
  | python3 -c 'import json,sys; g=json.load(sys.stdin)["result"]["geographies"]; print(g["Census Tracts"][0]["GEOID"], g["Counties"][0]["NAME"])'
sleep 1
# coordinates only, no vintage needed
curl -sS --fail -G "$G/locations/onelineaddress?benchmark=Public_AR_Current&format=json" --data-urlencode "address=233 S Wacker Dr, Chicago, IL 60606" \
  | python3 -c 'import json,sys; m=json.load(sys.stdin)["result"]["addressMatches"]; print([(x["matchedAddress"], x["coordinates"]) for x in m])'
sleep 1
# batch: CSV in (id, street, city, state, zip; up to 10,000 rows), CSV out with no header
printf '1,1600 Pennsylvania Ave NW,Washington,DC,20500\n2,200 N Spring St,Los Angeles,CA,90012\n3,123 Nowhere Rd,Faketown,ZZ,00000\n' > /tmp/geocoder-batch.csv
curl -sS --fail --form addressFile=@/tmp/geocoder-batch.csv --form benchmark=Public_AR_Current --form vintage=Current_Current "$G/geographies/addressbatch"
sleep 1
# headers: no CORS header for an outside Origin (www.census.gov gets one), no caching, no rate-limit headers
curl -sS -D - -o /dev/null -H 'Origin: https://example.com' -G "$G/locations/onelineaddress?benchmark=4&format=json" --data-urlencode "address=1600 Pennsylvania Ave NW, Washington, DC 20500" \
  | tr -d '\r' | grep -iE '^(HTTP/|(content-type|cache-control|vary|access-control-allow-origin|x-ratelimit-limit|retry-after):)'
sleep 1
# mistakes: a miss is HTTP 200 with addressMatches []; missing vintage is HTTP 400 JSON; no format is an HTML page
curl -sS -w ' <- HTTP %{http_code}\n' -G "$G/locations/onelineaddress?benchmark=4&format=json" --data-urlencode "address=123 Nowhere Rd, Faketown, ZZ 00000" | python3 -c 'import sys; t=sys.stdin.read(); print(t[t.index("\"addressMatches\""):], end="")'
sleep 1
curl -sS -w ' <- HTTP %{http_code}\n' -G "$G/geographies/onelineaddress?benchmark=Public_AR_Current&format=json" --data-urlencode "address=1600 Pennsylvania Ave NW, Washington, DC 20500"
sleep 1
curl -sS -o /dev/null -w 'no format: HTTP %{http_code} %{content_type}\n' -G "$G/locations/onelineaddress?benchmark=4" --data-urlencode "address=1600 Pennsylvania Ave NW, Washington, DC 20500"
sleep 1
curl -sS -o /dev/null -w 'robots.txt: HTTP %{http_code}\n' https://geocoding.geo.census.gov/robots.txt
```

Output (from the run on 2026-11-17, 00:00 UTC):

```text
1 match
1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500 {'x': -77.035189204737, 'y': 38.898702605245}
  Counties 11001 District of Columbia
  120th Congressional Districts 1198 Delegate District (at Large)
  Census Tracts 11001980000 Census Tract 9800
36061007600 New York County
[('233 S WACKER DR, CHICAGO, IL, 60606', {'x': -87.636602278191, 'y': 41.878919545908})]
"1","1600 Pennsylvania Ave NW, Washington, DC, 20500","Match","Exact","1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500","-77.035189204737,38.898702605246","76225813","L","11","001","980000","1034"
"2","200 N Spring St, Los Angeles, CA, 90012","Match","Non_Exact","200 S SPRING ST, LOS ANGELES, CA, 90012","-118.245593523439,34.051622610747","141618119","L","06","037","207306","1000"
"3","123 Nowhere Rd, Faketown, ZZ, 00000","No_Match"
HTTP/1.1 200 
Content-Type: application/json
Cache-Control: private, no-store
Vary: Origin
"addressMatches":[]}} <- HTTP 200
{"errors":["Vintage must be specified"],"status":"400"} <- HTTP 400
no format: HTTP 200 text/html;charset=UTF-8
robots.txt: HTTP 404
```

## Fields (geographies JSON)

| Path / parameter | Value | Notes |
|---|---|---|
| `benchmark` | `Public_AR_Current` (id 4) | required on every call. `/geocoder/benchmarks?format=json` listed `Public_AR_Current`, `Public_AR_ACS2026`, `Public_AR_LUCA`, `Public_AR_Census2020`. `Current` alone is HTTP 400 |
| `vintage` | `Current_Current` (id 4) | required on `/geographies/...` only. Must belong to the benchmark: `/geocoder/vintages?benchmark=Public_AR_Current&format=json` listed `Current_Current`, `Census2010_Current`, `ACS2017_Current` ... `ACS2026_Current`, `Census2020_Current`; `Census2020_Census2020` with `Public_AR_Current` is HTTP 400 |
| `format` | `json` | without it the answer is the HTML form (HTTP 200) |
| `layers` | default set, or `all`, or ids | default for `Current_Current` gave 10 layers (States, Counties, Census Tracts, 2020 Census Blocks, 120th Congressional Districts, 2026 State Legislative Districts - Upper, County Subdivisions, Incorporated Places, Urban Areas, Combined Statistical Areas); `layers=all` gave 18 for the White House, adding Census Block Groups, 2020 Census ZIP Code Tabulation Areas, Unified School Districts, PUMAs, metro areas, regions and divisions |
| `result.addressMatches[]` | list | `matchedAddress` (standardised, upper case), `coordinates.x` (longitude), `coordinates.y` (latitude), `tigerLine.tigerLineId` and `side` (L/R), `addressComponents` (`fromAddress`, `toAddress`, `preDirection`, `streetName`, `suffixType`, `suffixDirection`, `city`, `state`, `zip`), `geographies` |
| `geographies[<layer>][0]` | one feature | `GEOID`, `NAME`, `BASENAME`, the code parts (`STATE`, `COUNTY`, `TRACT`, `BLOCK`, `BLKGRP`), `CENTLAT`/`CENTLON`, `INTPTLAT`/`INTPTLON`, `AREALAND`/`AREAWATER` |
| county `GEOID` | 5 digits | state FIPS (2) + county (3): `11001` |
| tract `GEOID` | 11 digits | state + county + `TRACT` (6): `11001980000`; `NAME` puts the decimal back (`Census Tract 2073.06` for `207306`) |
| block `GEOID` | 15 digits | tract GEOID + 4-digit `BLOCK`; layer `2020 Census Blocks` in `Current_Current`, `Census Blocks` in `Census2020_Current` |
| district `GEOID` | 4 digits | state FIPS + 2-digit district: `3612` = NY-12; `98` = delegate at large (DC `1198`). `CDSESSN` holds the Congress number (`120`) and the field `CD120` the district |
| batch output | CSV, no header | `id, input, Match/No_Match/Tie, Exact/Non_Exact, matched address, "lon,lat", TIGER line id, side, state, county, tract, block`; No_Match and Tie rows stop after column 3 |

## Gotchas

- **Coordinates are interpolated.** "Address ranges within TIGER include all possible structure numbers even though actual structures may not exist" and "Coordinate results are interpolated, or approximated" (Census documentation page). 1646 Pennsylvania Ave NW matched too, at x -77.037762, 0.0026 degrees (about 220 m) west of 1600 on the same 1600-1648 range. Do not treat `x`/`y` as a building location.
- **Ambiguous input gives several matches, in no useful order.** Without NW the White House query listed 1600 Pennsylvania Ave SE (ZIP 20003) first; batch marks the same row `Tie`. Ask again with the direction and ZIP.
- **Fuzzy matching changes the address.** 200 N Spring St became 200 S SPRING ST (`Non_Exact`), "Pensylvania" became PENNSYLVANIA, ZIP 90210 became 20500, ZIP 10001 became 10118. Compare the matched address with what you sent; the blocks flag direction, street-name and ZIP changes. "Apt 2" is ignored (same match as without it).
- **Puerto Rico addresses need care.** `onelineaddress` "does not support Puerto Rico addresses with Urbanization and Municipio" (API doc); "1 Calle Fortaleza" matched four `1 CALLE E` streets, while "63 Calle Fortaleza, San Juan, PR 00901" matched `63 CLL DE LA FORTALEZA`. Use `/locations/addressPR` (`street`, `urb`, `municipio`, `zip`) for urbanization addresses.
- **No match is not an error.** HTTP 200 with `addressMatches: []` for a fake address, a ZIP alone, a street without a house number, a PO Box and a Canadian address. The FAQ PDF adds that real addresses can miss because the address is "non-residential or commercial", newly built, renamed, or because geocoding it would disclose information protected by Title 13 ("This is rare").
- **`x` is longitude, `y` is latitude.** Swapped values return HTTP 200 with `geographies: {}`, the same answer as a point in the Atlantic. Check for an empty dict.
- **Layer names change with the vintage.** `Current_Current` returns `120th Congressional Districts` and `2020 Census Blocks`; `Census2020_Current` returns `116th Congressional Districts` and `Census Blocks`. Match layer names by pattern and report which Congress the district belongs to.
- **Batch results can vary between runs.** The FAQ PDF says the same 100-address batch gave "Match: 92, No_Match: 7, Tie: 1" and then "Match: 91, No_Match: 9, Tie: 0", a known load-related issue; it advises resubmitting only the unmatched rows rather than the whole batch. Batch and single lookups also differed in the 12th decimal of `y` (38.898702605246 vs 38.898702605245).
- **CORS only for census.gov.** A page on www.census.gov could `fetch()` the API; `Origin: https://example.com` and `Origin: null` got no `Access-Control-Allow-Origin` (curl). The API doc says "the geocoder does not support CORS requests" and offers `format=jsonp&callback=`. The server does send `Access-Control-Allow-Origin` for `https://www.census.gov` and `https://geocoding.geo.census.gov` (urllib, 2026-11-17); blocks 1 and 2 call `fetch()` from a geocoder page (same origin) instead.
- **No caching headers to lean on.** Answers carry `Cache-Control: private, no-store` and a `TS0193e6a1` cookie; no `X-RateLimit-Limit` or `Retry-After` was seen.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **Addresses outside the US, Puerto Rico and the Island Areas** (24 Sussex Dr, Ottawa: 0 matches).
- **`/geocoder/locations/coordinates`**: HTTP 404 `{"errors":["Requested resource wasn't found on the server."],"status":"404"}`; coordinates work only with `geographies`.
- **Congressional districts in batch output**: not included; look each match up by coordinates (block 3).
- **More than 10,000 addresses per batch file**: "split their data into multiple submissions that are 10,000 addresses or less" (FAQ PDF). Not tested above 6 rows.
- **Not tested:** rate-limit behaviour (never provoked), `coordinatesbatch`, Excel batch files, the LUCA endpoints, Island Areas addresses (one Guam query, "1 Marine Corps Dr, Hagatna, GU 96910", returned 0 matches), and benchmarks other than `Public_AR_Current`.
