# Macrotrends — Data Extraction

`https://www.macrotrends.net` — long-term historical financial and economic charts. Three access patterns depending on page type; all work with plain `http_get`, no browser required.

All results validated against live site on 2026-04-18.

## Do this first: pick your access pattern

| Goal | Pattern | Latency | Variable |
|------|---------|---------|----------|
| Stock OHLCV price history | Direct iframe PHP | ~190ms | `dataDaily` |
| Stock market cap (daily) | Direct iframe PHP | ~200ms | `chartData` |
| Stock fundamentals (PE, revenue, margins) | Direct iframe PHP | ~140ms | `chartData` |
| S&P 500 / composite index charts | `chart_iframe_comp.php` | ~90ms | `originalData` |
| Economic indicators (rates, yields, CPI) | `/economic-data/` JSON API | ~150ms | `data[]` array |
| Gold, commodity prices | Either path (both work) | ~150ms | `data[]` or `originalData` |

**Never use the browser for Macrotrends read-only tasks.** All endpoints are accessible via `http_get` with the default `Mozilla/5.0` UA. For pages that occasionally 403, switch to a Chrome UA (see gotchas).

---

## Pattern 1: Stock price history (OHLCV)

Construct the iframe URL directly — no need to fetch the main page first.

```python
import json, re
from helpers import http_get

def get_stock_ohlcv(ticker: str, years_back: int = None) -> list[dict]:
    """
    Returns daily OHLCV records for any US stock.

    ticker:     uppercase ticker symbol, e.g. 'AAPL', 'MSFT', 'TSLA', 'NVDA'
    years_back: number of years of history (1=~250 records, 15=~3772 records).
                Omit (None) to get ALL available history (AAPL goes back to 1980).
    """
    url = f"https://www.macrotrends.net/production/stocks/desktop/PRODUCTION/stock_price_history.php?t={ticker}"
    if years_back:
        url += f"&yb={years_back}"

    html = http_get(url)
    m = re.search(r'var\s+dataDaily\s*=\s*\[', html)
    if not m:
        raise ValueError(f"No dataDaily found for ticker {ticker!r}")

    si = html.index('[', m.start())
    bc = 0
    for j, ch in enumerate(html[si:], si):
        if ch == '[':   bc += 1
        elif ch == ']':
            bc -= 1
            if bc == 0: ei = j; break
    return json.loads(html[si:ei+1])

# Usage
records = get_stock_ohlcv('AAPL', years_back=15)
# [{'d': '2011-04-18', 'o': '9.771', 'h': '9.9547', 'l': '9.593', 'c': '9.9433', 'v': '18.275'}, ...]

latest = records[-1]
# {'d': '2026-04-17', 'o': '266.96', 'h': '272.3', 'l': '266.72', 'c': '270.23',
#  'v': '55.211', 'ma50': '260.554', 'ma200': '251.828'}

print(f"{latest['d']}: close=${latest['c']} vol={latest['v']}M shares")
```

### dataDaily field reference

| Field | Meaning | Type |
|-------|---------|------|
| `d` | Date (YYYY-MM-DD) | str |
| `o` | Open price (adjusted for splits) | str/float |
| `h` | High | str/float |
| `l` | Low | str/float |
| `c` | Close | str/float |
| `v` | Volume in **millions of shares** | str/float |
| `ma50` | 50-day moving average | str/float (appears on recent records only) |
| `ma200` | 200-day moving average | str/float (appears on recent records only) |

**Note:** All price values are strings — cast with `float()`. Volume is millions: `55.211` = 55.2M shares traded.

### Confirmed tickers (2026-04-18)

All tested with direct iframe URL, no page fetch needed:

```python
# All work: AAPL, MSFT, TSLA, NVDA, GOOGL, AMZN, META, NFLX, etc.
# 3772 records for yb=15 (goes back to 2011-04-18)
# AAPL full history: 11428 records back to 1980-12-12
```

---

## Pattern 2: Stock fundamentals (PE ratio, revenue, market cap, margins)

Different PHP files depending on metric. Construct directly.

### Market cap (daily, in billions USD)

```python
import json, re
from helpers import http_get

def get_market_cap(ticker: str, years_back: int = 15) -> list[dict]:
    url = f"https://www.macrotrends.net/production/stocks/desktop/PRODUCTION/market_cap.php?t={ticker}&yb={years_back}"
    html = http_get(url)
    m = re.search(r'var\s+chartData\s*=\s*\[', html)
    si = html.index('[', m.start())
    bc = 0
    for j, ch in enumerate(html[si:], si):
        if ch == '[':   bc += 1
        elif ch == ']':
            bc -= 1
            if bc == 0: ei = j; break
    return json.loads(html[si:ei+1])

data = get_market_cap('AAPL')
# [{'date': '2026-04-15', 'v1': 3929.35}, {'date': '2026-04-16', 'v1': 3884.67}, ...]
# v1 = market cap in billions USD
```

### PE ratio, revenue, current ratio (quarterly/annual fundamentals)

```python
import json, re
from helpers import http_get

def get_fundamental(ticker: str, metric_type: str, statement: str,
                    freq: str = 'Q', years_back: int = 15) -> list[dict]:
    """
    freq: 'Q' = quarterly, 'A' = annual
    """
    url = (
        f"https://www.macrotrends.net/production/stocks/desktop/PRODUCTION/"
        f"fundamental_iframe.php?t={ticker}&type={metric_type}&statement={statement}"
        f"&freq={freq}&sub=&yb={years_back}"
    )
    html = http_get(url)
    m = re.search(r'var\s+chartData\s*=\s*\[', html)
    si = html.index('[', m.start())
    bc = 0
    for j, ch in enumerate(html[si:], si):
        if ch == '[':   bc += 1
        elif ch == ']':
            bc -= 1
            if bc == 0: ei = j; break
    return json.loads(html[si:ei+1])

# PE ratio
pe = get_fundamental('AAPL', 'pe-ratio', 'price-ratios')
# [{'date': '2025-09-30', 'v1': 254.146, 'v2': 7.46, 'v3': 34.07}, ...]
# v1 = stock price, v2 = quarterly EPS, v3 = PE ratio

# Revenue
rev = get_fundamental('AAPL', 'revenue', 'income-statement')
# [{'date': '2025-12-31', 'v1': 435.617, 'v2': 143.756, 'v3': 15.65}, ...]
# v1 = TTM revenue ($B), v2 = quarterly revenue ($B), v3 = YoY growth %

# Total assets
assets = get_fundamental('AAPL', 'total-assets', 'balance-sheet')

# Current ratio
ratio = get_fundamental('AAPL', 'current-ratio', 'ratios')
```

### Profit margins

```python
def get_profit_margins(ticker: str, years_back: int = 15) -> list[dict]:
    url = (
        f"https://www.macrotrends.net/production/stocks/desktop/PRODUCTION/"
        f"fundamental_metric.php?t={ticker}&chart=profit-margin&sub=&yb={years_back}"
    )
    html = http_get(url)
    m = re.search(r'var\s+chartData\s*=\s*\[', html)
    si = html.index('[', m.start())
    bc = 0
    for j, ch in enumerate(html[si:], si):
        if ch == '[':   bc += 1
        elif ch == ']':
            bc -= 1
            if bc == 0: ei = j; break
    return json.loads(html[si:ei+1])

margins = get_profit_margins('AAPL')
# [{'date': '2025-12-31', 'v1': 47.33, 'v2': 32.38, 'v3': 27.04}, ...]
# v1 = gross margin %, v2 = operating margin %, v3 = net margin %
```

### Dividend yield

```python
def get_dividend_yield(ticker: str, years_back: int = 15) -> list[dict]:
    url = f"https://www.macrotrends.net/production/stocks/desktop/PRODUCTION/dividend_yield.php?t={ticker}&yb={years_back}"
    html = http_get(url)
    m = re.search(r'var\s+chartData\s*=\s*\[', html)
    si = html.index('[', m.start())
    bc = 0
    for j, ch in enumerate(html[si:], si):
        if ch == '[':   bc += 1
        elif ch == ']':
            bc -= 1
            if bc == 0: ei = j; break
    return json.loads(html[si:ei+1])

dy = get_dividend_yield('AAPL')
# [{'date': '2026-04-17', 'c': 270.23, 'ttm_d': 1.03848, 'ttm_dy': 0.3843}, ...]
# c = stock price, ttm_d = TTM dividend ($), ttm_dy = TTM yield (%)
```

### Stock metric URL reference

| Metric | PHP file | Extra params |
|--------|----------|-------------|
| Stock price OHLCV | `stock_price_history.php` | — |
| Market cap (daily) | `market_cap.php` | — |
| Dividend yield | `dividend_yield.php` | — |
| Stock splits (price history) | `stock_splits.php` | — |
| PE ratio | `fundamental_iframe.php` | `type=pe-ratio&statement=price-ratios` |
| Revenue | `fundamental_iframe.php` | `type=revenue&statement=income-statement` |
| Total assets | `fundamental_iframe.php` | `type=total-assets&statement=balance-sheet` |
| Current ratio | `fundamental_iframe.php` | `type=current-ratio&statement=ratios` |
| Profit margins | `fundamental_metric.php` | `chart=profit-margin` |

Base URL prefix: `https://www.macrotrends.net/production/stocks/desktop/PRODUCTION/`

All take `?t={TICKER}&yb={N}` (or `&sub=&yb={N}` for the fundamental ones).

---

## Pattern 3: Index and composite charts (S&P 500, Shiller PE, etc.)

These pages embed chart data via `chart_iframe_comp.php`. The variable is `originalData`.

```python
import json, re
from helpers import http_get

def extract_index_chart(page_id: int, url_slug: str) -> list[dict]:
    """
    page_id:  the numeric ID from the page URL, e.g. 2577
    url_slug: last segment of the page URL, e.g. 'sp500-pe-ratio-price-to-earnings-chart'
    """
    url = f"https://www.macrotrends.net/assets/php/chart_iframe_comp.php?id={page_id}&url={url_slug}"
    html = http_get(url)
    m = re.search(r'var\s+originalData\s*=\s*\[', html)
    if not m:
        raise ValueError("originalData not found — this page may use a different pattern")
    si = html.index('[', m.start())
    bc = 0
    for j, ch in enumerate(html[si:], si):
        if ch == '[':   bc += 1
        elif ch == ']':
            bc -= 1
            if bc == 0: ei = j; break
    return json.loads(html[si:ei+1])

# S&P 500 PE ratio (1180 monthly records, 1927-2026)
pe_data = extract_index_chart(2577, 'sp500-pe-ratio-price-to-earnings-chart')
# [{'date': '1927-12-01', 'close': '15.9099'}, ..., {'date': '2026-03-01', 'close': '27.8925'}]
# 'close' is the PE ratio value

# Gold prices (1336 monthly records, 1915-2026)
gold_data = extract_index_chart(1333, 'historical-gold-prices-100-year-chart')
# [{'id': 'GOLDAMGBD228NLBM', 'date': '1915-01-01', 'close': '629.36', 'close1': '19.250'}, ...]
# 'close' = inflation-adjusted price, 'close1' = nominal USD price

print(f"Latest S&P PE: {pe_data[-1]}")   # {'date': '2026-03-01', 'close': '27.8925'}
print(f"Latest gold:   {gold_data[-1]}") # {'id': ..., 'date': '2026-04-01', 'close': '5177.19', 'close1': '5177.190'}
```

### Detecting which pattern a page uses

```python
def get_page_pattern(page_url: str) -> str:
    html = http_get(page_url)
    if 'chart_iframe_comp.php' in html:
        return 'index_chart'           # use extract_index_chart()
    elif 'generateChart' in html and 'highchartsURL' in html:
        return 'economic_api'          # use get_economic_data()
    elif '/production/stocks/desktop/PRODUCTION/' in html:
        return 'stock_iframe'          # use get_stock_ohlcv() etc.
    return 'unknown'
```

### To get the ID and slug from a page

```python
import re
from helpers import http_get

page_url = "https://www.macrotrends.net/2577/sp500-pe-ratio-price-to-earnings-chart"
html = http_get(page_url)

# Option A: parse from the iframe src in the HTML
m = re.search(r'chart_iframe_comp\.php\?id=(\d+)&url=([^"&]+)', html)
if m:
    page_id, url_slug = int(m.group(1)), m.group(2)

# Option B: derive from the page URL (works when slug matches)
import urllib.parse
parts = page_url.rstrip('/').split('/')
page_id  = int(parts[-2])   # 2577
url_slug = parts[-1]         # 'sp500-pe-ratio-price-to-earnings-chart'
```

---

## Pattern 4: Economic indicator API

Pages that use `generateChart()` in their JS load data from `/economic-data/{pageID}/{freq}`.
This endpoint requires a `Referer` header matching the page URL.

```python
import json, datetime, gzip, urllib.request
from helpers import http_get

def get_economic_data(page_id: int, referer_url: str, freq: str = 'D') -> dict:
    """
    page_id:     numeric ID from the page URL (e.g. 2015 for Fed Funds Rate)
    referer_url: the full page URL — required as Referer header
    freq:        'D' = daily, 'M' = monthly (not all support both)
    
    Returns {'data': [[ts_ms, value], ...], 'metadata': {...}}
    """
    url = f"https://www.macrotrends.net/economic-data/{page_id}/{freq}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, */*",
        "Accept-Encoding": "gzip",
        "Referer": referer_url,
    }
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        result = json.loads(raw)
    if result is None:
        raise ValueError(f"pageID={page_id} does not support freq={freq!r}")
    return result

# Fed Funds Rate (daily, 25319 records)
ffr = get_economic_data(2015, "https://www.macrotrends.net/2015/fed-funds-rate-historical-chart", freq='D')
print(ffr['metadata']['name'])  # 'Fed Funds Interest Rate'
print(ffr['metadata']['label']) # '%'

# Convert timestamps to dates
for ts_ms, value in ffr['data'][-3:]:
    dt = datetime.datetime.fromtimestamp(ts_ms / 1000, datetime.UTC)
    print(f"{dt.strftime('%Y-%m-%d')}: {value}%")
# 2026-04-13: 3.64%
# 2026-04-14: 3.64%
# 2026-04-15: 3.64%

# 10-Year Treasury yield (daily, 16074 records)
t10 = get_economic_data(2016, "https://www.macrotrends.net/2016/10-year-treasury-bond-rate-yield-chart", freq='D')
# Last: 2026-04-15: 4.29%

# Gold prices (monthly, 1336 records, 1915-present) — template=5
gold = get_economic_data(1333, "https://www.macrotrends.net/1333/historical-gold-prices-100-year-chart", freq='M')
# metadata: {'name': 'Gold Prices', 'currency': '$', 'label': ''}

# US Unemployment Rate (monthly, 938 records)
unemp = get_economic_data(1316, "https://www.macrotrends.net/1316/us-national-unemployment-rate", freq='M')
# metadata: {'name': 'U.S. Unemployment Rate', 'label': '%'}

# Debt-to-GDP ratio (monthly, 712 records)
debt_gdp = get_economic_data(1381, "https://www.macrotrends.net/1381/debt-to-gdp-ratio-historical-chart", freq='M')
```

### metadata fields

```python
{
    'name':            'Fed Funds Interest Rate',  # chart title
    'tableHeaderName': 'Fed Funds Interest Rate',
    'currency':        '',            # '$' for dollar-denominated series
    'label':           '%',          # units label
    'chartType':       'line',
    'mobileChartType': 'line',
    'lineWidth':       2,
    'positiveColor':   '#2caffe',
    'negativeColor':   '',
    'decimals':        '',
    'chartScale':      'linear',
    'seriesUnits':     ''
}
```

### Available frequency codes

| Code | Meaning | Notes |
|------|---------|-------|
| `D` | Daily | Most series support this |
| `M` | Monthly | Returns `null` if not available |
| `Q` | Quarterly | Usually `null` — use `M` instead |
| `A` | Annual | Usually `null` — use `M` instead |
| `DEFAULT` | Default (usually monthly) | Same data as `M` for most series |
| `INDEXMONTHLY` | Monthly index close | Some commodity/index series |
| `INDEXDAILY` | Daily index | Some series |
| `DAILYEXCHANGERATE` | Daily FX rate | Currency pairs |
| `10YD` | 10-year daily | Specialized series |

Try `D` first, fall back to `M` if you get `null`.

### Known economic page IDs

| ID | URL slug | Description |
|----|----------|-------------|
| 1316 | us-national-unemployment-rate | U.S. Unemployment Rate (monthly, back to 1948) |
| 1333 | historical-gold-prices-100-year-chart | Gold Prices (monthly, back to 1915) |
| 1381 | debt-to-gdp-ratio-historical-chart | U.S. Debt to GDP Ratio |
| 2015 | fed-funds-rate-historical-chart | Fed Funds Interest Rate (daily, back to 1954) |
| 2016 | 10-year-treasury-bond-rate-yield-chart | 10-Year Treasury Yield (daily, back to 1962) |
| 2577 | sp500-pe-ratio-price-to-earnings-chart | S&P 500 PE Ratio (uses `chart_iframe_comp.php`) |

---

## Generic extraction helper

One function that handles all three embedded-JS patterns:

```python
import json, re
from helpers import http_get

def extract_chart_var(html: str, var_name: str) -> list:
    """Extract a JS array variable from Macrotrends iframe HTML."""
    m = re.search(rf'var\s+{re.escape(var_name)}\s*=\s*\[', html)
    if not m:
        return []
    si = html.index('[', m.start())
    bc = 0
    for j, ch in enumerate(html[si:], si):
        if ch == '[':   bc += 1
        elif ch == ']':
            bc -= 1
            if bc == 0:
                return json.loads(html[si:j+1])
    return []

# Works for dataDaily, chartData, or originalData:
html = http_get("https://www.macrotrends.net/production/stocks/desktop/PRODUCTION/stock_price_history.php?t=AAPL&yb=15")
daily = extract_chart_var(html, 'dataDaily')

html2 = http_get("https://www.macrotrends.net/assets/php/chart_iframe_comp.php?id=2577&url=sp500-pe-ratio-price-to-earnings-chart")
pe_data = extract_chart_var(html2, 'originalData')
```

---

## URL construction guide

### Stock pages

```python
STOCK_BASE = "https://www.macrotrends.net/production/stocks/desktop/PRODUCTION/"

# Price history OHLCV
f"{STOCK_BASE}stock_price_history.php?t={ticker}"                        # all history
f"{STOCK_BASE}stock_price_history.php?t={ticker}&yb={years}"             # last N years

# Market cap
f"{STOCK_BASE}market_cap.php?t={ticker}&yb={years}"

# Fundamentals
f"{STOCK_BASE}fundamental_iframe.php?t={ticker}&type={type}&statement={stmt}&freq={freq}&sub=&yb={years}"
# type/statement combos: pe-ratio/price-ratios, revenue/income-statement,
#                        total-assets/balance-sheet, current-ratio/ratios

# Metrics
f"{STOCK_BASE}fundamental_metric.php?t={ticker}&chart={metric}&sub=&yb={years}"
# metrics: profit-margin

# Dividend yield
f"{STOCK_BASE}dividend_yield.php?t={ticker}&yb={years}"
```

### Economic / index pages

```python
# From numeric ID + URL slug (read from page source or page URL)
f"https://www.macrotrends.net/assets/php/chart_iframe_comp.php?id={id}&url={slug}"

# Economic indicator JSON API (requires Referer header)
f"https://www.macrotrends.net/economic-data/{page_id}/{freq}"
```

---

## Rate limits and anti-bot

- **No rate limiting observed** at any tested volume. 10 rapid requests to the same stock iframe completed in 1.8s with no throttling, CAPTCHA, or 429 errors.
- **Default UA works** (`Mozilla/5.0`) for most endpoints. The iframe PHP files never 403'd.
- **Chrome UA needed** for some main HTML pages (not data endpoints): use when fetching `/stocks/charts/...` or `/2015/...` wrapper pages if you get 403. Switch to:
  ```python
  headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
  ```
- **Referer required** for `/economic-data/{id}/{freq}` — send the page URL as `Referer`. Without it, the request is allowed but you get a 403 on some pages.
- **No cookies, sessions, or auth tokens** needed for any endpoint.

---

## Gotchas

**Main page URL ≠ data page:** Some URLs redirect to different content. `/1316/us-national-debt-by-year` redirects to `/1316/us-national-unemployment-rate`. Always check the final URL with `r.url` if the returned data looks wrong. Use the final URL as the Referer.

**yb parameter controls history depth:**
- `yb=1` → ~250 records (last year)
- `yb=15` → ~3772 records (last 15 years)
- omit → full history (AAPL: 11428 records to 1980; default for most queries)

**Two iframe patterns for economic pages:** Pages at `macrotrends.net/NNNN/slug` use either `chart_iframe_comp.php` (→ `originalData`) or `generateChart` + `/economic-data/` API. Check the main page HTML to detect which:
```python
if 'chart_iframe_comp.php' in html:   # use extract_index_chart()
elif 'highchartsURL' in html:          # use get_economic_data()
```

**Gold data has two price columns:**
```python
{'id': 'GOLDAMGBD228NLBM', 'date': '2026-04-01', 'close': '5177.19', 'close1': '5177.190'}
# 'close'  = inflation-adjusted price (base year adjusts over time)
# 'close1' = nominal USD price (the raw market price)
```

**Economic API frequency codes:** Only `D` and `M` consistently return data across most series. `A` and `Q` return `null` for most economic indicators. Always try `D` first.

**chartData fields vary by metric:**
- `market_cap.php` → `{'date', 'v1'}` (v1 = market cap in $B)
- `fundamental_iframe.php` type=pe-ratio → `{'date', 'v1', 'v2', 'v3'}` (stock price, EPS, PE)
- `fundamental_iframe.php` type=revenue → `{'date', 'v1', 'v2', 'v3'}` (TTM revenue, quarterly revenue, YoY%)
- `fundamental_metric.php` chart=profit-margin → `{'date', 'v1', 'v2', 'v3'}` (gross%, operating%, net%)
- `dividend_yield.php` → `{'date', 'c', 'ttm_d', 'ttm_dy'}` (price, dividend, yield%)

**Bracket matching required for large arrays:** The `var dataDaily = [...]` in stock iframes is ~450KB with 3772 OHLCV records. The `re.DOTALL` greedy approach works but is slow; bracket-counting (`bc` pattern above) is O(n) and fast.

**No public API for ticker lookup:** To find the company slug for a URL, check the search endpoint: `https://www.macrotrends.net/production/stocks/desktop/PRODUCTION/ticker_search_list.php?v=YYYYMMDD` — but the stock price iframe only needs the ticker symbol (`?t=AAPL`), not the slug.
