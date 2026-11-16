# Bank of Canada - Current Policy Interest Rate and the Latest USD/CAD Exchange Rate (official keyless Valet API)

Field-tested against www.bankofcanada.ca on 2026-11-14 (Saturday, 23:29-23:36 UTC) using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux server. 4 browser page loads and 14 in-page `fetch()` calls, about 56 curl calls (Valet API, OpenAPI spec, robots.txt, terms, how-to and rates pages) and 3 urllib calls, all serial at 1 s or more spacing: every call was HTTP 200 except the deliberate 400/404 probes below and the `http://` and bare-domain 301 redirects. No 429, no challenge, no key, no login, no cookie needed.

robots.txt (checked 2026-11-14, curl and the cloud browser): https://www.bankofcanada.ca/robots.txt is one group, `User-agent: *` with `Disallow: /wp-admin/` and `Allow: /wp-admin/admin-ajax.php`, plus a sitemap line. There are no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot, Bytespider, Applebot-Extended and Meta-ExternalAgent all follow `*`; curl with each of those 14 User-Agents got the same file, and Python's `urllib.robotparser` gives ALLOW for `/valet/observations/...`, `/valet/docs`, `/terms/` and `/core-functions/monetary-policy/key-interest-rate/` for all 14 and for `*`. Terms: every Valet response carries `"terms": {"url": "https://www.bankofcanada.ca/terms/"}`. That page says "the Bank permits you to freely use, copy, distribute and transmit its website content" on these terms: "You must attribute the Bank of Canada as the source of the content, and indicate if changes were made", "but not in any way that suggests that the Bank endorses you or your use of the content"; "You must exercise due diligence in ensuring the accuracy of any content you reproduce"; and if you provide it "through paid services or incorporate any content in documents for sale", you "must inform any prospective purchaser ... that such information is available on this website free of charge". Exceptions: bank note images need written permission, "The Bank's logo and wordmark may not be reproduced, whether for personal, commercial or non-commercial purposes, without written authorization", and third-party content is not licensed unless marked. You agree not to "Circumvent such limit or limits imposed by the Bank with respect to the number or frequency of requests made to a Bank Site, including ... the Bank of Canada Valet API", or to overburden the site. Exchange rates "are indicative rates only" and "are not intended to be used as the benchmark rate for executing foreign exchange trades". No AI/ML, scraping, automated-access or non-commercial clause (block 2 checks the quotes); the page's "Use of Artificial Intelligence" section is about the Bank's own staff ("we encourage employees to use AI in a responsible and ethical way"), not a limit on users. The Valet how-to guide (https://www.bankofcanada.ca/valet-api-how-to/): "No registration is required to use the Valet API. You do not need an access key." This skill names the source "Bank of Canada" in plain text, shows no logo, wordmark or bank-note image, prints the published values unchanged and labels its own calculations (the inverse check, the data age). It is not affiliated with or endorsed by the Bank of Canada.

## Quick summary

- **No scraping.** `GET https://www.bankofcanada.ca/valet/observations/V39079/json?recent=1` returns the target for the overnight rate (the policy interest rate) and `GET /valet/observations/FXUSDCAD/json?recent=1` the USD/CAD daily average rate. No key. Both series in one call: `/valet/observations/V39079,FXUSDCAD/json?recent=1`.
- **Answer (2026-11-14, 23:33 UTC):** **policy rate 2.50%** (latest daily value 2026-11-12; at 2.50% since 2026-10-29, after the October 28, 2026 decision, +0.25); next scheduled decision **December 9, 2026**. **USD/CAD 1.4257** Canadian dollars per US dollar on 2026-11-13 (Friday; no rate on weekends).
- **When did it change:** `B114039` is the same target with one row per change, dated the day it took effect (`2026-10-29 2.50`, `2025-10-30 2.25`). "As of 2021, a change takes effect the day after its announcement" (the policy rate page), so the announcement date is one day earlier.
- **Next decision date** is not in the API spec. The "Policy interest rate" page (https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/) has the decisions table (`#target-table`) and "Schedule for 2026" / "Schedule for 2027" tables; block 1 reads them.
- **FX timing:** "The daily average exchange rates are published once each business day by 16:30 ET" (daily exchange rates page). None on weekends or bank holidays (2026-11-11 was a "Bank holiday").
- **Rate limit:** no number is published (the OpenAPI spec defines no 429). The terms forbid circumventing Valet request limits; the how-to guide says "Start slow", "If a request fails, wait before trying again" and, for exchange rates, "store the response instead of calling the API again". Blocks pace 1 s per call, serial, and wait 60 s once on 429/500/502/503/504.

## What works

### 1. Policy rate, last change, next decision and USD/CAD (browser)

`on_boc_tab()` opens the logged-out "Policy interest rate" page once; the Valet `fetch()` calls run from that tab (same origin; Valet also allows any origin, block 2). `get()` returns parsed JSON on 200, waits 60 s once on 429/500/502/503/504 and otherwise raises, so an error never looks like "no data".

```python
import json, re, time
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SITE = "https://www.bankofcanada.ca"
VALET = SITE + "/valet"
PAGE = SITE + "/core-functions/monetary-policy/key-interest-rate/"  # "Policy interest rate": decisions table + schedule
PAUSE = 1.0  # terms: do not "Circumvent such limit or limits ... (e.g., the Bank of Canada Valet API)"; how-to: "Start slow"

def on_boc_tab():
    """Open the logged-out "Policy interest rate" page once and reuse it. Valet fetch() calls run from this tab
    (same origin; Valet also sends Access-Control-Allow-Origin: *)."""
    try:
        if js("location.href").startswith(PAGE):
            return
    except Exception:
        pass
    new_tab(PAGE)
    wait_for_load()
    if not js("location.href").startswith(PAGE) or not js("!!document.querySelector('#target-table')"):
        raise RuntimeError(f"policy rate page did not load as expected (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__boc = window.__boc || {}; const id = String(Math.random()).slice(2); window.__boc[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { window.__boc[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__boc[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__boc[%s]; if (v) delete window.__boc[%s]; return v; })()"""

def get(path, timeout=60):
    """GET VALET+path from inside the tab -> parsed JSON. 400/404 bodies are {"message": ..., "docs": ...} and raise.
    Waits 60 s once on 429/500/502/503/504 or a network error (how-to: "If a request fails, wait before trying again")."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(VALET + path)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        if r["status"] != 200 or "json" not in (r["type"] or ""):
            raise RuntimeError(f"{path}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
        return json.loads(r["text"])
    raise RuntimeError(f"{path}: still failing after one retry: stop")

def observations(series, n):
    """Latest n observations of one series, newest first, as [(date, float)]. Sorted here: Valet's default order
    differs between recent= (newest first) and start_date= (oldest first)."""
    d = get(f"/observations/{series}/json?recent={n}")
    if series not in d.get("seriesDetail", {}):
        raise RuntimeError(f"{series}: not in seriesDetail {list(d.get('seriesDetail', {}))}: stop")
    rows = [(o["d"], float(o[series]["v"])) for o in d["observations"] if series in o and o[series].get("v") not in (None, "")]
    if not rows:
        raise RuntimeError(f"{series}: no observations: stop")
    return sorted(rows, reverse=True), d["seriesDetail"][series]

def ottawa_date(t):
    """t as a Bank of Canada (Ottawa, Eastern Time) calendar day. The schedule, the decisions table and Valet rows
    use these days: compared with the UTC date, from 00:00 UTC until midnight ET a decision dated "tomorrow" in
    Ottawa looks past."""
    try:
        return t.astimezone(ZoneInfo("America/Toronto")).date()
    except ZoneInfoNotFoundError:
        raise RuntimeError("no time zone data for America/Toronto (e.g. Windows): pip install tzdata, then re-run") from None

on_boc_tab()
now = datetime.now(timezone.utc)
today = ottawa_date(now)
print(f"now {now:%Y-%m-%d %H:%M} UTC = {today} {today:%A} in Ottawa (ET)")

# 1. Policy rate. V39079 = "Target for the overnight rate (business daily)": one row per business day.
#    B114039 = the same target, one row per change, dated the day it took effect.
daily, meta = observations("V39079", 5)
changes, _ = observations("B114039", 2)
rate_day, rate = daily[0]
since, level = changes[0]
print(f"\nV39079 {meta['label']} ({meta['metadata']['unit']}): " + ", ".join(f"{d} {v:.2f}" for d, v in daily))
print(f"B114039 last changes: " + ", ".join(f"{d} {v:.2f}" for d, v in changes))
if abs(level - rate) > 1e-9:
    print(f"  NOTE: latest change level {level:.2f} != latest daily value {rate:.2f}: a new decision may not be in V39079 yet")

# 2. The decisions table and schedule on the page (the API has no announcement calendar).
page = js("""(() => {
  const rows = [...document.querySelectorAll('#target-table tbody tr')].map(tr =>
    [tr.querySelector('th')?.dataset.date, ...[...tr.querySelectorAll('td')].map(td => td.innerText.trim())]);
  const sched = [...document.querySelectorAll('table')].filter(t => /Schedule for \\d{4}/.test(t.caption?.innerText || ''))
    .map(t => [t.caption.innerText.trim().slice(-4), [...t.querySelectorAll('tbody tr td:first-child')].map(td => td.innerText.replace(/\\s+/g, ' ').trim())]);
  return {rows, sched};
})()""")
if not page["rows"] or not page["sched"]:
    raise RuntimeError(f"policy rate page layout changed (rows={page['rows']}, schedules={len(page['sched'])}): re-read {PAGE}")
print("\npage: latest decisions " + "; ".join(f"{d} target {t}% change {c}" for d, t, c in page["rows"][:3]))
# "---" = held; "+0.25" / "-0.25" = changed. Take the latest change TO the current level, so a decision that is
# announced but not yet in effect (B114039 still shows the old level) is not credited to the old level.
moved = [r for r in page["rows"] if r[2].strip("-") and abs(float(r[1]) - level) < 1e-9]
if not moved:
    raise RuntimeError(f"no change to {level:.2f}% in the page's {len(page['rows'])} listed decisions: read B114039 history instead")
announce = date.fromisoformat(moved[0][0])
if float(page["rows"][0][1]) != level:
    print(f"  NOTE: page target {page['rows'][0][1]} != B114039 {level:.2f}")
upcoming = []
for year, days in page["sched"]:
    for s in days:
        upcoming.append(datetime.strptime(f"{s} {year}", "%B %d %Y").date())
# A decision dated today (ET) stays "next" until the decisions table lists it.
listed = {r[0] for r in page["rows"]}
nxt = min((d for d in upcoming if d > today or (d == today and d.isoformat() not in listed)), default=None)
print(f"page: {len(upcoming)} scheduled announcement dates; next not yet announced: {nxt}")

# 3. USD/CAD daily average rate.
fx, fxmeta = observations("FXUSDCAD", 5)
fx_day, usdcad = fx[0]
print(f"\nFXUSDCAD {fxmeta['label']} ({fxmeta['metadata']['unit']}, {fxmeta['metadata']['frequency']}): "
      + ", ".join(f"{d} {v:.4f}" for d, v in fx))
inv, _ = observations("FXCADUSD", 1)
print(f"FXCADUSD (the Bank's own inverse): {inv[0][0]} {inv[0][1]:.4f}; 1/{usdcad} = {1 / usdcad:.4f}")

age = (today - date.fromisoformat(fx_day)).days
def long_date(d):
    return f"{d:%B} {d.day}, {d.year}"  # "December 9, 2026" (strftime %-d is not portable)

nxt_txt = f"next scheduled decision {long_date(nxt)}" if nxt else "next decision date not found on the page"
print(f"\nanswer: Bank of Canada policy interest rate (target for the overnight rate) {rate:.2f}% "
      f"(latest daily value {rate_day}; at this level since {since}, announced {long_date(announce)}); {nxt_txt}.")
print(f"        USD/CAD {usdcad:.4f} CAD per USD on {fx_day} (Bank of Canada daily average, published by 16:30 ET; {age} day(s) old).")
print("  Source: Bank of Canada (Valet API and bankofcanada.ca), https://www.bankofcanada.ca/terms/. "
      "Indicative rate, not a trading rate. Unchanged values; the inverse and age are our calculation.")
```

Output (re-run on 2026-11-15, 00:37 UTC, after the Eastern Time fix; past midnight UTC but still 2026-11-14 in Ottawa. The values on every line below the first match the first run, 2026-11-14 23:33 UTC; only the `page:` line's label changed, from `next after today` to `next not yet announced`):

```text
now 2026-11-15 00:37 UTC = 2026-11-14 Saturday in Ottawa (ET)

V39079 Target for the overnight rate (business daily) (Percent): 2026-11-12 2.50, 2026-11-11 2.50, 2026-11-10 2.50, 2026-11-09 2.50, 2026-11-06 2.50
B114039 last changes: 2026-10-29 2.50, 2025-10-30 2.25

page: latest decisions 2026-10-28 target 2.50% change +0.25; 2026-09-02 target 2.25% change ---; 2026-07-15 target 2.25% change ---
page: 16 scheduled announcement dates; next not yet announced: 2026-12-09

FXUSDCAD USD/CAD (Canadian dollars per US dollar, Business daily): 2026-11-13 1.4257, 2026-11-12 1.4255, 2026-11-10 1.4181, 2026-11-09 1.4123, 2026-11-06 1.4113
FXCADUSD (the Bank's own inverse): 2026-11-13 0.7014; 1/1.4257 = 0.7014

answer: Bank of Canada policy interest rate (target for the overnight rate) 2.50% (latest daily value 2026-11-12; at this level since 2026-10-29, announced October 28, 2026); next scheduled decision December 9, 2026.
        USD/CAD 1.4257 CAD per USD on 2026-11-13 (Bank of Canada daily average, published by 16:30 ET; 1 day(s) old).
  Source: Bank of Canada (Valet API and bankofcanada.ca), https://www.bankofcanada.ca/terms/. Indicative rate, not a trading rate. Unchanged values; the inverse and age are our calculation.
```

### 2. robots.txt, the terms and error shapes (browser)

Reads robots.txt and six clauses of the terms page, makes 9 Valet calls from the bankofcanada.ca tab (mostly deliberate errors), then one from example.com to show that cross-origin reads work.

```python
import json, time

SITE = "https://www.bankofcanada.ca"

# robots.txt, as the browser sees it. Reuse block 1's tab if it is open.
try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
(goto_url if on_site else new_tab)(SITE + "/robots.txt")
wait_for_load()
print("robots.txt: " + " | ".join(l for l in (js("document.body.innerText") or "").splitlines() if l.strip()) + "\n")

# The terms page every Valet response links to ("terms": {"url": "https://www.bankofcanada.ca/terms/"}).
goto_url(SITE + "/terms/")
wait_for_load()
text = " ".join((js("document.body.innerText") or "").split())
for q in ("the Bank permits you to freely use, copy, distribute and transmit", "You must attribute the Bank of Canada",
          "If You provide content from this website through paid services", "logo and wordmark may not be reproduced",
          "Circumvent such limit or limits", "Bank of Canada exchange rates are released for statistical"):
    i = text.find(q)
    if i < 0:
        raise RuntimeError(f"terms page changed, {q!r} not found: re-read {SITE}/terms/ before relying on this skill")
    end = text.find(". ", i + len(q))
    print(f"terms: {text[i:end + 1 if end > 0 else i + 240][:300]}")

START_JS = """(() => { window.__boc = window.__boc || {}; const id = String(Math.random()).slice(2); window.__boc[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__boc[id] = {status: r.status, type: r.headers.get('content-type'), acao: r.headers.get('access-control-allow-origin'), text: await r.text()}; })
    .catch(e => { window.__boc[id] = {status: 0, type: '', acao: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__boc[%s]; if (v) delete window.__boc[%s]; return v; })()"""

def raw(url, timeout=60):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{url}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r["status"], r["type"], r["acao"], " ".join(r["text"].split())

# Valet probes from the bankofcanada.ca tab. No retries: this block only inspects answers.
if js("location.origin") != SITE:
    raise RuntimeError(f"not on {SITE} (at {js('location.href')}): stop")
print()
V = SITE + "/valet"
for path in ("/observations/NOPE123/json?recent=1",                         # unknown series
             "/observations/FXUSDCAD/json?recent=1&start_date=2026-11-01",  # recent + date range
             "/observations/FXUSDCAD/json?start_date=2026-13-01",           # bad date
             "/observations/FXUSDCAD/json?recent=0",
             "/observations/FXUSDCAD/xyz?recent=1",                         # bad format
             "/observations/fxusdcad/json?recent=1",                        # lower case name
             "/observations/FXUSDCAD/json?start_date=2026-11-14",           # Saturday: no rows yet
             "/observations/FXUSDCAD/json?start_date=2026-11-09&end_date=2026-11-13",  # 11-11 is a bank holiday
             "/observations/V39079,FXUSDCAD/json?recent=1"):                # two series: each its own latest date
    s, ct, acao, body = raw(V + path)
    if s == 200 and body.startswith("{"):
        d = json.loads(body)
        body = f"{len(d['observations'])} obs {[(o['d'], {k: v['v'] for k, v in o.items() if k != 'd'}) for o in d['observations']]}"
    print(f"{path}: HTTP {s} ACAO={acao} {body[:150]}")

# The same call from another site's page: Valet sends Access-Control-Allow-Origin: *, so it works.
goto_url("https://example.com/")
wait_for_load()
s, ct, acao, body = raw(V + "/observations/FXUSDCAD/json?recent=1")
print(f"\nfrom {js('location.origin')}: HTTP {s} ACAO={acao} {json.loads(body)['observations'] if s == 200 else body[:80]}")
```

Output (from the run on 2026-11-14, 23:34 UTC):

```text
robots.txt: User-agent: * | Disallow: /wp-admin/ | Allow: /wp-admin/admin-ajax.php | Sitemap: https://www.bankofcanada.ca/wp-sitemap.xml

terms: the Bank permits you to freely use, copy, distribute and transmit its website content under the following terms: 1.1.
terms: You must attribute the Bank of Canada as the source of the content, and indicate if changes were made.
terms: If You provide content from this website through paid services or incorporate any content in documents for sale (regardless of the medium), You must inform any prospective purchaser, prior to its distribution or sale, that said content was obtained from this website and that such information is avai
terms: logo and wordmark may not be reproduced, whether for personal, commercial or non-commercial purposes, without written authorization from the Bank.
terms: Circumvent such limit or limits imposed by the Bank with respect to the number or frequency of requests made to a Bank Site, including the retrieval of financial data and information using Bank of Canada services (e.g., the Bank of Canada Valet API).
terms: Bank of Canada exchange rates are released for statistical and analytical purposes only and are not intended to be used as the benchmark rate for executing foreign exchange trades.

/observations/NOPE123/json?recent=1: HTTP 404 ACAO=* { "message": "Series NOPE123 not found.", "docs": "https://www.bankofcanada.ca/valet/docs#/Series/get_observations__seriesNames___format_" }
/observations/FXUSDCAD/json?recent=1&start_date=2026-11-01: HTTP 400 ACAO=* { "message": "Bad recent observations request parameters, you can not mix start_date or end_date with any of recent, recent_weeks, recent_months, rece
/observations/FXUSDCAD/json?start_date=2026-13-01: HTTP 400 ACAO=* { "message": "Start date contains a value that is not allowed. Expected format is YYYY-MM-DD, e.g. 2001-01-27", "docs": "https://www.bankofcanada.ca/v
/observations/FXUSDCAD/json?recent=0: HTTP 400 ACAO=* { "message": "Bad recent observations request parameters, you cannot have a recent value less than one", "docs": "https://www.bankofcanada.ca/valet/do
/observations/FXUSDCAD/xyz?recent=1: HTTP 400 ACAO=* { "message": "Bad output format (xyz) requested.", "docs": "https://www.bankofcanada.ca/valet/docs#/Series/get_observations__seriesNames___format_" }
/observations/fxusdcad/json?recent=1: HTTP 200 ACAO=* 1 obs [('2026-11-13', {'FXUSDCAD': '1.4257'})]
/observations/FXUSDCAD/json?start_date=2026-11-14: HTTP 200 ACAO=* 0 obs []
/observations/FXUSDCAD/json?start_date=2026-11-09&end_date=2026-11-13: HTTP 200 ACAO=* 4 obs [('2026-11-09', {'FXUSDCAD': '1.4123'}), ('2026-11-10', {'FXUSDCAD': '1.4181'}), ('2026-11-12', {'FXUSDCAD': '1.4255'}), ('2026-11-13', {'FXUSDC
/observations/V39079,FXUSDCAD/json?recent=1: HTTP 200 ACAO=* 2 obs [('2026-11-12', {'V39079': '2.50'}), ('2026-11-13', {'FXUSDCAD': '1.4257'})]

from https://example.com: HTTP 200 ACAO=None [{'d': '2026-11-13', 'FXUSDCAD': {'v': '1.4257'}}]
```

`ACAO=None` on the last line is the browser hiding a header that is not CORS-safelisted from cross-origin code; the call succeeded, and curl shows `Access-Control-Allow-Origin: *` (block 4).

### 3. Same answer with Python urllib (no browser)

```python
import json, sys, time, urllib.error, urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VALET = "https://www.bankofcanada.ca/valet"
UA = {"User-Agent": "boc-rates-example/1.0", "Accept": "application/json"}

def get(path):
    """GET -> parsed JSON. Waits 60 s once on HTTP 429/500/502/503/504 or a network error (how-to: "wait before
    trying again")."""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(VALET + path, headers=UA), timeout=60) as r:
                body = r.read()
                time.sleep(1)  # serial and slow: the terms forbid circumventing Valet request limits
                return json.loads(body)  # an empty or cut body fails loudly
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{path}: HTTP {e.code} {e.read().decode()[:160]}")  # 400/404 {"message": "...", "docs": "..."}
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{path}: {e}")
    sys.exit(f"{path}: still failing after one retry")

def latest(series):
    obs = [o for o in get(f"/observations/{series}/json?recent=1")["observations"] if o.get(series, {}).get("v")]
    if not obs:
        sys.exit(f"{series}: no observation")
    return obs[0]["d"], obs[0][series]["v"]  # v is a string: keep it as published ("2.50", "1.4257")

rate_day, rate = latest("V39079")    # target for the overnight rate, business daily
since, level = latest("B114039")     # same target, one row per change (effective date)
fx_day, usdcad = latest("FXUSDCAD")  # USD/CAD daily average, CAD per USD
if level != rate:
    print(f"NOTE: last change says {level}%, daily series says {rate}% (a new decision may not be in V39079 yet)")
try:
    ottawa_today = datetime.now(ZoneInfo("America/Toronto")).date()  # Valet dates are Ottawa (ET) days
except ZoneInfoNotFoundError:
    sys.exit("no time zone data for America/Toronto (e.g. Windows): pip install tzdata, then re-run")
age = (ottawa_today - date.fromisoformat(fx_day)).days
print(f"policy rate {rate}% (daily value {rate_day}, at this level since {since})")
print(f"USD/CAD {usdcad} on {fx_day} ({age} day(s) old)")
print("Source: Bank of Canada, https://www.bankofcanada.ca/terms/ (indicative exchange rate, not for trading).")
```

Output (from the run on 2026-11-14, 23:34 UTC):

```text
policy rate 2.50% (daily value 2026-11-12, at this level since 2026-10-29)
USD/CAD 1.4257 on 2026-11-13 (1 day(s) old)
Source: Bank of Canada, https://www.bankofcanada.ca/terms/ (indicative exchange rate, not for trading).
```

### 4. curl

```bash
V=https://www.bankofcanada.ca/valet
UA='boc-rates-example/1.0'
R='--max-time 60 --retry 1 --retry-delay 60'  # one retry after 60 s on a timeout or HTTP 408/429/500/502/503/504
curl -sS --fail $R -A "$UA" "$V/observations/V39079,B114039,FXUSDCAD/json?recent=1" | python3 -c '
import json, sys
for o in json.load(sys.stdin)["observations"]:
    print(o["d"], {k: v["v"] for k, v in o.items() if k != "d"})
'
sleep 1
curl -sS --fail $R -A "$UA" "$V/observations/FXUSDCAD/csv?recent=2"; echo   # CSV: terms + series header, then oldest first
sleep 1
curl -sS -D - -o /dev/null -A "$UA" "$V/observations/FXUSDCAD/json?recent=1" | grep -iE '^(content-type|cache-control|access-control-allow-origin):'
sleep 1
curl -sS -o /dev/null -A "$UA" -w 'unknown series (NOPE123): HTTP %{http_code}\n' "$V/observations/NOPE123/json?recent=1"
```

Output (from the run on 2026-11-14, 23:35 UTC):

```text
2026-11-12 {'V39079': '2.50'}
2026-10-29 {'B114039': '2.50'}
2026-11-13 {'FXUSDCAD': '1.4257'}
﻿"TERMS AND CONDITIONS"
"https://www.bankofcanada.ca/terms/"

"SERIES"
"id","label","description","date_format"
"FXUSDCAD","USD/CAD","Daily average exchange rate of the US dollar in Canadian dollars.","daily"

"OBSERVATIONS"
"date","FXUSDCAD"
"2026-11-12","1.4255"
"2026-11-13","1.4257"

Access-Control-Allow-Origin: *
Content-Type: application/json; charset=utf-8
Cache-Control: max-age=30
unknown series (NOPE123): HTTP 404
```

## Fields

From the responses above and the OpenAPI 3.0.3 spec behind https://www.bankofcanada.ca/valet/docs (https://www.bankofcanada.ca/valet/static/swagger/api-en.yml, read once while writing this skill).

| Field / series | Where | Notes |
|---|---|---|
| `V39079` | series | "Target for the overnight rate (business daily)", unit `Percent`: one row per business day |
| `B114039` | series | "Target for the overnight rate", one row per change, dated the day it took effect |
| `FXUSDCAD` | series | "USD/CAD", "Daily average exchange rate of the US dollar in Canadian dollars", unit "Canadian dollars per US dollar", "Business daily" |
| `FXCADUSD` | series | the inverse (US dollars per Canadian dollar), published by the Bank: `0.7014` on 2026-11-13 |
| `FX_RATES_DAILY` | group | all daily rates: `/valet/observations/group/FX_RATES_DAILY/json?recent=1` (15 KB) |
| `terms.url` | every response | `https://www.bankofcanada.ca/terms/` |
| `seriesDetail.<name>` | observations | `label`, `description`, `dimension` (`{"key": "d", "name": "Date"}`), `dateFormat`, `metadata.unit`, `metadata.frequency` |
| `observations[]` | observations | `{"d": "2026-11-13", "FXUSDCAD": {"v": "1.4257"}}`; `v` is a string, keep it as published |
| `recent`, `recent_weeks`, `recent_months`, `recent_years` | query | integer, minimum 1; cannot be combined with `start_date` / `end_date` (HTTP 400) |
| `start_date`, `end_date`, `order_dir` | query | `YYYY-MM-DD`; `order_dir` `asc` or `desc` |
| `{format}` | path | `json` (default when omitted), `csv`, `xml` |

Also from the `/valet/series/V39079/json` route: `"metadata": {"frequency":"Business daily","unit":"Percent","unit_symbol":"%"}`. Series names: `/valet/lists/series/json` (3.7 MB, 16,380 series on 2026-11-14); groups: `/valet/lists/groups/json` (1.3 MB). Fetch those once and cache them.

## Gotchas

- **The daily policy-rate series lags.** At 23:33 UTC on Saturday 2026-11-14 the newest `V39079` row was Thursday 2026-11-12, while `FXUSDCAD` already had Friday 2026-11-13. Report its value, not its date, as "the rate right now", and take the effective date from `B114039`. If a decision is new, `B114039` and `V39079` may briefly disagree; blocks 1 and 3 print a NOTE then.
- **Effective date vs announcement date.** `B114039` says `2026-10-29`; the page's decisions table says `October 28, 2026` (`data-date="2026-10-28"`). Both are right: the change took effect the day after the announcement.
- **"Held" decisions are rows too.** The page lists every fixed announcement date, with `---` when the rate did not move. Block 1 takes the latest row with a `+`/`-` change whose target equals the current `B114039` level, so a decision announced but not yet in effect is not credited to the old level.
- **Dates are Ottawa days.** The schedule, the decisions table and Valet `d` values are Eastern Time calendar days; blocks 1 and 3 compare them with `datetime.now(ZoneInfo("America/Toronto")).date()`, not the UTC date, which runs a day ahead from 00:00 UTC until midnight ET. `zoneinfo` reads the system time zone database; the Python docs recommend the `tzdata` package where none is available, notably on Windows. Without either, blocks 1 and 3 stop with "pip install tzdata" instead of guessing the offset.
- **Holidays differ by series.** 2026-11-11 is a "Bank holiday" on the daily exchange rates page and has no `FXUSDCAD` row, but `V39079` has a 2026-11-11 row (2.50). `recent=N` counts observations, not days.
- **Default sort order changes.** `recent=` on one series returned newest first (with several series, rows come grouped by series: `V39079,FXUSDCAD` `recent=3` gave 11-12, 11-11, 11-10, then 11-13); `start_date=` returned oldest first (2024-01-02 first); CSV came oldest first. Sort by `d` yourself or pass `order_dir`.
- **Several series, several dates.** `/observations/V39079,FXUSDCAD/json?recent=1` returns two observation objects, `2026-11-12` with only `V39079` and `2026-11-13` with only `FXUSDCAD`. Read each series' own latest row.
- **Empty is HTTP 200.** `start_date=2026-11-14` (a Saturday) returns `"observations": []`. Check for an empty list.
- **Errors are JSON.** `{"message": "...", "docs": "..."}`: 404 `"Series NOPE123 not found."`, 400 `"Bad recent observations request parameters, you can not mix start_date or end_date with any of recent, ..."`, 400 `"Start date contains a value that is not allowed. Expected format is YYYY-MM-DD, e.g. 2001-01-27"`, 400 `"... you cannot have a recent value less than one"`, 400 `"Bad output format (xyz) requested."`.
- **Lower case works.** `fxusdcad` returned the same as `FXUSDCAD`. Omitting `/json` also returns JSON.
- **Indicative, not a trading rate.** The terms: Bank of Canada exchange rates "are released for statistical and analytical purposes only and are not intended to be used as the benchmark rate for executing foreign exchange trades". Say so with the answer.
- **Processing delay.** The spec: "there may be a brief processing delay between when data is published and when it appears in the API. If you don't see data immediately, check back later in the day." So a call on a business day before 16:30 ET can still return the previous business day's rate (inferred from the publishing time; this run was on a Saturday).
- **CSV starts with a BOM** (U+FEFF, invisible in the output above) and a `"TERMS AND CONDITIONS"` and `"SERIES"` header before `"OBSERVATIONS"`; parse from the `"date",...` line.
- **Hosts.** `http://` and `https://bankofcanada.ca/` answer 301 to `https://www.bankofcanada.ca/`; the French host `https://www.banqueducanada.ca/valet/` also answered 200.
- **Caching and CORS.** `Cache-Control: max-age=30`, `Access-Control-Allow-Origin: *`. A `fetch()` from example.com worked.
- **User-Agent.** A custom one, an empty one and `Python-urllib/3.12` all got HTTP 200 from curl.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.href`, the DOM and the JSON, not the title.

## What does not work

- **The next decision date from Valet:** the spec's routes are lists, series, groups, observations, observations by group, `fx_rss` and search; none is an announcement calendar. Read the date from the policy rate page (block 1).
- **Mixing `recent` with `start_date`/`end_date`:** HTTP 400 (see Gotchas).
- **Not tested:** XML output, `recent_weeks`/`recent_months`/`recent_years`, the RSS exchange-rate routes, the search routes, other groups (CPI, bond yields), the `B114039` behaviour on a decision day, and rate-limit behaviour (never provoked).
