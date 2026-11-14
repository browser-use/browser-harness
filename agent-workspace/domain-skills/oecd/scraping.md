# OECD - Compare the Latest Composite Leading Indicator (CLI) for the US, Germany and Japan (official keyless SDMX API)

Field-tested against sdmx.oecd.org on 2026-11-14 (23:30-23:38 UTC) using a fresh Browser Use cloud browser (logged out, two short sessions) plus Python `urllib` and `curl` from a Linux server. 9 browser page loads (API, Data Explorer, robots, terms and docs pages) and 18 in-page `fetch()` calls, 31 curl calls and 5 urllib calls, all serial at 1 s or more spacing: every API call was HTTP 200 except the deliberate 403/404 probes below, the User-Agent 403 described under Gotchas and one HTTP 400 on a guessed metadata URL. No 429, no challenge page, no key, no login needed.

robots.txt (checked 2026-11-14, curl, urllib and the cloud browser): https://sdmx.oecd.org/robots.txt is HTTP 404 (an IIS "404 - File or directory not found." HTML page), so the API host has no rules for `*` or any agent. https://www.oecd.org/robots.txt has four groups, `*`, `Twitterbot`, `Googlebot` and `Spacecat/1.0`; `*` disallows only `/content/dam/oecd/` and `/adobe/dynamicmedia/deliver/`. https://data-explorer.oecd.org/robots.txt (a 302 to `/assets/oecd/data-explorer/robots.txt`) has one `*` group: `Allow: /` plus four `Disallow` rules for the archive tenant (`df[ds]=DisseminateArchiveDMZ`, `tenant=archive`). There are no named AI-agent groups on any of the three hosts, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot, Bytespider, Applebot-Extended and Meta-ExternalAgent all follow `*`. An RFC 9309 matcher gives ALLOW for `*` and all 14 named agents on every path this skill uses (the API data and `dataflow/all` paths, the terms, indicator and API explainer pages, and the Data Explorer citation link). The CLI methodology PDF the API links to lives under `/content/dam/oecd/` and is disallowed, so it is not fetched. Terms: OECD "Terms and Conditions" (https://www.oecd.org/en/about/terms-conditions.html, "Last updated on 1 July 2024"), Data section: "you can extract from, download, copy, adapt, print, distribute, share and embed Data for any purpose, even for commercial use", "Except where additional restrictions apply": "It is the user's responsibility to verify, either directly in the metadata or, if available, by clicking on the icon and then referring to the "source" tab, whether the Data is fully or partially owned by third parties and/or whether additional restrictions may apply". The Data Explorer overview of this dataflow shows "© OECD", "Last updated: November 09, 2026 at 6:29:45 AM" and no third-party source note; the SDMX answer has no source or restriction attribute. Limits: "The OECD may monitor your use of the Data and reserves the right ... to modify the amount of Data you may request in a single query, to modify the number of queries you may make over a specified time"; for the APIs, "You agree not to modify, distribute, decompile, disassemble, reverse engineer or perform any similar action on the APIs" and "not to use any technical means to interfere with the OECD's monitoring of usage". Registration is voluntary: "the OECD encourages, but does not require, you to register your details". Naming: "The OECD logo is legally protected and may not be used without express written permission", so this skill writes "OECD" only as the source in the citation the terms ask for, in plain text, with no logo. The terms page has no AI/ML, scraping, automated-access or non-commercial clause (its only "artificial intelligence" text is the site's topic menu). This skill is not affiliated with or endorsed by the OECD.

**Citation:** the terms say "You must give appropriate credit to the OECD by using the citation associated with the relevant Data, or, if no specific citation is available, you must cite the source information using the following format: OECD (year), (dataset name),(data source) DOI or URL (accessed on (date))." No DOI was found for this dataflow in the API answer or the Data Explorer overview, so blocks 1 and 3 print `OECD (2026), Composite leading indicators, OECD Data Explorer, https://data-explorer.oecd.org/vis?df[ds]=dsDisseminateFinalDMZ&df[id]=DSD_STES%40DF_CLI&df[ag]=OECD.SDD.STES (accessed on 14 November 2026).` and say which numbers (month-on-month differences, ordering) are ours. The OECD values themselves are printed as served, not rounded.

## Quick summary

- **No scraping.** `GET https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI/USA+DEU+JPN.M.LI...AA...H?lastNObservations=1&dimensionAtObservation=AllDimensions&format=csvfilewithlabels` returns one CSV row per country with codes and English labels side by side. `format=jsondata` returns SDMX-JSON 1.0 instead. No key.
- **Answer (2026-11-14, 23:37 UTC; Data Explorer "Last updated: November 09, 2026"):** latest month **2026-10** for all three. **Germany 101.1611** (rising, +0.1422 on September), **United States 100.9566** (rising, +0.0256), **Japan 100.2095** (falling, -0.0200). All three are above 100, the long-term average. Japan's 13-month high was 2026-08 (100.2432); the US and Germany peaked in 2026-10.
- **Pin the headline series.** The 9-part key is `REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION.TIME_HORIZ.METHODOLOGY`. `LI` + `AA` (amplitude adjusted) + `H` (OECD harmonised) is the headline CLI. Leaving `ADJUSTMENT` empty also returns trend-restored (`TR`, about 132 for the US), normalised (`NOR`) and growth-rate (`GY`) versions in the same answer.
- **Direction beats level.** The dataflow description: "the main message of CLI movements over time is the increase or decrease, rather than the amplitude of the changes." The indicator page: "measured as an amplitude adjusted index, long-term average = 100". Blocks 1 and 3 print the level, the change and whether it is above 100.
- **Silent misses and plain-text errors.** An unknown area next to a known one is dropped (HTTP 200); an answer with no series is HTTP 404 `NoRecordsFound` (text/plain); a key with the wrong number of parts is **HTTP 403** `Not enough key values in query, expecting 9 got 3`. Check that every requested country came back.
- **Python's default User-Agent is refused.** `Python-urllib/3.12` gets HTTP 403 `error code: 1010` from the Cloudflare front; curl's default, an empty one and a descriptive one got 200. Block 3 sends an honest User-Agent naming the client.
- **Rate limit:** the OECD API explainer says "rate limiting has been introduced" and publishes no number; no rate-limit headers were sent (block 4). Answers carry `cache-control: public,max-age=7200`. Blocks 1 and 3 make 1 data call each (block 1 also opens one small API answer in the tab on first use), block 2 makes 8 and block 4 makes 5, 1 s apart.

## What works

### 1. Latest headline CLI for the US, Germany and Japan, with direction (browser)

`on_api_tab()` opens one small `format=jsondata` answer on sdmx.oecd.org, so `fetch()` is same-origin. (A `csvfilewithlabels` URL is sent as `content-disposition: attachment`, so a tab would download it rather than show it; `fetch()` reads it fine.) `get()` returns the CSV text on HTTP 200, waits 30 s once on 429/500/502/503/504 and otherwise raises. The block checks that every row is the monthly amplitude-adjusted OECD-harmonised CLI, that all three countries came back with 4 months each and that they end in the same month, then prints level, 1- and 3-month changes, direction, ordering and the citation.

```python
import csv, io, json, time, urllib.parse
from datetime import datetime, timezone

AREAS = ["USA", "DEU", "JPN"]  # OECD REF_AREA codes (ISO 3166 alpha-3)
FLOW = "OECD.SDD.STES,DSD_STES@DF_CLI"  # agency,dataflow: "Composite leading indicators"
# 9-part key REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION.TIME_HORIZ.METHODOLOGY;
# empty = any. LI = CLI, AA = amplitude adjusted (the OECD headline CLI), H = OECD harmonised.
KEY = "+".join(AREAS) + ".M.LI...AA...H"
PIN = {"FREQ": "M", "MEASURE": "LI", "UNIT_MEASURE": "IX", "ADJUSTMENT": "AA", "TRANSFORMATION": "IX", "METHODOLOGY": "H"}
N = 4  # latest month plus 3 before it, for the direction

SITE = "https://sdmx.oecd.org"
API = SITE + "/public/rest/data/"
PAUSE = 1.0  # OECD rate-limits the API and publishes no number; stay serial

def url(fmt, n=N):
    return API + FLOW + "/" + KEY + "?" + urllib.parse.urlencode(
        {"lastNObservations": n, "dimensionAtObservation": "AllDimensions", "format": fmt})

def on_api_tab():
    """fetch() runs same-origin from a logged-out sdmx.oecd.org tab that shows one small API answer. Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(url("jsondata", 1))
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"dataSets"' not in body:
        raise RuntimeError(f"sdmx.oecd.org did not serve the API answer (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__oe = window.__oe || {}; const id = String(Math.random()).slice(2); window.__oe[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__oe[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__oe[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__oe[%s]; if (v) delete window.__oe[%s]; return v; })()"""

def get(u, timeout=60):
    """Same-origin GET -> body text on HTTP 200. Errors are short text/plain bodies ("NoRecordsFound" is HTTP 404,
    a wrong key length is HTTP 403). Waits 30 s once on 429/500/502/503/504 or a network error, raises on anything else."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(u)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"no answer after {timeout}s: {u}")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        if r["status"] != 200 or "csv" not in (r["type"] or ""):
            raise RuntimeError(f"HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:200]!r}; stopping")
        return r["text"]

on_api_tab()
rows = list(csv.DictReader(io.StringIO(get(url("csvfilewithlabels")))))
if not rows:
    raise RuntimeError("empty CSV: stop")

# Check every series is the headline CLI and every country came back (an unknown code is dropped, HTTP 200).
series = {}
for r in rows:
    for dim, code in PIN.items():
        if r[dim] != code:
            raise RuntimeError(f"{r['REF_AREA']}: {dim}={r[dim]}, expected {code}: stop")
    series.setdefault(r["REF_AREA"], []).append(r)
missing = [a for a in AREAS if a not in series]
if missing:
    raise RuntimeError(f"no CLI series for {missing}: stop")
for a in AREAS:
    series[a].sort(key=lambda r: r["TIME_PERIOD"])
    if len(series[a]) != N:
        raise RuntimeError(f"{a}: {len(series[a])} months, expected {N}: stop")

# lastNObservations counts per series, so check all three end in the same month before comparing.
latest = {a: series[a][-1]["TIME_PERIOD"] for a in AREAS}
if len(set(latest.values())) != 1:
    raise RuntimeError(f"latest months differ: {latest}; compare on a common month instead")
month = latest[AREAS[0]]
r0 = rows[0]
print(f"{r0['STRUCTURE_NAME']} ({r0['STRUCTURE_ID']}): {r0['Measure']}, {r0['Adjustment']}, {r0['Unit of measure']}, "
      f"{r0['Calculation methodology']}; long-term average = 100")
print(f"\nLatest month: {month} (months in answer {series[AREAS[0]][0]['TIME_PERIOD']}..{month})")
print(f"  {'':<15} {'CLI':>9} {'1m chg':>8} {'3m chg':>8}  direction  status")
out = []
for a in AREAS:
    v = [float(r["OBS_VALUE"]) for r in series[a]]
    d1, d3 = v[-1] - v[-2], v[-1] - v[0]
    way = "rising" if d1 > 0 else "falling" if d1 < 0 else "flat"
    out.append((v[-1], a))
    print(f"  {series[a][-1]['Reference area']:<15} {v[-1]:>9.4f} {d1:>+8.4f} {d3:>+8.4f}  {way:<9}  {series[a][-1]['Observation status']}")
out.sort(reverse=True)
print("  highest to lowest: " + " > ".join(f"{a} {v:.4f}" for v, a in out))
print(f"  above 100 (long-term average): {', '.join(a for v, a in out if v > 100) or 'none'}")

today = datetime.now(timezone.utc)
print(f"\nOECD ({today.year}), Composite leading indicators, OECD Data Explorer, "
      f"https://data-explorer.oecd.org/vis?df[ds]=dsDisseminateFinalDMZ&df[id]=DSD_STES%40DF_CLI&df[ag]=OECD.SDD.STES "
      f"(accessed on {today.day} {today:%B %Y}).")
print("Changes computed by us from the OECD values (1- and 3-month differences, ordering); the values are not rounded.")
```

Output (from the run on 2026-11-14, 23:37 UTC, second session; the first session at 23:34 UTC printed the same):

```text
Composite leading indicators (OECD.SDD.STES:DSD_STES@DF_CLI(4.1)): Composite leading indicator (CLI), Amplitude adjusted, Index, OECD harmonised; long-term average = 100

Latest month: 2026-10 (months in answer 2026-07..2026-10)
                        CLI   1m chg   3m chg  direction  status
  United States    100.9566  +0.0256  +0.1387  rising     Normal value
  Germany          101.1611  +0.1422  +0.4368  rising     Normal value
  Japan            100.2095  -0.0200  -0.0293  falling    Normal value
  highest to lowest: DEU 101.1611 > USA 100.9566 > JPN 100.2095
  above 100 (long-term average): DEU, USA, JPN

OECD (2026), Composite leading indicators, OECD Data Explorer, https://data-explorer.oecd.org/vis?df[ds]=dsDisseminateFinalDMZ&df[id]=DSD_STES%40DF_CLI&df[ag]=OECD.SDD.STES (accessed on 14 November 2026).
Changes computed by us from the OECD values (1- and 3-month differences, ordering); the values are not rounded.
```

### 2. robots.txt, dataflow discovery and error shapes (browser)

Same tab, 8 same-origin `fetch()` calls. `dataflow/all` is about 9 MB of SDMX-ML, so the page lists it and sends back only agency, id, version and English name.

```python
import csv, io, json, time

SITE = "https://sdmx.oecd.org"
REST = SITE + "/public/rest/"
CLI = "data/OECD.SDD.STES,DSD_STES@DF_CLI/"
Q = "?lastNObservations=1&dimensionAtObservation=AllDimensions&format=csvfilewithlabels"

START_JS = """(() => { window.__oe = window.__oe || {}; const id = String(Math.random()).slice(2); window.__oe[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__oe[id] = {status: r.status, type: r.headers.get('content-type'),
      bytes: t.length, text: %s}; })
    .catch(e => { window.__oe[id] = {status: 0, type: '', bytes: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__oe[%s]; if (v) delete window.__oe[%s]; return v; })()"""
KEEP_TEXT = "t"
# dataflow/all is about 9 MB of XML: list it inside the page and send back only id, version and English name.
LIST_FLOWS = r"""JSON.stringify([...t.matchAll(/<structure:Dataflow [\s\S]*?<\/structure:Dataflow>/g)].map(m => {
  const h = m[0].match(/^<structure:Dataflow [^>]*?id="([^"]+)"[^>]*?agencyID="([^"]+)"[^>]*?version="([^"]+)"/);
  const n = m[0].match(/<common:Name xml:lang="en">([^<]*)/); return [h[2], h[1], h[3], n ? n[1] : ""]; }))"""

def fetch(u, text_js=KEEP_TEXT, timeout=90):
    """One same-origin fetch from the tab -> dict(status, type, bytes, text). No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % (json.dumps(u), text_js)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"no answer after {timeout}s: {u}")
        time.sleep(0.3)
    time.sleep(1.0)
    return r

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(REST + CLI + "USA.M.LI...AA...H?lastNObservations=1&format=jsondata")
    wait_for_load()

r = fetch(SITE + "/robots.txt")
print(f"sdmx.oecd.org/robots.txt: HTTP {r['status']} {r['type']}, title {r['text'].split('<title>')[1].split('</title>')[0]!r}" if "<title>" in r["text"]
      else f"sdmx.oecd.org/robots.txt: HTTP {r['status']} {r['type']} {r['text'][:200]!r}")

# Discovery: every dataflow, then the ones about leading indicators.
r = fetch(REST + "dataflow/all", LIST_FLOWS)
if r["status"] != 200:
    raise RuntimeError(f"dataflow/all HTTP {r['status']}: stop")
flows = json.loads(r["text"])
print(f"\ndataflow/all: HTTP 200, {r['bytes']:,} characters of SDMX-ML, {len(flows)} dataflows, "
      f"{sum(1 for f in flows if not f[3])} without an English name")
for ag, fid, ver, name in flows:
    if "leading" in name.lower():
        print(f"  {ag},{fid} v{ver}  {name}")

print()
for label, path in (
    ("USA+DEU+JPN, headline CLI        ", CLI + "USA+DEU+JPN.M.LI...AA...H" + Q),
    ("unknown area XXX next to USA     ", CLI + "USA+XXX.M.LI...AA...H" + Q),
    ("only an unknown area XXX         ", CLI + "XXX.M.LI...AA...H" + Q),
    ("3-part key (needs 9 parts)       ", CLI + "USA.M.LI" + Q),
    ("misspelt dataflow DF_CLIX        ", "data/OECD.SDD.STES,DSD_STES@DF_CLIX/USA.M.LI...AA...H" + Q),
    ("every USA series in DF_CLI       ", CLI + "USA.M......." + Q),
):
    r = fetch(REST + path)
    if r["status"] == 200 and "csv" in (r["type"] or ""):
        rows = list(csv.DictReader(io.StringIO(r["text"])))
        ends = sorted({(x["MEASURE"], x["ADJUSTMENT"], x["TRANSFORMATION"], x["TIME_PERIOD"]) for x in rows})
        brief = ", ".join(f"{x['REF_AREA']} {x['TIME_PERIOD']} {x['OBS_VALUE']}" for x in rows) if len(rows) <= 3 else \
            f"{len(rows)} series; latest month per series ranges {min(e[3] for e in ends)}..{max(e[3] for e in ends)}"
        print(f"{label} HTTP 200 {brief}")
    else:
        print(f"{label} HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:120]!r}")
```

Output (from the run on 2026-11-14, 23:37 UTC):

```text
sdmx.oecd.org/robots.txt: HTTP 404 text/html, title '404 - File or directory not found.'

dataflow/all: HTTP 200, 8,880,735 characters of SDMX-ML, 1553 dataflows, 1 without an English name
  OECD.SDD.STES,DSD_STES@DF_CLI v4.1  Composite leading indicators

USA+DEU+JPN, headline CLI         HTTP 200 JPN 2026-10 100.2095, DEU 2026-10 101.1611, USA 2026-10 100.9566
unknown area XXX next to USA      HTTP 200 USA 2026-10 100.9566
only an unknown area XXX          HTTP 404 text/plain 'NoRecordsFound'
3-part key (needs 9 parts)        HTTP 403 text/plain 'Not enough key values in query, expecting 9 got 3'
misspelt dataflow DF_CLIX         HTTP 404 text/plain 'Could not find Dataflow and/or DSD related with this data request'
every USA series in DF_CLI        HTTP 200 16 series; latest month per series ranges 2026-05..2026-10
```

### 3. Same comparison with Python urllib and SDMX-JSON, 13 months (no browser)

Reads `format=jsondata` and decodes the observation keys itself. Compares the latest common month with the month before and with the same month a year earlier.

```python
import json, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

AREAS = ["USA", "DEU", "JPN"]
URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI/" + "+".join(AREAS) + ".M.LI...AA...H?"
       + urllib.parse.urlencode({"lastNObservations": 13, "dimensionAtObservation": "AllDimensions", "format": "jsondata"}))
# Python's default "Python-urllib/3.x" User-Agent gets HTTP 403 "error code: 1010" from the API's Cloudflare front.
# Send an honest User-Agent that names your client (not a browser string).
UA = {"User-Agent": "oecd-cli-example/1.0 (+https://github.com/browser-use/browser-harness)", "Accept": "application/json"}

def get(url):
    """-> SDMX-JSON 1.0 dict. Errors are short text/plain bodies; exits on them."""
    time.sleep(1.0)  # OECD rate-limits the API (number not published): one request at a time
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {' '.join(e.read().decode(errors='replace').split())[:200]}")

def observations(d):
    """SDMX-JSON (dimensionAtObservation=AllDimensions) -> (list of ({dim: code}, value, {attr: code}), {dim: {code: name}}).
    Keys like "2:0:0:0:0:0:0:0:0:3" index each observation dimension's "values" list, in order."""
    st = d["data"]["structure"]
    dims = st["dimensions"]["observation"]
    attrs = st["attributes"]["observation"]
    out = []
    for key, arr in d["data"]["dataSets"][0]["observations"].items():
        codes = {dim["id"]: dim["values"][int(i)]["id"] for dim, i in zip(dims, key.split(":"))}
        at = {a["id"]: (a["values"][j]["id"] if j is not None and a["values"] else None) for a, j in zip(attrs, arr[1:])}
        out.append((codes, arr[0], at))
    return out, {dim["id"]: {v["id"]: v["name"] for v in dim["values"]} for dim in dims}

d = get(URL)
obs, names = observations(d)
s = {}
for codes, v, at in obs:
    if (codes["MEASURE"], codes["ADJUSTMENT"], codes["METHODOLOGY"]) != ("LI", "AA", "H"):
        sys.exit(f"unexpected series {codes}")
    s.setdefault(codes["REF_AREA"], {})[codes["TIME_PERIOD"]] = (v, at.get("OBS_STATUS"))
if set(AREAS) - set(s):
    sys.exit(f"missing areas: {sorted(set(AREAS) - set(s))}")
common = sorted(set.intersection(*(set(s[a]) for a in AREAS)))
if len(common) < 13:
    sys.exit(f"only {len(common)} common months: {common}")
m, m_1, m_12 = common[-1], common[-2], common[0]
print(f"{d['data']['structure']['name']}: amplitude adjusted CLI, long-term average = 100; prepared {d['meta']['prepared']}")
print(f"latest common month {m}; compared with {m_1} and {m_12}")
for a in sorted(AREAS, key=lambda a: -s[a][m][0]):
    v = s[a][m][0]
    print(f"  {names['REF_AREA'][a]:<14} {v:.4f}  vs {m_1}: {v - s[a][m_1][0]:+.4f}  vs {m_12}: {v - s[a][m_12][0]:+.4f}"
          f"  {'above' if v > 100 else 'below'} 100  status {s[a][m][1]}")
peak = {a: max(common, key=lambda t: s[a][t][0]) for a in AREAS}
print("highest month in the last 13: " + ", ".join(f"{a} {peak[a]} {s[a][peak[a]][0]:.4f}" for a in AREAS))

today = datetime.now(timezone.utc)
print(f"\nOECD ({today.year}), Composite leading indicators, OECD Data Explorer, "
      "https://data-explorer.oecd.org/vis?df[ds]=dsDisseminateFinalDMZ&df[id]=DSD_STES%40DF_CLI&df[ag]=OECD.SDD.STES "
      f"(accessed on {today.day} {today:%B %Y}). Differences computed by us.")
```

Output (from the run on 2026-11-14, 23:35 UTC):

```text
Composite leading indicators: amplitude adjusted CLI, long-term average = 100; prepared 2026-11-14T23:35:56Z
latest common month 2026-10; compared with 2026-09 and 2025-10
  Germany        101.1611  vs 2026-09: +0.1422  vs 2025-10: +0.6774  above 100  status A
  United States  100.9566  vs 2026-09: +0.0256  vs 2025-10: +1.2722  above 100  status A
  Japan          100.2095  vs 2026-09: -0.0200  vs 2025-10: +0.4264  above 100  status A
highest month in the last 13: USA 2026-10 100.9566, DEU 2026-10 101.1611, JPN 2026-08 100.2432

OECD (2026), Composite leading indicators, OECD Data Explorer, https://data-explorer.oecd.org/vis?df[ds]=dsDisseminateFinalDMZ&df[id]=DSD_STES%40DF_CLI&df[ag]=OECD.SDD.STES (accessed on 14 November 2026). Differences computed by us.
```

### 4. curl, headers, the User-Agent trap and robots files

```bash
U='https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI/USA+DEU+JPN.M.LI...AA...H'
# latest headline CLI per country (csvfilewithlabels: one row per observation, codes and labels side by side)
curl -sS --fail "$U?lastNObservations=1&dimensionAtObservation=AllDimensions&format=csvfilewithlabels" | python3 -c '
import csv, sys
rows = list(csv.DictReader(sys.stdin))
if len(rows) != 3: sys.exit(f"expected 3 rows, got {len(rows)}")
for r in sorted(rows, key=lambda r: -float(r["OBS_VALUE"])):
    print(r["TIME_PERIOD"], r["REF_AREA"], r["Reference area"], r["OBS_VALUE"], r["Adjustment"], r["Observation status"])'
sleep 1
# headers: no rate-limit headers; Cloudflare in front; 2 h public cache
curl -sS -D - -o /dev/null "$U?lastNObservations=1&format=csvfilewithlabels" | grep -iE '^(HTTP|content-type|cache-control|server|x-ratelimit|ratelimit|retry-after)' | tr -d '\r'
sleep 1
# the User-Agent trap: Python's default UA string is refused at the edge
curl -sS -A 'Python-urllib/3.12' -o /dev/null -w 'UA Python-urllib/3.12 -> HTTP %{http_code}\n' "$U?lastNObservations=1&format=jsondata"
sleep 1
curl -sS -o /dev/null -w 'sdmx.oecd.org/robots.txt HTTP %{http_code} %{content_type}\n' https://sdmx.oecd.org/robots.txt
sleep 1
curl -sS https://www.oecd.org/robots.txt | grep -iE '^(user-agent|disallow|allow)' | tr -d '\r' | paste -sd' ' -
```

Output (from the run on 2026-11-14, 23:36 UTC):

```text
2026-10 DEU Germany 101.1611 Amplitude adjusted Normal value
2026-10 USA United States 100.9566 Amplitude adjusted Normal value
2026-10 JPN Japan 100.2095 Amplitude adjusted Normal value
HTTP/2 200 
content-type: application/vnd.sdmx.data+csv; labels=name; version=2; charset=utf-8
cache-control: public,max-age=7200
server: cloudflare
UA Python-urllib/3.12 -> HTTP 403
sdmx.oecd.org/robots.txt HTTP 404 text/html
User-agent: * Disallow: /content/dam/oecd/ Disallow: /adobe/dynamicmedia/deliver/ User-agent: Twitterbot Allow: / User-agent: Googlebot Allow: / User-agent: Spacecat/1.0 Allow: /
```

## Fields (DF_CLI, `format=csvfilewithlabels`)

Each code column is followed by its label column. Labels quoted from the API answer.

| Field | Notes |
|---|---|
| `STRUCTURE_ID`, `STRUCTURE_NAME` | `OECD.SDD.STES:DSD_STES@DF_CLI(4.1)`, "Composite leading indicators" |
| `REF_AREA` | ISO alpha-3 codes. With `LI.AA.H`, 22 areas had 2026-10: 17 countries (AUS, BRA, CAN, CHN, DEU, ESP, FRA, GBR, IDN, IND, ITA, JPN, KOR, MEX, TUR, USA, ZAF) and the aggregates A5M, G20, G4E, G7, NAFTA |
| `FREQ` | `M` monthly (the dataflow also has `Q`) |
| `MEASURE` | `LI` "Composite leading indicator (CLI)"; also `BCICP` / `CCICP` business and consumer confidence, `RS` "Reference series (GDP)" and many `LOCO*` component series |
| `ADJUSTMENT` | `AA` "Amplitude adjusted" (headline), `NOR` "Normalized", `TR` "Trend restored", `T` "Trend", `RT` "Ratio to trend", `Y` |
| `TRANSFORMATION` | `IX` "Index", `GY` "Growth rate, over 1 year" (with `TR`) |
| `METHODOLOGY` | `H` "OECD harmonised", `N` |
| `TIME_PERIOD`, `OBS_VALUE` | `YYYY-MM`; values such as `100.9566` or `95.99793` |
| `OBS_STATUS` | `A` "Normal value" for all three on 2026-10 |
| `UNIT_MULT`, `DECIMALS` | `0` "Units", `2` "Two" (yet the headline CLI values carry 4 decimals, e.g. `100.9566`) |
| SDMX-JSON (`format=jsondata`) | `data.dataSets[0].observations` keyed `"i:j:...:k"`, one index per `data.structure.dimensions.observation` entry in order; value array is `[OBS_VALUE, attribute indexes...]`; `meta.prepared` is the answer time |

## Gotchas

- **`lastNObservations` counts per series**, not per dataflow. For the three headline CLIs it gave 2026-10 for all; across the 16 US series in DF_CLI, the latest month ranged from 2026-05 to 2026-10 (the GDP reference series ended at 2026-08). Block 1 stops if the countries end in different months.
- **The key needs all 9 parts.** `USA.M.LI` is HTTP 403 (not 400) `Not enough key values in query, expecting 9 got 3`; `USA.M......` (8 parts) is also 403 `expecting 9 got 8`. Empty parts mean "any"; `+` joins codes.
- **Errors are short text/plain bodies, not SDMX.** `NoRecordsFound` (404) when nothing matches, `Could not find Dataflow and/or DSD related with this data request` (404) for a misspelt dataflow. Unknown codes next to known ones are dropped silently (HTTP 200).
- **User-Agent.** Python's default `Python-urllib/3.12` got HTTP 403 `error code: 1010` (Cloudflare); `python-requests/2.32.3`, curl's default, an empty one and a descriptive one got 200 (5 probes, 23:31 UTC). The cloud browser's Chrome User-Agent got 200. Send an honest User-Agent naming your client; do not pose as a browser.
- **Level is relative to each country's own long-term average.** The indicator page: "measured as an amplitude adjusted index, long-term average = 100", so a higher CLI means further above that country's own long-term average, not a bigger economy; the OECD stresses direction ("increase or decrease") over amplitude.
- **`csvfilewithlabels` downloads in a tab** (`content-disposition: attachment`). Open `format=jsondata` in the tab and `fetch()` the CSV.
- **Caching.** `cache-control: public,max-age=7200` and Cloudflare `cf-cache-status: HIT` (age 365 s on one call): an answer can be up to 2 h old. SDMX-JSON `meta.prepared` shows when it was built.
- **`dataflow/all` is 8.9 MB** of SDMX-ML: 1553 dataflows, one (`DSD_TQ_SURVEY@DF_TRUTH_QUEST`) without an English name. A regex that skips to the next `<common:Name>` across dataflow boundaries mislabels the rest; split on `</structure:Dataflow>` first (block 2 does).
- **The agency can be omitted:** `data/DSD_STES@DF_CLI/...` also returned the CSV. Keep it in for clarity.
- **`NonProductionDataflow`.** DF_CLI carries an annotation `NonProductionDataflow` = `true`; its meaning is not documented in the pages read. The data was served normally.
- **Tab marker.** The harness prefixes tab titles with a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **The CLI methodology PDF** (`https://www.oecd.org/content/dam/oecd/en/data/methods/OECD-System-of-Composite-Leading-Indicators.pdf`, linked from the API answer): `/content/dam/oecd/` is disallowed for `*` in www.oecd.org/robots.txt. Not fetched.
- **A tab on a `csvfilewithlabels` URL**: downloads instead of rendering (see block 1).
- **Python urllib with its default User-Agent**: HTTP 403 (see Gotchas).
- **Not tested:** the SDMX 2.1 `availableconstraint` endpoint (the Data Explorer calls it), reference-metadata queries (a `v2/metadata/metadataset/*/*/*` guess was HTTP 400), `startPeriod`/`endPeriod` filters, the Data Explorer "source" tab, other dataflows, and rate-limit behaviour (never provoked).
