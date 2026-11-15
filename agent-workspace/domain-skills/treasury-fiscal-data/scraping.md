# U.S. Treasury Fiscal Data - Debt to the Penny, Exchange Rates, Average Interest Rates (official API + site)

Field-tested against fiscaldata.treasury.gov and api.fiscaldata.treasury.gov on 2026-11-05 using a Browser Use cloud browser, logged out. Blocks 1-3 call the official Fiscal Data API (https://fiscaldata.treasury.gov/api-documentation/) with `fetch()` from a fiscaldata.treasury.gov tab, block 4 reads the public dataset pages, block 5 is the same API over plain HTTP. About 70 browser API calls, 20 page loads and 40 plain HTTP calls: every answer was HTTP 200 or a documented 400, no 429, no challenge, no login or consent wall.

robots.txt (fetched 2026-11-05): fiscaldata.treasury.gov has only `User-agent: *` / `Allow: /` (no named AI-agent groups); api.fiscaldata.treasury.gov/robots.txt is HTTP 404, and this skill calls its documented endpoints under the official-API exception (the docs: "Our API is open, meaning that it does not require a user account or registration for a token").

## Quick summary

- **Use the API.** Keyless, JSON, `Access-Control-Allow-Origin: *`. The dataset pages call the same endpoints themselves. Base `https://api.fiscaldata.treasury.gov/services/api/fiscal_service`, then:
  - `/v2/accounting/od/debt_to_penny` - total public debt outstanding, debt held by the public, intragovernmental holdings; one row per business day, published the next business day.
  - `/v1/accounting/od/rates_of_exchange` - Treasury Reporting Rates of Exchange: quarterly rates per `country_currency_desc`, plus amendment rows with a later `effective_date`.
  - `/v2/accounting/od/avg_interest_rates` - monthly average interest rate per security line (16 lines in Oct 2026).
- **Query syntax:** `fields=a,b`, `filter=field:op:value,field2:op:value` (ops seen working: `eq`, `lte`, `gte`, `in:(a,b)`), `sort=-field,field2`, `page[number]=N&page[size]=M` (max 10000, default 100). `meta.total-count` and `meta.total-pages` drive paging.
- **Everything is a string**, including `"null"`. Convert yourself; amounts are full dollars and cents (`"40550230047609.15"`), rates are percent (`"3.580"`).
- **The API decodes the query twice.** A literal `&` in a value (`Trinidad & Tobago-Dollar`) must be sent as `%2526`; sent as `%26` the filter is cut at the `&` and the rest of it is silently dropped (block 2 checks for this).
- **400s are invisible to in-browser `fetch()`.** Error answers carry no CORS header, so the tab sees `TypeError: Failed to fetch`. Block 5 (plain HTTP) shows the API's message.
- **Rate limits:** none published; the docs' response-code table lists 200, 400, 403, 404, 500. The blocks run one call at a time with 0.5 s between calls and stop on 403/429.

## What works

Blocks 1-3 share the same helpers: `on_fiscaldata_tab()` opens `https://fiscaldata.treasury.gov/robots.txt` once (a tiny allowed page) and later blocks reuse any fiscaldata.treasury.gov tab. `api(path, params)` builds the query (`qs()` double-encodes `&`), runs one `fetch()` in that tab, polls for the answer, reads big bodies back in 500,000-character slices and returns parsed JSON. It stops on 403/429, retries 5xx and network errors twice with backoff, and raises on anything else, so a failure never looks like an empty result. `all_rows()` follows `meta.total-pages`.

### 1. Debt to the Penny: latest, on a date, year-end history (browser, official API)

```python
import json, time, urllib.parse

DATES = ["2025-11-04", "2025-01-01", "2020-03-15", "2001-01-01"]   # value on the last record on or before each date
LATEST_N = 5

API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
DTTP = "/v2/accounting/od/debt_to_penny"
PACE = 0.5        # seconds between calls; the docs publish no rate limit, so stay serial and slow
CHUNK = 500_000   # characters per js() read when pulling a big body out of the tab

def on_fiscaldata_tab():
    """API calls run as fetch() from a logged-out fiscaldata.treasury.gov tab; the API answers with CORS '*'."""
    try:
        if js("location.origin") == "https://fiscaldata.treasury.gov":
            return
    except Exception:
        pass
    new_tab("https://fiscaldata.treasury.gov/robots.txt")   # tiny allowed page on the site
    wait_for_load()
    if js("location.origin") != "https://fiscaldata.treasury.gov":
        raise SystemExit(f"tab landed on {js('location.href')}: stop and tell the user; do not retry around it")

START_JS = """(() => { window.__fd = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__fd = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__fd = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def qs(params):
    """The API decodes the query twice: a literal '&' in a value must go out as %2526 or it silently splits the filter."""
    return urllib.parse.urlencode({k: str(v).replace("&", "%26") for k, v in params.items()},
                                  safe=":,()[]", quote_via=urllib.parse.quote)

def api(path, params=None, tries=3):
    """Serial GET of one Fiscal Data API endpoint. Returns parsed JSON (data, meta, links).
    403/429 stop; 5xx and network errors retry twice with backoff; anything else raises."""
    url = API + path + ("?" + qs(params) if params else "")
    for attempt in range(tries):
        js(START_JS % json.dumps(url))
        t0 = time.time()
        while not (meta := js("window.__fd && {status: window.__fd.status, len: window.__fd.len, err: window.__fd.err}")):
            if time.time() - t0 > 90:
                raise RuntimeError(f"{url}: no answer in 90 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__fd.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__fd = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        if status in (403, 429):
            raise SystemExit(f"HTTP {status} from {url}: stop and back off; do not retry with another session, IP or user agent")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        if status == 0:   # 400 answers carry no CORS header, so fetch() reports them as a network error
            raise RuntimeError(f"fetch failed ({meta.get('err')}): probably a 400 (bad field, operator or sort); "
                               f"open the URL in the tab to read the API message: {url}")
        msg = json.loads(body).get("message") if body.startswith("{") else body[:120]
        raise RuntimeError(f"HTTP {status} {url}: {msg}")

def all_rows(path, params, page_size=10000):
    """Every row for a filter: follows meta total-pages (max page[size] is 10000)."""
    rows, page = [], 1
    while True:
        d = api(path, {**params, "page[number]": page, "page[size]": page_size})
        rows += d["data"]
        if page >= d["meta"]["total-pages"]:
            return rows, d["meta"]["total-count"]
        page += 1

def money(v):
    return None if v in (None, "", "null") else float(v)   # the API returns every value as a string, nulls as "null"

on_fiscaldata_tab()

# 1. Latest records, newest first
d = api(DTTP, {"sort": "-record_date", "page[size]": LATEST_N})
print(f"{d['meta']['total-count']} records in the dataset; latest {LATEST_N}:")
rows = d["data"]
for r, prev in zip(rows, rows[1:] + [None]):
    total = money(r["tot_pub_debt_out_amt"])
    chg = f"  {total - money(prev['tot_pub_debt_out_amt']):+,.2f} vs {prev['record_date']}" if prev else ""
    print(f"  {r['record_date']}  total ${total:,.2f}  public ${money(r['debt_held_public_amt']):,.2f}  intragov ${money(r['intragov_hold_amt']):,.2f}{chg}")

# 2. Value on (or last business day before) given dates
for day in DATES:
    r = api(DTTP, {"filter": f"record_date:lte:{day}", "sort": "-record_date", "page[size]": 1})["data"]
    if not r:
        print(f"{day}: no record on or before this date")
        continue
    r = r[0]
    print(f"{day}: record {r['record_date']} total ${money(r['tot_pub_debt_out_amt']):,.2f}  public {r['debt_held_public_amt']}  intragov {r['intragov_hold_amt']}")

# 3. Full history with paging: year-end totals for the last 6 calendar years and the change
hist, total_count = all_rows(DTTP, {"fields": "record_date,tot_pub_debt_out_amt", "sort": "record_date"})
print(f"history: {len(hist)} of {total_count} rows, {hist[0]['record_date']} .. {hist[-1]['record_date']}")
year_end = {}
for r in hist:
    year_end[r["record_date"][:4]] = r   # sorted ascending, so the last row of each year wins
years = sorted(year_end)[-7:]
for y0, y1 in zip(years, years[1:]):
    a, b = money(year_end[y0]["tot_pub_debt_out_amt"]), money(year_end[y1]["tot_pub_debt_out_amt"])
    ytd = "  (year to date)" if not year_end[y1]["record_date"].endswith(("-12-29", "-12-30", "-12-31")) else ""
    print(f"  {year_end[y1]['record_date']}  ${b / 1e12:,.3f}T  {(b - a) / 1e12:+,.3f}T vs {year_end[y0]['record_date']}{ytd}")
```

Output observed on 2026-11-05:

```text
8428 records in the dataset; latest 5:
  2026-11-04  total $40,550,230,047,609.15  public $32,765,175,912,225.50  intragov $7,785,054,135,383.65  +2,826,476,624.33 vs 2026-11-03
  2026-11-03  total $40,547,403,570,984.82  public $32,765,330,118,710.62  intragov $7,782,073,452,274.20  +45,322,604,887.68 vs 2026-11-02
  2026-11-02  total $40,502,080,966,097.14  public $32,719,901,942,674.43  intragov $7,782,179,023,422.71  -22,429,046,965.27 vs 2026-10-30
  2026-10-30  total $40,524,510,013,062.41  public $32,738,422,032,176.85  intragov $7,786,087,980,885.56  -69,127,249,821.07 vs 2026-10-29
  2026-10-29  total $40,593,637,262,883.48  public $32,712,190,190,967.42  intragov $7,881,447,071,916.06
2025-11-04: record 2025-11-04 total $38,047,239,753,103.02  public 30588445700448.40  intragov 7458794052654.62
2025-01-01: record 2024-12-31 total $36,218,605,311,689.91  public 28836996111881.81  intragov 7381609199808.10
2020-03-15: record 2020-03-13 total $23,442,398,235,873.06  public 17441348876495.70  intragov 6001049359377.36
2001-01-01: record 2000-12-29 total $5,662,216,013,697.37  public null  intragov null
history: 8428 of 8428 rows, 1993-04-01 .. 2026-11-04
  2021-12-31  $29.617T  +1.869T vs 2020-12-31
  2022-12-30  $31.420T  +1.802T vs 2021-12-31
  2023-12-29  $34.001T  +2.582T vs 2022-12-30
  2024-12-31  $36.219T  +2.217T vs 2023-12-29
  2025-12-31  $38.514T  +2.295T vs 2024-12-31
  2026-11-04  $40.550T  +2.036T vs 2025-12-31  (year to date)
```

### 2. Exchange rates: exact names, rate in effect on a date, amendments, long history (browser, official API)

The dataset notes say the quarter-end rates apply "as of the date of this report and for the ensuing three months", and an amendment "will appear on the report as a separate line with a new effective date". So the rate for a transaction date is the row with the latest `effective_date` on or before that date.

```python
import json, time, urllib.parse

SEARCH = ["euro zone", "yen", "united kingdom", "zimbabwe", "tobago"]   # find exact country_currency_desc names
CURRENCIES = ["Euro Zone-Euro", "Japan-Yen", "United Kingdom-Pound", "Mexico-Peso", "Iran-Rial", "Trinidad & Tobago-Dollar"]
AS_OF = ["2026-11-05", "2024-09-20", "2024-07-15"]   # transaction dates: which reporting rate applies
AMOUNT = 1_000_000                                   # foreign units to convert to USD
SINCE = "2024-01-01"                                 # window for the as-of lookups
HISTORY_COUNTRIES = ["United Kingdom", "Mexico"]     # long history by country: currency labels change over time
HISTORY_SINCE = "2014-01-01"

API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
FX = "/v1/accounting/od/rates_of_exchange"
PACE = 0.5        # seconds between calls; the docs publish no rate limit, so stay serial and slow
CHUNK = 500_000   # characters per js() read when pulling a big body out of the tab

def on_fiscaldata_tab():
    """API calls run as fetch() from a logged-out fiscaldata.treasury.gov tab; the API answers with CORS '*'."""
    try:
        if js("location.origin") == "https://fiscaldata.treasury.gov":
            return
    except Exception:
        pass
    new_tab("https://fiscaldata.treasury.gov/robots.txt")   # tiny allowed page on the site
    wait_for_load()
    if js("location.origin") != "https://fiscaldata.treasury.gov":
        raise SystemExit(f"tab landed on {js('location.href')}: stop and tell the user; do not retry around it")

START_JS = """(() => { window.__fd = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__fd = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__fd = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def qs(params):
    """The API decodes the query twice: a literal '&' in a value must go out as %2526 or it silently splits the filter."""
    return urllib.parse.urlencode({k: str(v).replace("&", "%26") for k, v in params.items()},
                                  safe=":,()[]", quote_via=urllib.parse.quote)

def api(path, params=None, tries=3):
    """Serial GET of one Fiscal Data API endpoint. Returns parsed JSON (data, meta, links).
    403/429 stop; 5xx and network errors retry twice with backoff; anything else raises."""
    url = API + path + ("?" + qs(params) if params else "")
    for attempt in range(tries):
        js(START_JS % json.dumps(url))
        t0 = time.time()
        while not (meta := js("window.__fd && {status: window.__fd.status, len: window.__fd.len, err: window.__fd.err}")):
            if time.time() - t0 > 90:
                raise RuntimeError(f"{url}: no answer in 90 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__fd.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__fd = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        if status in (403, 429):
            raise SystemExit(f"HTTP {status} from {url}: stop and back off; do not retry with another session, IP or user agent")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        if status == 0:   # 400 answers carry no CORS header, so fetch() reports them as a network error
            raise RuntimeError(f"fetch failed ({meta.get('err')}): probably a 400 (bad field, operator or sort); "
                               f"open the URL in the tab to read the API message: {url}")
        msg = json.loads(body).get("message") if body.startswith("{") else body[:120]
        raise RuntimeError(f"HTTP {status} {url}: {msg}")

def all_rows(path, params, page_size=10000):
    """Every row for a filter: follows meta total-pages (max page[size] is 10000)."""
    rows, page = [], 1
    while True:
        d = api(path, {**params, "page[number]": page, "page[size]": page_size})
        rows += d["data"]
        if page >= d["meta"]["total-pages"]:
            return rows
        page += 1

def rate_on(rows, day):
    """Reporting rate for a transaction date: the row with the latest effective_date on or before it
    (quarter-end rows have effective_date == record_date; amendments carry a later effective_date)."""
    ok = [r for r in rows if r["effective_date"] <= day]
    return max(ok, key=lambda r: (r["effective_date"], r["record_date"])) if ok else None

on_fiscaldata_tab()

# 1. Exact names: filters need the full country_currency_desc string ("Country-Currency")
latest = api(FX, {"sort": "-record_date", "page[size]": 1})["data"][0]["record_date"]
quarter = api(FX, {"fields": "country_currency_desc,exchange_rate,effective_date,record_date,src_line_nbr",   # a sort field must be in fields
                   "filter": f"record_date:eq:{latest}", "sort": "src_line_nbr", "page[size]": 1000})["data"]
names = sorted({r["country_currency_desc"] for r in quarter})
amended = [(r["country_currency_desc"], r["effective_date"], r["exchange_rate"]) for r in quarter if r["effective_date"] != r["record_date"]]
print(f"latest quarter {latest}: {len(quarter)} rows, {len(names)} currencies, amended since: {amended}")
for s in SEARCH:
    print(f"  {s!r}: {[n for n in names if s.lower() in n.lower()]}")
missing = [c for c in CURRENCIES if c not in names]
if missing:
    raise SystemExit(f"not in the latest quarter: {missing}; pick exact strings from the search above")

# 2. Rate in effect on each AS_OF date (quarter-end rates + amendments since SINCE)
rows = all_rows(FX, {
    "fields": "record_date,effective_date,country_currency_desc,exchange_rate",
    "filter": f"country_currency_desc:in:({','.join(CURRENCIES)}),record_date:gte:{SINCE}",
    "sort": "country_currency_desc,effective_date",
})
if any(r["record_date"] < SINCE for r in rows) or {r["country_currency_desc"] for r in rows} != set(CURRENCIES):
    raise SystemExit("filter was not applied as written (check encoding of special characters); stopping")
by = {}
for r in rows:
    by.setdefault(r["country_currency_desc"], []).append(r)
for c in CURRENCIES:
    amend = [(r["record_date"], r["effective_date"], r["exchange_rate"]) for r in by[c] if r["effective_date"] != r["record_date"]]
    print(f"{c}: {len(by[c])} rows since {SINCE}; amendments {amend}")
for day in AS_OF:
    print(f"as of {day}:")
    for c in CURRENCIES:
        r = rate_on(by[c], day)
        if not r:
            print(f"   {c:<26} no rate on or before {day} since {SINCE}")
            continue
        rate = float(r["exchange_rate"])
        print(f"   {c:<26} {rate:>9} per USD  (record {r['record_date']}, effective {r['effective_date']})  {AMOUNT:,} = ${AMOUNT / rate:,.2f}")

# 3. Long history by country: the currency label is not stable (e.g. "Pound Sterling" 2015-2019)
for country in HISTORY_COUNTRIES:
    h = all_rows(FX, {"fields": "record_date,effective_date,country,currency,exchange_rate",
                      "filter": f"country:eq:{country},record_date:gte:{HISTORY_SINCE}", "sort": "record_date,effective_date"})
    labels = {}
    for r in h:
        labels.setdefault(r["currency"], []).append(r["record_date"])
    print(f"{country}: {len(h)} rows since {HISTORY_SINCE}; labels " +
          ", ".join(f"{k} {v[0]}..{v[-1]} ({len(v)})" for k, v in labels.items()))
    print("   " + " ".join(f"{r['record_date'][:7]}={r['exchange_rate']}" for r in h if r["effective_date"] == r["record_date"]))
```

Output observed on 2026-11-05:

```text
latest quarter 2026-09-30: 169 rows, 165 currencies, amended since: [('Iran-Rial', '2026-10-15', '1779500.0'), ('Iraq-Dinar', '2026-10-15', '1510.0'), ('South Sudan-Sudanese Pound', '2026-10-30', '4850.0'), ('Venezuela-Bolivar Soberano', '2026-10-15', '876.925')]
  'euro zone': ['Euro Zone-Euro']
  'yen': ['Japan-Yen']
  'united kingdom': ['United Kingdom-Pound']
  'zimbabwe': ['Zimbabwe-Gold']
  'tobago': ['Trinidad & Tobago-Dollar']
Euro Zone-Euro: 11 rows since 2024-01-01; amendments []
Japan-Yen: 12 rows since 2024-01-01; amendments [('2024-06-30', '2024-09-16', '140.04')]
United Kingdom-Pound: 11 rows since 2024-01-01; amendments []
Mexico-Peso: 12 rows since 2024-01-01; amendments [('2024-03-31', '2024-06-14', '18.566')]
Iran-Rial: 13 rows since 2024-01-01; amendments [('2025-12-31', '2026-01-15', '1068906.0'), ('2026-09-30', '2026-10-15', '1779500.0')]
Trinidad & Tobago-Dollar: 11 rows since 2024-01-01; amendments []
as of 2026-11-05:
   Euro Zone-Euro                 0.881 per USD  (record 2026-09-30, effective 2026-09-30)  1,000,000 = $1,135,073.78
   Japan-Yen                     157.09 per USD  (record 2026-09-30, effective 2026-09-30)  1,000,000 = $6,365.78
   United Kingdom-Pound           0.752 per USD  (record 2026-09-30, effective 2026-09-30)  1,000,000 = $1,329,787.23
   Mexico-Peso                   18.134 per USD  (record 2026-09-30, effective 2026-09-30)  1,000,000 = $55,145.03
   Iran-Rial                  1779500.0 per USD  (record 2026-09-30, effective 2026-10-15)  1,000,000 = $0.56
   Trinidad & Tobago-Dollar       6.743 per USD  (record 2026-09-30, effective 2026-09-30)  1,000,000 = $148,301.94
as of 2024-09-20:
   Euro Zone-Euro                 0.935 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $1,069,518.72
   Japan-Yen                     140.04 per USD  (record 2024-06-30, effective 2024-09-16)  1,000,000 = $7,140.82
   United Kingdom-Pound           0.791 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $1,264,222.50
   Mexico-Peso                   18.296 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $54,656.76
   Iran-Rial                    42000.0 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $23.81
   Trinidad & Tobago-Dollar       6.757 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $147,994.67
as of 2024-07-15:
   Euro Zone-Euro                 0.935 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $1,069,518.72
   Japan-Yen                     160.63 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $6,225.49
   United Kingdom-Pound           0.791 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $1,264,222.50
   Mexico-Peso                   18.296 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $54,656.76
   Iran-Rial                    42000.0 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $23.81
   Trinidad & Tobago-Dollar       6.757 per USD  (record 2024-06-30, effective 2024-06-30)  1,000,000 = $147,994.67
United Kingdom: 52 rows since 2014-01-01; labels Pound 2014-03-31..2026-09-30 (33), Pound Sterling 2015-03-31..2019-09-30 (19)
   2014-03=0.6 2014-06=0.588 2014-09=0.62 2014-12=0.642 2015-03=0.677 2015-06=0.636 2015-09=0.659 2015-12=0.675 2016-03=0.694 2016-06=0.745 2016-09=0.772 2016-12=0.812 2017-03=0.8 2017-06=0.771 2017-09=0.747 2017-12=0.74 2018-03=0.712 2018-06=0.76 2018-09=0.767 2018-12=0.781 2019-03=0.764 2019-06=0.788 2019-09=0.812 2019-12=0.758 2020-03=0.81 2020-06=0.815 2020-09=0.78 2020-12=0.732 2021-03=0.726 2021-06=0.722 2021-09=0.744 2021-12=0.74 2022-03=0.762 2022-06=0.826 2022-09=0.906 2022-12=0.83 2023-03=0.808 2023-06=0.79 2023-09=0.816 2023-12=0.786 2024-03=0.793 2024-06=0.791 2024-09=0.745 2024-12=0.797 2025-03=0.772 2025-06=0.73 2025-09=0.744 2025-12=0.743 2026-03=0.756 2026-06=0.756 2026-09=0.752
Mexico: 52 rows since 2014-01-01; labels Peso 2014-03-31..2026-09-30 (37), New Peso 2015-03-31..2018-09-30 (15)
   2014-03=13.25 2014-06=12.987 2014-09=13.5 2014-12=14.702 2015-03=15.351 2015-06=15.679 2015-09=16.944 2015-12=17.362 2016-03=17.17 2016-06=18.58 2016-09=19.46 2016-12=20.652 2017-03=18.709 2017-06=18.025 2017-09=18.178 2017-12=19.704 2018-03=18.181 2018-06=19.663 2018-09=18.837 2018-12=19.654 2019-03=19.295 2019-06=19.175 2019-09=19.725 2019-12=22.491 2020-03=23.791 2020-06=23.164 2020-09=20.067 2020-12=19.913 2021-03=20.518 2021-06=19.838 2021-09=20.522 2021-12=20.531 2022-03=19.888 2022-06=20.207 2022-09=20.149 2022-12=19.546 2023-03=18.063 2023-06=17.077 2023-09=17.471 2023-12=16.949 2024-03=16.558 2024-06=18.296 2024-09=19.655 2024-12=20.704 2025-03=20.386 2025-06=18.83 2025-09=18.344 2025-12=17.956 2026-03=18.028 2026-06=17.454 2026-09=18.134
```

### 3. Average interest rates: latest month and a monthly table (browser, official API)

```python
import json, time, urllib.parse

SECURITIES = ["Treasury Bills", "Treasury Notes", "Treasury Bonds", "Total Marketable", "Total Interest-bearing Debt"]
MONTHS = 13            # history window in months, newest first

API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
AIR = "/v2/accounting/od/avg_interest_rates"
PACE = 0.5        # seconds between calls; the docs publish no rate limit, so stay serial and slow
CHUNK = 500_000   # characters per js() read when pulling a big body out of the tab

def on_fiscaldata_tab():
    """API calls run as fetch() from a logged-out fiscaldata.treasury.gov tab; the API answers with CORS '*'."""
    try:
        if js("location.origin") == "https://fiscaldata.treasury.gov":
            return
    except Exception:
        pass
    new_tab("https://fiscaldata.treasury.gov/robots.txt")   # tiny allowed page on the site
    wait_for_load()
    if js("location.origin") != "https://fiscaldata.treasury.gov":
        raise SystemExit(f"tab landed on {js('location.href')}: stop and tell the user; do not retry around it")

START_JS = """(() => { window.__fd = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__fd = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__fd = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def qs(params):
    """The API decodes the query twice: a literal '&' in a value must go out as %2526 or it silently splits the filter."""
    return urllib.parse.urlencode({k: str(v).replace("&", "%26") for k, v in params.items()},
                                  safe=":,()[]", quote_via=urllib.parse.quote)

def api(path, params=None, tries=3):
    """Serial GET of one Fiscal Data API endpoint. Returns parsed JSON (data, meta, links).
    403/429 stop; 5xx and network errors retry twice with backoff; anything else raises."""
    url = API + path + ("?" + qs(params) if params else "")
    for attempt in range(tries):
        js(START_JS % json.dumps(url))
        t0 = time.time()
        while not (meta := js("window.__fd && {status: window.__fd.status, len: window.__fd.len, err: window.__fd.err}")):
            if time.time() - t0 > 90:
                raise RuntimeError(f"{url}: no answer in 90 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__fd.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__fd = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        if status in (403, 429):
            raise SystemExit(f"HTTP {status} from {url}: stop and back off; do not retry with another session, IP or user agent")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        if status == 0:   # 400 answers carry no CORS header, so fetch() reports them as a network error
            raise RuntimeError(f"fetch failed ({meta.get('err')}): probably a 400 (bad field, operator or sort); "
                               f"open the URL in the tab to read the API message: {url}")
        msg = json.loads(body).get("message") if body.startswith("{") else body[:120]
        raise RuntimeError(f"HTTP {status} {url}: {msg}")

def all_rows(path, params, page_size=10000):
    """Every row for a filter: follows meta total-pages (max page[size] is 10000)."""
    rows, page = [], 1
    while True:
        d = api(path, {**params, "page[number]": page, "page[size]": page_size})
        rows += d["data"]
        if page >= d["meta"]["total-pages"]:
            return rows
        page += 1

def pct(v):
    return None if v in (None, "", "null") else float(v)

on_fiscaldata_tab()

# 1. Latest month: every security line (marketable, non-marketable, totals)
latest = api(AIR, {"sort": "-record_date", "page[size]": 1})["data"][0]["record_date"]
month = api(AIR, {"filter": f"record_date:eq:{latest}", "sort": "src_line_nbr", "page[size]": 100})["data"]
print(f"average interest rates for {latest} ({len(month)} lines):")
for r in month:
    print(f"  {r['src_line_nbr']:>2} {r['security_type_desc']:<22} {r['security_desc']:<48} {r['avg_interest_rate_amt']}%")

# 2. Monthly history for chosen securities: first find the record date MONTHS back
dates = [r["record_date"] for r in api(AIR, {"fields": "record_date", "filter": "security_desc:eq:Total Marketable",
                                              "sort": "-record_date", "page[size]": MONTHS})["data"]]
known = {r["security_desc"] for r in month}
missing = [s for s in SECURITIES if s not in known]
if missing:
    raise SystemExit(f"not in the latest month: {missing}; use names from the table above")
hist = all_rows(AIR, {"fields": "record_date,security_desc,avg_interest_rate_amt",
                      "filter": f"security_desc:in:({','.join(SECURITIES)}),record_date:gte:{dates[-1]}",
                      "sort": "-record_date"})
grid = {}
for r in hist:
    grid.setdefault(r["record_date"], {})[r["security_desc"]] = pct(r["avg_interest_rate_amt"])
print("\nrecord date  " + "  ".join(f"{s[:16]:>16}" for s in SECURITIES))
for d in sorted(grid, reverse=True):
    print(f"{d}   " + "  ".join(f"{grid[d].get(s, float('nan')):>16.3f}" for s in SECURITIES))
new, old = max(grid), min(grid)
print(f"\nchange {old} -> {new} (percentage points): " +
      ", ".join(f"{s} {grid[new][s] - grid[old][s]:+.3f}" for s in SECURITIES if s in grid[new] and s in grid[old]))
```

Output observed on 2026-11-05:

```text
average interest rates for 2026-10-31 (16 lines):
   1 Marketable             Treasury Bills                                   4.014%
   2 Marketable             Treasury Notes                                   3.399%
   3 Marketable             Treasury Bonds                                   3.483%
   4 Marketable             Treasury Inflation-Protected Securities (TIPS)   1.227%
   5 Marketable             Treasury Floating Rate Notes (FRN)               4.170%
   6 Marketable             Federal Financing Bank                           2.383%
   7 Marketable             Total Marketable                                 3.570%
   8 Non-marketable         Domestic Series                                  7.577%
   9 Non-marketable         Special Purpose Vehicle                          3.140%
  10 Non-marketable         State and Local Government Series                3.490%
  11 Non-marketable         United States Savings Securities                 3.131%
  12 Non-marketable         United States Savings Inflation Securities       4.594%
  13 Non-marketable         Government Account Series                        3.629%
  14 Non-marketable         Government Account Series Inflation Securities   1.393%
  15 Non-marketable         Total Non-marketable                             3.630%
  16 Interest-bearing Debt  Total Interest-bearing Debt                      3.580%

record date    Treasury Bills    Treasury Notes    Treasury Bonds  Total Marketable  Total Interest-b
2026-10-31              4.014             3.399             3.483             3.570             3.580
2026-09-30              3.870             3.383             3.466             3.518             3.531
2026-08-31              3.788             3.345             3.453             3.475             3.490
2026-07-31              3.758             3.309             3.442             3.443             3.447
2026-06-30              3.706             3.283             3.430             3.411             3.409
2026-05-31              3.690             3.248             3.413             3.386             3.353
2026-04-30              3.696             3.230             3.403             3.373             3.340
2026-03-31              3.702             3.212             3.392             3.365             3.327
2026-02-28              3.720             3.190             3.377             3.355             3.320
2026-01-31              3.760             3.169             3.369             3.348             3.316
2025-12-31              3.860             3.157             3.360             3.362             3.324
2025-11-30              3.983             3.133             3.346             3.382             3.348
2025-10-31              4.075             3.124             3.338             3.393             3.355

change 2025-10-31 -> 2026-10-31 (percentage points): Treasury Bills -0.061, Treasury Notes +0.275, Treasury Bonds +0.145, Total Marketable +0.177, Total Interest-bearing Debt +0.225
```

### 4. What the dataset pages show: date range, last updated, next release, preview grid (browser, HTML)

Use this for freshness ("Last Updated", "New Data Expected") or to see what a person sees. The numbers are the same as the API (blocks 1-3).

```python
import time

PAGES = [
    "https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/",
    "https://fiscaldata.treasury.gov/datasets/treasury-reporting-rates-exchange/",
    "https://fiscaldata.treasury.gov/datasets/average-interest-rates-treasury-securities/",
]
ROWS = 5        # preview rows to print per page
PAUSE = 2.0     # seconds between page loads; robots.txt sets no crawl-delay

# The Data Preview grid is the table whose header has "Record Date" (the first table on some pages is "Reports and Files").
FIND_JS = r"""function previewTable() {
  return [...document.querySelectorAll('table')].find(t => [...t.querySelectorAll('thead th')].some(th => th.innerText.includes('Record Date')));
}
"""

def load(url):
    goto_url(url)
    wait_for_load()
    t = (js("document.title") or "").lower()
    if any(s in t for s in ("just a moment", "access denied", "attention required", "too many requests")):
        raise SystemExit(f"challenge or block page on {js('location.href')}: stop and back off, do not retry")
    t0 = time.time()   # the preview grid is filled by the page's own API calls after load
    while not js(FIND_JS + "(() => { const t = previewTable(); return !!(t && t.querySelector('tbody tr td')); })()"):
        if time.time() - t0 > 30:
            raise RuntimeError(f"{url}: preview table did not render in 30 s")
        time.sleep(0.5)
    time.sleep(PAUSE)

READ_JS = FIND_JS + r"""(() => {
  const text = document.body.innerText;
  const head = text.match(/(\d\d\/\d\d\/\d{4}) \u2014 (\d\d\/\d\d\/\d{4})Released (\w+)Last Updated (\d\d\/\d\d\/\d{4})New Data Expected (\d\d\/\d\d\/\d{4})/);
  const table = previewTable();
  const cols = [...table.querySelectorAll('thead th')].map(th => th.innerText.split('\n')[0].trim()).filter(Boolean);
  const rows = [...table.querySelectorAll('tbody tr')].map(tr => [...tr.cells].map(td => td.innerText.trim()));
  return {url: location.href, title: document.title.split(' | ')[0], range: head && [head[1], head[2]], released: head && head[3],
          last_updated: head && head[4], next_expected: head && head[5],
          preview_range: (text.match(/Date Range:\s*(\S+ - \S+)/) || [])[1] || null,
          shown: (text.match(/Showing 1 - \d+ rows of [\d,]+ rows/) || [null])[0], cols, rows};
})()"""

for url in PAGES:
    load(url)
    p = js(READ_JS)
    if not p["range"]:
        raise RuntimeError(f"{url}: dataset header not found; the page layout changed")
    print(p["url"])
    print(f"   {p['title']}: data {p['range'][0]} .. {p['range'][1]}, released {p['released']}, last updated {p['last_updated']}, "
          f"next {p['next_expected']} | preview {p['preview_range']} | {p['shown']}")
    print("   cols:", p["cols"])
    for r in p["rows"][:ROWS]:
        print("   ", r)
```

Output observed on 2026-11-05:

```text
https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny
   Debt to the Penny: data 04/01/1993 .. 11/04/2026, released Daily, last updated 11/05/2026, next 11/06/2026 | preview 11/05/2021 - 11/04/2026 | Showing 1 - 10 rows of 1253 rows
   cols: ['Record Date', 'Debt Held by the Public', 'Intragovernmental Holdings', 'Total Public Debt Outstanding']
    ['11/4/2026', '$32,765,175,912,225.50', '$7,785,054,135,383.65', '$40,550,230,047,609.15']
    ['11/3/2026', '$32,765,330,118,710.62', '$7,782,073,452,274.20', '$40,547,403,570,984.82']
    ['11/2/2026', '$32,719,901,942,674.43', '$7,782,179,023,422.71', '$40,502,080,966,097.14']
    ['10/30/2026', '$32,738,422,032,176.85', '$7,786,087,980,885.56', '$40,524,510,013,062.41']
    ['10/29/2026', '$32,712,190,190,967.42', '$7,881,447,071,916.06', '$40,593,637,262,883.48']
https://fiscaldata.treasury.gov/datasets/treasury-reporting-rates-exchange/treasury-reporting-rates-of-exchange
   Treasury Reporting Rates of Exchange: data 03/31/2001 .. 09/30/2026, released Quarterly, last updated 10/30/2026, next 11/16/2026 | preview 07/01/2026 - 09/30/2026 | Showing 1 - 10 rows of 169 rows
   cols: ['Record Date', 'Country - Currency Description', 'Exchange Rate', 'Effective Date']
    ['9/30/2026', 'Afghanistan-Afghani', '65.15', '9/30/2026']
    ['9/30/2026', 'Albania-Lek', '80.75', '9/30/2026']
    ['9/30/2026', 'Algeria-Dinar', '133.126', '9/30/2026']
    ['9/30/2026', 'Angola-Kwanza', '913', '9/30/2026']
    ['9/30/2026', 'Antigua & Barbuda-East Caribbean Dollar', '2.7', '9/30/2026']
https://fiscaldata.treasury.gov/datasets/average-interest-rates-treasury-securities/average-interest-rates-on-u-s-treasury-securities
   Average Interest Rates on U.S. Treasury Securities: data 01/31/2001 .. 10/31/2026, released Monthly, last updated 11/05/2026, next 12/04/2026 | preview 11/01/2021 - 10/31/2026 | Showing 1 - 10 rows of 1013 rows
   cols: ['Record Date', 'Security Type Description', 'Security Description', 'Average Interest Rate Amount']
    ['10/31/2026', 'Marketable', 'Treasury Bills', '4.014%']
    ['10/31/2026', 'Marketable', 'Treasury Notes', '3.399%']
    ['10/31/2026', 'Marketable', 'Treasury Bonds', '3.483%']
    ['10/31/2026', 'Marketable', 'Treasury Inflation-Protected Securities (TIPS)', '1.227%']
    ['10/31/2026', 'Marketable', 'Treasury Floating Rate Notes (FRN)', '4.170%']
```

### 5. Same API over plain HTTP, with the 400 messages (no browser)

```python
import json, time, urllib.error, urllib.parse, urllib.request

API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
PACE = 0.5   # seconds between calls; the docs publish no rate limit

def get(path, params):
    """Plain HTTP GET with the default Python user agent. Returns parsed JSON; raises with the API's own message on 400."""
    q = urllib.parse.urlencode({k: str(v).replace("&", "%26") for k, v in params.items()}, safe=":,()[]", quote_via=urllib.parse.quote)
    try:
        with urllib.request.urlopen(f"{API}{path}?{q}", timeout=60) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise SystemExit(f"HTTP {e.code}: stop and back off")
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {json.loads(body).get('message') if body.startswith('{') else body[:120]}")
    time.sleep(PACE)
    return out

debt = get("/v2/accounting/od/debt_to_penny", {"sort": "-record_date", "page[size]": 1})["data"][0]
print(f"Debt to the Penny {debt['record_date']}: ${float(debt['tot_pub_debt_out_amt']):,.2f}")

fx = get("/v1/accounting/od/rates_of_exchange", {
    "fields": "record_date,effective_date,country_currency_desc,exchange_rate",
    "filter": "country_currency_desc:in:(Euro Zone-Euro,Japan-Yen,Trinidad & Tobago-Dollar),record_date:gte:2026-01-01",
    "sort": "-effective_date"})
print("Exchange rates:", [(r["country_currency_desc"], r["record_date"], r["effective_date"], r["exchange_rate"]) for r in fx["data"]][:3])

air = get("/v2/accounting/od/avg_interest_rates", {"filter": "security_desc:eq:Total Interest-bearing Debt", "sort": "-record_date", "page[size]": 3})
print("Average interest, total interest-bearing debt:", [(r["record_date"], r["avg_interest_rate_amt"]) for r in air["data"]])

old = get("/v2/accounting/od/debt_to_penny", {"sort": "record_date", "page[size]": 1})["data"][0]
print("oldest row:", {k: old[k] for k in ("record_date", "debt_held_public_amt", "intragov_hold_amt", "tot_pub_debt_out_amt")})

for bad in ({"fields": "record_date,bogus"}, {"filter": "record_date:xx:2026-01-01"}, {"page[size]": 20000},
            {"fields": "record_date", "sort": "-tot_pub_debt_out_amt"}):
    try:
        get("/v2/accounting/od/debt_to_penny", bad)
    except RuntimeError as e:
        print(f"{bad} -> {e}")
```

Output observed on 2026-11-05:

```text
Debt to the Penny 2026-11-04: $40,550,230,047,609.15
Exchange rates: [('Euro Zone-Euro', '2026-09-30', '2026-09-30', '0.881'), ('Japan-Yen', '2026-09-30', '2026-09-30', '157.09'), ('Trinidad & Tobago-Dollar', '2026-09-30', '2026-09-30', '6.743')]
Average interest, total interest-bearing debt: [('2026-10-31', '3.580'), ('2026-09-30', '3.531'), ('2026-08-31', '3.490')]
oldest row: {'record_date': '1993-04-01', 'debt_held_public_amt': 'null', 'intragov_hold_amt': 'null', 'tot_pub_debt_out_amt': '4225873987843.44'}
{'fields': 'record_date,bogus'} -> HTTP 400: Invalid query parameter: Field 'bogus' does not exist. For more information, please see the documentation.
{'filter': 'record_date:xx:2026-01-01'} -> HTTP 400: Invalid query parameter: Operator ':xx:' is not supported. For more information, please see the documentation.
{'page[size]': 20000} -> HTTP 400: Invalid query parameter: Limit '20000' is invalid. Expected an integer between 1 and 10000. For more information, please see the documentation.
{'fields': 'record_date', 'sort': '-tot_pub_debt_out_amt'} -> HTTP 400: Invalid query parameter: Field 'tot_pub_debt_out_amt' does not exist. For more information, please see the documentation.
```

## URL patterns (all observed)

| URL | What it is |
|---|---|
| `api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?sort=-record_date&page[size]=1` | latest Debt to the Penny row |
| `.../debt_to_penny?filter=record_date:lte:2025-01-01&sort=-record_date&page[size]=1` | last business day on or before a date |
| `.../v1/accounting/od/rates_of_exchange?filter=record_date:eq:2026-09-30` | one quarter, 169 rows (165 currencies + 4 amendments) |
| `.../rates_of_exchange?filter=country_currency_desc:in:(Euro Zone-Euro,Japan-Yen),record_date:gte:2024-01-01` | chosen currencies since a date |
| `.../rates_of_exchange?filter=country:eq:United Kingdom` | one country across currency label changes |
| `.../v2/accounting/od/avg_interest_rates?filter=record_date:eq:2026-10-31` | one month, all 16 lines |
| `.../avg_interest_rates?filter=security_desc:eq:Total Interest-bearing Debt&sort=-record_date` | one line over time |
| `fiscaldata.treasury.gov/datasets/debt-to-the-penny/` | dataset page (redirects to `.../debt-to-the-penny/debt-to-the-penny`) |
| `fiscaldata.treasury.gov/datasets/treasury-reporting-rates-exchange/` | dataset page, preview defaults to the latest quarter |
| `fiscaldata.treasury.gov/datasets/average-interest-rates-treasury-securities/` | dataset page, preview defaults to 5 years |

## Fields

| Endpoint | Key fields |
|---|---|
| `debt_to_penny` | `record_date`, `tot_pub_debt_out_amt`, `debt_held_public_amt`, `intragov_hold_amt` (USD with cents), `record_fiscal_year`, `record_calendar_*` |
| `rates_of_exchange` | `record_date` (quarter end), `effective_date`, `country`, `currency`, `country_currency_desc`, `exchange_rate` (foreign units per 1 USD: Euro Zone-Euro 0.881, Japan-Yen 157.09 on 2026-09-30), `src_line_nbr` |
| `avg_interest_rates` | `record_date` (month end), `security_type_desc` (Marketable / Non-marketable / Interest-bearing Debt), `security_desc`, `avg_interest_rate_amt` (percent), `src_line_nbr` |

Every response: `data[]`, `meta` (`count`, `labels`, `dataTypes`, `dataFormats`, `total-count`, `total-pages`), `links` (`self`, `first`, `prev`, `next`, `last`).

## Gotchas

- **Old Debt to the Penny rows have `"null"` breakdowns.** The total is daily from 1993-04-01, but of the 3,004 rows before 2005-04-04 only 46 have `debt_held_public_amt` / `intragov_hold_amt` (fiscal year-ends 1997-2001, then month-ends to 2005-03-31); the other 2,958 carry the string `"null"` (the dataset notes say `$0.00`; the API returned `"null"`, never `0`). 8,428 rows total on 2026-11-05.
- **No row on weekends and holidays.** Use `record_date:lte:<date>&sort=-record_date&page[size]=1` (2025-01-01 -> 2024-12-31, 2020-03-15 -> 2020-03-13). The newest row is the previous business day (2026-11-04 on 2026-11-05).
- **Exchange-rate amendments are live data.** The 2026-09-30 quarter had 4 amendment rows on 2026-11-05 (Iran-Rial 1,779,500 effective 2026-10-15 vs 1,374,100 at quarter end; Iraq-Dinar; South Sudan-Sudanese Pound; Venezuela-Bolivar Soberano). Taking "the latest quarter's row" without `effective_date` gives two answers for those currencies. The quarterly PDF on the page does not include amendments (dataset notes).
- **Currency labels change.** `United Kingdom-Pound Sterling` 2015-03 to 2019-09, `United Kingdom-Pound` before and after; `Mexico-New Peso` 2015-03 to 2018-09. A history by `country_currency_desc` has gaps; filter by `country` (block 2, step 3). Not every currency appears every quarter (165 in 2026-09-30, 196 names since 2024-01-01).
- **A sort field must also be in `fields`.** `fields=record_date&sort=-tot_pub_debt_out_amt` is a 400 `Field 'tot_pub_debt_out_amt' does not exist`.
- **`links` are relative query fragments** like `&page%5Bnumber%5D=2&page%5Bsize%5D=3`, not URLs. Page by number with `meta.total-pages` instead.
- **Aggregation (docs):** a `fields` list that drops identifying columns collapses non-unique rows. `rates_of_exchange?fields=record_date,exchange_rate&filter=record_date:eq:2026-09-30` returned 142 rows, not 169: currencies sharing a rate (10 at `1.0`, 3 at `2.7`) became one row each. Keep the identifying field (`country_currency_desc`, `security_desc`) in `fields`.
- **Average interest rate totals exclude TIPS and FRNs** (dataset notes): `Total Marketable`, `Total Non-marketable` and `Total Interest-bearing Debt` are not the average of the lines above them. Security names change over time too (2001 has `Treasury Inflation-Indexed Notes`, not `TIPS`); block 3 checks names against the latest month.
- **Which debt number:** the dataset notes list six Fiscal Data datasets with total public debt; Debt to the Penny includes Federal Financing Bank debt in intragovernmental holdings, and some others round to millions.
- **Release timing** is on each dataset page (block 4): Debt to the Penny daily (next 11/06/2026), exchange rates quarterly with amendment releases in between (next 11/16/2026), average interest rates monthly (next 12/04/2026).
- On a 403, 429 or challenge page, stop. Do not retry with a different user agent, session or IP.

## What does not work

- **Daily market exchange rates:** this dataset is the government's quarterly reporting rate set, not a market feed. Rates before 2001 are not in the API (the notes point to GovInfo.gov).
- **Seeing 400 messages from in-browser `fetch()`:** blocked by missing CORS headers on errors; use block 5 or open the URL in the tab.
- **`page[size]` above 10000:** HTTP 400 `Limit '20000' is invalid. Expected an integer between 1 and 10000.`
