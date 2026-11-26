# Macrostrat - Find the Geologic Map Unit Under a Latitude/Longitude: Unit Name, Age in Ma and International Period, Rock Description and the Source Map to Cite (REST JSON, no key)

Field-tested against the Macrostrat API v2 (macrostrat.org/api/v2) and the macrostrat.org about, brand and documentation pages on 2026-11-25 (US Pacific afternoon; 00:29-00:40 UTC on 26 November) using fresh Browser Use cloud browsers (logged out; one session 00:34:49-00:36:20 UTC for block 1's first two runs and block 2's first run, a new one 00:39:09-00:39:50 UTC for block 1's third run and block 2's second run; both stopped and confirmed `stopped` afterwards) plus Python `urllib` and `curl` from a Linux machine. 17 browser page loads (1 in each of block 1's three runs, 7 in each of block 2's two runs) and 48 in-page `fetch()` calls (8 in each of block 1's three runs, 12 in each of block 2's two runs), 28 urllib calls (block 3's seven commands ran twice, 14 calls each; the last command is refused before any call) and 94 curl calls (74 while exploring, 10 in each of block 4's two runs), all serial and at least 1 s apart. Every call was HTTP 200 except robots.txt and the other missing pages (HTTP 404) and the deliberate probes: HTTP 400 (no `z`), HTTP 404 (a longitude of exactly 0, see Gotchas) and HTTP 500 (a word for `lat`, an unknown `scale`). curl timed the API at 0.18-0.33 s for point queries at every zoom except z=0 (0.66 s) and z=2 (2.58 s), and 0.46 s for the `/changes` list (608 KB gzipped, 1.4 MB unzipped); the browser blocks poll every 0.2 s, so their times (0.06-0.32 s) are upper bounds. No 429, no challenge, no key, no login, no cookie. Each block ran at least twice; the outputs shown come from the last run of each block, and the earlier runs differed only in the timings and in output format fixed between runs (citations: `Machette. (2003)` became `Machette (2003)`; block 1's Quaternary note moved each source to its own line). An independent verifier re-ran all four blocks unchanged on 2026-11-26 00:42-00:44 UTC in a new cloud browser (stopped and confirmed `stopped` afterwards) and got the same units, ages, sources, quotes and statuses; only timings and clock minutes differed. Later on 2026-11-26 block 4 got a `trap ... EXIT` that removes its temporary directory even when the script stops early; that version re-ran from the same Linux machine at 01:01-01:04 UTC with the same output apart from the clock and timings. After review on 2026-11-26, blocks 1 and 3 wait for `Retry-After` (seconds or an HTTP date, at most 120 s) before their one retry, and block 3 accepts `--z` 0-24 (curl at 01:13 UTC on Madison: z=17, 22, 23 and 24 HTTP 200, z=25, 26, 28, 29, 30 and 100 HTTP 404). Block 1 re-ran in a new cloud browser (01:23:33-01:23:48 UTC, stopped and confirmed `stopped`) and block 3's seven commands at 01:15-01:16 UTC, with the same output apart from the clock and timings; `--z 24` gave the same Wonewoc Formation unit and `--z 25` is refused before any call.

robots.txt (checked 2026-11-26 00:29-00:40 UTC with curl, the cloud browser and blocks 3 and 4): https://macrostrat.org/robots.txt answers HTTP 404 with the site's HTML "Page Not Found" page, and the API lives on the same host (`/api/v2`), so there are no rules for `*` or for any named agent (GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot, Bytespider); RFC 9309 (section 2.3.1.3) says a 4xx robots.txt means "the crawler MAY access any resources on the server". Every path this skill uses (`/api/v2/mobile/map_query`, `/geologic_units/map`, `/defs/intervals`, `/meta`, `/about`, `/about/brand`, `/docs/data-services`) is allowed. Blocks 3 and 4 read robots.txt before any API call and stop if it ever returns rules that disallow a path. Terms: there is no terms page; https://macrostrat.org/terms, `/privacy` and `/sitemap.xml` are the same HTTP 404 page (block 2). The licence statements: https://macrostrat.org/about says, under its "Services" heading, "Free and public, described in the documentation." and "Data are licensed CC BY 4.0: attribute Macrostrat and the original data sources", and "Macrostrat is a shared community resource that must be credited in scientific products. Acknowledge Macrostrat as the source of any information or data." and "If specific data sets were targeted, you should also include citations to the original references."; https://macrostrat.org/docs/data-services says "Macrostrat's data are available through public web services, free to use under a CC-BY 4.0 license" and "Every response states its license, and records carry references to their original sources."; the API root answers `"license": "CC-BY 4.0. More info at /meta"` and `/meta` answers "All data are licensed under Creative Commons BY 4.0 International". CC BY 4.0 allows commercial use and asks for credit. No AI/ML, scraping, crawling, robot, automated-access, rate-limit or "commercial" wording on the about, brand or data-services pages (block 2 scans for the words). Naming: the brand page https://macrostrat.org/about/brand says "\"Macrostrat\", one word, capital M." and "When you mean the organization, \"the Macrostrat lab at the University of Wisconsin–Madison\"". It offers logos for acknowledgements ("Use these assets when you acknowledge Macrostrat in a talk, poster, paper or app", "Please do not alter the marks or recolor them"); this skill uses no logo and is not affiliated with or endorsed by Macrostrat or the University of Wisconsin-Madison. Blocks 1 and 3 print a credit line with the Macrostrat paper and the unit's own map source; block 4 prints the map source and a short Macrostrat CC BY 4.0 credit; block 2 shows no map data and prints the API's own `/meta` citation.

**What the answer is.** The unit is what the geologic map Macrostrat shows at that spot and zoom says is at the surface. Where the map is a bedrock map (Madison, Grand Canyon, London), that is the bedrock. Where it is a surface-geology map, it can be river, glacial or coastal sediment (Denver, New Orleans, Amsterdam, Tokyo, Death Valley all gave Holocene or Pleistocene units at z=12). The blocks flag any unit no older than 2.58 Ma (the base of the Quaternary) and list the older units other maps place at the point; none of that is a borehole, and the map is only as exact as its scale.

## Quick summary

- **No scraping needed.** One GET gives the answer: `https://macrostrat.org/api/v2/mobile/map_query?lat=43.0731&lng=-89.4012&z=12` -> `success.data` with `elevation`, `burwell[0]` (the map unit: `name`, `strat_name`, `descrip`, `lith`, `t_int_name`/`b_int_name` and `t_int_age`/`b_int_age` in Ma, `scale`, `source_id`, `map_id`, and `ref` with `authors`, `ref_year`, `ref_title`, `ref_source`, `isbn_doi`, `url`), `macrostrat` (the matched stratigraphic column units: narrower `t_age`/`b_age` and lithology proportions) and `lines` (a fault or contact there). `z` is required. For the period, map the age range onto `GET /defs/intervals?timescale=international%20periods` (22 periods, Siderian to Quaternary); `GET /defs/intervals?int_id=258,122` says whether a name is an era, period, epoch or age. Every map at the point, all scales: `GET /geologic_units/map?lat=&lng=` with a `refs` list keyed by `source_id`. `Access-Control-Allow-Origin: *`, so `fetch()` works from any https page.
- **Answers (26 November 2026, 00:39 UTC):** **Madison, Wisconsin** (43.0731, -89.4012): **Wonewoc Formation (Cw)**, Cambrian, **486.85-538.8 Ma** on the map (matched column units narrow it to 496.8-497.85 Ma, Dresbachian), "Quartz sandstone, medium grained, brownish yellow to white ...", from Brown, Peters and Massie-Ferch (2013), *Preliminary Bedrock Geology of Dane County, Wisconsin*. **Grand Canyon** (36.1069, -112.1129): **Hakatai Shale**, Mesoproterozoic (an era), **1000-1600 Ma**, periods Calymmian to Stenian, from Billingsley (2000), USGS Geologic Investigations Series I-2688. **Denver** (39.7392, -104.9903): **Broadway Alluvium**, Late Pleistocene, 0.0117-0.129 Ma: a surface deposit; the small-scale Geologic Map of North America database says Paleogene sedimentary rock there.
- **Rate limits:** none published (the about, brand and data-services pages, the API root and `/meta` have no number). Responses carry no rate-limit or `retry-after` headers; the cache headers are `etag`, `age`, `x-varnish`, `via: 1.1 production-api-gateway-... (Varnish/7.7)` and `x-cache: hit` or `miss`. The data-services page says "the data APIs were serving millions of requests each month" (as of 2023). The blocks run serially at 1 call a second; one point costs 1-3 calls.

## What works

### 1. The map unit, its age, period, rock and source map for a few points (browser)

`on_macrostrat_tab()` opens the logged-out about page; the API is on the same host and also answers `Access-Control-Allow-Origin: *`, so `fetch()` from it works. Per run: 1 call for the period list, then per point 1 `/mobile/map_query` and 1 `/defs/intervals` call, plus 1 `/geologic_units/map` call when the unit is Quaternary (8 calls here, about 13 s). Edit `POINTS` and `Z`.

```python
import email.utils, json, time
from datetime import datetime, timezone

POINTS = [                                    # (label, latitude, longitude), WGS84 decimal degrees
    ("Madison, Wisconsin", 43.0731, -89.4012),
    ("Grand Canyon, Arizona", 36.1069, -112.1129),
    ("Denver, Colorado", 39.7392, -104.9903),
]
Z = 12               # map zoom 0-24: 0-2 = tiny, 3-5 = small, 6-8 = medium, 9+ = large (most detailed map there)
API = "https://macrostrat.org/api/v2"
PAGE = "https://macrostrat.org/about"
PAUSE = 1.0          # serial, 1 call a second (no rate limit is published)
QUATERNARY_BASE = 2.58                         # Ma; a unit no older than this is a surface deposit
SCALES = ("large", "medium", "small", "tiny")  # most detailed first

def on_macrostrat_tab():
    """fetch() from the logged-out Macrostrat about page: same origin as the API, which also sends CORS *."""
    try:
        if js("location.href").startswith(PAGE):
            return
    except Exception:
        pass
    new_tab(PAGE)
    wait_for_load()
    if not js("location.href").startswith(PAGE):
        raise RuntimeError(f"Macrostrat about page did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it
START_JS = """(() => { window.__m = window.__m || {}; const id = String(Math.random()).slice(2); window.__m[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__m[id] = {status: r.status, retry: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__m[id] = {status: 0, retry: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__m[%s]; if (v) delete window.__m[%s]; return v; })()"""

calls = []
def retry_wait(value, default=10):
    """Retry-After as delay-seconds or an HTTP date -> seconds to wait; missing or unreadable -> default."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def call(path):
    """GET -> the 'success' object. 429, 500, 502, 503, 504 or a network error: one retry after Retry-After (seconds or an
    HTTP date; the page is same-origin, so it can read it), else 10 s; over 120 s stops. Anything else not 200 stops.
    A 404 HTML 'Cannot GET' page means a parameter was rejected (see Gotchas: longitude exactly 0)."""
    url = API + path
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer after 60s")
            time.sleep(0.2)
        calls.append((path.split("?")[0], r["status"], round(time.time() - t0, 2)))
        time.sleep(PAUSE)
        if attempt == 0 and r["status"] in (0, 429, 500, 502, 503, 504):
            wait = retry_wait(r.get("retry"))
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] != 200:
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
    d = json.loads(r["text"])
    if "success" not in d:
        raise RuntimeError(f"{url}: no 'success' in the answer: {r['text'][:160]!r}")
    return d["success"]

def periods_for(t, b, periods):
    """International periods that overlap t-b Ma, oldest first; [] for rock older than 2500 Ma."""
    hit = [p for p in periods if p["t_age"] < b and p["b_age"] > t]
    return sorted(hit, key=lambda p: -p["b_age"])

def period_text(t, b, periods):
    hit = periods_for(t, b, periods)
    if not hit:
        return "older than the oldest international period (Siderian, from 2500 Ma)"
    if len(hit) == 1:
        return hit[0]["name"]
    return f"{hit[0]['name']} to {hit[-1]['name']} ({len(hit)} periods)"

def cite(ref):
    """'Authors (year). Title. Series. DOI. URL' from the unit's ref; parts the source leaves empty are skipped."""
    a, y = ref.get("authors", "").strip().rstrip(","), ref.get("ref_year", "").strip()
    head = f"{a} ({y})" if a and y else a
    parts = [head] + [ref.get(k, "").strip().rstrip(".") for k in ("ref_title", "ref_source", "isbn_doi")]
    text = ". ".join(p.rstrip(".") if i else p for i, p in enumerate(parts) if p)
    return (text + "." if text else "") + (" " + ref["url"].strip() if ref.get("url", "").strip() else "")

on_macrostrat_tab()
print(f"Macrostrat API v2, checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
periods = call("/defs/intervals?timescale=international%20periods")["data"]
print(f"{len(periods)} international periods loaded ({periods[-1]['name']} {periods[-1]['b_age']} Ma to "
      f"{periods[0]['name']} {periods[0]['t_age']} Ma)")

for label, lat, lng in POINTS:
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError(f"{label}: {lat}, {lng} is not a latitude/longitude")
    if lng == 0:
        lng = 0.0001                      # the API answers 404 to a longitude of exactly 0
    d = call(f"/mobile/map_query?lat={lat}&lng={lng}&z={Z}")["data"]
    units = [u for u in d["burwell"] if u]          # [{}] = no map unit here (ocean, gap in coverage)
    print(f"\n{label}: {lat:.5f}, {lng:.5f} (z={Z}), elevation {d['elevation']} m")
    if not units:
        print("  no geologic map unit at this point and zoom")
        continue
    u = units[0]
    ints = {i["int_id"]: i for i in call(f"/defs/intervals?int_id={u['t_int_id']},{u['b_int_id']}")["data"]}
    t, b = u["t_int_age"], u["b_int_age"]
    span = (u["b_int_name"] if u["b_int_name"] == u["t_int_name"]
            else f"{u['b_int_name']} to {u['t_int_name']}")
    kinds = "/".join(sorted({ints[i]["int_type"] for i in (u["t_int_id"], u["b_int_id"]) if i in ints}))
    print(f"  Unit:   {u['name'].strip()}" + (f" (stratigraphic name: {u['strat_name']})"
                                       if u["strat_name"] and u["strat_name"] not in u["name"] else ""))
    print(f"  Age:    {span} ({kinds}), {t:g}-{b:g} Ma; period: {period_text(t, b, periods)}")
    m = d.get("macrostrat") or {}
    if m.get("b_age") is not None:
        print(f"          matched Macrostrat column units: {m['rank_names']}, {m['t_age']:g}-{m['b_age']:g} Ma "
              f"({m['b_int_name'] if m['b_int_name'] == m['t_int_name'] else m['b_int_name'] + ' to ' + m['t_int_name']})")
    desc = " ".join((u["descrip"] or "").split())
    print(f"  Rock:   {(desc[:260] + ' ...') if len(desc) > 260 else desc or '(no description on the map)'}")
    liths = sorted(m.get("lith") or [], key=lambda x: -x["prop"])
    if liths:
        print("  Liths:  " + ", ".join(f"{x['name']} {x['prop']:.0%}" for x in liths) + " (matched column units)")
    elif u["lith"]:
        print(f"  Liths:  {u['lith']} (map legend)")
    print(f"  Map:    {cite(u['ref'])} [{u['scale']} scale; Macrostrat source {u['source_id']}, map unit {u['map_id']}]")
    if b <= QUATERNARY_BASE:
        print(f"  Note:   this unit is Quaternary ({b:g} Ma or younger): a surface deposit, not bedrock. "
              f"Older units other maps place at this point:")
        g = call(f"/geologic_units/map?lat={lat}&lng={lng}")
        older = sorted((x for x in g["data"] if x["b_int_age"] and x["b_int_age"] > QUATERNARY_BASE),
                       key=lambda x: SCALES.index(x["scale"]))
        for x in older[:4]:
            src = g["refs"][str(x["source_id"])].strip()
            buried = "basement" in src.lower() or "precambrian surface" in src.lower()
            print(f"    {x['scale']:<6} {x['name'].strip()[:50]:<50} {x['t_int_age']:g}-{x['b_int_age']:g} Ma, "
                  f"{period_text(x['t_int_age'], x['b_int_age'], periods)}"
                  + (" [basement map: rock buried under the cover]" if buried else "") + f"\n           source: {src[:110]}")
        if not older:
            print("    none")

by = {}
for p, s, t in calls:
    by.setdefault(p, []).append((s, t))
print(f"\n{len(calls)} API calls: " + ", ".join(f"{p} x{len(v)} HTTP {sorted({s for s, _ in v})} "
      f"{min(t for _, t in v):.2f}-{max(t for _, t in v):.2f}s" for p, v in by.items()))
print("Data: Macrostrat (macrostrat.org, the Macrostrat lab at the University of Wisconsin-Madison), CC BY 4.0, "
      "and the map sources cited above. Cite Peters, S.E., Husson, J.M., and Czaplewski, J., 2018, Macrostrat: "
      "A Platform for Geological Data Integration and Deep-Time Earth Crust Research: Geochemistry, "
      "Geophysics, Geosystems, v. 19, p. 1393-1409, doi:10.1029/2018gc007467. Changed: periods matched to the map ages by this script; descriptions shortened.")
```

Output (third run, 2026-11-26 00:39 UTC, in a new cloud browser; the 00:35 and 00:36 UTC runs found the same units, ages and sources):

```text
Macrostrat API v2, checked 2026-11-26 00:39 UTC
22 international periods loaded (Siderian 2500 Ma to Quaternary 0 Ma)

Madison, Wisconsin: 43.07310, -89.40120 (z=12), elevation 270 m
  Unit:   Wonewoc Formation (Cw)
  Age:    Cambrian (period), 486.85-538.8 Ma; period: Cambrian
          matched Macrostrat column units: Wonewoc Formation, 496.8-497.85 Ma (Dresbachian)
  Rock:   Quartz sandstone, medium grained, brownish yellow to white, with medium- to large-scale cross bedding commonly seen in outcrop. Reaches a maximum thickness of 165 feet (50 m) in the subsurface. Part of Elk Mound Group.
  Liths:  quartz arenite 81%, siltstone 12%, shale 6% (matched column units)
  Map:    Brown, B.A., Peters, R.M., Massie-Ferch, K. (2013). Preliminary Bedrock Geology of Dane County, Wisconsin. Open-File Report. https://wgnhs.uwex.edu/pubs/wofr201301di/ [large scale; Macrostrat source 6, map unit 934954]

Grand Canyon, Arizona: 36.10690, -112.11290 (z=12), elevation 1027 m
  Unit:   Hakatai Shale
  Age:    Mesoproterozoic (era), 1000-1600 Ma; period: Calymmian to Stenian (3 periods)
  Rock:   Orange-red, purple, and red mudstone, shale, and sandstone. Forms an upper cliff unit, a middle slope unit, and a lower slope unit. Upper cliff unit consists of pale-purple or lavender, fine- to coarse-grained, thin- to medium-bedded, cross-bedded sandstone. F ...
  Map:    Billingsley, G.H. (2000). Geologic Map of the Grand Canyon 30' x 60' Quadrangle, Coconino and Mohave Counties, Northwestern Arizona. USGS Geologic Investigations Series I-2688. http://pubs.usgs.gov/imap/i-2688/ [large scale; Macrostrat source 34, map unit 2204858]

Denver, Colorado: 39.73920, -104.99030 (z=12), elevation 1601 m
  Unit:   Broadway Alluvium
  Age:    Late Pleistocene (age), 0.0117-0.129 Ma; period: Quaternary
          matched Macrostrat column units: Broadway Alluvium, 0.0117-0.3327 Ma (Pleistocene to Late Pleistocene)
  Rock:   Gravel, sand, silt, and clay forming alluvial terrace deposits commonly 7.6 to 12.2 m above present stream level. Includes pre-Piney Creek alluvium of Scott (1962, 1963a). Deposits of major streams west of South Platte River are more coarse-grained near the mo ...
  Liths:  gravel 42%, sand 42%, silt 8%, clay 8% (matched column units)
  Map:    Trimble, D.E., M.N. Machette (2003). Geologic Map of the Greater Denver Area, Front Range Urban Corridor, Colorado. U.S. Geological Survey Geologic Investigations Series I-856-H. http://pubs.usgs.gov/imap/i-856-h/ [large scale; Macrostrat source 64, map unit 2444199]
  Note:   this unit is Quaternary (0.129 Ma or younger): a surface deposit, not bedrock. Older units other maps place at this point:
    medium Biotite gneiss and migmatite                       1600-2500 Ma, Siderian to Statherian (4 periods) [basement map: rock buried under the cover]
           source: Sims, P.K., Bankey, V., Finn, C.A., 2001, Preliminary Precambrian basement map of Colorado-a geologic interpre
    small  Paleogene sedimentary                              23.04-66 Ma, Paleogene
           source: Garrity, C.P., and Soller, D.R.,. Database of the Geologic Map of North America: adapted from the map by J.C.
    tiny   Mesozoic sedimentary rocks                         201.4-251.902 Ma, Triassic
           source: Chorlton, L.B. Generalized geology of the world: bedrock domains and major faults in GIS format: a small-scale

8 API calls: /defs/intervals x4 HTTP [200] 0.06-0.06s, /mobile/map_query x3 HTTP [200] 0.32-0.32s, /geologic_units/map x1 HTTP [200] 0.32-0.32s
Data: Macrostrat (macrostrat.org, the Macrostrat lab at the University of Wisconsin-Madison), CC BY 4.0, and the map sources cited above. Cite Peters, S.E., Husson, J.M., and Czaplewski, J., 2018, Macrostrat: A Platform for Geological Data Integration and Deep-Time Earth Crust Research: Geochemistry, Geophysics, Geosystems, v. 19, p. 1393-1409, doi:10.1029/2018gc007467. Changed: periods matched to the map ages by this script; descriptions shortened.
```

### 2. robots.txt, the licence, citation and naming quotes, and what the API does with odd input (browser)

7 page loads and 12 in-page `fetch()` calls in the same tab. Pages are loaded as a reader sees them; the site is a JavaScript app, so the block waits for the text. The probes run from the last page (same origin as the API).

```python
import json, time

API = "https://macrostrat.org/api/v2"
ABOUT = "https://macrostrat.org/about"

START_JS = """(() => { window.__m = window.__m || {}; const id = String(Math.random()).slice(2); window.__m[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__m[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__m[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__m[%s]; if (v) delete window.__m[%s]; return v; })()"""

def raw(url):
    """One in-page GET -> {status, type, text}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    r["secs"] = round(time.time() - t0, 2)
    time.sleep(1.0)
    return r

def page(url, wait_for=None):
    """Load a page -> (HTTP status, content type, flattened text); waits up to 20 s for a phrase
    (the site is a JavaScript app, so the text can arrive after the load event). One retry on a timeout."""
    for attempt in range(2):
        try:
            goto_url(url)
            wait_for_load()
            break
        except Exception as e:
            if attempt:
                raise
            print(f"  (navigation to {url} failed once: {e}; retrying)")
            time.sleep(3)
    t0 = time.time()
    while True:
        txt = " ".join((js("(document.body || document.documentElement).innerText || ''") or "").split())
        if not wait_for or wait_for in txt or time.time() - t0 > 20:
            break
        time.sleep(0.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    time.sleep(1.0)
    return st, js("document.contentType"), txt

# 1) robots.txt and the pages a terms check looks for: all are the site's "Page Not Found" app page
for p in ("/robots.txt", "/terms", "/privacy", "/sitemap.xml"):
    st, ct, txt = page("https://macrostrat.org" + p, wait_for="Not Found")
    rules = st == 200 and ct.startswith("text/plain")
    print(f"macrostrat.org{p}: HTTP {st} {ct}; {'RULES/PAGE PRESENT, read it' if st == 200 else 'none'}; "
          f"text: {txt[:60]!r}")

# 2) the licence, citation and naming statements, as a reader sees them
for url, needles in (
    (ABOUT, ["Services Free and public",
             "Data are licensed CC BY 4.0",
             "attribute Macrostrat and the original data sources",
             "Macrostrat is a shared community resource that must be credited in scientific products.",
             "Acknowledge Macrostrat as the source of any information or data.",
             "If specific data sets were targeted, you should also include citations to the original references.",
             "doi:10.1029/2018gc007467",
             "Its development is centered at the Macrostrat lab at the University of Wisconsin"]),
    ("https://macrostrat.org/about/brand",
            ["\"Macrostrat\", one word, capital M.",
             "When you mean the organization, \"the Macrostrat lab at the University of Wisconsin",
             "Use these assets when you acknowledge Macrostrat in a talk, poster, paper or app.",
             "Please do not alter the marks or recolor them."]),
    ("https://macrostrat.org/docs/data-services",
            ["Macrostrat's data are available through public web services, free to use under a CC-BY 4.0 license",
             "Every response states its license, and records carry references to their original sources.",
             "Each route describes its own parameters when called without arguments.",
             "API version 2 is unchanged and remains the stable way to read data"]),
):
    st, ct, txt = page(url, wait_for=needles[0][:30])
    print(f"\n{url.split('//')[1]} HTTP {st}")
    for n in needles:
        print(f"  {'found' if n in txt else 'MISSING'}: {n[:100]!r}")
    low = txt.lower()
    for w in ("terms", "scrap", "crawl", "robot", "artificial intelligence", "machine learning", "automat",
              "rate limit", "requests per", "commercial"):
        hits = [low[max(0, i - 30):i + 30] for i in range(len(low)) if low.startswith(w, i)]
        print(f"  word {w!r}: {len(hits)}" + (f" -> {hits[0]!r}" if hits else ""))

# 3) what the API itself says about licence and citation
for path in ("", "/meta"):
    r = raw(API + path)
    s = json.loads(r["text"])["success"]
    print(f"\n/api/v2{path} HTTP {r['status']}: license {s.get('license')!r}"
          + (f"; data.license {s['data']['license']!r}; citation {s['data']['citation']!r}; version {s['data']['version']}"
             if path else f"; {len(s['routes'])} route families"))

# 4) what the API does with odd input (fetch from the about page: same origin)
print()
for label, path in (
    ("Madison, z=12                     ", "/mobile/map_query?lat=43.0731&lng=-89.4012&z=12"),
    ("Madison, no z                     ", "/mobile/map_query?lat=43.0731&lng=-89.4012"),
    ("Madison, z=2                      ", "/mobile/map_query?lat=43.0731&lng=-89.4012&z=2"),
    ("open Atlantic                     ", "/mobile/map_query?lat=30&lng=-40&z=10"),
    ("Greenwich, lng=0                  ", "/mobile/map_query?lat=51.4779&lng=0&z=12"),
    ("Greenwich, lng=0.0001             ", "/mobile/map_query?lat=51.4779&lng=0.0001&z=12"),
    ("geologic_units/map, lng=0         ", "/geologic_units/map?lat=51.4779&lng=0"),
    ("lat=95 (not a latitude)           ", "/mobile/map_query?lat=95&lng=10&z=10"),
    ("lat=abc                           ", "/mobile/map_query?lat=abc&lng=-89&z=10"),
    ("geologic_units/map, scale=huge    ", "/geologic_units/map?lat=43.0731&lng=-89.4012&scale=huge"),
):
    r = raw(API + path)
    body = " ".join(r["text"].split())
    if r["status"] == 200 and "burwell" in body:
        d = json.loads(r["text"])["success"]["data"]
        u = [x for x in d["burwell"] if x]
        body = (f"elevation {d['elevation']}, " + (f"{u[0]['name']!r} ({u[0]['scale']}, {u[0]['t_int_name']})"
                                                     if u else "burwell [{}] (no unit)"))
    print(f"{label} HTTP {r['status']} {r['secs']:.2f}s {(r['type'] or '').split(';')[0]}: {body[:110]}")
```

Output (second run, 2026-11-26 00:39 UTC; the first run at 00:35 UTC gave the same statuses and quotes):

```text
macrostrat.org/robots.txt: HTTP 404 text/html; none; text: 'Not found Page Not Found The page you are looking for does n'
macrostrat.org/terms: HTTP 404 text/html; none; text: 'Not found Page Not Found The page you are looking for does n'
macrostrat.org/privacy: HTTP 404 text/html; none; text: 'Not found Page Not Found The page you are looking for does n'
macrostrat.org/sitemap.xml: HTTP 404 text/html; none; text: 'Not found Page Not Found The page you are looking for does n'

macrostrat.org/about HTTP 200
  found: 'Services Free and public'
  found: 'Data are licensed CC BY 4.0'
  found: 'attribute Macrostrat and the original data sources'
  found: 'Macrostrat is a shared community resource that must be credited in scientific products.'
  found: 'Acknowledge Macrostrat as the source of any information or data.'
  found: 'If specific data sets were targeted, you should also include citations to the original references.'
  found: 'doi:10.1029/2018gc007467'
  found: 'Its development is centered at the Macrostrat lab at the University of Wisconsin'
  word 'terms': 0
  word 'scrap': 0
  word 'crawl': 0
  word 'robot': 0
  word 'artificial intelligence': 0
  word 'machine learning': 0
  word 'automat': 0
  word 'rate limit': 0
  word 'requests per': 0
  word 'commercial': 0

macrostrat.org/about/brand HTTP 200
  found: '"Macrostrat", one word, capital M.'
  found: 'When you mean the organization, "the Macrostrat lab at the University of Wisconsin'
  found: 'Use these assets when you acknowledge Macrostrat in a talk, poster, paper or app.'
  found: 'Please do not alter the marks or recolor them.'
  word 'terms': 0
  word 'scrap': 0
  word 'crawl': 0
  word 'robot': 0
  word 'artificial intelligence': 0
  word 'machine learning': 0
  word 'automat': 0
  word 'rate limit': 0
  word 'requests per': 0
  word 'commercial': 0

macrostrat.org/docs/data-services HTTP 200
  found: "Macrostrat's data are available through public web services, free to use under a CC-BY 4.0 license"
  found: 'Every response states its license, and records carry references to their original sources.'
  found: 'Each route describes its own parameters when called without arguments.'
  found: 'API version 2 is unchanged and remains the stable way to read data'
  word 'terms': 0
  word 'scrap': 0
  word 'crawl': 0
  word 'robot': 0
  word 'artificial intelligence': 0
  word 'machine learning': 0
  word 'automat': 0
  word 'rate limit': 0
  word 'requests per': 0
  word 'commercial': 0

/api/v2 HTTP 200: license 'CC-BY 4.0. More info at /meta'; 16 route families

/api/v2/meta HTTP 200: license 'CC-BY 4.0'; data.license 'All data are licensed under Creative Commons BY 4.0 International'; citation 'Peters, S.E. et al. Macrostrat: a platform for geological data integration and deep-time research. https://macrostrat.org, accessed on (date)'; version 2.6.0

Madison, z=12                      HTTP 200 0.32s application/json: elevation 270, 'Wonewoc Formation (Cw)' (large, Cambrian)
Madison, no z                      HTTP 400 0.06s application/json: { "error": { "v": 2, "license": "CC-BY 4.0", "message": "You are missing a required parameter", "about": { "v"
Madison, z=2                       HTTP 200 0.32s application/json: elevation 270, 'Paleozoic sedimentary rocks' (tiny, Paleozoic)
open Atlantic                      HTTP 200 0.32s application/json: elevation -3422, burwell [{}] (no unit)
Greenwich, lng=0                   HTTP 404 0.06s text/html: <!DOCTYPE html> <html lang="en"> <head> <meta charset="utf-8"> <title>Error</title> </head> <body> <pre>Cannot
Greenwich, lng=0.0001              HTTP 200 0.32s application/json: elevation 47, 'Lambeth Group' (medium, Paleocene)
geologic_units/map, lng=0          HTTP 200 0.32s application/json: {"success":{"v":2,"license":"CC-BY 4.0","data":[{"map_id":2030042,"source_id":23,"name":"Lambeth Group","strat
lat=95 (not a latitude)            HTTP 200 0.32s application/json: elevation None, burwell [{}] (no unit)
lat=abc                            HTTP 500 0.06s application/json: { "error": { "message": { "length": 161, "name": "error", "severity": "ERROR", "code": "22P02", "where": "unna
geologic_units/map, scale=huge     HTTP 500 0.06s application/json: { "error": { "message": "Invalid scale parameter passed." } }
```

### 3. The same with Python urllib, as a command-line tool: robots check, cached periods, one point (no browser)

Standard library only. It runs with `python3 -I`. Save it as `macrostrat.py`. It reads robots.txt, then the period list once a month (stored in `~/.cache/macrostrat/`, or in `$MACROSTRAT_CACHE`), then 1 `/mobile/map_query` call, plus 1 `/geologic_units/map` call for a Quaternary unit. A longitude of exactly 0 is sent as 0.0001 (the API answers 404 to 0; 0.0001 degrees is about 7 m at London's latitude). `--json` prints one object for other programs. Exit code 2 = no map unit at the point, or bad input. On a 429 or 5xx it retries once after 10 s.

```python
"""The geologic map unit at a latitude/longitude from Macrostrat (macrostrat.org API v2, Python standard library only):
name, age in Ma, international period(s), rock description, lithologies and the source map to cite.

  python3 macrostrat.py 43.0731 -89.4012            # Madison, Wisconsin, most detailed map (z=12)
  python3 macrostrat.py 39.7392 -104.9903           # Denver: Quaternary cover, lists older units below
  python3 macrostrat.py 43.0731 -89.4012 --z 6 --json   # the 1:1,000,000-style map, as JSON
"""
import argparse, email.utils, gzip, json, os, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from datetime import datetime, timezone

HOST = "https://macrostrat.org"
API = HOST + "/api/v2"
UA = "macrostrat-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider", "macrostrat-skill-example"]   # last = this UA
CACHE = os.path.expanduser(os.environ.get("MACROSTRAT_CACHE", "~/.cache/macrostrat"))
QUATERNARY_BASE = 2.58                         # Ma
SCALES = ("large", "medium", "small", "tiny")
CREDIT = ("Data: Macrostrat (macrostrat.org, the Macrostrat lab at the University of Wisconsin-Madison), CC BY 4.0, "
          "and the original map source above. Cite Peters, S.E., Husson, J.M., and Czaplewski, J., 2018, Macrostrat: "
          "A Platform for Geological Data Integration and Deep-Time Earth Crust Research: Geochemistry, Geophysics, Geosystems, v. 19, p. 1393-1409, doi:10.1029/2018gc007467.")
calls, _last, RP = [], [0.0], None

def retry_wait(value, default=10):
    """Retry-After as delay-seconds or an HTTP date -> seconds to wait; missing or unreadable -> default."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def http(url):
    """-> (status, text, Retry-After). Serial, at least 1 s apart; asks for gzip and unzips it (urllib does not)."""
    time.sleep(max(0.0, _last[0] + 1.0 - time.time()))
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status, enc, retry, body = r.status, r.headers.get("Content-Encoding"), None, r.read()
    except urllib.error.HTTPError as e:
        status, enc, retry, body = e.code, e.headers.get("Content-Encoding"), e.headers.get("Retry-After"), e.read()
    except (urllib.error.URLError, TimeoutError) as e:
        status, enc, retry, body = 0, None, None, str(e).encode()
    _last[0] = time.time()
    if enc == "gzip":
        body = gzip.decompress(body)
    path = urllib.parse.urlsplit(url).path
    calls.append((path.replace("/api/v2", "") or "/", status, round(time.time() - t0, 2)))
    return status, body.decode("utf-8", errors="replace"), retry

def call(path):
    """-> the 'success' object. Checks robots.txt first. 429, 500, 502, 503, 504 or a network error: one retry after
    Retry-After (seconds or an HTTP date), else 10 s; over 120 s exits."""
    url = API + path
    if RP and not all(RP.can_fetch(a, url) for a in AGENTS):
        sys.exit(f"robots.txt disallows {path}: stop")
    for attempt in range(2):
        s, text, retry = http(url)
        if attempt == 0 and s in (0, 429, 500, 502, 503, 504):
            wait = retry_wait(retry)
            if wait > 120:
                sys.exit(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if s != 200:
        sys.exit(f"{url}: HTTP {s} {' '.join(text.split())[:160]!r}")
    d = json.loads(text)
    if "success" not in d:
        sys.exit(f"{url}: no 'success' in the answer: {text[:160]!r}")
    return d["success"]

def robots_load():
    """macrostrat.org/robots.txt is the site's HTTP 404 page today: a 4xx other than 429 = no rules.
    429, 5xx or no answer = rules unknown, so stop."""
    global RP
    s, text, _ = http(HOST + "/robots.txt")
    if 400 <= s < 500 and s != 429:
        return f"robots.txt: HTTP {s}, no rules"
    if s != 200:
        sys.exit(f"robots.txt: HTTP {s}; rules unknown, try later")
    RP = urllib.robotparser.RobotFileParser()
    RP.parse(text.splitlines())
    return f"robots.txt: HTTP 200; every API path is checked for all {len(AGENTS)} agents"

def periods():
    """The 22 international periods (Siderian to Quaternary), cached for 30 days."""
    path = os.path.join(CACHE, "international-periods.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        with open(path, encoding="utf-8") as f:
            return json.load(f), "cached"
    data = call("/defs/intervals?timescale=international%20periods")["data"]
    os.makedirs(CACHE, exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)
    return data, "downloaded"

def period_names(t, b, pers):
    """Periods overlapping t-b Ma, oldest first; [] when all of it is older than 2500 Ma."""
    return [p["name"] for p in sorted((p for p in pers if p["t_age"] < b and p["b_age"] > t), key=lambda p: -p["b_age"])]

def ptext(names):
    if not names:
        return "older than the oldest international period (Siderian, from 2500 Ma)"
    return names[0] if len(names) == 1 else f"{names[0]} to {names[-1]} ({len(names)} periods)"

def cite(ref):
    """'Authors (year). Title. Series. DOI. URL' from the unit's ref; parts the source leaves empty are skipped."""
    a, y = ref.get("authors", "").strip().rstrip(","), ref.get("ref_year", "").strip()
    head = f"{a} ({y})" if a and y else a
    parts = [head] + [ref.get(k, "").strip().rstrip(".") for k in ("ref_title", "ref_source", "isbn_doi")]
    text = ". ".join(p.rstrip(".") if i else p for i, p in enumerate(parts) if p)
    return (text + "." if text else "") + (" " + ref["url"].strip() if ref.get("url", "").strip() else "")

ap = argparse.ArgumentParser()
ap.add_argument("lat", type=float, help="latitude, decimal degrees, -90 to 90")
ap.add_argument("lng", type=float, help="longitude, decimal degrees, -180 to 180")
ap.add_argument("--z", type=int, default=12, help="zoom 0-24: 0-2 tiny, 3-5 small, 6-8 medium, 9-24 large (default 12)")
ap.add_argument("--json", action="store_true", help="print one JSON object instead of text")
args = ap.parse_args()
if not -90 <= args.lat <= 90 or not -180 <= args.lng <= 180:
    ap.error("lat must be -90..90 and lng -180..180 (the API itself accepts lat=95 and answers 'no unit')")
if not 0 <= args.z <= 24:
    ap.error("--z must be 0..24 (the API answers HTTP 404 from z=25)")
lat, lng, nudged = args.lat, args.lng, args.lng == 0
if nudged:
    lng = 0.0001                               # /mobile/map_query answers HTTP 404 to a longitude of exactly 0

log = [f"Macrostrat, checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", robots_load()]
pers, how = periods()
log.append(f"periods: {len(pers)} international periods ({how})")
d = call(f"/mobile/map_query?lat={lat}&lng={lng}&z={args.z}")["data"]
units = [u for u in d["burwell"] if u]
out = {"lat": lat, "lng": lng, "z": args.z, "lng_nudged_from_0": nudged, "elevation_m": d["elevation"], "unit": None,
       "older_units_elsewhere": []}
if units:
    u, m = units[0], d.get("macrostrat") or {}
    t, b = u["t_int_age"], u["b_int_age"]
    out["unit"] = {
        "name": u["name"].strip(), "strat_name": u["strat_name"].strip(),
        "interval": u["b_int_name"] if u["b_int_name"] == u["t_int_name"] else f"{u['b_int_name']} to {u['t_int_name']}",
        "top_ma": t, "base_ma": b, "periods": period_names(t, b, pers),
        "column_match": ({"names": m["rank_names"], "top_ma": m["t_age"], "base_ma": m["b_age"]}
                         if m.get("b_age") is not None else None),
        "description": " ".join((u["descrip"] or "").split()), "lith_legend": u["lith"],
        "liths": [(x["name"], round(x["prop"], 3)) for x in sorted(m.get("lith") or [], key=lambda x: -x["prop"])],
        "scale": u["scale"], "source_id": u["source_id"], "map_id": u["map_id"], "map_citation": cite(u["ref"]),
        "map_url": u["ref"].get("url", ""), "surface_deposit": b <= QUATERNARY_BASE,
    }
    if b <= QUATERNARY_BASE:                   # Quaternary cover: what other maps put at this point
        g = call(f"/geologic_units/map?lat={lat}&lng={lng}")
        for x in sorted((x for x in g["data"] if x["b_int_age"] and x["b_int_age"] > QUATERNARY_BASE),
                        key=lambda x: SCALES.index(x["scale"])):
            src = g["refs"][str(x["source_id"])].strip()
            out["older_units_elsewhere"].append({
                "scale": x["scale"], "name": x["name"].strip(), "top_ma": x["t_int_age"], "base_ma": x["b_int_age"],
                "periods": period_names(x["t_int_age"], x["b_int_age"], pers), "source": src,
                "basement_map": "basement" in src.lower() or "precambrian surface" in src.lower()})
out["calls"] = calls
out["credit"] = CREDIT

if args.json:
    print(json.dumps(out, ensure_ascii=False, indent=1))
else:
    print("\n".join(log))
    print(f"\n{lat:.5f}, {lng:.5f}" + (" (lng 0 sent as 0.0001)" if nudged else "")
          + f", z={args.z}, elevation {d['elevation']} m")
    u = out["unit"]
    if not u:
        print("no geologic map unit here at this zoom (ocean, ice or no map coverage); try a smaller --z")
    else:
        print(f"  unit    {u['name']}" + (f" ({u['strat_name']})" if u["strat_name"] and u["strat_name"] not in u["name"] else ""))
        print(f"  age     {u['interval']}, {u['top_ma']:g}-{u['base_ma']:g} Ma; period {ptext(u['periods'])}")
        if u["column_match"]:
            c = u["column_match"]
            print(f"          Macrostrat column match: {c['names']}, {c['top_ma']:g}-{c['base_ma']:g} Ma")
        print(f"  rock    {u['description'][:300] + (' ...' if len(u['description']) > 300 else '') or '(no description)'}")
        if u["liths"] or u["lith_legend"]:
            print("  liths   " + (", ".join(f"{n} {p:.0%}" for n, p in u["liths"]) if u["liths"] else u["lith_legend"]))
        print(f"  map     {u['map_citation']}")
        print(f"          {u['scale']} scale, Macrostrat source {u['source_id']}, map unit {u['map_id']}")
        if u["surface_deposit"]:
            print("  note    Quaternary surface deposit, not bedrock; older units other maps put here:")
            for x in out["older_units_elsewhere"][:4]:
                print(f"    {x['scale']:<6} {x['name'][:48]:<48} {x['top_ma']:g}-{x['base_ma']:g} Ma, {ptext(x['periods'])}"
                      + (" [basement map: buried]" if x["basement_map"] else ""))
    by = {}
    for p, s, t in calls:
        by.setdefault(p, []).append(s)
    print(f"\n{len(calls)} calls: " + ", ".join(f"{p} x{len(v)} {sorted(set(v))}" for p, v in by.items()))
    print(CREDIT)
sys.exit(0 if out["unit"] else 2)
```

Output (seven commands, re-run on 2026-11-26 at 00:38 UTC with an empty cache; the first command downloaded the period list, the others read it):

```text
$ python3 -I macrostrat.py 43.0731 -89.4012
Macrostrat, checked 2026-11-26 00:38 UTC
robots.txt: HTTP 404, no rules
periods: 22 international periods (downloaded)

43.07310, -89.40120, z=12, elevation 270 m
  unit    Wonewoc Formation (Cw)
  age     Cambrian, 486.85-538.8 Ma; period Cambrian
          Macrostrat column match: Wonewoc Formation, 496.8-497.85 Ma
  rock    Quartz sandstone, medium grained, brownish yellow to white, with medium- to large-scale cross bedding commonly seen in outcrop. Reaches a maximum thickness of 165 feet (50 m) in the subsurface. Part of Elk Mound Group.
  liths   quartz arenite 81%, siltstone 12%, shale 6%
  map     Brown, B.A., Peters, R.M., Massie-Ferch, K. (2013). Preliminary Bedrock Geology of Dane County, Wisconsin. Open-File Report. https://wgnhs.uwex.edu/pubs/wofr201301di/
          large scale, Macrostrat source 6, map unit 934954

3 calls: /robots.txt x1 [404], /defs/intervals x1 [200], /mobile/map_query x1 [200]
Data: Macrostrat (macrostrat.org, the Macrostrat lab at the University of Wisconsin-Madison), CC BY 4.0, and the original map source above. Cite Peters, S.E., Husson, J.M., and Czaplewski, J., 2018, Macrostrat: A Platform for Geological Data Integration and Deep-Time Earth Crust Research: Geochemistry, Geophysics, Geosystems, v. 19, p. 1393-1409, doi:10.1029/2018gc007467.
(exit 0)

$ python3 -I macrostrat.py 36.1069 -112.1129
Macrostrat, checked 2026-11-26 00:38 UTC
robots.txt: HTTP 404, no rules
periods: 22 international periods (cached)

36.10690, -112.11290, z=12, elevation 1027 m
  unit    Hakatai Shale
  age     Mesoproterozoic, 1000-1600 Ma; period Calymmian to Stenian (3 periods)
  rock    Orange-red, purple, and red mudstone, shale, and sandstone. Forms an upper cliff unit, a middle slope unit, and a lower slope unit. Upper cliff unit consists of pale-purple or lavender, fine- to coarse-grained, thin- to medium-bedded, cross-bedded sandstone. Forms gradational contact with underlying ...
  map     Billingsley, G.H. (2000). Geologic Map of the Grand Canyon 30' x 60' Quadrangle, Coconino and Mohave Counties, Northwestern Arizona. USGS Geologic Investigations Series I-2688. http://pubs.usgs.gov/imap/i-2688/
          large scale, Macrostrat source 34, map unit 2204858

2 calls: /robots.txt x1 [404], /mobile/map_query x1 [200]
Data: Macrostrat (macrostrat.org, the Macrostrat lab at the University of Wisconsin-Madison), CC BY 4.0, and the original map source above. Cite Peters, S.E., Husson, J.M., and Czaplewski, J., 2018, Macrostrat: A Platform for Geological Data Integration and Deep-Time Earth Crust Research: Geochemistry, Geophysics, Geosystems, v. 19, p. 1393-1409, doi:10.1029/2018gc007467.
(exit 0)

$ python3 -I macrostrat.py 39.7392 -104.9903
Macrostrat, checked 2026-11-26 00:38 UTC
robots.txt: HTTP 404, no rules
periods: 22 international periods (cached)

39.73920, -104.99030, z=12, elevation 1601 m
  unit    Broadway Alluvium
  age     Late Pleistocene, 0.0117-0.129 Ma; period Quaternary
          Macrostrat column match: Broadway Alluvium, 0.0117-0.3327 Ma
  rock    Gravel, sand, silt, and clay forming alluvial terrace deposits commonly 7.6 to 12.2 m above present stream level. Includes pre-Piney Creek alluvium of Scott (1962, 1963a). Deposits of major streams west of South Platte River are more coarse-grained near the mountains. Deposits of streams east of Sou ...
  liths   gravel 42%, sand 42%, silt 8%, clay 8%
  map     Trimble, D.E., M.N. Machette (2003). Geologic Map of the Greater Denver Area, Front Range Urban Corridor, Colorado. U.S. Geological Survey Geologic Investigations Series I-856-H. http://pubs.usgs.gov/imap/i-856-h/
          large scale, Macrostrat source 64, map unit 2444199
  note    Quaternary surface deposit, not bedrock; older units other maps put here:
    medium Biotite gneiss and migmatite                     1600-2500 Ma, Siderian to Statherian (4 periods) [basement map: buried]
    small  Paleogene sedimentary                            23.04-66 Ma, Paleogene
    tiny   Mesozoic sedimentary rocks                       201.4-251.902 Ma, Triassic

3 calls: /robots.txt x1 [404], /mobile/map_query x1 [200], /geologic_units/map x1 [200]
Data: Macrostrat (macrostrat.org, the Macrostrat lab at the University of Wisconsin-Madison), CC BY 4.0, and the original map source above. Cite Peters, S.E., Husson, J.M., and Czaplewski, J., 2018, Macrostrat: A Platform for Geological Data Integration and Deep-Time Earth Crust Research: Geochemistry, Geophysics, Geosystems, v. 19, p. 1393-1409, doi:10.1029/2018gc007467.
(exit 0)

$ python3 -I macrostrat.py 51.4779 0
Macrostrat, checked 2026-11-26 00:38 UTC
robots.txt: HTTP 404, no rules
periods: 22 international periods (cached)

51.47790, 0.00010 (lng 0 sent as 0.0001), z=12, elevation 47 m
  unit    Lambeth Group
  age     Paleocene, 56-66 Ma; period Paleogene
  rock    (no description)
  liths   clay, silt, sand and gravel
  map     British Geological Survey (2015). DiGMapGB-625. British Geological Survey ©NERC. http://www.bgs.ac.uk/products/digitalmaps/DiGMapGB_625.html
          medium scale, Macrostrat source 23, map unit 2030042

2 calls: /robots.txt x1 [404], /mobile/map_query x1 [200]
Data: Macrostrat (macrostrat.org, the Macrostrat lab at the University of Wisconsin-Madison), CC BY 4.0, and the original map source above. Cite Peters, S.E., Husson, J.M., and Czaplewski, J., 2018, Macrostrat: A Platform for Geological Data Integration and Deep-Time Earth Crust Research: Geochemistry, Geophysics, Geosystems, v. 19, p. 1393-1409, doi:10.1029/2018gc007467.
(exit 0)

$ python3 -I macrostrat.py 30 -40
Macrostrat, checked 2026-11-26 00:38 UTC
robots.txt: HTTP 404, no rules
periods: 22 international periods (cached)

30.00000, -40.00000, z=12, elevation -3422 m
no geologic map unit here at this zoom (ocean, ice or no map coverage); try a smaller --z

2 calls: /robots.txt x1 [404], /mobile/map_query x1 [200]
Data: Macrostrat (macrostrat.org, the Macrostrat lab at the University of Wisconsin-Madison), CC BY 4.0, and the original map source above. Cite Peters, S.E., Husson, J.M., and Czaplewski, J., 2018, Macrostrat: A Platform for Geological Data Integration and Deep-Time Earth Crust Research: Geochemistry, Geophysics, Geosystems, v. 19, p. 1393-1409, doi:10.1029/2018gc007467.
(exit 2)

$ python3 -I macrostrat.py 43.0731 -89.4012 --z 6 --json
{
 "lat": 43.0731,
 "lng": -89.4012,
 "z": 6,
 "lng_nudged_from_0": false,
 "elevation_m": 270,
 "unit": {
  "name": "Sandstone with some dolomite and shale, undivided",
  "strat_name": "Sandstone with some dolomite and shale, undivided",
  "interval": "Cambrian",
  "top_ma": 486.85,
  "base_ma": 538.8,
  "periods": [
   "Cambrian"
  ],
  "column_match": null,
  "description": "Sandstone with some dolomite and shale, undivided; includes Trempealeau City and Elk Mound Groups",
  "lith_legend": "sandstone, shale",
  "liths": [],
  "scale": "medium",
  "source_id": 459,
  "map_id": 3769249,
  "map_citation": "Mudrey Jr., M.G., Brown, B.A., Greenberg, J.K., 1982, Bedrock Geologic Map of Wisconsin: Wisconsin Geological and Natural History Survey Map M-078, scale 1:1,000,000. https://wgnhs.wisc.edu/catalog/publication/000390",
  "map_url": "https://wgnhs.wisc.edu/catalog/publication/000390",
  "surface_deposit": false
 },
 "older_units_elsewhere": [],
 "calls": [
  [
   "/robots.txt",
   404,
   0.24
  ],
  [
   "/mobile/map_query",
   200,
   0.2
  ]
 ],
 "credit": "Data: Macrostrat (macrostrat.org, the Macrostrat lab at the University of Wisconsin-Madison), CC BY 4.0, and the original map source above. Cite Peters, S.E., Husson, J.M., and Czaplewski, J., 2018, Macrostrat: A Platform for Geological Data Integration and Deep-Time Earth Crust Research: Geochemistry, Geophysics, Geosystems, v. 19, p. 1393-1409, doi:10.1029/2018gc007467."
}
(exit 0)

$ python3 -I macrostrat.py 95 10
usage: macrostrat.py [-h] [--z Z] [--json] lat lng
macrostrat.py: error: lat must be -90..90 and lng -180..180 (the API itself accepts lat=95 and answers 'no unit')
(exit 2)
```

### 4. curl: one point, its interval type and periods, every map there, headers, mistakes

```bash
#!/usr/bin/env bash
# Macrostrat API v2 with curl: robots, the map unit at a point, its periods, the all-scales list, headers, mistakes.
set -euo pipefail
M=https://macrostrat.org/api/v2
C=(curl -sS --max-time 60 --compressed -A 'macrostrat-skill-example/1.0 (+https://github.com/browser-use/browser-harness)')
LAT=36.1069; LNG=-112.1129; Z=12
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# 0. robots.txt first: a 4xx other than 429 = no rules; 200 = check the paths below
code=$("${C[@]}" -o "$T/robots" -w '%{http_code}' https://macrostrat.org/robots.txt)
echo "robots.txt HTTP $code, $(wc -c < "$T/robots") bytes, title: $(grep -o '<title>[^<]*' "$T/robots" | head -1 | cut -c8-)"
python3 -c 'import sys, urllib.robotparser
code, text = int(sys.argv[1]), open(sys.argv[2]).read()
if code != 200 and not (400 <= code < 500 and code != 429): sys.exit("robots.txt rules unknown: stop")
rp = urllib.robotparser.RobotFileParser(); rp.parse(text.splitlines() if code == 200 else [])
paths = ("/mobile/map_query", "/geologic_units/map", "/defs/intervals", "/units", "/columns")
agents = ("*", "GPTBot", "ClaudeBot", "Claude-User", "PerplexityBot", "macrostrat-skill-example")
if not all(rp.can_fetch(a, "https://macrostrat.org/api/v2" + p) for a in agents for p in paths): sys.exit("robots.txt disallows a path: stop")
print("robots: paths allowed")' "$code" "$T/robots"
sleep 1
# 1. the map unit at the point (z 9+ = the most detailed "large" map there); burwell [{}] = no unit
"${C[@]}" --fail "$M/mobile/map_query?lat=$LAT&lng=$LNG&z=$Z" -o "$T/mq"
python3 -c 'import json, sys
d = json.load(open(sys.argv[1]))["success"]["data"]; u = [x for x in d["burwell"] if x]
if not u: sys.exit("no map unit here")
u = u[0]; r = u["ref"]
print("elevation", d["elevation"], "m |", u["name"], "|", u["scale"], "| source", u["source_id"], "map unit", u["map_id"])
print("age", u["b_int_name"], u["b_int_age"], "Ma to", u["t_int_name"], u["t_int_age"], "Ma | int ids", u["b_int_id"], u["t_int_id"])
print("rock", " ".join(u["descrip"].split())[:150], "...")
print("map ", r["authors"], "(" + r["ref_year"] + ").", r["ref_title"] + ".", r["ref_source"] + ".", r["url"])
open(sys.argv[2], "w").write("%s %s %s\n" % (u["t_int_age"], u["b_int_age"], u["t_int_id"]))' "$T/mq" "$T/age"
read -r TOP BASE INT < "$T/age"
sleep 1
# 2. what kind of interval the map gives (era, period, epoch, age) and which international periods it spans
"${C[@]}" --fail "$M/defs/intervals?int_id=$INT" | python3 -c 'import json, sys
i = json.load(sys.stdin)["success"]["data"][0]; print("interval", i["name"], "is an", i["int_type"], "|", i["t_age"], "-", i["b_age"], "Ma")'
sleep 1
"${C[@]}" --fail "$M/defs/intervals?timescale=international%20periods" | python3 -c 'import json, sys
t, b = float(sys.argv[1]), float(sys.argv[2])
p = sorted([p for p in json.load(sys.stdin)["success"]["data"] if p["t_age"] < b and p["b_age"] > t], key=lambda p: -p["b_age"])
print("periods", ", ".join("%s (%g-%g Ma)" % (x["name"], x["b_age"], x["t_age"]) for x in p) or "none (older than 2500 Ma)")' "$TOP" "$BASE"
sleep 1
# 3. every map at this point, all scales, with the reference list keyed by source_id
"${C[@]}" --fail "$M/geologic_units/map?lat=$LAT&lng=$LNG" | python3 -c 'import json, sys
s = json.load(sys.stdin)["success"]
for u in s["data"]:
    print(" ", u["scale"].ljust(6), u["name"][:52].ljust(52), u["t_int_age"], "-", u["b_int_age"], "Ma |", s["refs"][str(u["source_id"])][:60])'
sleep 1
# 4. response headers: CORS open, gzip, a Varnish cache, no rate-limit headers
"${C[@]}" -D - -o /dev/null "$M/mobile/map_query?lat=$LAT&lng=$LNG&z=$Z" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|content-encoding|cache-control|access-control-allow-origin|retry-after|x-cache|via|x-ratelimit[a-z-]*|ratelimit[a-z-]*):)'
sleep 1
# 5. mistakes: no z is HTTP 400; lng exactly 0 is an HTML 404; a word for lat is a 500; lat 95 is "no unit"
for q in "lat=$LAT&lng=$LNG" "lat=51.4779&lng=0&z=12" "lat=abc&lng=$LNG&z=12" "lat=95&lng=10&z=12"; do
  "${C[@]}" -o "$T/m" -w "map_query?$q: HTTP %{http_code} " "$M/mobile/map_query?$q"; tr -s ' \n' ' ' < "$T/m" | head -c 100; echo; sleep 1
done
echo "Data: Macrostrat (macrostrat.org), CC BY 4.0; cite Macrostrat and the map source above. Accessed $(date -u '+%d %B %Y %H:%M') UTC."
```

Output (second run, 2026-11-26 00:39 UTC; the 00:38 UTC run printed the same lines):

```text
robots.txt HTTP 404, 35632 bytes, title: Macrostrat
robots: paths allowed
elevation 1027 m | Hakatai Shale | large | source 34 map unit 2204858
age Mesoproterozoic 1600 Ma to Mesoproterozoic 1000 Ma | int ids 258 258
rock Orange-red, purple, and red mudstone, shale, and sandstone. Forms an upper cliff unit, a middle slope unit, and a lower slope unit. Upper cliff unit c ...
map  Billingsley, G.H. (2000). Geologic Map of the Grand Canyon 30' x 60' Quadrangle, Coconino and Mohave Counties, Northwestern Arizona. USGS Geologic Investigations Series I-2688. http://pubs.usgs.gov/imap/i-2688/
interval Mesoproterozoic is an era | 1000 - 1600 Ma
periods Calymmian (1600-1400 Ma), Ectasian (1400-1200 Ma), Stenian (1200-1000 Ma)
  large  Hakatai Shale                                        1000 - 1600 Ma | Billingsley, G.H. Geologic Map of the Grand Canyon 30' x 60'
  medium Middle Proterozoic sedimentary rocks                 635 - 1400 Ma | Horton, J.D., C.A. San Juan, and D.B. Stoeser. The State Geo
  medium Middle Proterozoic sedimentary rocks                 1000 - 1600 Ma | Richard, S.M., Reynolds, S.J., Spencer, J.E., and Pearthree,
  small  Paleoproterozoic metamorphic and undivided crystalli 1600 - 2500 Ma | Garrity, C.P., and Soller, D.R.,. Database of the Geologic M
  tiny   Paleozoic sedimentary rocks                          251.902 - 298.9 Ma | Chorlton, L.B. Generalized geology of the world: bedrock dom
HTTP/2 200
access-control-allow-origin: *
content-encoding: gzip
content-type: application/json; charset=utf-8
via: 1.1 production-api-gateway-7cf774df7d-xtrlc (Varnish/7.7)
x-cache: hit
map_query?lat=36.1069&lng=-112.1129: HTTP 400 { "error": { "v": 2, "license": "CC-BY 4.0", "message": "You are missing a required parameter", "abo
map_query?lat=51.4779&lng=0&z=12: HTTP 404 <!DOCTYPE html> <html lang="en"> <head> <meta charset="utf-8"> <title>Error</title> </head> <body> <
map_query?lat=abc&lng=-112.1129&z=12: HTTP 500 { "error": { "message": { "length": 161, "name": "error", "severity": "ERROR", "code": "22P02", "whe
map_query?lat=95&lng=10&z=12: HTTP 200 { "success": { "v": 2, "license": "CC-BY 4.0", "data": { "elevation": null, "burwell": [ {} ], "macr
Data: Macrostrat (macrostrat.org), CC BY 4.0; cite Macrostrat and the map source above. Accessed 26 November 2026 00:39 UTC.
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `/mobile/map_query?lat=&lng=&z=` -> `data.burwell[0]` | `name` (`Wonewoc Formation (Cw)`), `strat_name`, `descrip` (free text, can be `""`), `lith` (legend words, often `""`), `liths` (ids), `t_int_id`/`t_int_name`/`t_int_age` (top) and `b_int_*` (base, Ma), `color`, `scale` (`tiny`, `small`, `medium`, `large`), `source_id`, `map_id`, `macro_units`, `strat_names`, `ref` | `burwell` is `[{}]` (one empty object) when no map covers the point. `ref` holds `authors`, `ref_year`, `ref_title`, `ref_source`, `isbn_doi`, `url`, `name` (the map's short name, e.g. `Grand Canyon, AZ`) |
| `data.macrostrat` | `rank_names`, `strat_names`, `b_age`, `t_age`, `b_int_name`, `t_int_name`, `max_thick`, `lith` (`name`, `type`, `class`, `prop`), `environ`, `econ`, `pbdb_collections` | the stratigraphic column units the map unit is linked to; `{}` or only names when there is no link (Grand Canyon, London) |
| `data.elevation`, `data.lines` | `270` at Madison, `1601` at Denver, `-3422` in the Atlantic; `null` at lat 95. `lines`: `Tipoff Fault`, `normal fault` at the Grand Canyon point | units of `elevation` are not documented; the values match metres. `lines` is `{}` when no line is near |
| `z` -> scale (seen at Madison) | 0-2 `tiny`, 3-5 `small`, 6-8 `medium`, 9-16 `large` | where no `large` map exists, z=12 gives the most detailed one there (Chicago, London, Edinburgh: `medium`) |
| `/geologic_units/map?lat=&lng=[&scale=]` -> `data[]`, `refs` | same unit fields plus `t_age`, `b_age`, `best_int_name`; `refs` = `{source_id: "Authors. Title. Series."}` | all maps at all scales that cover the point (10 at Madison, from bedrock, Quaternary and Precambrian-basement maps); the route's own help lists `scale` as `small`, `medium` or `large`, and `tiny` also works (1 unit at Madison); an unknown value such as `huge` is HTTP 500 "Invalid scale parameter passed." |
| `/defs/intervals?timescale=international%20periods` | 22 rows: `int_id`, `name`, `abbrev`, `t_age`, `b_age`, `int_type` (`period`), `color` | Quaternary 0-2.58 Ma to Siderian 2300-2500 Ma; nothing older (Archean rock gets no period) |
| `/defs/intervals?int_id=258,122,492` | `int_type`: `era` (Mesoproterozoic), `period` (Cambrian), `age` (Late Pleistocene) | the map's interval names are of any rank; the North American stage `Dresbachian` also appears |
| `/meta` | `license`, `citation` ("Peters, S.E. et al. Macrostrat: a platform for geological data integration and deep-time research. https://macrostrat.org, accessed on (date)"), `version` (`2.6.0`) | the about page gives the 2018 paper citation the blocks print |
| errors | HTTP 400 JSON "You are missing a required parameter" (with the route's own help); HTTP 404 HTML "Cannot GET /mobile/map_query"; HTTP 500 JSON with a database error | any route called with no parameters returns its own description (fields, examples) |

## Gotchas

- **`z` is required and changes the answer.** Without it `/mobile/map_query` is HTTP 400. At Madison z=2 says "Paleozoic sedimentary rocks" (a world map), z=6 "Sandstone with some dolomite and shale, undivided" (the 1:1,000,000 Bedrock Geologic Map of Wisconsin) and z=12 "Wonewoc Formation (Cw)" (the Dane County map). Use z=12 for "what is here" and say which map and scale the answer comes from, as the blocks do.
- **Surface deposits come back as the unit.** Denver (Broadway Alluvium), New Orleans (Natural Levees), Amsterdam (Clay, Holocene), Tokyo (valley floor ... deposits) and a Death Valley point (alluvium, lake, playa, and terrace deposits) gave Quaternary units at z=12. Blocks 1 and 3 flag a unit whose base is 2.58 Ma or younger and list older units from other maps at the point, most detailed first.
- **Older units at a point are not all at the surface.** `/geologic_units/map` mixes maps: at Denver a "Preliminary Precambrian basement map of Colorado" puts 1600-2500 Ma gneiss there, under the cover, and at Madison a Precambrian surface map of Iowa puts granite there. The blocks mark sources whose title says "basement" or "Precambrian surface"; read the source title before calling any of them bedrock.
- **The map's age is an interval, not a date.** `t_int_age`/`b_int_age` are the bounds of the named interval (Cambrian 486.85-538.8 Ma), and the name can be an era (Mesoproterozoic), a period, an epoch or an age. When `data.macrostrat` has `b_age`/`t_age`, they are the matched column units' ages and are narrower (Wonewoc: 496.8-497.85 Ma). The period comes from overlapping the bounds with the 22 international periods; an era maps to several (Hakatai Shale: Calymmian, Ectasian, Stenian) and rock older than 2500 Ma maps to none.
- **Longitude 0 fails.** `/mobile/map_query?lat=51.4779&lng=0&z=12` (and `lng=0.0`) is HTTP 404 with an HTML "Cannot GET /mobile/map_query" page; `lng=0.0001` gives the Lambeth Group. `/geologic_units/map` accepts `lng=0`. Blocks 1 and 3 send 0.0001.
- **Bad input is not checked for you.** `lat=95` answers HTTP 200 with `elevation: null` and an empty unit; `lat=abc` is HTTP 500 with the database's error object. Validate -90..90 and -180..180 first (blocks 1 and 3 do).
- **No unit is `[{}]`, not `[]`.** The open Atlantic (30, -40) and Antarctic points gave `burwell: [{}]`; drop empty objects before reading `[0]`. At z=1, lat -80 gave the world map's "Phanerozoic ice".
- **`/units` and `/columns` answer a different question.** `/units?lat=&lng=&response=short` returns the whole stratigraphic column for a region (15 units at Madison in column 187, "Baraboo District, Sauk County, Wisconsin", 18,141 km²; 48 at Denver), not the rock at the point. Use them for the sequence below, not for the answer.
- **Cite both.** The about page asks for credit to Macrostrat and to the original data sources; `ref` is that source, and `ref_source` can carry the publisher's notice (`British Geological Survey ©NERC`). Keep it in the citation, as the blocks do. Some `ref_title` values are already a full citation with authors and year (the 1982 Wisconsin map); block 3's formatter then prints it as given.
- **Descriptions are long.** The Hakatai Shale `descrip` is 1,237 characters; the blocks shorten it for display (block 3's `--json` keeps it whole).
- **Tab marker.** The harness sets the tab title to a horse emoji. Blocks 1 and 2 check `location.href` and the page text, not the title.

## What does not work

- **A depth-to-bedrock or borehole answer**: the API returns map units, not what lies under a Quaternary cover at a point.
- **One exact age in Ma for most units**: maps give interval names; only units linked to Macrostrat columns get narrower ages.
- **Ages older than 2500 Ma as periods**: the international periods stop at the Siderian.
- **Not tested:** a 429 (never seen; no limit is published), the v3 API (the data-services page says it "should not be relied on for published work"), the tile server, CSV/GeoJSON output, `/geologic_units/map/points`, and points in every continent (Africa at 0, 10 gave no unit at z=10).
