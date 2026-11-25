# Statistics Denmark StatBank API via api.statbank.dk - Get Denmark's Latest Quarterly Population (Table FOLK1A) for the Whole Country and the 5 Largest Municipalities: Read the Table Info, Pull the Newest Quarters as Tidy Rows, Stream BULK Past the 1,000,000-Cell Limit (JSON-stat/CSV API, no key)

Field-tested against api.statbank.dk on 2026-11-24 (US Pacific afternoon; 2026-11-25 00:00 UTC to 00:14 UTC) using a fresh Browser Use cloud browser (logged out; one session, 00:04-00:11 UTC, stopped and confirmed `stopped` afterwards) plus Python `urllib` and `curl` from a Linux machine. 11 browser page loads (block 1 opened one API answer in each of its two runs; block 2 loaded two robots.txt files, the StatBank API help page and an API answer in each of its two runs; one more load read where "429" sat on the help page) and 44 in-page `fetch()` calls (block 1: 3 per run; block 2: 19 per run), 14 urllib calls (block 3 ran twice: 2 robots.txt files and 5 API calls each) and 67 curl calls (41 while exploring, five of them www.dst.dk or www.statbank.dk pages; 13 in each of block 4's two runs), all serial and at least 1 s apart in the blocks. Every data call was HTTP 200 except the deliberate HTTP 400 and 500 probes of mistakes and the HTTP 404 of the API host's robots.txt. No 403 or 429, no challenge, no key, no login, no cookie. Data calls took 0.7-3.5 s (JSON-stat for all 105 areas 2.6-2.9 s in curl, at most 3.5 s in the browser; error answers 0.7-1.0 s); the full newest-quarter BULK file is 3,058,022 bytes with codes and 6,038,491 with labels (the labelled one took 5.3 s). Each block below ran twice; the outputs shown come from the second run, and the first runs differed only as noted under each output. An independent re-run on 2026-11-25 00:14-00:17 UTC (a new cloud browser for blocks 1 and 2, stopped and confirmed `stopped`; urllib and curl for blocks 3 and 4) printed the same data in all four blocks; only the clock and the timings changed (slowest browser call 3.7 s). After a code review, blocks 1 and 3 also read a `Retry-After` given as an HTTP date; they re-ran on 2026-11-25 at 01:01 and 01:02 UTC (block 1 in a new cloud browser, stopped and confirmed `stopped`) with the same data, and the outputs shown for them come from those runs.

robots.txt (checked 2026-11-25 UTC, curl, the cloud browser and `urllib.robotparser`): https://api.statbank.dk/robots.txt is HTTP 404 with a JSON body (`{"errorTypeCode":"REQUEST-NOTFOUND",...}`), so the API host has no robots rules and no named AI-agent groups; RFC 9309 section 2.3.1.3 says that for 400-499 answers "the crawler MAY access any resources on the server". https://www.dst.dk/robots.txt has two groups: `User-agent: *` (Disallow lines for `/App_*`, `/Code/`, `/Internal/`, `/sitecore*`, `/temp/`, `/upload/`, `/xsl/`, `*.axd` and 94 `/Extranet/...` paths) and `User-agent: GPTBot` with `Crawl-delay: 10` and the same non-Extranet Disallow lines; no line touches `/en/`. ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`. Every path this skill uses is allowed for all 11 agents (block 3); GPTBot should space www.dst.dk loads 10 s apart. Terms: the StatBank API help page https://www.dst.dk/en/Statistik/hjaelp-til-statistikbanken/api says "You can use all statistical data at Statistikbanken.dk and the web page dst.dk free of charge for commercial as well as non-commercial purposes, as long as you include a source reference. This corresponds to the licence named Creative Commons, CC 4.0 BY", "You can make free use of data in the development of various services", and sets the only limit: "The maximum number of cells retrieved using "non-bulk" (e.g. CSV, px etc.) has been set to 1,000,000 cells", which "does not apply to the so-called "bulk" formats where data is streamed in smaller portions with no upper limit". Only the CATALOGUE function (a DCAT-AP list of tables) needs an API key. No AI/ML, scraping, automated-access or non-commercial-only clause (block 2 found none of the words scrap, artificial intelligence, machine learning, robot or crawl on the page, and "non-commercial" only inside "commercial as well as non-commercial"); the page states no call-rate limit. The "About the website" page https://www.dst.dk/en/OmDS/om-hjemmesiden links only a cookie policy, a privacy policy and a sitemap. Naming: this skill says "Statistics Denmark" in plain text, gives a source reference ("Source: Statistics Denmark, StatBank table FOLK1A" with the quarter, a link and the access date), uses no Statistics Denmark logo, and is not endorsed by Statistics Denmark.

**Official, but check the quarter.** FOLK1A counts the population "at the first day of the quarter": `2026K4` (label `2026Q4`) is the count for 1 October 2026, published 2026-11-10. Every answer carries the table ID, the quarter code and the `updated` time; quote them.

## Quick summary

- **No scraping.** Three GET endpoints, no key: `GET https://api.statbank.dk/v1/tables?lang=en&format=JSON` (every active table with `latestPeriod`; `pastdays=7`, `includeinactive=true`), `GET /v1/tableinfo/FOLK1A?lang=en&format=JSON` (variables, their codes and English labels) and `GET /v1/data/FOLK1A/{JSONSTAT|CSV|BULK}?lang=en&OMR%C3%85DE=*&Tid=(1)` (one cell per combination; `*` for all values, `(1)` the newest period, `(-n%2B2)` the newest two). The same parameters also go as a JSON body to `POST /v1/data`. CORS is open (`Access-Control-Allow-Origin: *`), so `fetch()` works from any page.
- **Answer (run 2026-11-25, 00:10 UTC):** Denmark's population on the first day of **2026Q4** (1 October 2026): **6,044,001** (+12,302 on 2026Q3's 6,031,699; +24,135 or +0.40% on 2025Q4). The 5 largest municipalities: **Copenhagen 674,381**, **Aarhus 381,363**, **Aalborg 227,718**, **Odense 214,064**, **Vejle 124,253** (FOLK1A, updated 2026-11-10). Men 3,004,716, women 3,039,285; 21.3% of Denmark is 65 or older, 11.2% of Copenhagen.
- **Read `/tableinfo` first.** Variable and value codes stay Danish with `lang=en` (`OMRÅDE`, `KØN`, `ALDER`, `CIVILSTAND`, `Tid`; `000` All Denmark, `TOT` total, `IALT` all ages, quarter `2026K4` whose label is `2026Q4`). The 105 `OMRÅDE` codes are `000`, 5 regions (`081`-`085`, labels start with "Region ") and 99 other codes (the municipalities, Christiansø `411` among them). Block 1 tells them apart by label.
- **Leave a variable out and you get its total.** No `KØN`, `ALDER` or `CIVILSTAND` means both sexes, all ages, all statuses; no `Tid` means the newest period. Here the 5 regions and the 99 municipality codes both sum exactly to the national figure, and men + women equal the total.
- **Limits:** 1,000,000 cells per non-streaming call (CSV, JSON-stat, PX, XLSX...; HTTP 400 `REQUEST-LIMIT` above it), none for BULK and SDMX, which stream. No call-rate limit is published and no rate-limit headers came back. Blocks 1 and 3 run serially 1 s apart, wait once on 429, 5xx or a network error (`Retry-After` as seconds or as an HTTP date, else 10 s; over 120 s they stop) and then stop. Block 2 only inspects answers (about one call a second, no retry); block 4 sleeps 1 s between calls and lets `curl --retry 1` retry once on a timeout or HTTP 408, 429, 500, 502, 503 or 504.

## What works

### 1. Latest quarter for Denmark and the 5 largest municipalities: table info, every area in one call, by sex (browser)

`on_statbank_tab()` opens one logged-out api.statbank.dk answer so `fetch()` runs same-origin (cross-origin works too, see block 2). `get()` returns parsed JSON on HTTP 200, waits once on 429/5xx or a network error and otherwise raises with Statistics Denmark's `errorTypeCode` and message. 3 `fetch()` calls: `/tableinfo`, all 105 areas for the newest two quarters, and the six answer areas by sex. Change `TABLE` and the variable check to reuse it for another StatBank table.

```python
import email.utils, json, time
from datetime import datetime, timezone
from urllib.parse import urlencode

API = "https://api.statbank.dk/v1"
TABLE = "FOLK1A"   # "Population at the first day of the quarter" by region, sex, age, marital status and time
PAUSE = 1.0        # Statistics Denmark publishes no call-rate limit (only 1,000,000 cells per non-streaming call); stay at one a second
TOP = 5
UTC = timezone.utc

def on_statbank_tab():
    """fetch() runs same-origin from an api.statbank.dk answer (CORS is open too, see block 2)."""
    try:
        if js("location.origin") == "https://api.statbank.dk":
            return
    except Exception:
        pass
    new_tab(API + "/tableinfo/" + TABLE + "?lang=en&format=JSON")
    wait_for_load()
    if js("location.origin") != "https://api.statbank.dk" or '"id":"FOLK1A"' not in (js("document.body ? document.body.innerText : ''") or ""):
        raise RuntimeError(f"api.statbank.dk did not serve the FOLK1A table info (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

calls = []
def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.2)
    calls.append((r["status"], round(time.time() - t0, 1)))
    time.sleep(PAUSE)
    return r

def retry_wait(value, default=10):
    """Retry-After as delay-seconds or an HTTP date -> seconds to wait; missing or unreadable -> default."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def get(path, **params):
    """GET API + path -> parsed JSON. Waits once on 429, 5xx or a network error (Retry-After in seconds or as an
    HTTP date, else 10 s; over 120 s stops). Raises on anything else with Statistics Denmark's errorTypeCode and message."""
    url = API + path + "?" + urlencode(params)   # encodes OMRÅDE, KØN and the + in (-n+2)
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = retry_wait(r["headers"].get("retry-after"))
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):   # data comes as text/json
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"])

def tidy(ds):
    """JSON-stat (dataset.dimension.id/size) -> one dict per cell. `value` is flat in the order of
    dimension.id, last dimension fastest; each category.index gives a code's position."""
    dim = ds["dimension"]
    ids, sizes = dim["id"], dim["size"]
    codes = [sorted(dim[d]["category"]["index"], key=dim[d]["category"]["index"].get) for d in ids]
    rows = []
    for i, v in enumerate(ds["value"]):
        row, rest = {}, i
        for d, cs, n in reversed(list(zip(ids, codes, sizes))):
            c = cs[rest % n]
            rest //= n
            row[d], row[d + "_label"] = c, dim[d]["category"]["label"][c]
        row["value"] = v
        rows.append(row)
    return rows

on_statbank_tab()
now = datetime.now(UTC)
print(f"Statistics Denmark, StatBank API, table {TABLE}, checked {now:%Y-%m-%d %H:%M} UTC")

# 1. Table info: variables, codes, the newest quarter. Codes are Danish (OMRÅDE, KØN, Tid 2026K4); labels English.
info = get(f"/tableinfo/{TABLE}", lang="en", format="JSON")
var = {v["id"]: v for v in info["variables"]}
if not info["active"] or set(var) != {"OMRÅDE", "KØN", "ALDER", "CIVILSTAND", "Tid"}:
    raise RuntimeError(f"{TABLE} changed: active={info['active']}, variables {list(var)}: read /tableinfo again")
quarters = [v["id"] for v in var["Tid"]["values"]]
area = {v["id"]: v["text"] for v in var["OMRÅDE"]["values"]}
regions = [c for c, t in area.items() if t.startswith("Region ")]
munis = [c for c in area if c != "000" and c not in regions]
print(f"  {info['text']} ({info['unit']}), updated {info['updated']} (no zone), quarters {quarters[0]}..{quarters[-1]} ({len(quarters)}); "
      f"OMRÅDE: {len(area)} codes = 000 {area['000']!r} + {len(regions)} regions + {len(munis)} municipality codes")

# 2. Every area, newest two quarters, one call. Unselected variables (KØN, ALDER, CIVILSTAND) are eliminated: the API returns their totals.
ds = get(f"/data/{TABLE}/JSONSTAT", lang="en", **{"OMRÅDE": "*", "Tid": "(-n+2)"})["dataset"]
rows = tidy(ds)
got = sorted(ds["dimension"]["Tid"]["category"]["index"])
if got[-1] != quarters[-1] or len(rows) != len(area) * 2:
    raise RuntimeError(f"asked for the newest 2 quarters of {len(area)} areas, got {got} and {len(rows)} cells: stop")
new, old = got[-1], got[-2]
val = {(r["OMRÅDE"], r["Tid"]): r["value"] for r in rows}
label_q = ds["dimension"]["Tid"]["category"]["label"]
nat = val[("000", new)]
print(f"  dataset: {ds['label']!r}, updated {ds['updated']}, source {ds['source']!r}")
print(f"\nDenmark, population on the first day of {label_q[new]} ({new}): {nat:,} "
      f"({nat - val[('000', old)]:+,} on {label_q[old]}: {val[('000', old)]:,})")
s_reg, s_mun = sum(val[(c, new)] for c in regions), sum(val[(c, new)] for c in munis)
print(f"  check: {len(regions)} regions sum to {s_reg:,}, {len(munis)} municipality codes to {s_mun:,} "
      f"({'both equal' if s_reg == s_mun == nat else 'NOT equal to'} the national figure)")

top = sorted(munis, key=lambda c: -val[(c, new)])[:TOP]
print(f"\n{TOP} largest municipalities, {label_q[new]}:")
for i, c in enumerate(top, 1):
    a, b = val[(c, new)], val[(c, old)]
    print(f"  {i}. {c} {area[c]:<12} {a:>9,}  {a / nat:6.2%} of Denmark  {a - b:+7,} on {label_q[old]}")

# 3. The same six areas by sex, newest quarter (Tid left out = the newest period, "(1)")
ds2 = get(f"/data/{TABLE}/JSONSTAT", lang="en", **{"OMRÅDE": ",".join(["000"] + top), "KØN": "TOT,1,2"})["dataset"]
by = {(r["OMRÅDE"], r["KØN"]): r["value"] for r in tidy(ds2)}
if list(ds2["dimension"]["Tid"]["category"]["index"]) != [new]:
    raise RuntimeError(f"Tid left out returned {list(ds2['dimension']['Tid']['category']['index'])}, not {new}: stop")
print(f"\nby sex, {label_q[new]} (KØN TOT, 1 men, 2 women):")
for c in ["000"] + top:
    t, m, w = by[(c, "TOT")], by[(c, "1")], by[(c, "2")]
    print(f"  {area[c]:<12} total {t:>9,}  men {m:>9,}  women {w:>9,}  men+women {'= total' if m + w == t else f'!= total ({m + w:,})'}")

print(f"\n{len(calls)} API calls, statuses {sorted({s for s, _ in calls})}, slowest {max(t for _, t in calls)} s")
print(f"Source: Statistics Denmark, StatBank table {TABLE} ({label_q[new]}), https://www.statbank.dk/{TABLE}, via {API}, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (re-run on 2026-11-25 after the code-review fixes, 01:01 UTC, in a new cloud browser; the same numbers as the 00:05 and 00:10 UTC runs, which printed "(Danish time)" and "(no zone)" on the second line respectively):

```text
Statistics Denmark, StatBank API, table FOLK1A, checked 2026-11-25 01:01 UTC
  Population at the first day of the quarter (Number), updated 2026-11-10T08:00:00 (no zone), quarters 2008K1..2026K4 (76); OMRÅDE: 105 codes = 000 'All Denmark' + 5 regions + 99 municipality codes
  dataset: 'Population at the first day of the quarter by region, Indhold and time', updated 2026-11-10T07:00:00Z, source 'Statistics Denmark'

Denmark, population on the first day of 2026Q4 (2026K4): 6,044,001 (+12,302 on 2026Q3: 6,031,699)
  check: 5 regions sum to 6,044,001, 99 municipality codes to 6,044,001 (both equal the national figure)

5 largest municipalities, 2026Q4:
  1. 101 Copenhagen     674,381  11.16% of Denmark   +3,992 on 2026Q3
  2. 751 Aarhus         381,363   6.31% of Denmark   +3,093 on 2026Q3
  3. 851 Aalborg        227,718   3.77% of Denmark   +1,314 on 2026Q3
  4. 461 Odense         214,064   3.54% of Denmark     +924 on 2026Q3
  5. 630 Vejle          124,253   2.06% of Denmark     +306 on 2026Q3

by sex, 2026Q4 (KØN TOT, 1 men, 2 women):
  All Denmark  total 6,044,001  men 3,004,716  women 3,039,285  men+women = total
  Copenhagen   total   674,381  men   330,938  women   343,443  men+women = total
  Aarhus       total   381,363  men   186,695  women   194,668  men+women = total
  Aalborg      total   227,718  men   114,273  women   113,445  men+women = total
  Odense       total   214,064  men   105,607  women   108,457  men+women = total
  Vejle        total   124,253  men    62,458  women    61,795  men+women = total

3 API calls, statuses [200], slowest 3.7 s
Source: Statistics Denmark, StatBank table FOLK1A (2026Q4), https://www.statbank.dk/FOLK1A, via https://api.statbank.dk/v1, accessed 25 November 2026 01:01 UTC.
```

### 2. robots.txt, the StatBank API help page, CORS, what the API does with mistakes, the table list (browser)

4 page loads and 19 in-page `fetch()` calls in the same tab. The `/tableinfo` call runs cross-origin from www.dst.dk: a CORS-blocked `fetch()` would fail, and it returned the body.

```python
import json, time

API = "https://api.statbank.dk/v1"
HELP = "https://www.dst.dk/en/Statistik/hjaelp-til-statistikbanken/api"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, %s)
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(url, body=None):
    """One in-page GET (or POST of a JSON body) -> {status, headers, text}. No retries: this block only inspects answers."""
    opts = {"credentials": "omit", "cache": "no-store"}
    if body is not None:
        opts.update(method="POST", headers={"Content-Type": "application/json"}, body=json.dumps(body))
    rid = json.dumps(js(START_JS % (json.dumps(url if url.startswith("http") else API + url), json.dumps(opts))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.2)
    time.sleep(1)   # no published call-rate limit; this block makes about one call a second
    return r

def page(url):
    """Load a page -> (HTTP status, content type, final URL, visible text; innerText skips script ids such as ...429...)."""
    goto_url(url)
    wait_for_load()
    time.sleep(1)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    ct = js("document.contentType")
    return st, ct, js("location.href"), js("(document.body || document.documentElement).innerText || ''") or ""

# robots.txt: none on the API host (a JSON 404), two groups on www.dst.dk
for url in ("https://api.statbank.dk/robots.txt", "https://www.dst.dk/robots.txt"):
    st, ct, href, txt = page(url)
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    if ct.startswith("text/plain"):
        groups = [l for l in lines if l.lower().startswith("user-agent")]
        print(f"{url.split('//')[1]:<34} HTTP {st} {ct}: {len(lines)} lines, groups {groups}, "
              f"crawl-delay {[l for l in lines if l.lower().startswith('crawl-delay')]}, sitemap {[l for l in lines if l.lower().startswith('sitemap')]}")
        print(f"{'':<34} Disallow lines for /en/: {[l for l in lines if l.lower().startswith('disallow: /en')] or 'none'}")
    else:
        print(f"{url.split('//')[1]:<34} HTTP {st} {ct}: {txt.strip()[:100]!r}")

# The StatBank API help page: licence, cell limit, streaming formats, keys
st, ct, href, txt = page(HELP)
flat = " ".join(txt.split())
print(f"\n{href} HTTP {st}")
for n in ("You can use all statistical data at Statistikbanken.dk and the web page dst.dk free of charge for commercial as well as non-commercial purposes, as long as you include a source reference",
          "This corresponds to the licence named Creative Commons, CC 4.0 BY",
          "You can make free use of data in the development of various services",
          "The maximum number of cells retrieved using \"non-bulk\" (e.g. CSV, px etc.) has been set to 1,000,000 cells",
          "This limitation does not apply to the so-called \"bulk\" formats where data is streamed in smaller portions with no upper limit",
          "Data formats that are streamed, do not allow elimination of variables",
          "If a period is not stated, data will be returned for the latest period in the table",
          "Using this method requires an API key",
          "From the outset, the API will respond in Danish"):
    print(f"  {'found' if n in flat else 'MISSING'}: {n[:96]!r}")
low = flat.lower()
bad = [w for w in ("scrap", "artificial intelligence", "machine learning", "noncommercial", "robot", "crawl") if w in low]
nc = low.count("non-commercial")
print(f"  words scrap/AI/ML/robot/crawl on the page: {bad or 'none'}; 'non-commercial' {nc}x, "
      f"{'only in' if nc == low.count('commercial as well as non-commercial') else 'NOT only in'} 'commercial as well as non-commercial'")
print(f"  rate words: {[w for w in ('requests per', 'per second', 'per minute', 'rate limit', 'throttl', '429') if w in low] or 'none'}")

# CORS: a cross-origin fetch() from www.dst.dk reads the API answer
r = raw(API + "/tableinfo/FOLK1A?lang=en&format=JSON")
print(f"\ncross-origin fetch() from {js('location.origin')} to /tableinfo/FOLK1A: HTTP {r['status']} {r['headers'].get('content-type')}, "
      f"body readable: {r['text'].startswith('{')}")

page(API + "/tableinfo/FOLK1A?lang=en&format=JSON")   # back on the API host
print()

def brief(r):
    t = " ".join(r["text"].replace("﻿", "<BOM>").split())
    return f"HTTP {r['status']} {r['headers'].get('content-type', '').split(';')[0]}: {t[:118]}"

D = "/data/FOLK1A/CSV?lang=en"
for label, path in (
    ("unknown table FOLK9Z               ", "/tableinfo/FOLK9Z?lang=en&format=JSON"),
    ("lower-case folk1a, no selection     ", "/data/folk1a/CSV?lang=en"),
    ("value label as code (Copenhagen)    ", D + "&OMR%C3%85DE=Copenhagen"),
    ("OMRADE without the ring             ", D + "&OMRADE=101"),
    ("omrÅde in lower case                ", D + "&omr%C3%A5de=101"),
    ("Tid=2026Q4 (the label)              ", D + "&Tid=2026Q4"),
    ("Tid=(-n+2) with a raw +             ", D + "&Tid=(-n+2)"),
    ("Tid=(-n%2B2)                        ", D + "&Tid=(-n%2B2)"),
    ("Tid=>=2026K2 as %3E%3D2026K2        ", D + "&Tid=%3E%3D2026K2"),
    ("valuePresentation=Code              ", D + "&OMR%C3%85DE=000,101&valuePresentation=Code"),
    ("no format in the path               ", "/data/FOLK1A?lang=en"),
    ("lang=sv                             ", "/data/FOLK1A/CSV?lang=sv"),
    ("CSV, every cell of the newest qtr   ", D + "&OMR%C3%85DE=*&K%C3%98N=*&ALDER=*&CIVILSTAND=*&Tid=(1)"),
    ("BULK, a variable left out           ", "/data/FOLK1A/BULK?lang=en&OMR%C3%85DE=000"),
):
    print(f"{label} {brief(raw(path))}")
r = raw(API + "/data", {"table": "FOLK1A", "format": "CSV", "lang": "en",
                        "variables": [{"code": "OMRÅDE", "values": ["000", "101"]}, {"code": "Tid", "values": ["(1)"]}]})
print(f"POST /data with a JSON body          {brief(r)}")

# Which tables exist, and which population tables are newest?
tabs = json.loads(raw("/tables?lang=en&format=JSON")["text"])
allt = json.loads(raw("/tables?lang=en&format=JSON&includeinactive=true")["text"])
recent = json.loads(raw("/tables?lang=en&format=JSON&pastdays=7")["text"])
print(f"\n/tables: {len(tabs)} active tables, {len(allt)} with includeinactive=true, {len(recent)} updated in the last 7 days")
for t in tabs:
    if t["id"] in ("FOLK1A", "FOLK1AM", "BEFOLK1", "FOLK1B"):
        print(f"  {t['id']:<8} {t['text']:<45} {t['firstPeriod']}..{t['latestPeriod']}  updated {t['updated']}  {t['variables']}")
h = r["headers"]
print("headers:", {k: h.get(k) for k in ("content-type", "cache-control", "etag", "last-modified", "retry-after",
                                          "access-control-allow-origin", "x-ratelimit-limit", "x-rate-limit-remaining")})
print(f"Source: Statistics Denmark, StatBank, via {API}.")
```

Output (second run, 2026-11-25 00:07 UTC; the first run read `textContent`, which includes inline scripts, and its "rate words" line said `['429']` from a menu id `...DF42999108B...` in a script; the visible text has no 429):

```text
api.statbank.dk/robots.txt         HTTP 404 application/json: '{"errorTypeCode":"REQUEST-NOTFOUND","message":"Siden kan ikke findes. / Page not found."}'
www.dst.dk/robots.txt              HTTP 200 text/plain: 127 lines, groups ['User-agent: *', 'User-agent: GPTBot'], crawl-delay ['Crawl-delay: 10'], sitemap []
                                   Disallow lines for /en/: none

https://www.dst.dk/en/Statistik/hjaelp-til-statistikbanken/api HTTP 200
  found: 'You can use all statistical data at Statistikbanken.dk and the web page dst.dk free of charge fo'
  found: 'This corresponds to the licence named Creative Commons, CC 4.0 BY'
  found: 'You can make free use of data in the development of various services'
  found: 'The maximum number of cells retrieved using "non-bulk" (e.g. CSV, px etc.) has been set to 1,000'
  found: 'This limitation does not apply to the so-called "bulk" formats where data is streamed in smaller'
  found: 'Data formats that are streamed, do not allow elimination of variables'
  found: 'If a period is not stated, data will be returned for the latest period in the table'
  found: 'Using this method requires an API key'
  found: 'From the outset, the API will respond in Danish'
  words scrap/AI/ML/robot/crawl on the page: none; 'non-commercial' 1x, only in 'commercial as well as non-commercial'
  rate words: none

cross-origin fetch() from https://www.dst.dk to /tableinfo/FOLK1A: HTTP 200 text/json; charset=utf-8, body readable: True

unknown table FOLK9Z                HTTP 400 application/json: {"errorTypeCode":"EXTRACT-NOTFOUND","message":"Table does not exist: FOLK9Z"}
lower-case folk1a, no selection      HTTP 200 text/csv: TID;INDHOLD 2026Q4;6044001
value label as code (Copenhagen)     HTTP 400 application/json: {"errorTypeCode":"EXTRACT-NOTFOUND","message":"Can't find value: Copenhagen (OMRÅDE)"}
OMRADE without the ring              HTTP 400 application/json: {"errorTypeCode":"EXTRACT-NOTFOUND","message":"Can't find variable: OMRADE"}
omrÅde in lower case                 HTTP 200 text/csv: OMRÅDE;TID;INDHOLD Copenhagen;2026Q4;674381
Tid=2026Q4 (the label)               HTTP 400 application/json: {"errorTypeCode":"EXTRACT-NOTFOUND","message":"Can't find value: 2026Q4 (Tid)"}
Tid=(-n+2) with a raw +              HTTP 400 application/json: {"errorTypeCode":"EXTRACT-NOTFOUND","message":"Can't find value: (-n 2) (Tid)"}
Tid=(-n%2B2)                         HTTP 200 text/csv: TID;INDHOLD 2026Q3;6031699 2026Q4;6044001
Tid=>=2026K2 as %3E%3D2026K2         HTTP 200 text/csv: TID;INDHOLD 2026Q2;6031247 2026Q3;6031699 2026Q4;6044001
valuePresentation=Code               HTTP 200 text/csv: OMRÅDE;TID;INDHOLD 000;2026K4;6044001 101;2026K4;674381
no format in the path                HTTP 400 application/json: {"errorTypeCode":"REQUEST-MISSING","message":"Format not found or not valid."}
lang=sv                              HTTP 500 application/json: {"errorTypeCode":"SYSTEM-100","message":"Der er opstået en fejl."}
CSV, every cell of the newest qtr    HTTP 400 application/json: {"errorTypeCode":"REQUEST-LIMIT","message":"The request of up to 1,200,150 cells is over the limit of max. 1,000,000 c
BULK, a variable left out            HTTP 400 application/json: {"errorTypeCode":"EXTRACT-NOTALLOWED","message":"Values must be selected for variable: KØN"}
POST /data with a JSON body          HTTP 200 text/csv: OMRÅDE;TID;INDHOLD All Denmark;2026Q4;6044001 Copenhagen;2026Q4;674381

/tables: 2318 active tables, 5765 with includeinactive=true, 111 updated in the last 7 days
  FOLK1A   Population at the first day of the quarter    2008Q1..2026Q4  updated 2026-11-10T08:00:00  ['region', 'sex', 'age', 'marital status', 'time']
  FOLK1AM  Population at the first day of the month      2021M10..2026M10  updated 2026-11-10T08:00:00  ['region', 'sex', 'age', 'time']
  BEFOLK1  Population 1. January                         1971..2026  updated 2026-02-12T08:00:00  ['sex', 'age', 'marital status', 'time']
  FOLK1B   Population at the first day of the quarter    2008Q1..2026Q4  updated 2026-11-10T08:00:00  ['region', 'sex', 'age', 'citizenship', 'time']
headers: {'content-type': 'text/csv; charset=utf-8', 'cache-control': 'no-cache', 'etag': None, 'last-modified': None, 'retry-after': None, 'access-control-allow-origin': '*', 'x-ratelimit-limit': None, 'x-rate-limit-remaining': None}
Source: Statistics Denmark, StatBank, via https://api.statbank.dk/v1.
```

### 3. Same API with Python urllib: robots check for every agent, the newest quarter, a year of quarters as CSV, the age profile from a streamed BULK file (no browser)

Sends a descriptive User-Agent. The API sends `Cache-Control: no-cache` and no `ETag`, `Last-Modified` or gzip (`/tableinfo/FOLK1A` is 10,779 bytes with or without `Accept-Encoding: gzip`), so there is nothing to revalidate; compare `updated` from `/tableinfo` before re-downloading. Section 4 asks for every cell of the newest quarter as CSV, gets `REQUEST-LIMIT` and streams the same selection as BULK line by line instead.

```python
import csv, email.utils, io, json, sys, time, urllib.error, urllib.request, urllib.robotparser
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlencode

API = "https://api.statbank.dk/v1"
UA = "statbank-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
TABLE, TOP = "FOLK1A", 5
PAUSE = 1.0   # no published call-rate limit; one call a second
UTC = timezone.utc
stats = Counter()

def retry_wait(value, default=10):
    """Retry-After as delay-seconds or an HTTP date -> seconds to wait; missing or unreadable -> default."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

class StatbankError(Exception):
    """HTTP 400/404 with Statistics Denmark's {"errorTypeCode", "message"} body."""

def call(path, params, stream=False):
    """GET API + path. Serial, PAUSE apart. Waits once on 429, 5xx or a network error (Retry-After in seconds or
    as an HTTP date, else 10 s; over 120 s exits). Raises StatbankError on a 4xx with an errorTypeCode; exits on anything else.
    stream=True returns the open response (read it line by line, then close it)."""
    url = API + path + "?" + urlencode(params)   # percent-encodes OMRÅDE, KØN and the + in (-n+5)
    for attempt in range(2):
        time.sleep(PAUSE)
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120)
            stats["calls"] += 1
            if stream:
                return r
            with r:
                body = r.read()
            stats["bytes"] += len(body)
            return body
        except urllib.error.HTTPError as e:
            stats["calls"] += 1
            body = e.read().decode("utf-8", "replace")
            if attempt == 0 and e.code in (429, 500, 502, 503, 504):
                wait = retry_wait(e.headers.get("Retry-After"))
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            try:
                err = json.loads(body)
                raise StatbankError(f"HTTP {e.code} {err['errorTypeCode']}: {err['message']}") from None
            except (ValueError, KeyError):
                sys.exit(f"HTTP {e.code} {url}: {' '.join(body.split())[:150]}")
        except OSError as e:   # DNS, refused connection, timeout, reset
            if attempt == 0:
                time.sleep(10)
                continue
            sys.exit(f"{url}: {e}")

def get_json(path, **params):
    return json.loads(call(path, params))

def get_csv(path, **params):
    """CSV and BULK are semicolon-separated UTF-8; CSV starts with a byte-order mark, so decode with utf-8-sig."""
    return list(csv.DictReader(io.StringIO(call(path, params).decode("utf-8-sig")), delimiter=";"))

# 1. robots.txt. api.statbank.dk/robots.txt is a JSON 404 (no rules); www.dst.dk has '*' and a GPTBot group.
for host, paths in (("https://api.statbank.dk", ["/v1/tables", "/v1/tableinfo/FOLK1A", "/v1/data/FOLK1A/JSONSTAT",
                                                  "/v1/data/FOLK1A/CSV", "/v1/data/FOLK1A/BULK"]),
                    ("https://www.dst.dk", ["/en/Statistik/hjaelp-til-statistikbanken/api"])):
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    try:
        with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
            lines = r.read().decode("utf-8", "replace").splitlines()
            rp.parse(lines)
            print(f"{host}/robots.txt: HTTP {r.status} {r.headers.get('Content-Type')}, {len(lines)} lines, "
                  f"groups {[l.strip() for l in lines if l.lower().startswith('user-agent')]}")
    except urllib.error.HTTPError as e:
        print(f"{host}/robots.txt: HTTP {e.code} {e.headers.get('Content-Type')}: no robots file, so no rules")
        if not 400 <= e.code < 500 or e.code in (401, 403, 429):
            sys.exit("robots.txt unreachable, access denied or rate-limited: stop")
        rp.allow_all = True   # what RobotFileParser.read() does on a 4xx other than 401/403
    time.sleep(PAUSE)
    for p in paths:
        ok = all(rp.can_fetch(a, host + p) for a in AGENTS)
        delays = {a: rp.crawl_delay(a) for a in AGENTS if rp.crawl_delay(a)}
        print(f"  robots {p:<46} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents; crawl-delay {delays or 'none'}")
        if not ok:
            sys.exit("robots.txt now disallows a path this skill uses: stop")

now = datetime.now(UTC)
print(f"\nStatistics Denmark, StatBank API, table {TABLE}, checked {now:%Y-%m-%d %H:%M} UTC")

# 2. Table info and the newest quarter for every area (one JSON-stat call); keep the municipality codes
info = get_json(f"/tableinfo/{TABLE}", lang="en", format="JSON")
area = {v["id"]: v["text"] for v in next(v for v in info["variables"] if v["id"] == "OMRÅDE")["values"]}
newest = next(v for v in info["variables"] if v["id"] == "Tid")["values"][-1]
munis = [c for c, t in area.items() if c != "000" and not t.startswith("Region ")]
ds = get_json(f"/data/{TABLE}/JSONSTAT", lang="en", **{"OMRÅDE": "*", "Tid": newest["id"]})["dataset"]
idx = ds["dimension"]["OMRÅDE"]["category"]["index"]
pop = {c: ds["value"][i] for c, i in idx.items()}   # one value per area: ContentsCode and Tid have size 1
top = sorted(munis, key=lambda c: -pop[c])[:TOP]
print(f"{info['text']}, newest {newest['text']} (code {newest['id']}), updated {info['updated']}: Denmark {pop['000']:,}; "
      f"largest {TOP} of {len(munis)} municipality codes: " + ", ".join(f"{area[c]} {pop[c]:,}" for c in top))

# 3. The last 5 quarters for Denmark and those 5 as CSV (Tid=(-n+5); urlencode turns + into %2B)
rows = get_csv(f"/data/{TABLE}/CSV", lang="en", valuePresentation="CodeAndValue",
               **{"OMRÅDE": ",".join(["000"] + top), "Tid": "(-n+5)"})
qs = sorted({r["TID"] for r in rows})
grid = {(r["OMRÅDE"], r["TID"]): int(r["INDHOLD"]) for r in rows}
names = sorted({r["OMRÅDE"] for r in rows}, key=lambda a: -grid[(a, qs[-1])])
print(f"\nCSV columns {list(rows[0])}; one year of quarters (valuePresentation=CodeAndValue):")
print(f"  {'':<18}" + "".join(f"{q.split(' ')[0]:>11}" for q in qs) + "  year on year")
for a in names:
    v = [grid[(a, q)] for q in qs]
    print(f"  {a:<18}" + "".join(f"{x:>11,}" for x in v) + f"  {v[-1] - v[0]:+8,} ({(v[-1] - v[0]) / v[0]:+.2%})")

# 4. Age profile from every cell of the newest quarter: CSV refuses over 1,000,000 cells, so stream BULK instead
sel = {"OMRÅDE": "*", "KØN": "*", "ALDER": "*", "CIVILSTAND": "*", "Tid": newest["id"]}
try:
    get_csv(f"/data/{TABLE}/CSV", lang="en", valuePresentation="Code", **sel)
    print("\nCSV accepted the full selection")
except StatbankError as e:
    print(f"\nCSV with every value of every variable: {e}")
    if "REQUEST-LIMIT" not in str(e):
        raise
r = call(f"/data/{TABLE}/BULK", dict(lang="en", valuePresentation="Code", **sel), stream=True)
n, size, ages = 0, 0, Counter()
want = set(["000"] + top)
with r:
    head = None
    for raw_line in r:   # streamed: rows arrive in portions, nothing is held in memory but the counters
        size += len(raw_line)
        line = raw_line.decode("utf-8-sig").rstrip("\r\n").split(";")
        if head is None:
            head = line
            continue
        n += 1
        row = dict(zip(head, line))
        if row["OMRÅDE"] in want and row["KØN"] == "TOT" and row["CIVILSTAND"] == "TOT" and row["ALDER"] != "IALT":
            a = int(row["ALDER"])
            ages[(row["OMRÅDE"], "65+" if a >= 65 else "0-17" if a < 18 else "18-64")] += int(row["INDHOLD"])
stats["bytes"] += size
cells = 1
for v in info["variables"]:
    cells *= 1 if v["id"] == "Tid" else len(v["values"])
print(f"BULK: HTTP {r.status} {r.headers.get('Content-Type')}, header {head}, {n:,} rows ({cells:,} combinations; "
      f"suppressedDataValue {info['suppressedDataValue']!r}: a missing row means that value), {size:,} bytes")
print(f"  {'':<12} {'0-17':>8} {'18-64':>8} {'65+':>8}  (shares of the age-total, {newest['text']})")
for c in ["000"] + top:
    tot = sum(ages[(c, g)] for g in ("0-17", "18-64", "65+"))
    if tot != pop[c]:
        sys.exit(f"{area[c]}: ages add to {tot:,}, JSON-stat total {pop[c]:,}: stop")
    print(f"  {area[c]:<12} " + " ".join(f"{ages[(c, g)] / tot:>8.1%}" for g in ("0-17", "18-64", "65+")) + f"  (sum {tot:,} = total)")

print(f"\ntotals: {stats['calls']} API calls, {stats['bytes']:,} bytes")
print(f"Source: Statistics Denmark, StatBank table {TABLE} ({newest['text']}), https://www.statbank.dk/{TABLE}, via {API}, "
      f"accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (re-run on 2026-11-25 after the code-review fixes, 01:02 UTC; the same rows, counts and bytes as the 00:08 UTC run apart from the clock; the first run, at 00:08 UTC too, counted 4 API calls because the refused CSV call was not counted, and said "rows with that value are left out"):

```text
https://api.statbank.dk/robots.txt: HTTP 404 application/json; charset=utf-8: no robots file, so no rules
  robots /v1/tables                                     allowed for all 11 agents; crawl-delay none
  robots /v1/tableinfo/FOLK1A                           allowed for all 11 agents; crawl-delay none
  robots /v1/data/FOLK1A/JSONSTAT                       allowed for all 11 agents; crawl-delay none
  robots /v1/data/FOLK1A/CSV                            allowed for all 11 agents; crawl-delay none
  robots /v1/data/FOLK1A/BULK                           allowed for all 11 agents; crawl-delay none
https://www.dst.dk/robots.txt: HTTP 200 text/plain, 128 lines, groups ['User-agent: *', 'User-agent: GPTBot']
  robots /en/Statistik/hjaelp-til-statistikbanken/api   allowed for all 11 agents; crawl-delay {'GPTBot': 10}

Statistics Denmark, StatBank API, table FOLK1A, checked 2026-11-25 01:02 UTC
Population at the first day of the quarter, newest 2026Q4 (code 2026K4), updated 2026-11-10T08:00:00: Denmark 6,044,001; largest 5 of 99 municipality codes: Copenhagen 674,381, Aarhus 381,363, Aalborg 227,718, Odense 214,064, Vejle 124,253

CSV columns ['OMRÅDE', 'TID', 'INDHOLD']; one year of quarters (valuePresentation=CodeAndValue):
                         2025K4     2026K1     2026K2     2026K3     2026K4  year on year
  000 All Denmark     6,019,866  6,025,603  6,031,247  6,031,699  6,044,001   +24,135 (+0.40%)
  101 Copenhagen        672,677    671,714    673,438    670,389    674,381    +1,704 (+0.25%)
  751 Aarhus            377,970    378,361    378,295    378,270    381,363    +3,393 (+0.90%)
  851 Aalborg           225,877    226,033    226,279    226,404    227,718    +1,841 (+0.82%)
  461 Odense            212,703    213,168    213,431    213,140    214,064    +1,361 (+0.64%)
  630 Vejle             123,063    123,250    123,648    123,947    124,253    +1,190 (+0.97%)

CSV with every value of every variable: HTTP 400 REQUEST-LIMIT: The request of up to 1,200,150 cells is over the limit of max. 1,000,000 cells for this file format. Use BULK or other streaming format instead.
BULK: HTTP 200 text/csv; charset=utf-8, header ['OMRÅDE', 'KØN', 'ALDER', 'CIVILSTAND', 'TID', 'INDHOLD'], 129,677 rows (200,025 combinations; suppressedDataValue '0': a missing row means that value), 3,058,022 bytes
                   0-17    18-64      65+  (shares of the age-total, 2026Q4)
  All Denmark     18.7%    60.0%    21.3%  (sum 6,044,001 = total)
  Copenhagen      16.3%    72.5%    11.2%  (sum 674,381 = total)
  Aarhus          17.2%    67.2%    15.5%  (sum 381,363 = total)
  Aalborg         17.4%    63.7%    18.8%  (sum 227,718 = total)
  Odense          17.8%    64.0%    18.2%  (sum 214,064 = total)
  Vejle           20.6%    59.1%    20.3%  (sum 124,253 = total)

totals: 5 API calls, 3,074,098 bytes
Source: Statistics Denmark, StatBank table FOLK1A (2026Q4), https://www.statbank.dk/FOLK1A, via https://api.statbank.dk/v1, accessed 25 November 2026 01:02 UTC.
```

### 4. curl: table info, every area, CSV, POST, headers, mistakes, BULK

```bash
B=https://api.statbank.dk/v1
# --retry 1 retries once on a timeout or HTTP 408, 429, 500, 502, 503 or 504, 10 s later; no published call-rate limit, so 1 s apart
C="curl -sS --max-time 120 --retry 1 --retry-delay 10"
T=$(mktemp)
# 1. table info: variables (codes are Danish: OMRÅDE, KØN, ALDER, CIVILSTAND, Tid), the newest quarter, the update time
$C --fail "$B/tableinfo/FOLK1A?lang=en&format=JSON" | python3 -c 'import json, sys
t = json.load(sys.stdin); print(t["id"], repr(t["text"]), "updated", t["updated"], "active", t["active"], "suppressedDataValue", repr(t["suppressedDataValue"]))
for v in t["variables"]:
    print(" ", v["id"], "=", repr(v["text"]), "| eliminable" if v["elimination"] else "| required", "|", len(v["values"]), "values:", v["values"][0], "...", v["values"][-1])'
sleep 1
# 2. the newest quarter for every area as JSON-stat (Tid=(1)); OMRÅDE must be percent-encoded as OMR%C3%85DE
S=$($C --fail -o "$T" -w '%{time_total}' "$B/data/FOLK1A/JSONSTAT?lang=en&Tid=(1)&OMR%C3%85DE=*")
python3 -c 'import json, sys
d = json.load(open(sys.argv[1]))["dataset"]; cat = d["dimension"]["OMRÅDE"]["category"]
pop = {c: d["value"][i] for c, i in cat["index"].items()}
q = list(d["dimension"]["Tid"]["category"]["label"].values())[0]
mun = [c for c in pop if c != "000" and not cat["label"][c].startswith("Region ")]
print(q, "| All Denmark", format(pop["000"], ","), "| updated", d["updated"], "|", sys.argv[2], "s")
for c in sorted(mun, key=lambda c: -pop[c])[:5]: print(" ", c, cat["label"][c], format(pop[c], ","))' "$T" "$S"
sleep 1
# 3. CSV: semicolons, a UTF-8 byte-order mark, the last two quarters with (-n%2B2) (a raw + would arrive as a space)
$C --fail "$B/data/FOLK1A/CSV?lang=en&OMR%C3%85DE=000,101,751,851,461,630&Tid=(-n%2B2)&valuePresentation=CodeAndValue" -o "$T"
head -c 3 "$T" | od -An -tx1; cat "$T"; echo
sleep 1
# 4. POST with a JSON body (the help page recommends POST; no percent-encoding needed): men and women, Denmark and Copenhagen
$C --fail -H 'Content-Type: application/json' -d '{"table":"FOLK1A","format":"CSV","lang":"en","variables":[{"code":"OMRÅDE","values":["000","101"]},{"code":"KØN","values":["1","2"]},{"code":"Tid","values":["(1)"]}]}' "$B/data"
echo; sleep 1
# 5. headers: no ETag, Last-Modified or rate-limit headers; a request id; CORS open
$C -D - -o /dev/null -H 'Origin: https://example.org' "$B/tableinfo/FOLK1A?lang=en" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|etag|last-modified|retry-after|x-rate[a-z-]*|statbankapi-request-id|access-control-allow-origin):)' \
  | sed -E 's/(statbankapi-request-id: ).*/\1<uuid>/I'
sleep 1
# 6. mistakes are JSON {errorTypeCode, message}, also in a StatbankAPI-Error-* header
for u in "tableinfo/FOLK9Z?lang=en" \
         "data/FOLK1A/CSV?lang=en&OMR%C3%85DE=Copenhagen" \
         "data/FOLK1A/CSV?lang=en&OMRADE=101" \
         "data/FOLK1A/CSV?lang=en&Tid=(-n+2)" \
         "data/FOLK1A/CSV?lang=en&OMR%C3%85DE=*&K%C3%98N=*&ALDER=*&CIVILSTAND=*&Tid=(1)" \
         "data/FOLK1A/BULK?lang=en&OMR%C3%85DE=000"; do
  curl -sS --max-time 60 -o "$T" -w "%{http_code} " "$B/$u"; echo "$(head -c 150 "$T")  <- $u"; sleep 1
done
# 7. BULK streams past the cell limit: count rows without keeping the file
curl -sS --fail --max-time 300 "$B/data/FOLK1A/BULK?lang=en&valuePresentation=Code&OMR%C3%85DE=*&K%C3%98N=*&ALDER=*&CIVILSTAND=*&Tid=(1)" \
  | awk 'NR == 1 {print "BULK header: " $0} END {print "BULK rows: " NR - 1}'
rm -f "$T"; sleep 1
# 8. robots: none on the API host (JSON 404)
$C -o /dev/null -w 'api.statbank.dk/robots.txt: HTTP %{http_code} %{content_type}\n' https://api.statbank.dk/robots.txt
echo "Source: Statistics Denmark, StatBank table FOLK1A, https://www.statbank.dk/FOLK1A, via $B, accessed $(date -u '+%d %B %Y %H:%M') UTC."
```

Output (second run, 2026-11-25 00:11 UTC; the 00:10 UTC run printed the same apart from the timing and the clock):

```text
FOLK1A 'Population at the first day of the quarter' updated 2026-11-10T08:00:00 active True suppressedDataValue '0'
  OMRÅDE = 'region' | eliminable | 105 values: {'id': '000', 'text': 'All Denmark'} ... {'id': '851', 'text': 'Aalborg'}
  KØN = 'sex' | eliminable | 3 values: {'id': 'TOT', 'text': 'Total'} ... {'id': '2', 'text': 'Women'}
  ALDER = 'age' | eliminable | 127 values: {'id': 'IALT', 'text': 'Age, total'} ... {'id': '125', 'text': '125 years'}
  CIVILSTAND = 'marital status' | eliminable | 5 values: {'id': 'TOT', 'text': 'Total'} ... {'id': 'F', 'text': 'Divorced'}
  Tid = 'time' | required | 76 values: {'id': '2008K1', 'text': '2008Q1'} ... {'id': '2026K4', 'text': '2026Q4'}
2026Q4 | All Denmark 6,044,001 | updated 2026-11-10T07:00:00Z | 2.560568 s
  101 Copenhagen 674,381
  751 Aarhus 381,363
  851 Aalborg 227,718
  461 Odense 214,064
  630 Vejle 124,253
 ef bb bf
﻿OMRÅDE;TID;INDHOLD
000 All Denmark;2026K3 2026Q3;6031699
000 All Denmark;2026K4 2026Q4;6044001
101 Copenhagen;2026K3 2026Q3;670389
101 Copenhagen;2026K4 2026Q4;674381
751 Aarhus;2026K3 2026Q3;378270
751 Aarhus;2026K4 2026Q4;381363
851 Aalborg;2026K3 2026Q3;226404
851 Aalborg;2026K4 2026Q4;227718
461 Odense;2026K3 2026Q3;213140
461 Odense;2026K4 2026Q4;214064
630 Vejle;2026K3 2026Q3;123947
630 Vejle;2026K4 2026Q4;124253

﻿OMRÅDE;KØN;TID;INDHOLD
All Denmark;Men;2026Q4;3004716
All Denmark;Women;2026Q4;3039285
Copenhagen;Men;2026Q4;330938
Copenhagen;Women;2026Q4;343443

HTTP/2 200
cache-control: no-cache
content-type: text/json; charset=utf-8
access-control-allow-origin: *
statbankapi-request-id: <uuid>
400 {"errorTypeCode":"EXTRACT-NOTFOUND","message":"Table does not exist: FOLK9Z"}  <- tableinfo/FOLK9Z?lang=en
400 {"errorTypeCode":"EXTRACT-NOTFOUND","message":"Can't find value: Copenhagen (OMRÅDE)"}  <- data/FOLK1A/CSV?lang=en&OMR%C3%85DE=Copenhagen
400 {"errorTypeCode":"EXTRACT-NOTFOUND","message":"Can't find variable: OMRADE"}  <- data/FOLK1A/CSV?lang=en&OMRADE=101
400 {"errorTypeCode":"EXTRACT-NOTFOUND","message":"Can't find value: (-n 2) (Tid)"}  <- data/FOLK1A/CSV?lang=en&Tid=(-n+2)
400 {"errorTypeCode":"REQUEST-LIMIT","message":"The request of up to 1,200,150 cells is over the limit of max. 1,000,000 cells for this file format. Use B  <- data/FOLK1A/CSV?lang=en&OMR%C3%85DE=*&K%C3%98N=*&ALDER=*&CIVILSTAND=*&Tid=(1)
400 {"errorTypeCode":"EXTRACT-NOTALLOWED","message":"Values must be selected for variable: KØN"}  <- data/FOLK1A/BULK?lang=en&OMR%C3%85DE=000
BULK header: OMRÅDE;KØN;ALDER;CIVILSTAND;TID;INDHOLD
BULK rows: 129677
api.statbank.dk/robots.txt: HTTP 404 application/json; charset=utf-8
Source: Statistics Denmark, StatBank table FOLK1A, https://www.statbank.dk/FOLK1A, via https://api.statbank.dk/v1, accessed 25 November 2026 00:11 UTC.
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `/tables` | `[{id, text, unit, updated, firstPeriod, latestPeriod, active, variables}]` | 2,318 active tables, 5,765 with `includeinactive=true`; `pastdays=7` listed 111 on 2026-11-25, `pastdays=3` 50. `variables` are English labels (`"region"`, `"sex"`, `"time"`); there is no text search, so filter `text` yourself. FOLK1A: `2008Q1`..`2026Q4`; FOLK1AM (monthly, no marital status): `2021M10`..`2026M10` |
| `/tableinfo` | `{id, text, description, unit, suppressedDataValue, updated, active, contacts, documentation{id, url}, footnote, variables}` | FOLK1A: `"Number"`, `suppressedDataValue` `"0"`, `updated` `"2026-11-10T08:00:00"` (no zone), `active: true` |
| `/tableinfo` `variables[]` | `{id, text, elimination, time, values[{id, text}], map}` | `elimination: true` means you may leave it out and get the total; `Tid` is `elimination: false` but defaults to the newest period; `OMRÅDE` has `map: "denmark_municipality_07"` |
| `/data/.../JSONSTAT` | `{"dataset": {dimension, label, source, updated, value, extension}}` | JSON-stat 1.x layout: `dimension.id` `["OMRÅDE", "ContentsCode", "Tid"]`, `dimension.size`, `dimension.role` `{geo, metric, time}`; `updated` `"2026-11-10T07:00:00Z"`; `source` `"Statistics Denmark"`; `extension.px.infofile` is the documentation URL |
| `dataset.value` | flat list | in the order of `dimension.id`, last dimension fastest; within a dimension, by `category.index` |
| `dimension[V].category` | `{index: {code: position}, label: {code: English label}}` | `ContentsCode` also has `unit` `{"FOLK1A": {"base": "Number", "decimals": 0}}` |
| `/data/.../CSV` | `OMRÅDE;TID;INDHOLD` | semicolons, CRLF line ends, UTF-8 with a byte-order mark (`ef bb bf`), `text/csv; charset=utf-8`; `valuePresentation=Code`, `Value` (default text) or `CodeAndValue` (`000 All Denmark`, `2026K4 2026Q4`) |
| `/data/.../BULK` | `OMRÅDE;KØN;ALDER;CIVILSTAND;TID;INDHOLD` | every variable must be selected; CRLF line ends, no byte-order mark; 129,677 rows for 200,025 combinations of the newest quarter (rows equal to `suppressedDataValue` are not sent) |
| errors | `{"errorTypeCode", "message"}` | also in a `StatbankAPI-Error-<CODE>` header; HTTP 400 for `EXTRACT-NOTFOUND`, `EXTRACT-NOTALLOWED`, `REQUEST-MISSING`, `REQUEST-LIMIT`; HTTP 404 `REQUEST-NOTFOUND`; HTTP 500 `SYSTEM-100` (Danish only) |
| response headers | `content-type: text/json; charset=utf-8` (tableinfo, JSON-stat), `application/json` (errors), `cache-control: no-cache`, `StatbankAPI-Request-Id` | no `ETag`, `Last-Modified`, `Content-Encoding`, `Retry-After`, rate-limit headers or cookie; `Access-Control-Allow-Origin: *` |

## Gotchas

- **Codes are Danish, labels are English.** `OMRÅDE=Copenhagen` is HTTP 400 "Can't find value: Copenhagen (OMRÅDE)" (the code is `101`), and `Tid=2026Q4` fails the same way (the code is `2026K4`). Map labels to codes from `/tableinfo`, as blocks 1 and 3 do.
- **The ring in OMRÅDE matters, case does not.** `OMRADE` is HTTP 400 "Can't find variable"; `omrÅde` and `folk1a` work. Percent-encoding the `Å` (`OMR%C3%85DE`) is safest; a raw `Å` also got HTTP 200 in curl.
- **Encode the `+`.** `Tid=(-n+2)` arrives as `(-n 2)` and is HTTP 400; send `(-n%2B2)` (`urlencode` in blocks 1 and 3 does it), `(1),(2)` or `%3E%3D2026K2` (`>=2026K2`, the newest three).
- **Totals by leaving out.** Non-streaming formats eliminate any variable you leave out and return its total; BULK refuses with HTTP 400 `EXTRACT-NOTALLOWED` "Values must be selected for variable: KØN". Select `TOT`/`IALT` explicitly when you stream.
- **BULK leaves out rows.** The full newest quarter is 200,025 combinations; BULK sent 129,677 rows. `/tableinfo` says `suppressedDataValue: "0"`, and the help page's change log says that value "is to be used for missing row observations in streaming formats". Treat a missing row as 0 (the age sums in block 3 still matched the JSON-stat totals).
- **The cell count is an estimate.** `REQUEST-LIMIT` said "up to 1,200,150 cells" for 200,025 rows x 6 fields; the help page says the count is "The maximum number of rows to be extracted multiplied with the number of chosen fields where time and the observation value both are mandatory fields". Drop to BULK above 1,000,000.
- **Byte-order mark.** CSV starts with `ef bb bf`; decode with `utf-8-sig` or the first column is `﻿OMRÅDE`. Browser `fetch().text()` strips it for you.
- **`text/json`, not `application/json`.** Tableinfo, tables and JSON-stat answers are `text/json; charset=utf-8`; check for `json` in the content type, not an exact match.
- **Two `updated` stamps.** `/tableinfo` and `/tables` give `2026-11-10T08:00:00` with no zone; the JSON-stat `updated` is `2026-11-10T07:00:00Z`. Use the JSON-stat one when you need UTC.
- **Language.** `lang=en` or `lang=da` only; the default is Danish. `lang=sv` and `lang=de` are not a 400 but HTTP 500 `SYSTEM-100` "Der er opstået en fejl." Always send `lang=en`.
- **The first day of the quarter.** `2026Q4` is the population on 1 October 2026; `/tableinfo` gives `updated` 2026-11-10, so on 2026-11-25 the newest count was eight weeks old. FOLK1AM gives the first day of each month (newest `2026M10`) for region, sex and age.
- **No call-rate limit, no rate headers.** None is published and none came back. Keep calls serial and about a second apart; for GPTBot, www.dst.dk's robots.txt asks for `Crawl-delay: 10`.
- **Credit and no logo.** Give a source reference each time ("Source: Statistics Denmark, StatBank table FOLK1A", the quarter, a link to https://www.statbank.dk/FOLK1A and the access date), use no Statistics Denmark logo, and do not suggest an endorsement.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **Value labels as codes, `OMRADE` without the ring, a raw `+` in `(-n+2)`, `lang` other than `en`/`da`, a data URL without a format, an unknown table**: HTTP 400 (HTTP 500 `SYSTEM-100` for `lang=sv` and `lang=de`) with an `errorTypeCode` (blocks 2 and 4; `lang=de` in the verifier's check).
- **Every cell of FOLK1A's newest quarter as CSV or JSON-stat**: HTTP 400 `REQUEST-LIMIT` above 1,000,000 cells; BULK works.
- **BULK with a variable left out**: HTTP 400 `EXTRACT-NOTALLOWED`.
- **Conditional GETs and gzip**: no `ETag`, `Last-Modified` or `Content-Encoding`; compare `updated` instead.
- **Not tested:** a 429 or 503 (never seen), SDMX, PX, XLSX, HTML and PNG output, `sum(...)`/`subtract(...)` and percent calculations, saved queries, the CATALOGUE function (needs a key), `lang=da` beyond the default, and `/subjects` beyond one top-level call.
