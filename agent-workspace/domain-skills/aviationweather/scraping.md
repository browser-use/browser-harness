# Aviation Weather Center (aviationweather.gov) - Current METAR and TAF for JFK and SFO, and Which Airport Is VFR or Below Right Now (official keyless API)

Field-tested against aviationweather.gov on 2026-11-13 (23:29-23:35 UTC) using a fresh Browser Use cloud browser (logged out) plus Python urllib and `curl` from a Linux server. 10 browser page loads and 22 in-page `fetch()` calls, about 47 curl calls and 2 urllib calls to aviationweather.gov, all serial at 1 s or more spacing: every API call was HTTP 200 or the documented 204 except the deliberate HTTP 400 probes below and one HTTP 504 (the very first curl call, after 20 s; the retry 3 s later was 200); robots.txt was 404 and `www.` was a 308 redirect (both below). No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-13, curl and the cloud browser): https://aviationweather.gov/robots.txt is an nginx HTTP 404 page (`404 Not Found`), the same for User-Agent `*`, GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot, Bytespider, Applebot-Extended and Meta-ExternalAgent: no rules, no named AI-agent groups, so `/api/data/` is allowed for all of them (RFC 9309 section 2.3.1.3: when robots.txt is unavailable, a 400-499 status, "the crawler MAY access any resources on the server"). Terms: the Data API page (https://aviationweather.gov/data/api/, the OpenAPI spec's `termsOfService`) needs no key and asks you to "Set a custom user agent", keep to a "maximum 100 requests per minute" ("Exceeding request limits will result in access being blocked"), says "Most endpoints return a maximum of 400 entries (please consider using cache files for larger requests)", "Cross-origin resource sharing is not permitted at this time" and "Undocumented query parameter requests are restricted and will result in an error". The NWS disclaimer (https://www.weather.gov/disclaimer): NWS web information is "in the public domain, unless specifically noted otherwise, and may be used without charge for any lawful purpose so long as you do not: 1) claim it is your own ..., 2) use it in a manner that implies an endorsement or affiliation with NOAA/NWS, or 3) modify its content and then present it as official government material"; the NWS name and visual identifier are trademarks, but using the name "to identify unaltered NWS content or links to NWS web sites are allowable uses"; and "The user assumes the entire risk related to its use". No AI/ML, scraping, automated-access or non-commercial clause. This skill names the source "Aviation Weather Center (aviationweather.gov)" in plain text, shows no NOAA or NWS logo, prints the reports unaltered and labels its own category calculation as such. It is not affiliated with or endorsed by NOAA or the NWS.

**Not for flight planning.** This skill reads public reports for a quick look. Pilots: get an official weather briefing before flying.

## Quick summary

- **No scraping.** `GET https://aviationweather.gov/api/data/metar?ids=KJFK,KSFO&format=json` returns the latest METAR per station with `rawOb` (the report as issued) and `fltCat` (`VFR`, `MVFR`, `IFR`, `LIFR`). `GET /api/data/taf?ids=KJFK,KSFO&format=json` returns the TAF with `rawTAF` and decoded `fcsts[]` groups. No key.
- **Answer (2026-11-13, 23:34 UTC):** **KJFK is MVFR** (below VFR): `METAR KJFK 132251Z 36010KT 10SM -RA BKN019 OVC065 ...`, ceiling 1,900 ft in light rain. **KSFO is VFR**: `METAR KSFO 132256Z 28016KT 10SM FEW017 FEW045 SCT100 SCT150 ...`, no ceiling, 10+ miles. Both reports were about 40 minutes old.
- **"Right now" = the METAR.** The KSFO TAF group in force (21:00-00:00 UTC) forecast `4SM RA BR BKN024 OVC029`, MVFR, while the 22:56 observation was VFR. Report the METAR category; show the TAF as the forecast.
- **Category rules** (FAA AIM 7-1-7, https://www.faa.gov/air_traffic/publications/atpubs/aim_html/chap7_section_1.html): LIFR ceiling below 500 ft and/or visibility below 1 mile; IFR 500 to below 1,000 ft and/or 1 to below 3 miles; MVFR 1,000 to 3,000 ft and/or 3 to 5 miles; VFR ceiling above 3,000 ft and visibility above 5 miles. Ceiling = lowest BKN or OVC layer, or vertical visibility into a total obscuration (FAA AC 00-45H Change 2, 3.7.1.2.9, https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_00-45H_Chg_2.pdf). Block 1 recomputes it and agreed with `fltCat` for both stations. TAF groups have no `fltCat`; block 1 computes theirs.
- **4-letter ICAO ids.** `KJFK`, not `JFK`: `ids=JFK` is HTTP 204, the same as a station that does not exist. Lower case `kjfk` works.
- **Empty answers differ by route.** Unknown station on `/metar`: HTTP 204, empty body. On `/taf`: HTTP 200 `[]`. Check that every requested station came back.
- **Rate limit:** 100 requests per minute, max 400 results per query; use the cache files (`/data/cache/metars.cache.csv.gz`, updated "Once a minute") for bulk. Blocks pace 1 s per call, serial, and wait 60 s once on 429/5xx (the NWS disclaimer: "limit the number of retries to 1 minute intervals").

## What works

### 1. METAR, TAF and flight category for KJFK and KSFO (browser)

`on_awc_tab()` opens the Data API page on aviationweather.gov once, so `fetch()` is same-origin (the API sends no CORS header, so a fetch from any other site fails; block 2 shows it). A browser `fetch()` cannot set its own User-Agent; the cloud browser's Chrome one got HTTP 200. `get()` returns parsed JSON on 200, `[]` on 204, waits 60 s once on 429/5xx and otherwise raises, so an error never looks like "no weather".

```python
import json, re, time
from datetime import datetime, timezone

STATIONS = ["KJFK", "KSFO"]  # 4-letter ICAO ids; "JFK" alone is HTTP 204 (no data), not an error

SITE = "https://aviationweather.gov"
PAUSE = 1.0  # data/api: "maximum 100 requests per minute", "Exceeding request limits will result in access being blocked"

def on_awc_tab():
    """fetch() runs same-origin from a logged-out aviationweather.gov tab (the Data API page). The API sends no CORS
    headers ("Cross-origin resource sharing is not permitted"), so a fetch from any other site's page fails. Reuse the tab."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/data/api/")
    wait_for_load()
    if js("location.origin") != SITE:
        raise RuntimeError(f"aviationweather.gov did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__awc = window.__awc || {}; const id = String(Math.random()).slice(2); window.__awc[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { window.__awc[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__awc[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__awc[%s]; if (v) delete window.__awc[%s]; return v; })()"""

def get(path, timeout=60):
    """GET SITE+path from inside the tab -> parsed JSON list. HTTP 204 (valid request, no data) -> [].
    400 is {"status":"error","error":"..."} and raises. Waits 60 s once on 429/5xx (the NWS disclaimer asks for
    retries at 1-minute intervals; a cold call here once took 20 s and came back 504)."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        if r["status"] == 204:
            return []
        if r["status"] != 200 or "json" not in (r["type"] or ""):
            raise RuntimeError(f"{path}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
        return json.loads(r["text"])
    raise RuntimeError(f"{path}: still failing after one retry: stop")

def miles(v):
    """'10+' (METAR) / '6+' (TAF) -> 10 / 6; '1 1/2' -> 1.5; numbers pass through; ''/None -> None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().rstrip("+").lstrip("PM")
    m = re.fullmatch(r"(?:(\d+) )?(\d+)/(\d+)", s)
    return int(m[1] or 0) + int(m[2]) / int(m[3]) if m else float(s)

def ceiling(clouds, vert_vis):
    """Lowest broken (BKN), overcast (OVC) or obscured (OVX) layer, or vertical visibility, in feet; None = no ceiling."""
    bases = [c["base"] for c in clouds or [] if c.get("cover") in ("BKN", "OVC", "OVX") and c.get("base") is not None]
    if vert_vis is not None:
        bases.append(vert_vis)
    return min(bases) if bases else None

def category(ceil_ft, vis_sm):
    """FAA AIM 7-1-7: LIFR ceiling < 500 ft and/or vis < 1 mi; IFR 500 to < 1,000 and/or 1 to < 3;
    MVFR 1,000 to 3,000 and/or 3 to 5 inclusive; VFR ceiling > 3,000 and vis > 5. The worse of the two wins.
    ceil_ft None = no ceiling. vis_sm None = unknown: the ceiling alone gives "LIFR", "IFR or worse",
    "MVFR or worse", or "?" (it cannot tell VFR)."""
    c = ceil_ft if ceil_ft is not None else 99999
    by_ceil = "LIFR" if c < 500 else "IFR" if c < 1000 else "MVFR" if c <= 3000 else "VFR"
    if vis_sm is None:
        return {"LIFR": "LIFR", "VFR": "?"}.get(by_ceil, by_ceil + " or worse")
    by_vis = "LIFR" if vis_sm < 1 else "IFR" if vis_sm < 3 else "MVFR" if vis_sm <= 5 else "VFR"
    order = ["LIFR", "IFR", "MVFR", "VFR"]
    return min(by_ceil, by_vis, key=order.index)

def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc)

on_awc_tab()
ids = ",".join(STATIONS)
now = datetime.now(timezone.utc)
print(f"now {now:%Y-%m-%d %H:%M} UTC")

# 1. Latest METAR per station: fltCat is the API's flight category, rawOb the report as issued.
metars = get(f"/api/data/metar?ids={ids}&format=json")
by_id = {m["icaoId"]: m for m in metars}
missing = [s for s in STATIONS if s not in by_id]
if missing:
    raise RuntimeError(f"no recent METAR for {missing} (unknown ids and stations without data both give HTTP 204): stop")
answer = {}
for s in STATIONS:
    m = by_id[s]
    obs = utc(m["obsTime"])
    ceil_ft, vis = ceiling(m.get("clouds"), m.get("vertVis")), miles(m.get("visib"))
    ours = category(ceil_ft, vis)
    print(f"\n{s} {m['name']}")
    print(f"  METAR {m['rawOb']}")
    print(f"  observed {obs:%d %H:%M} UTC ({(now - obs).total_seconds() / 60:.0f} min ago), {m['metarType']}")
    print(f"  ceiling {f'{ceil_ft} ft' if ceil_ft is not None else 'none'}, visibility {m.get('visib')} sm, weather {m.get('wxString') or '-'}")
    print(f"  fltCat (API) {m.get('fltCat') or '?'}; AIM 7-1-7 from ceiling/visibility {ours}")
    if m.get("fltCat") and ours != "?" and ours != m["fltCat"]:
        print(f"  NOTE: categories differ, quoting the API's {m['fltCat']}")
    if m["rawOb"].rstrip().endswith("$"):
        print("  NOTE: rawOb ends with '$', the maintenance indicator: the automated station needs maintenance (FAA AC 00-45H 3.1.5.14.1)")
    answer[s] = m.get("fltCat") or ours

# 2. Current TAF per station: each fcsts[] group, with its category (TEMPO/PROB groups inherit what they do not change).
tafs = get(f"/api/data/taf?ids={ids}&format=json")  # an unknown id is HTTP 200 [] here, not 204
by_id = {t["icaoId"]: t for t in tafs if t.get("mostRecent", 1)}
for s in STATIONS:
    t = by_id.get(s)
    print(f"\n{s} TAF")
    if not t:
        print("  no TAF in force (not every airport has one)")
        continue
    print(f"  {t['rawTAF']}")
    print(f"  issued {t['issueTime'][:16]}Z, valid {utc(t['validTimeFrom']):%d %H:%M}..{utc(t['validTimeTo']):%d %H:%M} UTC")
    base = {}  # prevailing conditions: the base group, each FM, and each BECMG merged on top of what it changes
    for g in t["fcsts"]:
        kind = g.get("fcstChange") or "BASE"
        sky = bool(g.get("clouds")) or g.get("vertVis") is not None  # the group restates the sky
        clouds = g["clouds"] if sky else base.get("clouds")
        vv = g.get("vertVis") if sky else base.get("vertVis")
        vis = g.get("visib") if g.get("visib") not in (None, "") else base.get("visib")
        if kind in ("BASE", "FM", "BECMG"):  # these set the prevailing conditions; TEMPO and PROB do not
            base = {"clouds": clouds, "vertVis": vv, "visib": vis}
        a, b = utc(g["timeFrom"]), utc(g["timeTo"])
        flag = "  <- now" if a <= now < b else ""
        prob = f" PROB{g['probability']}" if g.get("probability") else ""
        cf = ceiling(clouds, vv)
        print(f"  {kind:<6}{prob} {a:%d %H:%M}..{b:%d %H:%M} UTC  ceiling {f'{cf} ft' if cf is not None else 'none'}, "
              f"vis {vis} sm, {g.get('wxString') or '-'} -> {category(cf, miles(vis))}{flag}")

below = [s for s in STATIONS if answer[s] not in ("VFR", "?")]
unknown = [s for s in STATIONS if answer[s] == "?"]  # no fltCat and no visibility: not counted either way
print("\nanswer (latest METAR): " + ", ".join(f"{s} {answer[s]}" for s in STATIONS) + "; "
      + (f"below VFR: {', '.join(below)}" if below else "none below VFR")
      + (f"; category unknown: {', '.join(unknown)}" if unknown else ""))
print("  Source: Aviation Weather Center (aviationweather.gov), NWS data; the TAF group categories are our calculation (FAA AIM 7-1-7).")
print("  Not for flight planning: get an official weather briefing before flying.")
```

Output (from the run on 2026-11-13, 23:34 UTC):

```text
now 2026-11-13 23:34 UTC

KJFK New York/JF Kennedy Intl, NY, US
  METAR METAR KJFK 132251Z 36010KT 10SM -RA BKN019 OVC065 05/02 A2970 RMK AO2 RAB44 SLP057 P0000 T00500022 $
  observed 13 22:51 UTC (44 min ago), METAR
  ceiling 1900 ft, visibility 10+ sm, weather -RA
  fltCat (API) MVFR; AIM 7-1-7 from ceiling/visibility MVFR
  NOTE: rawOb ends with '$', the maintenance indicator: the automated station needs maintenance (FAA AC 00-45H 3.1.5.14.1)

KSFO San Francisco Intl, CA, US
  METAR METAR KSFO 132256Z 28016KT 10SM FEW017 FEW045 SCT100 SCT150 16/11 A2961 RMK AO2 SLP026 T01560106
  observed 13 22:56 UTC (39 min ago), METAR
  ceiling none, visibility 10+ sm, weather -
  fltCat (API) VFR; AIM 7-1-7 from ceiling/visibility VFR

KJFK TAF
  TAF KJFK 132035Z 1321/1424 35014G20KT P6SM VCSH BKN020 BKN040 FM140000 34011KT P6SM SCT018 BKN040 TEMPO 1400/1404 BKN018 FM141400 31015G25KT P6SM BKN050
  issued 2026-11-13T20:35Z, valid 13 21:00..15 00:00 UTC
  BASE   13 21:00..14 00:00 UTC  ceiling 2000 ft, vis 6+ sm, VCSH -> MVFR  <- now
  FM     14 00:00..14 14:00 UTC  ceiling 4000 ft, vis 6+ sm, - -> VFR
  TEMPO  14 00:00..14 04:00 UTC  ceiling 1800 ft, vis 6+ sm, - -> MVFR
  FM     14 14:00..15 00:00 UTC  ceiling 5000 ft, vis 6+ sm, - -> VFR

KSFO TAF
  TAF KSFO 132102Z 1321/1424 33015KT 4SM RA BR BKN024 OVC029 FM140000 25015G20KT P6SM -SHRA OVC030 FM140400 25008KT P6SM VCSH OVC030 FM141000 20004KT P6SM SCT030 BKN050 FM142000 26006KT P6SM SCT030 BKN100
  issued 2026-11-13T21:02Z, valid 13 21:00..15 00:00 UTC
  BASE   13 21:00..14 00:00 UTC  ceiling 2400 ft, vis 4 sm, RA BR -> MVFR  <- now
  FM     14 00:00..14 04:00 UTC  ceiling 3000 ft, vis 6+ sm, -SHRA -> MVFR
  FM     14 04:00..14 10:00 UTC  ceiling 3000 ft, vis 6+ sm, VCSH -> MVFR
  FM     14 10:00..14 20:00 UTC  ceiling 5000 ft, vis 6+ sm, - -> VFR
  FM     14 20:00..15 00:00 UTC  ceiling 10000 ft, vis 6+ sm, - -> VFR

answer (latest METAR): KJFK MVFR, KSFO VFR; below VFR: KJFK
  Source: Aviation Weather Center (aviationweather.gov), NWS data; the TAF group categories are our calculation (FAA AIM 7-1-7).
  Not for flight planning: get an official weather briefing before flying.
```

### 2. robots.txt, the Data API rules and error shapes (browser)

Reads robots.txt and seven rules from the Data API page's "Using the API" tab (`/data/api/#api`; the default tab hides them), then makes 8 same-origin calls, mostly deliberate errors, and one cross-origin call from example.com to show the CORS block.

```python
import json, time

SITE = "https://aviationweather.gov"

# robots.txt, as the browser sees it.
new_tab(SITE + "/robots.txt")
wait_for_load()
print(f"robots.txt: title {js('document.title')!r}, text {' '.join((js('document.body.innerText') or '').split())[:80]!r}\n")

# The Data API page's own rules, on its "Using the API" tab (#api; the page is rendered by JavaScript).
goto_url(SITE + "/data/api/#api")
wait_for_load()
time.sleep(3)
text = " ".join((js("document.body.innerText") or "").split())
for q in ("Set a custom", "maximum 100 requests per minute", "Exceeding request limits",
          "Most endpoints return a maximum of 400", "Cross-origin resource sharing", "Undocumented query parameter",
          "Status code 204"):
    i = text.find(q)
    if i < 0:
        raise RuntimeError(f"Data API page changed, {q!r} not found: re-read {SITE}/data/api/ before relying on this skill")
    print(f"data/api: {text[i:text.find('.', i) + 1]}")

START_JS = """(() => { window.__awc = window.__awc || {}; const id = String(Math.random()).slice(2); window.__awc[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__awc[id] = {status: r.status, type: r.headers.get('content-type'), acao: r.headers.get('access-control-allow-origin'), text: await r.text()}; })
    .catch(e => { window.__awc[id] = {status: 0, type: '', acao: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__awc[%s]; if (v) delete window.__awc[%s]; return v; })()"""

def raw(url, timeout=60):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{url}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r["status"], r["type"], r["acao"], " ".join(r["text"].split())

# Same-origin probes from the aviationweather.gov tab. No retries: this block only inspects answers.
if js("location.origin") != SITE:
    raise RuntimeError(f"not on {SITE} (at {js('location.href')}): stop")
print()
for path in ("/api/data/metar?ids=ZZZZ&format=json",          # unknown station
             "/api/data/taf?ids=ZZZZ&format=json",            # same on the TAF route
             "/api/data/metar?ids=JFK&format=json",           # 3-letter FAA id instead of ICAO
             "/api/data/metar?ids=kjfk&format=json",          # lower case
             "/api/data/metar?ids=KJFK&format=json&foo=1",    # undocumented parameter
             "/api/data/metar?ids=KJFK&format=jsn",           # bad value
             "/api/data/metar?format=json",                   # no station
             "/api/data/metar?ids=KJFK&format=json&hours=3"): # history, newest first
    s, ct, acao, body = raw(SITE + path)
    if s == 200 and body.startswith("["):
        d = json.loads(body)
        body = f"{len(d)} item(s) {[x.get('reportTime', x.get('issueTime', ''))[:16] for x in d][:4]}"
    print(f"{path}: HTTP {s} {ct or '-'} ACAO={acao} {body[:110]}".rstrip())

# The same call from another site's page: no CORS header, so the browser blocks it.
goto_url("https://example.com/")
wait_for_load()
s, ct, acao, body = raw(SITE + "/api/data/metar?ids=KJFK&format=json")
print(f"\nfrom {js('location.origin')}: status {s} {body[:80]}")
```

Output (from the run on 2026-11-13, 23:35 UTC):

```text
robots.txt: title '🐴 404 Not Found', text '404 Not Found nginx'

data/api: Set a custom user agent to prevent automated filtering inadvertently blocking valid traffic.
data/api: maximum 100 requests per minute.
data/api: Exceeding request limits will result in access being blocked.
data/api: Most endpoints return a maximum of 400 entries (please consider using cache files for larger requests).
data/api: Cross-origin resource sharing is not permitted at this time.
data/api: Undocumented query parameter requests are restricted and will result in an error.
data/api: Status code 204 is returned for valid requests with no data available (except GeoJSON).

/api/data/metar?ids=ZZZZ&format=json: HTTP 204 - ACAO=None
/api/data/taf?ids=ZZZZ&format=json: HTTP 200 application/json; charset=utf-8 ACAO=None 0 item(s) []
/api/data/metar?ids=JFK&format=json: HTTP 204 - ACAO=None
/api/data/metar?ids=kjfk&format=json: HTTP 200 application/json; charset=utf-8 ACAO=None 1 item(s) ['2026-11-13T23:00']
/api/data/metar?ids=KJFK&format=json&foo=1: HTTP 400 application/json; charset=utf-8 ACAO=None {"status":"error","error":"Unexpected query parameter provided"}
/api/data/metar?ids=KJFK&format=jsn: HTTP 400 application/json; charset=utf-8 ACAO=None {"status":"error","error":"Invalid value for format"}
/api/data/metar?format=json: HTTP 400 application/json; charset=utf-8 ACAO=None {"status":"error","error":"Must specify station IDs or bounding box, zoom, and density"}
/api/data/metar?ids=KJFK&format=json&hours=3: HTTP 200 application/json; charset=utf-8 ACAO=None 4 item(s) ['2026-11-13T23:00', '2026-11-13T22:26', '2026-11-13T22:00', '2026-11-13T21:00']

from https://example.com: status 0 TypeError: Failed to fetch
```

### 3. Same answer with Python urllib (no browser)

Sends its own User-Agent, as the Data API page asks. (The User-Agent `Python-urllib/3.12` and an empty one also got HTTP 200 from curl in this run.)

```python
import json, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

STATIONS = ["KJFK", "KSFO"]
API = "https://aviationweather.gov/api/data"
UA = {"User-Agent": "metar-taf-example/1.0", "Accept": "application/json"}  # data/api: "Set a custom user agent"

def get(path):
    """GET -> parsed JSON; HTTP 204 (no data) -> []. Waits 60 s once on 429/5xx."""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + path, headers=UA), timeout=60) as r:
                body = r.read()
                time.sleep(1)  # max 100 requests per minute
                return [] if r.status == 204 else json.loads(body)  # an empty or cut 200 body fails loudly
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{path}: HTTP {e.code} {e.read().decode()[:160]}")  # 400 {"status":"error","error":"..."}
    sys.exit(f"{path}: still failing after one retry")

ids = ",".join(STATIONS)
metars = {m["icaoId"]: m for m in get(f"/metar?ids={ids}&format=json")}
tafs = {t["icaoId"]: t for t in get(f"/taf?ids={ids}&format=json")}
if set(STATIONS) - set(metars):
    sys.exit(f"no METAR for {sorted(set(STATIONS) - set(metars))}: stop")
now = datetime.now(timezone.utc)
for s in STATIONS:
    m = metars[s]
    age = (now - datetime.fromtimestamp(m["obsTime"], timezone.utc)).total_seconds() / 60
    print(f"{s} {m['fltCat'] or '?':<4} ({age:.0f} min old)  {m['rawOb']}")
    print(f"{'':10}TAF  {tafs[s]['rawTAF'] if s in tafs else '(none)'}")
below = [s for s in STATIONS if metars[s]["fltCat"] not in ("VFR", "", None)]  # '' = unknown, not "below VFR"
unknown = [s for s in STATIONS if not metars[s]["fltCat"]]
print(f"below VFR now: {', '.join(below) or 'none'}" + (f"; category unknown: {', '.join(unknown)}" if unknown else "")
      + ". Source: Aviation Weather Center (aviationweather.gov). Not for flight planning.")
```

Output (from the run on 2026-11-13, 23:35 UTC):

```text
KJFK MVFR (44 min old)  METAR KJFK 132251Z 36010KT 10SM -RA BKN019 OVC065 05/02 A2970 RMK AO2 RAB44 SLP057 P0000 T00500022 $
          TAF  TAF KJFK 132035Z 1321/1424 35014G20KT P6SM VCSH BKN020 BKN040 FM140000 34011KT P6SM SCT018 BKN040 TEMPO 1400/1404 BKN018 FM141400 31015G25KT P6SM BKN050
KSFO VFR  (39 min old)  METAR KSFO 132256Z 28016KT 10SM FEW017 FEW045 SCT100 SCT150 16/11 A2961 RMK AO2 SLP026 T01560106
          TAF  TAF KSFO 132102Z 1321/1424 33015KT 4SM RA BR BKN024 OVC029 FM140000 25015G20KT P6SM -SHRA OVC030 FM140400 25008KT P6SM VCSH OVC030 FM141000 20004KT P6SM SCT030 BKN050 FM142000 26006KT P6SM SCT030 BKN100
below VFR now: KJFK. Source: Aviation Weather Center (aviationweather.gov). Not for flight planning.
```

### 4. curl

```bash
B=https://aviationweather.gov/api/data
UA='metar-taf-example/1.0'
R='--max-time 60 --retry 1 --retry-delay 60'  # like blocks 1 and 3: one retry after 60 s on 429/5xx (curl also retries a timeout)
curl -sS --fail $R -A "$UA" "$B/metar?ids=KJFK,KSFO&format=json" | python3 -c '
import json, sys
for m in json.load(sys.stdin):
    print(m["icaoId"], m["fltCat"], m["rawOb"])
'
sleep 1
curl -sS --fail $R -A "$UA" "$B/taf?ids=KSFO" | sed 's/ *$//'; echo     # format omitted = raw text (lines end in spaces; stripped)
sleep 1
curl -sS --max-time 60 -o /dev/null -A "$UA" -w 'unknown station (ZZZZ): HTTP %{http_code}, %{size_download} bytes\n' "$B/metar?ids=ZZZZ&format=json"
```

Output (from the run on 2026-11-13, 23:35 UTC):

```text
KJFK MVFR METAR KJFK 132251Z 36010KT 10SM -RA BKN019 OVC065 05/02 A2970 RMK AO2 RAB44 SLP057 P0000 T00500022 $
KSFO VFR METAR KSFO 132256Z 28016KT 10SM FEW017 FEW045 SCT100 SCT150 16/11 A2961 RMK AO2 SLP026 T01560106
TAF KSFO 132102Z 1321/1424 33015KT 4SM RA BR BKN024 OVC029
  FM140000 25015G20KT P6SM -SHRA OVC030
  FM140400 25008KT P6SM VCSH OVC030
  FM141000 20004KT P6SM SCT030 BKN050
  FM142000 26006KT P6SM SCT030 BKN100

unknown station (ZZZZ): HTTP 204, 0 bytes
```

## Fields

Descriptions from the OpenAPI spec https://aviationweather.gov/data/schema/openapi.yaml (read once while writing this skill).

| Field | Where | Notes |
|---|---|---|
| `icaoId`, `name`, `lat`, `lon`, `elev` | METAR, TAF | `KJFK`, `New York/JF Kennedy Intl, NY, US` (the TAF `name` drops `, NY, US`) |
| `rawOb` | METAR | the report as issued; quote this, not your decoding |
| `fltCat` | METAR only | "Flight category restriction": `VFR`, `MVFR`, `IFR`, `LIFR`; `''` when unknown |
| `obsTime` | METAR | Unix seconds of the observation (22:51 UTC for KJFK) |
| `reportTime` | METAR | ISO time of the report slot (`2026-11-13T23:00:00.000Z` for the 22:51 observation); use `obsTime` for age |
| `metarType` | METAR | `METAR` or `SPECI` at airports (the spec's enum also lists `SYNOP`, `BUOY`, `CMAN`) |
| `visib` | METAR, TAF groups | statute miles; "10+ is greater than 10 sm" (METAR), "6+ is greater than 6 sm" (TAF); number or string; `''` in a TAF group that does not change it |
| `clouds[]` | METAR, TAF groups | `{cover, base}`; cover `CLR`, `CAVOK`, `FEW`, `SCT`, `BKN`, `OVC`, `OVX`; base in feet |
| `vertVis` | METAR, TAF groups | vertical visibility in feet (sky obscured); counts as the ceiling |
| `wxString` | METAR, TAF groups | `-RA`, `RA BR`, `VCSH` |
| `rawTAF`, `issueTime`, `validTimeFrom`, `validTimeTo` | TAF | raw forecast; issue time ISO; validity in Unix seconds (`1321/1424` = 13th 21:00 to 15th 00:00 UTC) |
| `fcsts[]` | TAF | decoded groups: `timeFrom`, `timeTo` (Unix seconds), `fcstChange` (`null` for the first group, `FM`, `TEMPO`, `BECMG`, `PROB`), `probability`, `wdir`, `wspd`, `wgst`, `visib`, `clouds`, `vertVis`, `wxString` |
| `remarks`, `mostRecent` | TAF | `" AMD"` = amended TAF (AC 00-45H 5.13.2.1; both TAFs at 23:30 UTC, while the routine KSFO TAF issued 23:35 had `''`); `mostRecent` 1 |

## Gotchas

- **The TAF can disagree with the METAR.** At 23:34 UTC KSFO observed VFR while its TAF group for 21:00-00:00 said MVFR (4 miles, rain and mist). "Right now" is the observation; the TAF is the forecast.
- **TEMPO, PROB and BECMG groups only list what changes.** The KJFK `TEMPO 1400/1404 BKN018` group has `visib: ""` and one cloud layer; block 1 takes the missing visibility from the prevailing group before computing its category. BECMG groups came back with the unchanged values already filled in (LIRF, LOWW and EGLL on 2026-11-14: `BECMG 1400/1402 03010KT` decoded with LIRF's `SCT030` and `6+`), and the API's `timeTo` for a BECMG group runs to the next change, not the end of the transition; block 1 still merges each BECMG group over the prevailing conditions in case a field is missing.
- **A new TAF can arrive before it is valid.** "A routine forecast, TAF, is issued 20 to 40 minutes before the beginning of its valid period" (AC 00-45H 5.13.2.3). At 23:37 UTC `/taf` already returned only the KSFO TAF issued 23:35 and valid from 14th 00:00 UTC, so block 1 marked no group `<- now`. Answer "right now" from the METAR.
- **`$` at the end of `rawOb`.** KJFK's METAR ended with `$`: "A maintenance indicator ($) is coded when an automated system detects that maintenance is needed on the system" (FAA AC 00-45H Change 2, 3.1.5.14.1, https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_00-45H_Chg_2.pdf). The report and its `fltCat` were still served.
- **Report age.** "most METARs update once per hour" (Data API page); at 23:34 UTC the latest were 22:51 (KJFK) and 22:56 (KSFO). Print the age with every answer. `hours=3` returns history newest first (4 KJFK reports: 23:00, 22:26, 22:00, 21:00 report slots).
- **First call can be slow.** The first curl call of the session took 20 s and returned HTTP 504 `Microsoft-Azure-Application-Gateway/v2`; the next call 3 s later was HTTP 200 in 0.2 s. Use a 60 s timeout and one retry.
- **Errors are JSON, not empty.** HTTP 400 bodies: `{"status":"error","error":"Unexpected query parameter provided"}` (any undocumented parameter, e.g. `&foo=1`), `"Invalid value for format"`, `"Must specify station IDs or bounding box, zoom, and density"`.
- **`format` defaults to raw text.** Without `format=json`, `/metar` returns plain METAR lines and `/taf` the raw TAF with `FM` groups on new lines (block 4).
- **No CORS.** Responses carry no `Access-Control-Allow-Origin`; a `fetch()` from example.com failed with `TypeError: Failed to fetch`. Run browser fetches from an aviationweather.gov page. `www.aviationweather.gov` answers HTTP 308 to `aviationweather.gov`; the Data API page says not to use the www subdomain.
- **Caching.** `cache-control: max-age=60`; repeated calls within a minute can return the same data.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **3-letter FAA ids** (`JFK`, `SFO`): HTTP 204, no data. Use ICAO (`KJFK`, `KSFO`).
- **Cross-origin `fetch()`** from another site's page: blocked (no CORS). Same-origin from aviationweather.gov works.
- **Undocumented query parameters:** HTTP 400 (see Gotchas).
- **Not tested:** bounding-box queries (`bbox`), the cache files themselves, XML/IWXXM/GeoJSON formats, `date` and `taf=true` on `/metar`, PIREP/SIGMET/G-AIRMET routes, stations outside the US, rate-limit behaviour (never provoked).
