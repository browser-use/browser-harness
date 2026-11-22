# geo.admin.ch (Swiss federal geoportal, swisstopo) via api3.geo.admin.ch - Geocode a Swiss Address or Place Name to WGS84 and LV95 Coordinates and Get Its Elevation Above Sea Level, Plus Its Commune and a Terrain Profile (REST API, no key)

Field-tested against api3.geo.admin.ch, docs.geo.admin.ch and www.geo.admin.ch on 2026-11-21 (US Pacific afternoon; 00:17-00:32 UTC on 22 November, 01:17-01:32 in Switzerland) using a fresh Browser Use cloud browser (logged out; one session, 00:20-00:30 UTC) plus Python `urllib` and `curl` from a Linux machine. 27 browser page loads (6 while reading the terms, the federal disclaimer and robots.txt files, 1 in block 1's first run, 10 in each of block 2's two runs) and 67 in-page `fetch()` calls (block 1 ran 3 times, block 2 twice), 41 urllib calls (14 searches while exploring; block 3 twice, the second time from its cache: 21 API calls and 6 robots.txt) and 71 curl calls (41 to the API and 12 to the docs and robots.txt while exploring, 18 in block 4's two runs), all serial, at least 1.5 s apart while exploring and 2 s apart in the blocks (under the 40 requests a minute the terms allow). Every API call was HTTP 200 except the deliberate HTTP 400 probes below; docs URLs I guessed wrong and https://docs.geo.admin.ch/robots.txt answered HTTP 404. curl and urllib timed searches at 0.21-0.32 s and heights at 0.08-0.37 s. No 429, no 403, no challenge, no key, no login. Block 1's output below is its third run (identical to the second apart from the clock), block 2's its second (identical to the first), block 3's its first (empty cache; the second run answered all 22 lookups from disk), block 4's its second (after a comment fix; only CloudFront's `x-cache` changed). An independent re-run on 2026-11-22 at 00:34-00:37 UTC (a new cloud browser, empty cache) printed the same output for all 4 blocks apart from the clock. After review on 2026-11-22, block 3 skips profile points without an elevation and closes its cache files; it re-ran at 00:58 UTC on an empty cache (21 API calls) with the same output.

robots.txt (checked 2026-11-22 UTC, curl, the cloud browser and `urllib.robotparser` in block 3): https://api3.geo.admin.ch/robots.txt is one `User-agent: *` group with `Disallow: /loader.js`, `/dev`, `/testi18n`, `/checker`, `/checker_dev` and `/mapproxy`, nothing else; https://www.geo.admin.ch/robots.txt and https://www.admin.ch/robots.txt are `User-agent: *` with an empty `Disallow:`; https://docs.geo.admin.ch/robots.txt answers HTTP 404 (an S3 `NoSuchKey` page), which RFC 9309 (section 2.3.1.3) treats as no rules. No file names an AI agent (0 named groups), so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-Web, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot and Bytespider all fall under `*`, and every path this skill uses (`/rest/services/api/SearchServer`, `/rest/services/height`, `/rest/services/profile.json`, `/rest/services/profile.csv`, `/rest/services/api/MapServer/identify`, `/rest/services/api/MapServer`) is allowed for all 14 agents: none starts with a disallowed prefix, and block 3 checks four of them with `urllib.robotparser`. Terms: the General Terms of Use and Operating Conditions of the Federal Spatial Data Infrastructure FSDI (https://www.geo.admin.ch/en/general-terms-of-use-fsdi, "swisstopo COSIG / 01.01.2025") say "The acquisition and use of data or services is free of charge, subject to the provisions on fair use", "Use of the geoservices of the FSDI does not require registration and is free-of-charge", and "The data obtained may be processed, analysed and published in accordance with their terms of use"; the request-limit table gives "API Rest Services (general)", `*.geo.admin.ch`, "21 Mio requests / year" and "40 requests / minute"; "Note on web scraping: Automatic parsing of geoservices via bots with high query intensities is to be avoided. The download service should be used to obtain the datasets outside the context of the web services"; section 3.1 asks for the source "in accordance with the terms of use of the corresponding dataset, as is done in the lower right corner of the map viewer. © Data: swisstopo"; section 4.1: "the disclaimer of the Federal administration and the respective terms of use must be complied with in every case". That disclaimer (https://www.admin.ch/gov/en/start/terms-and-conditions.html, which redirects to /en/terms-and-conditions) says "no warranty can be given in respect of the accuracy, reliability, up-to-dateness or completeness of this information" and "In no event will the Federal Authorities be liable", and its copyright paragraph says reproducing texts, illustrations, photos or other data from the federal websites "requires the prior written consent of the copyright holder"; this skill copies no site content and uses the geoservices on the FSDI terms above. The developer docs add rules for AI agents (https://docs.geo.admin.ch/llms.txt): "Use identify, find and search for interactive use only: one user, one map click or one query", "Do not loop over a grid of bounding boxes to export a layer. We block clients that do this.", "Send a User-Agent header with your application name and a contact (e-mail or URL)", "If you get HTTP 429, wait and retry with exponential backoff" and "If you get HTTP 403, stop." No clause bans AI/ML use, automated access at a moderate rate, or commercial use. So the blocks look up one place at a time, 2 s apart, send a User-Agent with a contact URL, back off on 429 and 5xx, stop on 403, cache by `Cache-Control`, and point bulk work to the STAC download service. Naming: this skill says "geo.admin.ch" (the federal geoportal, operated by swisstopo) in plain text, prints "© Data: swisstopo" with every answer, uses no Swiss coat of arms or federal logo, and is not affiliated with or endorsed by swisstopo or the Swiss federal authorities. Slug `geo-admin-ch`.

**Not for surveying, navigation or legal boundaries.** Search coordinates come as single-precision floats (steps up to about 0.4 m) and heights are read from a terrain model; the federal disclaimer above applies. Use official survey data for anything that needs certified positions.

## Quick summary

- **No scraping.** Two GETs per place, no key: `GET https://api3.geo.admin.ch/rest/services/api/SearchServer?searchText=Bundesplatz%203%2C%203011%20Bern&type=locations&limit=50&sr=2056&lang=en` -> `{"results": [{"attrs": {"label": "Bundesplatz 3 <b>3011 Bern</b>", "origin": "address", "lat": 46.946773529052734, "lon": 7.444191932678223, "x": 1199521.125, "y": 2600423.25, "geom_st_box2d": "BOX(2600423.2569999993 1199521.109000001,...)", ...}, "weight": 1, "id": 1006706}]}`, then `GET https://api3.geo.admin.ch/rest/services/height?easting=2600423.25&northing=1199521.12&sr=2056` -> `{"height": "543.1"}`. One search with `sr=2056` gives both systems: `lat`/`lon` are always WGS84, `x`/`y` are LV95. `Access-Control-Allow-Origin: *`.
- **Answers (block 1, 2026-11-22 00:29 UTC):** **Bundesplatz 3, 3011 Bern** -> WGS84 46.94677, 7.44419; LV95 E 2,600,423.2, N 1,199,521.1; **543.1 m**. **Rue du Mont-Blanc 18, 1201 Genève** -> 46.20835, 6.14543; E 2,500,195.0, N 1,118,257.8; **376.7 m**. **Matterhorn** (the "Alpin peak" entry) -> 45.97641, 7.65861; **4477.2 m**. **Säntis** peak (AI) -> 47.24942, 9.34324; **2501.9 m**. **Lugano** (commune) -> 46.02943, 8.98888; 723.6 m at the commune's label point. A typo ("Bahnhofstrase 1 Zurich") gets only fuzzy matches, and the block refuses to guess.
- **x is NORTHING, y is EASTING** in LV95 (`sr=2056`) and LV03 (`sr=21781`) answers, the reverse of `/height?easting=&northing=`; in a `sr=4326` answer x is the longitude and y the latitude. Swapping them on `/height` gives HTTP 400 "Query is out of bounds" (block 2).
- **The first result is often not the place you mean.** Results come grouped by type (postcode, commune, district, canton, names, addresses, stations, parcels), not by match quality: "Matterhorn" lists three gondolas (weight 1) before the peak (weight 100), "Säntis" lists a "Populated Place Säntis" in canton Aargau first, "Zürich HB" lists the stop entry "Zürich HB SZU Süd (Spw)" before "train Zürich HB". The blocks keep exact matches (`weight` 100), require the query's numbers in the label, take optional hint words ("Säntis | peak"), and reject `weight` > 1000 (fuzzy).
- **Fair use: 40 requests a minute** for the REST API (21 million a year), no rate-limit headers, `Cache-Control` 600 s on searches, 86,400 s on heights and profiles, 1,800 s on identify. The blocks wait 2 s between calls, retry 429/5xx/network errors with truncated exponential backoff and jitter (1, 2, 4 ... s plus 0-1 s, as https://docs.geo.admin.ch/get-started/retry.html recommends), and stop on 403. For whole datasets use the STAC API (https://data.geo.admin.ch/api/stac/v1/), not loops over the search.

## What works

### 1. Addresses and place names as a person writes them -> WGS84, LV95 and height (browser)

`on_docs_tab()` opens the logged-out search docs on docs.geo.admin.ch; the API answers `Access-Control-Allow-Origin: *`, so `fetch()` from there needs no credentials. `get()` retries HTTP 0/429/5xx up to 3 times after 1, 2 and 4 s plus 0-1 s of jitter, stops on 403 and raises on anything else. 2 calls per place, 2 s apart (11 calls, about 30 s). `lang=en` fixes the label language (the cloud browser's Accept-Language would pick it otherwise). The place list stands for what one user asks in one go, looked up one search at a time, 2 s apart, as the docs' "one user, one map click or one query" rule asks; do not feed it a file of addresses (for bulk work download the data from the STAC API). This block's `fetch()` calls carry the browser's own User-Agent; the app-name-and-contact User-Agent the docs ask for is sent by blocks 3 and 4, so use those for anything unattended.

```python
import json, random, re, time, urllib.parse

# Places as a person writes them. "name | word" keeps only candidates whose label contains every word after the bar
# (labels carry the feature type in the `lang` language, e.g. "Alpin peak" in English, and the canton, e.g. "(AI)").
PLACES = ["Bundesplatz 3, 3011 Bern", "Rue du Mont-Blanc 18 Genève", "Matterhorn", "Säntis | peak",
          "Lugano", "Bahnhofstrase 1 Zurich"]

DOCS = "https://docs.geo.admin.ch/access-data/search.html"
API = "https://api3.geo.admin.ch/rest/services"
LANG = "en"   # label words: de (the default, also via Accept-Language), fr, it, en
PAUSE = 2.0   # fair use for the REST API: 40 requests / minute (geo.admin.ch FSDI terms, 2.3); this stays at 30
RETRYABLE = (0, 429, 500, 502, 503, 504)

def on_docs_tab():
    """A logged-out page on docs.geo.admin.ch; the API answers Access-Control-Allow-Origin: * to any Origin."""
    try:
        if js("location.href").startswith(DOCS):
            return
    except Exception:
        pass
    new_tab(DOCS)
    wait_for_load()
    for _ in range(30):
        if "SearchServer" in (js("document.body ? document.body.innerText : ''") or ""):
            return
        time.sleep(1)
    raise RuntimeError(f"docs.geo.admin.ch did not show the search docs (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__g[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def get(path, **params):
    """GET API + path -> parsed JSON. Truncated exponential backoff with jitter on 429/5xx/network errors
    (1, 2, 4 s + 0-1 s; docs.geo.admin.ch "Retrying Failed Requests"), stop on 403 and on anything else."""
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        r = fetch(url)
        if r["status"] in RETRYABLE and attempt < 3:
            time.sleep(2 ** attempt + random.random())
            continue
        break
    if r["status"] == 403:
        raise RuntimeError(f"HTTP 403 {url}: blocked; the docs say stop, do not retry")
    if r["status"] != 200:
        raise RuntimeError(f"HTTP {r['status']} {url}: {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"])

def text(label):
    """'<i>Alpiner Gipfel</i> <b>Matterhorn</b> () - ' -> 'Alpiner Gipfel Matterhorn () -'"""
    return " ".join(re.sub(r"<[^>]+>", " ", label).split())

def pick(query, words, results):
    """First candidate that is not fuzzy (weight > 1000), contains every number of the query as a whole number
    (house number, postcode) and every hint word; exact matches (weight 100) first, else the API's order."""
    nums = re.findall(r"\d+", query)
    ok = [r for r in results if r["weight"] <= 1000
          and all(re.search(rf"(?<![\d.]){n}(?![\d.])", text(r["attrs"]["label"])) for n in nums)
          and all(w.lower() in text(r["attrs"]["label"]).lower() for w in words)]
    exact = [r for r in ok if r["weight"] == 100]
    return (exact or ok or [None])[0], len(exact)

on_docs_tab()
print(f"geo.admin.ch location search + height, checked {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
for place in PLACES:
    query, *hint = [p.strip() for p in place.split("|")]
    words = hint[0].split() if hint else []
    # sr=2056: x/y come back in LV95 (x = NORTHING, y = EASTING); lat/lon are always WGS84
    res = get("api/SearchServer", searchText=query, type="locations", limit=50, sr=2056, lang=LANG)["results"]
    best, n_exact = pick(query, words, res)
    print(f"\n{place!r}: {len(res)} candidates")
    if not best:
        print("  no confident match (every candidate is fuzzy or lacks the numbers/words); closest: "
              + "; ".join(f"{text(r['attrs']['label'])} [weight {r['weight']}]" for r in res[:3]))
        continue
    a = best["attrs"]
    e, n = a["y"], a["x"]   # LV95 easting, northing
    h = get("height", easting=f"{e:.2f}", northing=f"{n:.2f}", sr=2056)
    print(f"  -> {text(a['label'])}  [{a['origin']}, weight {best['weight']}, {n_exact} exact match(es)]")
    print(f"  WGS84 lat {a['lat']:.5f}, lon {a['lon']:.5f} | LV95 E {e:,.1f}, N {n:,.1f} | height {float(h['height']):.1f} m above sea level")
    others = [text(r["attrs"]["label"]) for r in res if r is not best and r["weight"] == 100][:3]
    if others:
        print(f"  other exact matches: {'; '.join(others)}")
print("\n© Data: swisstopo")
```

Output (from the third run on 2026-11-22, 00:29 UTC; the second run at 00:24 printed the same lines. The first run at 00:23, before `lang=en` and with the hint "Säntis | Gipfel", printed English labels anyway because of the browser's Accept-Language, so the German hint matched a weight-4 "Building Restaurant Säntisgipfel" instead of the peak):

```text
geo.admin.ch location search + height, checked 2026-11-22 00:29 UTC

'Bundesplatz 3, 3011 Bern': 1 candidates
  -> Bundesplatz 3 3011 Bern  [address, weight 1, 0 exact match(es)]
  WGS84 lat 46.94677, lon 7.44419 | LV95 E 2,600,423.2, N 1,199,521.1 | height 543.1 m above sea level

'Rue du Mont-Blanc 18 Genève': 3 candidates
  -> Rue du Mont-Blanc 18 1201 Genève  [address, weight 4, 0 exact match(es)]
  WGS84 lat 46.20835, lon 6.14543 | LV95 E 2,500,195.0, N 1,118,257.8 | height 376.7 m above sea level

'Matterhorn': 25 candidates
  -> Alpin peak Matterhorn Mont Cervin|Monte Cervino () -  [gazetteer, weight 100, 2 exact match(es)]
  WGS84 lat 45.97641, lon 7.65861 | LV95 E 2,617,048.8, N 1,091,673.0 | height 4477.2 m above sea level
  other exact matches: Building Matterhorn Terminal (VS) - Täsch

'Säntis | peak': 50 candidates
  -> Alpin peak Säntis (AI) - Schwende-Rüte  [gazetteer, weight 100, 1 exact match(es)]
  WGS84 lat 47.24942, lon 9.34324 | LV95 E 2,744,170.8, N 1,234,917.5 | height 2501.9 m above sea level
  other exact matches: Populated Place Säntis (AG) - Unterkulm; Local name swisstopo Säntis (SH) - Buch (SH); Local name swisstopo Säntis (TG) - Erlen

'Lugano': 50 candidates
  -> Lugano (TI)  [gg25, weight 100, 12 exact match(es)]
  WGS84 lat 46.02943, lon 8.98888 | LV95 E 2,720,030.8, N 1,098,728.5 | height 723.6 m above sea level
  other exact matches: Lugano (TI) - Porza,Savosa,Canobbio,Massagno,Lugano,Sorengo,Paradiso,Collina d'Oro; Building Lugano Ressiga 300/50/25m (TI) - Porza; Area with fixed mobil-homes Lugano - Muzzano (TI) - Muzzano

'Bahnhofstrase 1 Zurich': 50 candidates
  no confident match (every candidate is fuzzy or lacks the numbers/words); closest: Part of a populated place Stadtkreis 1 Altstadt (ZH) - Zürich [weight 1518]; School Dorfschule 21 (ZH) - Zürich [weight 1503]; Part of a populated place Stadtkreis 12 Schwamendingen (ZH) - Zürich [weight 1498]

© Data: swisstopo
```

### 2. robots.txt, the terms, the AI-agent rules, coordinate order, caps, height and identify behaviour, mistakes (browser)

10 page loads and 17 in-page `fetch()` calls (about 40 s with the 2 s pacing) in the same tab.

```python
import json, re, time, urllib.parse

API = "https://api3.geo.admin.ch/rest/services"
PAUSE = 2.0   # 40 requests / minute fair-use limit for the REST API; this block makes 17 API calls, about 40 s

START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__g[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def raw(path, **params):
    """One in-page GET of API/path -> {status, headers, text}. No retries: this block only inspects answers."""
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def page(url, needles=()):
    goto_url(url)
    wait_for_load()
    txt = ""
    for _ in range(20):   # wait until every needle shows (or 20 s)
        txt = js("document.body ? document.body.innerText : ''") or ""
        flat = " ".join(txt.split())
        if all(" ".join(n.split()) in flat for n in needles):
            break
        time.sleep(1)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("location.href"), txt

def text(label):
    return " ".join(re.sub(r"<[^>]+>", " ", label).split())

# 1. robots.txt on every host this skill touches
for host in ("api3.geo.admin.ch", "www.geo.admin.ch", "docs.geo.admin.ch", "www.admin.ch"):
    st, href, txt = page(f"https://{host}/robots.txt")
    ua = [l.strip() for l in txt.splitlines() if l.lower().startswith("user-agent")]
    dis = [l.split(":", 1)[1].strip() for l in txt.splitlines() if l.lower().startswith("disallow")]
    print(f"{host + '/robots.txt':<30} HTTP {st}: " + (f"user-agent lines {ua}, Disallow {dis}" if ua
          else f"no robots rules: {' '.join(txt.split())[:70]!r}"))

# 2. Terms, fair-use limits, the federal disclaimer, the rules for AI agents, and what the search docs say
for url, needles in (
    ("https://www.geo.admin.ch/en/general-terms-of-use-fsdi", [
        "The acquisition and use of data or services is free of charge, subject to the provisions on fair use.",
        "Use of the geoservices of the FSDI does not require registration and is free-of-charge.",
        "API Rest Services (general)", "21 Mio requests / year", "40 requests / minute",
        "Automatic parsing of geoservices via bots with high query intensities is to be avoided.",
        "The download service should be used to obtain the datasets outside the context of the web services",
        "© Data: swisstopo",
        "the disclaimer of the Federal administration and the respective terms of use must be complied with",
        "swisstopo COSIG / 01.01.2025"]),
    ("https://www.admin.ch/gov/en/start/terms-and-conditions.html", [
        "no warranty can be given in respect of the accuracy, reliability, up-to-dateness or completeness",
        "In no event will the Federal Authorities be liable"]),
    ("https://docs.geo.admin.ch/llms.txt", [
        "Rules for AI agents and generated code",
        "Use identify, find and search for interactive use only: one user, one map click or one query.",
        "Do not loop over a grid of bounding boxes to export a layer. We block clients that do this.",
        "Send a User-Agent header with your application name and a contact (e-mail or URL).",
        "If you get HTTP 429, wait and retry with exponential backoff",
        "If you get HTTP 403, stop."]),
    ("https://docs.geo.admin.ch/access-data/search.html", [
        "(Max and default limit=50)", "(Max and default limit=30)", "(Max and default limit=20)",
        "Maximum of 10 words", "weight = 100", "typically indicates exact matches",
        "This attribute is in CH1903 / LV03 (EPSG:21781) reference system"]),
    ("https://docs.geo.admin.ch/get-started/retry.html", ["truncated exponential backoff algorithm with jitter"]),
):
    st, href, txt = page(url, needles)
    flat = " ".join(txt.split())
    for n in needles:
        print(f"{href.split('//')[1][:44]:<44} HTTP {st}: {'found' if ' '.join(n.split()) in flat else 'MISSING'}: {n[:64]!r}")
goto_url("https://docs.geo.admin.ch/access-data/search.html")   # stay on docs.geo.admin.ch for the API calls
wait_for_load()
print()

# 3. x and y flip with sr; lat/lon are always WGS84; geom_st_box2d follows sr (the docs say LV03)
q = dict(searchText="Bundesplatz 3 Bern", type="locations", origins="address", limit=1)
for sr in (2056, 4326, 21781):
    r = raw("api/SearchServer", sr=sr, **q)
    a = json.loads(r["text"])["results"][0]["attrs"]
    print(f"sr={sr:<5} x={a['x']:<18} y={a['y']:<18} lat={a['lat']} lon={a['lon']} box2d={a['geom_st_box2d']}")
h = r["headers"]
print("response headers:", {k: h[k] for k in sorted(h) if k in ("content-type", "cache-control", "etag", "retry-after",
      "access-control-allow-origin") or k.startswith("x-ratelimit")})

# 4. Per-call caps: limit=100 is cut to 50 / 30 / 20 without an error
for label, params in (("locations", dict(searchText="Bern", type="locations")),
                      ("layers", dict(searchText="wald", type="layers", lang="en")),
                      ("featuresearch", dict(searchText="bern", type="featuresearch", features="ch.bav.haltestellen-oev", sr=2056))):
    r = raw("api/SearchServer", limit=100, **params)
    print(f"type={label:<14} limit=100 -> HTTP {r['status']}, {len(json.loads(r['text'])['results'])} results")

# 5. Height: the right order, the swapped order, WGS84, no sr, LV03
for label, params in (("E/N LV95, sr=2056     ", dict(easting=2600423.26, northing=1199521.11, sr=2056)),
                      ("swapped (x as easting)", dict(easting=1199521.11, northing=2600423.26, sr=2056)),
                      ("lon/lat with sr=4326  ", dict(easting=7.444192, northing=46.946774, sr=4326)),
                      ("LV95 without sr       ", dict(easting=2600423.26, northing=1199521.11)),
                      ("LV03 without sr       ", dict(easting=600423.26, northing=199521.11))):
    r = raw("height", **params)
    print(f"height {label} HTTP {r['status']}: {' '.join(r['text'].split())[:110]}")

# 6. Profile along a line and the commune/canton at a point (identify)
line = json.dumps({"type": "LineString", "coordinates": [[2600423.26, 1199521.11], [2600618, 1197300]]})
r = raw("profile.json", geom=line, sr=2056, nb_points=5)
pts = json.loads(r["text"])
print(f"\nprofile.json nb_points=5: HTTP {r['status']}, {len(pts)} points, keys {sorted(pts[0])}, alts keys {sorted(pts[0]['alts'])}")
for p in pts:
    print(f"  {p['dist']:>7.1f} m  E {p['easting']:.1f} N {p['northing']:.1f}  COMB {p['alts']['COMB']} m")
ident = dict(geometry="2600423.26,1199521.11", geometryType="esriGeometryPoint", tolerance=0, returnGeometry="false",
             sr=2056, layers="all:ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill")
r = raw("api/MapServer/identify", **ident)
res = json.loads(r["text"])["results"]
print(f"identify commune, no timeInstant: {len(res)} results, years {res[0]['attributes']['jahr']}..{res[-1]['attributes']['jahr']}")
r = raw("api/MapServer/identify", timeInstant=time.gmtime().tm_year, lang="en", **ident)
a = json.loads(r["text"])["results"][0]["attributes"]
print(f"identify commune, timeInstant={time.gmtime().tm_year}: {a['gemname']} ({a['kanton']}), BFS no. {a['gde_nr']}, year {a['jahr']}, current {a['is_current_jahr']}")

# 7. Mistakes
for label, params in (("11 words           ", dict(searchText="a b c d e f g h i j k", type="locations")),
                      ("type=location      ", dict(searchText="Bern", type="location")),
                      ("sr=4327            ", dict(searchText="Bern", type="locations", sr=4327))):
    r = raw("api/SearchServer", **params)
    print(f"search {label} HTTP {r['status']}: {' '.join(r['text'].split())[:120]}")
print("\n© Data: swisstopo")
```

Output (from the second run on 2026-11-22, 00:28 UTC; the first run at 00:25 printed the same lines):

```text
api3.geo.admin.ch/robots.txt   HTTP 200: user-agent lines ['User-agent: *'], Disallow ['/loader.js', '/dev', '/testi18n', '/checker', '/checker_dev', '/mapproxy']
www.geo.admin.ch/robots.txt    HTTP 200: user-agent lines ['User-agent: *'], Disallow ['']
docs.geo.admin.ch/robots.txt   HTTP 404: no robots rules: 'This XML file does not appear to have any style information associated'
www.admin.ch/robots.txt        HTTP 200: user-agent lines ['User-agent: *'], Disallow ['']
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: 'The acquisition and use of data or services is free of charge, s'
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: 'Use of the geoservices of the FSDI does not require registration'
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: 'API Rest Services (general)'
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: '21 Mio requests / year'
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: '40 requests / minute'
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: 'Automatic parsing of geoservices via bots with high query intens'
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: 'The download service should be used to obtain the datasets outsi'
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: '© Data: swisstopo'
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: 'the disclaimer of the Federal administration and the respective '
www.geo.admin.ch/en/general-terms-of-use-fsd HTTP 200: found: 'swisstopo COSIG / 01.01.2025'
www.admin.ch/en/terms-and-conditions         HTTP 200: found: 'no warranty can be given in respect of the accuracy, reliability'
www.admin.ch/en/terms-and-conditions         HTTP 200: found: 'In no event will the Federal Authorities be liable'
docs.geo.admin.ch/llms.txt                   HTTP 200: found: 'Rules for AI agents and generated code'
docs.geo.admin.ch/llms.txt                   HTTP 200: found: 'Use identify, find and search for interactive use only: one user'
docs.geo.admin.ch/llms.txt                   HTTP 200: found: 'Do not loop over a grid of bounding boxes to export a layer. We '
docs.geo.admin.ch/llms.txt                   HTTP 200: found: 'Send a User-Agent header with your application name and a contac'
docs.geo.admin.ch/llms.txt                   HTTP 200: found: 'If you get HTTP 429, wait and retry with exponential backoff'
docs.geo.admin.ch/llms.txt                   HTTP 200: found: 'If you get HTTP 403, stop.'
docs.geo.admin.ch/access-data/search.html    HTTP 200: found: '(Max and default limit=50)'
docs.geo.admin.ch/access-data/search.html    HTTP 200: found: '(Max and default limit=30)'
docs.geo.admin.ch/access-data/search.html    HTTP 200: found: '(Max and default limit=20)'
docs.geo.admin.ch/access-data/search.html    HTTP 200: found: 'Maximum of 10 words'
docs.geo.admin.ch/access-data/search.html    HTTP 200: found: 'weight = 100'
docs.geo.admin.ch/access-data/search.html    HTTP 200: found: 'typically indicates exact matches'
docs.geo.admin.ch/access-data/search.html    HTTP 200: found: 'This attribute is in CH1903 / LV03 (EPSG:21781) reference system'
docs.geo.admin.ch/get-started/retry.html     HTTP 200: found: 'truncated exponential backoff algorithm with jitter'

sr=2056  x=1199521.125        y=2600423.25         lat=46.946773529052734 lon=7.444191932678223 box2d=BOX(2600423.2569999993 1199521.109000001,2600423.2569999993 1199521.109000001)
sr=4326  x=7.444191932678223  y=46.946773529052734 lat=46.946773529052734 lon=7.444191932678223 box2d=BOX(7.444191 46.946774,7.444191 46.946774)
sr=21781 x=199521.046875      y=600423.1875        lat=46.946773529052734 lon=7.444191932678223 box2d=BOX(600423.1876273175 199521.0479856885,600423.1876273175 199521.0479856885)
response headers: {'cache-control': 'public, max-age=600', 'content-type': 'application/json'}
type=locations      limit=100 -> HTTP 200, 50 results
type=layers         limit=100 -> HTTP 200, 30 results
type=featuresearch  limit=100 -> HTTP 200, 20 results
height E/N LV95, sr=2056      HTTP 200: {"height":"543.1"}
height swapped (x as easting) HTTP 400: {"error":{"code":400,"message":"Query is out of bounds"},"success":false}
height lon/lat with sr=4326   HTTP 400: {"error":{"code":400,"message":"Please provide a valid number for the spatial reference system model: 21781, 2
height LV95 without sr        HTTP 200: {"height":"543.1"}
height LV03 without sr        HTTP 200: {"height":"543.1"}

profile.json nb_points=5: HTTP 200, 5 points, keys ['alts', 'dist', 'easting', 'northing'], alts keys ['COMB', 'DTM2', 'DTM25']
      0.0 m  E 2600423.3 N 1199521.1  COMB 543.1 m
    557.4 m  E 2600471.9 N 1198965.8  COMB 502.4 m
   1114.8 m  E 2600520.6 N 1198410.6  COMB 504.8 m
   1672.2 m  E 2600569.3 N 1197855.3  COMB 541.3 m
   2229.6 m  E 2600618.0 N 1197300.0  COMB 628.5 m
identify commune, no timeInstant: 177 results, years 1850..2026
identify commune, timeInstant=2026: Bern (BE), BFS no. 351, year 2026, current True
search 11 words            HTTP 400: {"error":{"code":400,"message":"The searchText parameter can not contain more than 10 words"},"success":false}
search type=location       HTTP 400: {"error":{"code":400,"message":"The type parameter you provided is not valid. Possible values are locations, layers, fea
search sr=4327             HTTP 400: {"error":{"code":400,"message":"Unsupported spatial reference 4327"},"success":false}

© Data: swisstopo
```

In a browser, `fetch()` sees only the headers CORS exposes (here `cache-control` and `content-type`); block 4 shows the rest.

### 3. Several places with Python urllib: robots check for every agent, coordinates, height, commune and canton, a terrain profile, data owners, cache by Cache-Control (no browser)

Sends a User-Agent with a contact URL (the docs ask for one). One call every 2 s; answers are kept on disk for the `max-age` the API sends. 21 API calls on an empty cache, 44.6 s in all.

```python
import hashlib, json, os, random, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser

PLACES = ["Bundesplatz 3, 3011 Bern", "Zürich HB | train", "Uetliberg | hill", "Matterhorn | peak", "Lugano"]
PROFILE = ("Zürich HB | train", "Uetliberg | hill")   # straight-line terrain profile between two of the places
API = "https://api3.geo.admin.ch/rest/services"
UA = "geo-admin-ch-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"   # docs: app name + contact
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "Claude-Web", "Claude-SearchBot",
          "anthropic-ai", "Google-Extended", "PerplexityBot", "Perplexity-User", "CCBot", "Bytespider"]
GAP = 2.0          # fair use: 40 requests / minute for the REST API (FSDI terms 2.3); one call every 2 s is 30
MAX_DELAY, DEADLINE = 64, 300   # backoff cap and give-up time, docs.geo.admin.ch "Retrying Failed Requests"
CACHE_DIR = "~/.cache/geo-admin-ch-skill"
CACHE = os.path.expanduser(CACHE_DIR)
LAYER = {"address": "ch.swisstopo.amtliches-gebaeudeadressverzeichnis", "gazetteer": "ch.swisstopo.swissnames3d",
         "haltestellen": "ch.bav.haltestellen-oev", "gg25": "ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill",
         "height": "ch.swisstopo.swissalti3d-reliefschattierung"}
YEAR = time.gmtime().tm_year
stats = {"net": 0, "cache": 0, "retries": 0, "last": 0.0}

def get(path, **params):
    """API/path?params -> JSON. Disk copy reused for the response's Cache-Control max-age. One call every GAP s.
    Truncated exponential backoff with jitter on 429/5xx/network errors (1, 2, 4 ... 64 s + 0-1 s, give up after
    DEADLINE s); exits at once on 403 (the docs: stop) and on any other error."""
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest())
    try:
        with open(f) as fh:
            meta = json.load(fh)
        if time.time() < meta["expires"]:
            stats["cache"] += 1
            return meta["body"]
    except (OSError, ValueError, KeyError):
        pass
    t0, n = time.time(), 0
    while True:
        time.sleep(max(0, stats["last"] + GAP - time.time()))
        stats["last"] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                body = json.load(r)
                cc = r.headers.get("Cache-Control", "")
            stats["net"] += 1
            age = int(m[1]) if (m := re.search(r"max-age=(\d+)", cc)) else 0
            os.makedirs(CACHE, exist_ok=True)
            with open(f, "w") as fh:
                json.dump({"expires": time.time() + age, "body": body}, fh)
            return body
        except urllib.error.HTTPError as e:
            msg = " ".join(e.read().decode(errors="replace").split())[:160]
            if e.code == 403:
                sys.exit(f"HTTP 403 {url}: blocked; the docs say stop, do not retry")
            if e.code not in (429, 500, 502, 503, 504):
                sys.exit(f"HTTP {e.code} {url}: {msg}")
            err = f"HTTP {e.code}"
        except OSError as e:   # DNS, refused, reset, timeout
            err = str(e)
        delay = min(2 ** n, MAX_DELAY) + random.random()
        if time.time() + delay - t0 > DEADLINE:
            sys.exit(f"{url}: still failing after {time.time() - t0:.0f} s ({err}): stopping")
        stats["retries"] += 1
        n += 1
        time.sleep(delay)

def text(label):
    return " ".join(re.sub(r"<[^>]+>", " ", label).split())

def geocode(place):
    """'name | words' -> (candidate attrs, weight) or (None, closest labels). Rule as in block 1."""
    query, *hint = [p.strip() for p in place.split("|")]
    words = hint[0].lower().split() if hint else []
    res = get("api/SearchServer", searchText=query, type="locations", limit=50, sr=2056, lang="en")["results"]
    nums = re.findall(r"\d+", query)
    ok = [r for r in res if r["weight"] <= 1000
          and all(re.search(rf"(?<![\d.]){n}(?![\d.])", text(r["attrs"]["label"])) for n in nums)
          and all(w in text(r["attrs"]["label"]).lower() for w in words)]
    best = ([r for r in ok if r["weight"] == 100] or ok or [None])[0]
    return (best["attrs"], best["weight"]) if best else (None, [text(r["attrs"]["label"]) for r in res[:3]])

# robots.txt for every agent, fetched with our User-Agent and handed to the parser (a 404 means no rules)
for host, paths in (("https://api3.geo.admin.ch", ["/rest/services/api/SearchServer?searchText=Bern&type=locations",
                                                   "/rest/services/height?easting=2600000&northing=1200000",
                                                   "/rest/services/profile.json", "/rest/services/api/MapServer/identify"]),
                    ("https://docs.geo.admin.ch", ["/llms.txt", "/access-data/search.html"]),
                    ("https://www.geo.admin.ch", ["/en/general-terms-of-use-fsdi"])):
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    try:
        with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
            st = r.status
            rp.parse(r.read().decode("utf-8", "replace").splitlines())
    except urllib.error.HTTPError as e:
        st = e.code
        rp.disallow_all = e.code in (401, 403)
        rp.allow_all = 400 <= e.code < 500 and not rp.disallow_all
    time.sleep(1)
    for p in paths:
        ok = all(rp.can_fetch(a, host + p) for a in AGENTS)
        print(f"{host[8:]:<18} robots.txt HTTP {st}  {p[:60]:<60} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
        if not ok:
            sys.exit("robots.txt now disallows a path this skill uses: stop")

print(f"\ngeo.admin.ch, checked {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
print(f"{'place':<26} {'match':<34} {'lat':>9} {'lon':>9} {'E (LV95)':>11} {'N (LV95)':>11} {'height':>8}  commune (canton)")
found, owners = {}, set()
for place in PLACES:
    a, w = geocode(place)
    if not a:
        print(f"{place:<26} no confident match; closest {w}")
        continue
    e, n = a["y"], a["x"]   # sr=2056: y is EASTING, x is NORTHING
    h = float(get("height", easting=f"{e:.2f}", northing=f"{n:.2f}", sr=2056)["height"])
    idr = get("api/MapServer/identify", geometry=f"{e:.2f},{n:.2f}", geometryType="esriGeometryPoint", tolerance=0,
              returnGeometry="false", sr=2056, timeInstant=YEAR, lang="en",
              layers="all:ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill")["results"]
    com = f"{idr[0]['attributes']['gemname']} ({idr[0]['attributes']['kanton']})" if idr else "outside any commune"
    found[place] = (e, n, h)
    owners.update({a["origin"], "gg25", "height"})
    print(f"{place:<26} {text(a['label'])[:34]:<34} {a['lat']:>9.5f} {a['lon']:>9.5f} {e:>11,.1f} {n:>11,.1f} {h:>7.1f}m  {com}")

# Terrain along the straight line between two places (profile.json takes LV95 E, N pairs)
if not all(p in found for p in PROFILE):
    sys.exit(f"profile needs both {PROFILE} geocoded: stop")
p0, p1 = (found[p] for p in PROFILE)
pts = get("profile.json", geom=json.dumps({"type": "LineString", "coordinates": [list(p0[:2]), list(p1[:2])]}),
          sr=2056, nb_points=50)
z = [(p.get("alts") or {}).get("COMB") for p in pts]   # guard: points without a COMB value are skipped
known = [x for x in z if x is not None]
pairs = [(a, b) for a, b in zip(z, z[1:]) if a is not None and b is not None]
up, down = sum(max(0, b - a) for a, b in pairs), sum(max(0, a - b) for a, b in pairs)
gap = f" (partial: {len(z) - len(known)} of {len(z)} points have no elevation)" if len(known) < len(z) else ""
print(f"\nprofile {PROFILE[0]} -> {PROFILE[1]}: {pts[-1]['dist'] / 1000:.2f} km straight line, {len(pts)} points, "
      + (f"{z[0]:.1f} m -> {z[-1]:.1f} m, " if z[0] is not None and z[-1] is not None else "")
      + (f"lowest {min(known):.1f} m, highest {max(known):.1f} m, +{up:.0f} m / -{down:.0f} m{gap}" if known else "no elevation data"))

# Who owns the data behind each answer (layer metadata), for the source line
src = []
for o in sorted(owners):
    lay = get("api/MapServer", searchText=LAYER[o], lang="en")["layers"]
    src.append(f"{o}: {lay[0]['attributes']['dataOwner'] if lay else '?'}")
print("data owners: " + "; ".join(src))

# Ask again within max-age: answered from disk
before = dict(stats)
geocode(PLACES[0])
print(f"\nrepeat: {stats['net'] - before['net']} calls, {stats['cache'] - before['cache']} disk hits")
print(f"totals: {stats['net']} API calls, {stats['cache']} disk hits, {stats['retries']} retries, cache {CACHE_DIR}")
print("© Data: swisstopo")
```

Output (from the first run on 2026-11-22, 00:27 UTC, empty cache; a second run right after made 0 API calls and printed the same table from 22 disk hits):

```text
api3.geo.admin.ch  robots.txt HTTP 200  /rest/services/api/SearchServer?searchText=Bern&type=locatio allowed for all 14 agents
api3.geo.admin.ch  robots.txt HTTP 200  /rest/services/height?easting=2600000&northing=1200000       allowed for all 14 agents
api3.geo.admin.ch  robots.txt HTTP 200  /rest/services/profile.json                                  allowed for all 14 agents
api3.geo.admin.ch  robots.txt HTTP 200  /rest/services/api/MapServer/identify                        allowed for all 14 agents
docs.geo.admin.ch  robots.txt HTTP 404  /llms.txt                                                    allowed for all 14 agents
docs.geo.admin.ch  robots.txt HTTP 404  /access-data/search.html                                     allowed for all 14 agents
www.geo.admin.ch   robots.txt HTTP 200  /en/general-terms-of-use-fsdi                                allowed for all 14 agents

geo.admin.ch, checked 2026-11-22 00:27 UTC
place                      match                                    lat       lon    E (LV95)    N (LV95)   height  commune (canton)
Bundesplatz 3, 3011 Bern   Bundesplatz 3 3011 Bern             46.94677   7.44419 2,600,423.2 1,199,521.1   543.1m  Bern (BE)
Zürich HB | train          train Zürich HB                     47.37818   8.54022 2,683,190.0 1,248,066.0   408.1m  Zürich (ZH)
Uetliberg | hill           Hill Uetliberg (ZH) - Stallikon     47.34946   8.49197 2,679,589.2 1,244,824.0   870.7m  Stallikon (ZH)
Matterhorn | peak          Alpin peak Matterhorn Mont Cervin|  45.97641   7.65861 2,617,048.8 1,091,673.0  4477.2m  outside any commune
Lugano                     Lugano (TI)                         46.02943   8.98888 2,720,030.8 1,098,728.5   723.6m  Lugano (TI)

profile Zürich HB | train -> Uetliberg | hill: 4.85 km straight line, 50 points, 408.1 m -> 870.7 m, lowest 405.2 m, highest 870.7 m, +481 m / -18 m
data owners: address: Federal Office of Topography swisstopo; gazetteer: Federal Office of Topography swisstopo; gg25: Federal Office of Topography swisstopo; haltestellen: Federal Office of Transport FOT; height: Federal Office of Topography swisstopo

repeat: 0 calls, 1 disk hits
totals: 21 API calls, 1 disk hits, 0 retries, cache ~/.cache/geo-admin-ch-skill
© Data: swisstopo
```

### 4. curl: address -> coordinates -> height, a CSV profile, headers, mistakes

```bash
B=https://api3.geo.admin.ch/rest/services
# --retry 3 retries a timeout or HTTP 408, 429, 500, 502, 503, 504 with curl's own backoff (1, 2, 4 s); a 403 is not retried
C="curl -sS --compressed --max-time 30 --retry 3 -A geo-admin-ch-skill-example/1.0(+https://github.com/browser-use/browser-harness)"
Q="Rue du Mont-Blanc 18 Genève"
# 1. Address -> WGS84 + LV95 in one call (sr=2056: x is NORTHING, y is EASTING; lat/lon are WGS84)
read E N < <($C --fail -G "$B/api/SearchServer" --data-urlencode "searchText=$Q" \
    -d type=locations -d origins=address -d limit=1 -d sr=2056 | python3 -c 'import json, re, sys
a = json.load(sys.stdin)["results"][0]["attrs"]
print(re.sub("<[^>]+>", "", a["label"]), "| lat", round(a["lat"], 5), "lon", round(a["lon"], 5), "| E", a["y"], "N", a["x"], file=sys.stderr)
print(a["y"], a["x"])')
sleep 2
# 2. Height at that point (easting = attrs.y, northing = attrs.x)
$C --fail "$B/height?easting=$E&northing=$N&sr=2056"; echo
sleep 2
# 3. Elevation profile as CSV (profile.csv) between two LV95 points
$C --fail -G "$B/profile.csv" --data-urlencode 'geom={"type":"LineString","coordinates":[[2600423,1199521],[2600618,1197300]]}' \
    -d sr=2056 -d nb_points=3 | tr -d '\r'
sleep 2
# 4. Headers: cache lifetime per endpoint, CORS open to any origin, no rate-limit headers
for p in "api/SearchServer?searchText=Bern&type=locations&limit=1" "height?easting=2600423&northing=1199521&sr=2056"; do
  echo "-- $p"
  $C -D - -o /dev/null -H "Origin: https://example.org" "$B/$p" | tr -d '\r' \
    | grep -iE '^(HTTP/|(content-type|cache-control|access-control-allow-origin|retry-after|x-ratelimit[a-z-]*|x-cache):)'
  sleep 2
done
# 5. Mistakes are JSON with HTTP 400
$C -w ' <- HTTP %{http_code}\n' "$B/height?easting=$N&northing=$E&sr=2056"; sleep 2
$C -w ' <- HTTP %{http_code}\n' "$B/height?easting=6.14543&northing=46.20835&sr=4326"; sleep 2
$C -w ' <- HTTP %{http_code}\n' "$B/height?easting=2000000&northing=1000000&sr=2056"; sleep 2
$C -w ' <- HTTP %{http_code}\n' "$B/api/SearchServer?type=locations"
echo "© Data: swisstopo"
```

Output (from the second run on 2026-11-22, 00:31 UTC; the first run at 00:28 differed only in `x-cache: Miss from cloudfront`):

```text
Rue du Mont-Blanc 18 1201 Genève | lat 46.20835 lon 6.14543 | E 2500195.0 N 1118257.75
{"height":"376.7"}

"Distance";"Altitude";"Easting";"Northing"
"0";"543.1";"2600423.0";"1199521.0"
"1114.8";"504.8";"2600520.5";"1198410.5"
"2229.5";"628.5";"2600618.0";"1197300.0"
-- api/SearchServer?searchText=Bern&type=locations&limit=1
HTTP/2 200 
content-type: application/json
access-control-allow-origin: *
cache-control: public, max-age=600
x-cache: Hit from cloudfront
-- height?easting=2600423&northing=1199521&sr=2056
HTTP/2 200 
content-type: application/json
access-control-allow-origin: *
cache-control: public, max-age=86400
x-cache: Hit from cloudfront
{"error":{"code":400,"message":"Query is out of bounds"},"success":false}
 <- HTTP 400
{"error":{"code":400,"message":"Please provide a valid number for the spatial reference system model: 21781, 2056"},"success":false}
 <- HTTP 400
{"error":{"code":400,"message":"Query is out of bounds"},"success":false}
 <- HTTP 400
{"error":{"code":400,"message":"Please provide a search text"},"success":false}
 <- HTTP 400
© Data: swisstopo
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `SearchServer?type=locations` | `results[]` of `{attrs, id, weight}` | `limit` max 50 (larger values are cut to 50 without an error); `searchText` max 10 words; `origins=zipcode,gg25,district,kantone,gazetteer,address,parcel` filters; no paging parameter |
| `attrs.origin` | `zipcode`, `gg25` (commune), `district`, `kantone`, `gazetteer` (swissNAMES3D), `haltestellen` (public transport stops), `address`, `parcel` | results are ordered by `attrs.rank` (1 postcode ... 10 parcel), then the engine's own order |
| `attrs.label` | HTML: `<i>type</i> <b>name</b> (canton) - commune(s)` | type words follow `lang` (`de` default, `fr`, `it`, `en`) or Accept-Language; stops show a nested `<i><i>haltestellen_</i></i>`; one "Lugano" label had a newline inside the `<b>` |
| `attrs.lat`, `attrs.lon` | WGS84 degrees, always | single-precision floats (46.946773529052734) |
| `attrs.x`, `attrs.y` | in the `sr` system | `sr=2056`/`21781`: x = northing, y = easting; `sr=4326`: x = longitude, y = latitude; default `sr` is 21781 (LV03) |
| `attrs.geom_st_box2d` | `BOX(minE minN,maxE maxN)` | in the `sr` system (the docs say always LV03); full double precision; a point is a zero-size box |
| `attrs.num` | house number for addresses | "18.1" comes back as `num` 181 |
| `attrs.links` (addresses) | `/rest/services/ech/MapServer/ch.swisstopo.amtliches-gebaeudeadressverzeichnis/<id>` and the building register | the docs recommend these links over feature URLs built by hand |
| `weight` | 100 exact name match, < 100 partial, > 1000 fuzzy | addresses that matched exactly still had small weights (1, 4, 7) |
| `height?easting=&northing=&sr=` | `{"height": "543.1"}` (a string, metres) | `sr` 2056 or 21781 only; without `sr` the service guesses from the size of the numbers |
| `profile.json?geom=&sr=&nb_points=` | `[{"dist", "easting", "northing", "alts": {"COMB", "DTM2", "DTM25"}}]` | `geom` is a GeoJSON LineString in LV95/LV03, up to 5,000 coordinates; default 200 points; `profile.csv` gives `"Distance";"Altitude";"Easting";"Northing"` |
| `api/MapServer/identify` | `results[]` of `{layerBodId, layerName, featureId, attributes}` | commune layer: `gemname`, `kanton`, `gde_nr` (BFS number), `jahr`, `is_current_jahr`; needs `timeInstant=<year>` or you get every year since 1850 |
| response headers | `content-type: application/json`, `cache-control: public, max-age=600` (search) / `86400` (height, profile) / `max-age=1800, public` (identify), `access-control-allow-origin: *`, `x-cache` | no `ETag`, no rate-limit headers; served through CloudFront (`server: gunicorn` on search, height and profile, `Apache/2.4.69 (Debian)` on identify) |

## Gotchas

- **Coordinate order flips with `sr`.** LV95/LV03 answers put the northing in `x` and the easting in `y`; WGS84 answers put the longitude in `x`. `/height` takes `easting=` (attrs.y) and `northing=` (attrs.x). Easier: request `sr=2056` and read WGS84 from `lat`/`lon`.
- **Precision.** `x`, `y`, `lat` and `lon` are single-precision floats: LV95 `y` 2600423.25 against `geom_st_box2d` 2600423.2569999993, so steps of 0.125-0.25 m in LV95 and about 0.4 m in latitude. For a point result, parse `geom_st_box2d` for full precision; for an area (commune, canton) it is a bounding box and `x`/`y` is a label point inside it.
- **A commune's point is not its town centre.** "Lugano" (gg25) gives one label point inside the commune area, and the height there (723.6 m) is the terrain at that point, not "the elevation of Lugano". For a town, geocode a named place, a station or an address in it.
- **Pick with `weight` and the label, not position.** See the Matterhorn, Säntis and Zürich HB cases above. Without a postcode, "Bundesplatz 3 Bern" returned numbers 3, 1, 2, 4, 5 and 8 (the right one first, weight 7); with "Bundesplatz 3, 3011 Bern" only number 3. Check that the house number in the label is a whole number ("18" must not match "18.1").
- **Fuzzy matches look confident.** "Bahnhofstrase 1 Zurich" returned "Stadtkreis 1 Altstadt" and a "Rue de Zurich 1" in Biel/Bienne, all with weights 1498-1518. The docs say weights above 1000 are fuzzy and "weight values should be used as general guidelines only"; ask the user instead of picking one.
- **Label language changes.** The same "Matterhorn" entry is "Alpiner Gipfel" (default), "Alpin peak" (`lang=en` or `Accept-Language: en`), "Sommet alpin" (fr) or "Cima alpina" (it). Fix `lang` before matching words in labels.
- **Strip the HTML in labels.** `<b>`, `<i>` and the nested `<i><i>haltestellen_</i></i>` for stops; "Lugano" also came back twice, once with a newline inside the `<b>` (weight 1) and once without (weight 100).
- **Per-call caps without errors.** `limit=100` gave 50 locations, 30 layers, 20 feature-search hits (block 2), with no next page, so a full page (50, 30 or 20) may be cut off: say so. To find one thing, narrow with `origins`, a postcode or a canton name; for a complete list (every address in a commune, every stop) download the dataset from the STAC API instead of working around the cap.
- **Heights outside Switzerland can still answer.** A point 200 km west and 200 km south of Bern (E 2,400,000, N 1,000,000) returned 200.8 m; only further away (E 2,000,000) did the service say "Query is out of bounds". Do not use `/height` to test whether a point is in Switzerland; use `identify` on the commune layer.
- **No commune for some points.** The Matterhorn summit point (its label lists no canton or commune) returned no commune from `identify` (block 3). Handle an empty `results` list instead of indexing `[0]`.
- **`identify` on time-enabled layers returns history.** The commune layer gave 177 features (years 1850-2026) for one point until `timeInstant=2026` was added.
- **CORS is open, caching is long.** Every answer had `access-control-allow-origin: *`; heights and profiles may be cached for a day, searches for 10 minutes. Block 3 honours `max-age` and keeps answers in `~/.cache/geo-admin-ch-skill`.
- **Fair use is the limit, and bulk is a different service.** 40 requests a minute, 21 million a year for the REST API (terms, block 2); "We block clients that do this" for grid loops; contact webgis@swisstopo.ch before high volumes (docs) or info@geo.admin.ch when you expect to exceed the limits (terms). For a whole layer, download it from the STAC API.
- **Credit and naming.** Print "© Data: swisstopo" with results. Stops (`haltestellen`) come from the Federal Office of Transport FOT (layer metadata, block 3); check each dataset's own terms on geocat.ch, as the terms ask. Say "geo.admin.ch" or "swisstopo" in plain text; no coat of arms or federal logo, no official look.
- **Docs URLs.** https://docs.geo.admin.ch/llms.txt links every docs page as a Markdown twin (`/access-data/search.md`, `/get-started/retry.md`); guessed paths such as `/get-started/retrying-failed-requests.html` are HTTP 404. The docs show `/rest/services/ech/SearchServer`; `/rest/services/api/SearchServer` returned the same first result.

## What does not work

- **WGS84 on `/height`**: `sr=4326` is HTTP 400 "Please provide a valid number for the spatial reference system model: 21781, 2056". Search with `sr=2056` (or convert) first.
- **Swapped coordinates**: `easting=<northing>&northing=<easting>` is HTTP 400 "Query is out of bounds".
- **Search mistakes**: 11 words ("can not contain more than 10 words"), `type=location`, `sr=4327` ("Unsupported spatial reference 4327") and a missing `searchText` ("Please provide a search text") are HTTP 400 with `{"error": {"code": 400, "message": ...}, "success": false}`.
- **A fake browser User-Agent on www.admin.ch**: https://www.admin.ch/gov/en/start/terms-and-conditions.html answered curl and Python `requests` with HTTP 403 "Access Denied" (an Akamai edgesuite page) when they sent a Chrome User-Agent string (2026-11-21 and 2026-11-22). With curl's default User-Agent or an honest one with a contact URL it answered HTTP 301 to /en/terms-and-conditions and then HTTP 200; the cloud browser loaded it too (block 2).
- **Not tested:** a 429 or 403 (never provoked), `POST` to the profile service, the `find` and feature endpoints, `type=layers` output beyond the count, parcel search, WMS/WMTS tiles, the geodesy reframe service and STAC downloads.
