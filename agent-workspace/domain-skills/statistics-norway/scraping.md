# Statistics Norway (SSB) Statbank via data.ssb.no (PxWebApi v2) - Get the Newest Official Norwegian Figure for a Topic (Population by Age and Sex, CPI, Unemployment): Search Tables, Read Their Variables, Pull the Latest Period as Tidy Rows (JSON-stat API, no key)

Field-tested against data.ssb.no on 2026-11-20 (US Pacific afternoon, just after midnight in Norway; 23:27-23:39 UTC) using a fresh Browser Use cloud browser (logged out; one session, 23:32-23:35 UTC) plus Python `urllib` and `curl` from a Linux machine. 8 browser page loads (one API answer, two robots.txt URLs, four www.ssb.no pages, then the API again) and 30 in-page `fetch()` calls (block 1 ran twice), 36 urllib calls (block 3 ran 3 times: twice with an empty cache, once warm; 6 of the calls were robots.txt) and 54 curl calls (42 while exploring, 12 in block 4; 48 to the API host, 6 to robots.txt, the user guide and RFC 9309), all serial, at most one a second while exploring and one every 2 s or more in the blocks. Every data call was HTTP 200 except the deliberate HTTP 400 and 404 probes of mistakes. No 429, no challenge, no key, no login, no cookie needed (the API sets an `X-Identity` cookie; the blocks do not send it back). An independent verifier re-ran all four blocks verbatim at 23:43-23:46 UTC (cloud browser for blocks 1 and 2, `python3 -I` with an empty cache and then warm for block 3, bash for block 4): the same rows and numbers, differing only in the access time, `x-cache` and `x-ratelimit-remaining`.

robots.txt (checked 2026-11-20, curl, the cloud browser and `urllib.robotparser`): https://data.ssb.no/robots.txt answers HTTP 301 to https://www.ssb.no/omssb/tjenester-og-verktoy/api, which ends on the HTML page https://www.ssb.no/api (HTTP 200, `text/html`, no `User-agent` line), so the API host has no robots rules and no named AI-agent groups; RFC 9309 says crawlers "SHOULD follow at least five consecutive redirects" (section 2.3.1.2) and, where "no groups are present at all, no rules apply" (section 2.2.1); Python's parser also allows every path. https://www.ssb.no/robots.txt is two lines, `User-agent: *` and `Disallow: /a/kostra/stt`, with no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`. Every path this skill uses is allowed for all 11 agents (block 3). Terms: the API page https://www.ssb.no/en/api says "The APIs are open and do not require registration" and "Like the rest of ssb.no, the APIs use the license CC BY 4.0". The licence page https://www.ssb.no/en/diverse/lisens grants CC BY 4.0 to share and adapt "for any purpose, even commercially", asks you to "attribute us as Statistics Norway, SSB or Statistisk sentralbyå and if possible with a link to www.ssb.no", and to give credit "not in any way that suggests the licensor endorses you or your use"; it excludes "Data containing personal data, and which is confidential" and the photos. The API user guide https://www.ssb.no/en/api/pxwebapiv2 sets the limits: "The limits per extract are 800,000 data cells, and the number of queries is currently 30 per minute. The limit is per IP address". The PxWebApi page https://www.ssb.no/en/api/pxwebapi says v2 "was launched in autumn 2025" and "PxWebApi v1 will remain available during a transition period". No AI/ML, scraping, automated-access or non-commercial clause on any of the four pages (block 2 found none of the words scrap, artificial intelligence, machine learning, non-commercial or robot on them). Naming: this skill says "Statistics Norway (SSB)" with a link to www.ssb.no and the CC BY 4.0 licence, uses no SSB logo, and is not affiliated with or endorsed by Statistics Norway.

**Official, but check the period and the table.** Every answer carries the table number, the period (`2026`, `2026M10`, `2026K3`), the `updated` time and the unit. Many topics have several tables (seasonally adjusted or not, a new index base, a closed old series); say which one you used.

## Quick summary

- **No scraping.** Three GET endpoints, JSON, no key: `GET https://data.ssb.no/api/pxwebapi/v2/tables?query=consumer%20price%20index&lang=en` (search; `pageSize`, `pageNumber`, `pastDays`, `includeDiscontinued=true`), `GET /tables/{id}/metadata?lang=en` (the variables, their codes and English labels, JSON-stat 2.0) and `GET /tables/{id}/data?lang=en&outputFormat=json-stat2&valueCodes[Var]=...` (one cell per combination; `*`, `top(n)`, `from(2026M08)`, lists `00,01`, masks `03*`; `codelist[Var]=` for groupings such as 10-year age groups). `outputFormat=csv` also works. No CORS header, so a browser has to be on a data.ssb.no page to `fetch()`.
- **Answer (run 2026-11-20, 23:33 UTC):** population of Norway on 1 January **2026**: **5,627,400** (table 10211, the 22 rows of 10-year age groups by sex sum to the same number as the whole-country cell of table 07459). CPI **October 2026** (table 14700, updated 2026-11-10): **12-month rate 3.6 per cent**, index **104.3** (2025=100). Unemployment rate (Labour Force Survey) **September 2026**, seasonally adjusted, 15-74 years: **5.0 per cent**, **156,000** persons (table 13760, updated 2026-10-22).
- **Read `/metadata` first.** Variable codes stay Norwegian with `lang=en` (`Region`, `Kjonn`, `Alder`, `Justering`, `ContentsCode`, `Tid`) and value codes are SSB's own (`Kjonn` `1` = Males, `2` = Females, `0` = Both sexes; `Justering` `S` = Seasonally adjusted). The English text is only in the labels. Blocks 1 and 3 pick by label and send codes.
- **Search returns more than you want.** `query=population sex age` ranked a labour-force table (14077) first and the plain population table (10211) third, and default search hides closed series (21 CPI tables, 53 with `includeDiscontinued=true`). Block 1 keeps the first hit with exactly the variables you name and a label containing your words.
- **Rate limit:** the user guide says 30 queries per minute per IP address and 800,000 cells per extract; every response carried `x-ratelimit-policy: 40;w=60s` and `x-ratelimit-limit: 40`, and `x-ratelimit-remaining` stayed at 39 or 38 through every run (38 on all 9 calls of block 1 in the verifier's re-run), so it is not a usable countdown. The blocks run serially at one call every 2.1 s (under 30 a minute), wait once on 429, 5xx or a network error (`Retry-After` seconds or date, else 60 s; over 120 s they stop), and stop after that. The guide also asks you to avoid 07:55-08:15 on release days and says tables are unavailable during the metadata updates at 05:00 and 11:30.

## What works

### 1. Newest period for a topic: search, pick the table, read its variables, pull tidy rows (browser)

`on_ssb_tab()` opens one logged-out data.ssb.no API answer so `fetch()` runs same-origin (the API sends no `Access-Control-Allow-Origin`). `get()` returns parsed JSON on HTTP 200, waits once on 429/500/502/503/504 or a network error (`Retry-After` seconds or date, else 60 s; above 120 s it stops) and otherwise raises. 9 `fetch()` calls: per topic one search, one `/metadata`, one `/data`. Add a topic by naming its search words, the exact variable labels, a label fragment and the values you want.

```python
import email.utils, json, time
from datetime import datetime, timezone
from urllib.parse import urlencode

API = "https://data.ssb.no/api/pxwebapi/v2"
PAUSE = 2.1   # SSB's user guide: "the number of queries is currently 30 per minute" per IP address
UTC = timezone.utc

# One entry per question. Search words, then the table must have exactly these variable names (English labels)
# and a label containing `label_has`. `pick` maps a variable label to the value labels you want; the time
# variable always gets top(1) (the newest period); a variable you leave out is dropped if the table allows
# that (the API then sums it, e.g. the whole country), otherwise every value comes back.
TOPICS = {
    "population by age and sex": dict(
        query="population sex age", vars={"sex", "age", "contents", "year"}, label_has="Population, by sex and age",
        pick={"sex": ["Females", "Males"]}, codelist={"age": "10-years groups"}),
    "consumer price index": dict(
        query="consumer price index", vars={"goods and services", "contents", "month"},
        label_has="Consumer price index (CPI), by goods and services",
        pick={"goods and services": ["Total"], "contents": ["12-month rate (per cent)", "Consumer Price Index (2025=100)"]}),
    "unemployment": dict(
        query="unemployment", vars={"sex", "age", "type of adjustment", "contents", "month"},
        label_has="Labour force, employment, unemployment",
        pick={"sex": ["Both sexes"], "age": ["15-74 years"], "type of adjustment": ["Seasonally adjusted"],
              "contents": ["Unemployment rate (LFS)", "Unemployment (LFS) (1000 persons)"]}),
}

def on_ssb_tab():
    """fetch() runs same-origin from a data.ssb.no page (the API sends no Access-Control-Allow-Origin header)."""
    try:
        if js("location.origin") == "https://data.ssb.no":
            return
    except Exception:
        pass
    new_tab(API + "/tables?query=population&lang=en&pageSize=1")
    wait_for_load()
    if js("location.origin") != "https://data.ssb.no" or '"tables"' not in (js("document.body ? document.body.innerText : ''") or ""):
        raise RuntimeError(f"data.ssb.no did not serve the table list (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def retry_wait(value, default):
    """Retry-After is seconds or an HTTP date -> seconds to wait; `default` when it is absent or unreadable."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

calls = []
def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    calls.append((r["status"], r["headers"].get("x-ratelimit-remaining")))
    time.sleep(PAUSE)
    return r

def get(path, **params):
    """GET API + path -> parsed JSON. Waits once on 429/5xx or a network error: Retry-After seconds or date, else
    60 s (the limit is per minute; tables are also briefly unavailable during the 05:00 and 11:30 metadata
    updates); over 120 s stops. Raises on anything else."""
    url = API + path + "?" + urlencode(params)
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = retry_wait(r["headers"].get("retry-after"), 60)
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:150]!r}; stopping")
    return json.loads(r["text"])

def find_table(query, vars, label_has):
    """Search (newest tables only: discontinued ones are left out by default) and keep the first hit whose
    variable names are exactly `vars` and whose label contains `label_has`. Prints the top of the hit list.
    Reads the next page of 40 hits only while nothing matched (1 call per page)."""
    page = 1
    while True:
        res = get("/tables", query=query, lang="en", pageSize=40, pageNumber=page)
        hits = res["tables"]
        if page == 1:
            print(f"  search {query!r}: {res['page']['totalElements']} tables; top 3: "
                  + "; ".join(f"{t['id']} {t['label'].split(': ', 1)[1][:48]}" for t in hits[:3]))
        for t in hits:
            if set(t["variableNames"]) == vars and label_has.lower() in t["label"].lower() and not t.get("discontinued"):
                if page > 1:
                    print(f"  match on page {page} of {res['page']['totalPages']}")
                return t
        if page >= res["page"]["totalPages"]:
            break
        page += 1
    raise RuntimeError(f"no table for {query!r} with variables {sorted(vars)} and label {label_has!r} "
                       f"in {res['page']['totalElements']} hits: read the hits")

def tidy(ds):
    """json-stat2 -> list of dicts, one per cell. `value` is one flat list in the order of ds['id'] (last
    dimension fastest); a suppressed cell is null with a symbol in ds['status'] (keyed by flat index)."""
    dims = ds["id"]
    codes = [sorted(ds["dimension"][d]["category"]["index"], key=ds["dimension"][d]["category"]["index"].get) for d in dims]
    status = ds.get("status") or {}
    rows = []
    for i, v in enumerate(ds["value"]):
        row, rest = {}, i
        for d, cs, n in reversed(list(zip(dims, codes, ds["size"]))):
            c = cs[rest % n]
            rest //= n
            row[d] = c
            row[d + "_label"] = ds["dimension"][d]["category"]["label"][c]
        row["value"] = v
        row["status"] = status.get(str(i))
        rows.append(row)
    return rows

def latest(table_id, pick=None, codelist=None):
    """Newest period of one table as tidy rows. Reads /metadata first: the variable codes are Norwegian
    (Region, Kjonn, Alder, Tid, ContentsCode) even with lang=en, so `pick` and `codelist` use the English labels."""
    meta = get(f"/tables/{table_id}/metadata", lang="en")
    by_label = {meta["dimension"][d]["label"]: d for d in meta["id"]}
    time_var = meta["role"]["time"][0]
    q = {"lang": "en", "outputFormat": "json-stat2", f"valueCodes[{time_var}]": "top(1)"}
    for lab, cl in (codelist or {}).items():
        d = by_label[lab]
        ids = {c["label"]: c["id"] for c in meta["dimension"][d]["extension"].get("codelists", [])}
        if cl not in ids:
            raise RuntimeError(f"{table_id} {d}: no code list {cl!r}; it has {sorted(ids)}")
        q[f"codelist[{d}]"] = ids[cl]
        q[f"valueCodes[{d}]"] = "*"
    for d in meta["id"]:
        dim = meta["dimension"][d]
        lab = dim["label"]
        if d == time_var or f"valueCodes[{d}]" in q:
            continue
        if lab in (pick or {}):
            want = pick[lab]
            code = {v: k for k, v in dim["category"]["label"].items()}
            missing = [w for w in want if w not in code]
            if missing:
                raise RuntimeError(f"{table_id} {d} ({lab}): no value {missing}; it has {list(code)[:12]}")
            q[f"valueCodes[{d}]"] = ",".join(code[w] for w in want)
        elif not dim["extension"].get("elimination"):
            q[f"valueCodes[{d}]"] = "*"   # mandatory variable: leaving it out is an HTTP 400
    ds = get(f"/tables/{table_id}/data", **{k: v for k, v in q.items() if k not in ("lang", "outputFormat")},
             lang="en", outputFormat="json-stat2")
    if ds.get("extension", {}).get("discontinued"):
        print(f"  note: table {table_id} is discontinued; look for the table that replaces it")
    return meta, ds, tidy(ds)

on_ssb_tab()
now = datetime.now(UTC)
print(f"Statistics Norway (SSB) Statbank via PxWebApi v2, checked {now:%Y-%m-%d %H:%M} UTC")
for topic, t in TOPICS.items():
    print(f"\n{topic}:")
    tab = find_table(t["query"], t["vars"], t["label_has"])
    meta, ds, rows = latest(tab["id"], t.get("pick"), t.get("codelist"))
    time_var = meta["role"]["time"][0]
    period = rows[0][time_var]
    if period != tab["lastPeriod"]:
        raise RuntimeError(f"{tab['id']}: top(1) gave {period}, the table list says {tab['lastPeriod']}: stop")
    cc = ds["dimension"]["ContentsCode"]
    print(f"  table {tab['id']} ({ds['label']}), updated {ds['updated'][:16].replace('T', ' ')} UTC, "
          f"newest period {period}; codes {ds['id']}")
    keys = [d for d in ds["id"] if d not in (time_var, "ContentsCode")]
    for r in rows[:8]:
        u = cc["category"].get("unit", {}).get(r["ContentsCode"], {})   # e.g. {"base": "per cent", "decimals": 1}
        ref = cc.get("extension", {}).get("refperiod", {}).get(r["ContentsCode"])   # "01.01." = 1 January
        val = f"{r['value']:,.{u.get('decimals', 0)}f}" if r["value"] is not None else f"null, status {r['status']!r}"
        print(f"    {period}{' (' + ref + ')' if ref else ''}  " + "  ".join(r[d + "_label"] for d in keys)
              + f"  {r['ContentsCode_label']}: {val} {u.get('base', '')}")
    if len(rows) > 8:
        print(f"    ... {len(rows) - 8} more rows ({len(rows)} in all)")
    if topic == "population by age and sex" and all(r["value"] is not None for r in rows):
        print(f"  sum of the {len(rows)} rows: {sum(r['value'] for r in rows):,} persons")
    if any(r["value"] is None for r in rows):
        print(f"  {sum(r['value'] is None for r in rows)} cells suppressed (null; symbol in status)")
print(f"\n{len(calls)} API calls, statuses {sorted({s for s, _ in calls})}, x-ratelimit-remaining seen {sorted({x for _, x in calls if x})}")
print(f"Source: Statistics Norway (SSB), https://www.ssb.no, Statbank tables via {API}, CC BY 4.0, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the run on 2026-11-20, 23:33 UTC; the first run at 23:32 UTC, before the values were formatted by the unit's decimals, printed the same numbers with `5` for the unemployment rate):

```text
Statistics Norway (SSB) Statbank via PxWebApi v2, checked 2026-11-20 23:33 UTC

population by age and sex:
  search 'population sex age': 143 tables; top 3: 14077 Population, by labour force status, sex, age and; 14090 Population, by labour force status, sex, age and; 10211 Population, by sex and age 1846-2026
  table 10211 (10211: Population, by age, sex and year), updated 2026-02-25 07:00 UTC, newest period 2026; codes ['Alder', 'Kjonn', 'ContentsCode', 'Tid']
    2026 (01.01.)  0-9 years  Females  Persons: 277,471 number
    2026 (01.01.)  0-9 years  Males  Persons: 293,261 number
    2026 (01.01.)  10-19 years  Females  Persons: 323,364 number
    2026 (01.01.)  10-19 years  Males  Persons: 344,538 number
    2026 (01.01.)  20-29 years  Females  Persons: 341,820 number
    2026 (01.01.)  20-29 years  Males  Persons: 360,751 number
    2026 (01.01.)  30-39 years  Females  Persons: 387,529 number
    2026 (01.01.)  30-39 years  Males  Persons: 404,172 number
    ... 14 more rows (22 in all)
  sum of the 22 rows: 5,627,400 persons

consumer price index:
  search 'consumer price index': 21 tables; top 3: 14710 Consumer price index (2025=100) 1920M03-2026M10; 14711 Consumer price index, historical series (2025=10; 14709 Consumer price index, by month (2025=100) 1920-2
  table 14700 (14700: Consumer price index, by goods and services and month), updated 2026-11-10 07:00 UTC, newest period 2026M10; codes ['VareTjenesteGrp', 'ContentsCode', 'Tid']
    2026M10 (Month)  Total  12-month rate (per cent): 3.6 per cent
    2026M10 (Month)  Total  Consumer Price Index (2025=100): 104.3 index

unemployment:
  search 'unemployment': 13 tables; top 3: 13760 Labour force, employment, unemployment and man-w; 14483 Population, by labour force status, age and sex.; 14454 Unemployed persons, by sex, age and job seeker s
  table 13760 (13760: Labour force, employment, unemployment and man-weeks worked for persons aged 15-74, by sex, age, type of adjustment and month), updated 2026-10-22 06:00 UTC, newest period 2026M09; codes ['Kjonn', 'Alder', 'Justering', 'ContentsCode', 'Tid']
    2026M09 (Month)  Both sexes  15-74 years  Seasonally adjusted  Unemployment rate (LFS): 5.0 per cent
    2026M09 (Month)  Both sexes  15-74 years  Seasonally adjusted  Unemployment (LFS) (1000 persons): 156 1000 persons

9 API calls, statuses [200], x-ratelimit-remaining seen ['39']
Source: Statistics Norway (SSB), https://www.ssb.no, Statbank tables via https://data.ssb.no/api/pxwebapi/v2, CC BY 4.0, accessed 20 November 2026 23:33 UTC.
```

### 2. robots.txt, the API, licence and limits pages, and what the API does with mistakes (browser)

7 page loads and 12 in-page `fetch()` calls in the same tab. The licence page keeps the attribution wording in a pop-up, so the block reads `textContent`.

```python
import json, re, time

API = "https://data.ssb.no/api/pxwebapi/v2"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(path):
    """One in-page GET of API + path -> {status, headers, text}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(API + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(2.1)   # 30 queries a minute (SSB user guide)
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    time.sleep(1)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    ct = js("document.contentType")
    # textContent, not innerText: the licence page keeps the attribution wording in a pop-up
    return st, ct, js("location.href"), js("(document.body || document.documentElement).textContent || ''") or ""

for url in ("https://data.ssb.no/robots.txt", "https://www.ssb.no/robots.txt"):
    st, ct, href, txt = page(url)
    if ct.startswith("text/plain"):
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        print(f"{url.split('//')[1]:<26} HTTP {st} {ct}: {lines}")
    else:
        print(f"{url.split('//')[1]:<26} -> {href} (HTTP {st}, {ct}): an HTML page, not a robots file; "
              f"'User-agent' in it: {'user-agent' in txt.lower()}")

for url, needles in (
    ("https://www.ssb.no/en/api", ["The APIs are open and do not require registration",
                                   "Like the rest of ssb.no, the APIs use the license"]),
    ("https://www.ssb.no/en/api/pxwebapi", ["It was launched in autumn 2025",
                                            "PxWebApi v1 will remain available during a transition period"]),
    ("https://www.ssb.no/en/api/pxwebapiv2", ["The limits per extract are 800,000 data cells, and the number of queries is currently 30 per minute",
                                              "The limit is per IP address",
                                              "Unless you need it, avoid the time period 07:55",
                                              "Metadata is updated at 05:00 and 11:30, and during these updates the tables are unavailable",
                                              "In json-stat2, the special characters are displayed under status"]),
    ("https://www.ssb.no/en/diverse/lisens", ["Creative Commons Attribution 4.0 International (CC BY 4.0)",
                                              "for any purpose, even commercially",
                                              "attribute us as Statistics Norway, SSB or Statistisk sentralbyå and if possible with a link to www.ssb.no",
                                              "not in any way that suggests the licensor endorses you or your use"]),
):
    st, ct, href, txt = page(url)
    flat = " ".join(txt.split())
    for n in needles:
        print(f"{href.split('//')[1]:<34} HTTP {st}: {'found' if n in flat else 'MISSING'}: {n[:70]!r}")
    bad = [w for w in ("scrap", "artificial intelligence", "machine learning", "non-commercial", "noncommercial", "robot")
           if w in flat.lower()]
    print(f"{href.split('//')[1]:<34} words scrap/AI/ML/non-commercial/robot on the page: {bad or 'none'}")

page(API + "/tables?query=population&lang=en&pageSize=1")   # back on data.ssb.no for same-origin fetch()
print()

def brief(r):
    t = " ".join(r["text"].split())
    return f"HTTP {r['status']} {r['headers'].get('content-type', '?')}: {t[:110]}"

D = "outputFormat=json-stat2&lang=en&valueCodes[Tid]=top(1)"
for label, path in (
    ("table id without leading zero 7459", "/tables/7459/metadata?lang=en"),
    ("unknown table 99999              ", "/tables/99999/metadata?lang=en"),
    ("English code sex instead of Kjonn", f"/tables/07459/data?{D}&valueCodes[ContentsCode]=*&valueCodes[sex]=*"),
    ("value label 'Males' as a code     ", f"/tables/07459/data?{D}&valueCodes[ContentsCode]=*&valueCodes[Kjonn]=Males"),
    ("ContentsCode left out             ", f"/tables/07459/data?{D}&valueCodes[Kjonn]=*"),
    ("every cell of 07459               ", "/tables/07459/data?outputFormat=json-stat2&lang=en&valueCodes[Region]=*&valueCodes[Kjonn]=*"
                                           "&valueCodes[Alder]=*&valueCodes[ContentsCode]=*&valueCodes[Tid]=*"),
):
    print(f"{label} {brief(raw(path))}")

# Leaving out an optional variable sums it: Region, Kjonn, Alder dropped = the whole country
r = raw(f"/tables/07459/data?{D}&valueCodes[ContentsCode]=*")
ds = json.loads(r["text"])
print(f"\n07459, only ContentsCode and Tid: ids {ds['id']}, sizes {ds['size']}, value {ds['value']}, label {ds['label']!r}")
h = r["headers"]
print("headers:", {k: h.get(k) for k in ("content-type", "cache-control", "access-control-allow-origin",
                                          "x-ratelimit-limit", "x-ratelimit-policy", "x-ratelimit-remaining", "x-cache")})

# lang=no: same Norwegian codes, Norwegian labels
r = raw(f"/tables/07459/data?outputFormat=json-stat2&lang=no&valueCodes[Tid]=top(1)&valueCodes[ContentsCode]=*&valueCodes[Kjonn]=*")
ds = json.loads(r["text"])
print(f"lang=no: ids {ds['id']}, Kjonn labels {ds['dimension']['Kjonn']['category']['label']}, value {ds['value']}")

# Discontinued tables are hidden from search unless asked for
a = json.loads(raw("/tables?query=consumer%20price%20index&lang=en&pageSize=100")["text"])
b = json.loads(raw("/tables?query=consumer%20price%20index&lang=en&pageSize=100&includeDiscontinued=true")["text"])
old = json.loads(raw("/tables/03013?lang=en")["text"])
print(f"search 'consumer price index': {a['page']['totalElements']} tables, with includeDiscontinued=true "
      f"{b['page']['totalElements']}; 03013 in the first: {'03013' in [t['id'] for t in a['tables']]}, in the second: "
      f"{'03013' in [t['id'] for t in b['tables']]}")
print(f"03013: {old['label']!r}, discontinued {old.get('discontinued')}, lastPeriod {old['lastPeriod']}")

# CSV: Latin-1, wide (periods become columns)
r = raw("/tables/14700/data?outputFormat=csv&lang=en&valueCodes[VareTjenesteGrp]=00&valueCodes[ContentsCode]=Tolvmanedersendring&valueCodes[Tid]=top(3)")
print(f"csv: HTTP {r['status']} {r['headers'].get('content-type')}: {r['text'].strip().splitlines()}")
```

Output (from the run on 2026-11-20, 23:34-23:35 UTC):

```text
data.ssb.no/robots.txt     -> https://www.ssb.no/api (HTTP 200, text/html): an HTML page, not a robots file; 'User-agent' in it: False
www.ssb.no/robots.txt      HTTP 200 text/plain: ['User-agent: *', 'Disallow: /a/kostra/stt']
www.ssb.no/en/api                  HTTP 200: found: 'The APIs are open and do not require registration'
www.ssb.no/en/api                  HTTP 200: found: 'Like the rest of ssb.no, the APIs use the license'
www.ssb.no/en/api                  words scrap/AI/ML/non-commercial/robot on the page: none
www.ssb.no/en/api/pxwebapi         HTTP 200: found: 'It was launched in autumn 2025'
www.ssb.no/en/api/pxwebapi         HTTP 200: found: 'PxWebApi v1 will remain available during a transition period'
www.ssb.no/en/api/pxwebapi         words scrap/AI/ML/non-commercial/robot on the page: none
www.ssb.no/en/api/pxwebapiv2       HTTP 200: found: 'The limits per extract are 800,000 data cells, and the number of queri'
www.ssb.no/en/api/pxwebapiv2       HTTP 200: found: 'The limit is per IP address'
www.ssb.no/en/api/pxwebapiv2       HTTP 200: found: 'Unless you need it, avoid the time period 07:55'
www.ssb.no/en/api/pxwebapiv2       HTTP 200: found: 'Metadata is updated at 05:00 and 11:30, and during these updates the t'
www.ssb.no/en/api/pxwebapiv2       HTTP 200: found: 'In json-stat2, the special characters are displayed under status'
www.ssb.no/en/api/pxwebapiv2       words scrap/AI/ML/non-commercial/robot on the page: none
www.ssb.no/en/diverse/lisens       HTTP 200: found: 'Creative Commons Attribution 4.0 International (CC BY 4.0)'
www.ssb.no/en/diverse/lisens       HTTP 200: found: 'for any purpose, even commercially'
www.ssb.no/en/diverse/lisens       HTTP 200: found: 'attribute us as Statistics Norway, SSB or Statistisk sentralbyå and if'
www.ssb.no/en/diverse/lisens       HTTP 200: found: 'not in any way that suggests the licensor endorses you or your use'
www.ssb.no/en/diverse/lisens       words scrap/AI/ML/non-commercial/robot on the page: none

table id without leading zero 7459 HTTP 404 application/json; charset=utf-8: {"type":"Parameter error","title":"Non-existent table","status":404}
unknown table 99999               HTTP 404 application/json; charset=utf-8: {"type":"Parameter error","title":"Non-existent table","status":404}
English code sex instead of Kjonn HTTP 400 application/json; charset=utf-8: {"type":"Parameter error","title":"Non-existent variable","status":400}
value label 'Males' as a code      HTTP 400 application/json; charset=utf-8: {"type":"Parameter error","title":"Non-existent value","status":400}
ContentsCode left out              HTTP 400 application/json; charset=utf-8: {"type":"Parameter error","title":"Missing selection for mandantory variable","status":400}
every cell of 07459                HTTP 400 application/json; charset=utf-8: {"type":"Parameter error","title":"Too many cells selected","status":400,"detail":"Too many cells selected"}

07459, only ContentsCode and Tid: ids ['ContentsCode', 'Tid'], sizes [1, 1], value [5627400], label '07459: Population, by year'
headers: {'content-type': 'application/json; charset=UTF-8', 'cache-control': None, 'access-control-allow-origin': None, 'x-ratelimit-limit': '40', 'x-ratelimit-policy': '40;w=60s', 'x-ratelimit-remaining': '39', 'x-cache': 'MISS'}
lang=no: ids ['Kjonn', 'ContentsCode', 'Tid'], Kjonn labels {'2': 'Kvinner', '1': 'Menn'}, value [2790483, 2836917]
search 'consumer price index': 21 tables, with includeDiscontinued=true 53; 03013 in the first: False, in the second: True
03013: '03013: Consumer Price Index, by consumption group (2015=100) (closed series) 1979M01-2025M12', discontinued True, lastPeriod 2025M12
csv: HTTP 200 text/csv; charset=iso-8859-1: ['"VareTjenesteGrp","Tolvmanedersendring 2026M08","Tolvmanedersendring 2026M09","Tolvmanedersendring 2026M10"', '"00",3.3,3.4,3.6']
```

### 3. Same API with Python urllib: robots check for every agent, what was published lately, CPI and unemployment series, largest municipalities, metadata cache (no browser)

Sends a descriptive User-Agent and asks for gzip (`/metadata` for 07459 is 50,502 bytes plain, 15,922 gzipped). The API sends no `ETag` or `Last-Modified`, so the cache keeps each table's `/metadata` on disk and re-downloads it only when the table's `updated` stamp in `/tables/{id}` (one small call) has changed.

```python
import email.utils, gzip, json, os, sys, time, urllib.error, urllib.request, urllib.robotparser
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlencode

API = "https://data.ssb.no/api/pxwebapi/v2"
UA = "ssb-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/ssb-skill"
CACHE = os.path.expanduser(CACHE_DIR)
PAUSE = 2.1   # "the number of queries is currently 30 per minute", per IP address (SSB user guide)
UTC = timezone.utc
stats = Counter()

def retry_wait(value, default):
    """Retry-After is seconds or an HTTP date -> seconds to wait; `default` when it is absent or unreadable."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def get(path, **params):
    """GET API + path -> parsed JSON. Serial, 2.1 s apart, gzip. On 429 or 5xx waits Retry-After (seconds or a
    date, else 60 s; over 120 s exits) once, on a network error 60 s once (tables are briefly unavailable during
    the 05:00 and 11:30 metadata updates); exits on anything else, printing SSB's error title."""
    url = API + path + ("?" + urlencode(params) if params else "")
    for attempt in range(2):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"}),
                                        timeout=60) as r:
                body = r.read()
                stats["calls"] += 1
                stats["bytes"] += len(body)
                stats["remaining=" + str(r.headers.get("x-ratelimit-remaining"))] += 1
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return json.loads(body)
        except urllib.error.HTTPError as e:
            if attempt == 0 and e.code in (429, 500, 502, 503, 504):
                wait = retry_wait(e.headers.get("Retry-After"), 60)
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:150]}")
        except OSError as e:  # DNS, refused connection, timeout, reset
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")

def metadata(table_id):
    """/metadata (50 KB for 07459) from disk while the table's `updated` stamp is unchanged. The API sends no
    ETag or Last-Modified, so the cheap /tables/{id} entry (about 2 KB) is the change check."""
    info = get(f"/tables/{table_id}", lang="en")
    f = os.path.join(CACHE, f"{table_id}.en.json")
    try:
        meta = json.load(open(f))
        if meta.get("updated") == info["updated"]:
            stats["meta from disk"] += 1
            return info, meta
    except (OSError, ValueError):
        pass
    meta = get(f"/tables/{table_id}/metadata", lang="en")
    os.makedirs(CACHE, exist_ok=True)
    json.dump(meta, open(f, "w"))
    return info, meta

def codes(meta, var_label, *value_labels):
    """English labels -> SSB's codes for one variable (codes are Norwegian or numeric, e.g. Kjonn '1' = Males)."""
    d = next(d for d in meta["id"] if meta["dimension"][d]["label"] == var_label)
    by = {v: k for k, v in meta["dimension"][d]["category"]["label"].items()}
    missing = [v for v in value_labels if v not in by]
    if missing:
        sys.exit(f"{meta['label']}: {var_label} has no {missing}; it has {list(by)[:10]}")
    return d, ",".join(by[v] for v in value_labels)

def tidy(ds):
    """json-stat2 -> rows of {code: (code, label), ..., 'value', 'status'}; ds['value'] runs in ds['id'] order, last fastest."""
    cats = [ds["dimension"][d]["category"] for d in ds["id"]]
    order = [sorted(c["index"], key=c["index"].get) for c in cats]
    out = []
    for i, v in enumerate(ds["value"]):
        row, rest = {}, i
        for d, c, o, n in reversed(list(zip(ds["id"], cats, order, ds["size"]))):
            row[d] = (o[rest % n], c["label"][o[rest % n]])
            rest //= n
        row["value"], row["status"] = v, (ds.get("status") or {}).get(str(i))
        out.append(row)
    return out

# 1. robots.txt. data.ssb.no/robots.txt is a 301 to an HTML page (www.ssb.no/api), so the API host has no rules;
#    RobotFileParser follows the redirect, finds no User-agent lines and allows everything.
for host, paths in (("https://data.ssb.no", ["/api/pxwebapi/v2/tables", "/api/pxwebapi/v2/tables/07459/metadata",
                                              "/api/pxwebapi/v2/tables/07459/data"]),
                    ("https://www.ssb.no", ["/en/api", "/en/api/pxwebapiv2", "/en/diverse/lisens"])):
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
        print(f"{host}/robots.txt: HTTP {r.status} {r.headers.get('Content-Type')} (final URL {r.url})")
        rp.parse(r.read().decode("utf-8", "replace").splitlines())
    time.sleep(PAUSE)
    for p in paths:
        ok = all(rp.can_fetch(a, host + p) for a in AGENTS)
        print(f"  robots {p:<40} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
        if not ok:
            sys.exit("robots.txt now disallows a path this skill uses: stop")

now = datetime.now(UTC)
print(f"\nStatistics Norway (SSB) Statbank via PxWebApi v2, checked {now:%Y-%m-%d %H:%M} UTC")

# 2. What did SSB publish lately? pastDays lists tables updated in the last N days (paged).
recent, page = [], 1
while True:
    res = get("/tables", pastDays=3, lang="en", pageSize=100, pageNumber=page)
    recent += res["tables"]
    if page >= res["page"]["totalPages"]:
        break
    page += 1
days = Counter(t["updated"][:10] for t in recent)
print(f"tables updated in the last 3 days: {len(recent)} ({res['page']['totalElements']} per the API) in {page} pages; "
      f"by day {dict(sorted(days.items()))}")

# 3. CPI: 12-month rate, last 13 months (top(13)) for the total and two groups
info, meta = metadata("14700")
g, gc = codes(meta, "goods and services", "Total", "Food and non-alcoholic beverages", "Electricity, gas and other fuels")
c, cc = codes(meta, "contents", "12-month rate (per cent)")
ds = get("/tables/14700/data", lang="en", outputFormat="json-stat2", **{f"valueCodes[{g}]": gc, f"valueCodes[{c}]": cc,
                                                                         "valueCodes[Tid]": "top(13)"})
rows = tidy(ds)
months = sorted({r["Tid"][0] for r in rows})
print(f"\n{info['label']} (updated {info['updated'][:10]}), 12-month rate, per cent:")
print(f"  {'':<36}" + " ".join(f"{m[2:]:>6}" for m in months))
for code in gc.split(","):
    vals = {r["Tid"][0]: r["value"] for r in rows if r[g][0] == code}
    name = next(r[g][1] for r in rows if r[g][0] == code)
    print(f"  {name[:36]:<36}" + " ".join(f"{vals[m]:>6.1f}" if vals[m] is not None else "     -" for m in months))

# 4. Unemployment rate (LFS), seasonally adjusted, last 6 months, by sex
info, meta = metadata("13760")
k, kc = codes(meta, "sex", "Both sexes", "Females", "Males")
a, ac = codes(meta, "age", "15-74 years")
j, jc = codes(meta, "type of adjustment", "Seasonally adjusted")
c, cc = codes(meta, "contents", "Unemployment rate (LFS)")
ds = get("/tables/13760/data", lang="en", outputFormat="json-stat2",
         **{f"valueCodes[{k}]": kc, f"valueCodes[{a}]": ac, f"valueCodes[{j}]": jc, f"valueCodes[{c}]": cc,
            "valueCodes[Tid]": "top(6)"})
rows = tidy(ds)
months = sorted({r["Tid"][0] for r in rows})
print(f"\n{info['label'][:72]}... (updated {info['updated'][:10]}), unemployment rate (LFS), seasonally adjusted, 15-74:")
for code in kc.split(","):
    vals = {r["Tid"][0]: r["value"] for r in rows if r[k][0] == code}
    print(f"  {dict(zip(kc.split(','), ['Both sexes', 'Females', 'Males']))[code]:<11}"
          + "  ".join(f"{m} {vals[m]:.1f}" for m in months))

# 5. Population on 1 January, newest year: the 5 largest municipalities (code list 'All municipalities')
info, meta = metadata("07459")
dim = meta["dimension"]["Region"]["extension"]["codelists"]
vs = next(x["id"] for x in dim if x["label"] == "All municipalities")
ds = get("/tables/07459/data", lang="en", outputFormat="json-stat2",
         **{"codelist[Region]": vs, "valueCodes[Region]": "*", "valueCodes[ContentsCode]": "*", "valueCodes[Tid]": "top(1)"})
rows = [r for r in tidy(ds) if r["value"]]
year = rows[0]["Tid"][0]
print(f"\n{info['label']}: {len(rows)} municipalities with people on 1 January {year} "
      f"(code list {vs}, {ds['size'][0]} codes; {sum(r['value'] for r in rows):,} persons in all)")
for r in sorted(rows, key=lambda r: -r["value"])[:5]:
    print(f"  {r['Region'][0]}  {r['Region'][1]:<22} {r['value']:>9,}")

# 6. Ask again: metadata comes from disk while the table's `updated` stamp is unchanged
n = stats["calls"]
metadata("07459")
print(f"\nmetadata again: {stats['calls'] - n} API call (the /tables/07459 change check), {stats['meta from disk']} served from disk so far")
print(f"totals: {stats['calls']} API calls, {stats['bytes']:,} bytes on the wire (gzip), "
      f"x-ratelimit-remaining {sorted(k.split('=')[1] for k in stats if k.startswith('remaining='))}, cache {CACHE_DIR}")
print(f"Source: Statistics Norway (SSB), https://www.ssb.no, tables 14700, 13760 and 07459 via {API}, CC BY 4.0, "
      f"accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the run on 2026-11-20, 23:37 UTC, empty cache; a warm re-run at 23:38 UTC printed the same rows and "4 served from disk so far", 8 API calls, 27,355 bytes; an earlier cold run at 23:36 UTC differed only in column alignment):

```text
https://data.ssb.no/robots.txt: HTTP 200 text/html;charset=utf-8 (final URL https://www.ssb.no/api)
  robots /api/pxwebapi/v2/tables                  allowed for all 11 agents
  robots /api/pxwebapi/v2/tables/07459/metadata   allowed for all 11 agents
  robots /api/pxwebapi/v2/tables/07459/data       allowed for all 11 agents
https://www.ssb.no/robots.txt: HTTP 200 text/plain; charset=UTF-8 (final URL https://www.ssb.no/robots.txt)
  robots /en/api                                  allowed for all 11 agents
  robots /en/api/pxwebapiv2                       allowed for all 11 agents
  robots /en/diverse/lisens                       allowed for all 11 agents

Statistics Norway (SSB) Statbank via PxWebApi v2, checked 2026-11-20 23:37 UTC
tables updated in the last 3 days: 90 (90 per the API) in 1 pages; by day {'2026-11-18': 7, '2026-11-19': 64, '2026-11-20': 19}

14700: Consumer price index (CPI), by goods and services (2025=100) 2000M01-2026M10 (updated 2026-11-10), 12-month rate, per cent:
                                       25M10  25M11  25M12  26M01  26M02  26M03  26M04  26M05  26M06  26M07  26M08  26M09  26M10
  Total                                  3.1    3.0    3.2    3.6    2.7    3.6    3.4    3.1    2.7    3.0    3.3    3.4    3.6
  Food and non-alcoholic beverages       6.1    4.6    5.3    4.2    3.3    1.6    6.6    3.4    2.3    1.1    1.6    2.4    1.4
  Electricity, gas and other fuels       1.6    4.1    5.6    8.0   -2.3    9.2    2.1   -2.5   -0.1    8.7    6.1    3.3   11.5

13760: Labour force, employment, unemployment and man-weeks worked, by s... (updated 2026-10-22), unemployment rate (LFS), seasonally adjusted, 15-74:
  Both sexes 2026M04 4.6  2026M05 4.5  2026M06 4.6  2026M07 4.1  2026M08 4.6  2026M09 5.0
  Females    2026M04 4.2  2026M05 4.2  2026M06 4.4  2026M07 3.9  2026M08 4.4  2026M09 4.8
  Males      2026M04 4.9  2026M05 4.7  2026M06 4.8  2026M07 4.3  2026M08 4.8  2026M09 5.2

07459: Population, by sex and one-year age groups  (M) 1986-2026: 357 municipalities with people on 1 January 2026 (code list vs_Kommun, 952 codes; 5,627,400 persons in all)
  0301  Oslo - Oslove            728,714
  4601  Bergen                   294,860
  5001  Trondheim - Tråante      218,460
  1103  Stavanger                151,669
  3201  Bærum                    133,228

metadata again: 1 API call (the /tables/07459 change check), 1 served from disk so far
totals: 11 API calls, 59,405 bytes on the wire (gzip), x-ratelimit-remaining ['39'], cache ~/.cache/ssb-skill
Source: Statistics Norway (SSB), https://www.ssb.no, tables 14700, 13760 and 07459 via https://data.ssb.no/api/pxwebapi/v2, CC BY 4.0, accessed 20 November 2026 23:37 UTC.
```

### 4. curl: search, variables, one number, CSV, headers, mistakes

```bash
B=https://data.ssb.no/api/pxwebapi/v2
# -g: keep [ ] in the URL literal (curl would read them as a range); --retry 1 retries once on a timeout or HTTP 408, 429, 500, 502, 503 or 504, 60 s later
C="curl -sSg --max-time 60 --retry 1 --retry-delay 60"
# 1. search: id, last period, variables (discontinued tables are left out unless includeDiscontinued=true)
$C --fail "$B/tables?query=consumer%20price%20index&lang=en&pageSize=5" | python3 -c 'import json, sys
for t in json.load(sys.stdin)["tables"]:
    print(t["id"], t["lastPeriod"], t["updated"][:10], t["variableNames"])'
sleep 2
# 2. read the variables first: codes stay Norwegian with lang=en (Kjonn, Alder, Tid, ContentsCode)
$C --fail "$B/tables/13760/metadata?lang=en" | python3 -c 'import json, sys
m = json.load(sys.stdin)
for d in m["id"]:
    x = m["dimension"][d]; c = x["category"]["label"]
    print(d, "=", repr(x["label"]), "| optional" if x["extension"].get("elimination") else "| required", "|", dict(list(c.items())[:4]), "+%d more" % (len(c) - 4) if len(c) > 4 else "")'
sleep 2
# 3. newest month of the unemployment rate (LFS), seasonally adjusted, both sexes, 15-74
$C --fail "$B/tables/13760/data?lang=en&outputFormat=json-stat2&valueCodes[Kjonn]=0&valueCodes[Alder]=15-74&valueCodes[Justering]=S&valueCodes[ContentsCode]=ArbledProsArbstyrk&valueCodes[Tid]=top(1)" \
  | python3 -c 'import json, sys
d = json.load(sys.stdin); print(d["label"][:40], "|", list(d["dimension"]["Tid"]["category"]["index"]), d["value"], "| updated", d["updated"])'
sleep 2
# 4. CSV, three newest months of the CPI 12-month rate (Latin-1, periods become columns)
$C --fail "$B/tables/14700/data?lang=en&outputFormat=csv&valueCodes[VareTjenesteGrp]=00&valueCodes[ContentsCode]=Tolvmanedersendring&valueCodes[Tid]=top(3)" | iconv -f latin1 -t utf-8
echo
sleep 2
# 5. headers: the rate-limit policy, no CORS header, no ETag/Last-Modified
$C -D - -o /dev/null "$B/tables/07459/metadata?lang=en" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|etag|last-modified|access-control-allow-origin|x-ratelimit-[a-z]+|retry-after):)'
sleep 2
$C -o /dev/null -w 'metadata 07459: %{size_download} bytes plain, ' "$B/tables/07459/metadata?lang=en"; sleep 2
$C -o /dev/null -w '%{size_download} bytes with Accept-Encoding: gzip\n' -H 'Accept-Encoding: gzip' "$B/tables/07459/metadata?lang=en"
sleep 2
# 6. mistakes are JSON with a title; the status in the body can differ from the HTTP status
T=$(mktemp)
for u in "tables/7459/data?lang=en&valueCodes[Tid]=top(1)" "tables/07459/data?lang=en&valueCodes[Tid]=top(1)" \
         "tables/07459/data?lang=en&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(1)&valueCodes[Kjonn]=M"; do
  $C -o "$T" -w "%{http_code} " "$B/$u"; echo "$(cat "$T")  <- $u"; sleep 2
done
rm -f "$T"
# 7. no robots file on the API host: data.ssb.no/robots.txt is a redirect to an HTML page
$C -o /dev/null -w 'data.ssb.no/robots.txt: HTTP %{http_code} -> %{redirect_url}\n' https://data.ssb.no/robots.txt; sleep 2
$C https://www.ssb.no/robots.txt
echo
echo "Source: Statistics Norway (SSB), https://www.ssb.no, Statbank via $B, CC BY 4.0, accessed $(date -u '+%d %B %Y %H:%M') UTC."
```

Output (from the run on 2026-11-20, 23:39 UTC):

```text
14710 2026M10 2026-11-10 ['contents', 'month']
14711 2025 2026-02-06 ['contents', 'year']
14709 2026 2026-11-10 ['month', 'contents', 'year']
14708 2026M10 2026-11-10 ['derived series', 'contents', 'month']
14702 2026M10 2026-11-10 ['derived series', 'delivery sector', 'contents', 'month']
Kjonn = 'sex' | optional | {'0': 'Both sexes', '2': 'Females', '1': 'Males'} 
Alder = 'age' | optional | {'15-74': '15-74 years', '15-24': '15-24 years', '25-74': '25-74 years'} 
Justering = 'type of adjustment' | required | {'T': 'Trend', '3MGG': 'Seasonal adjusted, 3-months moving average', 'S': 'Seasonally adjusted', 'IS': 'Not seasonally adjusted'} 
ContentsCode = 'contents' | required | {'Arbeidsstyrken': 'Labour force (1000 persons)', 'Sysselsatte': 'Total employment (1000 persons)', 'Ukeverk': 'Man-weeks worked of 37.5 hours (1000)', 'Arbeidsledige': 'Unemployment (LFS) (1000 persons)'} +4 more
Tid = 'month' | required | {'2006M01': '2006M01', '2006M02': '2006M02', '2006M03': '2006M03', '2006M04': '2006M04'} +245 more
13760: Labour force, employment, unemplo | ['2026M09'] [5] | updated 2026-10-22T06:00:00Z
"VareTjenesteGrp","Tolvmanedersendring 2026M08","Tolvmanedersendring 2026M09","Tolvmanedersendring 2026M10"
"00",3.3,3.4,3.6

HTTP/2 200 
content-type: application/json; charset=utf-8
x-ratelimit-resource: SB_API_1MIN
x-ratelimit-limit: 40
x-ratelimit-policy: 40;w=60s
x-ratelimit-remaining: 39
metadata 07459: 50502 bytes plain, 15922 bytes with Accept-Encoding: gzip
400 {"type":"Parameter error","title":"Non-existent table","status":404}  <- tables/7459/data?lang=en&valueCodes[Tid]=top(1)
400 {"type":"Parameter error","title":"Missing selection for mandantory variable","status":400}  <- tables/07459/data?lang=en&valueCodes[Tid]=top(1)
400 {"type":"Parameter error","title":"Non-existent value","status":400}  <- tables/07459/data?lang=en&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(1)&valueCodes[Kjonn]=M
data.ssb.no/robots.txt: HTTP 301 -> https://www.ssb.no/omssb/tjenester-og-verktoy/api
User-agent: *
Disallow: /a/kostra/stt


Source: Statistics Norway (SSB), https://www.ssb.no, Statbank via https://data.ssb.no/api/pxwebapi/v2, CC BY 4.0, accessed 20 November 2026 23:39 UTC.
```

POST also works for long selections: `POST /tables/14700/data?lang=en&outputFormat=json-stat2` with `Content-Type: application/json` and `{"selection": [{"variableCode": "VareTjenesteGrp", "valueCodes": ["00", "01"]}, {"variableCode": "ContentsCode", "valueCodes": ["Tolvmanedersendring"]}, {"variableCode": "Tid", "valueCodes": ["top(1)"]}]}` returned HTTP 200 with `[3.6, 1.4]` (total and food, 2026M10) on 2026-11-20.

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `/tables` `tables[]` | `{id, label, updated, firstPeriod, lastPeriod, timeUnit, variableNames, subjectCode, paths, links, ...}` | `id` is a 5-character string (`"07459"`); `label` starts with the id and ends with the period range; `variableNames` are the English labels (`"sex"`, `"age"`, `"contents"`, `"month"`); `timeUnit` `Annual`, `Quarterly`, `Monthly`, `Weekly`, `Other` (3,146 / 237 / 131 / 3 / 253 of the 3,770 tables listed on 2026-11-20) |
| `/tables` `page` | `{pageNumber, pageSize, totalElements, totalPages, links}` | `pageSize=1000` returned all 398 hits for `query=population` in one page (631,623 bytes) |
| `/tables/{id}` | the same entry for one table, plus `discontinued` | `discontinued: true` on 03013 (CPI 2015=100, "closed series", last period 2025M12); the key was absent on the current tables seen in search |
| `/metadata` `id`, `size`, `role` | variable codes in order, number of values each, `role.time` / `role.geo` / `role.metric` | `role.time[0]` is the time variable (`Tid` in every table seen); 07459: sizes `[994, 2, 106, 1, 41]` |
| `/metadata` `dimension[V].label` | English variable label | what `variableNames` in the search lists |
| `dimension[V].category.label` | `{code: English label}` | `Kjonn`: `{"2": "Females", "1": "Males"}` in 07459, plus `"0": "Both sexes"` in 10211 and 13760 |
| `dimension[V].extension.elimination` | `true` / `false` | `true`: you may leave the variable out and get the total; `false`: you must select it (HTTP 400 otherwise) |
| `dimension[V].extension.codelists` | `[{id, label, type}]` | groupings and value sets: `agg_TiAarigGruppering` "10-years groups", `agg_FemAarigGruppering` "5-years groups", `vs_Kommun` "All municipalities" (952 codes, 357 with people in 2026) |
| `dimension.ContentsCode.category.unit` | `{code: {base, decimals}}` | `{"base": "per cent", "decimals": 1}`; JSON numbers drop trailing zeros (`5` = 5.0) |
| `dimension.ContentsCode.extension.refperiod` | e.g. `"1.1."` (07459), `"01.01."` (10211), `"Month"` (14700, 13760) | the spelling is per table and the same in `/metadata` and `/data`; population is a stock on 1 January |
| `/data` `value` | flat list, one number per cell | in the order of `id`, last variable fastest; within a variable, the order of `category.index` (not sorted by code: `Kjonn` `2` before `1`) |
| `/data` `status` | `{flat index: symbol}` | the guide: `.` category not applicable, `..` not available, `:` confidential; the value is `null` there. No suppressed cell came up in these runs (an expired municipality code returned `0`) |
| `/data` `updated`, `label`, `extension`, `note` | update time (UTC), a label built from the selected variables, `px` table info and `discontinued`, notes | `label` differs from the search label (`"10211: Population, by age, sex and year"`); the 07459 `/metadata` had `extension.px.official-statistics: true` |
| response headers | `content-type: application/json; charset=UTF-8`, `x-ratelimit-policy: 40;w=60s`, `x-ratelimit-limit: 40`, `x-ratelimit-remaining`, `x-cache`, `set-cookie: X-Identity=...` | no `cache-control`, `etag`, `last-modified` or `access-control-allow-origin`; CSV is `text/csv; charset=iso-8859-1` |

## Gotchas

- **Codes are Norwegian, labels are English.** `valueCodes[sex]=*` is HTTP 400 "Non-existent variable"; `valueCodes[Kjonn]=Males` (or `M`) is HTTP 400 "Non-existent value". Always map labels to codes from `/metadata` of that table: the same variable can have different values in different tables (07459 `Kjonn` has no "Both sexes", 10211 has).
- **Keep the leading zero.** `/tables/7459/metadata` is HTTP 404 and `/tables/7459/data` is HTTP 400, both with `"title": "Non-existent table"` and `"status": 404` in the body. Store ids as strings.
- **Required variables.** Leave out a variable whose `elimination` is `false` (`ContentsCode` and `Tid` in every table seen, in 13760 also `Justering`) and you get HTTP 400 "Missing selection for mandantory variable" (SSB's spelling). Leave out one whose `elimination` is `true` and the API returns the total: 07459 with only `ContentsCode` and `Tid` gave `[5627400]`, labelled "07459: Population, by year".
- **Newest period = `top(1)` on the time variable.** Block 1 also checks it equals the table's `lastPeriod`. Periods are text: `2026`, `2026M10` (month), `2026K3` (quarter, `K` for kvartal), `2026H2` (half year), `U` plus a week number in the 3 weekly tables, and ranges such as `2025-2026` or `2025/2026` in some `Other` tables.
- **New CPI base, old tables closed.** The CPI tables moved to 2025=100 (14700, 14710, updated 2026-11-10); 03013 (2015=100) is a "closed series" ending 2025M12 and is hidden from search unless `includeDiscontinued=true`. A closed table id still answers (03013 returns its entry with `discontinued: true`), so check `discontinued` before reusing a table id.
- **Search ranking is loose.** For `population sex age` the first two hits were labour-force tables; for `CPI`, derived series (14707) came first. Filter by `variableNames` and the label, or pass a known table id.
- **Release mornings.** The `updated` stamps seen were 07:00 UTC under Norwegian winter time (CET) and 06:00 UTC under summer time (CEST, which ran to 25 October in 2026) (14700: 2026-11-10T07:00:00Z; 10211: 2026-02-25T07:00:00Z; 13760: 2026-10-22T06:00:00Z; 14090: 2026-06-23T06:00:00Z), that is 08:00 in Norway, the release time the guide names. The guide: avoid 07:55-08:15 unless you need the new figure, figures being revised "will be shown as 0 or dot in the time period 05:00 – 08.00", and tables are unavailable during the 05:00 and 11:30 metadata updates.
- **The rate-limit header is not a countdown.** `x-ratelimit-remaining` read 39 or 38 on every call, even 9 calls in 25 s from one browser; the documented limit (30 a minute per IP, shared by everyone behind that IP) is the one to respect.
- **Too many cells.** All 994 regions x 2 sexes x 106 ages x 41 years of 07459 is HTTP 400 "Too many cells selected"; the guide's limit is 800,000 cells per extract. Narrow with `top(n)`, a code list or fewer values.
- **Municipality codes include expired ones.** `codelist[Region]=vs_Kommun` with `*` gave 952 codes for 2026, 357 of them with people; the others answer `0`, not `null`. Names can be bilingual ("Oslo - Oslove", "Trondheim - Tråante").
- **CSV is Latin-1 and wide.** `outputFormat=csv` puts periods in columns (`"Tolvmanedersendring 2026M10"`) and is `iso-8859-1`; decode it, or use json-stat2 and `tidy()`.
- **curl and brackets.** `valueCodes[Tid]` needs `curl -g` (or `%5B`/`%5D`); the user guide lists the encodings for space, `+`, `"`, `(`, `)`, `[`, `]`.
- **v1 still answers.** `https://data.ssb.no/api/v0/en/table/07459` returned HTTP 200 (27,521 bytes of v1 metadata) on 2026-11-20, but SSB keeps v1 only "during a transition period"; use v2.
- **Credit and no logo.** Show "Source: Statistics Norway (SSB)" with a link to https://www.ssb.no, the table number, the CC BY 4.0 licence and the access date, say if you changed or combined the figures, use no SSB logo, and do not suggest SSB endorses your use.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **English variable codes, labels as value codes, ids without the leading zero, or leaving out `ContentsCode`/`Tid`**: all HTTP 400 or 404 (block 2).
- **A whole large table in one call**: HTTP 400 "Too many cells selected" above 800,000 cells.
- **Cross-origin `fetch()` from another site**: the API sends no `Access-Control-Allow-Origin`; run it from a data.ssb.no page or outside the browser.
- **Conditional GETs**: no `ETag` or `Last-Modified`; compare `updated` from `/tables/{id}` instead.
- **Not tested:** a 429 (never provoked), a call during the 05:00 or 11:30 metadata update or at 08:00 on a release day, a suppressed (`null`) cell, `outputFormat` values other than json-stat2 and csv, `stub`/`heading`/`outputFormatParams`, saved queries (`/savedqueries/{id}`), the Klass classification API (`data.ssb.no/api/klass/v1`) and `lang=no` beyond one call.
