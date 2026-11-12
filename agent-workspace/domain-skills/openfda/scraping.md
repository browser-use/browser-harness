# openFDA - List This Month's FDA Food Recalls That Mention Peanuts, with Firm, Product and Recall Class (public API, no key)

Field-tested against api.fda.gov on 2026-11-12 using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux machine. 16 browser page loads and 2 in-page `fetch()` attempts (both blocked by the API's CSP, see below), 36 curl calls and 4 urllib calls to api.fda.gov, all serial at 0.5 s or more spacing: every call was HTTP 200 except the 404 "no matches" answers and the deliberate 400/404 probes below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-12, curl and the cloud browser): https://api.fda.gov/robots.txt is HTTP 404 (`Cannot GET /robots.txt`), so nothing is disallowed for `*` or any agent. https://open.fda.gov/robots.txt (the docs host) is HTTP 403 (S3 AccessDenied), which RFC 9309 treats as "unavailable" (crawlers may access everything); the blocks never call that host. No named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider have no rules against them. Terms (https://open.fda.gov/terms/, every API answer links it in `meta.terms`): content and data are "public domain and made available with a Creative Commons CC0 1.0 Universal dedication. ... You can copy, modify, distribute, and perform the work, even for commercial purposes, all without asking permission." Attribution "While not required ... we ask that proper credit be given": "Data provided by the U.S. Food and Drug Administration (https://open.fda.gov)". "Right to Limit": FDA may restrict users who "attempted to exceed or circumvent these limits". The only AI clause covers GMDN medical-device nomenclature ("for AI training purposes, must first obtain an appropriate license from The GMDN Agency"), so this skill stays on the food and drug endpoints and never reads device data. The licence page adds: "When using or citing the work, you should not imply endorsement". No scraping, automated-access or non-commercial clause. Naming follows the FDA Name and Logo Policy (https://www.fda.gov/about-fda/website-policies/fda-name-and-logo-policy), which says the FDA Mark must not be used "To indicate or imply endorsement by the FDA" and that FDA is identified "only in ordinary text": "openFDA" names the data source only, in plain text, no FDA logo or seal, no endorsement wording. This skill is not affiliated with or endorsed by the U.S. Food and Drug Administration.

## Quick summary

- **No scraping.** `GET https://api.fda.gov/food/enforcement.json?search=report_date:[20261101 TO 20261130] AND peanut*&limit=1000` returns the month's food recall records that mention peanuts. Each record has `recalling_firm`, `product_description`, `classification` (`Class I`/`II`/`III`), `reason_for_recall`, `report_date`, `status`. No key, `Access-Control-Allow-Origin: *`.
- **Answer (2026-11-12, 18:32 ET):** November 2026 has **12 food recalls reported, none mention peanuts**. Only the 2026-11-04 Enforcement Report was loaded (`meta.last_updated` 2026-11-04). The most recent month with matches is October 2026: 5 of 117, all from El Ruisenor De Mexico, Inc. (Vernon, CA), report 2026-10-28, one recall event (99727): Special Red Almond Mole Powder and Homestyle Poblano Mole (Class I), Tropical Trail Mix (Class II), Butter Toffee Peanuts and Raw In-Shell Peanuts (Class III), all "undeclared allergen ingredient".
- **"Reported this month" = `report_date`**, the date FDA issued the weekly Enforcement Report. The API is "updated weekly" and lags: on 2026-11-12 it held nothing after the 2026-11-04 report. Block 1 prints `last_updated` and the report dates it found.
- **Use `peanut*`, not `peanut`.** No stemming: in 2026, `product_description:peanut` matched 12 records, `peanuts` 24, `peanut*` 33. A bare `peanut*` (any field) matched 47, exactly the 47 a local `/peanut/i` scan of all 1,142 records of 2026 found.
- **No match is HTTP 404** `{"error":{"code":"NOT_FOUND","message":"No matches found!"}}`, and so is a typo in a field name (`reason_for_recal:peanut`). The blocks prove the query shape with a non-empty baseline and cross-check the server search against a local scan of the whole month, so "none" is a real answer.
- **Brackets:** date ranges need `curl -g` (otherwise `curl: (3) bad range in URL`); in code, percent-encode the query.
- **Rate limit:** without a key, "240 requests per minute, per IP address. 1,000 requests per day, per IP address." (open.fda.gov/apis/authentication). No rate-limit headers. Blocks pace 0.5 s per call; block 1 makes 6 page loads.

## What works

### 1. This month's food recalls that mention peanuts, with firm, product and class (browser)

api.fda.gov sends `content-security-policy: default-src 'none'`, so `fetch()` inside an api.fda.gov tab fails (`TypeError: Failed to fetch`, `connect-src` violation). `get()` therefore loads each API URL as a page in one tab and reads the status from the navigation entry. It returns parsed JSON on 200, `None` on 404 NOT_FOUND, waits 30 s once on 429/5xx and otherwise raises. The block checks a 60-day baseline first, reads every record of the month, and refuses to answer if the server's `peanut*` search and a local scan of every text field disagree. If this month has no match it shows last month, labelled.

```python
import json, re, time, urllib.parse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TERM = "peanut"  # server: peanut* in any field; locally: /peanut/i in every text field (peanut, peanuts, Peanut Butter)

SITE = "https://api.fda.gov"
EP = SITE + "/food/enforcement.json"
PAUSE = 0.5  # no key: 240 requests/min and 1,000 requests/day per IP (open.fda.gov/apis/authentication); keep calls serial

def get(**params):
    """Load food/enforcement.json?params as a page in the tab -> parsed JSON, or None for openFDA's
    404 {"error":{"code":"NOT_FOUND","message":"No matches found!"}}. A mistyped field name gives the same 404,
    so callers prove the query shape with a non-empty baseline first. Waits 30 s once on 429/5xx, raises otherwise.
    In-page fetch() does not work here: api.fda.gov sends content-security-policy: default-src 'none'."""
    url = EP + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    for attempt in range(2):
        goto_url(url)
        wait_for_load()
        r = js("""(() => { const n = performance.getEntriesByType('navigation')[0] || {};
          const pre = document.querySelector('pre');
          return {origin: location.origin, status: n.responseStatus, type: n.contentType || '',
                  text: pre ? pre.textContent : (document.body ? document.body.innerText : '')}; })()""")
        time.sleep(PAUSE)
        if r["origin"] != SITE:
            raise RuntimeError(f"{url}: ended up on {r['origin']}; stop")
        if r["status"] == 200 and "json" in r["type"]:
            return json.loads(r["text"])
        if r["status"] == 404 and '"NOT_FOUND"' in r["text"]:
            return None
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")

def report_range(a, b):
    return f"report_date:[{a:%Y%m%d} TO {b:%Y%m%d}]"  # report_date = the weekly Enforcement Report the recall appeared in

def all_records(search):
    """Every record for a search, 1,000 per call (the max). skip tops out at 25,000; a full month in 2025-2026 was 67 to 273."""
    out, total = [], None
    while total is None or len(out) < total:
        d = get(search=search, limit=1000, skip=len(out))
        if d is None:
            break
        total = d["meta"]["results"]["total"]
        out += d["results"]
        if not d["results"]:
            break
    if total is not None and len(out) != total:
        raise RuntimeError(f"{search}: got {len(out)} of {total} records")
    return out

def mentions(rec):
    return [k for k, v in rec.items() if isinstance(v, str) and re.search(TERM, v, re.I)]

def recalls_mentioning(a, b):
    """-> (every record in the window, [(record, fields that mention TERM)]); the server search and a local scan must agree."""
    rng = report_range(a, b)
    month = all_records(rng)
    local = {r["recall_number"]: (r, mentions(r)) for r in month if mentions(r)}
    srv = all_records(f"{rng} AND {TERM}*")  # bare term = any field; * = prefix (peanut, peanuts); no stemming
    srv_ids = {r["recall_number"] for r in srv}
    if srv_ids != set(local):
        raise RuntimeError(f"server search and local scan disagree: only server {srv_ids - set(local)}, only local {set(local) - srv_ids}")
    hits = sorted(local.values(), key=lambda x: (x[0]["report_date"], x[0]["classification"], x[0]["recall_number"]))
    return month, hits

try:  # one working api.fda.gov tab; every API call below is a page load in it
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(EP + "?limit=1")
    wait_for_load()
today = datetime.now(ZoneInfo("America/New_York")).date()  # FDA's clock
first = today.replace(day=1)
last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)

# Baseline: a 60-day window must have records, which proves the field name and the date syntax (a typo is also a 404).
base = get(search=report_range(today - timedelta(days=60), today), limit=1)
if base is None or base["meta"]["results"]["total"] == 0:
    raise RuntimeError("no food recalls reported in the last 60 days: the query shape is wrong or the API changed; stop")
meta = base["meta"]
updated = date.fromisoformat(meta["last_updated"])
print(f"openFDA food/enforcement: last_updated {updated}, {base['meta']['results']['total']} recalls reported in the last 60 days")
print(f"  disclaimer: {meta['disclaimer'].split('. ')[0]}.")
if (today - updated).days > 8:
    print(f"  WARNING: data is {(today - updated).days} days old (updated weekly); later Enforcement Reports are missing")

month, hits = recalls_mentioning(first, last)
print(f"\n{first:%B %Y} ({report_range(first, last)}, today {today}): {len(month)} food recalls reported, {len(hits)} mention '{TERM}'")
print(f"  Enforcement Report dates loaded: {sorted({r['report_date'] for r in month}) or 'none yet'}")

def show(hits):
    for r, where in hits:
        print(f"  {r['report_date']}  {r['recall_number']:<12} {r['classification']:<9} {r['status']:<10} "
              f"{r['recalling_firm']} ({r['city']}, {r['state']})")
        print(f"      product: {' '.join(r['product_description'].split())[:110]}")
        print(f"      reason:  {' '.join(r['reason_for_recall'].split())[:110]}   [matched in {', '.join(where)}]")

show(hits)
if not hits:
    # Nothing yet this month: show the previous month, clearly labelled, so "none" is not mistaken for a broken query.
    pl = first - timedelta(days=1)
    pf = pl.replace(day=1)
    pmonth, phits = recalls_mentioning(pf, pl)
    print(f"\nfor context, {pf:%B %Y}: {len(pmonth)} food recalls reported, {len(phits)} mention '{TERM}'")
    show(phits)

print("\nData provided by the U.S. Food and Drug Administration (https://open.fda.gov), via the openFDA API; unvalidated, not medical advice.")
```

Output (from the run on 2026-11-12, 23:32 UTC):

```text
openFDA food/enforcement: last_updated 2026-11-04, 190 recalls reported in the last 60 days
  disclaimer: Do not rely on openFDA to make decisions regarding medical care.

November 2026 (report_date:[20261101 TO 20261130], today 2026-11-12): 12 food recalls reported, 0 mention 'peanut'
  Enforcement Report dates loaded: ['20261104']

for context, October 2026: 117 food recalls reported, 5 mention 'peanut'
  20261028  H-0141-2027  Class I   Ongoing    El Ruisenor De Mexico, Inc. (Vernon, CA)
      product: Special Red Almond Mole Powder; packaged in 1lb, 5lb, 11lb clear plastic units. No UPC
      reason:  undeclared allergen ingredient (Sesame, Peanuts, Wheat, Soy, Almonds, Walnuts, Yellow#5, Yellow#6, Red#40, Blu   [matched in reason_for_recall]
  20261028  H-0142-2027  Class I   Ongoing    El Ruisenor De Mexico, Inc. (Vernon, CA)
      product: Homestyle Poblano Mole; packaged in 1lb, 5lb, 22lb clear plastic units. No UPC
      reason:  undeclared allergen ingredient (Sesame, Peanuts, Wheat, Soy, Sulfites)   [matched in reason_for_recall]
  20261028  H-0157-2027  Class II  Ongoing    El Ruisenor De Mexico, Inc. (Vernon, CA)
      product: Tropical Trail Mix; packaged in 1lb, 5lb, 25lb clear plastic units. No UPC
      reason:  undeclared allergen ingredient (Peanuts, Almonds, Sulfites, Yellow#6)   [matched in reason_for_recall]
  20261028  H-0112-2027  Class III Ongoing    El Ruisenor De Mexico, Inc. (Vernon, CA)
      product: Butter Toffee Peanuts; packed in a clear plastic bag. 1lb, 5lb, 50lb unit size. No UPC
      reason:  undeclared allergen ingredient (Peanuts, Milk)   [matched in product_description, reason_for_recall]
  20261028  H-0113-2027  Class III Ongoing    El Ruisenor De Mexico, Inc. (Vernon, CA)
      product: Raw In-Shell Peanuts; packed in a clear plastic 1lb, 5lb, 50lb unit sizes. Raw Spanish Peanuts; sold by weight
      reason:  undeclared allergen ingredient (Peanuts)   [matched in product_description, reason_for_recall, code_info]

Data provided by the U.S. Food and Drug Administration (https://open.fda.gov), via the openFDA API; unvalidated, not medical advice.
```

### 2. robots.txt, search behaviour and error shapes (browser)

10 page loads in the same tab: robots.txt, four ways to spell the search, dashed dates, a count, and three deliberate errors.

```python
import json, time, urllib.parse

SITE = "https://api.fda.gov"
EP = SITE + "/food/enforcement.json"
YEAR = "report_date:[20260101 TO 20261130]"

def load(url):
    """One page load in the tab -> (HTTP status, content type, body text). No retries: this block only inspects answers."""
    goto_url(url)
    wait_for_load()
    r = js("""(() => { const n = performance.getEntriesByType('navigation')[0] || {}; const pre = document.querySelector('pre');
      return {origin: location.origin, status: n.responseStatus, type: n.contentType || '',
              text: pre ? pre.textContent : (document.body ? document.body.innerText : '')}; })()""")
    if r["origin"] != SITE:
        raise RuntimeError(f"{url}: ended up on {r['origin']}; stop")
    time.sleep(0.5)
    return r["status"], r["type"], r["text"]

def q(**params):
    return EP + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

def brief(text):
    try:
        d = json.loads(text)
    except ValueError:
        return " ".join(text.split())[:90]
    if "error" in d:
        return json.dumps(d["error"])
    if isinstance(d.get("results"), list) and d["results"] and "term" in d["results"][0]:
        return "counts " + json.dumps({x["term"]: x["count"] for x in d["results"]})
    return f"total {d['meta']['results']['total']}"

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(EP + "?limit=1")
    wait_for_load()

s, t, body = load(SITE + "/robots.txt")
print(f"robots.txt: HTTP {s} {t} {brief(body)!r}\n")

for label, url in (
    ("2026, product_description:peanut   ", q(search=f"{YEAR} AND product_description:peanut", limit=1)),
    ("2026, product_description:peanuts  ", q(search=f"{YEAR} AND product_description:peanuts", limit=1)),
    ("2026, product_description:peanut*  ", q(search=f"{YEAR} AND product_description:peanut*", limit=1)),
    ("2026, peanut* in any field         ", q(search=f"{YEAR} AND peanut*", limit=1)),
    ("Nov 2026, dashed dates             ", q(search="report_date:[2026-11-01 TO 2026-11-30]", limit=1)),
    ("Nov 2026, count by class           ", q(search="report_date:[20261101 TO 20261130]", count="classification.exact")),
    ("typo in field name                 ", q(search="reason_for_recal:peanut", limit=1)),
    ("limit=1001                         ", q(limit=1001)),
    ("skip=25001                         ", q(limit=1, skip=25001)),
):
    s, t, body = load(url)
    print(f"{label} HTTP {s} {brief(body)}")
```

Output (from the run on 2026-11-12, 23:32 UTC):

```text
robots.txt: HTTP 404 text/html 'Cannot GET /robots.txt'

2026, product_description:peanut    HTTP 200 total 12
2026, product_description:peanuts   HTTP 200 total 24
2026, product_description:peanut*   HTTP 200 total 33
2026, peanut* in any field          HTTP 200 total 47
Nov 2026, dashed dates              HTTP 200 total 12
Nov 2026, count by class            HTTP 200 counts {"Class I": 9, "Class II": 3}
typo in field name                  HTTP 404 {"code": "NOT_FOUND", "message": "No matches found!"}
limit=1001                          HTTP 400 {"code": "BAD_REQUEST", "message": "Limit cannot exceed 1000 results for search requests. Use the skip or search_after param to get additional results."}
skip=25001                          HTTP 400 {"code": "BAD_REQUEST", "message": "Skip value must 25000 or less."}
```

### 3. Same answer with Python urllib (no browser)

Python's default User-Agent got HTTP 200. Walks back from this month to the most recent month with a match.

```python
import json, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TERM = "peanut"
EP = "https://api.fda.gov/food/enforcement.json"

def get(**params):
    """-> parsed JSON, or None for 404 NOT_FOUND ("No matches found!"). Python's default User-Agent got HTTP 200."""
    url = EP + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)  # [ ] : and spaces percent-encoded
    time.sleep(0.5)  # no key: 240/min, 1,000/day per IP
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 404 and '"NOT_FOUND"' in body:
            return None
        sys.exit(f"HTTP {e.code} {' '.join(body.split())[:200]}")

def records(search):
    out = []
    while True:
        d = get(search=search, limit=1000, skip=len(out))
        if d is None:
            return out
        out += d["results"]
        if len(out) >= d["meta"]["results"]["total"] or not d["results"]:
            return out

def month_bounds(day):
    first = day.replace(day=1)
    return first, (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)

today = datetime.now(ZoneInfo("America/New_York")).date()
for a, b in (month_bounds(today), month_bounds(today.replace(day=1) - timedelta(days=1))):
    rng = f"report_date:[{a:%Y%m%d} TO {b:%Y%m%d}]"
    allr = records(rng)
    local = [r for r in allr if any(isinstance(v, str) and re.search(TERM, v, re.I) for v in r.values())]
    srv = records(f"{rng} AND {TERM}*")
    if {r["recall_number"] for r in srv} != {r["recall_number"] for r in local}:
        sys.exit(f"{rng}: server search ({len(srv)}) and local scan ({len(local)}) disagree")
    print(f"{a:%B %Y}: {len(allr)} food recalls reported, {len(local)} mention {TERM!r}")
    for r in sorted(local, key=lambda r: (r["classification"], r["recall_number"])):
        print(f"  {r['report_date']} {r['classification']:<9} {r['recalling_firm']} | {' '.join(r['product_description'].split())[:70]}")
    if local:
        break  # stop at the most recent month that has matches
    if not allr:
        print("  (no Enforcement Report loaded for this month yet)")
```

Output (from the run on 2026-11-12, 23:33 UTC):

```text
November 2026: 12 food recalls reported, 0 mention 'peanut'
October 2026: 117 food recalls reported, 5 mention 'peanut'
  20261028 Class I   El Ruisenor De Mexico, Inc. | Special Red Almond Mole Powder; packaged in 1lb, 5lb, 11lb clear plast
  20261028 Class I   El Ruisenor De Mexico, Inc. | Homestyle Poblano Mole; packaged in 1lb, 5lb, 22lb clear plastic units
  20261028 Class II  El Ruisenor De Mexico, Inc. | Tropical Trail Mix; packaged in 1lb, 5lb, 25lb clear plastic units. No
  20261028 Class III El Ruisenor De Mexico, Inc. | Butter Toffee Peanuts; packed in a clear plastic bag. 1lb, 5lb, 50lb u
  20261028 Class III El Ruisenor De Mexico, Inc. | Raw In-Shell Peanuts; packed in a clear plastic 1lb, 5lb, 50lb unit si
```

### 4. curl, headers and the drug endpoints

```bash
F=https://api.fda.gov/food/enforcement.json
# -g stops curl treating [ ] as a URL range; + is a space
curl -sSg --fail "$F?search=report_date:[20261001+TO+20261031]+AND+peanut*&count=classification.exact" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("Oct 2026 peanut recalls by class:", {r["term"]: r["count"] for r in d["results"]})'
sleep 1
curl -sSg -o /dev/null -w 'Nov 2026 peanut*: HTTP %{http_code} (404 = no matches)\n' "$F?search=report_date:[20261101+TO+20261130]+AND+peanut*"
sleep 1
curl -sS -o /dev/null "$F?search=report_date:[20261101+TO+20261130]" 2>&1 | head -1   # without -g
sleep 1
curl -sSg -D - -o /dev/null "$F?limit=1" | grep -iE '^(content-security-policy|access-control-allow-origin|x-ratelimit)'
sleep 1
# same search syntax on the drug endpoints
for ep in drug/enforcement drug/label drug/event; do
  case $ep in
    drug/enforcement) s='report_date:[20261001+TO+20261031]' ;;
    drug/label)       s='openfda.brand_name:"advil"' ;;
    drug/event)       s='receivedate:[20260101+TO+20261031]+AND+patient.drug.openfda.brand_name:"advil"' ;;
  esac
  curl -sSg "https://api.fda.gov/$ep.json?search=$s&limit=1" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('$ep:', 'total', d['meta']['results']['total'], 'last_updated', d['meta']['last_updated'])"
  sleep 1
done
```

Output (from the run on 2026-11-12, 23:33 UTC):

```text
Oct 2026 peanut recalls by class: {'Class I': 2, 'Class III': 2, 'Class II': 1}
Nov 2026 peanut*: HTTP 404 (404 = no matches)
curl: (3) bad range in URL position 63:
access-control-allow-origin: *
content-security-policy: default-src 'none'
drug/enforcement: total 75 last_updated 2026-11-04
drug/label: total 39 last_updated 2026-11-12
drug/event: total 10064 last_updated 2026-10-28
```

## Fields (food/enforcement)

Definitions quoted from https://open.fda.gov/fields/foodenforcement.yaml (read once while writing this skill).

| Field | Notes |
|---|---|
| `report_date` | `YYYYMMDD` string; "Date that the FDA issued the enforcement report for the product recall." Search accepts `20261101` or `2026-11-01` |
| `recall_number` | one per product (`H-0141-2027`); unique key |
| `event_id` | one per recall event; one event can cover many products (the 5 October peanut records are all event `99727`) |
| `classification` | `Class I`: "Dangerous or defective products that predictably could cause serious health problems or death" (examples include "food with undeclared allergens"); `Class II`: "might cause a temporary health problem, or pose only a slight threat of a serious nature"; `Class III`: "unlikely to cause any adverse health reaction, but that violate FDA labeling or manufacturing laws". Count with `count=classification.exact` |
| `status` | data says `Ongoing`, `Completed`, `Terminated`; the field docs spell it `On-Going` |
| `recalling_firm`, `city`, `state`, `country` | the firm and where it is located |
| `product_description`, `product_quantity`, `code_info` | free text; lots, UPCs, sizes |
| `reason_for_recall` | free text; allergen recalls list the allergens here (`undeclared allergen ingredient (Peanuts, Milk)`) |
| `recall_initiation_date`, `center_classification_date`, `termination_date` | `YYYYMMDD`; the October peanut recalls started 20260824, were classified 20261020 and reported 20261028 |
| `distribution_pattern`, `voluntary_mandated`, `initial_firm_notification` | free text |
| `openfda` | `{}` on every food record seen |
| `meta.last_updated`, `meta.results.total`, `meta.disclaimer` | load date, match count, "Do not rely on openFDA to make decisions regarding medical care" |

## Gotchas

- **Unvalidated data, not medical advice.** Every answer's `meta.disclaimer`: "Do not rely on openFDA to make decisions regarding medical care. While we make every effort to ensure that data is accurate, you should assume all results are unvalidated." Quote the class FDA assigned; do not re-rank it (two raw-peanut products with undeclared peanuts are Class III).
- **Weekly lag.** "The data is updated weekly" (food enforcement docs). On 2026-11-12 the newest `report_date` was 20261104 while `drug/label` said `last_updated` 2026-11-12: each endpoint has its own date. Always print `last_updated` with an empty answer.
- **404 means both "none" and "your query is wrong".** A misspelt field, a field that does not exist on this endpoint, or a real zero all return the same NOT_FOUND. Run a baseline without the term first.
- **Tokens, not substrings.** `peanut` misses "Peanuts"; `peanut*` catches both and "Peanut Butter". Quoted phrases work (`product_description:"peanut butter"` matched 10 in 2026). `+` or a space between terms is OR; use `AND` explicitly.
- **One firm, many rows.** October's 5 matches are one event at one firm. Group by `event_id` if the question is "how many recalls" rather than "how many products".
- **Paging.** `limit` max 1000 (`Limit cannot exceed 1000 results for search requests. Use the skip or search_after param to get additional results.`), `skip` max 25000 (`Skip value must 25000 or less.`). Every full month in 2025-2026 had 67 to 273 food recalls (fewest Nov 2025, most Jul 2025), so one call per month.
- **API key wording.** The authentication page opens with "An API key is required to make calls to the openFDA API" and then lists the no-key limits; keyless calls worked throughout. If you use a key, never print it; it goes in `api_key=`.
- **In-page `fetch()` is blocked** on api.fda.gov pages by `content-security-policy: default-src 'none'` (verified: `connect-src` violation). Load the API URL as the page instead, as blocks 1 and 2 do; CORS is open (`*`), so a fetch from another origin's page would also work.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **Device endpoints** (`/device/...`): not used. They carry GMDN content, which needs a GMDN Agency licence "for AI training purposes".
- **https://api.fda.gov/** itself: HTTP 404 `Cannot GET /`. Start the tab on an endpoint URL.
- **Dates without `-g` in curl:** `curl: (3) bad range in URL position 63`.
- **Not tested:** API keys, `search_after` and `sort=`, `food/event.json` (adverse events), field-specific searches on the drug endpoints beyond one call each, rate-limit behaviour (never provoked), Enforcement Reports newer than `last_updated` on fda.gov (www.fda.gov is not used by this skill).
