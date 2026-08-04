# CryptoCompare — Data Extraction

`https://min-api.cryptocompare.com` — free-tier REST API, no API key needed for the endpoints documented here. Pure JSON, no browser required.

## Do this first

**Use `http_get` directly — no browser, no parsing, structured JSON.**

```python
import json
data = json.loads(http_get("https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD"))
print(data['USD'])   # 75576.61
```

**No API key needed for price, OHLCV, top-coins, exchanges, and pairs endpoints.** Confirmed 50+ rapid sequential calls with no rate-limit errors — no delay needed between calls on the free tier.

**Symbols are uppercase** (`BTC`, `ETH`, `SOL`), unlike CoinGecko which uses kebab-case IDs.

## Rate limits (confirmed live)

- **Free tier**: no observed throttling after 50+ rapid sequential calls — no `Retry-After`, no 429s
- **Response body `RateLimit`**: always `{}` (empty) on free-tier calls — not used for counting
- **Cache**: responses include `cache-control: public, max-age=10` — safe to hammer
- No `time.sleep()` needed between calls (unlike CoinGecko which hard-limits at ~3/min)

## Endpoints that require API key (return `{"Response":"Error","Message":"You need a valid auth key..."}`)

- `/data/social/coin/latest` — Reddit/Twitter/GitHub stats
- `/data/blockchain/histo/day` — on-chain metrics (hashrate, difficulty, tx count)
- `/data/news/` and `/data/v2/news/` — crypto news articles
- `/data/ob/l2/snapshot` — order book data

**The above return HTTP 200 but with an error body** — no exception is raised. Always check `d.get('Response') == 'Error'` if you're unsure.

## Common workflows

### Simple price (one coin, multiple target currencies)

```python
import json
data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/price"
    "?fsym=BTC&tsyms=USD,EUR,GBP,ETH,BNB"
))
print(data)
# {'USD': 75576.61, 'EUR': 64259.31, 'GBP': 55903.09, 'ETH': 32.23, 'BNB': 120.34}
```

`fsym` = from symbol (single coin). `tsyms` = comma-separated target currencies (fiat or crypto).

### Multi-coin prices (batch lookup)

```python
import json
data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/pricemulti"
    "?fsyms=BTC,ETH,SOL,BNB,XRP&tsyms=USD,EUR,BTC"
))
for coin, prices in data.items():
    print(f"{coin}: ${prices['USD']:,.2f} | {prices['EUR']:,.2f} EUR | {prices['BTC']:.6f} BTC")
# BTC: $75,576.33 | 64,259.31 EUR | 1.000000 BTC
# ETH: $2,344.78  | 1,993.43 EUR  | 0.031040 BTC
# SOL: $85.71     | 72.86 EUR     | 0.001134 BTC
```

### Full price details (OHLCV + market cap + supply)

```python
import json
data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/pricemultifull"
    "?fsyms=BTC,ETH&tsyms=USD"
))
raw = data['RAW']['BTC']['USD']   # raw numeric values
disp = data['DISPLAY']['BTC']['USD']  # pre-formatted strings (e.g. "$ 75,585.8")

print(f"Price:          ${raw['PRICE']:,.2f}")
print(f"24h Change:     {raw['CHANGEPCT24HOUR']:+.2f}%  (${raw['CHANGE24HOUR']:+,.2f})")
print(f"24h High/Low:   ${raw['HIGH24HOUR']:,.2f} / ${raw['LOW24HOUR']:,.2f}")
print(f"Day High/Low:   ${raw['HIGHDAY']:,.2f} / ${raw['LOWDAY']:,.2f}")
print(f"Hour OHLC:      O={raw['OPENHOUR']:,.2f} H={raw['HIGHHOUR']:,.2f} L={raw['LOWHOUR']:,.2f}")
print(f"Volume 24h:     {raw['VOLUME24HOUR']:,.4f} BTC (${raw['VOLUME24HOURTO']/1e9:.2f}B)")
print(f"Market Cap:     ${raw['MKTCAP']/1e9:.1f}B")
print(f"Supply:         {raw['CIRCULATINGSUPPLY']:,.0f} BTC")
print(f"Last exchange:  {raw['LASTMARKET']}")
print(f"Image URL:      https://www.cryptocompare.com{raw['IMAGEURL']}")
# Formatted version (no math needed):
print(f"Price (display):{disp['PRICE']}")   # "$ 75,585.8"
print(f"MCap (display): {disp['MKTCAP']}")  # "$ 1,513.06 B"
```

All `RAW` fields (confirmed live):
`TYPE, MARKET, FROMSYMBOL, TOSYMBOL, FLAGS, LASTMARKET, MEDIAN, TOPTIERVOLUME24HOUR, TOPTIERVOLUME24HOURTO, LASTTRADEID, PRICE, LASTUPDATE, LASTVOLUME, LASTVOLUMETO, VOLUMEHOUR, VOLUMEHOURTO, OPENHOUR, HIGHHOUR, LOWHOUR, VOLUMEDAY, VOLUMEDAYTO, OPENDAY, HIGHDAY, LOWDAY, VOLUME24HOUR, VOLUME24HOURTO, OPEN24HOUR, HIGH24HOUR, LOW24HOUR, CHANGE24HOUR, CHANGEPCT24HOUR, CHANGEDAY, CHANGEPCTDAY, CHANGEHOUR, CHANGEPCTHOUR, CONVERSIONTYPE, CONVERSIONSYMBOL, CONVERSIONLASTUPDATE, SUPPLY, MKTCAP, MKTCAPPENALTY, CIRCULATINGSUPPLY, CIRCULATINGSUPPLYMKTCAP, TOTALVOLUME24H, TOTALVOLUME24HTO, TOTALTOPTIERVOLUME24H, TOTALTOPTIERVOLUME24HTO, IMAGEURL`

`DISPLAY` mirrors all fields but as pre-formatted strings (e.g. `"$ 75,585.8"`, `"$ 1,513.06 B"`).

### Historical OHLCV — daily candles

```python
import json, datetime

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/v2/histoday"
    "?fsym=BTC&tsym=USD&limit=7"   # limit = number of candles returned
))
candles = data['Data']['Data']     # list of dicts

for c in candles:
    dt = datetime.datetime.fromtimestamp(c['time'], tz=datetime.timezone.utc).strftime('%Y-%m-%d')
    print(f"{dt}: O={c['open']:,.0f} H={c['high']:,.0f} L={c['low']:,.0f} C={c['close']:,.0f} "
          f"Vol={c['volumefrom']:,.2f} {c['volumeto']:,.0f} USD")
# 2026-04-12: O=79,770 H=83,458 L=79,770 C=82,622 Vol=24,540.70
# ...

# Fields per candle: time, high, low, open, volumefrom, volumeto, close, conversionType, conversionSymbol
```

**`toTs` parameter** — fetch historical candles ending at a specific Unix timestamp:
```python
data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/v2/histoday"
    "?fsym=BTC&tsym=USD&limit=5&toTs=1700000000"   # Nov 14, 2023
))
# Returns 5 daily candles ending 2023-11-14 at BTC ~$35,551
```

**`aggregate` parameter** — group candles into weekly or other intervals:
```python
data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/v2/histoday"
    "?fsym=BTC&tsym=USD&limit=4&aggregate=7"   # weekly candles
))
# Returns 4 weekly OHLCV candles
# 2026-03-26: O=71,305 H=71,410 L=64,960 C=68,108 Vol=183,253.59 BTC
```

**Exchange-specific OHLCV** — add `&e=Coinbase` or `&e=Kraken` (uses CCCAGG aggregate by default):
```python
data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/v2/histoday"
    "?fsym=BTC&tsym=USD&limit=5&e=Coinbase"
))
# Returns Coinbase-specific OHLCV only
```

### Historical OHLCV — hourly candles

```python
import json, datetime

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/v2/histohour"
    "?fsym=ETH&tsym=USD&limit=24"   # last 24 hours
))
candles = data['Data']['Data']
meta = data['Data']
print(f"TimeFrom: {meta['TimeFrom']}  TimeTo: {meta['TimeTo']}")
print(f"Entries: {len(candles)}")

e = candles[-1]
dt = datetime.datetime.fromtimestamp(e['time'], tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
print(f"Latest: {dt}  C={e['close']:,.2f}")
```

Same fields as daily: `time, open, high, low, close, volumefrom, volumeto, conversionType, conversionSymbol`

Exchange-specific hourly (confirmed working for Coinbase):
```python
data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/v2/histohour"
    "?fsym=BTC&tsym=USD&limit=5&e=Coinbase"
))
# Coinbase-specific volume and OHLC
```

### Historical OHLCV — minute candles

```python
import json, datetime

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/v2/histominute"
    "?fsym=BTC&tsym=USD&limit=60"   # last 60 minutes
))
candles = data['Data']['Data']
print(f"Entries: {len(candles)}")   # 61 entries (includes the current partial minute)

e = candles[-1]
dt = datetime.datetime.fromtimestamp(e['time'], tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
print(f"{dt}: O={e['open']:,.2f} C={e['close']:,.2f}")
# 2026-04-19 01:42: O=75,571.67 C=75,571.74
```

Minute data is free (confirmed working — earlier `Error` test was a fluke). Max `limit` per call is not enforced strictly but use 1440 or less for reasonable responses.

### Top coins by market cap

```python
import json

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/top/mktcapfull"
    "?limit=10&tsym=USD"   # limit max 100
))
for item in data['Data']:
    info = item['CoinInfo']
    raw  = item['RAW']['USD']
    print(
        f"{info['Name']:6} {info['FullName']:20} "
        f"${raw['PRICE']:>12,.2f}  "
        f"MCap=${raw['MKTCAP']/1e9:.1f}B  "
        f"Vol24h={raw['VOLUME24HOUR']:,.0f}"
    )
# BTC    Bitcoin              $   75,604.86  MCap=$1513.4B  Vol24h=10,846
# ETH    Ethereum             $    2,346.16  MCap=$283.2B   Vol24h=171,815

# CoinInfo keys per item:
# Id, Name, FullName, Internal, ImageUrl, Url, Algorithm, ProofType,
# Rating, NetHashesPerSecond, BlockNumber, BlockTime, BlockReward,
# AssetLaunchDate, MaxSupply, Type, DocumentType
```

The `RAW` and `DISPLAY` sections are identical to `pricemultifull` (same full field set).

### Top coins by volume (top-tier exchanges only)

```python
import json

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/top/totaltoptiervolfull"
    "?limit=10&tsym=USD"
))
for item in data['Data']:
    info = item['CoinInfo']
    raw  = item.get('RAW', {}).get('USD', {})
    print(f"{info['Name']:6} ${raw.get('PRICE',0):>10,.2f}  Top-tier Vol24h={raw.get('TOPTIERVOLUME24HOUR',0):,.0f}")
# BTC    $   75,604.86  Top-tier Vol24h=10,882
# ETH    $    2,346.16  Top-tier Vol24h=174,036
# USDC   $        1.00  Top-tier Vol24h=304,987,042
```

### Top trading pairs for a coin

```python
import json

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/top/pairs"
    "?fsym=BTC&limit=10"
))
for p in data['Data']:
    print(
        f"{p['fromSymbol']}/{p['toSymbol']:6}  "
        f"Exchange: {p['exchange']:15}  "
        f"Vol24h: {p['volume24h']:>15,.2f}  "
        f"Price: {p['price']:,.4f}  "
        f"Grade: {p['exchangeGrade']}"
    )
# BTC/USDC   Exchange: CCCAGG          Vol24h:   7,000.73  Price: 75,591.5000  Grade: -
# BTC/BTC    Exchange: CCCAGG          Vol24h:   ...

# Pair fields: exchange, fromSymbol, toSymbol, volume24h, volume24hTo,
#              price, lastUpdateTs, exchangeGradePoints, exchangeGrade
```

The `exchange=CCCAGG` is the CryptoCompare aggregate market — covers all tracked exchanges combined.

### Top exchanges for a specific coin pair

```python
import json

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/top/exchanges/full"
    "?fsym=BTC&tsym=USD&limit=10"
))
d = data['Data']
agg = d['AggregatedData']
print(f"Aggregate: ${agg['PRICE']:,.2f}  Vol24h={agg['VOLUME24HOUR']:,.2f} BTC")

for ex in d['Exchanges']:
    print(f"  {ex['MARKET']:15} ${ex['PRICE']:>12,.2f}  Vol:{ex['VOLUME24HOUR']:>10,.2f}")
# Coinbase        $   75,590.00  Vol:  4,103.16
# cryptodotcom    $   75,595.80  Vol:  3,362.08
# Kraken          $   75,573.60  Vol:    860.20

# Exchange fields: TYPE, MARKET, FROMSYMBOL, TOSYMBOL, PRICE,
#   VOLUME24HOUR, VOLUME24HOURTO, HIGH24HOUR, LOW24HOUR,
#   CHANGE24HOUR, CHANGEPCT24HOUR, OPEN24HOUR, HIGHDAY, LOWDAY (etc.)
```

### Exchange metadata list

```python
import json

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/exchanges/general"
))
exchanges = data['Data']   # dict keyed by numeric exchange ID strings
print(f"Exchanges: {len(exchanges)}")   # 304 as of April 2026

# Find by name
for ex_id, ex in exchanges.items():
    if ex.get('Name') == 'Binance':
        print(f"ID: {ex_id}")
        print(f"Country: {ex.get('Country')}")       # Cayman Islands
        print(f"Grade: {ex.get('Grade')}")             # AA
        print(f"24h Vol: {ex.get('TOTALVOLUME24H')}")  # {'BTC': 91508.68}
        print(f"CentralizationType: {ex.get('CentralizationType')}")
        break

# Exchange fields: Id, Name, Url, LogoUrl, ItemType, CentralizationType,
#   InternalName, GradePoints, Grade, GradePointsSplit, AffiliateURL,
#   Country, OrderBook, Trades, Description, FullAddress, Fees,
#   DepositMethods, WithdrawalMethods, Sponsored, Recommended, Rating,
#   SortOrder, TOTALVOLUME24H, DISPLAYTOTALVOLUME24H
```

### All trading pairs on an exchange

```python
import json

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/v4/all/exchanges"
    "?tsym=USD&e=Binance"
))
exchanges = data['Data']['exchanges']
binance = exchanges.get('Binance', {})
print(f"Active: {binance.get('isActive')}")       # True
print(f"TopTier: {binance.get('isTopTier')}")     # True
pairs = binance.get('pairs', {})
print(f"Pairs count: {len(pairs)}")               # 437

# Each pair key is a coin symbol; value maps to quote currencies with history timestamps
for base_sym in list(pairs.keys())[:3]:
    quotes = list(pairs[base_sym]['tsyms'].keys())
    print(f"  {base_sym} -> {quotes}")
# BTC -> ['USDT', 'JPY', 'MXN', 'IDR', ...]

# Each tsym entry has: histo_minute_start_ts, histo_minute_start,
#   histo_minute_end_ts, histo_minute_end, isActive
```

### Coin list and metadata

```python
import json

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/all/coinlist"
))
coins = data['Data']   # dict keyed by ticker symbol (e.g. 'BTC', 'ETH')
print(f"Total coins: {len(coins)}")   # 19,331 as of April 2026

btc = coins['BTC']
print(f"Id:            {btc['Id']}")           # 1182  ← needed for social/blockchain endpoints
print(f"Name:          {btc['CoinName']}")     # Bitcoin
print(f"Algorithm:     {btc['Algorithm']}")    # SHA-256
print(f"ProofType:     {btc['ProofType']}")    # PoW
print(f"IsTrading:     {btc['IsTrading']}")    # True
print(f"ImageUrl:      https://www.cryptocompare.com{btc['ImageUrl']}")

# Fields: Id, Url, ImageUrl, ContentCreatedOn, Name, Symbol, CoinName,
#   FullName, Description, AssetTokenStatus, Algorithm, ProofType,
#   SortOrder, Sponsored, Taxonomy, Rating, IsTrading
```

**Use `coins[sym]['Id']` to get the numeric coin ID** needed for social/blockchain auth-required endpoints.

### Coin general info (supply + image URL, no auth)

```python
import json

data = json.loads(http_get(
    "https://min-api.cryptocompare.com/data/coin/generalinfo"
    "?fsyms=BTC,ETH,SOL&tsym=USD"
))
for item in data['Data']:
    ci   = item['CoinInfo']
    conv = item['ConversionInfo']
    print(f"{ci['Name']:5} Id={ci['Id']:7} {ci['FullName']:20} Supply={conv.get('Supply', 'N/A')}")
    print(f"       Image: https://www.cryptocompare.com{ci['ImageUrl']}")
# BTC   Id=1182    Bitcoin              Supply=20017787
# ETH   Id=7605    Ethereum             Supply=120690548.46
```

`ConversionInfo` also has: `Conversion, ConversionSymbol, CurrencyFrom, CurrencyTo, Market, Supply, MktCap`

## Symbol conventions

| Aspect | CoinGecko | CryptoCompare |
|--------|-----------|---------------|
| Format | kebab-case ID (`bitcoin`) | uppercase ticker (`BTC`) |
| Uniqueness | IDs are unique | Symbols may collide (rare) |
| Lookup | `/coins/list` needed | Use symbol directly |
| Unknown coin | Returns `{}` silently | Returns `{}` or `Error` response |

Symbols used in `fsym`/`fsyms` are case-insensitive in practice but always use uppercase to be safe: `BTC`, `ETH`, `SOL`, `XRP`, `BNB`, `DOGE`, `ADA`, `AVAX`, `DOT`.

## Supported quote currencies (`tsyms`)

Works with any major fiat or crypto: `USD`, `EUR`, `GBP`, `JPY`, `AUD`, `CAD`, `CHF`, `CNY`, `KRW`, `BRL`, `INR`, `MXN` (fiat) and `BTC`, `ETH`, `BNB`, `USDT`, `USDC` (crypto). More obscure pairs may silently return `{}`.

## Gotchas

- **No auth needed, but errors still return HTTP 200** — auth-required endpoints return `{"Response":"Error","Message":"You need a valid auth key..."}` with HTTP 200. No exception is raised by `http_get`. Always check `d.get('Response') == 'Error'` before reading data from untested endpoints.

- **`pricemultifull` returns both `RAW` and `DISPLAY`** — `RAW` is numeric, `DISPLAY` is pre-formatted strings with currency symbols (e.g. `"$ 75,585.8"`). Use `RAW` for computation, `DISPLAY` for printing directly.

- **`IMAGEURL` is a relative path** — `raw['IMAGEURL']` returns `/media/37746251/btc.png`. Prepend `https://www.cryptocompare.com` to get the full URL. Confirmed working (HTTP 200).

- **`histoday`/`histohour` `limit` is the number of candles, not days back** — `limit=7` returns 8 candles (the current partial period + 7 complete ones). The array has `limit + 1` entries.

- **`toTs` timestamp is inclusive** — `toTs=1700000000` returns candles ending on or before that Unix timestamp. The last candle's `time` will be `<= toTs`.

- **`aggregate=7` gives weekly candles from daily endpoint** — multiply the base interval (day) by `aggregate`. `aggregate=4` on `histohour` gives 4-hour candles.

- **`e=Coinbase` works for exchange-specific OHLCV** — adds the `&e=ExchangeName` param to `histoday`/`histohour`/`histominute`. Valid exchange names must match CryptoCompare's internal names (use `/data/exchanges/general` to find them: Binance, Kraken, Coinbase, Bitfinex, etc.).

- **`data/v4/all/exchanges` keyed by exchange name, `data/exchanges/general` keyed by numeric ID** — inconsistent. The v4 endpoint uses the exchange's display name (e.g. `'Binance'`) as key; the general endpoint uses a numeric ID string (e.g. `'283442'`). To match them, filter the general endpoint by `ex['Name'] == 'Binance'`.

- **Top coins `limit` max is 100** — `limit=250` for `top/mktcapfull` silently returns 100. Use pagination with `page=2` etc. if you need more.

- **`histominute` max lookback is ~7 days** — requesting more than ~10,080 minutes worth of data returns what's available (may be fewer entries than requested).

- **CCCAGG is the default aggregate market** — all price/volume data from `pricemulti`, `pricemultifull`, and `histoday` uses CryptoCompare's volume-weighted aggregate across all tracked exchanges unless you specify `&e=ExchangeName`. `TOTALVOLUME24H` in `pricemultifull` reflects the sum across all markets; `VOLUME24HOUR` reflects the top-tier aggregate.
