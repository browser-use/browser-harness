# TradingView — Scraping & Data Extraction

`https://www.tradingview.com` — charting platform with multiple internal REST APIs. Stock/crypto/forex screener and symbol search work without auth. Use `http_get` or raw `urllib` for all workflows except JS-rendered chart pages.

## Do this first

**Use the scanner API for bulk screener data — one POST, no browser, full column control.**

```python
import json, urllib.request

def tv_scan(payload, market="america"):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://scanner.tradingview.com/{market}/scan",
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())
```

**No auth, no Referer, no cookies required for the scanner.** Responses arrive in ~200ms.

## Common workflows

### Top stocks by market cap (screener)

```python
import json, urllib.request

payload = {
    "filter": [],
    "options": {"lang": "en"},
    "columns": ["name", "close", "change", "volume", "market_cap_basic"],
    "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
    "range": [0, 10]   # [start, end] — half-open, so this returns rows 0–9
}

data = json.dumps(payload).encode()
req = urllib.request.Request(
    "https://scanner.tradingview.com/america/scan",
    data=data,
    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
)
with urllib.request.urlopen(req, timeout=20) as r:
    resp = json.loads(r.read())

# resp["totalCount"] = 19549 (all US-listed instruments)
# resp["data"] is a list of {"s": "NASDAQ:NVDA", "d": [col0, col1, ...]}
# "d" values align positionally with "columns" in the payload

cols = payload["columns"]
for item in resp["data"]:
    row = dict(zip(cols, item["d"]))
    symbol = item["s"]   # e.g. "NASDAQ:AAPL"
    print(symbol, row["close"], row["change"], row["market_cap_basic"])
# NASDAQ:NVDA  201.68  1.68  4900823822021.0
# NASDAQ:AAPL  270.23  2.59  3967284528489.0
# ...
```

**Critical**: `"d"` is a plain positional array — index 0 = columns[0], index 1 = columns[1], etc. There are no keys in the row data itself.

### Pagination

```python
# Page 1: range [0, 20]
# Page 2: range [20, 40]
payload["range"] = [20, 40]
```

### Filtering stocks

```python
payload = {
    "filter": [
        {"left": "market_cap_basic", "operation": "greater", "right": 10_000_000_000},
        {"left": "volume",           "operation": "greater", "right": 5_000_000},
        {"left": "change",           "operation": "in_range", "right": [2, 10]},
        {"left": "exchange",         "operation": "equal",   "right": "NASDAQ"},
        {"left": "sector",           "operation": "equal",   "right": "Electronic Technology"},
    ],
    "columns": ["name", "close", "change", "volume", "market_cap_basic",
                "description", "sector", "industry"],
    "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
    "range": [0, 20]
}
```

Valid filter operations: `greater`, `less`, `equal`, `in_range` (right = [min, max]), `match` (substring on `name`).

Sector names use TradingView taxonomy (not GICS). Confirmed working values:
- `"Electronic Technology"` — NVDA, AAPL, TSM
- `"Technology Services"` — MSFT, GOOGL, META
- `"Finance"`, `"Health Technology"`, `"Consumer Non-Durables"`

### Full list of tested valid column names

```python
# Price & volume
"name"                     # ticker (e.g. "AAPL")
"description"              # full name ("Apple Inc.")
"close"                    # last price
"open", "high", "low"
"volume"
"change"                   # % change today
"change_abs"               # absolute price change
"change|1M"                # 1-month % change (also: |6M, |1Y)
"High.1M", "High.6M"       # period high
"High.All", "Low.All"      # all-time high/low
"price_52_week_high"       # confirmed works
"price_52_week_low"        # confirmed works
"premarket_change"         # pre-market %
"postmarket_change"        # after-hours %
"gap"                      # overnight gap %
"change_from_open_abs"     # intraday move from open
"average_volume_10d_calc"  # 10-day avg volume
"relative_volume_10d_calc" # relative volume vs 10-day avg
"relative_volume_intraday|5"  # intraday relative vol (5m bars)

# Fundamentals
"market_cap_basic"          # market cap in USD
"earnings_per_share_diluted_ttm"  # EPS TTM
"price_earnings_ttm"        # P/E TTM
"P/E"                       # P/E (snapshot)
"dividends_yield"           # dividend yield %
"beta_1_year"               # beta
"float_shares_outstanding"  # float shares

# Technical ratings & indicators
"Recommend.All"   # composite rating: -1 (strong sell) to +1 (strong buy)
"RSI"             # RSI 14
"MACD.macd"       # MACD line

# Classification
"sector", "industry", "country", "exchange"
"type"    # "stock", "fund", "dr" (depository receipt), etc.

# NOTE: "52_week_high" / "52_week_low" are INVALID — use "price_52_week_high" / "price_52_week_low"
# NOTE: "EPS_diluted_net" is INVALID — use "earnings_per_share_diluted_ttm"
```

Bad columns return HTTP 400 with `{"error": "Unknown field \"X\""}`.

### Other scanner markets

```python
# market argument options (confirmed working):
# "america"  — US equities (19,549 instruments)
# "crypto"   — crypto across exchanges (56,455 instruments)
# "forex"    — FX pairs (6,401 instruments)
# "futures"  — futures (53,947 instruments)

# Crypto example
payload = {
    "filter": [],
    "columns": ["name", "close", "change", "volume", "market_cap_calc"],
    "sort": {"sortBy": "market_cap_calc", "sortOrder": "desc"},
    "range": [0, 10]
}
resp = tv_scan(payload, market="crypto")
# Returns BTC, ETH, etc. across Binance, Bybit, OKX...
```

### Symbol search (requires Origin header)

```python
import json, urllib.request

def symbol_search(query, exchange="", type_filter="", limit=50):
    url = (
        f"https://symbol-search.tradingview.com/symbol_search/v3/"
        f"?text={query}&hl=1&exchange={exchange}&lang=en"
        f"&search_type={type_filter or 'undefined'}&domain=production"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Origin": "https://www.tradingview.com",   # REQUIRED — 403 without this
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

result = symbol_search("AAPL")
# result["symbols_remaining"] = 137
# result["symbols"] = list of up to 50 matches
# result["symbols"][0] keys:
#   symbol, description, type, exchange, country, currency_code,
#   cusip, isin, cik_code, logoid, provider_id, source_id,
#   is_primary_listing, typespecs
```

**Gotcha**: `symbol-search.tradingview.com` requires `Origin: https://www.tradingview.com`. Referer alone is not enough. The scanner API does NOT need Origin or Referer.

Filter by exchange and type:

```python
# Exact match on NASDAQ:AAPL
result = symbol_search("AAPL", exchange="NASDAQ", type_filter="stock")
# Returns 1 result — exact symbol only when exchange is specified
```

### News headlines for a symbol

```python
import json, urllib.request

def get_news(symbol, limit=20):
    # symbol format: "NASDAQ:AAPL", "NYSE:TSLA"
    url = (
        f"https://news-headlines.tradingview.com/v2/view/headlines/symbol"
        f"?symbol={symbol}&client=web&streaming=false&lang=en&limit={limit}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    return data["items"]  # list of news items

items = get_news("NASDAQ:AAPL", limit=10)
# item keys: id, title, provider, sourceLogoId, published (unix ts),
#            source, urgency, link, permission, relatedSymbols, storyPath
# example:
# items[0]["title"]     = "Apple Clears Major Legal Hurdle..."
# items[0]["published"] = 1776472317  (unix timestamp)
# items[0]["link"]      = "https://stocktwits.com/..."
# items[0]["relatedSymbols"] = [{"symbol": "NASDAQ:AAPL", "logoid": "apple"}]
```

No auth or special headers needed. Returns up to 200 items per request.

### Published trading ideas feed

```python
import json, urllib.request

def get_ideas(sort="trending", page=1, symbol=None):
    # Valid sort values (others return 400):
    # "trending", "recent", "latest_popular", "week_popular",
    # "suggested", "recent_extended", "picked_time"
    url = f"https://www.tradingview.com/api/v1/ideas/?lang=en&sort={sort}&page={page}"
    if symbol:
        url += f"&symbol={symbol}"  # e.g. "NASDAQ:AAPL"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

data = get_ideas("trending")
# data["count"]      = 1000 (always 1000 — soft cap)
# data["page_size"]  = 20
# data["page_count"] = 50
# data["next"]       = "https://www.tradingview.com/api/v1/ideas/?page=2"
# data["results"]    = list of idea objects

idea = data["results"][0]
# idea keys: id, name, description, created_at, chart_url, views_count,
#            likes_count, comments_count, is_video, is_education, is_hot,
#            symbol (dict with name/exchange/type/interval/direction),
#            user (dict with username/is_pro/badges), image (big/middle URLs)
# idea["symbol"]["direction"]: 1=long, 2=short, 0=neutral

# Filter by symbol:
aapl_ideas = get_ideas(symbol="NASDAQ:AAPL")
```

## API summary table

| Endpoint | Auth | Headers needed | Speed |
|---|---|---|---|
| `scanner.tradingview.com/{market}/scan` | None | None | ~200ms |
| `symbol-search.tradingview.com/symbol_search/v3/` | None | `Origin: https://www.tradingview.com` | ~150ms |
| `symbol-search.tradingview.com/symbol_search/` (v1) | None | `Origin: https://www.tradingview.com` | ~100ms |
| `news-headlines.tradingview.com/v2/view/headlines/symbol` | None | None | ~400ms |
| `www.tradingview.com/api/v1/ideas/` | None | None | ~300ms |
| `data.tradingview.com/quotes/` | None | None | **Dead** — connection refused |
| `economic-calendar.tradingview.com/events` | Yes | — | HTTP 403 |

## Gotchas

**Scanner `range` is half-open**: `[0, 10]` returns rows 0–9 (10 rows total). `[10, 20]` for the next page.

**Column order is critical**: The `"d"` array in each result row is positional — it exactly mirrors your `"columns"` array. Always zip them: `dict(zip(columns, item["d"]))`.

**`data.tradingview.com/quotes/` is dead**: The URL `https://data.tradingview.com/quotes/?symbols=NASDAQ:AAPL` closes the connection without a response. Use the scanner API instead for real-time quotes.

**Scanner needs no Referer**: `scanner.tradingview.com` works with just `User-Agent`. The symbol-search subdomain checks `Origin` (CORS enforcement on the server side).

**Symbol search highlights**: The v3 endpoint wraps matched text in `<em>` tags (e.g. `"<em>AAPL</em>"`). Strip them: `re.sub(r'</?em>', '', symbol["symbol"])`.

**Ideas sort validation**: Only specific values work. `"sort=popular"` returns 400. Use `"trending"`, `"recent"`, `"latest_popular"`, `"week_popular"`, `"suggested"`.

**Ideas count cap**: The API always reports `count=1000` regardless of actual corpus size. With `page_size=20`, max pages is 50.

**Scanner server is AWS CloudFront** (`X-Amz-Cf-Pop` header) with a custom `Server: tv` — no Cloudflare. No anti-bot on the scanner subdomain. Main `www.tradingview.com` is a React SPA with `window.initData = {}` (empty — no embedded data). All data is loaded via API calls after hydration.

**Rate limits**: No 429s observed in testing. 5 concurrent scanner calls complete in ~1s. Symbol search returns `symbols_remaining` in the response (counts against some quota — varies 90–180 across calls but never blocks). Observed no blocking after 15 rapid calls in a row.

**Sector names**: Use TradingView's own taxonomy, not GICS. "Technology" does not exist — use `"Electronic Technology"` (hardware/semis) or `"Technology Services"` (software/internet).

## When to use the browser

The charting UI (`/chart/`), symbol detail pages (`/symbols/NASDAQ-AAPL/`), and the ideas page (`/ideas/`) are React SPAs — their visible data comes from the APIs above, not embedded HTML. Use browser + JS extraction only if you need visual chart screenshots or data from auth-gated pages (watchlists, portfolio, paper trading).

```python
# Only if you need a chart screenshot:
goto("https://www.tradingview.com/chart/?symbol=NASDAQ:AAPL")
wait_for_load()
wait(3)   # chart renders asynchronously after readyState
screenshot("/tmp/aapl_chart.png", full=False)
```
