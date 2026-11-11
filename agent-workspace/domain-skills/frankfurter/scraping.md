# Frankfurter - Convert Currency at Today's ECB Euro Reference Rate (official API, ECB provider route)

Field-tested against api.frankfurter.dev on 2026-11-11 using two fresh Browser Use cloud browsers (logged out) plus Python urllib and `curl` from a laptop. About 16 browser page loads and 44 in-page `fetch()` calls, about 27 curl calls and 4 urllib calls, all serial at 1 s or more spacing: every call was HTTP 200 except the deliberate 404/422 probes below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-11, curl and the cloud browser): https://api.frankfurter.dev/robots.txt is `User-agent: *` / `Allow: /`; https://frankfurter.dev/robots.txt is `User-agent: *` / `Allow: /` / `Allow: /llms.txt`; https://www.ecb.europa.eu/robots.txt has one `User-agent: *` group with `Crawl-delay: 5` that disallows only `*_content.<lang>.html`, video, `/paym/coll/assets/html/dla/EA/` and `/euro/changeover/shared/data/` paths, not `/stats/`. No named AI-agent groups on any of the three, so GPTBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot and CCBot fall to `*` (allowed). Terms: the Frankfurter FAQ says "Is the API free for commercial use? Yes. Blended rates are Frankfurter's own calculation and free to use. Direct queries to individual provider endpoints remain subject to each provider's terms." and "There are no quotas. Requests are rate-limited to prevent abuse"; frankfurter.dev/license: code MIT, "If a provider publishes terms of use, they apply." The ECB's terms (https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html, the `terms_url` the API gives for ECB): users "may make free use of the information obtained directly from it" provided it appears accurately and "the ECB must be cited as the source"; "If the information is modified by the user (e.g. ... calculation of growth rates) this must be stated explicitly." No AI/ML, scraping, automated-access or non-commercial clause. This skill reads only the ECB provider route and the ECB's own page and feed, cites the ECB, and says that the converted amount is a calculation.

## Quick summary

- **No scraping.** `GET https://api.frankfurter.dev/v2/providers/ecb/rate/EUR/USD` returns `{"date":"2026-11-11","base":"EUR","quote":"USD","rate":1.1127}`: the ECB's euro reference rate. 250 USD = 250 / 1.1127 = **224.68 EUR** (ECB, 2026-11-11). There is no conversion endpoint (docs): multiply or divide yourself.
- **Use the ECB provider route, never the blended default.** `/v2/rate/USD/EUR` (no provider) blends many central banks: at 23:15 UTC on 2026-11-11 it was 0.89388 from 96 providers, including FRED (2026-11-06), against the ECB's 0.89871. That is 223.47 vs 224.68 EUR for 250 USD. FRED's terms ban scraping and AI use, so this skill does not touch the blended route.
- **The ECB publishes EUR-based rates only** (EUR 1 = 1.1127 USD). `/v2/providers/ecb/rate/USD/EUR` (0.89871) is Frankfurter's inversion of it. Say the USD->EUR figure is calculated (ECB terms: modifications "must be stated explicitly").
- **"Today" means the latest ECB fixing.** The ECB updates "at around 16:00 CET every working day, except on TARGET closing days". Before then, on weekends and on holidays, the API returns the previous fixing. Block 1 compares the fixing date with the Frankfurt clock and warns on a mismatch.
- **Cross-check with the ECB itself** in one extra call: the ECB reference-rates page (block 1, browser) or its linked XML feed `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml` (block 3). Both said 1.1127 for 2026-11-11.
- **Errors are JSON:** unknown code is HTTP 422 `{"status":422,"message":"invalid currency: ABC"}`; a currency the ECB does not publish (NGN) or a date before 1999 is HTTP 404 `{"status":404,"message":"not found"}`.
- **Rate limit:** no quotas, "rate-limited to prevent abuse" (FAQ), no rate-limit headers. Blocks pace 1 s per call, serial.

## What works

### 1. Convert 250 USD to EUR at today's ECB rate, and cross-check on the ECB's page (browser)

`on_api_tab()` opens the ECB provider record on api.frankfurter.dev once, so `fetch()` is same-origin. `get()` returns parsed JSON on 200, waits 30 s once on 429/5xx and otherwise raises, so an error never looks like a rate. The block refuses a stale or future fixing date, checks the inversion, then reads the USD row of the ECB's own table in the same tab.

```python
import json, time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

AMOUNT, CCY = 250, "USD"  # convert AMOUNT CCY -> EUR at the ECB euro reference rate

SITE = "https://api.frankfurter.dev"
ECB = SITE + "/v2/providers/ecb"  # ECB provider route only; the blended /v2/rate and /v2/rates mix in other providers
ECB_PAGE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"
PAUSE = 1.0  # Frankfurter: no quotas, "rate-limited to prevent abuse"; keep calls serial

def on_api_tab():
    """fetch() runs same-origin from a logged-out api.frankfurter.dev tab (the ECB provider record, plain JSON). Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(ECB)
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"key":"ECB"' not in body.replace(" ", ""):
        raise RuntimeError(f"api.frankfurter.dev did not serve the ECB provider record (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__fx = window.__fx || {}; const id = String(Math.random()).slice(2); window.__fx[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__fx[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__fx[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__fx[%s]; if (v) delete window.__fx[%s]; return v; })()"""

def get(url, timeout=30):
    """GET url from inside the tab -> parsed JSON. Errors are JSON {"status":422,"message":"invalid currency: ABC"}.
    Waits 30 s once on 429/5xx, raises on anything else, so an error never looks like a rate."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] == 200 and "json" in (r["type"] or ""):
            return json.loads(r["text"])
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")

def latest_expected(now):
    """The ECB publishes 'at around 16:00 CET every working day, except on TARGET closing days'. Most recent weekday
    whose fixing should be out by now (TARGET holidays not modelled: a mismatch is a warning, not an error)."""
    d = now.date() if now.hour * 60 + now.minute >= 16 * 60 + 30 else now.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

on_api_tab()
prov = get(ECB)
if prov["key"] != "ECB" or prov["pivot_currency"] != "EUR":
    raise RuntimeError(f"unexpected provider record: {prov['key']} pivot {prov['pivot_currency']}")
if CCY not in prov["currencies"]:
    raise RuntimeError(f"the ECB does not publish {CCY}; this skill cannot answer for it")
print(f"provider: {prov['name']} ({prov['rate_type']}, pivot {prov['pivot_currency']}), data {prov['start_date']} .. {prov['end_date']}")
print(f"  source: {prov['data_url']}\n  terms:  {prov['terms_url']}")

# The ECB publishes EUR-based rates (EUR 1 = x CCY). That is the official figure; the other direction is an inversion.
pub = get(f"{ECB}/rate/EUR/{CCY}")
inv = get(f"{ECB}/rate/{CCY}/EUR")  # Frankfurter's inversion of it, rounded (0.89871)
for d, b, q in ((pub, "EUR", CCY), (inv, CCY, "EUR")):
    if (d["base"], d["quote"]) != (b, q):
        raise RuntimeError(f"asked {b}/{q}, got {d['base']}/{d['quote']}")
if pub["date"] != inv["date"]:
    raise RuntimeError(f"dates disagree: EUR pair {pub['date']}, inverted {inv['date']}")
if pub["date"] != prov["end_date"]:  # a separately cached response (cache-control max-age), can lag a new fixing
    print(f"  note: provider record ends {prov['end_date']}, rate is dated {pub['date']}; quoting the rate's date")

now = datetime.now(ZoneInfo("Europe/Berlin"))  # CET/CEST, the ECB's clock
want = latest_expected(now)
got = date.fromisoformat(pub["date"])
print(f"\nnow in Frankfurt {now:%Y-%m-%d %H:%M %Z}; latest expected fixing {want}; API fixing date {got}")
if got > now.date() or (now.date() - got).days > 7:
    raise RuntimeError(f"fixing date {got} is impossible or stale; stop")
if got != want:
    print(f"  WARNING: expected {want}; a TARGET closing day or a late publication. Quote the date you got.")

official = pub["rate"]  # EUR 1 = official CCY
amount = AMOUNT / official
check = AMOUNT * inv["rate"]
if abs(official * inv["rate"] - 1) > 1e-4:  # the inverted rate is rounded to 5 significant digits
    raise RuntimeError(f"inversion disagrees: {official} x {inv['rate']} = {official * inv['rate']:.6f}, not 1")
print(f"ECB EUR/{pub['quote']} {official} on {pub['date']}; Frankfurter {inv['base']}/{inv['quote']} {inv['rate']}")
print(f"  {AMOUNT} {CCY} / {official} = {amount:.4f} -> {amount:,.2f} EUR   (via the inverted rate: {check:.4f})")

# Cross-check against the ECB's own page (one page load; robots.txt has only a * group, Crawl-delay 5).
goto_url(ECB_PAGE)  # same tab; a later on_api_tab() sees the ECB origin and opens a fresh API tab
wait_for_load()
row = js("""(() => { const td = document.querySelector('td#%s'); const tr = td && td.closest('tr');
  const h = document.querySelector('.jumbo-box h3');
  return {rate: tr && tr.querySelector('.rate') && tr.querySelector('.rate').textContent.trim(), day: h && h.textContent.trim()}; })()"""
         % CCY)
if not row or not row["rate"] or not row["day"]:
    raise RuntimeError(f"ECB page layout changed (got {row!r}); use the API figure and say it was not cross-checked")
ecb_day = datetime.strptime(row["day"], "%d %B %Y").date()
print(f"\nECB page ({row['day']}): EUR 1 = {row['rate']} {CCY}")
if float(row["rate"]) != official or ecb_day != got:
    raise RuntimeError(f"ECB page says {row['rate']} on {ecb_day}, API says {official} on {got}: stop")
print("  matches the API")

print(f"\nanswer: {AMOUNT} {CCY} = {amount:,.2f} EUR at the ECB euro reference rate of {pub['date']} (EUR 1 = {official} {CCY}).")
print("  Source: European Central Bank, euro foreign exchange reference rates (" + ECB_PAGE + "), via Frankfurter;")
print(f"  the {CCY}->EUR figure is calculated from the ECB's EUR/{CCY} rate ({AMOUNT} / {official}); the ECB publishes only EUR/{CCY}.")
```

Output (from the run on 2026-11-11, 23:24 UTC):

```text
provider: European Central Bank (reference rate, pivot EUR), data 1999-01-04 .. 2026-11-11
  source: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
  terms:  https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html

now in Frankfurt 2026-11-12 00:24 CET; latest expected fixing 2026-11-11; API fixing date 2026-11-11
ECB EUR/USD 1.1127 on 2026-11-11; Frankfurter USD/EUR 0.89871
  250 USD / 1.1127 = 224.6787 -> 224.68 EUR   (via the inverted rate: 224.6775)

ECB page (11 November 2026): EUR 1 = 1.1127 USD
  matches the API

answer: 250 USD = 224.68 EUR at the ECB euro reference rate of 2026-11-11 (EUR 1 = 1.1127 USD).
  Source: European Central Bank, euro foreign exchange reference rates (https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html), via Frankfurter;
  the USD->EUR figure is calculated from the ECB's EUR/USD rate (250 / 1.1127); the ECB publishes only EUR/USD.
```

### 2. Terms, robots.txt and error shapes (browser)

Reads three FAQ answers from the docs page, then makes 8 small calls from an api.frankfurter.dev page: robots.txt, two date edge cases and four deliberate errors.

```python
import json, time

SITE = "https://api.frankfurter.dev"
ECB = SITE + "/v2/providers/ecb"
DOCS = "https://frankfurter.dev/"

# The docs FAQ, as the page shows it: commercial use, provider terms, rate limits.
new_tab(DOCS)
wait_for_load()
text = " ".join((js("document.body.innerText") or "").split())
if "Frankfurter" not in text:
    raise RuntimeError(f"frankfurter.dev did not serve its docs (at {js('location.href')}): stop")
for q in ("Is the API free for commercial use?", "Does the API have any call limits?", "There's no conversion endpoint"):
    i = text.find(q)
    if i < 0:
        raise RuntimeError(f"docs FAQ changed, {q!r} not found: re-read https://frankfurter.dev/ before relying on this skill")
    cut = text[i:i + 260]
    print("docs:", cut[:cut.rfind(". ") + 1] + "\n")

# Same-origin probes from an api.frankfurter.dev page, same tab. No retries: this block only inspects answers.
goto_url(ECB)
wait_for_load()
if js("location.origin") != SITE:
    raise RuntimeError(f"not on {SITE} (at {js('location.href')}): stop")

START_JS = """(() => { window.__fx = window.__fx || {}; const id = String(Math.random()).slice(2); window.__fx[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__fx[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__fx[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__fx[%s]; if (v) delete window.__fx[%s]; return v; })()"""

def raw(url, timeout=30):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{url}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r["status"], r["type"], " ".join(r["text"].split())

s, t, body = raw(SITE + "/robots.txt")
print(f"api robots.txt: HTTP {s} {t} {body!r}\n")
for path in ("/rate/usd/eur",                 # lower case is fine
             "/rate/USD/EUR?date=2026-11-08",  # Sunday -> previous fixing
             "/rate/USD/EUR?date=2026-11-20",  # future -> latest fixing, no error
             "/rate/EUR/NGN",                  # a currency the ECB does not publish
             "/rate/EUR/ABC",                  # not a currency
             "/rate/USD/EUR?date=2026-13-01",  # bad date
             "/rate/USD/EUR?date=1998-12-31"): # before the euro
    s, t, body = raw(ECB + path)
    print(f"{path}: HTTP {s} {t} {body[:100]}")
```

Output (from the run on 2026-11-11, 23:24 UTC):

```text
docs: Is the API free for commercial use? Yes. Blended rates are Frankfurter's own calculation and free to use. Direct queries to individual provider endpoints remain subject to each provider's terms. Can I store or cache rates in my own database? Yes.

docs: Does the API have any call limits? There are no quotas. Requests are rate-limited to prevent abuse, but there are no monthly or daily caps. For high-volume use, consider caching responses, self-hosting, or querying the datasets directly.

docs: There's no conversion endpoint. Fetch the rate and convert in a few lines of code.

api robots.txt: HTTP 200 text/plain 'User-agent: * Allow: /'

/rate/usd/eur: HTTP 200 application/json; charset=utf-8 {"date":"2026-11-11","base":"USD","quote":"EUR","rate":0.89871}
/rate/USD/EUR?date=2026-11-08: HTTP 200 application/json; charset=utf-8 {"date":"2026-11-06","base":"USD","quote":"EUR","rate":0.89566}
/rate/USD/EUR?date=2026-11-20: HTTP 200 application/json; charset=utf-8 {"date":"2026-11-11","base":"USD","quote":"EUR","rate":0.89871}
/rate/EUR/NGN: HTTP 404 application/json; charset=utf-8 {"status":404,"message":"not found"}
/rate/EUR/ABC: HTTP 422 application/json; charset=utf-8 {"status":422,"message":"invalid currency: ABC"}
/rate/USD/EUR?date=2026-13-01: HTTP 422 application/json; charset=utf-8 {"status":422,"message":"invalid date"}
/rate/USD/EUR?date=1998-12-31: HTTP 404 application/json; charset=utf-8 {"status":404,"message":"not found"}
```

### 3. Same answer with Python urllib, cross-checked against the ECB XML feed (no browser)

Python's default User-Agent got HTTP 200 from both hosts. The XML feed is linked from the ECB reference-rates page.

```python
import json, sys, time, urllib.error, urllib.request
import xml.etree.ElementTree as ET

AMOUNT, CCY = 250, "USD"  # convert AMOUNT CCY -> EUR
ECB = "https://api.frankfurter.dev/v2/providers/ecb"
ECB_XML = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"  # linked from the ECB reference-rates page

def get(url):
    """GET -> (status, body). Python's default User-Agent got HTTP 200 from both hosts."""
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

s, body = get(f"{ECB}/rate/EUR/{CCY}")
if s != 200:
    sys.exit(f"Frankfurter: HTTP {s} {body[:120]}")  # e.g. 404 {"status":404,"message":"not found"} for a non-ECB currency
fx = json.loads(body)
if (fx["base"], fx["quote"]) != ("EUR", CCY):
    sys.exit(f"asked EUR/{CCY}, got {fx['base']}/{fx['quote']}")
print(f"Frankfurter ECB route: {fx['date']} EUR 1 = {fx['rate']} {CCY}")

time.sleep(5)  # www.ecb.europa.eu robots.txt: Crawl-delay: 5
s, body = get(ECB_XML)
if s != 200:
    sys.exit(f"ECB XML: HTTP {s}")
ns = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
day = ET.fromstring(body).find(".//e:Cube[@time]", ns)
row = day.find(f"e:Cube[@currency='{CCY}']", ns)
if row is None:
    sys.exit(f"the ECB XML has no {CCY} row for {day.get('time')}")
print(f"ECB eurofxref-daily.xml: {day.get('time')} EUR 1 = {row.get('rate')} {CCY}")
if (day.get("time"), float(row.get("rate"))) != (fx["date"], fx["rate"]):
    sys.exit("Frankfurter and the ECB disagree: quote the ECB figure and date")

print(f"{AMOUNT} {CCY} = {AMOUNT / fx['rate']:,.2f} EUR (ECB reference rate {fx['date']}, calculated as {AMOUNT} / {fx['rate']})")
```

Output (from the run on 2026-11-11, 23:22 UTC):

```text
Frankfurter ECB route: 2026-11-11 EUR 1 = 1.1127 USD
ECB eurofxref-daily.xml: 2026-11-11 EUR 1 = 1.1127 USD
250 USD = 224.68 EUR (ECB reference rate 2026-11-11, calculated as 250 / 1.1127)
```

### 4. curl

```bash
B=https://api.frankfurter.dev/v2/providers/ecb   # ECB route; not /v2/rate (blended)
curl -sS --fail "$B/rate/EUR/USD" | python3 -c '
import json, sys
d = json.load(sys.stdin)
eur = 250 / d["rate"]
print(d["date"], "EUR 1 =", d["rate"], "USD -> 250 USD =", "%.2f" % eur, "EUR")
'
sleep 1
curl -sS --fail "$B/rates?base=USD&quotes=EUR,GBP"; echo   # several quotes in one call (inverted from EUR)
sleep 1
curl -sS -o /dev/null -w 'not an ECB currency (EUR/NGN): HTTP %{http_code} %{content_type}\n' "$B/rate/EUR/NGN"
```

Output (from the run on 2026-11-11, 23:22 UTC):

```text
2026-11-11 EUR 1 = 1.1127 USD -> 250 USD = 224.68 EUR
[{"date":"2026-11-11","base":"USD","quote":"EUR","rate":0.89871},{"date":"2026-11-11","base":"USD","quote":"GBP","rate":0.75149}]
not an ECB currency (EUR/NGN): HTTP 404 application/json; charset=utf-8
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `date` | rate | fixing date `YYYY-MM-DD`, ECB working days only; a weekend, holiday or future `date=` gets the latest fixing on or before it |
| `base`, `quote` | rate | upper case even when asked in lower case (`/rate/usd/eur` gives `USD`/`EUR`) |
| `rate` | rate | number; EUR-based pairs are the ECB figure (`1.1127`), other pairs are Frankfurter's calculation (`0.89871`) |
| `key`, `name`, `rate_type`, `pivot_currency` | `/v2/providers/ecb` | `ECB`, `European Central Bank`, `reference rate`, `EUR` |
| `data_url`, `terms_url` | `/v2/providers/ecb` | the ECB reference-rates page and the ECB disclaimer & copyright page; cite the first |
| `start_date`, `end_date` | `/v2/providers/ecb` | `1999-01-04` .. latest fixing (`2026-11-11`) |
| `currencies[]` | `/v2/providers/ecb` | 45 codes on 2026-11-11, including retired ones (`CYP`, `EEK`, `GRD`, `LTL`, `SIT`, ...) for history |
| `/v2/providers/ecb/rates?base=&quotes=&date=` | list form | JSON array of `{date, base, quote, rate}`; several quotes in one call |

## Gotchas

- **Blended is the default.** `/v2/rate/<base>/<quote>` and `/v2/rates` without `providers=ecb` mixed 96 sources for USD/EUR on 2026-11-11, and `?expand=providers` lists FRED among them. Always use the `/v2/providers/ecb/...` route for "the ECB rate".
- **Future and non-working dates do not error.** `date=2026-11-20` (future) returned the 2026-11-11 fixing; `date=2026-11-08` (Sunday) returned 2026-11-06. Read `date` from the answer, never echo the one you asked for.
- **After midnight CET, "today" has no fixing yet.** At 00:24 CET on 2026-11-12 the latest fixing was 2026-11-11, which is correct until about 16:00 CET. Quote the fixing date with the amount.
- **Information only.** The ECB page: "The reference rates are published for information purposes only. Using the rates for transaction purposes is strongly discouraged." A bank or card rate will differ.
- **Caching.** Responses carry `cache-control: public, max-age=2654, stale-if-error=86400` and come from Cloudflare (`cf-cache-status: HIT`); right after 16:00 CET a cached answer can still show the previous day. The FAQ encourages storing daily observations locally.
- **`x-robots-tag: noindex`** on every API response: an instruction to search indexes, not an access rule.
- **CORS is open** (`access-control-allow-origin: *` when the request has an `Origin`), so `fetch()` from any tab works; the blocks use an api.frankfurter.dev tab anyway.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and page text, not the title.

## What does not work

- **The blended route for an "ECB rate" question:** wrong number (see Quick summary) and it includes FRED data, whose terms say "Don't do any data mining, scraping or extraction of FRED data" and forbid use "in connection with the development or training of ... machine learning, including ... generative artificial intelligence". Not used.
- **data.ecb.europa.eu / data-api.ecb.europa.eu (the ECB Data Portal API):** its robots.txt disallows GPTBot, ClaudeBot, Claude-Web, anthropic-ai, Google-Extended, PerplexityBot and CCBot. Not used; the reference-rates page and `eurofxref-daily.xml` on www.ecb.europa.eu carry the same daily figure.
- **Currencies the ECB does not publish** (NGN, for example; `/v2/providers/ecb` lists the 45 it has): HTTP 404 on the ECB route. Another provider route would answer, under that provider's terms; not covered here.
- **Not tested:** the v1 API (`/v1`; the FAQ says "The v1 API is deprecated in favor of v2, but remains available indefinitely" and "For European Central Bank data, use /v2/providers/ecb/rates"), date ranges (`from`/`to`), `group=`, CSV/NDJSON formats, the MCP server (mcp.frankfurter.dev), rate-limit behaviour (never provoked).
