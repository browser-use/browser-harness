# nobelprize.org API - Who Won a Nobel Prize, the Motivation and the Prize Amount (official API v2.1)

Field-tested against api.nobelprize.org on 2026-11-09 using a Browser Use cloud browser (logged out) plus plain HTTP (curl, Python urllib). About 12 browser requests (page loads and in-page `fetch()`) and 25 plain HTTP calls to api.nobelprize.org, all serial at 1 s or more spacing: every answer was HTTP 200, no 429, no challenge, no key, no login.

robots.txt (checked 2026-11-09, curl and the cloud browser): api.nobelprize.org/robots.txt is HTTP 200 `text/html`, a Slim framework placeholder page ("Hello robots.txt!") with 0 directives; www.nobelprize.org/robots.txt has only `User-agent: *` / `Disallow: /wp-admin/` / `Allow: /wp-admin/admin-ajax.php`. No named AI-agent groups on either host. Terms: the API terms (https://www.nobelprize.org/about/terms-of-use-for-api-nobelprize-org-and-data-nobelprize-org/) say "The Services are free to use according to the Creative Commons Zero (CC0) license. In case of conflicting terms or other inconsistencies, these Terms shall prevail", "There is no obligation to register in order to use the API", "Applications shall be constructed in a manner which minimizes the capacity burden of the API. Consider using a local cache", data should not be altered or censored, and apps "may not use Nobel Prize Outreach's name, logos, or other trademarks in their titles or logos, or in any way that implies endorsement" (citing the API as the data source is encouraged). No AI, ML, scraping or bot clause. The www.nobelprize.org site terms (https://www.nobelprize.org/about/terms-of-use/) cover the site's own Content (articles, photos) and require written permission for commercial use; this skill fetches only the API, which the API terms put under CC0, and those site terms also have no AI or scraping clause. This skill is not affiliated with or endorsed by Nobel Prize Outreach.

## Quick summary

- **No scraping.** Official, keyless JSON API, `Access-Control-Allow-Origin: *`, `cache-control: public, max-age=60`:
  - `GET https://api.nobelprize.org/2.1/nobelPrizes?nobelPrizeYear=2025&nobelPrizeCategory=phy` - the prize: `dateAwarded`, `prizeAmount`, laureates with `portion` and `motivation`.
  - `GET https://api.nobelprize.org/2.1/laureates?nobelPrizeYear=2025&nobelPrizeCategory=phy` - the same laureates as full records (birth, affiliation at the time of the award, Wikidata ID) in one call.
  - Also `/2.1/nobelPrize/<cat>/<year>`, `/2.1/laureate/<id>`, `/2.1/laureates?name=Curie`. Docs: https://www.nobelprize.org/about/developer-zone-2/ ; OpenAPI spec JSON: https://api.swaggerhub.com/apis/NobelMedia/NobelMasterData/2.1
- **Category codes are lowercase:** `phy`, `che`, `med`, `lit`, `pea`, `eco`. Anything else (`physics`, `Phy`) is dropped without an error and you get every category of that year (block 2, part 4). Check that `meta` echoes the filter, as the blocks do.
- **Amounts are SEK per full prize.** The API has no currency field; nobelprize.org's prize money page (https://www.nobelprize.org/prizes/about/the-nobel-prize-money/) gives the amounts in Swedish kronor. 2025: 11,000,000. 2026: 12,000,000.
- **"Latest" is not 2025 any more.** The 2026 prizes are in the API (Physics 2026-10-06, Francis Halzen). Pass the year you mean, or ask for `sort=desc&limit=1` (block 1, part 3).
- **Keep load low.** The terms ask apps to minimize API load and suggest a local cache; responses are cached 60 s. Two calls answer the whole task.
- **Browser or plain HTTP.** Block 1 opens a small API URL so `fetch()` is same-origin; blocks 2 and 3 need no browser.

## What works

### 1. Who won, the motivation, the prize amount, plus each laureate's affiliation (browser)

Self-contained. 1 page load + 3 calls. `get_json()` returns parsed JSON on 200, backs off on 429/5xx and otherwise raises, so a failure never looks like "no prize". `checked()` raises when the API ignored a filter.

```python
import json, time

YEAR, CATEGORY = 2025, "phy"  # category codes: phy, che, med, lit, pea, eco (lowercase; anything else is ignored, see Gotchas)

API = "https://api.nobelprize.org/2.1/"
PAUSE = 1.0  # no published rate limit; the terms ask apps to minimize load, so keep calls serial and few

def on_api_tab():
    """fetch() runs from a logged-out tab on api.nobelprize.org (a small API URL), so every call is same-origin. Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://api.nobelprize.org":
            return
    except Exception:
        pass
    new_tab(API + "nobelPrizes?limit=1")
    wait_for_load()
    if js("location.origin") != "https://api.nobelprize.org" or "json" not in (js("document.contentType") or ""):
        raise RuntimeError(f"tab landed on {js('location.href')} ({js('document.contentType')}): stop, do not retry around it")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__np = window.__np || {}; const id = String(Math.random()).slice(2); window.__np[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__np[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__np[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__np[%s]; if (v) delete window.__np[%s]; return v; })()"""

def get_json(url, tries=3, timeout=60):
    """GET url from inside the tab -> parsed JSON. Backs off 30 s on 429/5xx, raises on anything else, so a failure never looks like "no prize"."""
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] == 200 and "json" in (r["type"] or ""):
            return json.loads(r["text"])
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:200]!r}; stopping")
        time.sleep(30)

def checked(d, **want):
    """The API silently drops a parameter it does not understand (e.g. category 'physics' or 'Phy') and returns everything.
    meta echoes only the parameters it applied, so compare."""
    for k, v in want.items():
        if str(d["meta"].get(k)) != str(v):
            raise ValueError(f"API ignored {k}={v!r} (meta: {d['meta']}); use a lowercase code: phy che med lit pea eco")
    return d

name = lambda x: (x.get("knownName") or x.get("orgName") or {}).get("en")

on_api_tab()
# 1. The prize: date, amount, laureates, share, motivation
d = checked(get_json(API + f"nobelPrizes?nobelPrizeYear={YEAR}&nobelPrizeCategory={CATEGORY}"), nobelPrizeYear=YEAR, nobelPrizeCategory=CATEGORY)
assert d["meta"]["count"] == 1, d["meta"]
p = d["nobelPrizes"][0]
print(f"{p['categoryFullName']['en']} {p['awardYear']} | announced {p.get('dateAwarded')} | prize amount {p['prizeAmount']:,} SEK "
      f"(adjusted {p['prizeAmountAdjusted']:,}) | {len(p.get('laureates', []))} laureates")
if "topMotivation" in p:
    print("top motivation:", p["topMotivation"]["en"])
for l in p.get("laureates", []):
    print(f"  {l['sortOrder']}. {name(l)} (id {l['id']}) share {l['portion']}")
motivations = sorted({l["motivation"]["en"] for l in p.get("laureates", [])})
print("motivation:" if len(motivations) == 1 else "motivations:", *[f'"{m}"' for m in motivations])

# 2. One call for all laureates' full records: affiliation at the time of the award, birth
d = checked(get_json(API + f"laureates?nobelPrizeYear={YEAR}&nobelPrizeCategory={CATEGORY}"), nobelPrizeYear=YEAR, nobelPrizeCategory=CATEGORY)
print(f"\nlaureates endpoint, same filter: count {d['meta']['count']}")
for l in d["laureates"]:
    prize = next(x for x in l["nobelPrizes"] if x["awardYear"] == str(YEAR) and x["category"]["en"] == p["category"]["en"])
    aff = "; ".join(f"{a['name']['en']}, {a.get('city', {}).get('en', '?')}, {a.get('country', {}).get('en', '?')}" for a in prize.get("affiliations", []))
    born = l.get("birth", {})
    when = born.get("date", "?").replace("-00-00", "")  # only the year is known for many recent laureates: "1942-00-00"
    where = born.get("place", {}).get("locationString", {}).get("en", "place not listed")
    print(f"  {name(l)}: born {when}, {where} | {prize['prizeStatus']} | {aff}")
    print(f"     wikidata {l.get('wikidata', {}).get('id')} | {next((x['href'] for x in l['links'] if x['rel'] == 'external'), '')}")

# 3. Newest prize in the category, to see whether a later year is out
d = checked(get_json(API + f"nobelPrizes?nobelPrizeCategory={CATEGORY}&sort=desc&limit=1"), nobelPrizeCategory=CATEGORY)
n = d["nobelPrizes"][0]
print(f"\nnewest {n['category']['en']} prize in the API: {n['awardYear']} ({n.get('dateAwarded')}): {', '.join(name(l) for l in n.get('laureates', []))} "
      f"| {n['prizeAmount']:,} SEK | {d['meta']['count']} {n['category']['en']} prize years listed")
```

Output (from the run on 2026-11-09):

```text
The Nobel Prize in Physics 2025 | announced 2025-10-07 | prize amount 11,000,000 SEK (adjusted 11,000,000) | 3 laureates
  1. John Clarke (id 1050) share 1/3
  2. Michel H. Devoret (id 1051) share 1/3
  3. John M. Martinis (id 1052) share 1/3
motivation: "for the discovery of macroscopic quantum mechanical tunnelling and energy quantisation in an electric circuit"

laureates endpoint, same filter: count 3
  John Clarke: born 1942, Cambridge, United Kingdom | received | University of California, Berkeley, CA, USA
     wikidata Q555849 | https://www.nobelprize.org/laureate/1050
  John M. Martinis: born 1958, place not listed | received | University of California, Santa Barbara, CA, USA; Qolab, Los Angeles, CA, USA
     wikidata Q28976188 | https://www.nobelprize.org/laureate/1052
  Michel H. Devoret: born 1953, Paris, France | received | Yale University, New Haven, CT, USA; University of California, Santa Barbara, CA, USA; Google Quantum AI, Santa Barbara, CA, USA
     wikidata Q26703310 | https://www.nobelprize.org/laureate/1051

newest Physics prize in the API: 2026 (2026-10-06): Francis Halzen | 12,000,000 SEK | 126 Physics prize years listed
```

### 2. Search laureates by name, every prize of one year, a year with no prize (plain HTTP, no browser)

Python standard library only, truthful User-Agent, 5 calls at 1 s spacing.

```python
import json, time, urllib.error, urllib.parse, urllib.request

NAME = "Curie"  # part of a person's or organization's name
YEAR = 2025     # every prize of one year

UA = {"User-Agent": "browser-harness-skill/1.0 (Python urllib)"}
API = "https://api.nobelprize.org/2.1/"

def call(path, **params):
    """GET -> parsed JSON. Waits 30 s on 429/5xx, then stops. Serial, one call per second (the terms ask apps to keep load low)."""
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                status, body, ctype = r.status, r.read(), r.headers.get("content-type", "")
        except urllib.error.HTTPError as e:
            status, body, ctype = e.code, e.read(), e.headers.get("content-type", "")
        time.sleep(1)
        if status == 200 and "json" in ctype:
            return json.loads(body)
        if status not in (429, 500, 502, 503, 504) or attempt == 2:
            raise RuntimeError(f"{url}: HTTP {status} {ctype} {body[:200]!r}; stopping")
        time.sleep(30)

name = lambda x: (x.get("knownName") or x.get("orgName") or {}).get("en")

# 1. Laureates whose name matches, with every prize they won
d = call("laureates", name=NAME)
print(f"laureates matching {NAME!r}: {d['meta']['count']}")
for l in d["laureates"]:
    kind = "organization" if "orgName" in l else l.get("gender", "?")
    print(f"  {name(l)} (id {l['id']}, {kind}, wikidata {l.get('wikidata', {}).get('id')})")
    for p in l["nobelPrizes"]:
        aff = "; ".join(a["name"]["en"] for a in p.get("affiliations", []))
        print(f"     {p['awardYear']} {p['category']['en']:<10} share {p['portion']:<4} {p['prizeAmount']:>9,} SEK  {p['motivation']['en'][:90]}" + (f" | {aff}" if aff else ""))

# 2. Every prize in one year
d = call("nobelPrizes", nobelPrizeYear=YEAR)
print(f"\n{YEAR}: {d['meta']['count']} prizes")
for p in d["nobelPrizes"]:
    who = ", ".join(f"{name(l)} ({l['portion']})" for l in p.get("laureates", []))
    print(f"  {p.get('dateAwarded')} {p['category']['en']:<22} {p['prizeAmount']:,} SEK  {who}")

# 3. A year with no prize: no laureates, a topMotivation instead
d = call("nobelPrizes", nobelPrizeYear=1940, nobelPrizeCategory="phy")
p = d["nobelPrizes"][0]
print(f"\n1940 {p['category']['en']}: laureates {len(p.get('laureates', []))} | {p['topMotivation']['en']}")

# 4. Things that look like answers but are not
d = call("nobelPrizes", nobelPrizeYear=YEAR, nobelPrizeCategory="physics")  # not a category code
print(f"\ncategory 'physics': count {d['meta']['count']}, meta keeps nobelPrizeCategory? {'nobelPrizeCategory' in d['meta']} "
      f"-> first result is {d['nobelPrizes'][0]['category']['en']}")
d = call("laureate/99999")  # an ID that does not exist
print("laureate/99999:", "no record, only meta" if d and set(d[0]) == {"meta"} else d)
```

Output (from the run on 2026-11-09):

```text
laureates matching 'Curie': 3
  Irène Joliot-Curie (id 194, female, wikidata Q7504)
     1935 Chemistry  share 1/2    159,917 SEK  in recognition of their synthesis of new radioactive elements | Institut du Radium
  Marie Curie (id 6, female, wikidata Q7186)
     1903 Physics    share 1/4    141,358 SEK  in recognition of the extraordinary services they have rendered by their joint researches 
     1911 Chemistry  share 1      140,695 SEK  in recognition of her services to the advancement of chemistry by the discovery of the ele | Sorbonne University
  Pierre Curie (id 5, male, wikidata Q37463)
     1903 Physics    share 1/4    141,358 SEK  in recognition of the extraordinary services they have rendered by their joint researches  | École municipale de physique et de chimie industrielles (Municipal School of Industrial Physics and Chemistry)

2025: 6 prizes
  2025-10-08 Chemistry              11,000,000 SEK  Susumu Kitagawa (1/3), Richard Robson (1/3), Omar M. Yaghi (1/3)
  2025-10-13 Economic Sciences      11,000,000 SEK  Joel Mokyr (1/2), Philippe Aghion (1/4), Peter Howitt (1/4)
  2025-10-09 Literature             11,000,000 SEK  László Krasznahorkai (1)
  2025-10-10 Peace                  11,000,000 SEK  Maria Corina Machado (1)
  2025-10-07 Physics                11,000,000 SEK  John Clarke (1/3), Michel H. Devoret (1/3), John M. Martinis (1/3)
  2025-10-06 Physiology or Medicine 11,000,000 SEK  Mary E. Brunkow (1/3), Fred Ramsdell (1/3), Shimon Sakaguchi (1/3)

1940 Physics: laureates 0 | No Nobel Prize was awarded this year. 1/3 of the prize money was allocated to the main fund and 2/3 was allocated to the special fund of this prize section.

category 'physics': count 6, meta keeps nobelPrizeCategory? False -> first result is Chemistry
laureate/99999: no record, only meta
```

### 3. Same task with curl, and the CSV format

```bash
curl -sS --fail "https://api.nobelprize.org/2.1/nobelPrizes?nobelPrizeYear=2025&nobelPrizeCategory=phy" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["meta"].get("nobelPrizeCategory") == "phy", d["meta"]  # an unknown category is dropped silently
for p in d["nobelPrizes"]:
    print(p["categoryFullName"]["en"], p["awardYear"], "|", p["dateAwarded"], "|", format(p["prizeAmount"], ","), "SEK")
    for l in p["laureates"]:
        print(" ", l["knownName"]["en"], l["portion"], "|", l["motivation"]["en"])
'
sleep 1
curl -sS -o /dev/null -w 'csv: HTTP %{http_code} %{content_type}\n' "https://api.nobelprize.org/2.1/nobelPrizes?nobelPrizeYear=2025&nobelPrizeCategory=phy&format=csv"
sleep 1
curl -sS "https://api.nobelprize.org/2.1/nobelPrizes?nobelPrizeYear=2025&nobelPrizeCategory=phy&format=csv" | head -3
```

Output (from the run on 2026-11-09):

```text
The Nobel Prize in Physics 2025 | 2025-10-07 | 11,000,000 SEK
  John Clarke 1/3 | for the discovery of macroscopic quantum mechanical tunnelling and energy quantisation in an electric circuit
  Michel H. Devoret 1/3 | for the discovery of macroscopic quantum mechanical tunnelling and energy quantisation in an electric circuit
  John M. Martinis 1/3 | for the discovery of macroscopic quantum mechanical tunnelling and energy quantisation in an electric circuit
csv: HTTP 200 text/csv;charset=UTF-8
category,year,id,name,share,overallmotivation,motivation
Physics,2025,1050,"John Clarke",1/3,,"for the discovery of macroscopic quantum mechanical tunnelling and energy quantisation in an electric circuit",
Physics,2025,1051,"Michel H. Devoret",1/3,,"for the discovery of macroscopic quantum mechanical tunnelling and energy quantisation in an electric circuit",
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `awardYear`, `category.en`, `categoryFullName.en` | prize | year as a string (`"2025"`); `Physics`, `The Nobel Prize in Physics`; also `no`/`se` translations |
| `dateAwarded` | prize | announcement date, `2025-10-07`; absent for years with no prize |
| `prizeAmount` | prize | SEK for the full prize in that year; each laureate gets `portion` of it |
| `prizeAmountAdjusted` | prize | spec: "adjusted according to Index number yearly average"; 1940 Physics: 138,570 -> 4,464,201 |
| `topMotivation.en` | prize | only on some prizes, e.g. 1940 Physics "No Nobel Prize was awarded this year..." |
| `laureates[].id`, `knownName.en` / `orgName.en` | prize, laureate | persons have `knownName`, `givenName`, `familyName`, `gender`, `birth`; organizations have `orgName`, `founded` |
| `laureates[].portion`, `sortOrder`, `motivation.en` | prize | share `1`, `1/2`, `1/3`, `1/4`; motivation is per laureate and can differ (Economic Sciences 2025: 1/2, 1/4, 1/4) |
| `nobelPrizes[].affiliations[]` | laureate | `name`, `city`, `country` at the time of the award; can be several (Devoret: 3) or none |
| `nobelPrizes[].prizeStatus` | laureate | `received`, `declined`, `restricted` (spec enum) |
| `birth.date`, `birth.place.locationString.en` | laureate | `1942-00-00` when only the year is known; `place` can be missing (Martinis) |
| `wikidata.id`, `wikipedia.english`, `links[rel=external]` | laureate | `Q555849`; the laureate's page on www.nobelprize.org |
| `meta.count`, `meta.offset`, `meta.limit` | top level | `limit` defaults to 25; page with `offset`. `meta` echoes only the filters that were applied |

## Gotchas

- **Unknown filter values are ignored, not rejected.** `nobelPrizeCategory=physics` or `Phy` returns all six 2025 prizes, Chemistry first, HTTP 200. Read `meta.nobelPrizeCategory`, or check every returned `category`.
- **Unknown laureate ID is HTTP 200** with `[{"meta": {...}}]` and no record (`/2.1/laureate/99999`).
- **`links[].href` point at `/2/`** (`https://api.nobelprize.org/2/laureate/1050`), not `/2.1/`. Both answered 200; build `/2.1/` URLs from the `id` yourself.
- **Order differs by endpoint.** `nobelPrizes` lists laureates by `sortOrder` (Clarke, Devoret, Martinis); `laureates` sorts alphabetically by known name (Clarke, Martinis, Devoret). Years with several prizes come back alphabetical by category, not by date.
- **No-prize years are still listed.** 126 Physics entries for 1901-2026 include years like 1940 with no `laureates` and only `topMotivation`. Count laureates, not entries.
- **`yearTo` works without `nobelPrizeYear`** although the spec says it is required: `nobelPrizes?yearTo=2025` returned 688 prizes from 1901.
- **CSV has no amounts.** `format=csv` gives `category,year,id,name,share,overallmotivation,motivation` with a trailing comma on each row. Use JSON for amounts and affiliations.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; block 1 checks only origin and content type.

## What does not work

- **robots.txt on the API host** is a placeholder HTML page, not a robots file; there are no rules to read there.
- **Not tested:** `limit` maximum, rate limits (none documented, none hit), `/2.1/nobelPrize/<cat>/<year>` beyond one 200 call, the other laureate filters (`affiliation`, `birthCountry`, `deathDate`, ...), declined or restricted prizes.
