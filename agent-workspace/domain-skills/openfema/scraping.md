# OpenFEMA API (fema.gov) - List the FEMA Disaster Declarations for a US County or State, With the Incident Type and Which Assistance Programs Were Declared (REST API, no key)

Field-tested against www.fema.gov on 2026-11-17 (US Pacific afternoon; 23:31-23:46 UTC) using a fresh Browser Use cloud browser (logged out; one session) plus Python `urllib` and `curl` from a Linux machine. 6 browser page loads (the dataset page in 2 tabs, robots.txt, the OpenFEMA terms, the API documentation and the dataset page again) and 11 in-page `fetch()` calls, 35 urllib calls and 8 curl calls to www.fema.gov, all serial (exploration calls 2 s apart, the blocks below 15 s apart): every API call was HTTP 200 except the deliberate HTTP 400 probes below. `/robots.txt` answered HTTP 403 "Access Denied" to curl (2 calls) and urllib (2 calls), and the dataset page answered HTTP 403 to curl (1 call); the browser got HTTP 200 for both. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-17 in the cloud browser; curl and urllib get HTTP 403 for this file): https://www.fema.gov/robots.txt has two `User-agent: *` groups (Drupal's default `Disallow` list for `/core/`, `/profiles/`, `/admin/`, `/search/`, `/user/login` and similar, plus `Crawl-delay: 15`; and a second group disallowing translated-language folders such as `/es/` and `/fr/`), `User-agent: PetalBot` with `Disallow: /`, and `User-agent: Meta-ExternalAgent` with `Disallow: /`. Nothing disallows `/api/open/`, `/about/openfema/` or `/openfema-data-page/`, and there are no groups for GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot or Bytespider, so the `*` rules apply to them and allow the paths used here (blocks 2 and 3 check every agent). The blocks wait 15 s between requests to honour the crawl delay. Terms: the OpenFEMA Terms and Conditions (https://www.fema.gov/about/openfema/terms-conditions, "Last updated January 22, 2025", read in the cloud browser by block 2) say "you agree that the data will be used solely for statistical research or as a reporting record", "not to reidentify nor attempt to reidentify the individuals whose data is aggregated", "the data cannot be used to make determinations that might affect an individual's rights or eligibility for benefits", "Users should cite the specific API endpoint (including the version)" and "the date and preferably the time when the FEMA data are accessed", and that users "must clearly state" the notice below; "The logos and/or seals of FEMA and the Department of Homeland Security (DHS) may not be used without prior written authorization", and you "may not modify or falsely represent content accessed through FEMA's API and still claim the source is FEMA or FEMA.gov". The OpenFEMA API documentation (https://www.fema.gov/about/openfema/api, "Last updated November 13, 2026") says "Use of the API requires no registration", "authentication is not necessary", and recommends "a descriptive "user-agent" header (such as a custom application name and contact email)". No AI/ML, scraping, automated-access or non-commercial clause on either page. Naming: "OpenFEMA API" as plain text with the required notice; no FEMA or DHS logo or seal. This skill is not affiliated with or endorsed by FEMA.

**Required notice (print it with every answer, as blocks 1, 3 and 4 do):** "This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s)." Cite the endpoint with its version (`/api/open/v2/DisasterDeclarationsSummaries`, "Disaster Declarations Summaries - v2") and the access date and time.

**Use:** statistical research or a reporting record (the terms' words). Do not use the data to decide a person's rights or eligibility for benefits, and do not try to identify individuals.

## Quick summary

- **No scraping.** `GET https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?$filter=state eq 'TX' and designatedArea eq 'Harris (County)'&$orderby=declarationDate desc&$count=true` (URL-encode the spaces and quotes) returns every declaration that names that county, with `incidentType`, `declarationType` and the four program flags `ihProgramDeclared`, `iaProgramDeclared`, `paProgramDeclared`, `hmProgramDeclared`. JSON, or CSV with `$format=csv`. No key.
- **Answer (block 1, 23:44 UTC; block 4 at 00:51 on 2026-11-18 agrees):** **Harris (County), TX has 41 declarations**: 30 DR (major disaster), 10 EM (emergency), 1 FM (fire management). **Latest: DR-4798-TX, Hurricane Beryl, declared 2024-07-09, incident type Hurricane, IH and PA declared** (HM also declared; IA not). The same 41 come back by FIPS code (`fipsStateCode eq '48' and fipsCountyCode eq '201'`, block 3).
- **One row per designated area per disaster.** Texas has 5,453 rows but **392 declarations** (265 FM, 108 DR, 19 EM); DR-4485 COVID-19 Pandemic alone covers 257 Texas areas. Dedupe on `disasterNumber` for a state list (blocks 1 and 3).
- **Programs differ by area within one disaster.** DR-4935 (Texas floods, 2026-09-01) has 26 county rows: 17 with IH+PA, 3 (Bexar, Comal, Medina) with IH only, 6 with PA only. For a county read that county's row; for a state, the blocks OR the flags across areas and say so.
- **Silent zeros:** `designatedArea eq 'Harris County'` (no parentheses) and `state eq 'tx'` (lower case) both return HTTP 200 with 0 rows; leaving out `$count=true` makes `metadata.count` 0 even when rows come back. A misspelled field or an unquoted value is a loud HTTP 400 JSON (`OF_OQP_002`). Blocks 1 and 3 stop on 0 rows and check row totals against `metadata.count`.
- **Rate limit (API doc):** "200 requests/5-minute window per IP address", "No more than 2 concurrent requests per IP address", 100 per 5 minutes on the IHP valid registrations, IPAWS archived alerts, NFIP claims and NFIP policies datasets; over the limit is "HTTP 429 (Too Many Requests)" and "Repeated violations may result in an IP being blocked". robots.txt asks `Crawl-delay: 15`. The blocks run one request at a time, 15 s apart, and retry once on 429 after `Retry-After` (60 s if absent; they stop if it asks for more than 120 s).

## What works

### 1. Every declaration for a county, the state-wide designations, and a deduped state list (browser)

`on_fema_tab()` opens the logged-out dataset page once, so `fetch()` runs from www.fema.gov (the API also sends `Access-Control-Allow-Origin: *`). `get()` returns parsed JSON on HTTP 200, retries once after `Retry-After` when sent (else 60 s on 429, 10 s on 5xx or a network error; over 120 s it stops) and otherwise raises. `rows()` pages with `$top`/`$skip`, always sends `$count=true` and checks the row total against `metadata.count`. `by_disaster()` collapses the per-area rows to one entry per `disasterNumber`. 3 `fetch()` calls, 15 s apart.

```python
import json, time, urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

STATE = "TX"           # two-letter postal code, upper case ('tx' matches nothing)
COUNTY = "Harris"      # county name as FEMA writes it, without "County"
KIND = "County"        # 'County', 'Parish' (LA), 'Borough' or 'Census Area' (AK), ...
SINCE = "2025-01-01"   # state-wide list: declarations on or after this date

SITE = "https://www.fema.gov"
API = SITE + "/api/open/v2/DisasterDeclarationsSummaries"
DATASET_PAGE = SITE + "/openfema-data-page/disaster-declarations-summaries-v2"
FIELDS = ("disasterNumber,femaDeclarationString,declarationType,declarationDate,incidentType,declarationTitle,"
          "designatedArea,ihProgramDeclared,iaProgramDeclared,paProgramDeclared,hmProgramDeclared")
PAUSE = 15  # www.fema.gov robots.txt: 'Crawl-delay: 15' for '*'; the API's own limit is 200 requests / 5 min
PROGRAMS = (("ihProgramDeclared", "IH"), ("iaProgramDeclared", "IA"), ("paProgramDeclared", "PA"), ("hmProgramDeclared", "HM"))
TYPES = {"DR": "major disaster", "EM": "emergency", "FM": "fire management"}

def on_fema_tab():
    """Open the logged-out dataset page once; fetch() then runs from www.fema.gov. Reuse the tab if it is there."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(DATASET_PAGE)
    wait_for_load()
    if js("location.origin") != SITE:
        raise RuntimeError(f"www.fema.gov did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
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

def get(params, timeout=90):
    """One API page as parsed JSON. Retries once, after Retry-After when sent (else 60 s on 429, 10 s on 5xx or a
    network error); raises otherwise."""
    url = API + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"no answer after {timeout}s: {url}")
            time.sleep(0.3)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(retry_after(r.get("ra"), 60 if r["status"] == 429 else 10))
            continue
        if r["status"] != 200 or "json" not in (r["type"] or ""):
            raise RuntimeError(f"HTTP {r['status']} {r['type']} {r['text'][:300]!r} for {url}")
        d = json.loads(r["text"])
        if "DisasterDeclarationsSummaries" not in d or "count" not in d.get("metadata", {}):
            raise RuntimeError(f"unexpected body for {url}: {r['text'][:300]!r}")
        return d

def rows(flt, page=1000):
    """All rows for a $filter, newest first, paging with $skip. $count=true makes metadata.count the total
    (without it, count is 0). Waits PAUSE seconds between calls."""
    out, total, skip = [], None, 0
    while total is None or skip < total:
        if skip or rows.calls:
            time.sleep(PAUSE)
        rows.calls += 1
        d = get({"$filter": flt, "$orderby": "declarationDate desc,disasterNumber desc", "$select": FIELDS,
                 "$top": page, "$skip": skip, "$count": "true"})
        total = d["metadata"]["count"]
        got = d["DisasterDeclarationsSummaries"]
        out += got
        if not got:
            break
        skip += len(got)
    if len(out) != total:
        raise RuntimeError(f"got {len(out)} rows, metadata.count says {total}: {flt}")
    return out
rows.calls = 0

def by_disaster(rs):
    """One row per designated area -> one entry per disasterNumber, programs OR-ed over the areas, newest first."""
    out = {}
    for r in rs:
        e = out.setdefault(r["disasterNumber"], {**r, "areas": 0, "progs": set()})
        e["areas"] += 1
        e["progs"] |= {short for f, short in PROGRAMS if r[f]}
    return sorted(out.values(), key=lambda e: (e["declarationDate"], e["disasterNumber"]), reverse=True)

def line(e):
    progs = "+".join(p for _, p in PROGRAMS if p in e["progs"]) or "none"
    return (f"{e['declarationType']}-{e['disasterNumber']} {e['declarationDate'][:10]} {e['incidentType']:<16} "
            f"{TYPES.get(e['declarationType'], '?'):<15} programs {progs:<11} {e['declarationTitle']}")

on_fema_tab()
q = lambda s: s.replace("'", "''")  # OData string literal: double a single quote
area = f"{COUNTY} ({KIND})"

county = by_disaster(rows(f"state eq '{q(STATE)}' and designatedArea eq '{q(area)}'"))
if not county:
    raise RuntimeError(f"0 rows for '{area}' in {STATE}: check the spelling and the (County)/(Parish) suffix")
n = {t: sum(e["declarationType"] == t for e in county) for t in TYPES}
print(f"{area}, {STATE}: {len(county)} declarations ({n['DR']} DR major disaster, {n['EM']} EM emergency, "
      f"{n['FM']} FM fire management)")
for e in county[:8]:
    print("  " + line(e))
if len(county) > 8:
    print(f"  ... {len(county) - 8} older, the oldest {county[-1]['declarationDate'][:10]} {county[-1]['declarationTitle']}")
latest = county[0]
print(f"latest: {latest['femaDeclarationString']}, {latest['declarationTitle'].title()}, declared "
      f"{latest['declarationDate'][:10]}, incident type {latest['incidentType']}, IH "
      f"{'yes' if latest['ihProgramDeclared'] else 'no'}, PA {'yes' if latest['paProgramDeclared'] else 'no'}")

whole = by_disaster(rows(f"state eq '{q(STATE)}' and designatedArea eq 'Statewide'"))
own = {e["disasterNumber"] for e in county}
extra = [e for e in whole if e["disasterNumber"] not in own]
print(f"\n'Statewide' designations for {STATE}: {len(whole)}, {len(extra)} of them not also listed under {area}; newest:")
for e in extra[:3]:
    print("  " + line(e))

recent = by_disaster(rows(f"state eq '{q(STATE)}' and declarationDate ge '{SINCE}'"))
print(f"\n{STATE} state-wide since {SINCE}: {len(recent)} declarations (deduped on disasterNumber)")
for e in recent:
    print(f"  {line(e)}  [{e['areas']} area{'s' if e['areas'] != 1 else ''}]")

now = datetime.now(timezone.utc)
print(f"\n{rows.calls} API calls. Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations "
      f"Summaries - v2. Retrieved from {API} on {now:%B %d, %Y, %H:%M} UTC. This product uses the Federal Emergency "
      f"Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for "
      f"the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).")
```

Output (from the run on 2026-11-17, 23:44 UTC):

```text
Harris (County), TX: 41 declarations (30 DR major disaster, 10 EM emergency, 1 FM fire management)
  DR-4798 2024-07-09 Hurricane        major disaster  programs IH+PA+HM    HURRICANE BERYL
  DR-4781 2024-05-17 Flood            major disaster  programs IH+PA+HM    SEVERE STORMS, STRAIGHT-LINE WINDS, TORNADOES, AND FLOODING
  DR-4586 2021-02-19 Severe Ice Storm major disaster  programs IH+PA+HM    SEVERE WINTER STORMS
  EM-3554 2021-02-14 Severe Ice Storm emergency       programs PA          SEVERE WINTER STORM
  EM-3540 2020-08-24 Hurricane        emergency       programs PA          TROPICAL STORMS MARCO AND LAURA
  EM-3530 2020-07-26 Hurricane        emergency       programs PA          HURRICANE HANNA
  DR-4485 2020-03-25 Biological       major disaster  programs IH+PA+HM    COVID-19 PANDEMIC
  EM-3458 2020-03-13 Biological       emergency       programs PA          COVID-19
  ... 33 older, the oldest 1973-07-11 SEVERE STORMS & FLOODING
latest: DR-4798-TX, Hurricane Beryl, declared 2024-07-09, incident type Hurricane, IH yes, PA yes

'Statewide' designations for TX: 103, 101 of them not also listed under Harris (County); newest:
  FM-2807 2009-04-10 Fire             fire management programs PA          CEMENT MOUNTAIN FIRE
  FM-2797 2009-03-03 Fire             fire management programs PA          LOMA DEL NORTE FIRE
  FM-2246 1998-09-09 Fire             fire management programs PA          MEXICO FIRE

TX state-wide since 2025-01-01: 16 declarations (deduped on disasterNumber)
  FM-5677 2026-09-15 Fire             fire management programs PA          HYDRA FIRE  [1 area]
  DR-4935 2026-09-01 Flood            major disaster  programs IH+PA       SEVERE STORMS, STRAIGHT-LINE WINDS, TORNADOES, AND FLOODING  [26 areas]
  FM-5675 2026-08-25 Fire             fire management programs PA          ROSS FIRE  [2 areas]
  EM-3649 2026-07-18 Flood            emergency       programs PA          FLOODING  [33 areas]
  FM-5634 2026-05-18 Fire             fire management programs PA          STINKY FIRE  [1 area]
  FM-5633 2026-05-14 Fire             fire management programs PA          HUNGGATE FIRE  [1 area]
  FM-5625 2026-03-15 Fire             fire management programs PA          CORNER POCKET FIRE  [1 area]
  FM-5619 2026-02-18 Fire             fire management programs PA          8 BALL FIRE  [2 areas]
  DR-4879 2025-07-06 Flood            major disaster  programs IH+PA       SEVERE STORMS, STRAIGHT-LINE WINDS, AND FLOODING  [23 areas]
  DR-4871 2025-05-21 Flood            major disaster  programs IH          SEVERE STORMS AND FLOODING  [4 areas]
  FM-5573 2025-03-20 Fire             fire management programs PA+HM       PAULINE ROAD FIRE  [2 areas]
  FM-5571 2025-03-18 Fire             fire management programs PA+HM       DOUBLE S FIRE  [1 area]
  FM-5570 2025-03-15 Fire             fire management programs PA+HM       CRABAPPLE FIRE  [1 area]
  FM-5555 2025-03-14 Fire             fire management programs PA+HM       REST AREA FIRE  [2 areas]
  FM-5553 2025-03-05 Fire             fire management programs PA+HM       DUKE FIRE  [2 areas]
  FM-5552 2025-03-04 Fire             fire management programs PA+HM       WELDER FIRE  [1 area]

3 API calls. Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations Summaries - v2. Retrieved from https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries on November 17, 2026, 23:44 UTC. This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).
```

### 2. robots.txt, the terms, the API doc, the dataset page and the API's answers to mistakes (browser)

4 page loads and 5 in-page `fetch()` calls in the same tab, 15 s apart. It saves robots.txt for block 3, because www.fema.gov answers HTTP 403 to urllib and curl for that one file.

```python
import json, os, re, time, urllib.parse, urllib.robotparser

SITE = "https://www.fema.gov"
API = SITE + "/api/open/v2/DisasterDeclarationsSummaries"
SAVE_ROBOTS = os.path.expanduser("~/.cache/openfema-skill/robots_fema.txt")  # read by block 3
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider", "PetalBot", "Meta-ExternalAgent"]
PAUSE = 15  # robots.txt Crawl-delay for '*'

START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const t = await r.text(); let n = null, c = null;
       try { const j = JSON.parse(t); n = (j.DisasterDeclarationsSummaries || []).length; c = (j.metadata || {}).count; } catch (e) {}
       window.__o[id] = {status: r.status, type: r.headers.get('content-type'), cache: r.headers.get('cache-control'),
         acao: r.headers.get('access-control-allow-origin'), bytes: t.length, rows: n, count: c, text: t.slice(0, 400)}; })
    .catch(e => { window.__o[id] = {status: 0, type: '', bytes: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def api(params):
    """One in-page API request -> raw answer. No retries: this block only inspects answers."""
    url = API + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"no answer after 90s: {url}")
        time.sleep(0.3)
    time.sleep(PAUSE)
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    time.sleep(2)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    time.sleep(PAUSE)
    return st, js("document.body ? document.body.innerText : ''")

def last_updated(txt):
    m = re.search(r"Last updated\s+([A-Z][a-z]+ \d{1,2}, \d{4})", txt)
    return m[1] if m else "NOT FOUND"

try:
    here = js("location.origin")
except Exception:
    here = None
if here != SITE:
    new_tab(SITE + "/openfema-data-page/disaster-declarations-summaries-v2")
    wait_for_load()
    time.sleep(PAUSE)

# 1. robots.txt as the browser sees it (curl and urllib get HTTP 403 for this one file)
st, txt = page(SITE + "/robots.txt")
os.makedirs(os.path.dirname(SAVE_ROBOTS), exist_ok=True)
open(SAVE_ROBOTS, "w").write(txt)
print(f"robots.txt HTTP {st}, {len(txt)} chars, saved to ~/.cache/openfema-skill/ for block 3")
groups = re.findall(r"(?im)^user-agent:\s*(\S+)", txt)
print(f"User-agent lines: {groups}")
print(f"Crawl-delay lines: {re.findall(r'(?im)^crawl-delay:.*$', txt)}")
print(f"Disallow lines that touch /api: {[l for l in re.findall(r'(?im)^disallow:.*$', txt) if '/api' in l.lower()]}")
rp = urllib.robotparser.RobotFileParser()
rp.parse(txt.splitlines())
for p in ("/api/open/v2/DisasterDeclarationsSummaries", "/openfema-data-page/disaster-declarations-summaries-v2",
          "/about/openfema/terms-conditions", "/about/openfema/api"):
    res = {a: rp.can_fetch(a, SITE + p) for a in AGENTS}
    print(f"  {p:<58} allowed for {sum(res.values())}/{len(AGENTS)}; blocked: {[a for a, ok in res.items() if not ok]}")

# 2. the terms, the API doc and the dataset page: dates and the clauses this skill relies on
for url, needles in (
        (SITE + "/about/openfema/terms-conditions",
         ["used solely for statistical research or as a reporting record", "not to reidentify",
          "cannot be used to make determinations", "cite the specific API endpoint (including the version)",
          "is not endorsed by FEMA", "logos and/or seals"]),
        (SITE + "/about/openfema/api",
         ["requires no registration", "authentication is not necessary", "descriptive “user-agent” header",
          "200 requests/5-minute window per IP address", "No more than 2 concurrent requests", "HTTP 429"]),
        (SITE + "/openfema-data-page/disaster-declarations-summaries-v2",
         ["all three disaster declaration types", "0001-1999 Major Disaster Declaration",
          "this value will be 000", "Tribal Nations are currently included in State data"])):
    st, txt = page(url)
    low = txt.lower()
    words = [w for w in ("artificial intelligence", "machine learning", "scrap", "crawl", "robot", "non-commercial",
                         "noncommercial", "automated") if w in low]
    print(f"\n{url}\n  HTTP {st}, Last updated {last_updated(txt)}; AI/scraping/commercial words present: {words}")
    for n in needles:
        i = txt.find(n)
        print(f"  {'found  ' if i >= 0 else 'MISSING'} {n!r}")

# 3. what the API does with mistakes (each answer printed short)
for label, p in (("no $count", {"$filter": "state eq 'TX' and designatedArea eq 'Harris (County)'", "$top": 1}),
                 ("'Harris County'", {"$filter": "state eq 'TX' and designatedArea eq 'Harris County'", "$count": "true"}),
                 ("state 'tx'", {"$filter": "state eq 'tx'", "$count": "true", "$top": 1}),
                 ("unquoted TX", {"$filter": "state eq TX", "$top": 1}),
                 ("no $top", {"$filter": "state eq 'TX'", "$select": "disasterNumber", "$count": "true"})):
    r = api(p)
    if r["status"] == 200 and r["rows"] is not None:
        print(f"{label:<16} HTTP 200 metadata.count {r['count']}, {r['rows']} rows, {r['bytes']} chars, "
              f"cache-control {r['cache']!r}, access-control-allow-origin {r['acao']!r}")
    else:
        body = re.sub(r"\s+", " ", r["text"][:230])
        print(f"{label:<16} HTTP {r['status']} {r['type']} {body}")
```

Output (from the run on 2026-11-17, 23:37 UTC):

```text
robots.txt HTTP 200, 3287 chars, saved to ~/.cache/openfema-skill/ for block 3
User-agent lines: ['*', 'PetalBot', '*', 'Meta-ExternalAgent']
Crawl-delay lines: ['crawl-delay: 15']
Disallow lines that touch /api: []
  /api/open/v2/DisasterDeclarationsSummaries                 allowed for 11/13; blocked: ['PetalBot', 'Meta-ExternalAgent']
  /openfema-data-page/disaster-declarations-summaries-v2     allowed for 11/13; blocked: ['PetalBot', 'Meta-ExternalAgent']
  /about/openfema/terms-conditions                           allowed for 11/13; blocked: ['PetalBot', 'Meta-ExternalAgent']
  /about/openfema/api                                        allowed for 11/13; blocked: ['PetalBot', 'Meta-ExternalAgent']

https://www.fema.gov/about/openfema/terms-conditions
  HTTP 200, Last updated January 22, 2025; AI/scraping/commercial words present: []
  found   'used solely for statistical research or as a reporting record'
  found   'not to reidentify'
  found   'cannot be used to make determinations'
  found   'cite the specific API endpoint (including the version)'
  found   'is not endorsed by FEMA'
  found   'logos and/or seals'

https://www.fema.gov/about/openfema/api
  HTTP 200, Last updated November 13, 2026; AI/scraping/commercial words present: []
  found   'requires no registration'
  found   'authentication is not necessary'
  found   'descriptive “user-agent” header'
  found   '200 requests/5-minute window per IP address'
  found   'No more than 2 concurrent requests'
  found   'HTTP 429'

https://www.fema.gov/openfema-data-page/disaster-declarations-summaries-v2
  HTTP 200, Last updated November 17, 2026; AI/scraping/commercial words present: []
  found   'all three disaster declaration types'
  found   '0001-1999 Major Disaster Declaration'
  found   'this value will be 000'
  found   'Tribal Nations are currently included in State data'
no $count        HTTP 200 metadata.count 0, 1 rows, 1352 chars, cache-control 'public, max-age=150', access-control-allow-origin '*'
'Harris County'  HTTP 200 metadata.count 0, 0 rows, 452 chars, cache-control 'public, max-age=150', access-control-allow-origin '*'
state 'tx'       HTTP 200 metadata.count 0, 0 rows, 366 chars, cache-control 'public, max-age=150', access-control-allow-origin '*'
unquoted TX      HTTP 400 application/json; charset=utf-8 {"error":[{"name":"OData Query Parser Error","code":"OF_OQP_002","type":"$filter criteria error","message":"Field \"TX\" not found in the model path DisasterDeclarationsSummaries. Please check that the fields are valid."}]}
no $top          HTTP 200 metadata.count 5453, 1000 rows, 24399 chars, cache-control 'public, max-age=149', access-control-allow-origin '*'
```

### 3. A whole state with Python urllib, a county by FIPS code, robots check for every agent (no browser)

8 requests, 15 s apart: robots.txt (HTTP 403, so it parses block 2's browser copy), 6 pages of 1,000 rows for Texas, and 1 county by FIPS. `rules_for()` merges every group that names the agent (or every `*` group), as RFC 9309 says; Python's `urllib.robotparser` uses only the first `*` group, and on a 403 it treats the whole site as disallowed.

```python
import collections, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

STATE = "TX"
FIPS = ("48", "201")  # (state, county) FIPS for the county cross-check: 48/201 = Harris County, TX
ROBOTS_COPY = os.path.expanduser("~/.cache/openfema-skill/robots_fema.txt")  # saved by block 2

SITE = "https://www.fema.gov"
API = SITE + "/api/open/v2/DisasterDeclarationsSummaries"
UA = "openfema-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"  # the API doc asks for a descriptive one
PAUSE = 15  # robots.txt 'Crawl-delay: 15' for '*'; also far under the API's 200 requests / 5 min, 2 at a time
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
PROGRAMS = (("ihProgramDeclared", "IH"), ("iaProgramDeclared", "IA"), ("paProgramDeclared", "PA"), ("hmProgramDeclared", "HM"))
calls = 0

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

def get(url):
    """GET -> (status, content-type, text). One retry: after Retry-After when sent, else 60 s on 429 and 10 s on 5xx
    or a network error. Other HTTP errors are returned, not raised, so the caller decides."""
    global calls
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(2):
        if calls:
            time.sleep(PAUSE)
        calls += 1
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After"), 60 if e.code == 429 else 10))
                continue
            return e.code, e.headers.get("Content-Type", ""), e.read().decode(errors="replace")
        except OSError as e:
            if attempt == 0:
                time.sleep(10)
                continue
            sys.exit(f"{url}: {e}")

def rules_for(txt, agent):
    """RFC 9309 groups: every group naming the agent (merged), else every '*' group (merged). -> [(allow, path)]"""
    groups, cur, in_ua = [], None, False
    for raw in txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if not in_ua:
                cur = ([], [])
                groups.append(cur)
            cur[0].append(v.lower())
            in_ua = True
        elif k in ("allow", "disallow") and cur is not None:
            in_ua = False
            if v:
                cur[1].append((k == "allow", v))
        else:
            in_ua = False
    named = [g for g in groups if agent.lower() in g[0]] if agent != "*" else []
    return [r for g in (named or [g for g in groups if "*" in g[0]]) for r in g[1]]

def allowed(rules, path):
    """Longest matching rule wins, Allow wins a tie; '*' and '$' as in RFC 9309."""
    best = (-1, True)
    for ok, pat in rules:
        rx = "".join(".*" if c == "*" else ("$" if c == "$" and i == len(pat) - 1 else re.escape(c)) for i, c in enumerate(pat))
        if re.match(rx, path) and (len(pat) > best[0] or (len(pat) == best[0] and ok)):
            best = (len(pat), ok)
    return best[1]

def rows(flt, select, page=1000):
    """All rows for a $filter via $top/$skip; $count=true so metadata.count is the real total."""
    out, total = [], None
    while total is None or len(out) < total:
        q = {"$filter": flt, "$select": select, "$orderby": "declarationDate desc,disasterNumber desc",
             "$top": page, "$skip": len(out), "$count": "true"}
        st, ctype, text = get(API + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote))
        if st != 200 or "json" not in ctype:
            sys.exit(f"API HTTP {st} {ctype}: {text[:300]!r}")
        d = json.loads(text)
        total, got = d["metadata"]["count"], d["DisasterDeclarationsSummaries"]
        if not got:
            break
        out += got
    if len(out) != total:
        sys.exit(f"{len(out)} rows but metadata.count {total}")
    return out

# 1. robots.txt: www.fema.gov answers 403 to urllib and curl for this file, so fall back to the browser's copy
st, ctype, text = get(SITE + "/robots.txt")
src = "live"
if st != 200:
    head = " ".join(re.sub(r"<[^>]+>", " ", text).split())[:40]
    print(f"robots.txt via urllib: HTTP {st} {ctype} ({head!r}); using the cloud-browser copy from block 2")
    if not os.path.exists(ROBOTS_COPY):
        sys.exit(f"no browser copy at {ROBOTS_COPY}: run block 2 first, then re-run this block")
    text, src = open(ROBOTS_COPY).read(), "browser copy"
delay = re.findall(r"(?im)^crawl-delay:\s*(\d+)", text)
for p in ("/api/open/v2/DisasterDeclarationsSummaries", "/api/open/v1/OpenFemaDataSets"):
    ok = [a for a in AGENTS if allowed(rules_for(text, a), p)]
    print(f"robots ({src}) {p:<44} allowed for {len(ok)}/{len(AGENTS)} agents")
    if len(ok) != len(AGENTS):
        sys.exit(f"robots.txt disallows {p} for {sorted(set(AGENTS) - set(ok))}: stop")
print(f"robots crawl-delay: {delay} (this block waits {PAUSE} s between requests)")

# 2. every declaration in a state, one per disaster
SEL = "disasterNumber,declarationType,declarationDate,incidentType,declarationTitle,designatedArea," + \
      ",".join(f for f, _ in PROGRAMS)
rs = rows(f"state eq '{STATE}'", SEL)
dis = {}
for r in rs:
    e = dis.setdefault(r["disasterNumber"], {**r, "areas": set(), "progs": set()})
    e["areas"].add(r["designatedArea"])
    e["progs"] |= {s for f, s in PROGRAMS if r[f]}
dis = sorted(dis.values(), key=lambda e: (e["declarationDate"], e["disasterNumber"]), reverse=True)
if not dis:
    sys.exit(f"0 declarations for state '{STATE}': use the two-letter code in upper case")
print(f"\n{STATE}: {len(rs)} rows (one per designated area) -> {len(dis)} declarations: "
      f"{dict(collections.Counter(e['declarationType'] for e in dis).most_common())}")
print(f"incident types: {dict(collections.Counter(e['incidentType'] for e in dis).most_common(6))}")
print(f"programs (any area): " + ", ".join(f"{s} {sum(s in e['progs'] for e in dis)}" for _, s in PROGRAMS))
big = max(dis, key=lambda e: len(e["areas"]))
print(f"most areas: {big['declarationType']}-{big['disasterNumber']} {big['declarationTitle']} "
      f"({big['declarationDate'][:10]}): {len(big['areas'])} areas")
for e in dis[:3]:
    print(f"  {e['declarationType']}-{e['disasterNumber']} {e['declarationDate'][:10]} {e['incidentType']}: "
          f"{e['declarationTitle']} [{len(e['areas'])} area(s), {'+'.join(sorted(e['progs'])) or 'none'}]")

# 3. a county by FIPS code instead of by name
cty = rows(f"fipsStateCode eq '{FIPS[0]}' and fipsCountyCode eq '{FIPS[1]}'", SEL)
if not cty:
    sys.exit(f"0 rows for FIPS {FIPS[0]}/{FIPS[1]}: check the codes (3-digit county, '000' = state-wide)")
print(f"\nFIPS {FIPS[0]}/{FIPS[1]}: {len(cty)} rows, {len({r['disasterNumber'] for r in cty})} declarations, "
      f"names {sorted({r['designatedArea'] for r in cty})}; latest {cty[0]['declarationType']}-{cty[0]['disasterNumber']} "
      f"{cty[0]['declarationTitle']} {cty[0]['declarationDate'][:10]}")

now = datetime.now(timezone.utc)
print(f"\n{calls} requests. Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations Summaries - v2. "
      f"Retrieved from {API} on {now:%B %d, %Y, %H:%M} UTC. This product uses the Federal Emergency Management Agency's "
      f"OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses "
      f"derived from these data after the data have been retrieved from the Agency's website(s).")
```

Output (from the run on 2026-11-17, 23:40 UTC):

```text
robots.txt via urllib: HTTP 403 text/html ("Access Denied Access Denied You don't ha"); using the cloud-browser copy from block 2
robots (browser copy) /api/open/v2/DisasterDeclarationsSummaries   allowed for 11/11 agents
robots (browser copy) /api/open/v1/OpenFemaDataSets                allowed for 11/11 agents
robots crawl-delay: ['15'] (this block waits 15 s between requests)

TX: 5453 rows (one per designated area) -> 392 declarations: {'FM': 265, 'DR': 108, 'EM': 19}
incident types: {'Fire': 272, 'Flood': 45, 'Hurricane': 25, 'Severe Storm': 20, 'Tornado': 15, 'Severe Ice Storm': 3}
programs (any area): IH 29, IA 79, PA 370, HM 74
most areas: DR-4485 COVID-19 PANDEMIC (2020-03-25): 257 areas
  FM-5677 2026-09-15 Fire: HYDRA FIRE [1 area(s), PA]
  DR-4935 2026-09-01 Flood: SEVERE STORMS, STRAIGHT-LINE WINDS, TORNADOES, AND FLOODING [26 area(s), IH+PA]
  FM-5675 2026-08-25 Fire: ROSS FIRE [2 area(s), PA]

FIPS 48/201: 41 rows, 41 declarations, names ['Harris (County)']; latest DR-4798 HURRICANE BERYL 2024-07-09

8 requests. Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations Summaries - v2. Retrieved from https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries on November 17, 2026, 23:42 UTC. This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).
```

### 4. curl

```bash
A='https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries'
UA='openfema-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# the terms ask for the endpoint, its version, the access time and this notice with every answer
notice() { echo "Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations Summaries - v2. Retrieved from $A on $(date -u '+%B %d, %Y, %H:%M') UTC. This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s)."; }
# the answer: every declaration for one county, newest first, with the total in metadata.count
curl -sS --fail -G -A "$UA" "$A" \
  --data-urlencode "\$filter=state eq 'TX' and designatedArea eq 'Harris (County)'" \
  --data-urlencode '$orderby=declarationDate desc' --data-urlencode '$top=3' --data-urlencode '$count=true' \
  --data-urlencode '$select=femaDeclarationString,declarationDate,incidentType,declarationTitle,ihProgramDeclared,iaProgramDeclared,paProgramDeclared,hmProgramDeclared' \
  | python3 -c 'import sys, json
d = json.load(sys.stdin); print("metadata.count", d["metadata"]["count"], "rundate", d["metadata"]["rundate"])
for r in d["DisasterDeclarationsSummaries"]:
    p = "+".join(k[:2].upper() for k in ("ihProgramDeclared", "iaProgramDeclared", "paProgramDeclared", "hmProgramDeclared") if r[k])
    print(r["femaDeclarationString"], r["declarationDate"][:10], r["incidentType"], "|", r["declarationTitle"], "|", p or "none")'
notice
sleep 15
# headers: JSON, CORS open, cached 150 s, no rate-limit headers
curl -sS -G -A "$UA" -D - -o /dev/null "$A" --data-urlencode '$top=1' | tr -d '\r' \
  | grep -iE '^(HTTP/|content-type|cache-control|access-control-allow-origin|x-ratelimit|retry-after)'
sleep 15
# CSV instead of JSON: same query plus $format=csv
curl -sS -G -A "$UA" "$A" --data-urlencode "\$filter=state eq 'TX' and designatedArea eq 'Harris (County)'" \
  --data-urlencode '$orderby=declarationDate desc' --data-urlencode '$top=2' --data-urlencode '$format=csv' \
  --data-urlencode '$select=femaDeclarationString,declarationDate,incidentType,ihProgramDeclared,paProgramDeclared'
notice
sleep 15
# mistakes: a wrong field name is HTTP 400 JSON; robots.txt is refused to curl (read it in a browser)
curl -sS -G -A "$UA" -w '\nHTTP %{http_code}\n' "$A" --data-urlencode "\$filter=county eq 'Harris'"
sleep 15
curl -sS -A "$UA" -o /dev/null -w 'robots.txt via curl: HTTP %{http_code} %{content_type}\n' https://www.fema.gov/robots.txt
```

Output (from the run on 2026-11-18, 00:51 UTC; `rundate` is from the API's cache, built 00:49):

```text
metadata.count 41 rundate 2026-11-18T00:49:13.751Z
DR-4798-TX 2024-07-09 Hurricane | HURRICANE BERYL | IH+PA+HM
DR-4781-TX 2024-05-17 Flood | SEVERE STORMS, STRAIGHT-LINE WINDS, TORNADOES, AND FLOODING | IH+PA+HM
DR-4586-TX 2021-02-19 Severe Ice Storm | SEVERE WINTER STORMS | IH+PA+HM
Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations Summaries - v2. Retrieved from https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries on November 18, 2026, 00:51 UTC. This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).
HTTP/2 200 
content-type: application/json; charset=utf-8
access-control-allow-origin: *
cache-control: public, max-age=7
femaDeclarationString,declarationDate,incidentType,ihProgramDeclared,paProgramDeclared
DR-4798-TX,2024-07-09T00:00:00.000Z,Hurricane,1,1
DR-4781-TX,2024-05-17T00:00:00.000Z,Flood,1,1
Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations Summaries - v2. Retrieved from https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries on November 18, 2026, 00:51 UTC. This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).
{"error":[{"name":"OData Query Parser Error","code":"OF_OQP_002","type":"$filter criteria error","message":"Field \"county\" not found in the model path DisasterDeclarationsSummaries.  Please check that the fields are valid."}]}
HTTP 400
robots.txt via curl: HTTP 403 text/html
```

## Fields (DisasterDeclarationsSummaries v2)

| Field | Example | Notes |
|---|---|---|
| `femaDeclarationString` | `DR-4798-TX` | type, number and state in one string |
| `disasterNumber` | `4798` | the key to dedupe on; ranges per the dataset page: 0001-1999 and 4000-4999 major disaster, 2000-2999 and 5000-5999 fire management, 3000-3999 emergency |
| `declarationType` | `DR`, `EM`, `FM` | major disaster, emergency, fire management |
| `declarationDate` | `2024-07-09T00:00:00.000Z` | a date written as UTC midnight; use the first 10 characters |
| `incidentType` | `Hurricane`, `Flood`, `Severe Storm`, `Fire`, `Biological` | the "primary or official type"; `designatedIncidentTypes` (`H`, `F,T,W`, or null) is "A comma-separated list of incident types designated for the disaster" in letter codes (H Hurricane, F Flood, T Tornado, W Severe Storm) and can repeat the primary type (DR-4798: `H`) |
| `declarationTitle` | `HURRICANE BERYL` | upper case |
| `ihProgramDeclared` | `true` | Individuals and Households program, for this area |
| `iaProgramDeclared` | `false` | Individual Assistance program; the dataset page says to "use both ihProgramDeclared and iaProgramDeclared" to find events authorized for Individual Assistance |
| `paProgramDeclared` | `true` | Public Assistance program |
| `hmProgramDeclared` | `true` | Hazard Mitigation program |
| `designatedArea` | `Harris (County)`, `Orleans (Parish)`, `Statewide` | name plus the kind in parentheses; tribal areas appear inside the state's data |
| `state`, `fipsStateCode`, `fipsCountyCode`, `placeCode` | `TX`, `48`, `201`, `99201` | county FIPS is `000` for a state-wide designation (dataset page) |
| `incidentBeginDate`, `incidentEndDate` | `2024-07-05T00:00:00.000Z`, `2024-07-09T00:00:00.000Z` | the incident, not the declaration |
| `lastRefresh` | `2026-11-13T12:24:12.669Z` | "Date the record was last updated in the API data store" (dataset page) |

The response is `{"metadata": {...}, "DisasterDeclarationsSummaries": [...]}`; `metadata` echoes `filter`, `orderby`, `top`, `skip`, `version` (`v2`), `rundate` and `count`.

## Gotchas

- **Dedupe on `disasterNumber`.** A state query returns one row per county, parish, tribal area or `Statewide` designation per disaster (Texas: 5,453 rows, 392 declarations). Harris County happens to have one row per disaster (41 rows, 41 numbers), but a name pattern such as `startswith(designatedArea,'Harris')` also matches `Harrison (County)` (69 rows: 27 Harris, 23 Harrison in the first 50).
- **Area names carry the kind in parentheses.** `Harris (County)`, `Orleans (Parish)` (39 rows), and in Alaska `(Borough)`, `(Census Area)`, `(ANV/ANVSA)` and names such as `Lower Yukon Regional Educational Attendance Area`. `'Harris County'` matches nothing and still returns HTTP 200. FIPS codes avoid the spelling problem (block 3).
- **`Statewide` rows are separate.** A county query does not return them: Texas has 103 `Statewide` declarations, 101 of them not listed under Harris (block 1); the newest is FM-2807, 2009. Decide whether "declarations for a county" includes them, and say which you used.
- **`metadata.count` is 0 unless you send `$count=true`.** It is not the number of rows returned: with `$count=true` and the default page, Texas says 5,453 and returns 1,000.
- **Pages are 1,000 rows by default.** No `$top` and `$top=0` both returned 1,000 rows; `$top=10000` and `$top=10001` both returned all 5,453 Texas rows in one call. The blocks page at 1,000 with `$skip`.
- **String values are case-sensitive and need single quotes.** `state eq 'tx'` gives 0 rows; `state eq TX` is HTTP 400 `Field "TX" not found`. Inside a value, double a single quote (block 1's `q()`).
- **IH versus IA.** Harris's 1970s declarations have `iaProgramDeclared` true and `ihProgramDeclared` false; DR-4798 (2024) has IH true and IA false. Report both flags.
- **CSV booleans are `1`/`0`**, JSON booleans are `true`/`false`.
- **Responses are cached.** `cache-control: public, max-age=150`, and lower values (`149`, `41`, `7`) on other calls, so an answer can be up to 150 s old; `metadata.rundate` shows when it was built (block 4's 00:51 run got a `rundate` of 00:49).
- **robots.txt and the dataset page refuse curl** (HTTP 403 "Access Denied") but the API does not. Read those pages in a browser.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin`, never the title.

## What does not work

- **`'Harris County'`, `'tx'`, partial names with `eq`**: HTTP 200 with 0 rows, no error. Use the exact `designatedArea` value or FIPS codes.
- **Unknown field names** in `$filter`, `$orderby` or `$select`: HTTP 400 JSON with codes `OF_OQP_002`, `OF_OQP_001` and `OF_OQP_003`.
- **robots.txt from curl or urllib**: HTTP 403; `urllib.robotparser.read()` then reports every path as disallowed.
- **Not tested:** rate-limit behaviour (never provoked), the largest `$top` the server accepts, `$apply`/aggregation, and the other OpenFEMA datasets (the `/api/open/v1/OpenFemaDataSets` index is linked from the dataset page).
