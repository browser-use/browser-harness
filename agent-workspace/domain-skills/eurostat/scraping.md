# Eurostat - Rank EU Countries by the Latest Seasonally Adjusted Unemployment Rate (official keyless API)

Field-tested against ec.europa.eu on 2026-11-13 using a fresh Browser Use cloud browser (logged out, two short sessions) plus Python `urllib` and `curl` from a Linux server. 3 browser page loads and 21 in-page `fetch()` calls, 29 curl calls (API, robots.txt, docs, copyright pages) and 2 urllib calls, all serial at 1 s or more spacing: every API call was HTTP 200 except the deliberate 400/404/413 probes below. No 429, no challenge, no key, no login, no cookie needed.

robots.txt (checked 2026-11-13, curl and the cloud browser): https://ec.europa.eu/robots.txt has three groups, `Baiduspider`, `Twitterbot` and `*`. There are no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot, Bytespider, Applebot-Extended and Meta-ExternalAgent all follow `*`. No `*` rule matches `/eurostat/api/`: under `/eurostat/` it disallows only the legacy `/eurostat/SDMX/diss-web/rest/`, `/eurostat/search`, `/eurostat/tgm/`, `/eurostat/fr/`, `/eurostat/de/` and some portal search and login patterns (block 2 prints all 12). An RFC 9309 matcher (longest match, `*` wildcards) gives ALLOW for `/eurostat/api/dissemination/statistics/1.0/data/une_rt_m` for `*` and all 14 named agents. Terms: Eurostat's "Copyright notice and free re-use of data" (https://ec.europa.eu/eurostat/web/main/help/copyright-notice): "Reuse of statistical data, metadata, publications, and other dissemination tools published on this website for commercial or non-commercial purposes is authorised provided the source is acknowledged." Exceptions: "Logos and trademarks are excluded from the above mentioned general permission"; data "for countries other than" EU, EFTA and "official EU acceding and candidate countries" is non-commercial only ("Examples are data for the United States of America, Japan or China. In such cases, the user will need to eliminate these data from the tables before reusing them commercially."). `une_rt_m` carries UK, US and JP, so this skill requests only EU, EFTA and candidate codes. Changes must be disclosed: "When reuse involves ... modifications to the data or text, this must be stated clearly to the end user of the information. A disclaimer regarding the non-responsibility of Eurostat shall be included." The Commission legal notice (https://commission.europa.eu/legal-notice_en) licenses EU-owned content under CC BY 4.0 and says "trade marks, registered designs, logos and names, are excluded from the Commission's reuse policy and are not licensed to you": this skill writes "Eurostat" only as the data source in the citation the copyright notice asks for, in plain text, with no logo. Its one AI statement is about the Commission's own pages ("may contain text or audiovisual content which has been partially created with the assistance of artificial intelligence tools"). No AI/ML, scraping, automated-access or non-commercial clause for EU/EFTA/candidate data. This skill is not affiliated with or endorsed by Eurostat or the European Commission.

**Citation and changes:** for "Customised versions of a dataset" the copyright notice asks for "Source: [Eurostat dataset datacode link], [access date]". Blocks 1 and 3 print `Source: Eurostat (online data code: une_rt_m, https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table), accessed 2026-11-13.` and state the change: the data is filtered to the 27 Member States (block 3: also EFTA and candidates) and ranked by us, and Eurostat is not responsible for the ranking. The values themselves are not changed or rounded.

## Quick summary

- **No scraping.** `GET https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m?s_adj=SA&age=TOTAL&sex=T&unit=PC_ACT&sinceTimePeriod=2026-05&geo=BE&geo=BG&...&lang=EN` returns JSON-stat 2.0. With every other dimension pinned to one position, `value` is a sparse object keyed by the flat index `geo_index * n_months + month_index`; a missing key means no data. No key, `Access-Control-Allow-Origin: *`.
- **Answer (2026-11-13, 23:37 UTC; dataset `updated` 2026-11-05):** September 2026 is the latest month with all 27 Member States. Highest: **Finland 11.0%**, Spain 10.3, Sweden 8.6, France 8.5, Estonia 8.0. Lowest: **Czechia 2.8%**, then Bulgaria, Malta and Poland 3.4, Slovenia 3.6. EU27_2020: 6.2. Only Ireland has October (4.8), so it is not ranked on that month.
- **Use `sinceTimePeriod`, not `lastTimePeriod=1`.** `lastTimePeriod=1` returns the dataset-wide latest month (2026-10, which only Ireland had) and **0 values** for DE, FR, ES and EU27_2020. Request a few months back and pick the latest month every country has.
- **Silent misses are HTTP 200.** An unknown geo code (`XX`) is dropped from the answer; a bad dimension code (`s_adj=XX`) returns zero values. Check that every requested code came back.
- **EU, EFTA and candidate codes only.** UK, US and JP are in `une_rt_m` but are non-commercial only under the copyright notice; the blocks never request them. Greece is `EL`.
- **Big extracts: HTTP 413** `ASYNCHRONOUS_RESPONSE`. Docs: under 500,000 cells is synchronous, 500,000 to 5,000,000 is asynchronous, above that is an error; cached answers come back directly. A 413 means the extraction was queued: "API Statistics will not notify the user when the file is ready, the request must be made again to check its status." The ranking query is 28 geos x 6 months = 168 cells.
- **Rate limit:** none published and no rate-limit headers (block 4). Fair-use guidance: "trigger 1 extraction request at a time", "in case of use of scripts, don't use parallelisation"; heavy use is "forced to be processed asynchronously". The ranking blocks make 1 (block 1) or 2 (block 3) API calls, 1 s apart.

## What works

### 1. Rank the 27 EU Member States, latest common month (browser)

`on_api_tab()` opens one small API answer on ec.europa.eu, so `fetch()` is same-origin. `get()` returns parsed JSON-stat on HTTP 200, waits 30 s once on 429/5xx and otherwise raises, including on `{"error": ...}` bodies, so an error never looks like data. The block checks that all 28 codes and all four filters came back, picks the latest month with all 27 values, ranks with shared ranks for ties, prints flags with Eurostat's own labels, then the citation and the change note.

```python
import json, time, urllib.parse
from datetime import datetime, timezone

# The 27 EU Member States in Eurostat's codes (Glossary:Country_codes; Greece is EL, not GR).
EU27 = "BE BG CZ DK DE EE IE EL ES FR HR IT CY LV LT LU HU MT NL AT PL PT RO SI SK FI SE".split()
AGG = "EU27_2020"  # the EU aggregate, printed for reference, never ranked
FILTER = [("s_adj", "SA"), ("age", "TOTAL"), ("sex", "T"), ("unit", "PC_ACT")]  # seasonally adjusted, all ages, both sexes, % of labour force
MONTHS_BACK = 6  # countries publish with different lags; on 2026-11-13 all 27 had values for 2026-05..2026-09

SITE = "https://ec.europa.eu"
API = SITE + "/eurostat/api/dissemination/statistics/1.0/data/une_rt_m"
PAUSE = 1.0  # fair use: "trigger 1 extraction request at a time", "don't use parallelisation"; no published rate number

def url(params):
    return API + "?" + urllib.parse.urlencode(params + [("lang", "EN")])

def on_api_tab():
    """fetch() runs same-origin from a logged-out ec.europa.eu tab that shows one small API answer. Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(url(FILTER + [("geo", AGG), ("time", "2026-01")]))
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"UNE_RT_M"' not in body:
        raise RuntimeError(f"ec.europa.eu did not serve the une_rt_m API answer (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__es = window.__es || {}; const id = String(Math.random()).slice(2); window.__es[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { window.__es[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__es[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__es[%s]; if (v) delete window.__es[%s]; return v; })()"""

def get(params, timeout=60):
    """GET une_rt_m?params from inside the tab -> parsed JSON-stat 2.0. Errors are {"error": [{"status", "id", "label"}]};
    a too-big extraction is HTTP 413 {"error": [{"id": 413, "label": "ASYNCHRONOUS_RESPONSE. ..."}]}; the docs show the
    same label under "warning". All of these raise here. A 413 is not a final no: Eurostat queues the extraction and
    the same request must be sent again later to fetch it. This helper does not do that, so narrow the filters instead.
    Waits 30 s once on 429/5xx or a network error, raises on anything else."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url(params))))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"no answer after {timeout}s: {url(params)}")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        d = json.loads(r["text"]) if "json" in (r["type"] or "") else None
        if r["status"] != 200 or not isinstance(d, dict) or "error" in d or "warning" in d or d.get("class") != "dataset":
            raise RuntimeError(f"HTTP {r['status']} {' '.join(r['text'].split())[:240]!r}; stopping")
        return d

def cells(d):
    """JSON-stat 2.0 -> {(geo, month): (value, flag)}. value is a flat index (row-major over d["id"]); with every other
    dimension filtered to one position that is geo_index * n_months + month_index. Sparse: missing keys = no data."""
    for dim, n in zip(d["id"], d["size"]):
        if dim not in ("geo", "time") and n != 1:
            raise RuntimeError(f"dimension {dim} has {n} positions; the filter did not pin it: stop")
    gi, ti = d["dimension"]["geo"]["category"]["index"], d["dimension"]["time"]["category"]["index"]
    nt = len(ti)
    v, st = d["value"], d.get("status") or {}
    get_v = (lambda k: v.get(str(k))) if isinstance(v, dict) else (lambda k: v[k])
    get_s = (lambda k: st.get(str(k), "")) if isinstance(st, dict) else (lambda k: st[k] or "")
    out = {}
    for g, i in gi.items():
        for m, j in ti.items():
            x = get_v(i * nt + j)
            if x is not None:
                out[(g, m)] = (x, get_s(i * nt + j))
    return out

on_api_tab()
today = datetime.now(timezone.utc).date()
y, m = divmod(today.year * 12 + today.month - 1 - MONTHS_BACK, 12)
since = f"{y}-{m + 1:02d}"
d = get(FILTER + [("sinceTimePeriod", since)] + [("geo", g) for g in EU27 + [AGG]])

# Unknown geo codes are dropped silently (HTTP 200), so check every requested code came back.
geo = d["dimension"]["geo"]["category"]
missing = set(EU27 + [AGG]) - set(geo["index"])
if missing:
    raise RuntimeError(f"geo codes not in the answer: {sorted(missing)}; stop")
for dim, code in FILTER:
    got = list(d["dimension"][dim]["category"]["index"])
    if got != [code]:
        raise RuntimeError(f"{dim}: asked {code}, got {got}: stop")
c = cells(d)
months = sorted(d["dimension"]["time"]["category"]["index"])
flag_names = (d.get("extension", {}).get("status") or {}).get("label", {})
print(f"{d['label']} (une_rt_m), updated {d['updated']}; months in answer {months[0]}..{months[-1]}")
print("  filter: " + "; ".join(f"{k}={v} ({d['dimension'][k]['category']['label'][v]})" for k, v in FILTER))

# Reference month = the latest month in which all 27 Member States have a value.
full = [mo for mo in months if all((g, mo) in c for g in EU27)]
if not full:
    raise RuntimeError(f"no month since {since} has all 27 Member States: raise MONTHS_BACK")
ref = full[-1]
print(f"  values per month (of 27): " + ", ".join(f"{mo} {sum((g, mo) in c for g in EU27)}" for mo in months))

rows = sorted(((c[(g, ref)][0], g) for g in EU27), key=lambda r: (-r[0], r[1]))
print(f"\nEU Member States by seasonally adjusted unemployment rate, {ref} (highest first, % of labour force):")
rank = 0
for i, (val, g) in enumerate(rows):
    if i == 0 or val != rows[i - 1][0]:
        rank = i + 1  # ties share a rank (1, 2, 2, 4)
    fl = c[(g, ref)][1]
    print(f"  {rank:>2}. {g}  {geo['label'][g]:<12} {val:>5.1f}" + (f"  [{fl}: {flag_names.get(fl, fl)}]" if fl else ""))
agg = c.get((AGG, ref))
print(f"  for reference, {AGG} ({geo['label'][AGG]}): " + (f"{agg[0]:.1f} {agg[1]}".rstrip() if agg else f"no value for {ref}"))

newer = [(g, mo, c[(g, mo)][0]) for g in EU27 for mo in months if mo > ref and (g, mo) in c]
if newer:
    print(f"  newer than {ref}, not ranked (other countries have no value yet): "
          + ", ".join(f"{g} {mo} {v:.1f}" for g, mo, v in newer))

print(f"\nSource: Eurostat (online data code: une_rt_m, https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table), accessed {today}.")
print("Modified: filtered to the 27 EU Member States and ranked by us; Eurostat is not responsible for this ranking.")
```

Output (from the run on 2026-11-13, 23:37 UTC):

```text
Unemployment by sex and age - monthly data (une_rt_m), updated 2026-11-05T23:00:00+0100; months in answer 2026-05..2026-10
  filter: s_adj=SA (Seasonally adjusted data, not calendar adjusted data); age=TOTAL (Total); sex=T (Total); unit=PC_ACT (Percentage of population in the labour force)
  values per month (of 27): 2026-05 27, 2026-06 27, 2026-07 27, 2026-08 27, 2026-09 27, 2026-10 1

EU Member States by seasonally adjusted unemployment rate, 2026-09 (highest first, % of labour force):
   1. FI  Finland       11.0
   2. ES  Spain         10.3
   3. SE  Sweden         8.6
   4. FR  France         8.5
   5. EE  Estonia        8.0
   6. EL  Greece         7.6
   7. LU  Luxembourg     7.3
   7. LV  Latvia         7.3
   9. DK  Denmark        6.8
  10. AT  Austria        6.3
  10. IT  Italy          6.3
  10. RO  Romania        6.3
  13. LT  Lithuania      6.2
  14. BE  Belgium        6.0
  15. SK  Slovakia       5.7
  16. PT  Portugal       5.6
  17. IE  Ireland        4.7
  18. HU  Hungary        4.6
  19. HR  Croatia        4.3
  20. DE  Germany        4.1
  21. CY  Cyprus         4.0
  21. NL  Netherlands    4.0
  23. SI  Slovenia       3.6
  24. BG  Bulgaria       3.4
  24. MT  Malta          3.4
  24. PL  Poland         3.4
  27. CZ  Czechia        2.8
  for reference, EU27_2020 (European Union - 27 countries (from 2020)): 6.2
  newer than 2026-09, not ranked (other countries have no value yet): IE 2026-10 4.8

Source: Eurostat (online data code: une_rt_m, https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table), accessed 2026-11-13.
Modified: filtered to the 27 EU Member States and ranked by us; Eurostat is not responsible for this ranking.
```

### 2. robots.txt, time filters and error shapes (browser)

Same tab, 9 same-origin `fetch()` calls: robots.txt, three ways to ask for "latest", two silent misses, and three errors.

```python
import json, time, urllib.parse

SITE = "https://ec.europa.eu"
API = SITE + "/eurostat/api/dissemination/statistics/1.0/data/"
SA = "s_adj=SA&age=TOTAL&sex=T&unit=PC_ACT"

START_JS = """(() => { window.__es = window.__es || {}; const id = String(Math.random()).slice(2); window.__es[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__es[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__es[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__es[%s]; if (v) delete window.__es[%s]; return v; })()"""

def fetch(u, timeout=60):
    """One same-origin fetch from the tab -> (status, content type, body). No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(u)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"no answer after {timeout}s: {u}")
        time.sleep(0.3)
    time.sleep(1.0)
    return r["status"], r["type"] or "", r["text"]

def brief(text):
    d = json.loads(text)
    if "error" in d or "warning" in d:
        return json.dumps(d.get("error") or d.get("warning"))[:260]
    t = list(d["dimension"]["time"]["category"]["index"])
    g = list(d["dimension"]["geo"]["category"]["index"])
    n = len(d["value"]) if isinstance(d["value"], dict) else sum(x is not None for x in d["value"])
    return f"geo {g if len(g) < 6 else str(len(g)) + ' codes'}, time {t if len(t) < 6 else str(len(t)) + ' months'}, {n} values"

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(API + "une_rt_m?" + SA + "&geo=EU27_2020&time=2026-01&lang=EN")
    wait_for_load()

s, t, body = fetch(SITE + "/robots.txt")
groups = [l.split(":", 1)[1].strip() for l in body.splitlines() if l.lower().startswith("user-agent")]
api_rules = [l for l in body.splitlines() if l.lower().startswith(("disallow", "allow")) and "/eurostat/api" in l]
print(f"robots.txt: HTTP {s}, user-agent groups {groups}, rules naming /eurostat/api: {api_rules or 'none'}")
es = list(dict.fromkeys(l.split(":", 1)[1].strip() for l in body.splitlines() if l.lower().startswith("disallow") and "/eurostat/" in l))
print(f"  {len(es)} distinct Disallow rules under /eurostat/: {es}\n")

for label, path in (
    ("lastTimePeriod=1                ", f"une_rt_m?{SA}&lastTimePeriod=1&geo=DE&geo=FR&geo=ES&geo=EU27_2020"),
    ("lastTimePeriod=2                ", f"une_rt_m?{SA}&lastTimePeriod=2&geo=DE&geo=FR&geo=ES&geo=EU27_2020"),
    ("sinceTimePeriod=2026-08         ", f"une_rt_m?{SA}&sinceTimePeriod=2026-08&geo=DE&geo=FR&geo=ES&geo=EU27_2020"),
    ("unknown geo XX next to DE       ", f"une_rt_m?{SA}&time=2026-09&geo=DE&geo=XX"),
    ("s_adj=XX (bad code)             ", f"une_rt_m?s_adj=XX&age=TOTAL&sex=T&unit=PC_ACT&time=2026-09&geo=DE"),
    ("lastTimePeriod + sinceTimePeriod", f"une_rt_m?{SA}&lastTimePeriod=1&sinceTimePeriod=2026-08&geo=DE"),
    ("unknown dimension foo=1         ", f"une_rt_m?{SA}&time=2026-09&geo=DE&foo=1"),
    ("misspelt dataset une_rt_mx      ", "une_rt_mx?time=2026-09"),
):
    s, t, body = fetch(API + path + "&lang=EN")
    print(f"{label} HTTP {s} {brief(body)}")
```

Output (from the run on 2026-11-13, 23:37 UTC):

```text
robots.txt: HTTP 200, user-agent groups ['Baiduspider', 'Twitterbot', '*'], rules naming /eurostat/api: none
  12 distinct Disallow rules under /eurostat/: ['/eurostat/tgm/', '/eurostat/SDMX/diss-web/rest/', '/eurostat/*?*p_p_id=estatsearchportlet_WAR_estatsearchportlet', '/eurostat/*?*p_p_id=esssearchportlet_WAR_esssearchportlet', '/eurostat/home/-/search/data-browser', '/eurostat/group/*control_panel', '/eurostat/*com_liferay_login_web_portlet_LoginPortlet', '/eurostat/*doAsUserId', '/eurostat/search', '/eurostat/*/search/-/', '/eurostat/fr/', '/eurostat/de/']

lastTimePeriod=1                 HTTP 200 geo ['EU27_2020', 'DE', 'ES', 'FR'], time ['2026-10'], 0 values
lastTimePeriod=2                 HTTP 200 geo ['EU27_2020', 'DE', 'ES', 'FR'], time ['2026-09', '2026-10'], 4 values
sinceTimePeriod=2026-08          HTTP 200 geo ['EU27_2020', 'DE', 'ES', 'FR'], time ['2026-08', '2026-09', '2026-10'], 8 values
unknown geo XX next to DE        HTTP 200 geo ['DE'], time ['2026-09'], 1 values
s_adj=XX (bad code)              HTTP 200 geo ['DE'], time ['2026-09'], 0 values
lastTimePeriod + sinceTimePeriod HTTP 400 [{"status": 400, "id": 400, "label": "'TIME' parameter, 'TIME_PERIOD' parameter, 'lastTimePeriod' parameter and 'sinceTimePeriod' parameter cannot be set at the same time. Please choose one or the other."}]
unknown dimension foo=1          HTTP 400 [{"status": 400, "id": 150, "label": "INVALID_QUERY_DIMENSION: Query is invalid as per its structure's definition. Dimension \"FOO\" is not defined"}]
misspelt dataset une_rt_mx       HTTP 404 [{"status": 404, "id": 100, "label": "ERR_NOT_FOUND_4: UNE_RT_MX (DATA_FLOW:ALL,1.0) is not available for dissemination."}]
```

### 3. Same ranking with Python urllib, plus EFTA and candidate countries (no browser)

Python's default User-Agent got HTTP 200. The non-EU list uses the EFTA and candidate codes from Eurostat's Glossary:Country_codes (page last edited 22 January 2024) and shows each country's own latest month, unranked, because those months differ.

```python
import json, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

# Eurostat Glossary:Country_codes. Only these groups may be reused commercially (copyright notice);
# une_rt_m also carries UK, US and JP, which are non-commercial only, so they are never requested here.
EU27 = "BE BG CZ DK DE EE IE EL ES FR HR IT CY LV LT LU HU MT NL AT PL PT RO SI SK FI SE".split()
EFTA = "IS NO LI CH".split()
CANDIDATES = "BA ME MD MK GE AL RS TR UA".split()
AGG = "EU27_2020"
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m"
FILTER = [("s_adj", "SA"), ("age", "TOTAL"), ("sex", "T"), ("unit", "PC_ACT")]

def get(geos, since):
    """-> JSON-stat 2.0 dict. Python's default User-Agent got HTTP 200. Exits on {"error"} / {"warning"} bodies."""
    q = urllib.parse.urlencode(FILTER + [("sinceTimePeriod", since), ("lang", "EN")] + [("geo", g) for g in geos])
    time.sleep(1.0)  # one request at a time, no parallel calls (Eurostat fair-use guidance)
    try:
        with urllib.request.urlopen(f"{API}?{q}", timeout=60) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {' '.join(e.read().decode().split())[:240]}")
    if "error" in d or "warning" in d or d.get("class") != "dataset":
        sys.exit(f"no dataset: {json.dumps(d)[:240]}")
    return d

def series(d):
    """{geo: {month: value}} from the flat value index (geo_index * n_months + month_index; other dims pinned to 1)."""
    if any(n != 1 for dim, n in zip(d["id"], d["size"]) if dim not in ("geo", "time")):
        sys.exit(f"filter did not pin every dimension: {dict(zip(d['id'], d['size']))}")
    gi, ti = d["dimension"]["geo"]["category"]["index"], d["dimension"]["time"]["category"]["index"]
    v = d["value"]
    at = (lambda k: v.get(str(k))) if isinstance(v, dict) else (lambda k: v[k])
    return {g: {m: at(i * len(ti) + j) for m, j in ti.items() if at(i * len(ti) + j) is not None} for g, i in gi.items()}

today = datetime.now(timezone.utc).date()
y, m = divmod(today.year * 12 + today.month - 1 - 6, 12)
since = f"{y}-{m + 1:02d}"

d = get(EU27 + [AGG], since)
s = series(d)
if set(EU27 + [AGG]) - set(s):
    sys.exit(f"missing geo codes: {sorted(set(EU27 + [AGG]) - set(s))}")
months = sorted(d["dimension"]["time"]["category"]["index"])
ref = max((mo for mo in months if all(mo in s[g] for g in EU27)), default=None)
if ref is None:
    sys.exit("no month with all 27 Member States")
label = d["dimension"]["geo"]["category"]["label"]
rows = sorted(EU27, key=lambda g: (-s[g][ref], g))
print(f"une_rt_m updated {d['updated']}; ranking month {ref} (latest month with all 27 Member States)")
print("highest: " + ", ".join(f"{g} {s[g][ref]:.1f}" for g in rows[:5]))
print("lowest:  " + ", ".join(f"{g} {s[g][ref]:.1f}" for g in rows[-5:]))
print(f"{AGG}: {s[AGG].get(ref)}; spread {s[rows[0]][ref] - s[rows[-1]][ref]:.1f} points")

# Outside the EU: the EFTA and candidate codes une_rt_m carries. Not ranked with the EU; their latest month differs.
time.sleep(1.0)
o = get(EFTA + CANDIDATES, since)
os_ = series(o)
olabel = o["dimension"]["geo"]["category"]["label"]
print(f"\nEFTA and EU candidate countries in une_rt_m (asked {len(EFTA + CANDIDATES)} codes, answer has {sorted(os_)}):")
for g in EFTA + CANDIDATES:
    if g not in os_:
        print(f"  {g}: not in une_rt_m")
    elif not os_[g]:
        print(f"  {g} {olabel[g]}: in the dataset, no value since {since}")
    else:
        mo = max(os_[g])
        print(f"  {g} {olabel[g]:<24} {os_[g][mo]:>5.1f}  ({mo})")

print(f"\nSource: Eurostat (online data code: une_rt_m, https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table), accessed {today}.")
print("Modified: filtered and ranked by us; Eurostat is not responsible for this ranking.")
```

Output (from the run on 2026-11-13, 23:34 UTC):

```text
une_rt_m updated 2026-11-05T23:00:00+0100; ranking month 2026-09 (latest month with all 27 Member States)
highest: FI 11.0, ES 10.3, SE 8.6, FR 8.5, EE 8.0
lowest:  SI 3.6, BG 3.4, MT 3.4, PL 3.4, CZ 2.8
EU27_2020: 6.2; spread 8.2 points

EFTA and EU candidate countries in une_rt_m (asked 13 codes, answer has ['BA', 'CH', 'IS', 'MK', 'NO', 'TR']):
  IS Iceland                    5.9  (2026-09)
  NO Norway                     5.0  (2026-09)
  LI: not in une_rt_m
  CH Switzerland                5.1  (2026-06)
  BA Bosnia and Herzegovina    11.4  (2026-08)
  ME: not in une_rt_m
  MD: not in une_rt_m
  MK North Macedonia           10.7  (2026-09)
  GE: not in une_rt_m
  AL: not in une_rt_m
  RS: not in une_rt_m
  TR Türkiye                    8.4  (2026-09)
  UA: not in une_rt_m

Source: Eurostat (online data code: une_rt_m, https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table), accessed 2026-11-13.
Modified: filtered and ranked by us; Eurostat is not responsible for this ranking.
```

### 4. curl, the `lastTimePeriod` trap and headers

```bash
B=https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m
F='s_adj=SA&age=TOTAL&sex=T&unit=PC_ACT&lang=EN'
# September 2026 for four countries plus the EU; time= pins one month (no -g needed: no brackets in these URLs)
curl -sS --fail "$B?$F&time=2026-09&geo=ES&geo=FR&geo=DE&geo=PL&geo=EU27_2020" | python3 -c '
import json, sys
d = json.load(sys.stdin)
g = d["dimension"]["geo"]["category"]; nt = d["size"][d["id"].index("time")]
v = {code: d["value"].get(str(i * nt)) for code, i in g["index"].items()}
print("2026-09:", ", ".join(f"{k} {x}" for k, x in sorted(v.items(), key=lambda kv: -(kv[1] or 0))))'
sleep 1
# the trap: lastTimePeriod=1 is the dataset-wide latest month, which may have no value for your countries
curl -sS "$B?$F&lastTimePeriod=1&geo=ES&geo=FR&geo=DE" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("lastTimePeriod=1 ->", list(d["dimension"]["time"]["category"]["index"]), "values:", len(d["value"]))'
sleep 1
curl -sS -D - -o /dev/null "$B?$F&time=2026-09&geo=DE" | grep -iE '^(HTTP|content-type|access-control-allow-origin|x-ratelimit|retry-after)' | tr -d '\r'
sleep 1
curl -sS -o /dev/null -w 'robots.txt HTTP %{http_code}\n' https://ec.europa.eu/robots.txt
```

Output (from the run on 2026-11-13, 23:35 UTC):

```text
2026-09: ES 10.3, FR 8.5, EU27_2020 6.2, DE 4.1, PL 3.4
lastTimePeriod=1 -> ['2026-10'] values: 0
HTTP/1.1 200 OK
Content-Type: application/json
Access-Control-Allow-Origin: *
robots.txt HTTP 200
```

## Fields (une_rt_m, JSON-stat 2.0)

Labels quoted from the API answer (`lang=EN`).

| Field | Notes |
|---|---|
| `label`, `updated` | "Unemployment by sex and age - monthly data"; `2026-11-05T23:00:00+0100` on 2026-11-13 |
| `id`, `size` | dimension order `freq, s_adj, age, unit, sex, geo, time`; sizes after filtering, e.g. `[1, 1, 1, 1, 1, 28, 6]` |
| `s_adj` | `SA` "Seasonally adjusted data, not calendar adjusted data", `NSA` "Unadjusted data ...", `TC` "Trend cycle data" |
| `age` | `TOTAL`, `Y_LT25` "Less than 25 years", `Y25-74` |
| `sex` | `T`, `M`, `F` |
| `unit` | `PC_ACT` "Percentage of population in the labour force", `THS_PER` "Thousand persons" |
| `geo` | 38 codes: EU27_2020, EA21, the 27 Member States, IS, NO, CH, UK, BA, MK, TR, US, JP. CH had no value from 2026-07 on; UK had none in the window checked |
| `time` | `YYYY-MM`; the full dataset ran 1983-01 to 2026-10 |
| `value` | object `{"<flat index>": number}`; missing key = no data |
| `status`, `extension.status.label` | flags per flat index: `b` "break in time series", `d` "definition differs (see metadata)", `p` "provisional", `u` "low reliability". `status` is absent when no returned cell has a flag |
| `extension.annotation` | includes `OBS_PERIOD_OVERALL_LATEST` (2026-10), `UPDATE_DATA`, the DOI `10.2908/UNE_RT_M` and the metadata page https://ec.europa.eu/eurostat/cache/metadata/en/une_rt_m_esms.htm |

## Gotchas

- **Rank on one common month.** Countries publish with different lags. On 2026-11-13: 26 Member States ended at 2026-09, Ireland at 2026-10; outside the EU, Bosnia and Herzegovina ended at 2026-08 and Switzerland at 2026-06. Taking each country's own latest month would rank Ireland's October against everyone else's September.
- **`lastTimePeriod=N` counts back from the dataset-wide latest month**, not per country. `lastTimePeriod=2` returned 2026-09 and 2026-10 with 4 values for 4 geos. `sinceTimePeriod`, `untilTimePeriod`, `time` and `lastTimePeriod` cannot be combined, except since with until (HTTP 400, id 400).
- **HTTP 200 does not mean data.** Unknown geo codes are dropped (`geo=DE&geo=XX` returns only DE). `s_adj=XX` returns `size` 0 for `s_adj` and no values. `geo=ZZ` alone returns 0 geos. Unknown dimension names (`foo=1`) are HTTP 400 id 150; a misspelt dataset code is HTTP 404 id 100 `ERR_NOT_FOUND_4`.
- **413 comes as `error`, the docs show `warning`.** An uncached 1.08M-cell request (`une_rt_m?freq=M&untilTimePeriod=2026-10`) returned HTTP 413 `{"error": [{"status": 413, "id": 413, "label": "ASYNCHRONOUS_RESPONSE. Your request will be treated asynchronously. Please try again later."}]}` in 0.55 s; the API guide shows `{"warning":{"status":413, ...}}`. The same cells without filters came back HTTP 200 (10 MB, 12 s), presumably cached. The blocks here raise on a 413 instead of sending the request again later (that flow is not tested); filter `s_adj`, `age`, `sex`, `unit`, `geo` and time instead of downloading the dataset.
- **Flags.** In the full dataset, 11,303 of 759,687 values carry a flag (`p` 5,832, `u` 3,318, `b` 1,307, `d` 846). For the SA / TOTAL / T / PC_ACT series over the last 24 months, only one Malta value carries `b`. Print the flag next to the number.
- **Ties are common** at one decimal: September 2026 had three countries at 6.3 and three at 3.4. Block 1 gives tied countries the same rank.
- **Country codes.** Eurostat uses `EL` for Greece. `EU27_2020` and `EA21` are aggregates, not countries; keep them out of the ranking.
- **Commercial reuse is limited by country.** UK, US and JP (and any other code outside the EU, EFTA and candidate list) are non-commercial only. Remove them before any commercial use; the blocks never request them.
- **Python's `urllib.robotparser` misreads this robots.txt.** It ends a group at the first blank line, so it sees only the first part of the `*` group (for example it reports `/eurostat/search` as allowed). Use an RFC 9309 matcher, where groups end at the next `User-agent` line.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **`/eurostat/SDMX/diss-web/rest/`** (legacy SDMX): disallowed for `*` in robots.txt. Not used.
- **`lastTimePeriod=1` for "latest"**: 0 values for most countries (see block 2).
- **Data Browser pages** (`/eurostat/databrowser/view/une_rt_m/...`): HTTP 200 HTML, not parsed; the API gives the numbers as JSON. Used only as the citation link.
- **Not tested:** the asynchronous retrieval flow after a 413, SDMX 2.1 endpoints, bulk download, other datasets, `lang` other than `EN`, `NSA`/`TC` series, and rate-limit behaviour (never provoked).
