# Yahoo Finance — Scraping & Data Extraction

`https://finance.yahoo.com` — use the `v8/finance/chart` and `v1/finance/search` endpoints directly. Both are free, require no auth, and work with `User-Agent: Mozilla/5.0`. No browser needed for price/OHLCV/search data.

## Do this first

**`v8/finance/chart` is the core free endpoint** — returns real-time price, OHLCV history, and rich metadata in one call. Covers equities, ETFs, crypto, forex, and futures.

```python
import json

headers = {"User-Agent": "Mozilla/5.0"}

data = json.loads(http_get(
    "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=5d",
    headers=headers
))
result = data['chart']['result'][0]
meta   = result['meta']

print(meta['symbol'])               # "AAPL"
print(meta['regularMarketPrice'])   # 270.23
print(meta['currency'])             # "USD"
print(meta['exchangeName'])         # "NMS"
print(meta['longName'])             # "Apple Inc."
```

**Do NOT attempt `v10/quoteSummary` for fundamental data** — it requires a crumb token that can only be obtained from an authenticated browser session cookie. It will return `401 Unauthorized` from `http_get`.

---

## Common workflows

### Current quote (real-time price + metadata)

```python
import json

headers = {"User-Agent": "Mozilla/5.0"}

def get_quote(symbol):
    data = json.loads(http_get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d",
        headers=headers
    ))
    return data['chart']['result'][0]['meta']

meta = get_quote("AAPL")
print(meta['regularMarketPrice'])    # current price: 270.23
print(meta['regularMarketDayHigh'])  # day high
print(meta['regularMarketDayLow'])   # day low
print(meta['regularMarketVolume'])   # volume
print(meta['fiftyTwoWeekHigh'])      # 52-week high
print(meta['fiftyTwoWeekLow'])       # 52-week low
print(meta['chartPreviousClose'])    # previous close
print(meta['instrumentType'])        # "EQUITY", "ETF", "CRYPTOCURRENCY", etc.
print(meta['exchangeTimezoneName'])  # "America/New_York"
```

Full meta fields: `currency, symbol, exchangeName, fullExchangeName, instrumentType, firstTradeDate, regularMarketTime, hasPrePostMarketData, gmtoffset, timezone, exchangeTimezoneName, regularMarketPrice, fiftyTwoWeekHigh, fiftyTwoWeekLow, regularMarketDayHigh, regularMarketDayLow, regularMarketVolume, longName, shortName, chartPreviousClose, priceHint, currentTradingPeriod, dataGranularity, range, validRanges`.

### Historical OHLCV data

```python
import json
from datetime import datetime

headers = {"User-Agent": "Mozilla/5.0"}

data = json.loads(http_get(
    "https://query1.finance.yahoo.com/v8/finance/chart/TSLA?interval=1d&range=1mo",
    headers=headers
))
result = data['chart']['result'][0]

timestamps = result['timestamp']             # list of Unix timestamps
quotes     = result['indicators']['quote'][0]
adjclose   = result['indicators']['adjclose'][0]['adjclose']  # adjusted closes

rows = []
for i, ts in enumerate(timestamps):
    rows.append({
        'date':     datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d'),
        'open':     round(quotes['open'][i], 4) if quotes['open'][i] else None,
        'high':     round(quotes['high'][i], 4) if quotes['high'][i] else None,
        'low':      round(quotes['low'][i], 4) if quotes['low'][i] else None,
        'close':    round(quotes['close'][i], 4) if quotes['close'][i] else None,
        'volume':   quotes['volume'][i],
        'adjclose': round(adjclose[i], 4) if adjclose[i] else None,
    })

for r in rows[:3]:
    print(r)
# {'date': '2026-04-14', 'open': ..., 'high': ..., 'low': ..., 'close': 352.42, 'volume': ..., 'adjclose': ...}
```

Individual OHLCV values can be `None` for incomplete candles (e.g. current day's candle if market is mid-session). Always guard with `if value else None`.

### Interval and range options

```python
# interval controls candle size; range controls how far back
# Confirmed valid ranges (from meta['validRanges']):
# '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'

# Common interval + range combos:
# Intraday (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h) — only available for recent data (≤60d)
# Daily (1d) — all ranges
# Weekly (1wk) — all ranges
# Monthly (1mo) — all ranges

data_1h = json.loads(http_get(
    "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1h&range=5d",
    headers=headers
))
print("Hourly bars:", len(data_1h['chart']['result'][0]['timestamp']))  # ~36 for 5d

data_1wk = json.loads(http_get(
    "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1wk&range=1y",
    headers=headers
))
print("Weekly bars:", len(data_1wk['chart']['result'][0]['timestamp']))  # ~54 for 1y

# Max history (all available data)
data_max = json.loads(http_get(
    "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1mo&range=max",
    headers=headers
))
```

### ETF and crypto

```python
import json

headers = {"User-Agent": "Mozilla/5.0"}

# ETF — same endpoint, instrumentType will be "ETF"
spy = json.loads(http_get(
    "https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=1d",
    headers=headers
))
print("SPY:", spy['chart']['result'][0]['meta']['regularMarketPrice'])   # 710.14
print("Type:", spy['chart']['result'][0]['meta']['instrumentType'])      # "ETF"

# Crypto — append -USD (or -EUR, -GBP, etc.)
btc = json.loads(http_get(
    "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?interval=1d&range=1d",
    headers=headers
))
print("BTC-USD:", btc['chart']['result'][0]['meta']['regularMarketPrice'])  # 76298.73

eth = json.loads(http_get(
    "https://query1.finance.yahoo.com/v8/finance/chart/ETH-USD?interval=1d&range=1d",
    headers=headers
))
print("ETH-USD:", eth['chart']['result'][0]['meta']['regularMarketPrice'])
```

### Forex

```python
import json

headers = {"User-Agent": "Mozilla/5.0"}

# Forex pairs — append =X to the pair
eurusd = json.loads(http_get(
    "https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=1d&range=5d",
    headers=headers
))
print("EUR/USD:", eurusd['chart']['result'][0]['meta']['regularMarketPrice'])  # 1.1767

# Other pairs: GBPUSD=X, USDJPY=X, AUDUSD=X
```

### Symbol search / autocomplete

```python
import json

headers = {"User-Agent": "Mozilla/5.0"}

search = json.loads(http_get(
    "https://query1.finance.yahoo.com/v1/finance/search"
    "?q=tesla&quotesCount=5&newsCount=0",
    headers=headers
))

for q in search['quotes']:
    print(q['symbol'], q.get('shortname'), q.get('quoteType'), q.get('exchDisp'))
    # "TSLA"   "Tesla, Inc."           "EQUITY"  "NASDAQ"
    # "TL0.F"  "Tesla Inc.  R"         "EQUITY"  "Frankfurt"

# Fields per result:
# exchange, shortname, quoteType, symbol, index, score, typeDisp,
# longname, exchDisp, sector, sectorDisp, industry, industryDisp,
# dispSecIndFlag, isYahooFinance
```

### Parallel multi-symbol fetch

```python
import json
from concurrent.futures import ThreadPoolExecutor

headers = {"User-Agent": "Mozilla/5.0"}

def fetch_price(symbol):
    try:
        data = json.loads(http_get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d",
            headers=headers
        ))
        return symbol, data['chart']['result'][0]['meta']['regularMarketPrice']
    except Exception as e:
        return symbol, None

symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "SPY", "BTC-USD"]
with ThreadPoolExecutor(max_workers=4) as ex:
    results = dict(ex.map(lambda s: fetch_price(s), symbols))

for sym, price in results.items():
    print(sym, price)
```

---

## Gotchas

- **`User-Agent: Mozilla/5.0` is required** — the default in `http_get` works. Without it, many requests return 403 or redirect to consent page.

- **Bad symbol returns HTTP 404** — not a JSON error object. Wrap in try/except:
  ```python
  try:
      data = json.loads(http_get("https://query1.finance.yahoo.com/v8/finance/chart/XXXX?interval=1d&range=1d", headers=headers))
  except Exception as e:
      print("Symbol not found:", e)  # "HTTP Error 404: Not Found"
  ```

- **OHLCV values can be `None`** — especially for incomplete current-day candles and market holidays. Always guard: `round(v, 2) if v else None`.

- **`regularMarketTime` is a Unix timestamp** — convert with `datetime.utcfromtimestamp(meta['regularMarketTime'])`.

- **`v10/quoteSummary` requires a crumb** — this endpoint returns balance sheet, income statement, analyst estimates, earnings, etc. but requires a `crumb` query parameter extracted from a real browser session cookie (`CSRF` flow). From `http_get` you get `401 Unauthorized`. If fundamental data is needed, use a browser: `goto("https://finance.yahoo.com")`, let the page load, then extract the crumb from the cookie or page source.

- **`query1` vs `query2`** — both are Yahoo Finance API servers. `query1.finance.yahoo.com` is confirmed working. `query2.finance.yahoo.com` is a mirror and can be used as fallback.

- **Intraday data is only available for recent windows** — `interval=1m` only works for `range=1d`. `interval=1h` works for `range≤5d`. Longer ranges with minute intervals return an error or fall back to daily.

- **Adjusted close is in `indicators.adjclose`** — a separate list from `indicators.quote`. It may be missing for some instruments (e.g. crypto). Check `result['indicators'].get('adjclose')` before accessing.

- **`hasPrePostMarketData`** — when `True`, timestamps may include pre/post market candles. Filter by `currentTradingPeriod.regular.start/end` unix timestamps to get only regular session data.

- **No official rate limit documented** — in practice, moderate parallel fetching (4–8 concurrent) works without issues. Excessive scraping (100+ rapid calls) may trigger temporary 429 responses. Add `time.sleep(0.1)` between sequential calls for safety.

- **`firstTradeDate` is negative for old stocks** — Apple's first trade date returns a large negative Unix timestamp (pre-1970 epoch). Don't rely on it for display without clamping.
