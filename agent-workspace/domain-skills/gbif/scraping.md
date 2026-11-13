# GBIF.org - Count Openly Licensed Mountain Lion (Puma concolor) Records in the US, by State (public API, no key)

Field-tested against api.gbif.org on 2026-11-13 using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux machine. 17 browser page loads (API, robots files, terms and docs pages) and 71 in-page `fetch()` calls, 60 curl calls and 8 urllib calls to api.gbif.org, all serial at 1 s or more spacing: every API call was HTTP 200 except the deliberate HTTP 400 probes below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-13, curl and the cloud browser): https://api.gbif.org/robots.txt has one rule for `User-agent: *`, `Disallow: /v1/image/unsafe`, plus an empty `Disallow:` for social preview bots (Discordbot, LinkedInBot, Pinterestbot, Slackbot, Snapchat, TelegramBot, Twitterbot, WhatsApp, facebookexternalhit). No named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*` and may fetch the `/v1/species/match`, `/v1/occurrence/search`, `/v1/dataset/`, `/v1/organization/` and `/v1/geocode/gadm/` paths used here. https://www.gbif.org/robots.txt (curl got a Cloudflare challenge, HTTP 403; the cloud browser got HTTP 200 on its second load) disallows `/occurrence/`, `/search`, `/taxon/search`, `/dataset/search` and similar for `*`, with `crawl-delay: 0.1`; this skill never loads www.gbif.org pages, and the API docs say the same: "The GBIF website at www.GBIF.org is not part of the public API. Scripted use of www.GBIF.org, including scraping, bulk downloading of webpages or web page resources may be blocked without warning." Terms: https://www.gbif.org/terms says "all open-access species occurrence datasets on GBIF.org carry standardized, machine-readable licences", one of CC0, CC BY or CC BY-NC ("CC BY-NC, under which data are made available for any use provided that attribution is appropriately given and provided the use is not for commercial purposes"). The Data user agreement (https://www.gbif.org/terms/data-user, "last updated: 15 September 2026"): "Users must comply with the terms and conditions included in the licence selected by each Data Publisher"; "Users must publicly acknowledge ... the Data Publishers whose biodiversity data they have used, where appropriate through use of a Digital Object Identifier (DOI)"; "the identifier of ownership of data must be retained with every data record shared onward for reuse"; "it is forbidden to use APIs to create denial of service, disruption in the service, and in general to interfere with the normal operations of GBIF and the Data Publishers." No AI/ML, scraping or automated-access clause for the API (the API docs invite use "in scripts, workflows or analyses"). The non-commercial limit attaches to CC BY-NC records, so every block filters on `license=CC0_1_0&license=CC_BY_4_0`; that drops 6,899 of the 11,916 US records. Naming: the citation guidelines name the site "GBIF.org" and the organisation "GBIF: The Global Biodiversity Information Facility"; this skill uses those names in plain text only and no GBIF logo. This skill is not affiliated with or endorsed by GBIF.

**Attribution:** cite "GBIF.org" with the access date and the publishers whose records you use (block 1 prints the top 5 with dataset DOIs). The citation guidelines (https://www.gbif.org/citation-guidelines) say search-API results get no DOI: "It is up to the user to identify dataset publishers and properly acknowledge each of them when citing the data", and recommend a derived dataset for a citable DOI. CC BY records also need their own credit.

## Quick summary

- **No scraping.** `GET https://api.gbif.org/v1/species/match?name=Puma%20concolor` gives `usageKey` 2435099. Then `GET /v1/occurrence/search?taxonKey=2435099&country=US&license=CC0_1_0&license=CC_BY_4_0&occurrenceStatus=PRESENT&limit=0&facet=stateProvince&facetLimit=1000` gives the count and per-state counts in one call. No key, `access-control-allow-origin: *`.
- **Answer (2026-11-13, 23:37 UTC):** GBIF holds **11,916** US mountain lion records; **5,017 are openly licensed** (CC0 3,462 + CC BY 1,555), 5,016 after dropping one absence record. They sit in **34 states** (65 records have no state): **Nebraska 932, New Mexico 844, California 792**, Idaho 454, Texas 290, Arizona 260, Utah 257. The raw facet says New Mexico 843; one more record is spelled "New mexico".
- **Most are not sightings.** Only **1,524** are observations (`HUMAN_OBSERVATION` 1,485 + `MACHINE_OBSERVATION` 39), in 18 states: Nebraska 919, California 352, Montana 55. The other 3,492 are museum specimens (3,125), material samples (191) and fossils (176).
- **Records, not cats.** 918 of Nebraska's 919 observations come from one iNaturalist observer. In a sample of 20, several are tracks or scrapes, and all have coordinates blurred to about 28 km.
- **The licence filter is mandatory** and works per record. The iNaturalist dataset is CC BY-NC at dataset level, but its 1,464 records counted here carry CC BY 4.0 (1,323) or CC0 (141) record licences. Block 1 checks the record licences for each top dataset.
- **Silent failures:** a misspelt parameter is ignored (`contry=US` counts the world: 32,198); `taxonKey=abc` is HTTP 200 with count 0; `facet` returns only 10 values unless you set `facetLimit`. The blocks check every filter against a facet.
- **Rate limit:** none published. The API docs say search APIs "may be rate limited, depending on our server load", with HTTP 429, and "we do not guarantee any particular query rate will work". Blocks pace 1 s per call, serial, and wait 60 s once on 429/5xx.

## What works

### 1. Openly licensed US records by state, sightings only, and the publishers to cite (browser)

`on_api_tab()` opens one logged-out api.gbif.org JSON page, so `fetch()` is same-origin. `get()` returns parsed JSON on HTTP 200, waits 60 s once on 429/5xx and otherwise raises. `search()` always uses `limit=0` (count and facets only) and refuses a facet that hit its `facetLimit`. The block resolves the name, proves the licence filter against the licence facet, splits by `basisOfRecord`, merges spelling variants of `stateProvince`, and checks record licences for the top publishers.

```python
import json, re, time, urllib.parse
from datetime import datetime, timezone

NAME = "Puma concolor"   # scientific name; common names ("mountain lion") return matchType NONE
COUNTRY = "US"           # ISO 3166-1 alpha-2, as GBIF interprets it
OPEN = ["CC0_1_0", "CC_BY_4_0"]                 # leaves out CC_BY_NC_4_0 (non-commercial only)
SIGHTINGS = ["HUMAN_OBSERVATION", "MACHINE_OBSERVATION"]  # the other basisOfRecord values are specimens, samples, fossils

SITE = "https://api.gbif.org"
PAUSE = 1.0  # techdocs: search APIs "may be rate limited, depending on our server load" (HTTP 429); no fixed number, keep calls serial
US_STATES = {s.lower() for s in (
    "Alabama Alaska Arizona Arkansas California Colorado Connecticut Delaware Florida Georgia Hawaii Idaho Illinois Indiana "
    "Iowa Kansas Kentucky Louisiana Maine Maryland Massachusetts Michigan Minnesota Mississippi Missouri Montana Nebraska "
    "Nevada Ohio Oklahoma Oregon Pennsylvania Tennessee Texas Utah Vermont Virginia Washington Wisconsin Wyoming").split()} | {
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina", "north dakota", "rhode island",
    "south carolina", "south dakota", "west virginia", "district of columbia"}

def on_api_tab():
    """fetch() runs same-origin from a logged-out api.gbif.org tab (a JSON page). Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/v1/occurrence/search?limit=0")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"count"' not in body:
        raise RuntimeError(f"api.gbif.org did not serve occurrence/search (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { window.__g[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def get(path, params=(), timeout=60):
    """GET SITE+path?params from inside the tab -> parsed JSON. params is a list of (key, value) pairs because GBIF
    filters repeat (license=A&license=B means A OR B). Waits 60 s once on 429/5xx/network error, raises on anything else."""
    url = SITE + path + ("?" + urllib.parse.urlencode(list(params)) if params else "")
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)  # 429 = server under load: back off, or use the download API for big jobs
            continue
        if r["status"] != 200 or "json" not in (r["type"] or ""):
            raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
        return json.loads(r["text"])

def search(taxon, *extra, facets=(), facet_limit=1000):
    """occurrence/search with limit=0: only the count and the facets. Unknown or misspelt parameters are ignored
    silently (contry=US counts the whole world), so every filter used here is checked against a facet."""
    p = [("taxonKey", taxon), ("country", COUNTRY), ("limit", 0), *extra]
    p += [("facet", f) for f in facets] + ([("facetLimit", facet_limit)] if facets else [])
    d = get("/v1/occurrence/search", p)
    out = {f["field"]: {c["name"]: c["count"] for c in f["counts"]} for f in d.get("facets", [])}
    for f, counts in out.items():
        if len(counts) >= facet_limit:
            raise RuntimeError(f"facet {f} hit facetLimit={facet_limit}: raise it, the list is cut")
    return d["count"], out

on_api_tab()
now = datetime.now(timezone.utc)

# 1. Name -> taxon key. Synonyms carry the accepted key separately; searching the synonym key misses most records.
m = get("/v1/species/match", [("name", NAME)])
if m.get("matchType") not in ("EXACT", "FUZZY") or "usageKey" not in m:
    raise RuntimeError(f"{NAME!r}: matchType {m.get('matchType')}; give a scientific name, not a common name")
taxon = m.get("acceptedUsageKey", m["usageKey"])
print(f"{NAME!r} -> {m['scientificName']} ({m['rank']}, {m['status']}, {m['matchType']}, confidence {m['confidence']}), taxonKey {taxon}")

# 2. Every US record, split by licence. The facet proves the licence values and shows what the filter drops.
total, f = search(taxon, facets=["LICENSE"])
lic = f["LICENSE"]
if total == 0 or sum(lic.values()) != total:
    raise RuntimeError(f"licence facet ({sum(lic.values())}) does not add up to the count ({total}): stop")
print(f"\nAll GBIF records of taxonKey {taxon} in {COUNTRY}: {total:,}")
for k, v in sorted(lic.items(), key=lambda x: -x[1]):
    print(f"  {k:<13} {v:>6,}  {'kept' if k in OPEN else 'DROPPED (not openly licensed)'}")

# 3. Openly licensed, present records (occurrenceStatus=PRESENT drops absence records).
lic_p = [("license", x) for x in OPEN]
n_open, fs = search(taxon, *lic_p, facets=["OCCURRENCE_STATUS"])
if n_open != sum(lic.get(x, 0) for x in OPEN):
    raise RuntimeError(f"license filter returned {n_open}, the facet says {sum(lic.get(x, 0) for x in OPEN)}: stop")
n, f = search(taxon, *lic_p, ("occurrenceStatus", "PRESENT"), facets=["BASIS_OF_RECORD", "STATE_PROVINCE", "DATASET_KEY"])
print(f"\nOpenly licensed ({' + '.join(OPEN)}): {n_open:,}, occurrenceStatus {fs['OCCURRENCE_STATUS']}")
print(f"  {n_open - n} absence record(s) dropped -> {n:,} records")
basis = f["BASIS_OF_RECORD"]
print("  by basisOfRecord: " + ", ".join(f"{k} {v:,}" for k, v in sorted(basis.items(), key=lambda x: -x[1])))
n_sight = sum(basis.get(x, 0) for x in SIGHTINGS)
print(f"  sightings ({' + '.join(SIGHTINGS)}): {n_sight:,}; specimens, samples and fossils: {n - n_sight:,}")

def by_state(counts, n):
    """stateProvince is free text from each publisher: merge case and '(State)' variants, flag non-state values."""
    merged, spell = {}, {}
    for name, c in counts.items():
        k = re.sub(r"\s*\(state\)$", "", name.strip(), flags=re.I).lower()
        merged[k] = merged.get(k, 0) + c
        spell.setdefault(k, []).append(name)
    odd = {k: v for k, v in merged.items() if k not in US_STATES}
    rows = sorted(((max(spell[k], key=counts.get), v, spell[k]) for k, v in merged.items() if k in US_STATES), key=lambda x: -x[1])
    return rows, odd, n - sum(counts.values())

rows, odd, blank = by_state(f["STATE_PROVINCE"], n)
print(f"\nAll {n:,} openly licensed records: {len(rows)} states, {blank:,} with no stateProvince")
for name, c, sp in rows:
    print(f"  {name:<16} {c:>5,}" + (f"   (merged {sp})" if len(sp) > 1 else ""))
if odd:
    print(f"  not a US state name: {odd}")

# 4. Sightings only, and how concentrated the top states are (records, not individual animals).
n2, f2 = search(taxon, *lic_p, ("occurrenceStatus", "PRESENT"), *[("basisOfRecord", b) for b in SIGHTINGS], facets=["STATE_PROVINCE"])
if n2 != n_sight:
    raise RuntimeError(f"basisOfRecord filter gave {n2}, the facet says {n_sight}: stop")
rows2, odd2, blank2 = by_state(f2["STATE_PROVINCE"], n2)
print(f"\nSightings only ({n2:,}): {len(rows2)} states, {blank2:,} with no stateProvince")
for name, c, sp in rows2[:3]:
    _, f3 = search(taxon, *lic_p, ("occurrenceStatus", "PRESENT"), *[("basisOfRecord", b) for b in SIGHTINGS],
                   *[("stateProvince", s) for s in sp], facets=["RECORDED_BY"], facet_limit=1000)
    who = f3.get("RECORDED_BY", {})
    top = max(who.values()) if who else 0
    print(f"  {name:<16} {c:>5,}   {len(who)} named recorder(s); the busiest one made {top:,} ({top / c:.1%})")
print("  " + ", ".join(f"{name} {c:,}" for name, c, _ in rows2[3:]))
if odd2:
    print(f"  not a US state name: {odd2}")

# 5. Who published the records: needed for the attribution the data user agreement requires.
def cc(url):
    m = re.search(r"(publicdomain/zero|licenses/by-nc|licenses/by)/(\d\.\d)", url or "")
    return {"publicdomain/zero": "CC0", "licenses/by-nc": "CC BY-NC", "licenses/by": "CC BY"}[m[1]] + " " + m[2] if m else url

ds = f["DATASET_KEY"]
print(f"\nPublishers: {len(ds)} datasets; top 5 by records")
for key, c in sorted(ds.items(), key=lambda x: -x[1])[:5]:
    d = get(f"/v1/dataset/{key}")
    org = get(f"/v1/organization/{d['publishingOrganizationKey']}")
    # The filter works on each record's own licence; a dataset's licence can be stricter (iNaturalist: dataset CC BY-NC,
    # each observation keeps the observer's licence). Prove the records counted here are open.
    _, fl = search(taxon, *lic_p, ("occurrenceStatus", "PRESENT"), ("datasetKey", key), facets=["LICENSE"])
    if set(fl["LICENSE"]) - set(OPEN):
        raise RuntimeError(f"dataset {key}: record licences {fl['LICENSE']} include a non-open one: stop")
    rec = ", ".join(f"{k} {v:,}" for k, v in fl["LICENSE"].items())
    print(f"  {c:>5,}  {d['title']} | {org['title']} | https://doi.org/{d['doi']}")
    print(f"         dataset licence {cc(d['license'])}; record licences of these {c:,}: {rec}")

print(f"\nSource: GBIF.org occurrence search API, accessed {now:%d %B %Y %H:%M} UTC; records published by {len(ds)} datasets (top 5 above) "
      "(CC0 1.0 or CC BY 4.0, cite each publisher; for a publication, cite a GBIF derived dataset DOI).")
```

Output (from the run on 2026-11-13, 23:37 UTC):

```text
'Puma concolor' -> Puma concolor (Linnaeus, 1771) (SPECIES, ACCEPTED, EXACT, confidence 99), taxonKey 2435099

All GBIF records of taxonKey 2435099 in US: 11,916
  CC_BY_NC_4_0   6,899  DROPPED (not openly licensed)
  CC0_1_0        3,462  kept
  CC_BY_4_0      1,555  kept

Openly licensed (CC0_1_0 + CC_BY_4_0): 5,017, occurrenceStatus {'DETECTED': 5016, 'NOT_DETECTED': 1}
  1 absence record(s) dropped -> 5,016 records
  by basisOfRecord: PRESERVED_SPECIMEN 3,125, HUMAN_OBSERVATION 1,485, MATERIAL_SAMPLE 191, FOSSIL_SPECIMEN 176, MACHINE_OBSERVATION 39
  sightings (HUMAN_OBSERVATION + MACHINE_OBSERVATION): 1,524; specimens, samples and fossils: 3,492

All 5,016 openly licensed records: 34 states, 65 with no stateProvince
  Nebraska           932
  New Mexico         844   (merged ['New Mexico', 'New mexico'])
  California         792
  Idaho              454
  Texas              290
  Arizona            260
  Utah               257
  Florida            191
  Colorado           190   (merged ['Colorado', 'Colorado (State)'])
  Oregon             186
  Washington         157
  Montana            109
  Nevada              97
  South Dakota        78
  Wyoming             36
  New York            30
  Illinois             8
  Louisiana            7
  Kansas               5
  Minnesota            5
  Connecticut          4
  Pennsylvania         4
  Michigan             2
  Ohio                 2
  West Virginia        2
  Alabama              1
  Arkansas             1
  Georgia              1
  Hawaii               1
  Maryland             1
  North Carolina       1
  Tennessee            1
  Virginia             1
  Wisconsin            1

Sightings only (1,524): 18 states, 3 with no stateProvince
  Nebraska           919   2 named recorder(s); the busiest one made 918 (99.9%)
  California         352   106 named recorder(s); the busiest one made 91 (25.9%)
  Montana             55   9 named recorder(s); the busiest one made 36 (65.5%)
  Colorado 34, Arizona 29, New York 21, Washington 20, Florida 15, New Mexico 14, Utah 14, Oregon 13, Idaho 11, Texas 9, Nevada 6, Wyoming 4, South Dakota 3, Connecticut 1, Ohio 1

Publishers: 82 datasets; top 5 by records
  1,464  iNaturalist Research-grade Observations | iNaturalist.org | https://doi.org/10.15468/ab3s5x
         dataset licence CC BY-NC 4.0; record licences of these 1,464: CC_BY_4_0 1,323, CC0_1_0 141
  1,134  MSB Mammal Collection (Arctos) | Museum of Southwestern Biology | https://doi.org/10.15468/oirgxw
         dataset licence CC0 1.0; record licences of these 1,134: CC0_1_0 1,134
    697  NMNH Extant Specimen Records (USNM, US) | National Museum of Natural History, Smithsonian Institution | https://doi.org/10.15468/hnhrg3
         dataset licence CC0 1.0; record licences of these 697: CC0_1_0 697
    188  NMNH Material Samples (USNM) | National Museum of Natural History, Smithsonian Institution | https://doi.org/10.15468/jb9tdf
         dataset licence CC0 1.0; record licences of these 188: CC0_1_0 188
    167  MVZ Mammal Collection (Arctos) | Museum of Vertebrate Zoology | https://doi.org/10.15468/uwudf9
         dataset licence CC0 1.0; record licences of these 167: CC0_1_0 167

Source: GBIF.org occurrence search API, accessed 13 November 2026 23:37 UTC; records published by 82 datasets (top 5 above) (CC0 1.0 or CC BY 4.0, cite each publisher; for a publication, cite a GBIF derived dataset DOI).
```

### 2. robots.txt, name matching and silent failures (browser)

2 page loads and 14 in-page `fetch()` calls in the same tab.

```python
import json, time, urllib.parse

SITE = "https://api.gbif.org"
US = "taxonKey=2435099&country=US&limit=0"
OPEN = US + "&license=CC0_1_0&license=CC_BY_4_0&occurrenceStatus=PRESENT"

START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit'}).then(async r => { window.__g[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def raw(path):
    """One in-page GET -> (status, body text). No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r["status"], r["text"]

def brief(text):
    try:
        d = json.loads(text)
    except ValueError:
        return " ".join(text.split())[:100]
    if "count" in d:
        out = f"count {d['count']:,}" + (f", limit {d['limit']}, {len(d['results'])} results" if d["results"] else "")
        for f in d.get("facets", []):
            out += f", {f['field']} facet: {len(f['counts'])} values"
        return out
    keys = ("matchType", "usageKey", "acceptedUsageKey", "scientificName", "status")
    return json.dumps({k: d[k] for k in keys if k in d})

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(SITE + "/v1/occurrence/search?limit=0")
    wait_for_load()

goto_url(SITE + "/robots.txt")
wait_for_load()
st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
txt = js("document.body.innerText")
print(f"robots.txt HTTP {st}:")
print("\n".join("  " + l for l in txt.strip().splitlines() if l.strip() and not l.startswith("#")))
goto_url(SITE + "/v1/occurrence/search?limit=0")  # back to a JSON page for same-origin fetch()
wait_for_load()
print()

for label, path in (
    ("name 'mountain lion'                ", "/v1/species/match?name=mountain%20lion"),
    ("name 'Puma concolar' (typo)         ", "/v1/species/match?name=Puma%20concolar"),
    ("name 'Felis concolor' (old name)    ", "/v1/species/match?name=Felis%20concolor"),
    ("US, synonym key 2435104             ", "/v1/occurrence/search?taxonKey=2435104&country=US&limit=0"),
    ("US, accepted key 2435099            ", "/v1/occurrence/search?" + US),
    ("typo contry=US                      ", "/v1/occurrence/search?taxonKey=2435099&contry=US&limit=0"),
    ("taxonKey=abc                        ", "/v1/occurrence/search?taxonKey=abc&limit=0"),
    ("license=CC_BY_NC (not an enum)      ", "/v1/occurrence/search?" + US + "&license=CC_BY_NC"),
    ("open, facet stateProvince, default  ", "/v1/occurrence/search?" + OPEN + "&facet=stateProvince"),
    ("open, facetLimit=1000               ", "/v1/occurrence/search?" + OPEN + "&facet=stateProvince&facetLimit=1000"),
    ("open, stateProvince=Nebraska        ", "/v1/occurrence/search?" + OPEN + "&stateProvince=Nebraska"),
    ("open, stateProvince=nebraska        ", "/v1/occurrence/search?" + OPEN + "&stateProvince=nebraska"),
    ("open, hasCoordinate=false           ", "/v1/occurrence/search?" + OPEN + "&hasCoordinate=false"),
    ("US, limit=301                       ", "/v1/occurrence/search?taxonKey=2435099&country=US&limit=301"),
):
    s, body = raw(path)
    print(f"{label} HTTP {s} {brief(body)}")
```

Output (from the run on 2026-11-13, 23:36 UTC):

```text
robots.txt HTTP 200:
  User-agent: *
  Disallow: /v1/image/unsafe
  User-agent: Discordbot
  User-agent: LinkedInBot
  User-agent: Pinterestbot
  User-agent: Slackbot
  User-agent: Snapchat
  User-agent: TelegramBot
  User-agent: Twitterbot
  User-agent: WhatsApp
  User-agent: facebookexternalhit
  Disallow:

name 'mountain lion'                 HTTP 200 {"matchType": "NONE"}
name 'Puma concolar' (typo)          HTTP 200 {"matchType": "FUZZY", "usageKey": 2435099, "scientificName": "Puma concolor (Linnaeus, 1771)", "status": "ACCEPTED"}
name 'Felis concolor' (old name)     HTTP 200 {"matchType": "EXACT", "usageKey": 2435104, "acceptedUsageKey": 2435099, "scientificName": "Felis concolor Linnaeus, 1771", "status": "SYNONYM"}
US, synonym key 2435104              HTTP 200 count 88
US, accepted key 2435099             HTTP 200 count 11,916
typo contry=US                       HTTP 200 count 32,198
taxonKey=abc                         HTTP 200 count 0
license=CC_BY_NC (not an enum)       HTTP 400 Cannot parse CC_BY_NC into a known License
open, facet stateProvince, default   HTTP 200 count 5,016, STATE_PROVINCE facet: 10 values
open, facetLimit=1000                HTTP 200 count 5,016, STATE_PROVINCE facet: 36 values
open, stateProvince=Nebraska         HTTP 200 count 932
open, stateProvince=nebraska         HTTP 200 count 0
open, hasCoordinate=false            HTTP 200 count 2,115
US, limit=301                        HTTP 200 count 11,916, limit 300, 300 results
```

### 3. Same count with Python urllib, plus a coordinate cross-check (no browser)

GBIF also assigns each record with coordinates to a GADM state (`gadmLevel1Gid`), independent of the publisher's free-text `stateProvince`. Python's default `urllib` works; the API docs ask apps to put "a URL or email address" in the User-Agent, so set `GBIF_USER_AGENT`.

```python
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

API = "https://api.gbif.org/v1"
# techdocs: apps should send a User-Agent with "a URL or email address" so GBIF can contact them; set yours here.
UA = os.environ.get("GBIF_USER_AGENT", "gbif-skill-example/1.0")
OPEN = [("license", "CC0_1_0"), ("license", "CC_BY_4_0"), ("occurrenceStatus", "PRESENT")]

def get(path, params=()):
    url = f"{API}{path}" + ("?" + urllib.parse.urlencode(list(params)) if params else "")
    for attempt in range(2):
        time.sleep(1.0)  # no published rate; 429 under load
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"HTTP {e.code} {url}: {e.read().decode()[:200]}")

def facet(params, field):
    d = get("/occurrence/search", [*params, ("limit", 0), ("facet", field), ("facetLimit", 1000)])
    counts = {c["name"]: c["count"] for c in d["facets"][0]["counts"]} if d["facets"] else {}
    if len(counts) >= 1000:
        sys.exit(f"{field}: facetLimit reached")
    return d["count"], counts

m = get("/species/match", [("name", "Puma concolor")])
if m.get("matchType") not in ("EXACT", "FUZZY"):
    sys.exit(f"no match: {m}")
taxon = m.get("acceptedUsageKey", m["usageKey"])
base = [("taxonKey", taxon), ("country", "US"), *OPEN]

n, states = facet(base, "stateProvince")
merged = {}
for k, v in states.items():
    k = re.sub(r"\s*\(state\)$", "", k.strip(), flags=re.I).title()
    merged[k] = merged.get(k, 0) + v
top = sorted(merged.items(), key=lambda x: -x[1])
print(f"taxonKey {taxon}: {n:,} openly licensed US records in {len(merged)} stateProvince values "
      f"({n - sum(states.values()):,} blank); top 5: " + ", ".join(f"{k} {v:,}" for k, v in top[:5]))

# Cross-check: GBIF also places each record with coordinates in a GADM state (gadmLevel1Gid), independent of the
# publisher's free-text stateProvince. Records without coordinates have no GADM state.
nc, gadm = facet([*base, ("hasCoordinate", "true")], "gadmLevel1Gid")
print(f"\nGADM state from coordinates ({nc:,} records with coordinates; {n - nc:,} without):")
for gid, c in sorted(gadm.items(), key=lambda x: -x[1])[:5]:
    name = get(f"/geocode/gadm/{gid}")["name"]
    print(f"  {gid:<9} {name:<12} {c:>4,} by coordinates   {merged.get(name, 0):>4,} by stateProvince")
```

Output (from the run on 2026-11-13, 23:36 UTC):

```text
taxonKey 2435099: 5,016 openly licensed US records in 34 stateProvince values (65 blank); top 5: Nebraska 932, New Mexico 844, California 792, Idaho 454, Texas 290

GADM state from coordinates (2,901 records with coordinates; 2,115 without):
  USA.28_1  Nebraska      920 by coordinates    932 by stateProvince
  USA.32_1  New Mexico    592 by coordinates    844 by stateProvince
  USA.5_1   California    557 by coordinates    792 by stateProvince
  USA.45_1  Utah          140 by coordinates    257 by stateProvince
  USA.6_1   Colorado      137 by coordinates    190 by stateProvince
```

### 4. curl, headers and the licence enum

```bash
S=https://api.gbif.org/v1/occurrence/search
Q='taxonKey=2435099&country=US&license=CC0_1_0&license=CC_BY_4_0&occurrenceStatus=PRESENT&limit=0'
# open records, top states (facetLimit default is 10; ask for more)
curl -sS --fail "$S?$Q&facet=stateProvince&facetLimit=100" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); c=d["facets"][0]["counts"]; print("open US records:", d["count"], "| states:", len(c), "| top 3:", [(x["name"], x["count"]) for x in c[:3]])'
sleep 1
# what the licence filter drops
curl -sS --fail "$S?taxonKey=2435099&country=US&limit=0&facet=license" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("all US records:", d["count"], {x["name"]: x["count"] for x in d["facets"][0]["counts"]})'
sleep 1
# caching and CORS headers
curl -sS -D - -o /dev/null -H 'Origin: https://example.org' "$S?$Q" | grep -iE '^(cache-control|access-control-allow-origin|content-type):'
sleep 1
curl -sS -o /dev/null -w 'license=CC_BY_NC: HTTP %{http_code}\n' "$S?taxonKey=2435099&license=CC_BY_NC&limit=0"
```

Output (from the run on 2026-11-13, 23:37 UTC):

```text
open US records: 5016 | states: 36 | top 3: [('Nebraska', 932), ('New Mexico', 843), ('California', 792)]
all US records: 11916 {'CC_BY_NC_4_0': 6899, 'CC0_1_0': 3462, 'CC_BY_4_0': 1555}
access-control-allow-origin: *
content-type: application/json
cache-control: public, max-age=600
license=CC_BY_NC: HTTP 400
```

## Fields (occurrence/search)

| Field / parameter | Notes |
|---|---|
| `count` | matching records; with `limit=0` the call returns only this and `facets` |
| `taxonKey` | backbone key from `/v1/species/match`; the docs: "All included (child) and synonym taxa are included in the search". For a synonym name use its `acceptedUsageKey` |
| `country` | ISO 3166-1 alpha-2 (`US`), as GBIF interprets the record |
| `license` | record licence: `CC0_1_0`, `CC_BY_4_0`, `CC_BY_NC_4_0` (the enum also has `UNSPECIFIED` and `UNSUPPORTED`, 0 US records here). Repeat the parameter for OR. A value outside the enum (`CC_BY_NC`) is HTTP 400 `Cannot parse ... into a known License` |
| `occurrenceStatus` | filter `PRESENT`/`ABSENT`; the facet labels them `DETECTED`/`NOT_DETECTED` |
| `basisOfRecord` | values in these records: `HUMAN_OBSERVATION`, `MACHINE_OBSERVATION` (sightings, camera traps), `PRESERVED_SPECIMEN`, `MATERIAL_SAMPLE`, `FOSSIL_SPECIMEN`; the enum also has `LIVING_SPECIMEN`, `OBSERVATION`, `LITERATURE`, `MATERIAL_CITATION`, `OCCURRENCE`, `UNKNOWN` |
| `stateProvince` | free text from the publisher; the filter is exact and case-sensitive (`nebraska` = 0) |
| `gadmLevel1Gid` | state derived from coordinates (`USA.28_1` = Nebraska via `/v1/geocode/gadm/USA.28_1`); only for records with coordinates |
| `datasetKey` | the publishing dataset; `/v1/dataset/<key>` gives `title`, `doi`, `license`, `publishingOrganizationKey` |
| `recordedBy` | observer or collector name (facet it; block 1 prints only counts, not names) |
| `facet`, `facetLimit` | repeat `facet` for several fields in one call; `facetLimit` applies to each and defaults to 10 |
| `coordinateUncertaintyInMeters`, `informationWithheld` | sensitive or observer-requested blurring, e.g. "Coordinate uncertainty increased to 27754m at the request of the observer" |

## Gotchas

- **Answer with the licence split.** "How many sightings" has three honest numbers: all records (11,916), openly licensed records (5,016), openly licensed observations (1,524). Quote the one that matches the question and name the filter.
- **Dataset licence is not record licence.** `/v1/dataset/50c9509d-...` (iNaturalist Research-grade Observations) says CC BY-NC 4.0, while the records the `license` filter keeps say CC BY 4.0 or CC0 in their own `license` field. The filter uses the record field. If you reuse records, keep each record's `license` and `datasetKey`; the agreement requires keeping the ownership identifier.
- **Unknown parameters are ignored.** `contry=US` returned 32,198 (every country). `taxonKey=abc` returned HTTP 200, count 0. Check each filter against a facet, as block 1 does.
- **Scientific names only.** `mountain lion` gives `matchType` `NONE`. `Puma concolar` is a `FUZZY` match to 2435099. `Felis concolor` is a `SYNONYM` (`usageKey` 2435104, `acceptedUsageKey` 2435099); searching 2435104 finds 88 US records against 11,916 for 2435099.
- **`facetLimit` defaults to 10.** The default `stateProvince` facet covered 4,394 of 5,016 records; `facetLimit=1000` gave all 36 values.
- **State names are free text.** "New mexico" and "Colorado (State)" are separate facet values; block 1 merges case and "(State)" variants and flags anything that is not a US state name. 2,115 of the 5,016 records have no coordinates, so the GADM state covers only 2,901; the two methods disagree (New Mexico 844 by `stateProvince`, 592 by coordinates).
- **Single-observer skew.** Nebraska ranks first because one observer posted 918 observations. Single-record states outside the usual range (Hawaii has 1 record) need a record-by-record look before quoting them.
- **Paging.** `limit` above 300 is silently cut to 300 (`limit=301` returned 300 results). The occurrence docs: "a hard limit for any query of 100,000 records. You will get an error if the offset + limit exceeds 100,000"; use the download API (needs a GBIF.org account) beyond that. This task needs no paging.
- **Species API is marked deprecated.** The API docs list "Species API (Deprecated)" and `GET /v1/species/match` as "Legacy fuzzy name match service (Version 1 - flat format)". It worked on 2026-11-13; `GET /v2/species/match?scientificName=Puma%20concolor` returned the same key as `usage.key` "2435099" (a string).
- **Cached answers.** Responses carry `cache-control: public, max-age=600`, and records are re-crawled from publishers (a sampled iNaturalist record showed `lastCrawled` 2026-11-11, `lastParsed` 2026-11-12), so re-run before quoting a count.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **www.gbif.org pages** (`/occurrence/search`, `/species/...`): disallowed in its robots.txt for `*` and "not part of the public API"; curl got a Cloudflare challenge. Use api.gbif.org.
- **`/v1/image/unsafe`**: disallowed in api.gbif.org robots.txt; not used.
- **Common names in `species/match`**: `matchType` `NONE`.
- **Not tested:** the download API (needs an account) and derived-dataset DOIs, `/v2/species/match` beyond one call, rate-limit behaviour (never provoked), CC BY-NC records (excluded on purpose).
