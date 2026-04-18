# CoinMarketCap — Data Extraction

`https://coinmarketcap.com` — crypto market data. Three access paths tested: internal JSON API (fastest, no auth required), `__NEXT_DATA__` from HTML pages, and browser DOM. All real-money price data confirmed accurate against displayed UI values.

## Do this first: pick your access path

| Goal | Best approach | Latency |
|------|--------------|---------|
| Top N coins by market cap | Internal listing API | ~200ms |
| Single coin price/stats/ATH | Internal detail API | ~100ms |
| Global market metrics | Internal global-metrics API | ~65ms |
| All coins on homepage (101 items) | `__NEXT_DATA__` main page | ~700ms |
| Coin detail + full stats | `__NEXT_DATA__` currency page | ~700ms |
| Historical OHLCV | Internal historical API | ~160ms |
| Exchange pairs for a coin | Internal market-pairs API | ~200ms |
| News/articles | Internal content API | ~220ms |

**Never use the browser for read-only CMC tasks.** The internal API at `api.coinmarketcap.com` is accessible with no API key, no special headers, no auth — plain `http_get` works.

**Do NOT use `pro-api.coinmarketcap.com`** — that is the paid API requiring a key.

---

## Path 1: Internal listing API (fastest for ranked coins)

Returns CMC-ranked coins with full price data in one call. No auth needed.

```python
import json

resp = json.loads(http_get(
    "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
    "?start=1&limit=100&sortBy=market_cap&sortType=desc&convert=USD"
))

coins = resp['data']['cryptoCurrencyList']    # list of coin objects
total_available = resp['data']['totalCount']  # 8374 as of 2026-04-18

for c in coins:
    usd = next(q for q in c['quotes'] if q['name'] == 'USD')
    print(
        f"#{c['cmcRank']} {c['symbol']}: "
        f"${usd['price']:,.2f} | "
        f"MCap ${usd['marketCap']/1e9:.1f}B | "
        f"Vol24h ${usd['volume24h']/1e9:.1f}B | "
        f"24h {usd['percentChange24h']:+.2f}% | "
        f"CS {c['circulatingSupply']:,.0f}"
    )
```

### Coin object fields

Top-level (`c` in the loop above):
```
id, name, symbol, slug, cmcRank, marketPairCount,
circulatingSupply, selfReportedCirculatingSupply,
totalSupply, maxSupply, isActive, lastUpdated, dateAdded,
quotes, isAudited, auditInfoList, badges
```

Per-quote fields (inside `c['quotes']`, filtered by `name == 'USD'`):
```
name, price, volume24h, volumePercentChange, marketCap,
percentChange1h, percentChange24h, percentChange7d,
percentChange30d, percentChange60d, percentChange90d,
percentChange1y, ytdPriceChangePercentage,
fullyDilluttedMarketCap, marketCapByTotalSupply,
dominance, turnover, lastUpdated
```

### Query parameters

```python
# Pagination
"?start=1&limit=100"        # page 1 of 100
"?start=101&limit=100"      # page 2

# Sort
"sortBy=market_cap"         # default
"sortBy=volume_24h"
"sortBy=percent_change_24h"
"sortBy=price"
"sortBy=circulating_supply"
"sortType=desc"             # or asc

# Currency conversion (affects quote prices returned)
"convert=USD"               # USD prices
"convert=BTC"               # BTC-denominated

# Filter by type
"cryptoType=all"            # default — coins + tokens
"cryptoType=coins"          # layer-1s only (633 results)
"cryptoType=tokens"         # ERC-20 etc.

# Filter by tag (DeFi, NFT, etc.)
"tagSlugs=defi"             # 2698 results
"tagSlugs=nft"
```

---

## Path 2: Internal detail API (single coin, full stats)

Best for fetching one coin's complete data including ATH, ATL, 52-week high/low, volume ranks.

```python
import json

# Look up by CMC coin ID (BTC=1, ETH=1027, XRP=52, SOL=5426, BNB=1839)
resp = json.loads(http_get(
    "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail?id=1"
))
data = resp['data']
s = data['statistics']

print(f"Price:             ${s['price']:,.2f}")
print(f"Rank:              #{s['rank']}")
print(f"Market Cap:        ${s['marketCap']:,.0f}")
print(f"Volume 24h:        ${s['volume24h']:,.0f}")
print(f"Circulating Supply:{s['circulatingSupply']:,.0f}")
print(f"Total Supply:      {s['totalSupply']:,.0f}")
print(f"Max Supply:        {s['maxSupply']:,.0f}")
print(f"24h Change:        {s['priceChangePercentage24h']:+.2f}%")
print(f"7d Change:         {s['priceChangePercentage7d']:+.2f}%")
print(f"ATH:               ${s['highAllTime']:,.2f} on {s['highAllTimeTimestamp']}")
print(f"ATL:               ${s['lowAllTime']:,.4f} on {s['lowAllTimeTimestamp']}")
print(f"52w High:          ${s['high52w']:,.2f}")
print(f"52w Low:           ${s['low52w']:,.2f}")
print(f"MCap Dominance:    {s['marketCapDominance']:.2f}%")
```

### All statistics fields

```
price, priceChangePercentage1h, priceChangePercentage24h,
priceChangePercentage7d, priceChangePercentage30d,
priceChangePercentage60d, priceChangePercentage90d,
priceChangePercentage1y, priceChangePercentageAll,
marketCap, marketCapChangePercentage24h,
fullyDilutedMarketCap, mintedMarketCap,
circulatingSupply, totalSupply, maxSupply,
marketCapDominance, rank, roi,
low24h, high24h, low7d, high7d, low30d, high30d,
low52w, high52w, low90d, high90d,
lowAllTime, highAllTime,
lowAllTimeChangePercentage, highAllTimeChangePercentage,
lowAllTimeTimestamp, highAllTimeTimestamp,
lowYesterday, highYesterday, openYesterday, closeYesterday,
priceChangePercentageYesterday, volumeYesterday,
ytdPriceChangePercentage, volumeRank, volumeMcRank,
volume24h, volume24hReported, volume7d, volume7d Reported,
volume30d, volume30dReported, turnover
```

### Top-level data fields (beyond statistics)

```
id, name, symbol, slug, category, description, dateAdded,
volume, volumeChangePercentage24h, cexVolume, dexVolume,
urls (website, explorer, twitter, reddit, etc.),
tags, platforms, relatedCoins, wallets,
holders, watchCount, watchListRanking
```

---

## Path 3: Global market metrics

```python
import json

resp = json.loads(http_get(
    "https://api.coinmarketcap.com/data-api/v3/global-metrics/quotes/latest"
))
data = resp['data']
q = data['quotes'][0]   # USD quote (cryptoId=2781)

print(f"Total Market Cap:  ${q['totalMarketCap']/1e12:.2f}T")
print(f"Total Volume 24h:  ${q['totalVolume24H']/1e9:.1f}B")
print(f"Altcoin MCap:      ${q['altcoinMarketCap']/1e12:.2f}T")
print(f"DeFi MCap:         ${q['defiMarketCap']/1e9:.1f}B")
print(f"DeFi Vol 24h:      ${q['defiVolume24H']/1e9:.1f}B")
print(f"Stablecoin MCap:   ${q['stablecoinMarketCap']/1e9:.1f}B")
print(f"Derivatives Vol:   ${q['derivativesVolume24H']/1e9:.1f}B")
print(f"BTC Dominance:     {data['btcDominance']:.2f}%")
print(f"ETH Dominance:     {data['ethDominance']:.2f}%")
print(f"Active Cryptos:    {data['activeCryptoCurrencies']}")
print(f"Total Cryptos:     {data['totalCryptoCurrencies']}")
print(f"Active Exchanges:  {data['activeExchanges']}")
print(f"Active Pairs:      {data['activeMarketPairs']}")

# Yesterday comparison
print(f"\nMCap Yesterday:    ${q['totalMarketCapYesterday']/1e12:.2f}T")
print(f"MCap Change:       {q['totalMarketCapYesterdayPercentageChange']:+.2f}%")
```

---

## Path 4: Historical OHLCV (candlestick data)

```python
import json, time

now = int(time.time())

# Daily candles for BTC over last 7 days
resp = json.loads(http_get(
    "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/historical"
    f"?id=1&convertId=2781&timeStart={now - 7*86400}&timeEnd={now}&interval=daily"
))
candles = resp['data']['quotes']   # list of OHLCV dicts

for candle in candles:
    q = candle['quote']
    print(
        f"{candle['timeOpen'][:10]} "
        f"O={q['open']:,.0f} H={q['high']:,.0f} "
        f"L={q['low']:,.0f} C={q['close']:,.0f} "
        f"V=${q['volume']/1e9:.1f}B MCap=${q['marketCap']/1e12:.2f}T"
    )
```

Candle quote fields: `open, high, low, close, volume, marketCap, circulatingSupply, timestamp`

Supported intervals: `daily`, `1h` (hourly). `5m` returns HTTP 500 — not supported.

`convertId=2781` = USD. `timeStart`/`timeEnd` are Unix timestamps.

---

## Path 5: Exchange market pairs for a coin

```python
import json

resp = json.loads(http_get(
    "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/latest"
    "?id=1&start=1&limit=10&sort=volume"
))
data = resp['data']
print(f"Total pairs for {data['name']}: {data['numMarketPairs']}")

for pair in data['marketPairs']:
    print(
        f"  {pair['exchangeName']:20} {pair['marketPair']:12} "
        f"${pair['price']:,.2f} Vol=${pair['volumeUsd']/1e6:.1f}M"
    )
```

Pair fields: `rank, exchangeId, exchangeName, exchangeSlug, marketId, marketPair, category (spot/futures), baseSymbol, quoteSymbol, baseCurrencyId, quoteCurrencyId, price, volumeUsd, effectiveLiquidity, lastUpdated, volumeBase, volumeQuote, depthUsdNegativeTwo, depthUsdPositiveTwo, feeType, isVerified, type (cex/dex)`

---

## Path 6: Exchange listings

```python
import json

resp = json.loads(http_get(
    "https://api.coinmarketcap.com/data-api/v3/exchange/listing"
    "?start=1&limit=20&sortBy=score&sortType=desc"
))
exchanges = resp['data']['exchanges']
for ex in exchanges:
    print(f"  {ex['name']:30} score={ex.get('score')} trafficScore={ex.get('trafficScore')}")
```

Exchange fields: `id, name, slug, dexStatus, platformId, status, score, trafficScore, countries, fiats, filteredTotalVol24h`

---

## Path 7: Price conversion (cross-rate)

```python
import json

# Convert 1 BTC → USD
resp = json.loads(http_get(
    "https://api.coinmarketcap.com/data-api/v3/tools/price-conversion"
    "?amount=1&id=1&convert_id=2781"
))
result = resp['data']
usd_price = result['quote'][0]['price']
print(f"1 {result['symbol']} = ${usd_price:,.2f} USD")

# Convert ETH → BTC
resp2 = json.loads(http_get(
    "https://api.coinmarketcap.com/data-api/v3/tools/price-conversion"
    "?amount=1&id=1027&convert_id=1"
))
btc_price = resp2['data']['quote'][0]['price']
print(f"1 ETH = {btc_price:.6f} BTC")
```

`id` = source coin CMC ID, `convert_id` = target currency CMC ID (2781=USD, 1=BTC, 1027=ETH, 825=USDT)

---

## Path 8: News / articles

```python
import json

# News for a specific coin
resp = json.loads(http_get(
    "https://api.coinmarketcap.com/content/v3/news?coins=1&limit=10"
))
for article in resp['data']:
    meta = article['meta']
    print(f"  [{meta['sourceName']}] {meta['title']}")
    print(f"    {article['createdAt'][:10]} — {meta['sourceUrl']}")
```

Article fields: `slug, cover, assets, createdAt` + nested `meta` with `title, subtitle, sourceName, sourceUrl, language, type, status, id, createdAt, updatedAt, releasedAt`

Omit `coins=` param for general crypto news. Supports `limit` up to observed 50+ without errors.

---

## Path 9: __NEXT_DATA__ from HTML pages

Use when you need data that isn't in the API (e.g. Fear & Greed index, CMC100 index, trending categories).

### Main page (`coinmarketcap.com/`)

```python
import json, re

html = http_get("https://coinmarketcap.com/")
m = re.search(r'<script id="__NEXT_DATA__"[^>]+>([\s\S]*?)</script>', html)
nd = json.loads(m.group(1))
props = nd['props']

# Global market metrics (same data as global-metrics API, faster from HTML)
gm = props['pageProps']['globalMetrics']
print(f"Total cryptos: {gm['numCryptocurrencies']}")
print(f"BTC dominance: {gm['btcDominance']:.2f}%")
print(f"Total MCap:    ${gm['marketCap']/1e12:.2f}T")
print(f"Total Vol 24h: ${gm['totalVol']/1e9:.1f}B")

# Spot prices for BTC/ETH/USD/SATS/BITS (the "ticker bar" data)
# props['quotesLatestData'] — 5 items with short field names
for q in props['quotesLatestData']:
    print(f"  {q['symbol']}: p={q['p']} p24h={q['p24h']:+.3f}%")
    # fields: id, symbol, p (price), p1h, p24h, p7d, p30d, p60d, p90d, pytd, t

# Top 101 coins with full USD quotes — from dehydratedState
queries = props['dehydratedState']['queries']
homepage_q = next(q for q in queries if q['queryKey'] == ['homepage-data', 1, 100])
listing = homepage_q['state']['data']['data']['listing']
coins = listing['cryptoCurrencyList']   # 101 coins
total = listing['totalCount']

for c in coins:
    if c['symbol'] == 'BTC':
        usd = next(q for q in c['quotes'] if q['name'] == 'USD')
        print(f"BTC: #{c['cmcRank']} ${usd['price']:,.2f}")
        break

# Page-level shared data (Fear & Greed index, CMC20, altcoin index)
psd = props['pageProps']['pageSharedData']
print("pageSharedData keys:", list(psd.keys()))
# keys: topCategories, fearGreedIndexData, cmc100, cmc20, faqData, altcoinIndex, halvingInfo, deviceInfo
```

**Gotcha — regex pattern**: Use `[^>]+` to match the `crossorigin="anonymous"` attribute on the script tag. `type="application/json"` alone will miss it:
```python
# CORRECT
m = re.search(r'<script id="__NEXT_DATA__"[^>]+>([\s\S]*?)</script>', html)

# WRONG — returns None because of crossorigin attr
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
```

**`quotesLatestData` has only 5 entries** (SATS, BITS, BTC, ETH, USD) — it's the currency selector bar, not the full market ranking. For the full ranked listing use `dehydratedState`.

**`cmcRank` is at coin top level**, not inside the USD quote object. The `cmcRank` field inside the quote dict is `None`.

### Individual coin page (`/currencies/{slug}/`)

```python
import json, re

html = http_get("https://coinmarketcap.com/currencies/bitcoin/")
m = re.search(r'<script id="__NEXT_DATA__"[^>]+>([\s\S]*?)</script>', html)
nd = json.loads(m.group(1))

# All stats under props.pageProps.detailRes.detail.statistics
stats = nd['props']['pageProps']['detailRes']['detail']['statistics']

print(f"Price:     ${stats['price']:,.2f}")
print(f"Rank:      #{stats['rank']}")
print(f"MCap:      ${stats['marketCap']:,.0f}")
print(f"Vol 24h:   ${stats['volume24h']:,.0f}")
print(f"Circ Sup:  {stats['circulatingSupply']:,.0f}")
print(f"24h:       {stats['priceChangePercentage24h']:+.2f}%")
print(f"ATH:       ${stats['highAllTime']:,.2f} ({stats['highAllTimeTimestamp']})")
print(f"ATL:       ${stats['lowAllTime']:.4f}")
```

`detailRes.detail` also contains: `name, symbol, slug, description, tags, urls (website/explorer/twitter/reddit), platforms, relatedCoins, holders, watchCount`

**Note**: The currency page has no JSON-LD blocks — zero `<script type="application/ld+json">` elements.

---

## Common coin IDs

| ID | Symbol | Name |
|----|--------|------|
| 1 | BTC | Bitcoin |
| 1027 | ETH | Ethereum |
| 52 | XRP | XRP |
| 825 | USDT | Tether |
| 1839 | BNB | BNB |
| 3408 | USDC | USD Coin |
| 5426 | SOL | Solana |
| 74 | DOGE | Dogecoin |
| 2781 | USD | US Dollar (for convert_id) |

Find IDs from the listing API: `c['id']` or from the detail API URL by looking up a slug first via the listing API's `c['slug']` field.

---

## Anti-bot / rate limits

**Main site (`coinmarketcap.com`):**
- `http_get` works with the default `Mozilla/5.0` UA — no Cloudflare, no bot detection triggered.
- Page loads are ~700ms for 690–710KB of HTML+`__NEXT_DATA__`.

**Internal API (`api.coinmarketcap.com`):**
- No auth headers required. No `X-Request-Id` or `X-Forwarded-For` needed.
- 25 rapid sequential calls with zero rate limiting or errors — no throttle observed at that volume.
- Typical latency: 65–250ms per call.
- `error_code: '0'` and `error_message: 'SUCCESS'` in every response; no `credit_count` consumed.

**v2 API (`api.coinmarketcap.com/v2/`):**
- Returns HTTP 401 Unauthorized — requires API key. Do not use.

**Pro API (`pro-api.coinmarketcap.com`):**
- Paid, requires `X-CMC_PRO_API_KEY` header. Do not test or call.

---

## Gotchas

- **No JSON-LD on any page tested** — coin pages have zero `<script type="application/ld+json">` elements. Don't look for schema.org markup.

- **`__NEXT_DATA__` regex**: Must use `[^>]+` between `__NEXT_DATA__"` and `>` — the tag has `crossorigin="anonymous"` which breaks a naive `type="application/json">` match.

- **`cmcRank` location on homepage listing**: It's `c['cmcRank']` (top-level), NOT inside `c['quotes'][n]['cmcRank']` (that field is always `None`).

- **5m/sub-hourly OHLCV not available**: Interval `5m` returns HTTP 500. Use `1h` for sub-daily and `daily` for longer ranges.

- **v2 API is auth-only**: `api.coinmarketcap.com/v2/...` requires API key (401). The equivalent data is available via `data-api/v3/` without auth.

- **`convert` param accepts symbols not just IDs** in the listing API, but `convert_id` in the price-conversion API requires numeric IDs (e.g. `2781` not `USD`).

- **Circulating supply**: `c['circulatingSupply']` at the coin top level in the listing response — not inside the quote. The quote has `marketCap` which equals `price * circulatingSupply`.

- **Multiple quotes per coin**: The listing API returns multiple quote objects when you request multiple convert currencies. Always filter by `q['name'] == 'USD'` (or your target currency) before reading price fields.

- **Pagination**: `start` is 1-indexed (not 0-indexed). `start=1&limit=100` returns items 1–100, `start=101&limit=100` returns items 101–200.
