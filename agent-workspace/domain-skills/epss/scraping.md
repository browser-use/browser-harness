# EPSS (FIRST) via the FIRST API (api.first.org) - Get the Exploitation Probability and Percentile for a List of CVEs to Decide Which to Patch First (REST API, no key)

Field-tested against api.first.org on 2026-11-18 (US Pacific afternoon; 23:46-23:54 UTC) using a fresh Browser Use cloud browser (logged out; one session, 23:50-23:51 UTC) plus Python `urllib` and `curl` from a Linux machine. 17 browser page loads (an API JSON answer 3 times, both robots files and five documentation and terms pages twice each) and 28 in-page `fetch()` calls (blocks 1 and 2 each ran twice), 75 curl calls (67 to the API, 8 to robots.txt and documentation pages) and 14 urllib calls (8 of them robots.txt), all serial. Every API call was HTTP 200 except the deliberate HTTP 422 probes (a `date` before 2021-04-14) and one HTTP 404 probe of a misspelled path. Each call took about 0.05-0.7 s (most 0.15-0.35 s). No 429, no challenge, no key, no login. On 2026-11-19 (00:05 UTC) block 3 was re-run with an empty cache after a guard for an empty mover list: same output except the times.

robots.txt (checked 2026-11-18, curl, the cloud browser and `urllib.robotparser`): https://api.first.org/robots.txt answers HTTP 404 (the HTML "Oops, where is this page?" page), so the API host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources", and Python's parser treats it as allow-all. https://www.first.org/robots.txt is three lines: `User-agent: *`, `Disallow: /signin*`, `Disallow: /_/links/*`, with no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`; the documentation and terms pages this skill reads (`/epss/data`, `/epss/faq`, `/about/policies/terms`) are allowed for all 11 agents (block 3). Terms: the "Get the Data" page https://www.first.org/epss/data says "EPSS scores are published daily, free of charge, with no registration required" and "The EPSS API is designed for lookup, not bulk access. The intended use case is querying the current score for one CVE or a small batch"; for "bulk downloads or to keep a local copy of all scores in sync" it points to the daily CSV or the GitHub archive instead. The EPSS FAQ https://www.first.org/epss/faq: "Attribution is requested when EPSS data is used in publications or products." The API documentation https://api.first.org/ says "Public endpoints without authentication are limited to 1000 requests per minute" and "In the event you receive the response 429 Too many requests you have exceeded this limit and have been temporarily blocked", and asks to "avoid concurrent requests". The FIRST Services Terms of Use https://www.first.org/about/policies/terms (Version 1.0.0, effective September 2023; "API (Public)" is one of the listed Services) grant "a nonexclusive, nontransferable, revocable, limited license to view, copy, print, and distribute Content retrieved from the Services to the extent permissible under applicable laws only for vulnerability disclosure, cybersecurity incident response, or preventative cybersecurity uses", provided copyright and trademark notices are kept. Ranking your own CVEs for patching is a preventative cybersecurity use. No AI/ML, scraping, automated-access or non-commercial clause on any of these pages. Naming: the same terms say "FIRST® is a registered trademark of FIRST" and "You may not use or display any trademarks, service marks, logos, or designs owned by FIRST or its affiliates without FIRST’s prior written consent", so this skill says "EPSS (FIRST)" in plain text with a source line, uses no FIRST or EPSS logo, and is not affiliated with or endorsed by FIRST.

**Not a full risk score.** The FAQ: "EPSS is not a complete risk score. EPSS does not measure how much damage successful exploitation would cause, or whether it affects your environment." Use it to order a patch queue next to severity, exposure and known-exploited lists, and send CVE IDs only: never hostnames, asset names or ticket text.

## Quick summary

- **No scraping.** `GET https://api.first.org/data/v1/epss?cve=CVE-2021-44228,CVE-2024-3400` -> JSON `{"status":"OK","status-code":200,"version":"1.0","access":"public","total":2,"offset":0,"limit":100,"data":[{"cve":"CVE-2024-3400","epss":"0.999990000","percentile":"1.000000000","date":"2026-11-18"},{"cve":"CVE-2021-44228",...}]}`. No key, no registration, `Access-Control-Allow-Origin: *`.
- **Answer (run 2026-11-18, 23:51 UTC):** CVE-2021-44228 and CVE-2024-3400 both score **epss 0.99999, percentile 1.0**, dated 2026-11-18; of the 9 scored CVEs in block 1, CVE-2024-21762 is 0.84589 (percentile 0.99710) and CVE-2024-20131 is 0.00175 (percentile 0.07066). 562 CVEs score 0.95 or more out of 408,395 scored that day (`epss-gt=0.95`, `limit=0`).
- **`epss` is the probability of exploitation in the wild in the next 30 days; `percentile` is the share of all scored CVEs with the same score or lower** (FAQ and Get the Data page). Both are strings ("0.999990000"): convert before sorting. The FAQ says a 0.10 threshold "is commonly cited in the field but carries no special authority from EPSS".
- **Sort yourself, or use `sort=-epss`.** The answer comes in CVE-ID order, not by score. `order=!epss` was ignored in every run; the documented global parameter `sort=-epss` sorts by score, highest first.
- **Silent failures:** an unknown ID, a malformed ID, an ID with a leading space (`%20CVE-...`), a wrong date format, `epss-gt=abc` and a `cve=` value over 2000 characters are all HTTP 200: the ID is dropped, or (for the long list) **0 rows for the whole list**, or (for `epss-gt=abc`) the filter is ignored. The default `limit` is **100**, so a 133-ID list returned 100 of its 125 scored rows. Blocks 1 and 3 clean the IDs, split at 2000 characters, set `limit` to the chunk size and check `total` against the rows.
- **Rate limit:** 1000 requests per minute without auth; a 429 means a temporary block. All blocks are serial at 0.5 s or more per call (120/min at most), wait `Retry-After` once on 429/5xx (default 60 s) and stop above 120 s; block 3 caches answers on disk for 6 h. The server sends `Cache-Control: public, max-age=86400`. For your whole inventory or all scores, the docs say use the daily CSV, not the API.

## What works

### 1. CVE list -> EPSS and percentile, highest first (browser)

`on_api_tab()` opens one logged-out api.first.org JSON answer so `fetch()` runs same-origin (the API also allows any origin). `get()` returns the parsed JSON on HTTP 200 with `status-code` 200, waits once on 429/500/502/503/504 and otherwise raises. `scores()` sends one call per 2000-character chunk with `limit` equal to the chunk size and stops if `total` and the row count differ. 1 `fetch()` call for the 12 inputs.

```python
import json, re, time, urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Your patch queue: CVE IDs only (never hostnames, asset names or ticket text). Messy on purpose:
# lower case, spaces, a duplicate, an ID with no score and a malformed ID.
QUEUE = ["CVE-2024-3400", "CVE-2021-44228", "CVE-2024-3094", "CVE-2024-21762", " cve-2023-4863 ", "CVE-2024-7340",
         "CVE-2024-9340", "CVE-2024-20129", "CVE-2024-20131", "CVE-2024-3400", "CVE-2099-0001", "CVE-2024-12"]

SITE = "https://api.first.org"
API = SITE + "/data/v1/epss"
PAUSE = 0.5       # public limit is 1000 requests per minute; serial and 0.5 s apart = at most 120/min
MAX_CVE = 2000    # documented cap on the cve= value (commas included). Longer lists silently return 0 rows
CVE_ID = re.compile(r"CVE-\d{4}-\d{4,}")

def on_api_tab():
    """fetch() from a logged-out api.first.org JSON page (the API also sends Access-Control-Allow-Origin: *)."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(API + "?cve=CVE-2021-44228")
    wait_for_load()
    if js("location.origin") != SITE or '"CVE-2021-44228"' not in (js("document.body ? document.body.innerText : ''") or ""):
        raise RuntimeError(f"api.first.org did not serve the EPSS API (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date; 60 when absent or unreadable; at least 1. Over 120 s: stop."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    if s > 120:
        raise RuntimeError(f"server asks to wait {s:.0f} s (over 120 s): stopping")
    return max(s, 1)

def fetch(url):
    """One in-page GET -> {status, headers, text}."""
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def get(params):
    """-> parsed JSON body. Waits Retry-After once on 429 (the docs: a temporary block) or 500/502/503/504 or a
    network error; raises on any other status and on an answer whose own status-code is not 200."""
    url = API + "?" + urllib.parse.urlencode(params, safe=",")
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(retry_after(r["headers"].get("retry-after")))
            continue
        break
    if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
        raise RuntimeError(f"{url[:120]}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
    body = json.loads(r["text"])
    if body.get("status-code") != 200 or not isinstance(body.get("data"), list):
        raise RuntimeError(f"{url[:120]}: {body.get('status')} {body.get('message')}; stopping")
    return body

def clean(ids):
    """Trim, upper-case, drop duplicates (keeping order); split off anything that is not a CVE ID."""
    good, bad = [], []
    for x in ids:
        c = x.strip().upper()
        if not CVE_ID.fullmatch(c):
            bad.append(x)
        elif c not in good:
            good.append(c)
    return good, bad

def chunks(ids):
    """Comma lists of at most MAX_CVE characters each."""
    out, cur = [], []
    for c in ids:
        if cur and len(",".join(cur + [c])) > MAX_CVE:
            out.append(cur)
            cur = []
        cur.append(c)
    return out + [cur] if cur else out

def scores(ids):
    """CVE IDs -> ({cve: row}, calls). One call per 2000-character chunk, limit = chunk size (the default is 100)."""
    rows, parts = {}, chunks(ids)
    for part in parts:
        body = get({"cve": ",".join(part), "limit": len(part)})
        if body["total"] != len(body["data"]):
            raise RuntimeError(f"total {body['total']} but {len(body['data'])} rows: page with offset=")
        for d in body["data"]:
            rows[d["cve"]] = d
    return rows, len(parts)

on_api_tab()
now = datetime.now(timezone.utc)
ids, bad = clean(QUEUE)
rows, calls = scores(ids)
dates = sorted({d["date"] for d in rows.values()})
if len(dates) != 1:
    raise RuntimeError(f"rows carry several score dates {dates}: stop")
order = sorted(rows.values(), key=lambda d: (-float(d["epss"]), -float(d["percentile"]), d["cve"]))
print(f"EPSS (FIRST) for {len(ids)} CVEs, scores dated {dates[0]}, queried {now:%Y-%m-%d %H:%M} UTC")
print(f"{'#':>2}  {'CVE':<16} {'EPSS':>7}  {'percentile':>10}")
for i, d in enumerate(order, 1):
    print(f"{i:>2}  {d['cve']:<16} {float(d['epss']):>7.5f}  {float(d['percentile']):>10.5f}")
missing = [c for c in ids if c not in rows]
print(f"no EPSS score (unknown or not yet scored): {', '.join(missing) or 'none'}")
print(f"not a CVE ID, not sent: {', '.join(repr(x) for x in bad) or 'none'}")
print(f"{len(QUEUE)} inputs -> {len(ids)} unique IDs -> {calls} API call(s) (at most {MAX_CVE} characters of cve= each)")
print(f"\nEPSS: estimated probability that a CVE is exploited in the wild in the next 30 days. Source: EPSS (FIRST), {API}, "
      f"scores of {dates[0]}, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the run on 2026-11-18, 23:51 UTC):

```text
EPSS (FIRST) for 10 CVEs, scores dated 2026-11-18, queried 2026-11-18 23:51 UTC
 #  CVE                 EPSS  percentile
 1  CVE-2021-44228   0.99999     1.00000
 2  CVE-2024-3400    0.99999     1.00000
 3  CVE-2023-4863    0.99979     0.99980
 4  CVE-2024-3094    0.90900     0.99810
 5  CVE-2024-21762   0.84589     0.99710
 6  CVE-2024-7340    0.05015     0.92414
 7  CVE-2024-9340    0.00970     0.62577
 8  CVE-2024-20129   0.00306     0.23791
 9  CVE-2024-20131   0.00175     0.07066
no EPSS score (unknown or not yet scored): CVE-2099-0001
not a CVE ID, not sent: 'CVE-2024-12'
12 inputs -> 10 unique IDs -> 1 API call(s) (at most 2000 characters of cve= each)

EPSS: estimated probability that a CVE is exploited in the wild in the next 30 days. Source: EPSS (FIRST), https://api.first.org/data/v1/epss, scores of 2026-11-18, accessed 18 November 2026 23:51 UTC.
```

### 2. robots.txt, the terms pages and query mistakes (browser)

7 page loads, 1 return to the API page and 13 in-page `fetch()` calls in the same tab.

```python
import json, time

SITE = "https://api.first.org"
API = SITE + "/data/v1/epss"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__u[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(query):
    """One in-page GET of API?query -> {status, text}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(API + "?" + query)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{query[:60]}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(0.5)  # 1000 requests per minute is the public limit
    return r

def brief(r):
    out = f"HTTP {r['status']}"
    try:
        b = json.loads(r["text"])
    except ValueError:
        return out + f" not JSON: {' '.join(r['text'].split())[:70]!r}"
    if not isinstance(b, dict) or "total" not in b:
        return out + f" {b.get('status') if isinstance(b, dict) else type(b).__name__} {b.get('message') if isinstance(b, dict) else ''}"
    rows = [(d["cve"], d["epss"].rstrip("0")) for d in b["data"][:3]]
    return out + f" total {b['total']}, {len(b['data'])} rows, limit {b['limit']}" + (f", first {rows}" if rows else "")

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(API + "?cve=CVE-2021-44228")
    wait_for_load()

st, txt = page(SITE + "/robots.txt")
print(f"api.first.org robots.txt HTTP {st}: {' '.join(txt.split())[:60]!r}")
st, txt = page("https://www.first.org/robots.txt")
lines = [l.strip() for l in txt.splitlines() if l.strip()]
print(f"www.first.org robots.txt HTTP {st}: {lines}")
for url, needles in (
    ("https://api.first.org/epss/", ["The maximum size accepted for this parameter is 2000 characters",
                                     "Shows the last 30 days (or what is available)", "(since April 14, 2021)"]),
    ("https://api.first.org/", ["limited to 1000 requests per minute", "you have exceeded this limit and have been temporarily blocked",
                                "Fields starting with - (minus sign) indicate a descending order"]),
    ("https://www.first.org/epss/data", ["published daily, free of charge, with no registration required",
                                         "designed for lookup, not bulk access", "reference to the API version, not the EPSS version",
                                         "EPSS v5 (v2026.06.15): started publishing 2026-06-15"]),
    ("https://www.first.org/epss/faq", ["Attribution is requested when EPSS data is used in publications or products",
                                        "within the next 30 days", "typically within a minute or two after 13:30 UTC daily"]),
    ("https://www.first.org/about/policies/terms", ["only for vulnerability disclosure, cybersecurity incident response, or preventative cybersecurity uses",
                                                    "is a registered trademark of FIRST", "You may not use or display any trademarks"]),
):
    st, txt = page(url)
    flat = " ".join(txt.split())
    for n in needles:
        print(f"{url.split('//')[1]:<34} HTTP {st}: {'found' if n in flat else 'MISSING'}: {n[:70]!r}")
page(API + "?cve=CVE-2021-44228")  # back to an API page
print()

fit_list = ",".join(f"CVE-2024-{i}" for i in range(20000, 20133))   # 133 IDs, 1,994 characters
long_list = ",".join(f"CVE-2024-{i}" for i in range(20000, 20140))  # 140 IDs, 2,099 characters
for label, query in (
    ("2 CVEs                              ", "cve=CVE-2021-44228,CVE-2024-3400"),
    ("lower case, space after comma       ", "cve=cve-2021-44228,%20CVE-2024-3400"),
    ("unknown + malformed IDs only        ", "cve=CVE-2099-0001,log4shell"),
    ("1,994-char list (133 IDs)           ", "cve=" + fit_list),
    ("same, limit=133                     ", "cve=" + fit_list + "&limit=133"),
    ("2,099-char list (140 IDs)           ", "cve=" + long_list),
    ("epss-gt=0.95, order=!epss           ", "epss-gt=0.95&order=!epss&limit=3"),
    ("epss-gt=0.95, sort=-epss            ", "epss-gt=0.95&sort=-epss&limit=3"),
    ("date=2026-06-14 (last v4 day)       ", "cve=CVE-2024-3400&date=2026-06-14"),
    ("date=2021-04-13 (before the data)   ", "cve=CVE-2021-44228&date=2021-04-13"),
    ("date=18-11-2026 (wrong format)      ", "cve=CVE-2024-3400&date=18-11-2026"),
    ("epss-gt=abc                         ", "epss-gt=abc&limit=1"),
):
    print(f"{label} {brief(raw(query))}")
r = raw("cve=CVE-2024-3400&scope=time-series")
ts = json.loads(r["text"])["data"][0]["time-series"]
print(f"scope=time-series                    HTTP {r['status']} {len(ts)} days, {ts[-1]['date']}..{ts[0]['date']}, "
      f"epss strings {ts[0]['epss']!r} (newest) and {ts[1]['epss']!r}")
```

Output (from the run on 2026-11-18, 23:51 UTC):

```text
api.first.org robots.txt HTTP 404: 'API Documentation FIRST.Org website Oops, where is this page'
www.first.org robots.txt HTTP 200: ['User-agent: *', 'Disallow: /signin*', 'Disallow: /_/links/*']
api.first.org/epss/                HTTP 200: found: 'The maximum size accepted for this parameter is 2000 characters'
api.first.org/epss/                HTTP 200: found: 'Shows the last 30 days (or what is available)'
api.first.org/epss/                HTTP 200: found: '(since April 14, 2021)'
api.first.org/                     HTTP 200: found: 'limited to 1000 requests per minute'
api.first.org/                     HTTP 200: found: 'you have exceeded this limit and have been temporarily blocked'
api.first.org/                     HTTP 200: found: 'Fields starting with - (minus sign) indicate a descending order'
www.first.org/epss/data            HTTP 200: found: 'published daily, free of charge, with no registration required'
www.first.org/epss/data            HTTP 200: found: 'designed for lookup, not bulk access'
www.first.org/epss/data            HTTP 200: found: 'reference to the API version, not the EPSS version'
www.first.org/epss/data            HTTP 200: found: 'EPSS v5 (v2026.06.15): started publishing 2026-06-15'
www.first.org/epss/faq             HTTP 200: found: 'Attribution is requested when EPSS data is used in publications or pro'
www.first.org/epss/faq             HTTP 200: found: 'within the next 30 days'
www.first.org/epss/faq             HTTP 200: found: 'typically within a minute or two after 13:30 UTC daily'
www.first.org/about/policies/terms HTTP 200: found: 'only for vulnerability disclosure, cybersecurity incident response, or'
www.first.org/about/policies/terms HTTP 200: found: 'is a registered trademark of FIRST'
www.first.org/about/policies/terms HTTP 200: found: 'You may not use or display any trademarks'

2 CVEs                               HTTP 200 total 2, 2 rows, limit 100, first [('CVE-2024-3400', '0.99999'), ('CVE-2021-44228', '0.99999')]
lower case, space after comma        HTTP 200 total 1, 1 rows, limit 100, first [('CVE-2021-44228', '0.99999')]
unknown + malformed IDs only         HTTP 200 total 0, 0 rows, limit 100
1,994-char list (133 IDs)            HTTP 200 total 125, 100 rows, limit 100, first [('CVE-2024-20132', '0.00175'), ('CVE-2024-20131', '0.00175'), ('CVE-2024-20130', '0.00079')]
same, limit=133                      HTTP 200 total 125, 125 rows, limit 133, first [('CVE-2024-20132', '0.00175'), ('CVE-2024-20131', '0.00175'), ('CVE-2024-20130', '0.00079')]
2,099-char list (140 IDs)            HTTP 200 total 0, 0 rows, limit 100
epss-gt=0.95, order=!epss            HTTP 200 total 562, 3 rows, limit 3, first [('CVE-2026-87902', '0.95769'), ('CVE-2026-85706', '0.97355'), ('CVE-2026-8037', '0.99794')]
epss-gt=0.95, sort=-epss             HTTP 200 total 562, 3 rows, limit 3, first [('CVE-2026-109619', '0.99999'), ('CVE-2026-109618', '0.99999'), ('CVE-2025-53770', '0.99999')]
date=2026-06-14 (last v4 day)        HTTP 200 total 1, 1 rows, limit 100, first [('CVE-2024-3400', '0.94297')]
date=2021-04-13 (before the data)    HTTP 422 Unprocessable Entity ['listNoResults']
date=18-11-2026 (wrong format)       HTTP 200 total 0, 0 rows, limit 100
epss-gt=abc                          HTTP 200 total 408395, 1 rows, limit 1, first [('CVE-2026-99999', '0.00788')]
scope=time-series                    HTTP 200 30 days, 2026-10-19..2026-11-17, epss strings '0.999990000' (newest) and '0.99999000'
```

### 3. Same lookup with Python urllib, robots check for every agent, change since your last triage, 6 h disk cache (no browser)

Sends a descriptive User-Agent (curl's default User-Agent also got HTTP 200). `date=YYYY-MM-DD` returns the score as published that day, so you can see what moved since the last time you ranked the queue; `scope=time-series` adds the 30 days before. The cache is one JSON file per URL. Run with an empty cache.

```python
import hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

API = "https://api.first.org/data/v1/epss"
UA = "epss-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/epss-skill"
CACHE = os.path.expanduser(CACHE_DIR)
TTL = 6 * 3600  # scores change once a day (about 13:30 UTC); 6 h picks up a new day without re-asking every run
PAUSE = 0.5     # public limit: 1000 requests per minute. Serial, 0.5 s apart = at most 120/min
MAX_CVE = 2000  # documented cap on cve=; a longer value returns 0 rows with HTTP 200
CVE_ID = re.compile(r"CVE-\d{4}-\d{4,}")
calls = hits = 0

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date; 60 when absent or unreadable; at least 1. Over 120 s: exit."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    if s > 120:
        sys.exit(f"server asks to wait {s:.0f} s (over 120 s): stopping")
    return max(s, 1)

def get(params):
    """-> JSON body, from the disk cache when younger than TTL. Once waits Retry-After (default 60 s) on
    429/500/502/503/504 or a network error; exits on anything else and on a body whose status-code is not 200."""
    global calls, hits
    url = API + "?" + urllib.parse.urlencode(params, safe=",")
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")
    try:
        if time.time() - os.path.getmtime(f) < TTL:
            hits += 1
            return json.load(open(f))
    except (OSError, ValueError):
        pass
    for attempt in range(2):
        time.sleep(PAUSE)
        calls += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After")))
                continue
            sys.exit(f"HTTP {e.code} {url[:120]}: {' '.join(e.read().decode(errors='replace').split())[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url[:120]}: {e}")
    body = json.loads(raw)
    if body.get("status-code") != 200 or not isinstance(body.get("data"), list):
        sys.exit(f"{url[:120]}: {body.get('status')} {body.get('message')}")
    os.makedirs(CACHE, exist_ok=True)
    open(f, "wb").write(raw)
    return body

def clean(ids):
    good = []
    for x in ids:
        c = x.strip().upper()
        if CVE_ID.fullmatch(c) and c not in good:
            good.append(c)
    return good

def epss(ids, date=None):
    """CVE IDs -> {cve: (epss float, percentile float, date)}. Splits at 2000 characters, asks for every row
    (limit = chunk size) and checks total == rows. date=YYYY-MM-DD gives that day's published score."""
    out, cur, parts = {}, [], []
    for c in clean(ids):
        if cur and len(",".join(cur + [c])) > MAX_CVE:
            parts.append(cur)
            cur = []
        cur.append(c)
    for part in parts + ([cur] if cur else []):
        q = {"cve": ",".join(part), "limit": len(part)} | ({"date": date} if date else {})
        body = get(q)
        if body["total"] != len(body["data"]):
            sys.exit(f"total {body['total']} but {len(body['data'])} rows: page with offset=")
        for d in body["data"]:
            out[d["cve"]] = (float(d["epss"]), float(d["percentile"]), d["date"])
    return out

# robots.txt: api.first.org answers 404 (RobotFileParser.read() treats a 4xx other than 401/403 as allow-all,
# RFC 9309 section 2.3.1.3); www.first.org has one '*' group. Check both for every agent.
for host, paths in (("https://api.first.org", ["/data/v1/epss?cve=CVE-2021-44228", "/epss/"]),
                    ("https://www.first.org", ["/epss/data", "/epss/faq", "/about/policies/terms"])):
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    try:
        with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
            print(f"{host}/robots.txt: HTTP {r.status}")
    except urllib.error.HTTPError as e:
        print(f"{host}/robots.txt: HTTP {e.code}")
    rp.read()
    for p in paths:
        ok = all(rp.can_fetch(a, host + p) for a in AGENTS)
        print(f"  robots {p:<34} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
        if not ok:
            sys.exit("robots.txt now disallows a path this skill uses: stop")

QUEUE = ["CVE-2024-3400", "CVE-2021-44228", "CVE-2024-3094", "CVE-2024-21762", "CVE-2023-4863", "CVE-2024-7340",
         "CVE-2024-9340", "CVE-2024-20129", "CVE-2024-20131", "CVE-2026-8037"]
THEN = "2026-10-01"  # the day of your last triage; the API keeps every daily score since 2021-04-14

now = datetime.now(timezone.utc)
today, before = epss(QUEUE), epss(QUEUE, THEN)
day = {d for _, _, d in today.values()}
print(f"\nEPSS (FIRST), queried {now:%Y-%m-%d %H:%M} UTC: scores of {', '.join(sorted(day))} vs {THEN}")
print(f"{'CVE':<16} {'EPSS now':>9} {'pctl':>8} {'EPSS ' + THEN[5:]:>10} {'change':>8}")
for c, (e, p, _) in sorted(today.items(), key=lambda kv: -kv[1][0]):
    b = before.get(c)
    ch = f"{e - b[0]:+.5f}" if b else "new"
    print(f"{c:<16} {e:>9.5f} {p:>8.5f} {(f'{b[0]:.5f}' if b else '-'):>10} {ch:>8}")

# 30-day history for the two biggest movers (scope=time-series takes the same cve list)
movers = sorted((c for c in today if c in before), key=lambda c: -abs(today[c][0] - before[c][0]))[:2]
body = get({"cve": ",".join(movers), "scope": "time-series", "limit": len(movers)}) if movers else {"data": []}
for d in sorted((d for d in body["data"] if d["cve"] in movers), key=lambda d: movers.index(d["cve"])):
    ts = [float(x["epss"]) for x in d["time-series"]]
    print(f"{d['cve']}: {len(ts)} days before {d['date']}, EPSS min {min(ts):.5f} max {max(ts):.5f}, "
          f"{d['time-series'][-1]['date']} {ts[-1]:.5f} -> {d['date']} {float(d['epss']):.5f}")

n1 = calls
epss(QUEUE)
epss(QUEUE, THEN)
print(f"\nnetwork calls {n1}, then {calls - n1} more for 2 repeated lookups (cache hits so far: {hits}, cache {CACHE_DIR})")
print(f"Source: EPSS (FIRST), {API}, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the run on 2026-11-18, 23:53 UTC):

```text
https://api.first.org/robots.txt: HTTP 404
  robots /data/v1/epss?cve=CVE-2021-44228   allowed for all 11 agents
  robots /epss/                             allowed for all 11 agents
https://www.first.org/robots.txt: HTTP 200
  robots /epss/data                         allowed for all 11 agents
  robots /epss/faq                          allowed for all 11 agents
  robots /about/policies/terms              allowed for all 11 agents

EPSS (FIRST), queried 2026-11-18 23:53 UTC: scores of 2026-11-18 vs 2026-10-01
CVE               EPSS now     pctl EPSS 10-01   change
CVE-2024-3400      0.99999  1.00000    0.99999 +0.00000
CVE-2021-44228     0.99999  1.00000    0.99999 +0.00000
CVE-2023-4863      0.99979  0.99980    0.99979 +0.00000
CVE-2026-8037      0.99794  0.99958    0.77362 +0.22432
CVE-2024-3094      0.90900  0.99810    0.85974 +0.04926
CVE-2024-21762     0.84589  0.99710    0.83428 +0.01161
CVE-2024-7340      0.05015  0.92414    0.05015 +0.00000
CVE-2024-9340      0.00970  0.62577    0.00952 +0.00018
CVE-2024-20129     0.00306  0.23791    0.00306 +0.00000
CVE-2024-20131     0.00175  0.07066    0.00175 +0.00000
CVE-2026-8037: 30 days before 2026-11-18, EPSS min 0.77362 max 0.99837, 2026-10-19 0.77362 -> 2026-11-18 0.99794
CVE-2024-3094: 30 days before 2026-11-18, EPSS min 0.90900 max 0.90900, 2026-10-19 0.90900 -> 2026-11-18 0.90900

network calls 3, then 0 more for 2 repeated lookups (cache hits so far: 2, cache ~/.cache/epss-skill)
Source: EPSS (FIRST), https://api.first.org/data/v1/epss, accessed 18 November 2026 23:53 UTC.
```

### 4. curl, CSV, headers and mistakes

```bash
B=https://api.first.org/data/v1/epss
# CVE list -> EPSS and percentile, highest first (sort=-epss is the documented sort; limit covers the whole list)
curl -sS --fail -G "$B" -d "cve=CVE-2024-3400,CVE-2024-21762,CVE-2024-9340,CVE-2024-3094" -d limit=4 -d sort=-epss \
  | python3 -c 'import json, sys
b = json.load(sys.stdin); print("total", b["total"])
for d in b["data"]: print(d["cve"], d["epss"], d["percentile"], d["date"])'
sleep 0.5
# the same as CSV (".csv" extension); the first line is the header
curl -sS --fail "$B.csv?cve=CVE-2024-3400,CVE-2024-9340"
sleep 0.5
# headers: JSON, cached 1 day, CORS open, a total count
curl -sS -D - -o /dev/null "$B?cve=CVE-2024-3400" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|access-control-allow-origin|x-total|retry-after|x-ratelimit-limit):)'
sleep 0.5
# mistakes: an unknown ID is silently dropped; order=!epss is not a sort; a date before 2021-04-14 is HTTP 422
curl -sS -w ' <- HTTP %{http_code}\n' "$B?cve=CVE-2099-0001"
sleep 0.5
curl -sS "$B?epss-gt=0.95&order=!epss&limit=3" | python3 -c 'import json, sys; print("order=!epss:", [d["epss"] for d in json.load(sys.stdin)["data"]])'
sleep 0.5
curl -sS -w ' <- HTTP %{http_code}\n' "$B?cve=CVE-2021-44228&date=2021-04-13"
```

Output (from the run on 2026-11-18, 23:53 UTC):

```text
total 4
CVE-2024-3400 0.999990000 1.000000000 2026-11-18
CVE-2024-3094 0.909000000 0.998100000 2026-11-18
CVE-2024-21762 0.845890000 0.997100000 2026-11-18
CVE-2024-9340 0.009700000 0.625770000 2026-11-18
cve,epss,percentile,date
CVE-2024-9340,0.009700000,0.625770000,2026-11-18
CVE-2024-3400,0.999990000,1.000000000,2026-11-18
HTTP/2 200 
cache-control: public, max-age=86400, s-maxage=86400
content-type: application/json; charset=utf-8
access-control-allow-origin: *
x-total: 1
{"status":"OK","status-code":200,"version":"1.0","access":"public","total":0,"offset":0,"limit":100,"data":[]}
 <- HTTP 200
order=!epss: ['0.957690000', '0.973550000', '0.997940000']
{"status":"Unprocessable Entity","status-code":422,"version":"1.0","access":"public","message":["listNoResults"],"data":{"error":["listNoResults"]}}
 <- HTTP 422
```

## Fields (`GET /data/v1/epss`)

| Field / parameter | Value | Notes |
|---|---|---|
| `cve` | comma list of CVE IDs | "maximum size accepted for this parameter is 2000 characters (including commas)"; over that, HTTP 200 with 0 rows. Case-insensitive (`cve-2021-44228` matched); a leading space drops that ID |
| `date` | `YYYY-MM-DD` | that day's published score "since April 14, 2021"; before it HTTP 422 `listNoResults`; a future date or another format gives 0 rows, HTTP 200 |
| `scope=time-series` | adds `time-series` | the 30 days before `date` (default today), newest first, each `{epss, percentile, date}`; works for several CVEs at once |
| `epss-gt`, `epss-lt`, `percentile-gt`, `percentile-lt` | decimal | "greater or equal" / "lower or equal". A non-number is ignored (all 408,395 rows) |
| `q` | text | partial CVE ID match (`q=CVE-2024-340` -> 168 rows) |
| `limit`, `offset` | default 100, 0 | `limit` caps at 10,000 (asked 20,000, got `limit` 10000); `limit=0` returns only `total` |
| `sort` | `-epss`, `epss`, `-percentile` | documented global parameter; `-` means descending (all three worked). `order=!epss` is not a sort here |
| `fields`, `envelope`, `pretty` | `fields=cve,epss`; `envelope=false` returns the bare array | a `.csv` extension returned CSV with a header line (the docs also list `.xml`, `.yml`, `.xls`, `.xlsx`; not tested) |
| `data[].epss`, `data[].percentile` | strings, 9 decimals today | `time-series` days before today carried 8 decimals ("0.99999000") |
| `data[].date` | `YYYY-MM-DD` | the score date, not your query time |
| `total` | integer | all matches, before `limit`; also in the `x-total` header |
| response headers | `content-type: application/json; charset=utf-8`, `cache-control: public, max-age=86400, s-maxage=86400`, `access-control-allow-origin: *` | served through a Varnish cache (`age` 1753 on the first call); no rate-limit headers seen |

## Gotchas

- **`v1` is the API version, not the model.** Get the Data: "Please note the "v1" in the URL is a reference to the API version, not the EPSS version." The model has been EPSS v5 (v2026.06.15) since 2026-06-15. A score history that crosses that date "reflects a change in methodology": CVE-2024-3400 was 0.94297 on 2026-06-14 and 0.99999 on 2026-06-15; CVE-2024-7340 went from 0.87694 to 0.05015 the same night. Compare scores within one model version.
- **Scores are published daily, but many repeat.** The FAQ says new scores come "typically within a minute or two after 13:30 UTC daily". Between 2026-10-01 and 2026-11-18, CVE-2026-8037 rose from 0.77362 to 0.99794 while CVE-2024-7340 stayed at 0.05015 and CVE-2024-3094's 30-day series was flat at 0.90900. Store the `date` with every score and re-rank daily or weekly.
- **The answer order is descending CVE ID compared as text, not your order and not by score.** `CVE-2024-6387` came before `CVE-2024-3094` and `CVE-2024-21762`; `CVE-2026-99999` before `CVE-2026-9999`. Match rows by `cve`, not by position.
- **Missing IDs are not errors.** An unknown, reserved or malformed ID is simply absent (133 IDs in, 125 rows out). Block 1 lists what got no score so it is not mistaken for a low score.
- **Ties at the top.** On 2026-11-18, 41 CVEs scored `epss` 0.99999 (`epss-gt=0.99999`), with `percentile` from 0.99991 to 1.0, so `percentile` breaks some ties. Blocks 1 and 3 sort by `epss`, then `percentile`, then ID.
- **Bulk is not the API's job.** Get the Data: the API "should not be used for bulk downloads or to keep a local copy of all scores in sync". It points to https://epss.empiricalsecurity.com/epss_scores-current.csv.gz (daily) and https://github.com/empiricalsec/epss_scores (archive back to 2021-04-14); neither was fetched here.
- **Credit and no logo.** Show "Source: EPSS (FIRST)" with the API URL and the score date, no FIRST logo, and nothing that suggests FIRST endorses your product.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **`order=!epss`** (not a documented parameter: the API documentation lists `sort` as the global sort parameter and no `order`): HTTP 200, but the rows came back unsorted (0.95769, 0.97355, 0.99794 for `epss-gt=0.95`). Use `sort=-epss` or sort client-side.
- **One long `cve=` list**: over 2000 characters gives 0 rows with HTTP 200 and no message. Split the list (blocks 1 and 3).
- **Not tested:** the 429 response and the temporary block (never provoked), the `days` parameter, JSONP `callback`, `.xls`/`.xlsx`/`.xml`/`.yml`, and the daily CSV and GitHub archive (other hosts; their robots.txt and terms were not checked).
