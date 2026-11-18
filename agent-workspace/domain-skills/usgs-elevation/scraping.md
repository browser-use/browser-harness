# USGS Elevation Point Query Service (The National Map) - Get the Ground Elevation in Feet or Meters for a US Latitude/Longitude, or for Every Point Along a Route (REST API, no key)

Field-tested against epqs.nationalmap.gov on 2026-11-17 (US Pacific afternoon; 2026-11-18 00:01-00:11 UTC) using a fresh Browser Use cloud browser (logged out; one session, 00:05-00:10 UTC) plus Python `urllib` and `curl` from a Linux machine. 17 browser page loads (the EPQS page, robots.txt on three hosts twice, the USGS Copyrights and Credits page twice, two USGS FAQ pages and the Bulk Point Query page) and 31 in-page `fetch()` calls, 57 curl calls and 12 urllib calls to the API and its docs, plus 6 curl and 1 urllib robots.txt fetches on epqs.nationalmap.gov and apps.nationalmap.gov and 4 curl calls for the robots.txt files of nationalmap.gov and www.usgs.gov, all serial. Every API call was HTTP 200 except the deliberate HTTP 400 (missing parameter) and HTTP 403 (unknown path, `POST`) probes below; errors for points without data also come back as HTTP 200 (see Gotchas). No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-17, cloud browser, curl and urllib): neither host this skill uses serves one. https://epqs.nationalmap.gov/robots.txt answers HTTP 403 `{"message":"Missing Authentication Token"}` (Amazon API Gateway) and https://apps.nationalmap.gov/robots.txt answers HTTP 403 S3 `AccessDenied` XML, with the same result from curl and the cloud browser (block 2). Under RFC 9309 section 2.3.1.3 a 4xx means the file is "unavailable" and "the crawler MAY access any resources on the server", so there are no rules and no named AI-agent groups: GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider may fetch `/v1/json`, `/v1/xml`, `/v1/docs` and `/epqs/`. Python's `urllib.robotparser` reads a 403 as "disallow all", so block 3 applies RFC 9309 by hand. The apex host https://nationalmap.gov/robots.txt (a different host; block 2 reads only this robots.txt there, nothing else) is a Cloudflare-managed file: `User-agent: *` with `Content-Signal: search=yes,ai-train=no,use=reference` and `Allow: /`, and `Disallow: /` for GPTBot, ClaudeBot, anthropic-ai, Google-Extended, CCBot, Bytespider and other training crawlers; ChatGPT-User, OAI-SearchBot, Claude-User and PerplexityBot are not named. RFC 9309 section 2.3 places the file at `scheme:[//authority]/robots.txt`, so it covers nationalmap.gov only, not the epqs or apps subdomains. https://www.usgs.gov/robots.txt (curl, HTTP 200 on 2026-11-18) has only a `User-agent: *` group, and it allows the USGS FAQ, Copyrights and Credits and Policies and Notices pages cited here for `*` and every agent named above. Terms: the EPQS page (https://apps.nationalmap.gov/epqs/) says "The Elevation Point Query Service returns the elevation in international feet or meters for a specific latitude/longitude (NAD 1983) point from the USGS Elevation Service hosted at the NGTOC" and links the API docs (https://epqs.nationalmap.gov/v1/docs, an OpenAPI 3.0.1 spec in Swagger UI). USGS Copyrights and Credits (https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits): "USGS-authored or produced data and information are considered to be in the U.S. Public Domain", and it asks for credit such as "Credit: U.S. Geological Survey"; the USGS identifier (logo) "is trademarked and must be used in accordance with the rules outlined in the Visual Identity System". The USGS FAQ (https://www.usgs.gov/faqs/how-accurate-are-elevations-generated-elevation-point-query-service-national-map, updated July 18, 2025) says the values "are interpolated from the 3DEP dynamic elevation service", have an overall RMSE of 0.53 m, and "are not official and do not represent precisely measured ground surveyed values". No key or registration, no published rate limit, and no AI/ML, scraping, automated-access or non-commercial clause on the EPQS page, the API docs, the Copyrights and Credits page or the page behind its "Legal" link (https://www.usgs.gov/policies-and-notices). Naming: "USGS Elevation Point Query Service (The National Map)" as plain text; no USGS identifier or logo. This skill is not affiliated with or endorsed by the USGS.

**Attribution:** "Source: USGS Elevation Point Query Service (The National Map). Credit: U.S. Geological Survey." Blocks 1 and 3 print that line.

## Quick summary

- **No scraping.** `GET https://epqs.nationalmap.gov/v1/json?x=<lon>&y=<lat>&wkid=4326&units=Feet&includeDate=true` returns one small JSON object per point. No key, `access-control-allow-origin: *`. `/v1/xml` gives the same as XML.
- **Answer (run 2026-11-18 00:07 UTC, block 1):** **Colorado State Capitol (39.73928, -104.98484): 5,275.99 ft = 1,608.12 m, from a 1 m DEM, source data acquired 2021-02-06.** Other checks: a Hawaii point 13,803.28 ft, an Alaska point 20,167.42 ft (5 m DEM, 2010), Lake Michigan open water 579.70 ft, the Pacific off central California exactly 0, the mid-Atlantic no elevation (plain-text error).
- **Route (block 3):** 12 points every ~8 km on a straight 82.6 km line from the Capitol to (40.2549, -105.6836): 5,276 ft to 10,493 ft, rises summing to 6,333 ft, in 38 s.
- **x is longitude, y is latitude.** Swapping them gives a plain-text error, not a wrong number. Block 1 checks the answer's `location` against what you asked.
- **Always send `units=Feet` or `units=Meters`.** Left out, the service answers in **meters** (as a string), although the API docs give `Feet` as the default.
- **Rate limit:** none published and none hit (no 429 in about 100 API calls, no rate-limit headers). Calls took 0.1 to 15 s each in this run; a verify run on 2026-11-18 (00:20 UTC) saw up to 17.4 s and one HTTP 504 `{"message": "Endpoint request timed out"}` after 29.1 s (blocks 1 and 3 retry a 504 once). There is no batch endpoint, so stay serial with a 1 s pause and budget about 2 to 3 s per point.

## What works

### 1. Ground elevation for a latitude/longitude, in feet and meters (browser)

`on_epqs_tab()` opens the logged-out EPQS page once; the API sends `access-control-allow-origin: *`, so `fetch()` works from it. `elevation()` always sends `units=Feet` and `includeDate=true`, retries once (after `Retry-After` when sent, else 60 s after 429 and 3 s after 5xx, a network error or a plain-text "no elevation" answer; over 120 s it stops), checks the returned `location`, and converts with 1 ft = 0.3048 m. 7 `fetch()` calls (the mid-Atlantic point was retried).

```python
import json, re, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

POINTS = [  # (label, latitude, longitude): decimal degrees, south and west negative
    ("Colorado State Capitol", 39.73928, -104.98484),
    ("Hawaii point", 19.8207, -155.4681),
    ("Alaska point", 63.0695, -151.0074),
    ("Lake Michigan, open water", 44.0, -87.0),
    ("Pacific off central California", 37.5, -123.5),
    ("mid-Atlantic, far offshore", 30.0, -40.0),
]

PAGE = "https://apps.nationalmap.gov/epqs/"  # the official EPQS page; the API sends access-control-allow-origin: *
API = "https://epqs.nationalmap.gov/v1/json"
FT_TO_M = 0.3048  # the service answers in international feet

def on_epqs_tab():
    """Any page works for fetch() (CORS is open); use the logged-out EPQS page. Reuse the tab if it is there."""
    try:
        if js("location.href").startswith(PAGE):
            return
    except Exception:
        pass
    new_tab(PAGE)
    wait_for_load()
    if not js("location.href").startswith(PAGE):
        raise RuntimeError(f"EPQS page did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds and one point can take 15 s, so start the fetch, then poll for it.
START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__o[id] = {status: r.status, type: r.headers.get('content-type'),
                                         ra: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__o[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def retry_after(v, default):
    """Retry-After in seconds (a number or an HTTP date); default when absent or unreadable; at least 1.
    Over 120 s: stop rather than hammer or hang."""
    try:
        sec = float(v)
    except (TypeError, ValueError):
        try:
            sec = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            sec = default
    if sec != sec:  # 'nan'
        sec = default
    if sec > 120:
        raise RuntimeError(f"server asks to wait {sec:.0f} s (over 120 s): stopping")
    return max(sec, 1)

def fetch_text(url, timeout=60):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"no answer after {timeout}s: {url}")
        time.sleep(0.3)
    return r, time.time() - t0

def elevation(lat, lon):
    """-> dict with ft, m, resolution, date, or {'error': text}. Always sends units=Feet (leaving units out gives
    METERS, as a string) and includeDate=true. A non-JSON body is the service's 'no elevation here' answer: retry it
    once after 3 s, because the error text varies call to call; 429/5xx/network errors are retried once too, after
    Retry-After when sent (else 60 s on 429, 3 s otherwise)."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"lat {lat}, lon {lon} out of range (did you swap them?)")
    url = f"{API}?x={lon}&y={lat}&wkid=4326&units=Feet&includeDate=true"  # x = LONGITUDE, y = latitude
    for attempt in range(2):
        r, secs = fetch_text(url)
        body = r["text"].strip()
        if r["status"] in (0, 429, 500, 502, 503, 504) or (r["status"] == 200 and not body.startswith("{")):
            if attempt == 0:
                time.sleep(retry_after(r.get("ra"), 60 if r["status"] == 429 else 3) if r["status"] != 200 else 3)
                continue
            if r["status"] == 200:
                return {"error": body[:120], "secs": secs}
        if r["status"] != 200:
            raise RuntimeError(f"HTTP {r['status']} {r['type']} {body[:200]!r} for {url}")
        d = json.loads(body)
        v = d.get("value")
        try:
            ft = float(v)  # a number in Feet; the Meters answer is a string
        except (TypeError, ValueError):
            return {"error": f"value {v!r}", "secs": secs}
        loc = d.get("location", {})
        if abs(loc.get("x", 999) - lon) > 1e-6 or abs(loc.get("y", 999) - lat) > 1e-6:
            raise RuntimeError(f"answer is for x={loc.get('x')} y={loc.get('y')}, not {lon},{lat}")
        return {"ft": ft, "m": ft * FT_TO_M, "res": d.get("resolution"), "raster": d.get("rasterId"),
                "date": (d.get("attributes") or {}).get("AcquisitionDate"), "secs": secs}

def res_text(res):
    """resolution is in metres for 1 m and 5 m DEMs, in degrees for the arc-second DEMs."""
    if res is None:
        return "resolution not given"
    if res >= 0.5:
        return f"{res:g} m"
    arcsec = res * 3600
    for frac, label in ((1 / 9, "1/9 arc-second, about 3 m"), (1 / 3, "1/3 arc-second, about 10 m"), (1, "1 arc-second, about 30 m")):
        if abs(arcsec - frac) / frac < 0.01:
            return label
    return f"{arcsec:.4f} arc-second"

def date_text(s):
    """AcquisitionDate is M/D/YYYY; some rasters say day 0 ('4/0/2023'). Returns ISO or the raw string."""
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    if not m:
        return f"{s!r} (not a date)" if s else "no date"
    mo, dd, yy = int(m[1]), int(m[2]), int(m[3])
    return f"{yy}-{mo:02d}-{dd:02d}" if dd else f"{yy}-{mo:02d} (day 0 in the source)"

on_epqs_tab()
for label, lat, lon in POINTS:
    e = elevation(lat, lon)
    if "error" in e:
        print(f"{label} ({lat}, {lon}): NO ELEVATION, service said {e['error']!r} ({e['secs']:.1f} s)")
    else:
        note = ""
        if e["ft"] == 0:
            note = "  <- exactly 0 offshore: sea, not a ground height"
        print(f"{label} ({lat}, {lon}): {e['ft']:,.2f} ft = {e['m']:,.2f} m, {res_text(e['res'])}, "
              f"source acquired {date_text(e['date'])}, raster {e['raster']} ({e['secs']:.1f} s){note}")
    time.sleep(1)

print("\nSource: USGS Elevation Point Query Service (The National Map), 3DEP bare-earth DEMs, interpolated, "
      "not official surveyed values. Credit: U.S. Geological Survey.")
```

Output (from the run on 2026-11-18, 00:07 UTC, which is 2026-11-17 in the US):

```text
Colorado State Capitol (39.73928, -104.98484): 5,275.99 ft = 1,608.12 m, 1 m, source acquired 2021-02-06, raster 53518 (1.2 s)
Hawaii point (19.8207, -155.4681): 13,803.28 ft = 4,207.24 m, 1 m, source acquired 2020-05-01, raster 118011 (5.9 s)
Alaska point (63.0695, -151.0074): 20,167.42 ft = 6,147.03 m, 5 m, source acquired 2010-11-05, raster 5794 (0.4 s)
Lake Michigan, open water (44.0, -87.0): 579.70 ft = 176.69 m, 1/3 arc-second, about 10 m, source acquired 2023-04 (day 0 in the source), raster 4825 (0.8 s)
Pacific off central California (37.5, -123.5): 0.00 ft = 0.00 m, 1/3 arc-second, about 10 m, source acquired 2018-03-02, raster 5079 (4.9 s)  <- exactly 0 offshore: sea, not a ground height
mid-Atlantic, far offshore (30.0, -40.0): NO ELEVATION, service said 'Call failed.  [Failed cloud operation: Open, Path: /vsimem/_0000005D.aux.xml]' (2.2 s)

Source: USGS Elevation Point Query Service (The National Map), 3DEP bare-earth DEMs, interpolated, not official surveyed values. Credit: U.S. Geological Survey.
```

### 2. robots.txt, terms, the docs' default, and how the API answers mistakes (browser)

6 page loads and 12 in-page `fetch()` calls in the same tab.

```python
import json, re, time

PAGE = "https://apps.nationalmap.gov/epqs/"
API = "https://epqs.nationalmap.gov/v1"
CAP = "x=-104.98484&y=39.73928"  # Colorado State Capitol: x = longitude, y = latitude

START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  const [url, method] = %s; fetch(url, {method, credentials: 'omit', cache: 'no-store'})
    .then(async r => { const t = await r.text(); window.__o[id] = {status: r.status, type: r.headers.get('content-type'), text: t.slice(0, 20000)}; })
    .catch(e => { window.__o[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def raw(url, method="GET"):
    """One in-page request -> status, type, body. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps([url, method])))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    time.sleep(1)
    return (js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus"),
            js("document.body ? document.body.innerText : ''") or "")

def one_line(s, n=110):
    return re.sub(r"\s+", " ", s).strip()[:n]

# 1. robots.txt on the two hosts this skill uses, and on the apex nationalmap.gov (a different host)
for host in ("epqs.nationalmap.gov", "apps.nationalmap.gov", "nationalmap.gov"):
    st, txt = page(f"https://{host}/robots.txt")
    groups = re.findall(r"(?im)^user-agent:\s*(\S+)", txt)
    print(f"https://{host}/robots.txt HTTP {st}: {one_line(txt, 90)!r}")
    if groups:
        dis = [g for g in groups if g != "*"]
        print(f"   {len(groups)} User-agent lines; '*' -> {re.findall(r'(?im)^content-signal:.*$', txt)} "
              f"+ 'Allow: /'; disallowed named agents include {[g for g in dis if g in ('GPTBot', 'ClaudeBot', 'anthropic-ai', 'Google-Extended', 'CCBot', 'Bytespider')]}; "
              f"not named: {[a for a in ('ChatGPT-User', 'OAI-SearchBot', 'Claude-User', 'PerplexityBot') if a not in groups]}")

# 2. the EPQS page: what it says the service does, and its links
st, txt = page(PAGE)
m = re.search(r"The Elevation Point Query Service returns.*?negative values\.", txt, re.S)
print(f"\nEPQS page HTTP {st}: {one_line(m[0], 400) if m else 'description NOT FOUND'}")
links = js("[...document.querySelectorAll('a')].map(a => [a.innerText.trim(), a.href]).filter(x => /API Doc|Bulk|Legal/.test(x[0]))")
print("links:", links)

# 3. the OpenAPI spec in /v1/docs: documented default units
r = raw(API + "/docs")
units = re.search(r'"name":\s*"units".*?"default":\s*"(\w+)"', r["text"], re.S)
print(f"\n/v1/docs HTTP {r['status']}: documented default units = {units[1] if units else 'NOT FOUND'}; "
      f"formats {re.findall(r'\"enum\":\s*\[\s*\"(json)\",\s*\"(xml)\"', r['text'])}")

# 4. USGS Copyrights and Credits: public domain, credit line, trademarked identifier
st, txt = page("https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits")
for pat in (r"USGS-authored or produced data and information are considered to be in the U\.S\.\s*Public Domain",
            r"Credit:\s+U\.S\.\s+Geological\s+Survey", r"This\s+identifier\s+is\s+trademarked[^.]*\."):
    hit = re.search(pat, txt)
    print(f"copyrights page HTTP {st}: {one_line(hit[0], 160) if hit else 'NOT FOUND: ' + pat}")

# 5. how the API answers common mistakes (fetch from the EPQS page)
page(PAGE)
probes = [
    ("units=Feet (number)", f"{API}/json?{CAP}&wkid=4326&units=Feet"),
    ("units=Meters (string)", f"{API}/json?{CAP}&wkid=4326&units=Meters"),
    ("units left out", f"{API}/json?{CAP}&wkid=4326"),
    ("units=Yards", f"{API}/json?{CAP}&wkid=4326&units=Yards"),
    ("includeDate=1", f"{API}/json?{CAP}&units=Feet&includeDate=1"),
    ("includeDate=true", f"{API}/json?{CAP}&units=Feet&includeDate=true"),
    ("x and y swapped", f"{API}/json?x=39.73928&y=-104.98484&units=Feet"),
    ("y missing", f"{API}/json?x=-104.98484&units=Feet"),
    ("two points in x,y", f"{API}/json?x=-104.98484,-105.6836&y=39.73928,40.2549&units=Feet"),
    ("/v1/csv (no such path)", f"{API}/csv?{CAP}&units=Feet"),
    ("/v1/xml", f"{API}/xml?{CAP}&units=Feet"),
]
vals = {}
for label, url in probes:
    r = raw(url)
    body = r["text"].strip()
    v = None
    if body.startswith("{"):
        d = json.loads(body)
        v = d.get("value")
        extra = f"value={v!r} ({type(v).__name__}), attributes={d.get('attributes')}" if "value" in d else one_line(body, 80)
    else:
        extra = one_line(body, 95)
    vals[label] = v
    print(f"{label:<22} HTTP {r['status']} {r['type']}: {extra}")

ft, m = float(vals["units=Feet (number)"]), float(vals["units=Meters (string)"])
print(f"\nfeet x 0.3048 = {ft * 0.3048:.6f} m; service meters = {m:.6f} m; diff {abs(ft * 0.3048 - m) * 1000:.4f} mm")
```

Output (from the run on 2026-11-18, 00:09 UTC; the browser shows the 403 S3 XML through Chrome's XML viewer, hence "This XML file does not appear..."):

```text
https://epqs.nationalmap.gov/robots.txt HTTP 403: '{"message":"Missing Authentication Token"}'
https://apps.nationalmap.gov/robots.txt HTTP 403: 'This XML file does not appear to have any style information associated with it. The docume'
https://nationalmap.gov/robots.txt HTTP 200: '# As a condition of accessing this website, you agree to abide by the following # content '
   33 User-agent lines; '*' -> ['Content-Signal: search=yes,ai-train=no,use=reference'] + 'Allow: /'; disallowed named agents include ['Bytespider', 'CCBot', 'ClaudeBot', 'Google-Extended', 'GPTBot', 'anthropic-ai']; not named: ['ChatGPT-User', 'OAI-SearchBot', 'Claude-User', 'PerplexityBot']

EPQS page HTTP 200: The Elevation Point Query Service returns the elevation in international feet or meters for a specific latitude/longitude (NAD 1983) point from the USGS Elevation Service hosted at the NGTOC. Input parameters: x (longitude), y (latitude), units (Feet, Meters), output (XML, JSON). Latitude and longitude must be specified in decimal degrees with southern latitudes and western longitudes represented 
links: [['API Documentation', 'https://epqs.nationalmap.gov/v1/docs'], ['Bulk Point Query', 'https://apps.nationalmap.gov/bulkpqs/'], ['Legal', 'https://www.usgs.gov/policies-and-notices']]

/v1/docs HTTP 200: documented default units = Feet; formats [('json', 'xml')]
copyrights page HTTP 200: USGS-authored or produced data and information are considered to be in the U.S. Public Domain
copyrights page HTTP 200: Credit: U.S. Geological Survey
copyrights page HTTP 200: This identifier is trademarked and must be used in accordance with the rules outlined in the Visual Identity System.
units=Feet (number)    HTTP 200 application/json: value=5275.9864072469145 (float), attributes=None
units=Meters (string)  HTTP 200 application/json: value='1608.120605469' (str), attributes=None
units left out         HTTP 200 application/json: value='1608.120605469' (str), attributes=None
units=Yards            HTTP 200 application/json: value='1608.120605469' (str), attributes=None
includeDate=1          HTTP 200 application/json: value=5275.9864072469145 (float), attributes=None
includeDate=true       HTTP 200 application/json: value=5275.9864072469145 (float), attributes={'AcquisitionDate': '2/6/2021'}
x and y swapped        HTTP 200 application/json: The operation was attempted on an empty geometry.
y missing              HTTP 400 application/json: {"errorMessage" : "[BadRequest] missing parameters"}
two points in x,y      HTTP 200 application/json: Call failed. [Failed cloud operation: Open, Path: /vsimem/_000000B3.aux.xml]
/v1/csv (no such path) HTTP 0 : TypeError: Failed to fetch
/v1/xml                HTTP 200 application/xml: <?xml version="1.0" encoding="UTF-8"?><result><location><x>-104.98484</x><y>39.73928</y><spatia

feet x 0.3048 = 1608.120657 m; service meters = 1608.120605 m; diff 0.0515 mm
```

### 3. Elevation profile along a route with Python urllib, robots per RFC 9309 (no browser)

Give waypoints; the block adds a point every `STEP_KM` on each leg, asks each one serially, and prints the profile, the lowest and highest points and the sums of rises and drops. 1 robots.txt fetch and 12 API calls.

```python
import json, math, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ROUTE = [(39.73928, -104.98484), (40.2549, -105.6836)]  # waypoints (lat, lon); any polyline works
STEP_KM = 8.0      # one sample every ~8 km along each leg, plus every waypoint
PAUSE = 1.0        # seconds between calls; no rate limit is published, so stay serial

API = "https://epqs.nationalmap.gov/v1/json"
UA = "usgs-elevation-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
FT_TO_M = 0.3048

def retry_after(v, default):
    """Retry-After in seconds (a number or an HTTP date); default when absent or unreadable; at least 1.
    Over 120 s: stop rather than hammer or hang."""
    try:
        sec = float(v)
    except (TypeError, ValueError):
        try:
            sec = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            sec = default
    if sec != sec:  # 'nan'
        sec = default
    if sec > 120:
        sys.exit(f"server asks to wait {sec:.0f} s (over 120 s): stopping")
    return max(sec, 1)

def http(url, timeout=60):
    """GET -> (status, content-type, text, Retry-After header); HTTP errors are returned, not raised."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode(), None
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode(errors="replace"), e.headers.get("Retry-After")

def robots_ok(host, path):
    """RFC 9309 by hand: 2xx -> parse; 4xx -> 'unavailable', any path allowed; 5xx/network -> stop.
    (urllib.robotparser treats 401/403 as 'disallow all', which is not what RFC 9309 section 2.3.1.3 says.)"""
    try:
        st, ctype, text, _ = http(f"https://{host}/robots.txt", timeout=30)
    except OSError as e:
        sys.exit(f"robots.txt on {host} unreachable ({e}): stop")
    if 400 <= st < 500:
        return f"HTTP {st} {ctype}: unavailable, every path allowed (RFC 9309 2.3.1.3)"
    if st >= 500:
        sys.exit(f"robots.txt on {host}: HTTP {st}, unreachable: stop")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    agents = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
              "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
    bad = [a for a in agents if not rp.can_fetch(a, f"https://{host}{path}")]
    if bad:
        sys.exit(f"robots.txt on {host} now disallows {path} for {bad}: stop")
    return f"HTTP {st}: {path} allowed for all {len(agents)} agents"

def elevation_ft(lat, lon):
    """-> (feet, resolution, AcquisitionDate) or (None, error text, None). units=Feet always (left out = meters).
    A non-JSON 200 body means no elevation at that point; it is retried once, as are 429, 5xx and network errors
    (after Retry-After when sent)."""
    url = f"{API}?x={lon:.6f}&y={lat:.6f}&wkid=4326&units=Feet&includeDate=true"  # x = longitude, y = latitude
    for attempt in range(2):
        try:
            st, ctype, body, ra = http(url)
        except OSError as e:  # URLError, timeouts, resets
            st, ctype, body, ra = 0, "", str(e), None
        body = body.strip()
        retry = st in (0, 429, 500, 502, 503, 504) or (st == 200 and not body.startswith("{"))
        if retry and attempt == 0:
            time.sleep(retry_after(ra, 60 if st == 429 else 3) if st != 200 else 3)
            continue
        if st == 200 and body.startswith("{"):
            d = json.loads(body)
            try:
                return float(d["value"]), d.get("resolution"), (d.get("attributes") or {}).get("AcquisitionDate")
            except (KeyError, TypeError, ValueError):
                return None, f"no value in {body[:100]!r}", None
        if st == 200:
            return None, body[:100], None
        sys.exit(f"HTTP {st} {ctype} {body[:200]!r} for {url}")

def km(a, b):
    (la1, lo1), (la2, lo2) = [(math.radians(p[0]), math.radians(p[1])) for p in (a, b)]
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))

def densify(route, step):
    """Waypoints plus evenly spaced points on each leg (linear in lat/lon, fine for legs of tens of km)."""
    out = [route[0]]
    for a, b in zip(route, route[1:]):
        n = max(1, math.ceil(km(a, b) / step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(1, n + 1)]
    return out

print(f"robots epqs.nationalmap.gov: {robots_ok('epqs.nationalmap.gov', '/v1/json')}")
time.sleep(PAUSE)

pts = densify(ROUTE, STEP_KM)
print(f"{len(pts)} points, {sum(km(a, b) for a, b in zip(pts, pts[1:])):.1f} km straight-line legs\n")
print(f"{'km':>6}  {'lat':>9} {'lon':>11}  {'feet':>9} {'meters':>8}  res   acquired")
rows, dist, t0 = [], 0.0, time.time()
for i, p in enumerate(pts):
    if i:
        dist += km(pts[i - 1], p)
        time.sleep(PAUSE)
    ft, res, date = elevation_ft(*p)
    rows.append((dist, p, ft))
    if ft is None:
        print(f"{dist:6.1f}  {p[0]:9.5f} {p[1]:11.5f}  NO ELEVATION: {res}")
    else:
        print(f"{dist:6.1f}  {p[0]:9.5f} {p[1]:11.5f}  {ft:9,.1f} {ft * FT_TO_M:8,.1f}  {'?' if res is None else format(res, 'g'):<5} {date}")
secs = time.time() - t0

good = [r for r in rows if r[2] is not None]
if len(good) < 2:
    sys.exit("fewer than 2 elevations: no profile")
# rises and drops only between neighbouring samples that both have a value; a gap is not bridged
pairs = [(a, b) for a, b in zip(rows, rows[1:]) if a[2] is not None and b[2] is not None]
gaps = len(rows) - 1 - len(pairs)
up = sum(max(0, b[2] - a[2]) for a, b in pairs)
down = sum(max(0, a[2] - b[2]) for a, b in pairs)
lo, hi = min(good, key=lambda r: r[2]), max(good, key=lambda r: r[2])
print(f"\n{len(good)}/{len(rows)} points with an elevation in {secs:.0f} s ({secs / len(rows):.1f} s per point incl. {PAUSE:g} s pause)")
print(f"start {good[0][2]:,.0f} ft, end {good[-1][2]:,.0f} ft; lowest {lo[2]:,.0f} ft at km {lo[0]:.1f}, "
      f"highest {hi[2]:,.0f} ft at km {hi[0]:.1f}")
print(f"sum of rises {up:,.0f} ft, sum of drops {down:,.0f} ft between samples {STEP_KM:g} km apart "
      f"(a lower bound: climbs between samples are missed)")
if gaps:
    print(f"PARTIAL: {gaps} of {len(rows) - 1} legs skipped because a sample had no elevation")
print("\nSource: USGS Elevation Point Query Service (The National Map). Credit: U.S. Geological Survey.")
```

Output (from the run on 2026-11-18, 00:10 UTC):

```text
robots epqs.nationalmap.gov: HTTP 403 application/json: unavailable, every path allowed (RFC 9309 2.3.1.3)
12 points, 82.6 km straight-line legs

    km        lat         lon       feet   meters  res   acquired
   0.0   39.73928  -104.98484    5,276.0  1,608.1  1     2/6/2021
   7.5   39.78615  -105.04836    5,363.6  1,634.8  1     2/6/2021
  15.1   39.83303  -105.11189    5,626.7  1,715.0  1     2/6/2021
  22.6   39.87990  -105.17541    5,694.0  1,735.5  1     2/6/2021
  30.1   39.92678  -105.23893    5,944.1  1,811.8  1     2/6/2021
  37.6   39.97365  -105.30246    7,491.9  2,283.5  1     2/6/2021
  45.1   40.02053  -105.36598    7,053.6  2,149.9  1     9/1/2023
  52.6   40.06740  -105.42951    7,889.1  2,404.6  1     9/1/2023
  60.1   40.11428  -105.49303    8,682.4  2,646.4  1     9/1/2023
  67.6   40.16115  -105.55655   10,418.4  3,175.5  1     9/1/2023
  75.1   40.20803  -105.62008    9,740.2  2,968.8  1     2/6/2021
  82.6   40.25490  -105.68360   10,492.7  3,198.2  1     2/6/2021

12/12 points with an elevation in 38 s (3.1 s per point incl. 1 s pause)
start 5,276 ft, end 10,493 ft; lowest 5,276 ft at km 0.0, highest 10,493 ft at km 82.6
sum of rises 6,333 ft, sum of drops 1,116 ft between samples 8 km apart (a lower bound: climbs between samples are missed)

Source: USGS Elevation Point Query Service (The National Map). Credit: U.S. Geological Survey.
```

### 4. curl

```bash
E=https://epqs.nationalmap.gov/v1/json
UA='usgs-elevation-skill-example/1.0'
# one point (x = LONGITUDE, y = latitude); check the body is JSON before parsing it
curl -sS --fail -A "$UA" "$E?x=-104.98484&y=39.73928&wkid=4326&units=Feet&includeDate=true" | python3 -c 'import sys, json
b = sys.stdin.read().strip()
if not b.startswith("{"): sys.exit("no elevation: " + b[:100])
d = json.loads(b); ft = float(d["value"]); a = d.get("attributes") or {}
print(f"{ft:,.2f} ft = {ft * 0.3048:,.2f} m, resolution", d["resolution"], "acquired", a.get("AcquisitionDate"))'
sleep 1
# headers: open CORS, no cache or rate-limit headers (API Gateway behind CloudFront)
curl -sS -D - -o /dev/null -A "$UA" "$E?x=-104.98484&y=39.73928&units=Feet" | tr -d '\r' | grep -iE '^(HTTP/|content-type|access-control|cache-control|x-ratelimit|retry-after|x-cache|via)'
sleep 1
# mistakes: errors come back as HTTP 200 plain text labelled application/json, except a missing parameter (400)
for q in "x=39.73928&y=-104.98484&units=Feet" "x=-0.1276&y=51.5072&units=Feet" "x=-104.98484&units=Feet"; do
  curl -sS -A "$UA" -w "  <- HTTP %{http_code} %{content_type} ($q)\n" "$E?$q"; sleep 1
done
# unknown path and POST: HTTP 403 from API Gateway
curl -sS -A "$UA" -X POST -w "  <- HTTP %{http_code} (POST /v1/json)\n" "$E?x=-104.98484&y=39.73928&units=Feet"; sleep 1
curl -sS -A "$UA" -w "  <- HTTP %{http_code} (GET /v1/)\n" https://epqs.nationalmap.gov/v1/; sleep 1
# robots.txt on both hosts: HTTP 403, no file served
for h in epqs.nationalmap.gov apps.nationalmap.gov; do
  curl -sS -A "$UA" -o /dev/null -w "https://$h/robots.txt -> HTTP %{http_code} %{content_type}\n" "https://$h/robots.txt"; sleep 1
done
```

Output (from the run on 2026-11-18, 00:46 UTC):

```text
5,275.99 ft = 1,608.12 m, resolution 1 acquired 2/6/2021
HTTP/2 200 
content-type: application/json
access-control-allow-origin: *
x-cache: Miss from cloudfront
via: 1.1 109f4ff6e5e144109ffbce3fd668a510.cloudfront.net (CloudFront)
The operation was attempted on an empty geometry.  <- HTTP 200 application/json (x=39.73928&y=-104.98484&units=Feet)
Call failed.  [Failed cloud operation: Open, Path: /vsimem/_00000514.aux.xml]  <- HTTP 200 application/json (x=-0.1276&y=51.5072&units=Feet)
 {"errorMessage" : "[BadRequest] missing parameters"}  <- HTTP 400 application/json (x=-104.98484&units=Feet)
{"message":"Missing Authentication Token"}  <- HTTP 403 (POST /v1/json)
{"message":"Missing Authentication Token"}  <- HTTP 403 (GET /v1/)
https://epqs.nationalmap.gov/robots.txt -> HTTP 403 application/json
https://apps.nationalmap.gov/robots.txt -> HTTP 403 application/xml
```

## Fields (`/v1/json`)

| Field | Example (Colorado State Capitol) | Notes |
|---|---|---|
| `value` | `5275.9864072469145` (Feet), `"1608.120605469"` (Meters) | a number in Feet, a **string** in Meters; `0` offshore |
| `resolution` | `1` | metres for 1 m and 5 m DEMs (`1`, `5`); **degrees** for arc-second DEMs (`0.0000925926` = 1/3 arc-second, `0.000277778` = 1 arc-second, `0.0000308642` = 1/9 arc-second) |
| `attributes.AcquisitionDate` | `2/6/2021` | M/D/YYYY; only with `includeDate=true`; can have day 0 (`4/0/2023`) |
| `rasterId` | `53518` | the source raster |
| `location.x`, `location.y` | `-104.98484`, `39.73928` | echo of your input; x = longitude |
| `location.spatialReference` | `{"wkid": 4326, "latestWkid": 4326}` | `wkid=102100` (Web Mercator) also works |
| `locationId` | `0` | always 0 in this run |

Units are international feet (EPQS page). The USGS FAQ on 3DEP DEMs (https://www.usgs.gov/faqs/what-are-projection-horizontal-and-vertical-datum-units-and-resolution-3dep-standard-dems) gives the horizontal datum as NAD83 and the vertical datum as "Typically the North American Vertical Datum of 1988 (NAVD88)", with local mean sea level typical for Hawaii, Puerto Rico, the U.S. Virgin Islands and the Pacific Island territories, and the arc-second sizes used above (1/3 arc-second "~10 meters", 1 arc-second "~30 meters", 1/9 arc-second "~3 meters").

## Gotchas

- **x is longitude, y is latitude.** `x=39.73928&y=-104.98484` (swapped) and `y=95` both return `The operation was attempted on an empty geometry.` Block 1 also refuses out-of-range input before calling.
- **Errors are HTTP 200 plain text labelled `application/json`.** Only a missing `x` or `y` is HTTP 400 (` {"errorMessage" : "[BadRequest] missing parameters"}`). Check that the body starts with `{` before `json.loads`.
- **The error text changes from call to call.** The same mid-Atlantic point (30, -40) returned `Invalid or missing input parameters.`, `Call failed.  [Failed cloud operation: Open, Path: /vsimem/_00000027.aux.xml]` and, in the 2026-11-17 terms check, `The specified WKID (factory code) or WKT (definition string) is not a Geographic Coordinate System.` Do not match on the message; treat any non-JSON 200 as "no elevation" after one retry.
- **`units` left out means meters, not feet.** The docs say `"default": "Feet"`; the service returned `"1608.120605469"` (meters, string). `units=feet` and `FEET` give feet; `units=Yards` silently gives meters.
- **Meters come as a string.** `"value":"1608.120605469"` with `units=Meters`, a float with `units=Feet`. `float()` both. Feet x 0.3048 and the service's meters differ by 0.05 mm (block 2).
- **`includeDate=1` is ignored.** Only `true` (or `True`) adds `attributes.AcquisitionDate`.
- **Water is not an error.** Offshore points return exactly `0` (Pacific at 37.5, -123.5; off Cape Cod at 41.5, -69.5) and Lake Michigan open water (44.0, -87.0) returned 579.70 ft. A value does not mean the point is on land.
- **Not US-only, not worldwide.** Toronto (43.6532, -79.3832) returned 294.77 ft and Mexico City (19.4326, -99.1332) 7,385.17 ft from arc-second rasters; London (51.5072, -0.1276) and the open Atlantic returned plain-text errors. Puerto Rico (18.22, -66.59) and Guam (13.44, 144.79) returned values.
- **`resolution` mixes units.** `1` and `5` are metres; `0.00009259259341472414` is degrees (1/3 arc-second). Block 1's `res_text()` labels them.
- **Bare earth, interpolated.** USGS FAQs: a DEM is "the bare ground (bare earth) topographic surface of the Earth excluding trees, buildings, and any other surface objects", and EPQS values "might differ from monumented control elevation values ... for features such as mountain peaks or summits". Do not quote them as survey heights.
- **Slow and uneven.** `curl` time per call ranged from 0.09 s (the 400) to 15.07 s (the Hawaii point, which took 5.9 s in block 1). In a 2026-11-18 verify run one call returned HTTP 504 `{"message": "Endpoint request timed out"}` after 29.1 s and the same query answered in 0.2 s on retry. Use a 60 s timeout and retry 5xx once. Block 3 averaged 3.1 s per point including the 1 s pause.
- **No batch in the API.** `x=-104.98484,-105.6836&y=39.73928,40.2549` returned `Unable to complete operation.` and, later, `Call failed. ...`. The Bulk Point Query page (https://apps.nationalmap.gov/bulkpqs/) takes an uploaded text or CSV file of `longitude,latitude` lines; its instructions say "Number of coordinates cannot exceed 500". It is a web form, not tested here.
- **Unknown paths are HTTP 403 without CORS.** `/v1/`, `/v1/csv` and `POST /v1/json` return HTTP 403 `{"message":"Missing Authentication Token"}` (block 4); in the browser `/v1/csv` fails as `TypeError: Failed to fetch` because that answer has no `access-control-allow-origin`.
- **Other `wkid` values.** `wkid=102100` with Web Mercator metres works (5,268.93 ft at x=-11686597, y=4828890, a point about 0.6 km north-northeast of the Capitol); `wkid=3857` with degrees gave `Call failed. ...`, `wkid=9999` gave `'spatialReference' parameter is invalid.`
- **www.usgs.gov from a datacenter.** curl to https://www.usgs.gov/robots.txt got a CloudFront HTTP 403 error page on 2026-11-17 but HTTP 200 from the same kind of machine on 2026-11-18, so the block is intermittent; the cloud browser loaded the USGS pages with HTTP 200 both days. The API host was not affected.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.href`, never the title.

## What does not work

- **Several points in one request:** no such parameter in the OpenAPI spec (query parameters `x`, `y`, `wkid`, `units`, `includeDate`, plus the `/{format}` path, `json` or `xml`); comma lists fail. Loop serially (block 3) or use the Bulk Point Query web page for up to 500.
- **A route or profile endpoint:** none; sample the line yourself. Sums of rises between samples are a lower bound on the real climb.
- **Formats other than `json` and `xml`:** `/v1/csv` is HTTP 403.
- **Not tested:** rate-limit behaviour (never provoked), parallel requests, the Bulk Point Query upload, and accuracy against surveyed benchmarks.
