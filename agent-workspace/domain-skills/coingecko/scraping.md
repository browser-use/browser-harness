# CoinGecko — Data Extraction

`https://api.coingecko.com/api/v3` — no API key needed for free tier. Pure JSON REST API, no browser required.

## Do this first

**Use the API directly with `http_get` — no browser, no parsing, fully structured JSON.**

```python
import json
data = json.loads(http_get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"))
print(data['bitcoin']['usd'])   # 76286
```

**Rate limit is tight: ~3 calls per minute on the free tier.** The API returns HTTP 429 with `Retry-After: 60` when you exceed it. Always add `time.sleep(5)` between calls in a loop. Confirmed: rapid-fire calls hit 429 on call 3-4 with no delay; with 5s gaps you stay safe.

## Rate limits (confirmed live)

- **Free tier**: ~3 calls/minute per IP (no API key)
- **429 response**: includes `Retry-After: 60` header — wait 60 seconds before retrying
- **Coin ID lookup** (`/coins/list`) counts against the limit — call it once and cache
- **`/ping`** still counts — don't use it as a keep-alive

```python
import time, urllib.error, json

def safe_get(url, retries=2):
    for attempt in range(retries + 1):
        try:
            return json.loads(http_get(url))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                print(f"Rate limited, sleeping 65s...")
                time.sleep(65)
            else:
                raise
```

## Coin ID vs symbol — critical distinction

**IDs are kebab-case strings, not ticker symbols.** The API ignores symbols entirely.

| Intent | Wrong | Right |
|--------|-------|-------|
| Bitcoin price | `ids=BTC` | `ids=bitcoin` |
| Solana price | `ids=SOL` | `ids=solana` |
| Ethereum | `ids=ETH` | `ids=ethereum` |

- Unknown or wrong IDs return an **empty `{}` dict** — no error, no warning
- Symbols are not unique: 17+ coins share the symbol `sol` (bridged versions, wrapped, etc.)
- Use `/coins/list` to resolve symbol → id, or just know the canonical id

```python
# Resolve symbol to id
coins_list = json.loads(http_get("https://api.coingecko.com/api/v3/coins/list"))
# 17,564 entries as of April 2026
# Each: {'id': 'bitcoin', 'symbol': 'btc', 'name': 'Bitcoin'}
sol_coins = [c for c in coins_list if c['symbol'].lower() == 'sol']
# Returns 5+ entries — pick by name to get the real Solana: id='solana'
```

## Common workflows

### Simple price (one or many coins)

```python
import json
data = json.loads(http_get(
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum,solana"
    "&vs_currencies=usd,eur"
    "&include_market_cap=true"
    "&include_24hr_change=true"
))
for coin, info in data.items():
    print(f"{coin}: ${info['usd']:,.0f} | 24h: {info['usd_24h_change']:.1f}% | MCap: ${info['usd_market_cap']/1e9:.1f}B")
# bitcoin: $76,286 | 24h: 1.4% | MCap: $1528.0B
# ethereum: $2,361 | 24h: 0.8% | MCap: $284.9B
# solana: $87 | 24h: -1.0% | MCap: $50.2B
```

Response keys for each coin (when all flags enabled):
`usd`, `usd_market_cap`, `usd_24h_change`, `eur`, `eur_market_cap`, `eur_24h_change`

### Top coins by market cap (paginated)

```python
import json
data = json.loads(http_get(
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd"
    "&order=market_cap_desc"
    "&per_page=10"       # max 250
    "&page=1"            # 1-indexed; page=2 gives ranks 11-20 etc.
    "&sparkline=false"
    "&price_change_percentage=1h,7d,30d"  # optional extra columns
))
for c in data:
    print(f"#{c['market_cap_rank']} {c['symbol'].upper()} ${c['current_price']:,.2f} | {c['price_change_percentage_24h']:.1f}%")
# #1 BTC $76,281.00 | 1.4%
# #2 ETH $2,360.45 | 0.8%
```

Full fields per entry: `id`, `symbol`, `name`, `image`, `current_price`, `market_cap`, `market_cap_rank`, `fully_diluted_valuation`, `total_volume`, `high_24h`, `low_24h`, `price_change_24h`, `price_change_percentage_24h`, `market_cap_change_24h`, `market_cap_change_percentage_24h`, `circulating_supply`, `total_supply`, `max_supply`, `ath`, `ath_change_percentage`, `ath_date`, `atl`, `atl_change_percentage`, `atl_date`, `roi`, `last_updated`

Extra columns added by `price_change_percentage=1h,7d,30d`: `price_change_percentage_1h_in_currency`, `price_change_percentage_7d_in_currency`, `price_change_percentage_30d_in_currency`

Pagination: use `page=2`, `page=3`, etc. with `per_page` up to 250. Results are 1-indexed — page 2 with per_page=5 returns ranks 6–10.

### Coin detail (full metadata)

```python
import json
data = json.loads(http_get(
    "https://api.coingecko.com/api/v3/coins/bitcoin"
    "?localization=false"    # skip 40+ language translations
    "&tickers=false"         # skip exchange ticker list (can be huge)
    "&market_data=true"
    "&community_data=false"
    "&developer_data=false"
))
print(data['name'])                                    # Bitcoin
print(data['symbol'])                                  # btc
print(data['market_cap_rank'])                         # 1
print(data['market_data']['current_price']['usd'])     # 76279
print(data['market_data']['ath']['usd'])               # 126080
print(data['market_data']['ath_date']['usd'])          # 2025-10-06T18:57:42.558Z
print(data['market_data']['circulating_supply'])       # 20017459.0
print(data['description']['en'][:200])
```

Top-level keys: `id`, `symbol`, `name`, `web_slug`, `asset_platform_id`, `platforms`, `categories`, `description`, `links`, `image`, `genesis_date`, `sentiment_votes_up_percentage`, `market_cap_rank`, `market_data`, `last_updated`

`market_data` sub-keys include: `current_price`, `ath`, `ath_change_percentage`, `ath_date`, `atl`, `atl_change_percentage`, `atl_date`, `market_cap`, `fully_diluted_valuation`, `total_volume`, `high_24h`, `low_24h`, `price_change_percentage_24h`, `price_change_percentage_7d`, `price_change_percentage_14d`, `price_change_percentage_30d`, `price_change_percentage_60d`, `price_change_percentage_200d`, `price_change_percentage_1y`, `circulating_supply`, `total_supply`, `max_supply`

All price/market fields are objects keyed by currency code: `data['market_data']['current_price']['usd']`, `['eur']`, `['btc']`, etc.

### Historical OHLCV

```python
import json
# OHLCV candles: granularity auto-determined by `days`
# 1d = 30-min candles, 7d = 4-hr candles, 14d+ = daily candles
data = json.loads(http_get(
    "https://api.coingecko.com/api/v3/coins/ethereum/ohlc?vs_currency=usd&days=7"
))
print(len(data))         # 42 candles for 7-day window
print(data[-1])          # [1776499200000, 2407.32, 2412.96, 2402.21, 2405.03]
#                         [timestamp_ms,   open,    high,    low,     close]

# Convert timestamp:
import datetime
ts_ms = data[-1][0]
dt = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.timezone.utc)
```

`days` options: `1`, `7`, `14`, `30`, `90`, `180`, `365`, `max`

### Market chart (price + volume + market cap time series)

```python
import json
# interval='daily' gives one point per day; omit for auto (hourly for <=90 days)
chart = json.loads(http_get(
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    "?vs_currency=usd&days=7&interval=daily"
))
# Keys: 'prices', 'market_caps', 'total_volumes'
# Each is a list of [timestamp_ms, value]
print(len(chart['prices']))           # 8 points for 7-day daily
print(chart['prices'][-1])            # [1776508393000, 76286.699...]
print(chart['total_volumes'][-1])     # [1776508393000, 80459560788.47...]
```

### Market chart by date range

```python
import json, time
now = int(time.time())
thirty_days_ago = now - 30 * 86400
chart = json.loads(http_get(
    f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
    f"?vs_currency=usd&from={thirty_days_ago}&to={now}"
))
# Granularity: <1 day → minutely, 1-90 days → hourly, >90 days → daily
print(len(chart['prices']))    # 174 points for 7-day range (hourly)
```

### Search

```python
import json
results = json.loads(http_get("https://api.coingecko.com/api/v3/search?query=solana"))
# Top-level keys: 'coins', 'exchanges', 'icos', 'categories', 'nfts'
for c in results['coins'][:3]:
    print(f"{c['id']} | {c['symbol']} | rank {c['market_cap_rank']}")
# solana | SOL | rank 7
# solana-name-service | SNS | rank 1902
```

Search returns coins ordered by relevance, not market cap. First result is usually the canonical coin.

### Trending (top 7 searched in last 24h)

```python
import json
trending = json.loads(http_get("https://api.coingecko.com/api/v3/search/trending"))
# Top-level keys: 'coins', 'nfts', 'categories'
for item in trending['coins']:
    c = item['item']
    print(f"{c['name']} ({c['symbol']}) #{c['market_cap_rank']}")
# Item keys: id, coin_id, name, symbol, market_cap_rank, thumb, small, large,
#            slug, price_btc, score, data
```

`data` sub-object includes sparkline image URL, price/volume/market cap info if available.

### Global market overview

```python
import json
global_data = json.loads(http_get("https://api.coingecko.com/api/v3/global"))
gd = global_data['data']
print(f"Total market cap: ${gd['total_market_cap']['usd']/1e12:.2f}T")   # $2.66T
print(f"24h volume: ${gd['total_volume']['usd']/1e9:.1f}B")              # $156.6B
print(f"BTC dominance: {gd['market_cap_percentage']['btc']:.1f}%")       # 57.3%
print(f"Active coins: {gd['active_cryptocurrencies']}")                   # 17,564
print(f"Active exchanges: {gd['markets']}")                               # 1,475
```

### Coin categories (market cap by sector)

```python
import json
cats = json.loads(http_get(
    "https://api.coingecko.com/api/v3/coins/categories?order=market_cap_desc"
))
# 691 categories as of April 2026
for cat in cats[:5]:
    print(f"{cat['name']}: ${cat['market_cap']/1e9:.1f}B | 24h: {cat['market_cap_change_24h']:.1f}%")
# Smart Contract Platform: $2204.8B | 24h: 0.9%
# Layer 1 (L1): $2171.5B | 24h: 1.1%

# Category keys: id, name, market_cap, market_cap_change_24h, content,
#                top_3_coins_id, top_3_coins, volume_24h, updated_at
```

### Token price by contract address (ERC-20 and other chains)

```python
import json
# Platform IDs: ethereum, binance-smart-chain, polygon-pos, avalanche, solana, etc.
token = json.loads(http_get(
    "https://api.coingecko.com/api/v3/simple/token_price/ethereum"
    "?contract_addresses=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC
    "&vs_currencies=usd"
))
print(token)
# {'0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': {'usd': 0.999861}}
# Key is the lowercased contract address
```

## vs_currencies options

63 currencies supported (confirmed live). Common ones:

**Fiat**: `usd`, `eur`, `gbp`, `jpy`, `aud`, `cad`, `chf`, `cny`, `inr`, `krw`, `brl`, `mxn`, `sgd`, `hkd`, `nok`, `sek`, `dkk`, `nzd`, `zar`, `thb`, `try`, `aed`, `sar`, `myr`, `php`, `idr`, `pln`, `czk`, `huf`, `ron`

**Crypto**: `btc`, `eth`, `ltc`, `bch`, `bnb`, `eos`, `xrp`, `xlm`, `link`, `dot`, `yfi`, `sol`

**Commodities**: `xag` (silver), `xau` (gold)

Get the full list:
```python
currencies = json.loads(http_get("https://api.coingecko.com/api/v3/simple/supported_vs_currencies"))
# Returns list of 63 strings
```

## Endpoints that require Pro API (return HTTP 401)

- `/coins/{id}/history?date=DD-MM-YYYY` — historical price on a specific date
- `/coins/markets` with `category=` filter (the parameter is silently ignored, not 401)
- `/coins/{id}/contract/{address}` — full contract token details

Free tier alternatives:
- For historical price on date: use `/market_chart/range` with a narrow time window
- For category filtering: fetch `/coins/markets` unfiltered and filter client-side using `id` from `/coins/categories`

## Ping / health check

```python
import json
ping = json.loads(http_get("https://api.coingecko.com/api/v3/ping"))
print(ping)   # {'gecko_says': '(V3) To the Moon!'}
```

Note: ping still counts against the rate limit. Don't use it to check if a 429 has resolved — just wait 65 seconds and retry your actual call.

## Gotchas

- **Rate limit is much stricter than advertised** — The official docs say "30 calls/min" but in practice you get 429 on call 3-4 with no delay between calls. Observed `Retry-After: 60` in the response header. Treat it as "3 calls/minute, wait 65s on 429." Using `time.sleep(5)` between calls in a loop is safe.

- **Unknown coin IDs return `{}`, not an error** — `?ids=BTC` (uppercase) and `?ids=not_a_real_coin` both return an empty dict `{}`. Always check that the key you expect exists before accessing it.

- **Symbol lookup requires `/coins/list` + client-side filter** — There's no "get by symbol" endpoint. Multiple coins share any given symbol. After fetching the list (17,564 entries), filter by `symbol` and pick by `name`.

- **Coin ID casing matters** — IDs are always lowercase kebab-case: `bitcoin`, `ethereum`, `shiba-inu`. Uppercase or camelCase will silently return `{}`.

- **OHLCV granularity is automatic** — The `days` parameter determines candle size automatically: `1` → 30-min candles, `7`/`14` → 4-hr candles, `30`+  → daily candles. You cannot override this on the free tier.

- **`interval=daily` in market_chart affects point count** — Without `interval=daily`, a 7-day window returns hourly data (~168 points). With it, you get ~8 points. Choose based on whether you need resolution or summary.

- **market_chart timestamps are in milliseconds** — Divide by 1000 for standard Unix time: `datetime.fromtimestamp(ts / 1000)`.

- **`/coins/list` is expensive (rate-limit-wise)** — It returns 17,564 entries and costs one API call. Fetch once, store in a variable, filter locally. Don't call it in a loop.

- **Pagination is 1-indexed** — `page=1` returns items 1–N, `page=2` returns N+1–2N. `page=0` returns the same as `page=1` (it doesn't error).

- **`per_page` max is 250** — Requesting more than 250 per page silently returns 250. To get the full top-500, make two calls: `page=1&per_page=250` then `page=2&per_page=250`.

- **Contract address keys are lowercased** — When using `/simple/token_price`, the response key is the lowercased contract address regardless of what case you sent. Always call `.lower()` before using addresses as dict keys.

- **`tickers=false` is important for `/coins/{id}`** — Without it, the response includes a massive list of exchange tickers that can make the payload very large and slow to parse. Always set `tickers=false` unless you specifically need exchange data.

- **ETH priced against BTC is supported** — `vs_currencies=btc` works: `ethereum` returns `{'btc': 0.03095861}`. Crypto-to-crypto pairs work the same as fiat pairs.
