# FDIC BankFind Suite API (api.fdic.gov) - Check Whether a Bank Is Open and FDIC-Insured, Get Its CERT Number, Assets and Branches, or List Recent Bank Failures (REST API, no key)

Field-tested against api.fdic.gov on 2026-11-18 (US Pacific afternoon; 23:27-23:35 UTC) using a fresh Browser Use cloud browser (logged out; one session) plus Python `urllib` and `curl` from a Linux machine. 13 browser page loads (the BankFind "Find Insured Banks" page 3 times, the three robots.txt files twice each, the API documentation and the FDIC website policies twice each) and 29 in-page `fetch()` calls, 14 urllib calls and 49 curl calls (plus an independent re-run of every block at 23:36-23:41 UTC; block 4 then gained 3 curl probes) to api.fdic.gov, banks.data.fdic.gov and www.fdic.gov, all serial (at least 1 s apart in the blocks below): every API call was HTTP 200 except the deliberate HTTP 400 probes below, and robots.txt is HTTP 404 on both API hosts. Each call took about 0.16-0.32 s. No 429, no challenge, no key, no login. After code review on 2026-11-19, blocks 1 and 3 were re-run at 00:16-00:17 UTC (block 1 in a new cloud browser) so that failure lists and counts keep only `RESTYPE` FAILURE rows and block 1 pages past 100 failures; they show the re-run output.

robots.txt (checked 2026-11-18, curl, urllib and the cloud browser): https://api.fdic.gov/robots.txt answers HTTP 404 (JSON `NOT_FOUND`), and https://banks.data.fdic.gov/robots.txt redirects to https://api.fdic.gov/banks/robots.txt, also HTTP 404. A 4xx robots.txt means no rules apply (RFC 9309, 2.3.1.3: the crawler "MAY access any resources on the server"), so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider may all fetch `/banks/institutions`, `/banks/locations`, `/banks/failures` and the BankFind pages. https://www.fdic.gov/robots.txt (where the website policies live) has one `User-agent: *` group with `Crawl-delay: 1` and Drupal's default `Disallow` list (`/core/`, `/admin/`, `/search/`, `/fdic-search/`, `/user/login` and similar), and no named AI-agent groups; `/about/website-policies` is allowed for all 11 agents (block 3). The blocks wait 1 s between requests. Terms: the BankFind Suite API documentation (https://api.fdic.gov/banks/docs/, read in the cloud browser by block 2) says "Users are currently not required to register and obtain a unique “key” to use with every query submitted to our API" and links an optional key ("Obtain your API key here", via api.data.gov; the OpenAPI spec already lists an optional `api_key` parameter, so a key may become required later). The FDIC Website Policies (https://www.fdic.gov/about/website-policies, "Last Updated: May 12, 2026") say "Access to or use of the FDIC website constitutes consent to the following terms", that the FDIC "makes no express or implied warranty regarding such information or data", that the content "is not designed or intended to provide authoritative financial, accounting, investment, or other professional advice", that a reference to a commercial product "does not constitute an endorsement, a recommendation, or a favoring by the FDIC", and that attempts to "upload or change information, or otherwise cause damage" are "strictly prohibited". No AI/ML, scraping, automated-access or non-commercial clause on either page, and no published rate limit. Naming: "FDIC BankFind Suite" as plain text; no FDIC logo or official sign, no implied endorsement, and no statement about deposit insurance beyond what the API returns. This skill is not affiliated with or endorsed by the FDIC.

**Insured means `ACTIVE` = 1.** The field definition (https://api.fdic.gov/banks/docs/institution_properties.yaml) says `ACTIVE` is "1='Institutions that are currently open and insured by the FDIC'; 0='Institution closed or not insured by FDIC'". Report that field and its definition, with the data date; do not turn it into advice about a person's deposits or coverage.

## Quick summary

- **No scraping.** `GET https://api.fdic.gov/banks/institutions?filters=NAME:"Silicon Valley Bank"&fields=NAME,CERT,ACTIVE,ASSET,DEP,OFFICES,REPDTE` (URL-encode the quotes and spaces) returns `{"meta": {"total": ...}, "data": [{"data": {...}}], "totals": {...}}`. Same shape for `/locations` (branches), `/failures`, `/financials`, `/history`, `/sod` and `/summary`. JSON, or CSV with `format=csv`. No key.
- **Answers (block 1, 23:31 UTC; block 4 at 23:34 agrees):** **Silicon Valley Bank is CERT 24735, `ACTIVE` 0**, closed 03/10/2023; its failure record has assets of $209.03 billion and an estimated loss to the fund of $18.74 billion. **JPMorgan Chase Bank, National Association is CERT 628, `ACTIVE` 1**, assets $4.09 trillion (report date 06/30/2026), **5,416 offices** (the `/locations` count matches `OFFICES`). **Newest failure: Small Business Bank, Lenexa, KS, 7/17/2026** (CERT 25744); 4,117 failure and assistance rows since 1934, 6 since 2025-01-01.
- **Exact name or fuzzy search.** `filters=NAME:"..."` is an exact phrase (case-insensitive for `NAME`; code values such as `STALP` must be upper case, see Gotchas); the legal name is often longer ("JPMorgan Chase Bank" matches 0, the bank is "JPMorgan Chase Bank, National Association"). `search=NAME:JPMorgan Chase` is the fuzzy match (it also finds `Silicn Valey`). Block 1 tries exact first, then fuzzy, and prints the other candidates.
- **Silent zeros and silent noise:** a lowercase field name (`name:"..."`, `cert:628`), an unknown one (`BANKNAME:`) or a lowercase code value (`STALP:vt`) returns HTTP 200 with 0 rows; lowercase names in `fields=` return rows with only `ID`; an unquoted multi-word name (`NAME:Silicon Valley Bank`) returns 17 unrelated banks such as "Valley Bank". The loud errors seen were HTTP 400 for `limit` over 10,000 (block 2) and for a filter with an unclosed quote (block 4).
- **Money is in thousands of dollars** (the docs: "domestic deposits under 10,000 ($thousands)"; the failures spec: "Thousands of US Dollars"). **Dates are strings in four formats**: institutions `03/10/2023`, failures `7/17/2026` (no zero padding), financials `20260630`, history `2021-07-01T00:00:00`; filters take `yyyy-mm-dd`.
- **Rate limit:** none published. Keyless responses carry `x-ratelimit-limit: 20` and `x-ratelimit-remaining: 19` (still 19 on 3 back-to-back calls; the window is not documented). The blocks send 1 request per second (www.fdic.gov's `Crawl-delay: 1`) and retry once on 429 after `Retry-After` (60 s if absent; they stop if it asks for more than 120 s).

## What works

### 1. Is this bank open and insured? CERT, assets, branches, failure record, and recent failures (browser)

`on_bankfind_tab()` opens the logged-out "Find Insured Banks" page once, so `fetch()` runs from banks.data.fdic.gov (the API sends `Access-Control-Allow-Origin: *`). `get()` returns parsed JSON on HTTP 200, waits 1 s between calls, retries once after `Retry-After` when sent (else 60 s on 429, 10 s on 5xx or a network error; over 120 s it stops) and otherwise raises. `find()` tries the exact name, then the fuzzy `search`. An open bank gets its branch list by state; a closed one gets its `/failures` row. 7 `fetch()` calls.

```python
import json, time, urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

BANKS = ["Silicon Valley Bank", "JPMorgan Chase Bank"]  # names as a person types them
SINCE = "2025-01-01"  # list every failure on or after this date (yyyy-mm-dd, the filter's date format)

SITE = "https://banks.data.fdic.gov"
PAGE = SITE + "/bankfind-suite/bankfind"   # the logged-out "Find Insured Banks" page
API = "https://api.fdic.gov/banks"         # sends Access-Control-Allow-Origin: *
INST = "NAME,CERT,ACTIVE,ASSET,DEP,OFFICES,REPDTE,CITY,STALP,INSDATE,ENDEFYMD,REGAGNT,WEBADDR"
PAUSE = 1  # no published keyless limit; www.fdic.gov asks 'Crawl-delay: 1', so stay at 1 request per second

def on_bankfind_tab():
    """Open the logged-out BankFind page once; fetch() then runs from banks.data.fdic.gov. Reuse the tab if it is there."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(PAGE)
    wait_for_load()
    if js("location.origin") != SITE:
        raise RuntimeError(f"banks.data.fdic.gov did not load (at {js('location.href')}): stop")

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

def get(path, params, timeout=60):
    """One API call as parsed JSON ({meta, data, totals}). Waits PAUSE before every call after the first. Retries once,
    after Retry-After when sent (else 60 s on 429, 10 s on 5xx or a network error); raises otherwise."""
    url = f"{API}/{path}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    for attempt in range(2):
        if get.calls:
            time.sleep(PAUSE)
        get.calls += 1
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"no answer after {timeout}s: {url}")
            time.sleep(0.2)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(retry_after(r.get("ra"), 60 if r["status"] == 429 else 10))
            continue
        if r["status"] != 200 or "json" not in (r["type"] or ""):
            raise RuntimeError(f"HTTP {r['status']} {r['type']} {r['text'][:300]!r} for {url}")
        d = json.loads(r["text"])
        if not isinstance(d.get("data"), list) or "total" not in d.get("meta", {}):
            raise RuntimeError(f"unexpected body for {url}: {r['text'][:300]!r}")
        return d
get.calls = 0

def rows(d):
    return [x["data"] for x in d["data"]]

def usd(thousands):
    """The API gives money in thousands of dollars."""
    if not isinstance(thousands, (int, float)):
        return "n/a"
    v = thousands * 1000
    for div, unit in ((1e12, "trillion"), (1e9, "billion"), (1e6, "million")):
        if abs(v) >= div:
            return f"${v / div:,.2f} {unit}"
    return f"${v:,.0f}"

def day(s):
    """'03/10/2023' (institutions) and '7/17/2026' (failures) -> date. Never compare these strings as text."""
    return datetime.strptime(s, "%m/%d/%Y").date()

def find(name):
    """Exact name first (quoted phrase, case-insensitive); else the fuzzy 'search' parameter. -> (rows, how)"""
    q = name.replace("\\", "\\\\").replace('"', '\\"')
    d = get("institutions", {"filters": f'NAME:"{q}"', "fields": INST, "sort_by": "ACTIVE", "sort_order": "DESC", "limit": 10})
    if d["meta"]["total"]:
        return rows(d), "exact name"
    d = get("institutions", {"search": f"NAME:{name}", "fields": INST, "limit": 5})
    return rows(d), "fuzzy search"

on_bankfind_tab()
for name in BANKS:
    found, how = find(name)
    if not found:
        raise RuntimeError(f"no institution matches {name!r}: try a shorter name or the CERT number")
    b = {k: "n/a" for k in INST.split(",")} | found[0]  # a field with no value is left out of the row entirely
    others = ", ".join(f"{x['NAME']} (CERT {x['CERT']}, ACTIVE {x['ACTIVE']})" for x in found[1:4])
    print(f"{name!r} -> {how}, {len(found)} match(es); using {b['NAME']}, {b['CITY']}, {b['STALP']}"
          + (f"; also: {others}" if others else ""))
    print(f"  CERT {b['CERT']}  ACTIVE {b['ACTIVE']}  insured since {b['INSDATE']}  regulator {b['REGAGNT']}  "
          f"assets {usd(b['ASSET'])}  deposits {usd(b['DEP'])}  offices {b['OFFICES']}  (report date {b['REPDTE']})")
    if b["ACTIVE"] == 1:
        print("  status: ACTIVE 1 = 'Institutions that are currently open and insured by the FDIC' (field definition)")
        d = get("locations", {"filters": f"CERT:{b['CERT']}", "fields": "STALP,CITY,OFFNAME,MAINOFF", "limit": 10000})
        locs = rows(d)
        if len(locs) != d["meta"]["total"]:
            raise RuntimeError(f"got {len(locs)} locations, meta.total {d['meta']['total']}: page with offset")
        by_state = {}
        for x in locs:
            by_state[x["STALP"]] = by_state.get(x["STALP"], 0) + 1
        main = [x for x in locs if x["MAINOFF"] == 1]
        top = ", ".join(f"{k} {v}" for k, v in sorted(by_state.items(), key=lambda kv: -kv[1])[:6])
        print(f"  locations: {len(locs)} (OFFICES says {b['OFFICES']}) in {len(by_state)} states/territories; top: {top}")
        if main:
            print(f"  main office: {main[0]['OFFNAME']}, {main[0]['CITY']}, {main[0]['STALP']}")
    else:
        print(f"  status: ACTIVE 0 = 'Institution closed or not insured by FDIC'; closed {b['ENDEFYMD']}")
        f = rows(get("failures", {"filters": f"CERT:{b['CERT']}", "fields": "NAME,FAILDATE,RESTYPE,RESTYPE1,QBFASSET,COST"}))
        if f:
            x = f[0]
            what = "failed" if x["RESTYPE"] == "FAILURE" else "got FDIC assistance (not a failure) on"
            print(f"  failure record: {x['NAME']} {what} {x['FAILDATE']}, {x['RESTYPE']} {x['RESTYPE1']}, assets "
                  f"{usd(x['QBFASSET'])}, estimated loss to the fund {usd(x['COST'])}")
        else:
            print("  no failure record: it closed some other way (merger, voluntary closing); see the /history endpoint")
    print()

# RESTYPE:FAILURE leaves out the ASSISTANCE rows the same endpoint returns; page with offset until meta.total
recent, total = [], None
while total is None or len(recent) < total:
    d = get("failures", {"filters": f"FAILDATE:[{SINCE} TO *] AND RESTYPE:FAILURE", "sort_by": "FAILDATE", "sort_order": "DESC",
                         "fields": "NAME,CERT,CITYST,FAILDATE,QBFASSET,QBFDEP,COST,RESTYPE1", "limit": 100, "offset": len(recent)})
    total = d["meta"]["total"]
    if not d["data"]:
        raise RuntimeError(f"got {len(recent)} failures, meta.total {total}")
    recent += rows(d)
alltime = get("failures", {"filters": "RESTYPE:FAILURE", "fields": "CERT", "limit": 1})["meta"]["total"]
print(f"bank failures since {SINCE}: {len(recent)} (of {alltime} since 1934, RESTYPE FAILURE only), newest first")
for x in recent:
    print(f"  {day(x['FAILDATE'])}  {x['NAME']:<40} {x['CITYST']:<14} CERT {x['CERT']:<6} assets {usd(x['QBFASSET']):<16} "
          f"est. loss {usd(x['COST'])}")
print(f"\n{get.calls} API calls. Source: FDIC BankFind Suite API ({API}), retrieved "
      f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Data is as the FDIC reports it; this skill is not affiliated "
      f"with or endorsed by the FDIC.")
```

Output (from the re-run on 2026-11-19, 00:17 UTC):

```text
'Silicon Valley Bank' -> exact name, 1 match(es); using Silicon Valley Bank, Santa Clara, CA
  CERT 24735  ACTIVE 0  insured since 10/17/1983  regulator FED  assets $209.03 billion  deposits $175.38 billion  offices n/a  (report date 12/31/2022)
  status: ACTIVE 0 = 'Institution closed or not insured by FDIC'; closed 03/10/2023
  failure record: SILICON VALLEY BANK failed 3/10/2023, FAILURE PA, assets $209.03 billion, estimated loss to the fund $18.74 billion

'JPMorgan Chase Bank' -> fuzzy search, 2 match(es); using JPMorgan Chase Bank, National Association, Columbus, OH; also: JPMorgan Chase Bank, Dearborn (CERT 21761, ACTIVE 1)
  CERT 628  ACTIVE 1  insured since 01/01/1934  regulator OCC  assets $4.09 trillion  deposits $2.82 trillion  offices 5416  (report date 06/30/2026)
  status: ACTIVE 1 = 'Institutions that are currently open and insured by the FDIC' (field definition)
  locations: 5416 (OFFICES says 5416) in 50 states/territories; top: CA 855, NY 580, TX 489, FL 439, IL 264, OH 235
  main office: JPMorgan Chase Bank, National Association, Columbus, OH

bank failures since 2025-01-01: 6 (of 3524 since 1934, RESTYPE FAILURE only), newest first
  2026-07-17  SMALL BUSINESS BANK                      LENEXA, KS     CERT 25744  assets $72.95 million   est. loss $5.67 million
  2026-07-10  KENTLAND FS&LA                           KENTLAND, IN   CERT 28722  assets $3.81 million    est. loss $1.19 million
  2026-05-01  COMMUNITY BANK AND TRUST - WEST GEORGIA  LAGRANGE, GA   CERT 25796  assets $305.72 million  est. loss $97.28 million
  2026-01-30  METROPOLITAN CAPITAL B&T                 CHICAGO, IL    CERT 57488  assets $261.19 million  est. loss $19.65 million
  2025-06-27  SANTA ANNA NATIONAL BANK                 SANTA ANNA, TX CERT 5520   assets $76.94 million   est. loss $9.76 million
  2025-01-17  PULASKI SAVINGS BANK                     CHICAGO, IL    CERT 28611  assets $49.47 million   est. loss $31.85 million

7 API calls. Source: FDIC BankFind Suite API (https://api.fdic.gov/banks), retrieved 2026-11-19 00:17 UTC. Data is as the FDIC reports it; this skill is not affiliated with or endorsed by the FDIC.
```

### 2. robots.txt, the API doc, the website policies, and the API's answers to mistakes (browser)

6 page loads and 10 in-page `fetch()` calls in the same tab, 1 s apart.

```python
import json, re, time, urllib.parse

API = "https://api.fdic.gov/banks"
PAGE = "https://banks.data.fdic.gov/bankfind-suite/bankfind"
PAUSE = 1  # www.fdic.gov robots.txt: 'Crawl-delay: 1'

START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const t = await r.text(); let n = null, tot = null;
       try { const j = JSON.parse(t); n = (j.data || []).length; tot = (j.meta || {}).total; } catch (e) {}
       window.__o[id] = {status: r.status, type: r.headers.get('content-type'), rl: r.headers.get('x-ratelimit-limit'),
         rows: n, total: tot, text: t.slice(0, 600)}; })
    .catch(e => { window.__o[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def api(path, params):
    """One in-page API request -> raw answer. No retries: this block only inspects answers."""
    url = f"{API}/{path}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"no answer after 60s: {url}")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    time.sleep(2)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    time.sleep(PAUSE)
    return st, js("location.href"), js("document.body ? document.body.innerText : ''")

# 1. robots.txt on the three hosts, as a browser sees it
for host in ("https://api.fdic.gov", "https://banks.data.fdic.gov", "https://www.fdic.gov"):
    st, final, txt = page(host + "/robots.txt")
    agents = re.findall(r"(?im)^user-agent:\s*(\S+)", txt)
    print(f"{host}/robots.txt -> HTTP {st} at {final}; {len(txt)} chars; User-agent lines {agents}; "
          f"Crawl-delay {re.findall(r'(?im)^crawl-delay:\s*(\S+)', txt)}; first line {txt.strip().splitlines()[0][:70]!r}")

# 2. the API documentation and the FDIC website policies: the clauses this skill relies on
for url, needles in (
        ("https://api.fdic.gov/banks/docs/",
         ["Users are currently not required to register and obtain a unique", "Obtain your API key here",
          "Elastic Search", "To match a phrase, use double quotes", 'Dates must be entered in "yyyy-mm-dd" format',
          "($thousands)", "The format is controlled by"]),
        ("https://www.fdic.gov/about/website-policies",
         ["Access to or use of the FDIC website constitutes consent to the following terms",
          "makes no express or implied warranty", "not designed or intended to provide authoritative financial",
          "does not constitute an endorsement, a recommendation, or a favoring by the FDIC",
          "otherwise cause damage. Such attempts are strictly prohibited"])):
    st, final, txt = page(url)
    low = txt.lower()
    words = [w for w in ("artificial intelligence", "machine learning", " ai ", "scrap", "crawl", "robot", "non-commercial",
                         "noncommercial", "automated", "rate limit") if w in low]
    upd = re.search(r"Last Updated:?\s*([A-Z][a-z]+ \d{1,2}, \d{4})", txt)
    print(f"\n{url}\n  HTTP {st}, Last Updated {upd[1] if upd else 'not on page'}; AI/scraping/commercial/rate words: {words}")
    for n in needles:
        print(f"  {'found  ' if n in txt else 'MISSING'} {n!r}")

# 3. back on the BankFind page: what the API does with mistakes (each answer printed short)
st, final, txt = page(PAGE)
m = re.search(r"Data as of:\s*(\S+)", txt)
print(f"\n{PAGE} HTTP {st}; 'Data as of: {m[1] if m else 'NOT FOUND'}'")
for label, path, p in (
        ("lowercase field", "institutions", {"filters": 'name:"Silicon Valley Bank"', "fields": "NAME,CERT"}),
        ("lowercase fields=", "institutions", {"filters": "CERT:24735", "fields": "name,cert,asset"}),
        ("unknown field", "institutions", {"filters": 'BANKNAME:"Silicon Valley Bank"', "fields": "NAME,CERT"}),
        ("no quotes", "institutions", {"filters": "NAME:Silicon Valley Bank", "fields": "NAME,CERT", "limit": 3}),
        ("lowercase value", "institutions", {"filters": 'NAME:"silicon valley bank"', "fields": "NAME,CERT"}),
        ("closed bank INSFDIC", "institutions", {"filters": "CERT:24735", "fields": "NAME,ACTIVE,INSFDIC,INACTIVE,OFFICES"}),
        ("closed bank locations", "locations", {"filters": "CERT:24735", "fields": "OFFNAME"}),
        ("limit 10001", "failures", {"fields": "NAME", "limit": 10001}),
        ("default limit", "institutions", {"filters": "STALP:VT AND ACTIVE:1", "fields": "CERT"}),
        ("failures default limit", "failures", {"fields": "CERT"})):
    r = api(path, p)
    body = re.sub(r"\s+", " ", r["text"])
    if r["status"] == 200 and r["rows"] is not None:
        rows = json.loads(r["text"])["data"] if r["rows"] <= 3 and len(r["text"]) < 600 else None
        show = [x["data"] for x in rows] if rows is not None else f"{r['rows']} rows"
        print(f"{label:<22} HTTP 200 meta.total {r['total']}, {r['rows']} rows: {show}")
    else:
        print(f"{label:<22} HTTP {r['status']} {r['type']} {body[:260]}")
print(f"x-ratelimit-limit as this cross-origin page sees it: {r['rl']!r} (not exposed to pages; curl sees it, block 4)")
```

Output (from the run on 2026-11-18, 23:32 UTC):

```text
https://api.fdic.gov/robots.txt -> HTTP 404 at https://api.fdic.gov/robots.txt; 58 chars; User-agent lines []; Crawl-delay []; first line 'NOT_FOUND'
https://banks.data.fdic.gov/robots.txt -> HTTP 404 at https://api.fdic.gov/banks/robots.txt; 77 chars; User-agent lines []; Crawl-delay []; first line '{"message":"Cannot GET /api/robots.txt","error":"Not Found","statusCod'
https://www.fdic.gov/robots.txt -> HTTP 200 at https://www.fdic.gov/robots.txt; 2173 chars; User-agent lines ['*']; Crawl-delay ['1']; first line '#'

https://api.fdic.gov/banks/docs/
  HTTP 200, Last Updated not on page; AI/scraping/commercial/rate words: []
  found   'Users are currently not required to register and obtain a unique'
  found   'Obtain your API key here'
  found   'Elastic Search'
  found   'To match a phrase, use double quotes'
  found   'Dates must be entered in "yyyy-mm-dd" format'
  found   '($thousands)'
  found   'The format is controlled by'

https://www.fdic.gov/about/website-policies
  HTTP 200, Last Updated May 12, 2026; AI/scraping/commercial/rate words: []
  found   'Access to or use of the FDIC website constitutes consent to the following terms'
  found   'makes no express or implied warranty'
  found   'not designed or intended to provide authoritative financial'
  found   'does not constitute an endorsement, a recommendation, or a favoring by the FDIC'
  found   'otherwise cause damage. Such attempts are strictly prohibited'

https://banks.data.fdic.gov/bankfind-suite/bankfind HTTP 200; 'Data as of: 11/13/2026'
lowercase field        HTTP 200 meta.total 0, 0 rows: []
lowercase fields=      HTTP 200 meta.total 1, 1 rows: [{'ID': '24735'}]
unknown field          HTTP 200 meta.total 0, 0 rows: []
no quotes              HTTP 200 meta.total 17, 3 rows: [{'CERT': 10450, 'NAME': 'Valley Bank', 'ID': '10450'}, {'CERT': 13041, 'NAME': 'Valley Bank', 'ID': '13041'}, {'CERT': 15626, 'NAME': 'Valley Bank', 'ID': '15626'}]
lowercase value        HTTP 200 meta.total 1, 1 rows: [{'CERT': 24735, 'NAME': 'Silicon Valley Bank', 'ID': '24735'}]
closed bank INSFDIC    HTTP 200 meta.total 1, 1 rows: [{'ACTIVE': 0, 'INSFDIC': 1, 'INACTIVE': 1, 'NAME': 'Silicon Valley Bank', 'ID': '24735'}]
closed bank locations  HTTP 200 meta.total 0, 0 rows: []
limit 10001            HTTP 400 application/json; charset=utf-8 {"errors":[{"status":400,"code":"validate:too_big","title":"Invalid field data","detail":"Number must be less than or equal to 10000","source":{"parameter":"limit"},"meta":{"timestamp":"2026-11-18T23:33:08.554Z"}}]}
default limit          HTTP 200 meta.total 12, 10 rows: 10 rows
failures default limit HTTP 200 meta.total 4117, 10 rows: 10 rows
x-ratelimit-limit as this cross-origin page sees it: None (not exposed to pages; curl sees it, block 4)
```

### 3. Every open bank in a state, failures per year, robots check for every agent (Python urllib, no browser)

7 requests, 1 s apart: the three robots.txt files, 3 pages of 5 Vermont banks (to show `offset` paging; use `limit=10000` in practice), and every failure since 1934 in one call. `rules_for()` merges every group that names the agent (or every `*` group), as RFC 9309 says; a 4xx robots.txt means no rules, a 5xx means stop.

```python
import collections, json, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

STATE = "VT"       # two-letter code of the main office's state
SINCE_YEAR = 2008  # failures per year from this year on

API = "https://api.fdic.gov/banks"
UA = "fdic-bankfind-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
PAUSE = 1  # no published keyless limit; www.fdic.gov asks 'Crawl-delay: 1'
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
calls = 0
last_headers = {}

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
    """GET -> (status, final url, content-type, text). One retry: after Retry-After when sent, else 60 s on 429 and
    10 s on 5xx or a network error. Other HTTP errors are returned, not raised, so the caller decides."""
    global calls, last_headers
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(2):
        if calls:
            time.sleep(PAUSE)
        calls += 1
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                last_headers = dict(r.headers)
                return r.status, r.url, r.headers.get("Content-Type", ""), r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After"), 60 if e.code == 429 else 10))
                continue
            return e.code, e.url, e.headers.get("Content-Type", ""), e.read().decode(errors="replace")
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

def api(path, params):
    st, _, ctype, text = get(f"{API}/{path}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote))
    if st != 200 or "json" not in ctype:
        sys.exit(f"API HTTP {st} {ctype}: {text[:300]!r}")
    d = json.loads(text)
    if not isinstance(d.get("data"), list) or "total" not in d.get("meta", {}):
        sys.exit(f"unexpected body: {text[:300]!r}")
    return d

def all_rows(path, params, page=10000):
    """Every row for a query, paging with offset; checks the count against meta.total."""
    out, total = [], None
    while total is None or len(out) < total:
        d = api(path, {**params, "limit": page, "offset": len(out)})
        total = d["meta"]["total"]
        got = [x["data"] for x in d["data"]]
        if not got:
            break
        out += got
    if len(out) != total:
        sys.exit(f"{len(out)} rows but meta.total {total}")
    return out

# 1. robots.txt: a 4xx answer means no rules (RFC 9309 2.3.1.3: the crawler MAY access any resources)
for host, paths in (("https://api.fdic.gov", ["/banks/institutions", "/banks/locations", "/banks/failures", "/banks/docs/"]),
                    ("https://banks.data.fdic.gov", ["/bankfind-suite/bankfind"]),
                    ("https://www.fdic.gov", ["/about/website-policies"])):
    st, final, ctype, text = get(host + "/robots.txt")
    if 400 <= st < 500:
        print(f"{host}/robots.txt: HTTP {st} {ctype} (final {final}) -> no rules apply")
        continue
    if st != 200:
        sys.exit(f"{host}/robots.txt HTTP {st}: unreachable, so treat the host as disallowed (RFC 9309 2.3.1.4)")
    named = sorted({a for a in re.findall(r"(?im)^user-agent:\s*(\S+)", text)})
    for p in paths:
        ok = [a for a in AGENTS if allowed(rules_for(text, a), p)]
        print(f"{host}/robots.txt: HTTP 200, groups {named}, crawl-delay {re.findall(r'(?im)^crawl-delay:\s*(\S+)', text)}; "
              f"{p} allowed for {len(ok)}/{len(AGENTS)} agents")
        if len(ok) != len(AGENTS):
            sys.exit(f"robots.txt disallows {p} for {sorted(set(AGENTS) - set(ok))}: stop")

# 2. every open, insured bank headquartered in one state, largest first, paged 5 at a time to show offset paging
banks = all_rows("institutions", {"filters": f"STALP:{STATE} AND ACTIVE:1", "fields": "NAME,CERT,CITY,ASSET,DEP,OFFICES,REPDTE",
                                  "sort_by": "ASSET", "sort_order": "DESC"}, page=5)
if not banks:
    sys.exit(f"0 active banks for STALP:{STATE}: use the two-letter code in upper case")
print(f"\n{len(banks)} open FDIC-insured institutions headquartered in {STATE} (ACTIVE:1), report date "
      f"{sorted({b['REPDTE'] for b in banks})}, assets in thousands of dollars:")
for b in banks:
    print(f"  CERT {b['CERT']:<6} {b['NAME']:<44} {b['CITY']:<16} assets {b['ASSET']:>10,}  offices {b['OFFICES']}")
print(f"  total assets ${sum(b['ASSET'] for b in banks) / 1e6:,.2f} billion; {sum(b['OFFICES'] for b in banks)} offices")

# 3. failures per year: one call holds every failure since 1934 (4,117 rows fit under the 10,000 cap)
fails = all_rows("failures", {"fields": "FAILYR,FAILDATE,QBFASSET,COST,RESTYPE"})
kinds = collections.Counter(f["RESTYPE"] for f in fails)
years = collections.Counter(int(f["FAILYR"]) for f in fails if f["RESTYPE"] == "FAILURE")  # leave out ASSISTANCE rows
print(f"\n{len(fails)} rows since {min(int(f['FAILYR']) for f in fails)}: RESTYPE {dict(kinds)}; "
      f"RESTYPE FAILURE per year from {SINCE_YEAR}:")
print("  " + ", ".join(f"{y} {years.get(y, 0)}" for y in range(SINCE_YEAR, max(years) + 1)))
newest = max((f for f in fails if f["RESTYPE"] == "FAILURE"), key=lambda f: datetime.strptime(f["FAILDATE"], "%m/%d/%Y"))
print(f"  newest FAILURE {newest['FAILDATE']}; peak year for failures {years.most_common(1)[0]}")

rl = {k.lower(): v for k, v in last_headers.items() if k.lower().startswith("x-ratelimit")}
print(f"\n{calls} requests; last response headers {rl}. Source: FDIC BankFind Suite API ({API}), retrieved "
      f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.")
```

Output (from the re-run on 2026-11-19, 00:16 UTC):

```text
https://api.fdic.gov/robots.txt: HTTP 404 application/json (final https://api.fdic.gov/robots.txt) -> no rules apply
https://banks.data.fdic.gov/robots.txt: HTTP 404 application/json; charset=utf-8 (final https://api.fdic.gov/banks/robots.txt) -> no rules apply
https://www.fdic.gov/robots.txt: HTTP 200, groups ['*'], crawl-delay ['1']; /about/website-policies allowed for 11/11 agents

12 open FDIC-insured institutions headquartered in VT (ACTIVE:1), report date ['06/30/2026'], assets in thousands of dollars:
  CERT 14140  Northfield Savings Bank                      Northfield       assets  1,576,574  offices 13
  CERT 14158  Union Bank                                   Morrisville      assets  1,558,133  offices 21
  CERT 6271   Community National Bank                      Derby            assets  1,172,186  offices 12
  CERT 33418  Ledyard National Bank                        Norwich          assets  1,071,557  offices 11
  CERT 14134  Passumpsic Savings Bank                      Saint Johnsbury  assets    934,455  offices 13
  CERT 30350  The Bank of Bennington                       Bennington       assets    661,897  offices 5
  CERT 6275   The National Bank of Middlebury              Middlebury       assets    553,549  offices 7
  CERT 14168  Peoples Trust Company of St. Albans          Saint Albans     assets    395,438  offices 5
  CERT 59298  Business Bank, The                           S Burlington     assets    352,210  offices 2
  CERT 28837  The Brattleboro Savings and Loan Association Brattleboro      assets    296,376  offices 5
  CERT 14136  Wells River Savings Bank                     Wells River      assets    266,865  offices 6
  CERT 6280   The First National Bank of Orwell            Orwell           assets     91,503  offices 2
  total assets $8.93 billion; 102 offices

4117 rows since 1934: RESTYPE {'FAILURE': 3524, 'ASSISTANCE': 593}; RESTYPE FAILURE per year from 2008:
  2008 25, 2009 140, 2010 157, 2011 92, 2012 51, 2013 24, 2014 18, 2015 8, 2016 5, 2017 8, 2018 0, 2019 4, 2020 4, 2021 0, 2022 0, 2023 5, 2024 2, 2025 2, 2026 4
  newest FAILURE 7/17/2026; peak year for failures (1989, 530)

7 requests; last response headers {'x-ratelimit-limit': '20', 'x-ratelimit-remaining': '19'}. Source: FDIC BankFind Suite API (https://api.fdic.gov/banks), retrieved 2026-11-19 00:16 UTC.
```

### 4. curl

```bash
B='https://api.fdic.gov/banks'
UA='fdic-bankfind-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# is it open and insured? one institution by CERT (ACTIVE 1 = open and insured; money in thousands)
curl -sS --fail -G -A "$UA" "$B/institutions" --data-urlencode 'filters=CERT:628' \
  --data-urlencode 'fields=NAME,CERT,ACTIVE,ASSET,DEP,OFFICES,REPDTE,CITY,STALP' \
  | python3 -c 'import sys, json
d = json.load(sys.stdin)
if d["meta"]["total"] != 1:
    sys.exit("expected 1 row, got %s" % d["meta"]["total"])
b = d["data"][0]["data"]
print(b["NAME"], "| CERT", b["CERT"], "| ACTIVE", b["ACTIVE"], "| assets $%.2f trillion" % (b["ASSET"] * 1000 / 1e12),
      "| offices", b["OFFICES"], "| report date", b["REPDTE"], "| index", d["meta"]["index"]["name"])'
sleep 1
# the five newest bank failures as CSV: format=csv (an 'Accept: text/csv' header still got JSON on 2026-11-18)
curl -sS --fail -G -A "$UA" "$B/failures" --data-urlencode 'format=csv' --data-urlencode 'fields=NAME,CITYST,FAILDATE,CERT' \
  --data-urlencode 'sort_by=FAILDATE' --data-urlencode 'sort_order=DESC' --data-urlencode 'limit=5'
echo
sleep 1
# headers: JSON, CORS open, the keyless rate-limit headers
curl -sS -G -A "$UA" -D - -o /dev/null "$B/failures" --data-urlencode 'limit=1' | tr -d '\r' \
  | grep -iE '^(HTTP/|content-type|access-control-allow-origin|x-ratelimit|retry-after|via)'
sleep 1
# mistakes: limit over 10,000 and an unclosed quote are loud HTTP 400s; a lowercase field name or code value is a silent 0
curl -sS -G -A "$UA" -w '\nHTTP %{http_code}\n' "$B/failures" --data-urlencode 'limit=10001' --data-urlencode 'fields=NAME'
sleep 1
curl -sS -G -A "$UA" -o /dev/null -w 'filters=NAME:"Silicon Valley Bank (unclosed quote) -> HTTP %{http_code}\n' \
  "$B/institutions" --data-urlencode 'filters=NAME:"Silicon Valley Bank' --data-urlencode 'fields=NAME'
sleep 1
curl -sS -G -A "$UA" "$B/institutions" --data-urlencode 'filters=cert:628' --data-urlencode 'fields=NAME' \
  | python3 -c 'import sys, json; print("filters=cert:628 (lowercase) -> meta.total", json.load(sys.stdin)["meta"]["total"])'
sleep 1
for v in vt VT; do
  curl -sS -G -A "$UA" "$B/institutions" --data-urlencode "filters=STALP:$v AND ACTIVE:1" --data-urlencode 'fields=CERT' \
    | python3 -c 'import sys, json; print("filters=STALP:'"$v"' AND ACTIVE:1 -> meta.total", json.load(sys.stdin)["meta"]["total"])'
  sleep 1
done
# robots.txt: 404 on both API hosts (banks.data.fdic.gov redirects to api.fdic.gov/banks/robots.txt)
for u in https://api.fdic.gov/robots.txt https://banks.data.fdic.gov/robots.txt; do
  curl -sS -L -A "$UA" -o /dev/null -w "$u -> HTTP %{http_code} %{content_type} at %{url_effective}\n" "$u"; sleep 1
done
```

Output (from the verifier's re-run on 2026-11-18, 23:41 UTC):

```text
JPMorgan Chase Bank, National Association | CERT 628 | ACTIVE 1 | assets $4.09 trillion | offices 5416 | report date 06/30/2026 | index institutions_20261113100007
"CERT","CITYST","FAILDATE","ID","NAME"
25744,"LENEXA, KS","7/17/2026","4117","SMALL BUSINESS BANK"
28722,"KENTLAND, IN","7/10/2026","4116","KENTLAND FS&LA"
25796,"LAGRANGE, GA","5/1/2026","4115","COMMUNITY BANK AND TRUST - WEST GEORGIA"
57488,"CHICAGO, IL","1/30/2026","4114","METROPOLITAN CAPITAL B&T"
5520,"SANTA ANNA, TX","6/27/2025","4113","SANTA ANNA NATIONAL BANK"
HTTP/2 200 
content-type: application/json; charset=utf-8
access-control-allow-origin: *
via: https/1.1 api-umbrella (ApacheTrafficServer [cMsSf ])
x-ratelimit-limit: 20
x-ratelimit-remaining: 19
{"errors":[{"status":400,"code":"validate:too_big","title":"Invalid field data","detail":"Number must be less than or equal to 10000","source":{"parameter":"limit"},"meta":{"timestamp":"2026-11-18T23:41:31.722Z"}}]}
HTTP 400
filters=NAME:"Silicon Valley Bank (unclosed quote) -> HTTP 400
filters=cert:628 (lowercase) -> meta.total 0
filters=STALP:vt AND ACTIVE:1 -> meta.total 0
filters=STALP:VT AND ACTIVE:1 -> meta.total 12
https://api.fdic.gov/robots.txt -> HTTP 404 application/json at https://api.fdic.gov/robots.txt
https://banks.data.fdic.gov/robots.txt -> HTTP 404 application/json; charset=utf-8 at https://api.fdic.gov/banks/robots.txt
```

## Fields

| Endpoint | Field | Example | Notes |
|---|---|---|---|
| institutions | `CERT` | `628` | "A unique NUMBER assigned by the FDIC used to identify institutions and for the issuance of insurance certificates"; the key for `/locations`, `/failures`, `/financials` and `/history` |
| institutions | `ACTIVE` | `1` | 1 = "currently open and insured by the FDIC", 0 = "closed or not insured by FDIC" |
| institutions | `INSFDIC` | `1` | "Includes institutions insured by the FDIC"; still 1 for Silicon Valley Bank (closed 2023), so do not use it as "insured today" |
| institutions | `ASSET`, `DEP` | `4091315000` | total assets and total deposits, thousands of dollars ($4.09 trillion) |
| institutions | `OFFICES` | `5416` | offices including the main office; left out of the row for a closed bank |
| institutions | `REPDTE`, `DATEUPDT` | `06/30/2026`, `11/11/2026` | report date of the financials, last data update |
| institutions | `INSDATE`, `ENDEFYMD` | `01/01/1934`, `03/10/2023` | date insured; for a closed bank, "the day that the institution became inactive" |
| institutions | `NAME`, `CITY`, `STALP`, `REGAGNT`, `WEBADDR` | `Columbus`, `OH`, `OCC` | legal name, main-office city and state, primary regulator (OCC, FDIC, FED, OTS, STATE) |
| locations | `OFFNAME`, `CITY`, `STALP`, `MAINOFF`, `SERVTYPE_DESC` | `FOWLERVILLE BRANCH`, `0`, `FULL SERVICE - BRICK AND MORTAR` | one row per office; `MAINOFF` 1 is the main office; 0 rows for a closed bank |
| failures | `NAME`, `CITYST`, `FAILDATE`, `FAILYR` | `SMALL BUSINESS BANK`, `LENEXA, KS`, `7/17/2026`, `2026` | names upper case |
| failures | `QBFASSET`, `QBFDEP`, `COST` | `72947`, `68773`, `5671` | assets, deposits and estimated loss to the insurance fund, thousands of dollars |
| failures | `RESTYPE`, `RESTYPE1`, `SAVR` | `FAILURE`, `PA`, `DIF` | failure or assistance; transaction type (`PA` insured and uninsured deposits sold to an acquirer, `PI` insured deposits only, `PO` payout, ...); insurance fund |
| financials | `REPDTE`, `ASSET`, `DEP`, `NETINC` | `20260630` | quarterly history, 170 quarters for CERT 628 |

Every response has `meta.total` (all matches), `meta.index.name` and `meta.index.createTimestamp` (when the data was built: institutions and locations 2026-11-13, financials 2026-11-16, failures 2026-08-25 on 2026-11-18), and `ID` in each row. Definitions: https://api.fdic.gov/banks/docs/institution_properties.yaml, `location_properties.yaml` and `failure_properties.yaml` in the same folder.

## Gotchas

- **Field names and code values must be upper case.** `name:"Silicon Valley Bank"` and `cert:628` give 0 rows with HTTP 200, and so does the lowercase value `STALP:vt` (`STALP:VT` gives 12, block 4); the OpenAPI spec (https://api.fdic.gov/banks/docs/swagger.yaml) says "All values must be entered in UPPERCASE". `NAME` is the exception that matched in lower case too: `NAME:"silicon valley bank"` finds the bank. `fields=name,cert` returns only `ID`.
- **Quote multi-word values.** `NAME:Silicon Valley Bank` is read as a query string and returned 17 rows of other banks ("Valley Bank" first). Escape `"` and `\` inside the quotes (block 1's `find()`).
- **Use `ACTIVE`, not `INSFDIC`, for "insured now".** Silicon Valley Bank has `ACTIVE` 0, `INACTIVE` 1 and `INSFDIC` 1.
- **A closed bank is not always a failed bank.** `ACTIVE` 0 also covers mergers and voluntary closings; only `/failures` (by `CERT`) says it failed. The failures list mixes `FAILURE` (3,524) and `ASSISTANCE` (593) rows: filter on `RESTYPE` before counting failures (block 3: 25 in 2008, 140 in 2009, 157 in 2010, 4 in 2026).
- **Fields with no value are left out of the row**, not set to null: Silicon Valley Bank has no `OFFICES`. Block 1 fills missing keys with `n/a`.
- **Default page size is 10 on `/failures` too**, though the OpenAPI spec says 100 (block 2). The maximum is 10,000 per call; page further with `offset`. `meta.total` is the full count whatever the `limit`.
- **Money in thousands, four date formats** (see Quick summary). Sort `FAILDATE` on the server (`sort_by=FAILDATE&sort_order=DESC` sorts by date) or parse it with `%m/%d/%Y`; never sort the strings.
- **`format=csv` gives CSV; an `Accept: text/csv` header still got JSON** on 2026-11-18, although the docs say "The format is controlled by the Accept header".
- **Data is a snapshot.** The BankFind page said "Data as of: 11/13/2026"; financials are quarterly (`REPDTE` 06/30/2026 for most banks on 2026-11-18). Print the report date with every number.
- **The rate-limit headers are hidden from pages.** `x-ratelimit-limit` is readable from curl and urllib but `None` in an in-page `fetch()` (not exposed by CORS).
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin`, never the title.

## What does not work

- **Lowercase or unknown field names, lowercase code values, unquoted multi-word names**: HTTP 200 with 0 or wrong rows, no error.
- **`limit` above 10,000**: HTTP 400 JSON `validate:too_big`, "Number must be less than or equal to 10000".
- **An unclosed quote in `filters`**: HTTP 400 JSON, "Invalid request input, please double check your search query syntax" (block 4).
- **Branches of a closed bank**: `/locations?filters=CERT:24735` is 0 rows; use `/history` (45 structure events for CERT 24735) for its past offices.
- **Not tested:** rate-limit behaviour (never provoked), the optional api.data.gov key, `/sod`, `/summary` and `/demographics`, and the aggregation parameters (`agg_by`, `total_fields`, `subtotal_by`).
