# Statistics Sweden (SCB) Statistical Database via statistikdatabasen.scb.se (PxWebApi v2) - Get Sweden's Newest Population, or the Newest Value of Any SCB Table Found by Keyword (CPI, Unemployment): Search Tables, Read Their Variables, Pull the Latest Periods as Tidy Rows (JSON-stat API, no key)

Field-tested against statistikdatabasen.scb.se on 2026-11-23 (US Pacific afternoon; 2026-11-23 23:55 UTC to 2026-11-24 00:07 UTC) using a fresh Browser Use cloud browser (logged out; one session, 23:59-00:03 UTC) plus Python `urllib` and `curl` from a Linux machine. 13 browser page loads (one API answer, then two robots.txt URLs, three www.scb.se pages and the API again in each of block 2's two runs) and 71 in-page `fetch()` calls (block 1 ran three times, the first stopping on a search with no hits; block 2 twice), 42 urllib calls (block 3 ran 3 times: twice with an empty cache, once warm, plus 3 calls testing its pause at a low `X-Rate-Limit-Remaining` with the threshold raised by hand; 6 of the calls were robots.txt) and 92 curl calls (64 while exploring, one of them RFC 9309 from rfc-editor.org; 28 in block 4, which ran twice), all serial and at least 0.5 s apart. Every data call was HTTP 200 except the deliberate HTTP 400 and 404 probes of mistakes and the HTTP 404 of the API host's robots.txt. No 403 or 429, no challenge, no key, no login, no cookie. Data calls took 0.7-2.3 s in curl (a TAB638 population request took 4.6 s in an earlier check at 23:19 UTC) and at most 1.6 s in the browser. An independent verifier re-ran all four blocks verbatim on 2026-11-24 00:10-00:15 UTC (a second fresh cloud browser, urllib with an empty and then a warm cache, curl): every block ran and printed the same tables, codes and numbers; only the clock, timings and rate-limit countdowns changed. After a code review, blocks 1, 3 and 4 changed and re-ran on 2026-11-24 between 00:28 and 00:36 UTC (browser blocks in a new cloud browser); the outputs shown for them come from those runs. A second review round changed block 1 again; its re-run at 00:44 UTC in another new cloud browser printed the same apart from times.

robots.txt (checked 2026-11-23, curl, the cloud browser and `urllib.robotparser`): https://statistikdatabasen.scb.se/robots.txt is HTTP 404, so the API host has no robots rules and no named AI-agent groups; RFC 9309 section 2.3.1.3 says that for 400-499 answers "the crawler MAY access any resources on the server". https://www.scb.se/robots.txt is `Sitemap: https://www.scb.se/sitemap.xml`, `User-agent: *` and an empty `Disallow:` (allow everything), with no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`. Every path this skill uses is allowed for all 11 agents (block 3). Terms: the open-data page https://www.scb.se/en/services/open-data-api/ says "We use the licence CC0 for this data, which means that you may use and disseminate or provide such data without any requirement to state the source", recommends "Source: Statistics Sweden" if you state one, says statistics "which have a source reference to another agency, you should state this", "If you yourself have processed data from Statistics Sweden, do not state the source", and "You may not present a service as an “official cooperation” or “partnership” with Statistics Sweden." The API's own `/config` gives the licence as CC0 (https://creativecommons.org/share-your-work/public-domain/cc0/) and the credit line as "Source: Statistics Sweden". The PxWebApi page https://www.scb.se/en/services/open-data-api/pxwebapi/ sets the limits: "a limit of 150 000 data cells and make a maximum number of calls of 30 per 10 seconds. The limit is per IP address and can therefore apply to multiple colleagues at the same workplace". The website terms https://www.scb.se/en/About-us/about-the-website-and-terms-of-use/ put the statistics on scb.se itself under CC BY 4.0 ("you must always state Statistics Sweden as the source") and say photos and illustrations "cannot be copied and spread without permission". No AI/ML, scraping, automated-access or non-commercial clause on the three pages (block 2 found none of the words scrap, artificial intelligence, machine learning, non-commercial, robot or crawl on them). Naming: this skill says "Statistics Sweden (SCB)", credits "Source: Statistics Sweden" with a link to www.scb.se, uses no SCB logo, and is not an official cooperation or partnership with, or endorsed by, Statistics Sweden.

**Official, but check the period and the table.** Every answer carries the table ID (`TAB6473`), the period (`2026M09`, `2025`, `2026K3`), the `updated` time and the unit. SCB splits long series into a closed old table and a new one (population 1968-2024 in TAB638, 2025 in TAB5557); say which one you used.

## Quick summary

- **No scraping.** Three GET endpoints, JSON, no key: `GET https://statistikdatabasen.scb.se/api/v2/tables?query=population&lang=en` (search; `pageSize`, `pageNumber`, `pastDays`, `includeDiscontinued=true`), `GET /tables/{id}/metadata?lang=en` (the variables, their codes and English labels, JSON-stat 2.0) and `GET /tables/{id}/data?lang=en&outputFormat=json-stat2&valueCodes[Var]=...` (one cell per combination; `*`, `top(n)`, lists `00,01`; `codelist[Region]=vs_CKM03Kommun` for municipalities). `outputFormat=csv` also works; `GET /config` returns the limits, licence and credit line. CORS is open, so `fetch()` works from any page.
- **Answer (run 2026-11-24, 00:00 UTC):** Sweden's population at the end of **September 2026**: **10,621,725** (TAB6473, monthly, updated 2026-11-11; 10,621,103 in August). Population on 31 December **2025**: **10,605,529** (TAB4365 and TAB5557, updated 2026-02-24). The older yearly table TAB638 still answers but stops at **2024**: 10,551,707 (2023) and 10,587,710 (2024). CPI **October 2026** (TAB6596, 2020=100): index **125.97**, annual change **0.9**. Unemployment rate (LFS), seasonally adjusted, 15-74, **October 2026**: **8.2 per cent**, 476.4 thousand persons (TAB6387, updated 2026-11-20).
- **Pick the table with the newest `lastPeriod`.** Search returns closed series next to current ones and none is flagged `discontinued` (TAB638 "Year 1968-2024", TAB1625 "Month 2000M01-2024M12", the CPI "1980=100 (no update after 2025M12)" tables). Block 1 keeps every hit with exactly the variables you name and a label containing your words, then takes the newest.
- **Read `/metadata` first.** Variable and value codes stay Swedish with `lang=en` (`Region`, `Kon`, `Alder`, `Civilstand`, `Forandringar`, `ContentsCode`, `Tid`; `Kon` total is `TotSa` in one table and `1+2` in another, `ALÖSP` = unemployment rate). Blocks 1 and 3 pick by English label and send codes.
- **Totals and parts disagree on purpose.** From reference year 2025 SCB adds "a small controlled random uncertainty"; men + women came to 10,621,727 against a total of 10,621,725, the 21 counties to 10,621,721 and the 290 municipalities to 10,621,746. Use the published total; do not add parts.
- **Rate limit:** 30 calls per 10 s per IP and 150,000 cells per extract (the PxWebApi page and `/config`). Unlike many APIs, `X-Rate-Limit-Remaining` is a real countdown (29 down to 21 over block 1's 9 calls) with the window end in `X-Rate-Limit-Reset`. Blocks 1 and 3 run serially, 0.5 s apart, pause until the reset when 2 or fewer calls are left, wait once on 403, 429, 5xx or a network error (`Retry-After`, else the reset time, else 10 s; over 120 s they stop) and stop after that. Block 2 only inspects answers (about one call a second, no retry); block 4 sleeps 1 s between calls and lets `curl --retry 1` retry once on a timeout or HTTP 408, 429, 500, 502, 503 or 504.

## What works

### 1. Newest periods for a topic: search, pick the newest matching table, read its variables, pull tidy rows (browser)

`on_scb_tab()` opens one logged-out statistikdatabasen.scb.se API answer so `fetch()` runs same-origin (cross-origin works too, see block 2). `get()` returns parsed JSON on HTTP 200, pauses when the countdown is low, waits once on 403/429/5xx or a network error and otherwise raises. 9 `fetch()` calls in the run below: per topic one search page of 100 hits, one `/metadata`, one `/data`; `find_table` reads up to 2 more pages when the search has more than 100 hits. Add a topic by naming its search words, the exact variable labels, a label fragment and the values you want. Leave small words such as "of" out of the query: `labour status type of data sex age LFS` found 0 tables, `unemployment rate LFS` found 7.

```python
import email.utils, json, time
from datetime import datetime, timezone
from urllib.parse import urlencode

API = "https://statistikdatabasen.scb.se/api/v2"
PAUSE = 0.5   # SCB: "a maximum number of calls of 30 per 10 seconds", per IP address; this stays at 20 or fewer
UTC = timezone.utc

# One entry per question. Search words, then the table must have exactly these variable names (English labels)
# and a label containing `label_has`. Of the tables that match, the one with the newest lastPeriod wins (SCB splits
# long series into an old closed table and a new one). `pick` maps a variable label to the value labels you want;
# the time variable gets top(2) (the newest period and the one before); a variable you leave out is dropped if the
# table allows that (the API then returns its total), otherwise every value comes back.
TOPICS = {
    "population, newest month": dict(
        query="population statistics region sex month",
        vars={"region", "population changes", "sex", "observations", "month"},
        label_has="Population statistics by region and sex",
        pick={"region": ["Sweden"], "population changes": ["population"],
              "sex": ["total, all men and women", "men", "women"]}),
    "consumer price index": dict(
        query="consumer price index total 2020=100", vars={"observations", "month"},
        label_has="Consumer Price Index (CPI), total 2020=100",
        pick={"observations": ["CPI, fixed index numbers", "Annual changes"]}),
    "unemployment": dict(
        query="unemployment rate LFS", vars={"labour status", "type of data", "sex", "age", "observations", "month"},
        label_has="Population aged 15-74 (LFS) by labour status, type of data, sex and age",
        pick={"labour status": ["unemployment rate, percent", "unemployed, thousands"],
              "type of data": ["seasonally adjusted"], "sex": ["total"], "age": ["total 15–74 years"]}),
}

def on_scb_tab():
    """fetch() runs same-origin from a statistikdatabasen.scb.se page."""
    try:
        if js("location.origin") == "https://statistikdatabasen.scb.se":
            return
    except Exception:
        pass
    new_tab(API + "/tables?query=population&lang=en&pageSize=1")
    wait_for_load()
    if js("location.origin") != "https://statistikdatabasen.scb.se" or '"tables"' not in (js("document.body ? document.body.innerText : ''") or ""):
        raise RuntimeError(f"statistikdatabasen.scb.se did not serve the table list (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def wait_for(headers, default):
    """Seconds to wait before retrying: Retry-After (seconds or a date), else X-Rate-Limit-Reset (a UTC time), else `default`."""
    v = (headers.get("retry-after") or "").strip()
    if v.isdigit():
        return int(v)
    for parse, t in ((email.utils.parsedate_to_datetime, v),
                     (lambda s: datetime.fromisoformat(s[:26]).replace(tzinfo=UTC), headers.get("x-rate-limit-reset") or "")):
        try:
            return max(0, int((parse(t) - datetime.now(UTC)).total_seconds()) + 1)
        except (TypeError, ValueError):
            pass
    return default

calls = []
def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    left = r["headers"].get("x-rate-limit-remaining")
    calls.append((r["status"], left, round(time.time() - t0, 1)))
    # a real countdown of the 30 calls per 10 s for this IP (shared with anyone else behind it): pause near zero
    time.sleep(max(PAUSE, min(wait_for({"x-rate-limit-reset": r["headers"].get("x-rate-limit-reset")}, 10), 11))
               if left and left.isdigit() and int(left) <= 2 else PAUSE)
    return r

def get(path, **params):
    """GET API + path -> parsed JSON. Waits once on 403/429 (over the call limit), 5xx or a network error
    (Retry-After or X-Rate-Limit-Reset, else 10 s; over 120 s stops). Raises on anything else, with SCB's error title."""
    url = API + path + "?" + urlencode(params)
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 403, 429, 500, 502, 503, 504) and attempt == 0:
            wait = wait_for(r["headers"], 10)
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:150]!r}; stopping")
    return json.loads(r["text"])

def find_table(query, vars, label_has, max_pages=3):
    """Search and keep the hits whose variable names are exactly `vars` and whose label contains `label_has`;
    return the one with the newest lastPeriod (then the newest `updated`). Reads every page of 100; stops with an
    error instead of guessing when there are more than `max_pages` pages."""
    found, page = [], 1
    want = " ".join(label_has.lower().split())
    while True:
        res = get("/tables", query=query, lang="en", pageSize=100, pageNumber=page)
        hits = res["tables"]
        if page == 1:
            print(f"  search {query!r}: {res['page']['totalElements']} tables; top 3: "
                  + "; ".join(f"{t['id']} {t['lastPeriod']} {t['label'][:40]}" for t in hits[:3]))
        found += [t for t in hits if set(t["variableNames"]) == vars and want in " ".join(t["label"].lower().split())
                  and not t.get("discontinued")]
        if page >= res["page"]["totalPages"]:
            break
        if page >= max_pages:
            raise RuntimeError(f"{query!r}: {res['page']['totalPages']} pages of hits, only {max_pages} read; "
                               "a newer table could be on a later page: narrow the query")
        page += 1
    if not found:
        raise RuntimeError(f"no table for {query!r} with variables {sorted(vars)} and label {label_has!r}: read the hits")
    found.sort(key=lambda t: (t["lastPeriod"], t["updated"]), reverse=True)   # same time unit, so text order works
    if len(found) > 1:
        print(f"  {len(found)} tables match: " + ", ".join(f"{t['id']} (to {t['lastPeriod']})" for t in found) + f"; newest: {found[0]['id']}")
    return found[0]

def tidy(ds):
    """json-stat2 -> list of dicts, one per cell. `value` is one flat list in the order of ds['id'] (last
    dimension fastest); a missing cell is null with a symbol in ds['status'] (keyed by flat index)."""
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

def latest(table_id, pick=None, n=2):
    """Newest `n` periods of one table as tidy rows. Reads /metadata first: the variable and value codes are
    Swedish (Region, Kon, Alder, Tid, ContentsCode; Kon 'TotSa' or '1+2') even with lang=en, so `pick` uses the English labels."""
    meta = get(f"/tables/{table_id}/metadata", lang="en")
    time_var = meta["role"]["time"][0]
    q = {f"valueCodes[{time_var}]": f"top({n})"}
    for d in meta["id"]:
        dim = meta["dimension"][d]
        lab = dim["label"]
        if d == time_var:
            continue
        if lab in (pick or {}):
            code = {v: k for k, v in dim["category"]["label"].items()}
            missing = [w for w in pick[lab] if w not in code]
            if missing:
                raise RuntimeError(f"{table_id} {d} ({lab}): no value {missing}; it has {list(code)[:12]}")
            q[f"valueCodes[{d}]"] = ",".join(code[w] for w in pick[lab])
        elif not dim["extension"].get("elimination"):
            q[f"valueCodes[{d}]"] = "*"   # mandatory variable: leaving it out is an HTTP 400
    ds = get(f"/tables/{table_id}/data", lang="en", outputFormat="json-stat2", **q)
    return meta, ds, tidy(ds)

on_scb_tab()
now = datetime.now(UTC)
print(f"Statistics Sweden (SCB) Statistical Database via PxWebApi v2, checked {now:%Y-%m-%d %H:%M} UTC")
for topic, t in TOPICS.items():
    print(f"\n{topic}:")
    tab = find_table(t["query"], t["vars"], t["label_has"])
    meta, ds, rows = latest(tab["id"], t.get("pick"))
    time_var = meta["role"]["time"][0]
    periods = sorted({r[time_var] for r in rows})
    if periods[-1] != tab["lastPeriod"]:
        raise RuntimeError(f"{tab['id']}: top(2) ended at {periods[-1]}, the table list says {tab['lastPeriod']}: stop")
    cc = ds["dimension"]["ContentsCode"]
    print(f"  table {tab['id']} ({tab['label']}), updated {ds['updated'][:16].replace('T', ' ')} UTC, "
          f"periods {periods}; codes {ds['id']}")
    keys = [d for d in ds["id"] if d not in (time_var, "ContentsCode")]
    for r in rows:
        u = cc["category"].get("unit", {}).get(r["ContentsCode"], {})   # e.g. {"base": "index", "decimals": 2}
        val = f"{r['value']:,.{u.get('decimals', 0)}f}" if r["value"] is not None else f"null, status {r['status']!r}"
        print(f"    {r[time_var]}  " + "  ".join(r[d + "_label"] for d in keys)
              + f"  {r['ContentsCode_label']}: {val} {u.get('base', '')}")
    if topic == "population, newest month":
        new = {r["Kon_label"]: r["value"] for r in rows if r[time_var] == periods[-1]}
        tot, parts = new["total, all men and women"], new["men"] + new["women"]
        print(f"  men + women = {parts:,}; total = {tot:,}; difference {parts - tot:+,} "
              "(SCB adds a small controlled random uncertainty from 2025 on, so parts need not sum to the total)")
print(f"\n{len(calls)} API calls, statuses {sorted({s for s, _, _ in calls})}, "
      f"x-rate-limit-remaining seen {sorted({x for _, x, _ in calls if x}, key=int)}, slowest {max(t for _, _, t in calls)} s")
print(f"Source: Statistics Sweden, https://www.scb.se, Statistical Database tables via {API}, CC0, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:32 UTC, in a new cloud browser; the 00:00 UTC run printed the same numbers; before that, one run stopped with "no table" on the 0-hit query above and one printed the same numbers before the pause at a low countdown was added):

```text
Statistics Sweden (SCB) Statistical Database via PxWebApi v2, checked 2026-11-24 00:32 UTC

population, newest month:
  search 'population statistics region sex month': 2 tables; top 3: TAB6473 2026M09 Population statistics by region and sex.; TAB1625 2024M12 Population statistics by region and sex.
  2 tables match: TAB6473 (to 2026M09), TAB1625 (to 2024M12); newest: TAB6473
  table TAB6473 (Population statistics by region and sex.  Month 2025M01-2026M09), updated 2026-11-11 07:00 UTC, periods ['2026M08', '2026M09']; codes ['Region', 'Forandringar', 'Kon', 'ContentsCode', 'Tid']
    2026M08  Sweden  population  total, all men and women  Population: 10,621,103 number
    2026M09  Sweden  population  total, all men and women  Population: 10,621,725 number
    2026M08  Sweden  population  men  Population: 5,336,460 number
    2026M09  Sweden  population  men  Population: 5,336,571 number
    2026M08  Sweden  population  women  Population: 5,284,642 number
    2026M09  Sweden  population  women  Population: 5,285,156 number
  men + women = 10,621,727; total = 10,621,725; difference +2 (SCB adds a small controlled random uncertainty from 2025 on, so parts need not sum to the total)

consumer price index:
  search 'consumer price index total 2020=100': 13 tables; top 3: TAB7052 2025 Consumer Price Index (CPI), total annual; TAB6596 2026M10 Consumer Price Index (CPI), total 2020=1; TAB3414 2026M09 Rate of change Producer Price Index by m
  table TAB6596 (Consumer Price Index (CPI), total 2020=100. Month 1980M01-2026M10), updated 2026-11-12 07:00 UTC, periods ['2026M09', '2026M10']; codes ['ContentsCode', 'Tid']
    2026M09    CPI, fixed index numbers: 125.94 index
    2026M10    CPI, fixed index numbers: 125.97 index
    2026M09    Annual changes: 1.1 index
    2026M10    Annual changes: 0.9 index

unemployment:
  search 'unemployment rate LFS': 7 tables; top 3: TAB6752 2025 Population aged 65-89 (LFS) by labour st; TAB6514 2025 Population aged 15-74 (LFS) by labour st; TAB6512 2026M10 Population aged 15-74 (LFS) by labour st
  table TAB6387 (Population aged 15-74 (LFS) by labour status, type of data, sex and age. Month 2001M01-2026M10), updated 2026-11-20 07:00 UTC, periods ['2026M09', '2026M10']; codes ['Arbetskraftstillh', 'TypData', 'Kon', 'Alder', 'ContentsCode', 'Tid']
    2026M09  unemployment rate, percent  seasonally adjusted  total  total 15–74 years  Population aged 15-74: 8.5 thousands/percent
    2026M10  unemployment rate, percent  seasonally adjusted  total  total 15–74 years  Population aged 15-74: 8.2 thousands/percent
    2026M09  unemployed, thousands  seasonally adjusted  total  total 15–74 years  Population aged 15-74: 496.5 thousands/percent
    2026M10  unemployed, thousands  seasonally adjusted  total  total 15–74 years  Population aged 15-74: 476.4 thousands/percent

9 API calls, statuses [200], x-rate-limit-remaining seen ['21', '22', '23', '24', '25', '26', '27', '28', '29'], slowest 1.4 s
Source: Statistics Sweden, https://www.scb.se, Statistical Database tables via https://statistikdatabasen.scb.se/api/v2, CC0, accessed 24 November 2026 00:32 UTC.
```

### 2. robots.txt, the open-data, PxWebApi and terms pages, `/config`, and what the API does with mistakes (browser)

6 page loads and 23 in-page `fetch()` calls in the same tab. The `/config` call runs cross-origin from www.scb.se: a CORS-blocked `fetch()` would fail, and it returned the body.

```python
import json, time

API = "https://statistikdatabasen.scb.se/api/v2"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(url):
    """One in-page GET -> {status, headers, text}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(url if url.startswith("http") else API + url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1)   # 30 calls per 10 s per IP (SCB); this block makes about one a second
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    time.sleep(1)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    ct = js("document.contentType")
    return st, ct, js("location.href"), js("(document.body || document.documentElement).textContent || ''") or ""

for url in ("https://statistikdatabasen.scb.se/robots.txt", "https://www.scb.se/robots.txt"):
    st, ct, href, txt = page(url)
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    print(f"{url.split('//')[1]:<40} HTTP {st} {ct}: {lines if ct.startswith('text/plain') else (txt.strip()[:60] or '(empty body)')!r}")

for url, needles in (
    ("https://www.scb.se/en/services/open-data-api/", [
        "We use the licence CC0 for this data, which means that you may use and disseminate or provide such data without any requirement to state the source",
        "If you choose to state the source, we recommend putting (when stating it in English)",
        "which have a source reference to another agency, you should state this",
        "If you yourself have processed data from Statistics Sweden, do not state the source",
        "You may not present a service as an “official cooperation” or “partnership” with Statistics Sweden",
        "You may perform a maximum of ten call-ups in a 10-second period from an IP address",
        "You can retrieve a maximum of 100,000 values per table",
        "The statistics distributed by Statistics Sweden via the API are continually updated as we correct source data"]),
    ("https://www.scb.se/en/services/open-data-api/pxwebapi/", [
        "PxWebApi v2, which was launched October 2025. It will replace PxWebApi v1",
        "You can extract entire or parts of tables with a limit of 150 000 data cells and make a maximum number of calls of 30 per 10 seconds",
        "The limit is per IP address and can therefore apply to multiple colleagues at the same workplace"]),
    ("https://www.scb.se/en/About-us/about-the-website-and-terms-of-use/", [
        "Statistics Sweden uses the standardised license Creative Commons Attribution 4.0 International (CC-BY 4.0)",
        "you must always state Statistics Sweden as the source",
        "Photos and illustrations found on the website cannot be copied and spread without permission from Statistics Sweden"]),
):
    st, ct, href, txt = page(url)
    flat = " ".join(txt.split())
    short = href.split("//")[1].replace("www.scb.se/en/", "")
    for n in needles:
        print(f"{short:<48} HTTP {st}: {'found' if n in flat else 'MISSING'}: {n[:72]!r}")
    bad = [w for w in ("scrap", "artificial intelligence", "machine learning", "non-commercial", "noncommercial", "robot", "crawl")
           if w in flat.lower()]
    print(f"{short:<48} words scrap/AI/ML/non-commercial/robot/crawl on the page: {bad or 'none'}")

# CORS: the API answers a cross-origin fetch() from www.scb.se (Access-Control-Allow-Origin: *)
r = raw(API + "/config")   # a CORS-blocked fetch() would end as status 0 (TypeError), not a readable body
print(f"\ncross-origin fetch() from {js('location.origin')} to /config: HTTP {r['status']}, body readable: {r['text'].startswith('{')}")
cfg = json.loads(r["text"])
print("config:", {k: cfg[k] for k in ("apiVersion", "maxDataCells", "maxCallsPerTimeWindow", "timeWindow", "license", "defaultLanguage", "dataFormats")},
      "sourceReferences", [s["text"] for s in cfg["sourceReferences"]])

page(API + "/tables?query=population&lang=en&pageSize=1")   # back on the API host
print()

def brief(r):
    t = " ".join(r["text"].split())
    return f"HTTP {r['status']}: {t[:100]}"

D = "lang=en&outputFormat=json-stat2&valueCodes[Tid]=top(1)"
for label, path in (
    ("table id without TAB: 638             ", "/tables/638/metadata?lang=en"),
    ("unknown table TAB99999                ", "/tables/TAB99999/metadata?lang=en"),
    ("lower case tab638                     ", "/tables/tab638?lang=en"),
    ("lower case variable code region       ", f"/tables/TAB638/data?{D}&valueCodes[ContentsCode]=BE0101N1&valueCodes[region]=00"),
    ("value label 'Sweden' as a code        ", f"/tables/TAB638/data?{D}&valueCodes[ContentsCode]=BE0101N1&valueCodes[Region]=Sweden"),
    ("ContentsCode left out                 ", f"/tables/TAB638/data?{D}&valueCodes[Region]=00"),
    ("TAB5557, Civilstand/Alder left out    ", f"/tables/TAB5557/data?{D}&valueCodes[Region]=00&valueCodes[ContentsCode]=000007ME"),
    ("every region, age, sex, status x 3 yrs", "/tables/TAB638/data?lang=en&valueCodes[Region]=*&valueCodes[Civilstand]=*&valueCodes[Alder]=*"
                                               "&valueCodes[Kon]=*&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(3)"),
    ("lang=fi                               ", f"/tables/TAB638/data?lang=fi&valueCodes[Tid]=top(1)&valueCodes[ContentsCode]=BE0101N1"),
    ("code 1+2 with a raw +                 ", f"/tables/TAB4365/data?{D}&valueCodes[ContentsCode]=000000LV&valueCodes[Kon]=1+2"),
    ("code 1+2 as 1%2B2                     ", f"/tables/TAB4365/data?{D}&valueCodes[ContentsCode]=000000LV&valueCodes[Kon]=1%2B2"),
    ("code ALÖSP typed raw (fetch encodes)  ", f"/tables/TAB6387/data?{D}&valueCodes[Arbetskraftstillh]=ALÖSP&valueCodes[TypData]=SR_DATA&valueCodes[ContentsCode]=*"),
):
    print(f"{label} {brief(raw(path))}")

# Which table holds Sweden's population at year end? The 1968-2024 table stops; 2025 sits in new tables.
print()
for tid, q in (("TAB638", "valueCodes[Region]=00&valueCodes[ContentsCode]=BE0101N1"),
               ("TAB5557", "valueCodes[Region]=00&valueCodes[Civilstand]=SC&valueCodes[Alder]=TotSA&valueCodes[Kon]=TotSa&valueCodes[ContentsCode]=000007ME"),
               ("TAB4365", "valueCodes[ContentsCode]=000000LV")):
    info = json.loads(raw(f"/tables/{tid}?lang=en")["text"])
    ds = json.loads(raw(f"/tables/{tid}/data?{D.replace('top(1)', 'top(2)')}&{q}")["text"])
    per = sorted(ds["dimension"]["Tid"]["category"]["index"], key=ds["dimension"]["Tid"]["category"]["index"].get)
    print(f"{tid:<7} {info['label'][:62]:<62} discontinued={info.get('discontinued', False)!s:<5} updated {info['updated'][:10]}: "
          + ", ".join(f"{p} {v:,}" for p, v in zip(per, ds["value"])))
note = (json.loads(raw("/tables/TAB4365/metadata?lang=en")["text"]).get("note") or [""])[0]
print(f"TAB4365 note: {' '.join(note.split())[:205]!r}")

a = json.loads(raw("/tables?query=population&lang=en&pageSize=1")["text"])["page"]["totalElements"]
b = json.loads(raw("/tables?query=population&lang=en&pageSize=1&includeDiscontinued=true")["text"])["page"]["totalElements"]
print(f"search 'population': {a} tables, {b} with includeDiscontinued=true")

r = raw("/tables/TAB6473/data?lang=en&outputFormat=csv&valueCodes[Region]=00,01&valueCodes[Forandringar]=100&valueCodes[Kon]=TotSa"
        "&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(3)")
print(f"csv: HTTP {r['status']} {r['headers'].get('content-type')}: {r['text'].strip().splitlines()}")
h = r["headers"]
print("headers:", {k: h.get(k) for k in ("cache-control", "etag", "last-modified", "access-control-allow-origin",
                                          "x-rate-limit-limit", "x-rate-limit-remaining", "x-rate-limit-reset")})
print("Source: Statistics Sweden, https://www.scb.se, Statistical Database via " + API + ", CC0.")
```

Output (from the run on 2026-11-24, 00:02-00:03 UTC; the first run at 00:01 UTC printed the same lines except the countdown and the CORS line, which then read a header the browser does not expose):

```text
statistikdatabasen.scb.se/robots.txt     HTTP 404 text/html: 'This statistikdatabasen.scb.se page can’t be found\n         '
www.scb.se/robots.txt                    HTTP 200 text/plain: ['Sitemap: https://www.scb.se/sitemap.xml', 'User-agent: *', 'Disallow:']
services/open-data-api/                          HTTP 200: found: 'We use the licence CC0 for this data, which means that you may use and d'
services/open-data-api/                          HTTP 200: found: 'If you choose to state the source, we recommend putting (when stating it'
services/open-data-api/                          HTTP 200: found: 'which have a source reference to another agency, you should state this'
services/open-data-api/                          HTTP 200: found: 'If you yourself have processed data from Statistics Sweden, do not state'
services/open-data-api/                          HTTP 200: found: 'You may not present a service as an “official cooperation” or “partnersh'
services/open-data-api/                          HTTP 200: found: 'You may perform a maximum of ten call-ups in a 10-second period from an '
services/open-data-api/                          HTTP 200: found: 'You can retrieve a maximum of 100,000 values per table'
services/open-data-api/                          HTTP 200: found: 'The statistics distributed by Statistics Sweden via the API are continua'
services/open-data-api/                          words scrap/AI/ML/non-commercial/robot/crawl on the page: none
services/open-data-api/pxwebapi/                 HTTP 200: found: 'PxWebApi v2, which was launched October 2025. It will replace PxWebApi v'
services/open-data-api/pxwebapi/                 HTTP 200: found: 'You can extract entire or parts of tables with a limit of 150 000 data c'
services/open-data-api/pxwebapi/                 HTTP 200: found: 'The limit is per IP address and can therefore apply to multiple colleagu'
services/open-data-api/pxwebapi/                 words scrap/AI/ML/non-commercial/robot/crawl on the page: none
About-us/about-the-website-and-terms-of-use/     HTTP 200: found: 'Statistics Sweden uses the standardised license Creative Commons Attribu'
About-us/about-the-website-and-terms-of-use/     HTTP 200: found: 'you must always state Statistics Sweden as the source'
About-us/about-the-website-and-terms-of-use/     HTTP 200: found: 'Photos and illustrations found on the website cannot be copied and sprea'
About-us/about-the-website-and-terms-of-use/     words scrap/AI/ML/non-commercial/robot/crawl on the page: none

cross-origin fetch() from https://www.scb.se to /config: HTTP 200, body readable: True
config: {'apiVersion': '2.3.2', 'maxDataCells': 150000, 'maxCallsPerTimeWindow': 30, 'timeWindow': 10, 'license': 'https://creativecommons.org/share-your-work/public-domain/cc0/', 'defaultLanguage': 'sv', 'dataFormats': ['json-stat2', 'csv', 'px', 'xlsx', 'html', 'json-px']} sourceReferences ['Source: Statistics Sweden', 'Källa: SCB']

table id without TAB: 638              HTTP 404: {"type":"Parameter error","title":"Non-existent table","status":404}
unknown table TAB99999                 HTTP 404: {"type":"Parameter error","title":"Non-existent table","status":404}
lower case tab638                      HTTP 200: {"language":"en","id":"TAB638","label":"Population by region, marital status, age and sex. Year 1968
lower case variable code region        HTTP 200: {"version":"2.0","class":"dataset","label":"Population by region and year","source":"Statistics Swed
value label 'Sweden' as a code         HTTP 400: {"type":"Parameter error","title":"Non-existent value","status":400}
ContentsCode left out                  HTTP 400: {"type":"Parameter error","title":"Missing selection for mandantory variable","status":400}
TAB5557, Civilstand/Alder left out     HTTP 400: {"type":"Parameter error","title":"Missing selection for mandantory variable","status":400}
every region, age, sex, status x 3 yrs HTTP 400: {"type":"Parameter error","title":"Too many cells selected","status":400,"detail":"Too many cells se
lang=fi                                HTTP 400: {"type":"Parameter error","title":"Unsupported language","status":400}
code 1+2 with a raw +                  HTTP 400: {"type":"Parameter error","title":"Non-existent value","status":400}
code 1+2 as 1%2B2                      HTTP 200: {"version":"2.0","class":"dataset","label":"Population by sex and year","source":"Statistics Sweden"
code ALÖSP typed raw (fetch encodes)   HTTP 200: {"version":"2.0","class":"dataset","label":"Population aged 15-74 by labour status, type of data and

TAB638  Population by region, marital status, age and sex.  Year 1968- discontinued=False updated 2025-02-21: 2023 10,551,707, 2024 10,587,710
TAB5557 Population by region, marital status, age and sex. Year 2025   discontinued=False updated 2026-02-24: 2025 10,605,529
TAB4365 Population and population changes in Sweden by sex. Year 1749- discontinued=False updated 2026-02-24: 2024 10,587,710, 2025 10,605,529
TAB4365 note: 'From the reference year 2025 onwards, a small controlled random uncertainty is introduced in all reported data. The uncertainty has been added to protect individuals so that no one risks being exposed in t'
search 'population': 319 tables, 358 with includeDiscontinued=true
csv: HTTP 200 text/csv; charset=iso-8859-1: ['"Region","Forandringar","Kon","000007SR 2026M07","000007SR 2026M08","000007SR 2026M09"', '"00","100","TotSa",10613531,10621103,10621725', '"01","100","TotSa",2496136,2498257,2498302']
headers: {'cache-control': None, 'etag': None, 'last-modified': None, 'access-control-allow-origin': None, 'x-rate-limit-limit': '10s', 'x-rate-limit-remaining': '23', 'x-rate-limit-reset': '2026-11-24T00:03:20.7250422Z'}
Source: Statistics Sweden, https://www.scb.se, Statistical Database via https://statistikdatabasen.scb.se/api/v2, CC0.
```

### 3. Same API with Python urllib: robots check for every agent, what was published lately, population by month and year, counties and municipalities, metadata cache (no browser)

Sends a descriptive User-Agent. The API sends no `ETag`, `Last-Modified` or gzip (`/metadata` for TAB638 is 24,319 bytes either way), so the cache keeps each table's `/metadata` on disk and re-downloads it only when the table's `updated` stamp in `/tables/{id}` (one small call) has changed.

```python
import email.utils, json, os, sys, time, urllib.error, urllib.request, urllib.robotparser
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlencode

API = "https://statistikdatabasen.scb.se/api/v2"
UA = "scb-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/scb-skill"
CACHE = os.path.expanduser(CACHE_DIR)
PAUSE = 0.5   # "a maximum number of calls of 30 per 10 seconds", per IP address (SCB's PxWebApi page and /config)
UTC = timezone.utc
stats = Counter()

def wait_for(headers, default):
    """Seconds to wait: Retry-After (seconds or a date), else X-Rate-Limit-Reset (a UTC time), else `default`."""
    v = (headers.get("Retry-After") or "").strip()
    if v.isdigit():
        return int(v)
    for parse, t in ((email.utils.parsedate_to_datetime, v),
                     (lambda s: datetime.fromisoformat(s[:26]).replace(tzinfo=UTC), headers.get("X-Rate-Limit-Reset") or "")):
        try:
            return max(0, int((parse(t) - datetime.now(UTC)).total_seconds()) + 1)
        except (TypeError, ValueError):
            pass
    return default

def get(path, **params):
    """GET API + path -> parsed JSON. Serial; pauses until X-Rate-Limit-Reset when X-Rate-Limit-Remaining is 2
    or less. On 403/429 (over the limit), 5xx or a network error waits once (Retry-After or the reset time, else
    10 s; over 120 s exits); exits on anything else, printing SCB's error title."""
    url = API + path + ("?" + urlencode(params) if params else "")
    for attempt in range(2):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                body = r.read()
                stats["calls"] += 1
                stats["bytes"] += len(body)
                left = r.headers.get("X-Rate-Limit-Remaining") or ""
                stats["lowest remaining"] = min(stats.get("lowest remaining", 30), int(left) if left.isdigit() else 30)
                if left.isdigit() and int(left) <= 2:
                    stats["paused for the limit"] += 1
                    time.sleep(min(wait_for(r.headers, 10), 11))
                return json.loads(body)
        except urllib.error.HTTPError as e:
            if attempt == 0 and e.code in (403, 429, 500, 502, 503, 504):
                wait = wait_for(e.headers, 10)
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:150]}")
        except OSError as e:  # DNS, refused connection, timeout, reset
            if attempt == 0:
                time.sleep(10)
                continue
            sys.exit(f"{url}: {e}")

def metadata(table_id):
    """/metadata from disk while the table's `updated` stamp is unchanged. The API sends no ETag or
    Last-Modified, so the small /tables/{id} entry is the change check."""
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
    """English labels -> SCB's codes for one variable (codes are Swedish: Kon 'TotSa' or '1+2', Alder 'TotSA')."""
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

# 1. robots.txt. statistikdatabasen.scb.se/robots.txt is HTTP 404, so the API host has no rules (RFC 9309 2.3.1.3:
#    "unavailable" means the crawler may access any resources); www.scb.se has 'User-agent: *' and an empty Disallow.
for host, paths in (("https://statistikdatabasen.scb.se", ["/api/v2/tables", "/api/v2/tables/TAB6473/metadata",
                                                            "/api/v2/tables/TAB6473/data", "/api/v2/config"]),
                    ("https://www.scb.se", ["/en/services/open-data-api/", "/en/services/open-data-api/pxwebapi/"])):
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    try:
        with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
            print(f"{host}/robots.txt: HTTP {r.status} {r.headers.get('Content-Type')}: {[l.strip() for l in text.splitlines() if l.strip()]}")
            rp.parse(text.splitlines())
    except urllib.error.HTTPError as e:
        print(f"{host}/robots.txt: HTTP {e.code}: no robots file, so no rules")
        if not 400 <= e.code < 500 or e.code in (401, 403, 429):
            sys.exit("robots.txt unreachable, access denied or rate-limited: stop")
        rp.allow_all = True   # what RobotFileParser.read() does on a 4xx other than 401/403
    time.sleep(PAUSE)
    for p in paths:
        ok = all(rp.can_fetch(a, host + p) for a in AGENTS)
        print(f"  robots {p:<40} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
        if not ok:
            sys.exit("robots.txt now disallows a path this skill uses: stop")

now = datetime.now(UTC)
print(f"\nStatistics Sweden (SCB) Statistical Database via PxWebApi v2, checked {now:%Y-%m-%d %H:%M} UTC")

# 2. What did SCB publish lately? pastDays lists tables updated in the last N days (paged).
recent, page = [], 1
while True:
    res = get("/tables", pastDays=7, lang="en", pageSize=100, pageNumber=page)
    recent += res["tables"]
    if page >= res["page"]["totalPages"]:
        break
    page += 1
days = Counter(t["updated"][:10] for t in recent)
print(f"tables updated in the last 7 days: {len(recent)} ({res['page']['totalElements']} per the API) in {page} pages; "
      f"by day {dict(sorted(days.items()))}")

# 3. Population: newest month (key figures table TAB4481) and newest year end (TAB4365, 1749 on)
info, meta = metadata("TAB4481")
k, kc = codes(meta, "key figure", "Population")
ds = get("/tables/TAB4481/data", lang="en", outputFormat="json-stat2",
         **{f"valueCodes[{k}]": kc, "valueCodes[ContentsCode]": "*", "valueCodes[Tid]": "top(1)"})
v = {r["ContentsCode"][1]: r["value"] for r in tidy(ds)}
national = v["Number of persons"]
month = next(iter(ds["dimension"]["Tid"]["category"]["index"]))
print(f"\n{info['id']} {info['label']} (updated {info['updated'][:10]}): {month}: {v['Number of persons']:,} persons, "
      f"{v['Change from previous month, percent']:+.2f} % on the month, {v['Change from same period previous year, percent']:+.2f} % on the year")

info, meta = metadata("TAB4365")
c, cc = codes(meta, "observations", "Population", "Births", "Deaths", "Immigrations", "Emigrations")
ds = get("/tables/TAB4365/data", lang="en", outputFormat="json-stat2",
         **{"valueCodes[Kon]": "1+2", f"valueCodes[{c}]": cc, "valueCodes[Tid]": "top(5)"})
rows = tidy(ds)
years = sorted({r["Tid"][0] for r in rows})
print(f"{info['id']} {info['label']} (updated {info['updated'][:10]}), whole year, population on 31 December:")
print(f"  {'':<13}" + "".join(f"{y:>12}" for y in years))
for code in cc.split(","):
    vals = {r["Tid"][0]: r["value"] for r in rows if r[c][0] == code}
    name = next(r[c][1] for r in rows if r[c][0] == code)
    print(f"  {name:<13}" + "".join(f"{vals[y]:>12,}" for y in years))

# 4. The 21 counties and the 5 largest municipalities, newest month (TAB6473, code lists for the Region variable)
info, meta = metadata("TAB6473")
f, fc = codes(meta, "population changes", "population")
reg = {x["label"]: x["id"] for x in meta["dimension"]["Region"]["extension"]["codelists"]}
for cl, top in (("county", 3), ("municipalities", 5)):
    ds = get("/tables/TAB6473/data", lang="en", outputFormat="json-stat2",
             **{"codelist[Region]": reg[cl], "valueCodes[Region]": "*", f"valueCodes[{f}]": fc, "valueCodes[Kon]": "TotSa",
                "valueCodes[ContentsCode]": "*", "valueCodes[Tid]": "top(1)"})
    rows = [r for r in tidy(ds) if r["value"] is not None]
    print(f"\n{info['id']} {cl} (code list {reg[cl]}): {len(rows)} regions in {rows[0]['Tid'][0]}, "
          f"{sum(r['value'] for r in rows):,} persons in all (national figure {national:,}: SCB's added noise); largest {top}:")
    for r in sorted(rows, key=lambda r: -r["value"])[:top]:
        print(f"  {r['Region'][0]:<5} {r['Region'][1]:<22} {r['value']:>10,}")

# 5. Ask again: metadata comes from disk while the table's `updated` stamp is unchanged
n = stats["calls"]
metadata("TAB6473")
print(f"\nmetadata again: {stats['calls'] - n} API call (the /tables/TAB6473 change check), {stats['meta from disk']} served from disk so far")
print(f"totals: {stats['calls']} API calls, {stats['bytes']:,} bytes, lowest X-Rate-Limit-Remaining {stats['lowest remaining']}, "
      f"paused for the limit {stats['paused for the limit']} times, cache {CACHE_DIR}")
print(f"Source: Statistics Sweden, https://www.scb.se, tables TAB4481, TAB4365 and TAB6473 via {API}, CC0, "
      f"accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:29 UTC, empty cache; the same rows as the 00:04 UTC run apart from the clock and the lowest countdown (26 here, 25 then); a warm re-run at 00:05 UTC printed the same rows with "4 served from disk so far", 9 API calls and 123,832 bytes):

```text
https://statistikdatabasen.scb.se/robots.txt: HTTP 404: no robots file, so no rules
  robots /api/v2/tables                           allowed for all 11 agents
  robots /api/v2/tables/TAB6473/metadata          allowed for all 11 agents
  robots /api/v2/tables/TAB6473/data              allowed for all 11 agents
  robots /api/v2/config                           allowed for all 11 agents
https://www.scb.se/robots.txt: HTTP 200 text/plain: ['Sitemap: https://www.scb.se/sitemap.xml', 'User-agent: *', 'Disallow:']
  robots /en/services/open-data-api/              allowed for all 11 agents
  robots /en/services/open-data-api/pxwebapi/     allowed for all 11 agents

Statistics Sweden (SCB) Statistical Database via PxWebApi v2, checked 2026-11-24 00:29 UTC
tables updated in the last 7 days: 77 (77 per the API) in 1 pages; by day {'2026-11-17': 4, '2026-11-18': 6, '2026-11-19': 1, '2026-11-20': 49, '2026-11-23': 17}

TAB4481 Key figures, populations statistics 2016M09-2026M09 (updated 2026-11-11): 2026M09: 10,621,725 persons, +0.01 % on the month, +0.12 % on the year
TAB4365 Population and population changes in Sweden by sex. Year 1749-2025 (updated 2026-02-24), whole year, population on 31 December:
                       2021        2022        2023        2024        2025
  Population     10,452,326  10,521,556  10,551,707  10,587,710  10,605,529
  Births            114,263     104,734     100,051      98,451      97,491
  Deaths             91,958      94,737      94,385      91,268      92,212
  Immigrations       90,631     102,436      94,514     116,197      89,434
  Emigrations        48,284      50,592      73,434      86,449      77,483

TAB6473 county (code list vs_CKM02Län): 21 regions in 2026M09, 10,621,721 persons in all (national figure 10,621,725: SCB's added noise); largest 3:
  01    Stockholm county        2,498,302
  14    Västra Götaland county  1,781,454
  12    Skåne county            1,435,906

TAB6473 municipalities (code list vs_CKM03Kommun): 290 regions in 2026M09, 10,621,746 persons in all (national figure 10,621,725: SCB's added noise); largest 5:
  0180  Stockholm               1,003,052
  1480  Göteborg                  616,446
  1280  Malmö                     368,994
  0380  Uppsala                   251,025
  0580  Linköping                 169,588

metadata again: 1 API call (the /tables/TAB6473 change check), 1 served from disk so far
totals: 12 API calls, 162,121 bytes, lowest X-Rate-Limit-Remaining 26, paused for the limit 0 times, cache ~/.cache/scb-skill
Source: Statistics Sweden, https://www.scb.se, tables TAB4481, TAB4365 and TAB6473 via https://statistikdatabasen.scb.se/api/v2, CC0, accessed 24 November 2026 00:29 UTC.
```

### 4. curl: limits, search, variables, the newest two months, the closed 1968-2024 table, CSV, headers, mistakes

```bash
B=https://statistikdatabasen.scb.se/api/v2
# -g: keep [ ] in the URL literal (curl would read them as a range); --retry 1 retries once on a timeout or HTTP 408, 429, 500, 502, 503 or 504, 10 s later
C="curl -sSg --max-time 60 --retry 1 --retry-delay 10"
# 1. the server's own limits, licence and credit line
$C --fail "$B/config" | python3 -c 'import json, sys
c = json.load(sys.stdin); print({k: c[k] for k in ("apiVersion", "maxDataCells", "maxCallsPerTimeWindow", "timeWindow", "license")}, c["sourceReferences"][0]["text"])'
sleep 1
# 2. search: id, last period, variables (hits are not sorted by period: compare lastPeriod)
$C --fail "$B/tables?query=population%20statistics%20region%20sex%20month&lang=en&pageSize=5" | python3 -c 'import json, sys
for t in json.load(sys.stdin)["tables"]:
    print(t["id"], t["lastPeriod"], t["updated"][:10], t["variableNames"])'
sleep 1
# 3. read the variables first: codes stay Swedish with lang=en (Region, Forandringar, Kon, ContentsCode, Tid)
$C --fail "$B/tables/TAB6473/metadata?lang=en" | python3 -c 'import json, sys
m = json.load(sys.stdin)
for d in m["id"]:
    x = m["dimension"][d]; c = x["category"]["label"]
    print(d, "=", repr(x["label"]), "| optional" if x["extension"].get("elimination") else "| required", "|", dict(list(c.items())[:3]), "+%d more" % (len(c) - 3) if len(c) > 3 else "")'
sleep 1
# 4. Sweden's population, the two newest months (the documented example: Region=00, Tid=top(2), ContentsCode=*)
$C --fail "$B/tables/TAB6473/data?lang=en&outputFormat=json-stat2&valueCodes[Region]=00&valueCodes[Forandringar]=100&valueCodes[Kon]=TotSa&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(2)" \
  | python3 -c 'import json, sys
d = json.load(sys.stdin); print(d["label"], "|", list(d["dimension"]["Tid"]["category"]["index"]), d["value"], "| updated", d["updated"])'
sleep 1
# 5. the same request on TAB638 (1968-2024) still answers, but its newest year is 2024 (BE0101N1 = population)
T=$(mktemp)
S=$($C --fail -o "$T" -w '%{time_total}' "$B/tables/TAB638/data?lang=en&outputFormat=json-stat2&valueCodes[Region]=00&valueCodes[Tid]=top(2)&valueCodes[ContentsCode]=BE0101N1")
python3 -c 'import json, sys
d = json.load(open(sys.argv[1])); print(d["label"], "|", list(d["dimension"]["Tid"]["category"]["index"]), d["value"], "|", sys.argv[2], "s")' "$T" "$S"
sleep 1
# 6. CSV (Latin-1, periods become columns)
$C --fail "$B/tables/TAB6473/data?lang=en&outputFormat=csv&valueCodes[Region]=00&valueCodes[Forandringar]=100&valueCodes[Kon]=TotSa&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(3)" | iconv -f latin1 -t utf-8
echo
sleep 1
# 7. headers: a real countdown (X-Rate-Limit-Remaining) and the window end (X-Rate-Limit-Reset); no ETag/Last-Modified
$C -D - -o /dev/null "$B/tables/TAB6473?lang=en" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|etag|last-modified|x-rate-limit-[a-z]+|retry-after):)'
sleep 1
# 8. mistakes are JSON with a title; non-ASCII codes need percent-encoding and + must be %2B
for u in "tables/638/metadata?lang=en" \
         "tables/TAB4365/data?lang=en&valueCodes[ContentsCode]=000000LV&valueCodes[Tid]=top(1)&valueCodes[Kon]=1+2" \
         "tables/TAB4365/data?lang=en&valueCodes[ContentsCode]=000000LV&valueCodes[Tid]=top(1)&valueCodes[Kon]=1%2B2" \
         "tables/TAB6387/data?lang=en&valueCodes[Arbetskraftstillh]=ALÖSP&valueCodes[TypData]=SR_DATA&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(1)" \
         "tables/TAB6387/data?lang=en&valueCodes[Arbetskraftstillh]=AL%C3%96SP&valueCodes[TypData]=SR_DATA&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(1)"; do
  $C -o "$T" -w "%{http_code} " "$B/$u"; echo "$(head -c 90 "$T")  <- $u"; sleep 1
done
rm -f "$T"
# 9. robots: none on the API host, allow-all on www.scb.se
$C -o /dev/null -w 'statistikdatabasen.scb.se/robots.txt: HTTP %{http_code}\n' https://statistikdatabasen.scb.se/robots.txt; sleep 1
$C https://www.scb.se/robots.txt
echo
echo "Source: Statistics Sweden, https://www.scb.se, Statistical Database via $B, CC0, accessed $(date -u '+%d %B %Y %H:%M') UTC."
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:30 UTC; TAB638 now asks only for BE0101N1, population, so its line has two values instead of four; the rest matches the 00:05 and 00:06 UTC runs apart from timings and the clock):

```text
{'apiVersion': '2.3.2', 'maxDataCells': 150000, 'maxCallsPerTimeWindow': 30, 'timeWindow': 10, 'license': 'https://creativecommons.org/share-your-work/public-domain/cc0/'} Source: Statistics Sweden
TAB6473 2026M09 2026-11-11 ['region', 'population changes', 'sex', 'observations', 'month']
TAB1625 2024M12 2025-02-21 ['region', 'population changes', 'sex', 'observations', 'month']
Region = 'region' | optional | {'00': 'Sweden', '01': 'Stockholm county', '0114': 'Upplands Väsby'} +309 more
Forandringar = 'population changes' | required | {'100': 'population', '110': 'population increase/decline', '115': 'births'} +18 more
Kon = 'sex' | optional | {'TotSa': 'total, all men and women', '1': 'men', '2': 'women'}
ContentsCode = 'observations' | required | {'000007SR': 'Population'}
Tid = 'month' | required | {'2025M01': '2025M01', '2025M02': '2025M02', '2025M03': '2025M03'} +18 more
Population by region, population changes, sex and month | ['2026M08', '2026M09'] [10621103, 10621725] | updated 2026-11-11T07:00:00Z
Population by region and year | ['2023', '2024'] [10551707, 10587710] | 1.207294 s
"Region","Forandringar","Kon","000007SR 2026M07","000007SR 2026M08","000007SR 2026M09"
"00","100","TotSa",10613531,10621103,10621725

HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
X-Rate-Limit-Limit: 10s
X-Rate-Limit-Remaining: 28
X-Rate-Limit-Reset: 2026-11-24T00:30:01.7860476Z
404 {"type":"Parameter error","title":"Non-existent table","status":404}  <- tables/638/metadata?lang=en
400 {"type":"Parameter error","title":"Non-existent value","status":400}  <- tables/TAB4365/data?lang=en&valueCodes[ContentsCode]=000000LV&valueCodes[Tid]=top(1)&valueCodes[Kon]=1+2
200 {"version":"2.0","class":"dataset","label":"Population by sex and year","source":"Statisti  <- tables/TAB4365/data?lang=en&valueCodes[ContentsCode]=000000LV&valueCodes[Tid]=top(1)&valueCodes[Kon]=1%2B2
400 {"type":"Parameter error","title":"Non-existent value","status":400}  <- tables/TAB6387/data?lang=en&valueCodes[Arbetskraftstillh]=ALÖSP&valueCodes[TypData]=SR_DATA&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(1)
200 {"version":"2.0","class":"dataset","label":"Population aged 15-74 by labour status, type o  <- tables/TAB6387/data?lang=en&valueCodes[Arbetskraftstillh]=AL%C3%96SP&valueCodes[TypData]=SR_DATA&valueCodes[ContentsCode]=*&valueCodes[Tid]=top(1)
statistikdatabasen.scb.se/robots.txt: HTTP 404
Sitemap: https://www.scb.se/sitemap.xml
User-agent: *
Disallow:
Source: Statistics Sweden, https://www.scb.se, Statistical Database via https://statistikdatabasen.scb.se/api/v2, CC0, accessed 24 November 2026 00:30 UTC.
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `/tables` `tables[]` | `{id, label, description, sortCode, updated, firstPeriod, lastPeriod, category, variableNames, source, subjectCode, timeUnit, paths, links}` | `id` is `TAB` plus digits (`"TAB6473"`); `label` ends with the period range; `variableNames` are the English labels (`"region"`, `"sex"`, `"observations"`, `"month"`); `discontinued: true` marks closed tables that only come back with `includeDiscontinued=true` (319 hits for `population`, 358 with it, 39 of them flagged) |
| `/tables` `page` | `{pageNumber, pageSize, totalElements, totalPages, links}` | `pageSize=1000` returned all 17 tables of `pastDays=3` in one page on 2026-11-23; `pastDays=7` listed 77 tables on 2026-11-24 |
| `/tables/{id}` | the same entry for one table | the cheap change check (`updated`) |
| `/config` | `{apiVersion, maxDataCells, maxCallsPerTimeWindow, timeWindow, license, sourceReferences, defaultLanguage, dataFormats, features}` | `2.3.2`, 150000, 30, 10, CC0, "Source: Statistics Sweden", `sv`, `json-stat2, csv, px, xlsx, html, json-px` |
| `/metadata` `id`, `size`, `role`, `note` | variable codes in order, number of values each, `role.time` / `role.metric`, notes | TAB638 sizes `[312, 4, 102, 2, 2, 57]`; the notes carry the 2025 random-uncertainty warning |
| `dimension[V].label` | English variable label | what `variableNames` in the search lists |
| `dimension[V].category.label` | `{code: English label}` | `Kon`: `{"TotSa": "total, all men and women", "1": "men", "2": "women"}` in TAB6473; `{"1": "men", "2": "women", "1+2": "total"}` in TAB4365 |
| `dimension[V].extension.elimination` | `true` / `false` | `true`: you may leave the variable out and get its total; `false`: you must select it (HTTP 400 otherwise). TAB5557 makes `Civilstand` and `Alder` mandatory, TAB638 does not |
| `dimension[V].extension.codelists` | `[{id, label, type}]` | TAB6473 Region: `vs_CKM01Riket` Sweden, `vs_CKM02Län` county (21), `vs_CKM03Kommun` municipalities (290); TAB638 Alder: `agg_Ålder5år` 5-year intervals |
| `dimension.ContentsCode.category.unit` | `{code: {base, decimals}}` | `{"base": "number of persons", "decimals": 0}`; the CPI's "Annual changes" says `"base": "index"` and TAB6387 says `"thousands/percent"`, so read the value label too |
| `dimension.ContentsCode.extension.refperiod` | e.g. `"31 December each year"` (TAB638), `"Month"` (TAB6473) | population is a stock at the end of the period |
| `/data` `value` | flat list, one number per cell | in the order of `id`, last variable fastest; within a variable, the order of `category.index` |
| `/data` `status` | `{flat index: symbol}` | the value is `null` there; no such cell came up in these runs |
| `/data` `updated`, `label`, `source` | update time (UTC), a label built from the selected variables, `"Statistics Sweden"` | `label` differs from the search label (`"Population by region and year"` for TAB638) |
| response headers | `content-type: application/json; charset=utf-8`, `X-Rate-Limit-Limit: 10s`, `X-Rate-Limit-Remaining`, `X-Rate-Limit-Reset` (UTC, 7 decimals) | no `cache-control`, `etag`, `last-modified` or cookie; `Access-Control-Allow-Origin: *` when the request has an `Origin`; CSV is `text/csv; charset=iso-8859-1` |

## Gotchas

- **Closed tables are not flagged.** TAB638 (population 1968-2024) has no `discontinued` flag and answers normally, but its newest year is 2024; 2025 sits in TAB5557 ("Year 2025") and TAB4365 (1749-2025). The same happens for months (TAB1625 to 2024M12, TAB6473 from 2025M01) and the CPI (the 1980=100 monthly tables say "no update after 2025M12"; TAB6596 is 2020=100). Compare `lastPeriod` across matching hits, as block 1 does.
- **Parts do not add up from 2025 on.** SCB's note: "a small controlled random uncertainty is introduced in all reported data ... the reported totals are not always equal to the sum of their reported components". Use the published total cell (`TotSa`, `1+2`, `00`, `TotSA`), not a sum.
- **Codes are Swedish, labels are English.** `valueCodes[Region]=Sweden` is HTTP 400 "Non-existent value"; the code is `00`. Variable codes and table ids are case-insensitive (`region`, `tab638` worked); `638` without `TAB` is HTTP 404 "Non-existent table".
- **Encode codes.** `+` in a raw URL becomes a space (`Kon=1+2` is HTTP 400; `1%2B2` works) and `ALÖSP` must be `AL%C3%96SP` in curl (raw it is HTTP 400; a browser `fetch()` encodes it for you). `urlencode` in blocks 1 and 3 handles both.
- **Required variables differ by table.** Leave out a variable whose `elimination` is `false` and you get HTTP 400 "Missing selection for mandantory variable" (SCB's spelling). TAB5557 needs `Civilstand=SC` and `Alder=TotSA` for the whole population; TAB638 lets you drop them.
- **Search words: no "of", and loose matches.** `type of data` and `population of` returned 0 tables (`of` alone matched 8, `type` 851, `data` 349), so drop small words. Results are not ordered by period, and `population` returns 319 tables (water supply, projections to 2120). Filter by `variableNames` and the label, or pass a known table id.
- **Projections look like data.** `population` also finds TAB4161 and others with `lastPeriod` 2120; the newest-period rule would pick them if their variables matched, so keep `vars` and `label_has` specific.
- **Two rate-limit texts.** The general open-data page still says "ten call-ups in a 10-second period", "100,000 values per table" and "HTTP 403 Forbidden"; the PxWebApi v2 page, `/config` and the headers say 30 calls per 10 s and 150,000 cells. Blocks 1 and 3 follow v2, watch the countdown and treat both 403 and 429 as "wait".
- **Too many cells.** All 312 regions x 4 marital statuses x 102 ages x 2 sexes x 2 contents x 3 years of TAB638 is HTTP 400 "Too many cells selected". Narrow with `top(n)`, a code list or fewer values.
- **Units are loose.** The CPI "Annual changes" row says `base: index` and the LFS table says `thousands/percent` for every row; the value label ("unemployment rate, percent", "unemployed, thousands") tells you which.
- **CSV is Latin-1 and wide.** `outputFormat=csv` puts periods in columns (`"000007SR 2026M09"`) and is `iso-8859-1`; decode it, or use json-stat2 and `tidy()`.
- **Language.** `lang=en` and `lang=sv` only (`lang=fi` is HTTP 400 "Unsupported language"); the default is Swedish, so always send `lang=en` for English labels.
- **curl and brackets.** `valueCodes[Tid]` needs `curl -g` (or `%5B`/`%5D`).
- **Credit and no logo.** CC0 needs no credit, but print "Source: Statistics Sweden" with the table ID, period and access date, name another agency when the table cites one, drop the credit if you changed the figures, use no SCB logo, and never present your service as an "official cooperation" or "partnership" with Statistics Sweden.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **Value labels as codes, ids without `TAB`, leaving out a mandatory variable, a raw `+` or unencoded `Ö` in curl, `lang` other than `en`/`sv`**: all HTTP 400 or 404 (blocks 2 and 4).
- **A whole large table in one call**: HTTP 400 "Too many cells selected" above 150,000 cells.
- **Conditional GETs and gzip**: no `ETag`, `Last-Modified` or `Content-Encoding`; compare `updated` from `/tables/{id}` instead.
- **Not tested:** a 403 or 429 (never provoked), a suppressed (`null`) cell, `outputFormat` values other than json-stat2 and csv, `codelist` aggregations on age, POST selections, saved queries, PxWebApi v1 beyond one call (`https://api.scb.se/OV0104/v1/doris/en/ssd/BE/BE0101/BE0101A/BefolkningNy` returned HTTP 200, 8,859 bytes, on 2026-11-23), and `lang=sv` beyond one search.
