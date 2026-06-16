# SEC EDGAR — Scraping & Data Extraction

`https://www.sec.gov` / `https://data.sec.gov` / `https://efts.sec.gov` — all public data, no auth required. Every workflow here is pure `http_get` — no browser needed.

## Do this first

**SEC.gov requires a custom User-Agent on `www.sec.gov` and `data.sec.gov`. Always pass `headers=UA` or you get 403.**

```python
import json
UA = {"User-Agent": "browser-harness research@example.com"}
# Format required: "CompanyName contact@email.com"
# "Mozilla/5.0" (http_get default) works on efts.sec.gov and data.sec.gov
# but FAILS on www.sec.gov (company_tickers.json, Archives/, etc.)
```

Start with `company_tickers.json` to resolve any ticker → CIK in one call, then branch to whichever endpoint you need.

```python
import json
UA = {"User-Agent": "browser-harness research@example.com"}
tickers = json.loads(http_get("https://www.sec.gov/files/company_tickers.json", headers=UA))
# 10,391 public companies, ~50KB, always fresh
# Entry format: {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}

# Look up by ticker (exact, case-sensitive in the data)
aapl = next(v for v in tickers.values() if v['ticker'] == 'AAPL')
# {'cik_str': 320193, 'ticker': 'AAPL', 'title': 'Apple Inc.'}

# CIK is an int here; pad to 10 digits for API URLs
cik = str(aapl['cik_str']).zfill(10)  # "0000320193"
```

## Common workflows

### Ticker / name → CIK lookup

```python
import json
UA = {"User-Agent": "browser-harness research@example.com"}
tickers = json.loads(http_get("https://www.sec.gov/files/company_tickers.json", headers=UA))

# By ticker
tsla = next((v for v in tickers.values() if v['ticker'] == 'TSLA'), None)
# {'cik_str': 1318605, 'ticker': 'TSLA', 'title': 'Tesla, Inc.'}

# By partial name match
apples = [v for v in tickers.values() if 'APPLE' in v['title'].upper()]
# [{'cik_str': 320193, 'ticker': 'AAPL', 'title': 'Apple Inc.'}, ...]
```

### Company submissions (metadata + recent filings list)

```python
import json
UA = {"User-Agent": "browser-harness research@example.com"}
cik = "0000320193"  # Apple - always zero-pad to 10 digits
data = json.loads(http_get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=UA))

print(data['name'])             # "Apple Inc."
print(data['cik'])              # "0000320193"
print(data['sic'])              # "3571"
print(data['sicDescription'])   # "Electronic Computers"
print(data['tickers'])          # ["AAPL"]
print(data['exchanges'])        # ["Nasdaq"]

# Most recent ~1,000 filings are in data['filings']['recent']
recent = data['filings']['recent']
# Fields per filing (parallel arrays, same index):
# accessionNumber, filingDate, reportDate, form, primaryDocument,
# primaryDocDescription, size, isXBRL, items, fileNumber

# Filter for 10-K and 10-Q only
filings_10k = [
    (f, d, a, doc)
    for f, d, a, doc in zip(
        recent['form'], recent['filingDate'],
        recent['accessionNumber'], recent['primaryDocument']
    )
    if f in ('10-K', '10-Q')
]
# Result: [('10-Q', '2026-01-30', '0000320193-26-000006', 'aapl-20251227.htm'), ...]
```

### Build direct filing document URL

```python
# Given accessionNumber and primaryDocument from submissions JSON:
accn = "0000320193-25-000079"
doc  = "aapl-20250927.htm"
cik  = "320193"  # int part only (no leading zeros) for Archives path

accn_nodash = accn.replace("-", "")
url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn_nodash}/{doc}"
# https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm

# Full 10-K is 1.5MB of XBRL-tagged HTML — use http_get for text extraction
content = http_get(url, headers=UA)  # UA required on www.sec.gov
```

### XBRL financial data — single company, one concept over time

```python
import json
UA = {"User-Agent": "browser-harness research@example.com"}
cik_padded = "0000320193"

# companyconcept: one metric, all reported values (quarterly + annual)
data = json.loads(http_get(
    f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik_padded}/us-gaap/Assets.json",
    headers=UA
))
# data keys: cik, taxonomy, tag, label, description, entityName, units
# data['units']['USD'] -> list of {end, val, accn, fy, fp, form, filed}

entries = data['units']['USD']

# Deduplicate: same period re-reported across multiple filings — keep latest
def annual_series(entries):
    seen = {}
    for e in entries:
        if e.get('form') == '10-K' and e.get('fp') == 'FY':
            end = e['end']
            if end not in seen or e['filed'] > seen[end]['filed']:
                seen[end] = e
    return [seen[k] for k in sorted(seen)]

assets = annual_series(entries)
for e in assets[-5:]:
    print(f"{e['end']}  ${e['val']/1e9:.1f}B")
# 2021-09-25  $351.0B
# 2022-09-24  $352.8B
# 2023-09-30  $352.6B
# 2024-09-28  $365.0B
# 2025-09-27  $359.2B
```

### XBRL financial data — all US-GAAP metrics for a company

```python
import json
UA = {"User-Agent": "browser-harness research@example.com"}

# companyfacts: all reported XBRL concepts in one ~5MB call
data = json.loads(http_get(
    "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
    headers=UA
))
# data['entityName'] = "Apple Inc."
# data['facts'] = {'us-gaap': {...503 concepts...}, 'dei': {...}}

usgaap = data['facts']['us-gaap']
print(len(usgaap))   # 503 concepts for Apple

# Common concept names (companies vary — check what's available):
# Revenue:     RevenueFromContractWithCustomerExcludingAssessedTax  (post-2018 standard)
#              SalesRevenueNet                                       (older filings)
#              Revenues                                              (some companies still use)
# Net income:  NetIncomeLoss
# Assets:      Assets
# Cash:        CashAndCashEquivalentsAtCarryingValue
# EPS:         EarningsPerShareBasic, EarningsPerShareDiluted

# Find all revenue-related concepts this company reported:
revenue_keys = [k for k in usgaap if 'Revenue' in k]

# Extract annual revenue — handle company-specific concept name
for concept in ['RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'Revenues']:
    if concept in usgaap:
        entries = usgaap[concept]['units'].get('USD', [])
        annual = {}
        for e in entries:
            if e.get('form') == '10-K' and e.get('fp') == 'FY':
                end = e['end']
                if end not in annual or e['filed'] > annual[end]['filed']:
                    annual[end] = e
        if annual:
            print(f"Using: {concept}")
            for end in sorted(annual)[-3:]:
                print(f"  {end}  ${annual[end]['val']/1e9:.1f}B")
            break
# Apple output:
# Using: RevenueFromContractWithCustomerExcludingAssessedTax
#   2023-09-30  $383.3B
#   2024-09-28  $391.0B
#   2025-09-27  $416.2B
```

### Cross-company financial comparison (XBRL frames)

```python
import json
UA = {"User-Agent": "browser-harness research@example.com"}

# frames: one concept, one period, all companies that reported it
# Period formats:
#   CY2024           = calendar year 2024 (annual)
#   CY2024Q4I        = Q4 2024 instantaneous (balance sheet items)
#   CY2024Q4         = Q4 2024 duration (income statement items)

# Top companies by annual revenue (2024)
data = json.loads(http_get(
    "https://data.sec.gov/api/xbrl/frames/us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax/USD/CY2024.json",
    headers=UA
))
companies = sorted(data['data'], key=lambda x: x['val'], reverse=True)
# data['data'] entries: {accn, cik, entityName, loc, start, end, val}
for c in companies[:5]:
    print(f"{c['entityName']:<40}  ${c['val']/1e9:.0f}B")
# Walmart Inc.                              $675B
# AMAZON.COM, INC.                          $638B
# Apple Inc.                                $391B
# McKESSON CORPORATION                      $359B
# Alphabet Inc.                             $350B

# Total assets snapshot end of 2024 (balance sheet = instantaneous)
data2 = json.loads(http_get(
    "https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/CY2024Q4I.json",
    headers=UA
))
# 6,229 companies for this frame
```

### Full-text search across all filings

```python
import json
UA = {"User-Agent": "browser-harness research@example.com"}

# Search for any phrase across filing documents
# Params: q (quoted phrase), forms (comma-separated), dateRange=custom,
#         startdt, enddt, size (max 100), from (offset for pagination)
url = (
    "https://efts.sec.gov/LATEST/search-index"
    "?q=%22climate+risk%22"
    "&forms=10-K"
    "&dateRange=custom&startdt=2024-01-01"
    "&size=10&from=0"
)
data = json.loads(http_get(url, headers=UA))
# Note: default http_get UA (Mozilla/5.0) works fine on efts.sec.gov

print(data['hits']['total']['value'])   # e.g. 1438 matching documents
hits = data['hits']['hits']             # up to 100 per call

for h in hits:
    src = h['_source']
    # Key fields: display_names, ciks, form, file_date, adsh (accession), period_ending
    name = src['display_names'][0] if src.get('display_names') else '?'
    cik  = src['ciks'][0] if src.get('ciks') else '?'
    print(f"{name}  form={src['form']}  filed={src['file_date']}  accn={src['adsh']}")

# Pagination: max 100 per page, use from= to walk through results
# Page 2: from=100, Page 3: from=200, etc.
for page in range(0, 300, 100):
    page_url = url + f"&from={page}"
    page_data = json.loads(http_get(page_url, headers=UA))
    if not page_data['hits']['hits']:
        break
    # process...

# Aggregations — group hits by entity, SIC, state
aggs = data['aggregations']
top_entities = aggs['entity_filter']['buckets']   # [{key: "Name (CIK...)", doc_count: N}, ...]
top_sics     = aggs['sic_filter']['buckets']
top_states   = aggs['biz_states_filter']['buckets']
```

### Find a company's CIK by name search (via search aggregations)

```python
import json, re
UA = {"User-Agent": "browser-harness research@example.com"}

# Best method: company_tickers.json (fastest, all tickers)
tickers = json.loads(http_get("https://www.sec.gov/files/company_tickers.json", headers=UA))
msft = next(v for v in tickers.values() if v['ticker'] == 'MSFT')
# CIK = msft['cik_str']  → 789019

# Alternative: full-text search aggregations (finds CIK from company name)
data = json.loads(http_get(
    "https://efts.sec.gov/LATEST/search-index?q=%22microsoft+corporation%22&forms=10-K",
    headers=UA
))
buckets = data['aggregations']['entity_filter']['buckets']
# [{'key': 'MICROSOFT CORP  (MSFT)  (CIK 0000789019)', 'doc_count': 11}, ...]
for b in buckets[:3]:
    m = re.search(r'\(CIK (\d+)\)', b['key'])
    if m:
        print(f"{b['key'][:50]}  →  CIK {m.group(1)}")
```

### Parallel fetching (multiple companies)

```python
import json
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "browser-harness research@example.com"}

def get_company_meta(ticker_cik):
    ticker, cik = ticker_cik
    subs = json.loads(http_get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=UA))
    return {"ticker": ticker, "name": subs['name'], "sic": subs['sic']}

companies = [("AAPL", "0000320193"), ("TSLA", "0001318605"), ("MSFT", "0000789019")]
with ThreadPoolExecutor(max_workers=3) as ex:
    results = list(ex.map(get_company_meta, companies))
# Confirmed: 3 requests complete in ~0.28s
# SEC rate limit: 10 req/sec — stay at max_workers ≤ 8 to be safe
```

## API reference

| Endpoint | What it returns | UA required |
|---|---|---|
| `www.sec.gov/files/company_tickers.json` | All 10,391 tickers → CIK mapping | YES |
| `data.sec.gov/submissions/CIK{10-digit}.json` | Company meta + ~1000 recent filings | YES |
| `data.sec.gov/api/xbrl/companyfacts/CIK{10-digit}.json` | All XBRL facts (~5MB) | YES |
| `data.sec.gov/api/xbrl/companyconcept/CIK{10-digit}/{taxonomy}/{concept}.json` | One concept, all values | YES |
| `data.sec.gov/api/xbrl/frames/{taxonomy}/{concept}/{unit}/{period}.json` | All companies for one period | YES |
| `efts.sec.gov/LATEST/search-index?q=...` | Full-text search across filings | NO (Mozilla/5.0 works) |
| `www.sec.gov/Archives/edgar/data/{cik}/{accn-nodash}/{doc}` | Actual filing document | YES |

`data.sec.gov` accepts `Mozilla/5.0` (the http_get default). `www.sec.gov` (Archives, company_tickers) requires the `"CompanyName email@example.com"` format.

## Rate limits

SEC documents a **10 requests/second** limit. In practice:
- 12 rapid sequential calls to `data.sec.gov` completed in 2.4s (5 req/s) with no throttling.
- 3 parallel calls completed in 0.28s without issue.
- Stay at `max_workers ≤ 8` for ThreadPoolExecutor to respect the 10 req/s ceiling.
- No per-day or per-hour cap documented; the 10/s limit is the only stated constraint.

## Gotchas

- **`www.sec.gov` returns 403 with `Mozilla/5.0` UA** — The http_get default (`"Mozilla/5.0"`) works on `data.sec.gov` and `efts.sec.gov` but is blocked on `www.sec.gov`. Always pass `headers=UA` where UA includes your company name and email. Confirmed: `"python-requests/2.28"` → 403.

- **`data.sec.gov` is more permissive** — `Mozilla/5.0` works on `data.sec.gov` (submissions, xbrl). But always use the proper UA anyway — SEC's policy page explicitly requires it and they can add stricter checks at any time.

- **XBRL contains duplicate entries per period** — The same fiscal year end date appears multiple times when a company restates or re-files. Each entry has a `filed` date and `accn` (accession). To get the canonical value, deduplicate by `end` keeping the entry with the latest `filed` date.

- **Revenue concept name varies by company and era** — There is no single canonical "revenue" concept. Apple uses `RevenueFromContractWithCustomerExcludingAssessedTax`. Microsoft uses the same for recent years, but older filings used `SalesRevenueNet`. Always check which concepts are actually present: `[k for k in usgaap if 'Revenue' in k]`.

- **`fp` field for annual filings is `'FY'`, but quarterly values also appear in 10-K** — A 10-K re-reports each quarter (fp=Q1, Q2, Q3) plus the full year (fp=FY). Filter on both `form == '10-K'` AND `fp == 'FY'` to get only annual totals.

- **`companyfacts` is ~5MB per company** — For a single metric, use `companyconcept` instead (much smaller). Only use `companyfacts` when you need multiple concepts from the same company.

- **`submissions` recent filings cap at ~1,000** — Very old filings don't appear. If you need historical data before that window, use the `filings.files` array in submissions JSON to find older filing JSON pages (`data.sec.gov/submissions/CIK{cik}-submissions-001.json`, etc.).

- **`adsh` in search results is the accession number** — The search index returns `adsh` (no dashes). To build the document URL, insert dashes: `adsh[:10] + '-' + adsh[10:12] + '-' + adsh[12:]`, or use the `accessionNumber` field from submissions JSON (which already has dashes).

- **`size` param is capped at 100** — Requesting `size=200` silently returns 100 hits. Walk results with `from=0`, `from=100`, etc. Maximum reachable index is 10,000 (Elasticsearch default).

- **Search total `'gte'` relation means >10,000 hits** — When `total['relation'] == 'gte'`, there are more than 10,000 results (only first 10,000 accessible). Narrow with `dateRange` or `forms` filters.

- **`company_tickers.json` covers only exchange-listed companies** — ~10,391 entries. Many SEC filers (private companies, bond issuers, FHLBs) have CIKs but no ticker. Find them via the full-text search aggregations or `submissions` lookup if you have the CIK.

- **Filing document is XBRL-tagged HTML, 1–2MB** — Retrieving the actual 10-K HTML works but is large. For financial data extraction, always prefer the XBRL API endpoints over parsing the document.

- **CIK format gotcha** — `company_tickers.json` returns `cik_str` as an int (`320193`). The submissions and xbrl APIs require a 10-digit zero-padded string in the filename (`CIK0000320193`). Always use `str(cik).zfill(10)` when building URLs.
