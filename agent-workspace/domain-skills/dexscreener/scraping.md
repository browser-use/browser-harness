# DEX Screener - Pair Search, Token Pairs, New Pairs and Boosted Tokens (official API + New Pairs page)

Field-tested against dexscreener.com and api.dexscreener.com on 2026-11-02 using a Browser Use cloud browser, logged out. API calls are `fetch()` from an api.dexscreener.com tab; New Pairs is read from the dexscreener.com page. No CAPTCHA, 403 or 429 across about 80 API calls and 10 dexscreener.com page loads; an independent rerun in a fresh browser got one Cloudflare "Just a moment..." page on New Pairs page 2 (see Gotchas).

robots.txt (fetched 2026-11-02 in the browser): dexscreener.com is `User-agent: *` / `Allow: /`; api.dexscreener.com has no robots.txt (HTTP 404) and is used under the official-API exception: it is DEX Screener's documented public API (https://docs.dexscreener.com/api/reference), no key, limits 300 requests/min for pairs, tokens, token-pairs and search, 60/min for boosts, profiles, orders and the rest.

## Quick summary

- **API first.** Four official endpoints cover search and token pairs, two cover boosts. JSON, no key, no cookies, `access-control-allow-origin: *`:
  - `/latest/dex/search?q=<text>` - pairs matching a symbol, name, `BASE/QUOTE` or address. **Max 30 results, no paging.** (300/min)
  - `/token-pairs/v1/<chainId>/<tokenAddress>` - the token's pools. **Max 30, no paging.** (300/min)
  - `/tokens/v1/<chainId>/<addr1>,<addr2>,...` - up to 30 tokens per call; returned 1 main pair per token today. (300/min)
  - `/latest/dex/pairs/<chainId>/<pair1>,<pair2>,...` - fresh numbers for known pairs; 30 per call worked. (300/min)
  - `/token-boosts/latest/v1` and `/token-boosts/top/v1` - 30 rows each. (60/min)
- **New pairs have no API endpoint.** Read the site's table at `https://dexscreener.com/new-pairs?rankBy=pairAge&order=asc` (what its "Newest" button sets): 100 rows per page, `/new-pairs/page-2?...` for more, `/new-pairs/<chainId>?...` for one chain. Then fetch exact numbers for those pairs from `/latest/dex/pairs`.
- **Never take prices from the page.** The table draws leading zeros as a subscript, so its text reads `$0.046151` for a price of `0.00006151`. Use `priceUsd` from the API.
- `get()` paces each endpoint group under its documented limit (x1.1 margin), runs one call at a time, retries 429/5xx with backoff, and otherwise raises. A failed call never comes back as an empty result.

## What works

API blocks share the same helpers: `on_api_tab()` opens a tiny JSON answer on api.dexscreener.com once (later blocks reuse it), `get(path)` starts `fetch()` in that tab and polls for the result (big answers can take longer than `js()`'s 5 s timeout), and `pair_row()` flattens the shared Pair schema. Block 3 adds `open_site()` and `table_row()` for the New Pairs page and stops on any challenge page.

### 1. Search pairs (browser, official API)

```python
import json, time, urllib.parse
from datetime import datetime, timezone

QUERIES = ["PEPE", "SOL/USDC", "zzqx-no-such-token-987"]   # symbol, name, pair "BASE/QUOTE" or an address

API = "https://api.dexscreener.com"
PER_MIN = {"slow": 60, "fast": 300}   # documented limits, requests per minute per endpoint group
FAST = ("/latest/dex/", "/tokens/v1/", "/token-pairs/v1/")   # 300/min; boosts, profiles, orders etc. are 60/min
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab
_last = {"slow": 0.0, "fast": 0.0}

def on_api_tab():
    """All API calls run as same-origin fetch() in a logged-out api.dexscreener.com tab; reuse it if already there."""
    try:
        if js("location.origin + ' ' + document.contentType") == API + " application/json":
            return
    except Exception:
        pass
    # A tiny JSON answer ("[]"). Not the host root: its 'Cannot GET /' 404 page sends CSP default-src 'none',
    # which makes every fetch() from that tab fail with "Failed to fetch".
    new_tab(API + "/token-pairs/v1/solana/x")
    wait_for_load()

START_JS = """(() => { window.__dx = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__dx = {status: r.status, len: t.length, ra: r.headers.get('retry-after'), body: t}; })
    .catch(e => { window.__dx = {status: 0, len: 0, err: String(e), body: ''}; });
  return 1; })()"""

def get(path, tries=4):
    """Serial GET of api.dexscreener.com<path>, paced under the documented limit. Returns parsed JSON.
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    bucket = "fast" if path.startswith(FAST) else "slow"
    url = API + path
    for attempt in range(tries):
        gap = 60 / PER_MIN[bucket] * 1.1 - (time.time() - _last[bucket])
        if gap > 0:
            time.sleep(gap)
        _last[bucket] = time.time()
        js(START_JS % json.dumps(url))   # fetch runs in the page; poll so slow answers do not hit js()'s timeout
        t0 = time.time()
        while not (meta := js("window.__dx && {status: window.__dx.status, len: window.__dx.len, ra: window.__dx.ra, err: window.__dx.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.3)
        status = meta["status"]
        if status == 200:
            text = "".join(js(f"window.__dx.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__dx = null")
            return json.loads(text)
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('err') or ''}; stopping")
        ra = meta.get("ra") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if isinstance(ms, (int, float)) else None

def pair_row(p):
    """One flat row per pair from search, token-pairs, tokens and pairs responses (all share the Pair schema)."""
    liq, vol, chg, tx = p.get("liquidity") or {}, p.get("volume") or {}, p.get("priceChange") or {}, (p.get("txns") or {}).get("h24") or {}
    return {
        "chain": p["chainId"], "dex": p["dexId"], "labels": p.get("labels") or [],
        "pair": p["pairAddress"], "url": p["url"],
        "base": p["baseToken"]["symbol"], "base_name": p["baseToken"]["name"], "base_address": p["baseToken"]["address"],
        "quote": p["quoteToken"]["symbol"], "quote_address": p["quoteToken"]["address"],
        "price_usd": float(p["priceUsd"]) if p.get("priceUsd") else None, "price_native": p.get("priceNative"),
        "liquidity_usd": liq.get("usd"), "volume_h24": vol.get("h24"), "change_h24": chg.get("h24"),
        "buys_h24": tx.get("buys"), "sells_h24": tx.get("sells"),
        "fdv": p.get("fdv"), "market_cap": p.get("marketCap"),
        "created": iso(p.get("pairCreatedAt")), "boosts": (p.get("boosts") or {}).get("active"),
    }

def short(r):
    return (f"{r['chain']:<9} {r['dex']:<11} {r['base'][:12]:>12}/{r['quote'][:6]:<6} "
            f"${r['price_usd'] if r['price_usd'] is not None else '-':<12} liq ${r['liquidity_usd'] or 0:>14,.0f} "
            f"vol24 ${r['volume_h24'] or 0:>14,.0f} created {r['created']}")

on_api_tab()
results = {}
for q in QUERIES:
    pairs = get("/latest/dex/search?q=" + urllib.parse.quote(q))["pairs"] or []
    # Rank by 24h volume, not liquidity: some pools report billions of "liquidity" with almost no trades.
    rows = sorted((pair_row(p) for p in pairs), key=lambda r: r["volume_h24"] or 0, reverse=True)
    results[q] = rows
    print(f"{q!r}: {len(rows)} pairs, chains {sorted({r['chain'] for r in rows})}")
    for r in rows[:5]:
        print("  ", short(r))
print(json.dumps(results["PEPE"][0], indent=1, ensure_ascii=False))
```

Output observed on 2026-11-02:

```text
'PEPE': 30 pairs, chains ['arbitrum', 'base', 'bsc', 'ethereum', 'pulsechain', 'robinhood', 'solana', 'tron']
   ethereum  uniswap             PEPE/WETH   $4.667e-06    liq $    30,619,496 vol24 $     1,851,318 created 2023-04-14T17:21Z
   solana    meteora             PEPE/SOL    $4.676e-06    liq $        94,499 vol24 $       475,572 created 2026-09-20T15:50Z
   bsc       pancakeswap         PEPE/WBNB   $4.628e-06    liq $       322,399 vol24 $       445,859 created 2023-05-19T02:22Z
   solana    raydium             PEPE/USDC   $3.999e-06    liq $     3,656,612 vol24 $       385,287 created 2026-08-22T05:33Z
   solana    raydium             PEPE/USDC   $4.182e-06    liq $     3,893,941 vol24 $       340,308 created 2026-10-14T05:21Z
'SOL/USDC': 30 pairs, chains ['arc', 'base', 'robinhood', 'solana']
   base      aero                 SOL/USDC   $91.32        liq $       392,322 vol24 $     4,961,402 created None
   solana    raydium              SOL/USDC   $104.35       liq $ 2,191,052,972 vol24 $       340,320 created 2026-10-23T05:46Z
   solana    raydium         SOL-USDC/USDC   $1.0002       liq $   309,741,269 vol24 $       340,306 created 2026-10-19T14:42Z
   solana    orca             JitoSOL/USDC   $119.41       liq $       279,372 vol24 $       317,210 created 2023-06-02T20:02Z
   base      aerodrome            SOL/USDC   $91.3         liq $        95,653 vol24 $       210,333 created None
'zzqx-no-such-token-987': 0 pairs, chains []
{
 "chain": "ethereum",
 "dex": "uniswap",
 "labels": [
  "v2"
 ],
 "pair": "0xA43fe16908251ee70EF74718545e4FE6C5cCEc9f",
 "url": "https://dexscreener.com/ethereum/0xa43fe16908251ee70ef74718545e4fe6c5ccec9f",
 "base": "PEPE",
 "base_name": "Pepe",
 "base_address": "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
 "quote": "WETH",
 "quote_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
 "price_usd": 4.667e-06,
 "price_native": "0.000000002073",
 "liquidity_usd": 30619496.31,
 "volume_h24": 1851317.66,
 "change_h24": -4.42,
 "buys_h24": 403,
 "sells_h24": 434,
 "fdv": 1931373358,
 "market_cap": 1931373358,
 "created": "2023-04-14T17:21Z",
 "boosts": null
}
```

`SOL/USDC` shows the limits of search: 30 loosely matched pairs (an LP token, JitoSOL, Base pools), and the large Solana SOL/USDC pools are not among them. For a known token, use its address with block 2.

### 2. Pools of a token, batch token quotes, pair lookups (browser, official API)

```python
import json, time
from datetime import datetime, timezone

TOKENS = [   # (chainId, token address); chainId is the first path part of a dexscreener.com pair URL
    ("solana", "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"),     # Jupiter
    ("ethereum", "0x6982508145454Ce325dDbE47a25d4ec3d2311933"),    # Pepe
    ("solana", "zzqxNoSuchToken1111111111111111111111111111"),
]

API = "https://api.dexscreener.com"
PER_MIN = {"slow": 60, "fast": 300}   # documented limits, requests per minute per endpoint group
FAST = ("/latest/dex/", "/tokens/v1/", "/token-pairs/v1/")   # 300/min; boosts, profiles, orders etc. are 60/min
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab
_last = {"slow": 0.0, "fast": 0.0}

def on_api_tab():
    """All API calls run as same-origin fetch() in a logged-out api.dexscreener.com tab; reuse it if already there."""
    try:
        if js("location.origin + ' ' + document.contentType") == API + " application/json":
            return
    except Exception:
        pass
    # A tiny JSON answer ("[]"). Not the host root: its 'Cannot GET /' 404 page sends CSP default-src 'none',
    # which makes every fetch() from that tab fail with "Failed to fetch".
    new_tab(API + "/token-pairs/v1/solana/x")
    wait_for_load()

START_JS = """(() => { window.__dx = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__dx = {status: r.status, len: t.length, ra: r.headers.get('retry-after'), body: t}; })
    .catch(e => { window.__dx = {status: 0, len: 0, err: String(e), body: ''}; });
  return 1; })()"""

def get(path, tries=4):
    """Serial GET of api.dexscreener.com<path>, paced under the documented limit. Returns parsed JSON.
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    bucket = "fast" if path.startswith(FAST) else "slow"
    url = API + path
    for attempt in range(tries):
        gap = 60 / PER_MIN[bucket] * 1.1 - (time.time() - _last[bucket])
        if gap > 0:
            time.sleep(gap)
        _last[bucket] = time.time()
        js(START_JS % json.dumps(url))   # fetch runs in the page; poll so slow answers do not hit js()'s timeout
        t0 = time.time()
        while not (meta := js("window.__dx && {status: window.__dx.status, len: window.__dx.len, ra: window.__dx.ra, err: window.__dx.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.3)
        status = meta["status"]
        if status == 200:
            text = "".join(js(f"window.__dx.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__dx = null")
            return json.loads(text)
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('err') or ''}; stopping")
        ra = meta.get("ra") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if isinstance(ms, (int, float)) else None

def pair_row(p):
    """One flat row per pair from search, token-pairs, tokens and pairs responses (all share the Pair schema)."""
    liq, vol, chg, tx = p.get("liquidity") or {}, p.get("volume") or {}, p.get("priceChange") or {}, (p.get("txns") or {}).get("h24") or {}
    return {
        "chain": p["chainId"], "dex": p["dexId"], "labels": p.get("labels") or [],
        "pair": p["pairAddress"], "url": p["url"],
        "base": p["baseToken"]["symbol"], "base_name": p["baseToken"]["name"], "base_address": p["baseToken"]["address"],
        "quote": p["quoteToken"]["symbol"], "quote_address": p["quoteToken"]["address"],
        "price_usd": float(p["priceUsd"]) if p.get("priceUsd") else None, "price_native": p.get("priceNative"),
        "liquidity_usd": liq.get("usd"), "volume_h24": vol.get("h24"), "change_h24": chg.get("h24"),
        "buys_h24": tx.get("buys"), "sells_h24": tx.get("sells"),
        "fdv": p.get("fdv"), "market_cap": p.get("marketCap"),
        "created": iso(p.get("pairCreatedAt")), "boosts": (p.get("boosts") or {}).get("active"),
    }

def short(r):
    return (f"{r['chain']:<9} {r['dex']:<11} {r['base'][:12]:>12}/{r['quote'][:6]:<6} "
            f"${r['price_usd'] if r['price_usd'] is not None else '-':<12} liq ${r['liquidity_usd'] or 0:>14,.0f} "
            f"vol24 ${r['volume_h24'] or 0:>14,.0f} created {r['created']}")

on_api_tab()

# 1. Every pool of one token: /token-pairs/v1/<chain>/<address> (max 30 pools come back)
pools = {}
for chain, addr in TOKENS:
    rows = sorted((pair_row(p) for p in get(f"/token-pairs/v1/{chain}/{addr}")), key=lambda r: r["volume_h24"] or 0, reverse=True)
    pools[addr] = rows
    print(f"{chain}/{addr}: {len(rows)} pools, dexes {sorted({r['dex'] for r in rows})}")
    for r in rows[:3]:
        print("  ", short(r))

# 2. Many tokens on one chain in one call: /tokens/v1/<chain>/<a>,<b>,... (up to 30 addresses)
by_chain = {}
for chain, addr in TOKENS:
    by_chain.setdefault(chain, []).append(addr)
for chain, addrs in by_chain.items():
    for i in range(0, len(addrs), 30):
        rows = [pair_row(p) for p in get(f"/tokens/v1/{chain}/{','.join(addrs[i:i + 30])}")]
        for addr in addrs[i:i + 30]:
            mine = [r for r in rows if addr in (r["base_address"], r["quote_address"])]
            top = max(mine, key=lambda r: r["volume_h24"] or 0, default=None)
            print(f"tokens/v1 {chain} {addr[:10]}...: {len(mine)} pairs; top by 24h volume:", short(top) if top else "none")

# 3. Fresh numbers for known pairs: /latest/dex/pairs/<chain>/<p1>,<p2>,... (lowercase addresses from URLs are fine)
first = pools[TOKENS[0][1]][:2]
res = get(f"/latest/dex/pairs/{TOKENS[0][0]}/{','.join(r['pair'].lower() for r in first)}")
print("pairs lookup:", len(res["pairs"] or []), "of", len(first))
print(json.dumps(pair_row(res["pairs"][0]), indent=1, ensure_ascii=False))
```

Output observed on 2026-11-02:

```text
solana/JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN: 30 pools, dexes ['meteora', 'orca', 'pancakeswap', 'raydium']
   solana    orca                 JUP/SOL    $0.2443       liq $       619,273 vol24 $       780,244 created 2024-01-31T04:35Z
   solana    meteora              JUP/SOL    $0.2433       liq $     1,795,333 vol24 $       384,912 created 2024-01-31T14:59Z
   solana    meteora              JUP/USDC   $0.2435       liq $       275,196 vol24 $       257,203 created 2024-05-27T22:12Z
ethereum/0x6982508145454Ce325dDbE47a25d4ec3d2311933: 30 pools, dexes ['0x7de800467aFcE442019884f51A4A1B9143a34fAc', '9inch', '9mm', 'aero', 'balancer', 'metric', 'pancakeswap', 'supernova', 'uniswap']
   ethereum  uniswap             PEPE/WETH   $4.667e-06    liq $    30,619,496 vol24 $     1,851,318 created 2023-04-14T17:21Z
   ethereum  aero                PEPE/WETH   $4.663e-06    liq $       189,445 vol24 $        20,864 created None
   ethereum  metric              PEPE/WETH   $4.616e-06    liq $         7,871 vol24 $        17,625 created 2026-10-22T14:44Z
solana/zzqxNoSuchToken1111111111111111111111111111: 0 pools, dexes []
tokens/v1 solana JUPyiwrYJF...: 1 pairs; top by 24h volume: solana    orca                 JUP/SOL    $0.2443       liq $       619,273 vol24 $       780,244 created 2024-01-31T04:35Z
tokens/v1 solana zzqxNoSuch...: 0 pairs; top by 24h volume: none
tokens/v1 ethereum 0x69825081...: 1 pairs; top by 24h volume: ethereum  uniswap             PEPE/WETH   $4.667e-06    liq $    30,619,496 vol24 $     1,851,318 created 2023-04-14T17:21Z
pairs lookup: 2 of 2
{
 "chain": "solana",
 "dex": "orca",
 "labels": [
  "wp"
 ],
 "pair": "C1MgLojNLWBKADvu9BHdtgzz1oZX4dZ5zGdGcgvvW8Wz",
 "url": "https://dexscreener.com/solana/c1mglojnlwbkadvu9bhdtgzz1ozx4dz5zgdgcgvvw8wz",
 "base": "JUP",
 "base_name": "Jupiter",
 "base_address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
 "quote": "SOL",
 "quote_address": "So11111111111111111111111111111111111111112",
 "price_usd": 0.2443,
 "price_native": "0.002667",
 "liquidity_usd": 619272.92,
 "volume_h24": 780244.33,
 "change_h24": -4.08,
 "buys_h24": 3903,
 "sells_h24": 4182,
 "fdv": 1710354824,
 "market_cap": 811045228,
 "created": "2024-01-31T04:35Z",
 "boosts": null
}
```

### 3. New pairs, newest first (browser, dexscreener.com page + official API)

```python
import json, time
from datetime import datetime, timezone

CHAIN = ""      # "" = all chains, or a chainId such as "solana", "base", "bsc"
PAGES = 2       # 100 rows per page; page 2+ is /new-pairs/page-<n>
ENRICH = 30     # newest N rows also fetched from the official API for exact prices and creation times

SITE = "https://dexscreener.com"
ROW_JS = r"""(() => {
  const title = document.title;
  if (/just a moment|attention required/i.test(title) || document.querySelector('#challenge-error-text, iframe[src*="challenges.cloudflare.com"]'))
    return {challenge: true, title};
  const rows = [...document.querySelectorAll('a[href]')]
    .filter(a => /^\/[a-z0-9-]+\/[A-Za-z0-9]{20,}$/.test(a.getAttribute('href')) && a.children.length >= 3)
    .map(a => ({href: a.getAttribute('href'), cells: [...a.children[2].children].map(c => c.innerText.split('\n').map(s => s.trim()).filter(Boolean))}));
  const next = [...document.querySelectorAll('a[href*="/page-"]')].map(a => a.getAttribute('href'));
  return {challenge: false, title, rows, next};
})()"""

def open_site(url):
    """Load a dexscreener.com page in the attached tab (or a new one) and wait for its pair rows."""
    try:
        same = js("location.origin") == SITE
    except Exception:
        same = False
    goto_url(url) if same else new_tab(url)
    wait_for_load()
    t0 = time.time()
    while True:
        page = js(ROW_JS)
        if page["challenge"]:
            raise RuntimeError(f"{url}: challenge page ({page['title']!r}); stopping, do not retry")
        if page["rows"] or time.time() - t0 > 30:
            return page
        time.sleep(0.5)

def money(s):
    """'$8.5M' -> 8500000.0, '<$1' -> 0.0, '0' -> 0.0. Only for volume/liquidity/mcap cells, never for prices."""
    s = s.replace("$", "").replace(",", "").replace("<", "").strip()
    mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(s[-1:], 1)
    try:
        return float(s.rstrip("KMB")) * mult
    except ValueError:
        return None

def table_row(r):
    """One /new-pairs table row -> dict. 13 cells: token, price, age, buys, sells, volume, makers, 5m, 1h, 6h, 24h, liquidity, mcap."""
    chain, pair = r["href"].strip("/").split("/")
    c = r["cells"]
    tok = c[0]                     # ['#1', <labels...>, BASE, '/', QUOTE, name, <boosts>]
    i = tok.index("/")
    tail = tok[i + 2:]
    return {
        "rank": int(tok[0].lstrip("#")), "chain": chain, "pair": pair, "url": SITE + r["href"],
        "labels": tok[1:i - 1], "base": tok[i - 1], "quote": tok[i + 1],
        "name": tail[0] if tail else None,
        "boosts": int(tail[1].replace(",", "")) if len(tail) > 1 and tail[1].replace(",", "").isdigit() else 0,
        "price_text": c[1][0],          # display only: leading zeros are drawn as a subscript, so '$0.042120' can mean 0.00002120
        "age": c[2][0],
        "buys": int(c[3][0].replace(",", "")), "sells": int(c[4][0].replace(",", "")),
        "volume_usd": money(c[5][0]), "makers": int(c[6][0].replace(",", "")),
        "change": dict(zip(["m5", "h1", "h6", "h24"], (x[0] for x in c[7:11]))),
        "liquidity_usd": money(c[11][0]), "market_cap": money(c[12][0]),
    }

API = "https://api.dexscreener.com"
PER_MIN = {"slow": 60, "fast": 300}   # documented limits, requests per minute per endpoint group
FAST = ("/latest/dex/", "/tokens/v1/", "/token-pairs/v1/")   # 300/min; boosts, profiles, orders etc. are 60/min
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab
_last = {"slow": 0.0, "fast": 0.0}

def on_api_tab():
    """All API calls run as same-origin fetch() in a logged-out api.dexscreener.com tab; reuse it if already there."""
    try:
        if js("location.origin + ' ' + document.contentType") == API + " application/json":
            return
    except Exception:
        pass
    # A tiny JSON answer ("[]"). Not the host root: its 'Cannot GET /' 404 page sends CSP default-src 'none',
    # which makes every fetch() from that tab fail with "Failed to fetch".
    new_tab(API + "/token-pairs/v1/solana/x")
    wait_for_load()

START_JS = """(() => { window.__dx = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__dx = {status: r.status, len: t.length, ra: r.headers.get('retry-after'), body: t}; })
    .catch(e => { window.__dx = {status: 0, len: 0, err: String(e), body: ''}; });
  return 1; })()"""

def get(path, tries=4):
    """Serial GET of api.dexscreener.com<path>, paced under the documented limit. Returns parsed JSON.
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    bucket = "fast" if path.startswith(FAST) else "slow"
    url = API + path
    for attempt in range(tries):
        gap = 60 / PER_MIN[bucket] * 1.1 - (time.time() - _last[bucket])
        if gap > 0:
            time.sleep(gap)
        _last[bucket] = time.time()
        js(START_JS % json.dumps(url))   # fetch runs in the page; poll so slow answers do not hit js()'s timeout
        t0 = time.time()
        while not (meta := js("window.__dx && {status: window.__dx.status, len: window.__dx.len, ra: window.__dx.ra, err: window.__dx.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.3)
        status = meta["status"]
        if status == 200:
            text = "".join(js(f"window.__dx.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__dx = null")
            return json.loads(text)
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('err') or ''}; stopping")
        ra = meta.get("ra") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if isinstance(ms, (int, float)) else None

def pair_row(p):
    """One flat row per pair from search, token-pairs, tokens and pairs responses (all share the Pair schema)."""
    liq, vol, chg, tx = p.get("liquidity") or {}, p.get("volume") or {}, p.get("priceChange") or {}, (p.get("txns") or {}).get("h24") or {}
    return {
        "chain": p["chainId"], "dex": p["dexId"], "labels": p.get("labels") or [],
        "pair": p["pairAddress"], "url": p["url"],
        "base": p["baseToken"]["symbol"], "base_name": p["baseToken"]["name"], "base_address": p["baseToken"]["address"],
        "quote": p["quoteToken"]["symbol"], "quote_address": p["quoteToken"]["address"],
        "price_usd": float(p["priceUsd"]) if p.get("priceUsd") else None, "price_native": p.get("priceNative"),
        "liquidity_usd": liq.get("usd"), "volume_h24": vol.get("h24"), "change_h24": chg.get("h24"),
        "buys_h24": tx.get("buys"), "sells_h24": tx.get("sells"),
        "fdv": p.get("fdv"), "market_cap": p.get("marketCap"),
        "created": iso(p.get("pairCreatedAt")), "boosts": (p.get("boosts") or {}).get("active"),
    }

def short(r):
    return (f"{r['chain']:<9} {r['dex']:<11} {r['base'][:12]:>12}/{r['quote'][:6]:<6} "
            f"${r['price_usd'] if r['price_usd'] is not None else '-':<12} liq ${r['liquidity_usd'] or 0:>14,.0f} "
            f"vol24 ${r['volume_h24'] or 0:>14,.0f} created {r['created']}")

# 1. Read the New Pairs table, newest first (rankBy=pairAge&order=asc is what the site's "Newest" button sets)
rows, seen = [], set()
for n in range(1, PAGES + 1):
    path = "/new-pairs" + (f"/{CHAIN}" if CHAIN else "") + (f"/page-{n}" if n > 1 else "")
    try:
        page = open_site(SITE + path + "?rankBy=pairAge&order=asc")
    except RuntimeError as e:   # challenge page: stop paging, keep the rows already read, do not retry
        print(e)
        break
    got = [table_row(r) for r in page["rows"]]
    fresh = [r for r in got if (r["chain"], r["pair"]) not in seen]   # the list moves while you page; drop repeats
    seen.update((r["chain"], r["pair"]) for r in fresh)
    rows += fresh
    print(f"page {n}: {len(got)} rows, {len(fresh)} new, next link {page['next'][:1]}")
    time.sleep(5)
print(f"{len(rows)} pairs; chains {sorted({r['chain'] for r in rows})}")
for r in rows[:5]:
    print(f"  #{r['rank']:<3} {r['chain']:<9} {r['base'][:12]:>12}/{r['quote']:<6} age {r['age']:<6} liq ${r['liquidity_usd'] or 0:>10,.0f} "
          f"vol ${r['volume_usd'] or 0:>9,.0f} buys {r['buys']} sells {r['sells']} labels {r['labels']} shown price {r['price_text']}")

# 2. Exact numbers for the newest rows: /latest/dex/pairs/<chain>/<p1>,<p2>,... (30 per call, lowercase addresses OK)
on_api_tab()
api, calls = {}, []
todo = {}
for r in rows[:ENRICH]:
    todo.setdefault(r["chain"], []).append(r["pair"])
for chain, pairs in todo.items():
    for i in range(0, len(pairs), 30):
        got = get(f"/latest/dex/pairs/{chain}/{','.join(pairs[i:i + 30])}")["pairs"] or []
        calls.append((chain, len(pairs[i:i + 30]), len(got)))
        for p in got:
            api[(chain, p["pairAddress"].lower())] = pair_row(p)
print(f"API returned {len(api)} of {min(ENRICH, len(rows))} pairs; calls (chain, sent, returned): {calls}")
for r in rows[:5]:
    a = api.get((r["chain"], r["pair"].lower()))
    print(f"  {r['base'][:12]:>12}: shown {r['price_text']:<12} api price_usd {a and a['price_usd']}  created {a and a['created']}  dex {a and a['dex']}")
```

Output observed on 2026-11-02:

```text
page 1: 100 rows, 100 new, next link ['/new-pairs/page-2?order=asc&rankBy=pairAge']
page 2: 100 rows, 100 new, next link ['/new-pairs/page-3?order=asc&rankBy=pairAge']
200 pairs; chains ['arc', 'base', 'bsc', 'ethereum', 'hyperevm', 'optimism', 'robinhood', 'solana']
  #1   base             AIORA/WETH   age 24s    liq $     8,600 vol $        0 buys 1 sells 0 labels [] shown price $0.053893
  #2   solana           FLOAT/SOL    age 25s    liq $        18 vol $        1 buys 11 sells 0 labels ['CPMM'] shown price $0.071052
  #3   robinhood        AIORA/WETH   age 26s    liq $     8,600 vol $        0 buys 1 sells 0 labels [] shown price $0.053893
  #4   bsc               CAPY/WBNB   age 32s    liq $     9,400 vol $      944 buys 6 sells 2 labels ['V2'] shown price $0.042609
  #5   robinhood        WAGBI/WETH   age 34s    liq $     1,300 vol $        6 buys 1 sells 0 labels ['V4'] shown price $0.051381
API returned 30 of 30 pairs; calls (chain, sent, returned): [('base', 6, 6), ('solana', 8, 8), ('robinhood', 9, 9), ('bsc', 3, 3), ('optimism', 2, 2), ('arc', 2, 2)]
         AIORA: shown $0.053893    api price_usd 3.893e-06  created 2026-11-02T19:34Z  dex flapsh
         FLOAT: shown $0.071052    api price_usd 1.052e-08  created 2026-11-02T19:34Z  dex raydium
         AIORA: shown $0.053893    api price_usd 3.893e-06  created 2026-11-02T19:34Z  dex flapsh
          CAPY: shown $0.042609    api price_usd 2.875e-05  created 2026-11-02T19:34Z  dex pancakeswap
         WAGBI: shown $0.051381    api price_usd 1.381e-06  created 2026-11-02T19:34Z  dex uniswap
```

The shown price and the API price agree once the subscript zeros are counted: `$0.053893` on the page is `3.893e-06`. Seconds-old pairs also move between the page read and the API call (CAPY above). On an earlier run one 26 s old Base V4 pair was not yet in the API (29 of 30 returned); the block prints `None` for such rows instead of dropping them. A separate check sent 30 Solana pair addresses in one `/latest/dex/pairs` call and got 30 back.

### 4. Boosted tokens with market data (browser, official API)

```python
import json, time
from datetime import datetime, timezone

TOP_N = 10      # rows printed per list

API = "https://api.dexscreener.com"
PER_MIN = {"slow": 60, "fast": 300}   # documented limits, requests per minute per endpoint group
FAST = ("/latest/dex/", "/tokens/v1/", "/token-pairs/v1/")   # 300/min; boosts, profiles, orders etc. are 60/min
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab
_last = {"slow": 0.0, "fast": 0.0}

def on_api_tab():
    """All API calls run as same-origin fetch() in a logged-out api.dexscreener.com tab; reuse it if already there."""
    try:
        if js("location.origin + ' ' + document.contentType") == API + " application/json":
            return
    except Exception:
        pass
    # A tiny JSON answer ("[]"). Not the host root: its 'Cannot GET /' 404 page sends CSP default-src 'none',
    # which makes every fetch() from that tab fail with "Failed to fetch".
    new_tab(API + "/token-pairs/v1/solana/x")
    wait_for_load()

START_JS = """(() => { window.__dx = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__dx = {status: r.status, len: t.length, ra: r.headers.get('retry-after'), body: t}; })
    .catch(e => { window.__dx = {status: 0, len: 0, err: String(e), body: ''}; });
  return 1; })()"""

def get(path, tries=4):
    """Serial GET of api.dexscreener.com<path>, paced under the documented limit. Returns parsed JSON.
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    bucket = "fast" if path.startswith(FAST) else "slow"
    url = API + path
    for attempt in range(tries):
        gap = 60 / PER_MIN[bucket] * 1.1 - (time.time() - _last[bucket])
        if gap > 0:
            time.sleep(gap)
        _last[bucket] = time.time()
        js(START_JS % json.dumps(url))   # fetch runs in the page; poll so slow answers do not hit js()'s timeout
        t0 = time.time()
        while not (meta := js("window.__dx && {status: window.__dx.status, len: window.__dx.len, ra: window.__dx.ra, err: window.__dx.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.3)
        status = meta["status"]
        if status == 200:
            text = "".join(js(f"window.__dx.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__dx = null")
            return json.loads(text)
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('err') or ''}; stopping")
        ra = meta.get("ra") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if isinstance(ms, (int, float)) else None

def pair_row(p):
    """One flat row per pair from search, token-pairs, tokens and pairs responses (all share the Pair schema)."""
    liq, vol, chg, tx = p.get("liquidity") or {}, p.get("volume") or {}, p.get("priceChange") or {}, (p.get("txns") or {}).get("h24") or {}
    return {
        "chain": p["chainId"], "dex": p["dexId"], "labels": p.get("labels") or [],
        "pair": p["pairAddress"], "url": p["url"],
        "base": p["baseToken"]["symbol"], "base_name": p["baseToken"]["name"], "base_address": p["baseToken"]["address"],
        "quote": p["quoteToken"]["symbol"], "quote_address": p["quoteToken"]["address"],
        "price_usd": float(p["priceUsd"]) if p.get("priceUsd") else None, "price_native": p.get("priceNative"),
        "liquidity_usd": liq.get("usd"), "volume_h24": vol.get("h24"), "change_h24": chg.get("h24"),
        "buys_h24": tx.get("buys"), "sells_h24": tx.get("sells"),
        "fdv": p.get("fdv"), "market_cap": p.get("marketCap"),
        "created": iso(p.get("pairCreatedAt")), "boosts": (p.get("boosts") or {}).get("active"),
    }

def short(r):
    return (f"{r['chain']:<9} {r['dex']:<11} {r['base'][:12]:>12}/{r['quote'][:6]:<6} "
            f"${r['price_usd'] if r['price_usd'] is not None else '-':<12} liq ${r['liquidity_usd'] or 0:>14,.0f} "
            f"vol24 ${r['volume_h24'] or 0:>14,.0f} created {r['created']}")

on_api_tab()

# 1. Both boost lists (60 requests/min each): newest boost orders, and tokens with the most active boosts
latest = get("/token-boosts/latest/v1")
top = get("/token-boosts/top/v1")
print(f"latest: {len(latest)} rows, top: {len(top)} rows")

# 2. Market data for every boosted token: /tokens/v1/<chain>/<up to 30 addresses> returns its main pair
tokens = {}
for b in latest + top:
    tokens.setdefault(b["chainId"], set()).add(b["tokenAddress"])
market, calls = {}, []
for chain, addrs in tokens.items():
    addrs = sorted(addrs)
    for i in range(0, len(addrs), 30):
        got = get(f"/tokens/v1/{chain}/{','.join(addrs[i:i + 30])}")
        calls.append((chain, len(addrs[i:i + 30]), len(got)))
        for p in got:
            r = pair_row(p)
            key = (chain, r["base_address"])
            if key not in market or (r["volume_h24"] or 0) > (market[key]["volume_h24"] or 0):
                market[key] = r
print(f"{sum(len(a) for a in tokens.values())} distinct tokens on {sorted(tokens)}; market data for {len(market)}; calls (chain, sent, returned): {calls}")

def boost_row(b):
    m = market.get((b["chainId"], b["tokenAddress"])) or {}
    return {
        "chain": b["chainId"], "token": b["tokenAddress"], "url": b["url"],
        "amount": b.get("amount"),               # this boost order (latest list only)
        "total_amount": b.get("totalAmount"),    # all active boosts on the token
        "symbol": m.get("base"), "name": m.get("base_name"), "price_usd": m.get("price_usd"),
        "liquidity_usd": m.get("liquidity_usd"), "volume_h24": m.get("volume_h24"), "change_h24": m.get("change_h24"),
        "market_cap": m.get("market_cap"), "pair_created": m.get("created"), "pair_url": m.get("url"),
        "links": [l.get("url") for l in b.get("links") or []],
        "description": (b.get("description") or "")[:120],
    }

for title, lst in (("TOP (most active boosts)", top), ("LATEST boost orders", latest)):
    print(title)
    for r in map(boost_row, lst[:TOP_N]):
        print(f"  {r['chain']:<8} {str(r['symbol'])[:12]:>12} total {r['total_amount']:>5} amount {str(r['amount']):>5} "
              f"mcap ${r['market_cap'] or 0:>14,.0f} vol24 ${r['volume_h24'] or 0:>12,.0f} pair created {r['pair_created']}")
print(json.dumps(boost_row(top[0]), indent=1, ensure_ascii=False))
```

Output observed on 2026-11-02:

```text
latest: 30 rows, top: 30 rows
43 distinct tokens on ['arc', 'robinhood', 'solana']; market data for 43; calls (chain, sent, returned): [('robinhood', 10, 10), ('solana', 30, 30), ('solana', 2, 2), ('arc', 1, 1)]
TOP (most active boosts)
  solana         ANAKIN total   500 amount  None mcap $     1,042,595 vol24 $   8,583,702 pair created 2026-11-01T22:28Z
  solana         Anakin total   500 amount  None mcap $     1,532,722 vol24 $   2,688,486 pair created 2026-10-29T19:28Z
  solana           RICO total   500 amount  None mcap $       144,162 vol24 $     260,391 pair created 2026-11-02T16:26Z
  solana           GATO total   200 amount  None mcap $    11,178,515 vol24 $   2,773,870 pair created 2026-08-25T12:27Z
  solana           HELL total   100 amount  None mcap $     3,077,075 vol24 $     157,752 pair created 2026-10-13T13:03Z
  solana       MAMESUKE total   100 amount  None mcap $     1,438,286 vol24 $   3,457,922 pair created 2026-11-02T11:34Z
  solana           DIGS total   100 amount  None mcap $        81,322 vol24 $     251,858 pair created 2026-10-28T12:32Z
  solana         GLITCH total   100 amount  None mcap $     3,044,654 vol24 $     445,694 pair created 2026-10-16T15:34Z
  robinhood          OAK total   100 amount  None mcap $       131,312 vol24 $     197,382 pair created 2026-11-02T04:59Z
  robinhood    SLIPPYGME total   100 amount  None mcap $       112,891 vol24 $      20,639 pair created 2026-11-01T05:19Z
LATEST boost orders
  robinhood         FOBO total    50 amount    50 mcap $       848,064 vol24 $      66,149 pair created 2026-10-26T17:02Z
  solana            GTA total    10 amount    10 mcap $        28,960 vol24 $      99,872 pair created 2026-11-02T13:29Z
  solana          SOULD total    10 amount    10 mcap $         8,313 vol24 $         483 pair created 2026-10-17T16:36Z
  solana        NETWORK total    10 amount    10 mcap $       119,411 vol24 $     184,338 pair created 2026-10-24T21:48Z
  solana           KUIP total    10 amount    10 mcap $        36,233 vol24 $      85,598 pair created 2026-11-01T23:08Z
  solana        MINUSIQ total    10 amount    10 mcap $         3,657 vol24 $       4,692 pair created 2026-11-02T18:08Z
  solana          SHORT total    50 amount    50 mcap $        38,286 vol24 $       7,921 pair created 2026-11-02T17:19Z
  arc           SAFEARC total    10 amount    10 mcap $        19,156 vol24 $         426 pair created 2026-10-07T11:04Z
  solana         CBUCKS total    10 amount    10 mcap $     1,704,577 vol24 $     174,426 pair created 2026-10-06T18:29Z
  solana           ANTI total    10 amount    10 mcap $         8,101 vol24 $      25,083 pair created 2026-11-02T16:54Z
{
 "chain": "solana",
 "token": "8s4bNqEztH1JP7mkU747uMr7AckCQdiV47FDqYnDpump",
 "url": "https://dexscreener.com/solana/8s4bnqezth1jp7mku747umr7ackcqdiv47fdqyndpump",
 "amount": null,
 "total_amount": 500,
 "symbol": "ANAKIN",
 "name": "Anakin Coin",
 "price_usd": 0.001047,
 "liquidity_usd": 91618.21,
 "volume_h24": 8583701.57,
 "change_h24": 1941,
 "market_cap": 1042595,
 "pair_created": "2026-11-01T22:28Z",
 "pair_url": "https://dexscreener.com/solana/hcgpz2exv8sfcmvq9fjpbd71brljvzutd2avvv86gwbk",
 "links": [
  "https://anakin.meme",
  "https://x.com/AnakinMemeCoin"
 ],
 "description": "<the token's own promo text, omitted here>"
}
```

`description` is free text the token's promoter wrote; one value is replaced above.

## Fields

Pair row (`pair_row()`, blocks 1, 2, 4 and the API half of 3):

| Key | Source | Notes |
|---|---|---|
| `chain`, `dex` | `chainId`, `dexId` | `dexId` is sometimes a raw contract address (seen on Ethereum) |
| `labels` | `labels` | pool type, e.g. `v2`, `v4`, `wp`, `DLMM`, `CPMM` |
| `pair`, `url` | `pairAddress`, `url` | `pairAddress` keeps the chain's case; `url` is lowercased |
| `base*`, `quote*` | `baseToken`, `quoteToken` | symbols are free text; one search hit had a symbol thousands of characters long |
| `price_usd`, `price_native` | `priceUsd`, `priceNative` | strings in the API; `priceUsd` can be missing |
| `liquidity_usd` | `liquidity.usd` | can be absurd on thin pools (billions next to $50 of 24h volume); rank by volume |
| `volume_h24`, `change_h24`, `buys_h24`, `sells_h24` | `volume`, `priceChange`, `txns` | the API also has `m5`, `h1`, `h6` |
| `fdv`, `market_cap` | `fdv`, `marketCap` | USD |
| `created` | `pairCreatedAt` (ms) | missing on some pairs (Aerodrome on Base, Aero on Ethereum) |
| `boosts` | `boosts.active` | only present on boosted pairs |

New Pairs table row (`table_row()`): `rank`, `chain`, `pair` (lowercase, from the row link), `labels`, `base`, `quote`, `name`, `boosts` (0 if no badge), `price_text` (display only), `age` (`18s`, `7h 53m`), `buys`, `sells`, `volume_usd`, `makers`, `change` (`m5`/`h1`/`h6`/`h24` as shown), `liquidity_usd`, `market_cap`. Dollar cells like `$8.5M` are parsed to floats by `money()`, so they are rounded.

Boost row (block 4): `chain`, `token`, `url`, `amount` (this order; latest list only), `total_amount` (all active boosts on the token), `links`, `description`, plus the main pair's market data from `/tokens/v1`.

## Gotchas

- **30-row caps.** Search, token-pairs and both boost lists returned exactly 30 rows for busy inputs (PEPE, JUP, SOL). There is no page parameter; do not reshape queries to get around it. Use `/tokens/v1` or `/latest/dex/pairs` when you already know addresses.
- **Unknown inputs are not errors.** Unknown search text gives `{"pairs": []}`, an unknown token `[]`, an unknown pair `{"pairs": null, "pair": null}`, all HTTP 200.
- **Do not open the API host root as the fetch tab.** `https://api.dexscreener.com/` is an HTTP 404 page with `Content-Security-Policy: default-src 'none'`, so every `fetch()` from it fails with `TypeError: Failed to fetch`. `on_api_tab()` opens a JSON answer instead and checks `document.contentType`.
- **Caching:** API answers carried `Cache-Control: public, max-age=30` (pairs, tokens) or `max-age=60` (search, boosts), so repeating a call within that window can return the same numbers.
- **Lowercase pair addresses work.** Row links on dexscreener.com are lowercased even for case-sensitive Solana addresses; `/latest/dex/pairs` accepted them and returned the real `pairAddress`.
- **New Pairs moves while you read it.** Rows are seconds old and shift between page loads; block 3 drops pairs it already saw. Class names are hashed (`dsp-...`), so the block keys on row links (`/<chain>/<address>`) and the 13-cell order.
- **Plain HTTP:** `curl` to api.dexscreener.com answered 200 today; dexscreener.com answered `curl` with a Cloudflare "Just a moment..." 403, so the New Pairs page needs the browser. If the browser gets a challenge page, `open_site()` stops; do not retry around it.
- **Cloudflare on page 2.** In a fresh cloud browser on 2026-11-02, `/new-pairs/page-2` once loaded as a Cloudflare "Just a moment..." page right after page 1. Block 3 then stops paging and keeps the rows it already has; the API half still runs.
- **API terms** (https://docs.dexscreener.com/api/api-terms-and-conditions) forbid using the API to build a product that competes directly with DEX Screener.

## What does not work

- **New pairs via the API:** no documented endpoint lists new pairs; this skill reads the robots-allowed `/new-pairs` page and only enriches its rows through the API.
- **More than 30 search or token-pairs results:** not available from the free endpoints.
- **Untested:** `/token-profiles/latest/v1`, `/token-profiles/recent-updates/v1`, `/community-takeovers/latest/v1`, `/ads/latest/v1`, `/metas/*` and `/orders/v1/<chainId>/<tokenAddress>` are documented at 60/min but were not exercised here; WebSockets (https://docs.dexscreener.com/api/websockets) were not tried.
