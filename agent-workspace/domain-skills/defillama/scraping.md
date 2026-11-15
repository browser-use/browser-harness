# DefiLlama - TVL by Protocol and Chain, Protocol TVL History, Yield Pools (official free API)

Field-tested against api.llama.fi, yields.llama.fi and defillama.com on 2026-11-04 UTC (evening of 2026-11-03 US time) using a Browser Use cloud browser, logged out. Every browser call is a `fetch()` from a defillama.com tab to DefiLlama's free, keyless API. No CAPTCHA, 403 or 429 across about 50 browser API calls and 10 plain HTTP calls.

robots.txt (defillama.com, read in the browser 2026-11-04): `User-agent: *` / `Allow: /`; api.llama.fi/robots.txt is HTTP 404 (`Route not found`) and yields.llama.fi/robots.txt is HTTP 404 (`Cannot GET /robots.txt`), so neither API host has rules; the blocks use only the free API endpoints under the official-API exception (https://api-docs.defillama.com: "The free API needs no key").

## Quick summary

- **No scraping.** Six free JSON endpoints cover the task. No key, no cookies:
  - `GET https://api.llama.fi/protocols` - every protocol with current `tvl`, `chainTvls` per chain, `change_1d` / `change_7d`, `category`, `slug` (9.5 MB, 8,927 rows).
  - `GET https://api.llama.fi/v2/chains` - current TVL per chain (420 rows).
  - `GET https://api.llama.fi/protocol/<slug>` - full daily TVL history, per-chain history and current per-chain split (11 MB for `aave`).
  - `GET https://api.llama.fi/v2/historicalChainTvl[/<chain>]` - daily DeFi TVL of one chain or of all chains.
  - `GET https://yields.llama.fi/pools` - every yield pool: APY (base + reward), TVL, 30-day mean, stablecoin flag (11 MB, 15,932 pools).
  - `GET https://yields.llama.fi/chart/<pool>` - daily APY and TVL of one pool.
  - `GET https://api.llama.fi/tvl/<slug>` - one number, handy for plain HTTP.
- **Free yield endpoints end on 2026-11-13.** The docs banner says: "The free yield endpoints /pools and /chart/{pool} shut down on November 13, 2026. The same data remains available on the API plan at /yields/v1/pools and /yields/v1/chart/{pool}." Block 3 stops working then; the TVL blocks are unaffected.
- **Yields live on `yields.llama.fi`**, not `api.llama.fi`. The docs' llms-free.txt lists `/pools` under base `https://api.llama.fi`, but there it answers HTTP 404 `Route not found`.
- **Parse in the page, return a slice.** Responses are up to 11 MB and `js()` gives up after 5 s, so the shared `get()` starts the `fetch()`, polls until it lands, keeps the parsed JSON in `window.__llama`, and returns only what a JS `pick` function selects. A second `get()` on the same URL reuses the cached copy.
- **Chain names differ by endpoint.** `/protocols` keys chains by legacy names (`Binance`, `Optimism`, `xDai`, `zkSync Era`); `/v2/chains`, `/pools` and parent protocols use `BSC`, `OP Mainnet`, `Gnosis`, `ZKsync Era`. Block 1 maps them through the shared `gecko_id` in `/v2/chains` (Binance, Optimism), a case-insensitive match (zkSync Era) and a small `ALIASES` table (xDai), and raises if a chain with TVL matches no protocol. Other `/protocols` keys such as `Klaytn`, `Pulse`, `Ripple`, `Op_Bnb` and `Elrond` have no row in `/v2/chains` either.

## What works

All browser blocks share the same helpers: `on_llama_tab()` opens `https://defillama.com/robots.txt` (small, robots-allowed) once and later blocks reuse that tab; it raises if anything other than robots.txt comes back. `get(url, pick)` returns `pick(json)`, `None` on 400/404 (unknown slug or chain), backs off on 429/5xx and otherwise raises, so a failed call never looks like an empty result. Calls are serial with a 0.5 s pause.

### 1. TVL by chain, by protocol, and by protocol on one chain (browser)

```python
import json, os, tempfile, time

CHAIN = "BSC"        # display name from /v2/chains: Ethereum, Base, Solana, BSC, OP Mainnet, Gnosis, ...
CATEGORY = None      # e.g. "Lending", "Dexs", "Liquid Staking"; None = every category except CEX
TOP = 10

PAUSE = 0.5          # seconds between API calls; keep calls serial

def on_llama_tab():
    """Run fetch() from a logged-out defillama.com tab (robots.txt: Allow /). Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://defillama.com":
            return
    except Exception:
        pass
    new_tab("https://defillama.com/robots.txt")
    wait_for_load()
    if "User-agent" not in (js("document.body.innerText.slice(0, 200)") or ""):
        raise RuntimeError(f"defillama.com did not serve robots.txt (title {js('document.title')!r}): stop, do not retry around it")

START_JS = """(() => { const u = %s; window.__llama = window.__llama || {};
  if (window.__llama[u] && window.__llama[u].status === 200) return 'cached';
  window.__llama[u] = null;
  fetch(u, {credentials: 'omit'}).then(async r => { const t = await r.text(); let d = null; try { d = JSON.parse(t); } catch (e) {}
      window.__llama[u] = {status: r.status, data: d, text: t.slice(0, 200)}; })
    .catch(e => { window.__llama[u] = {status: 0, data: null, text: String(e)}; });
  return 'started'; })()"""

def get(url, pick="d => d", timeout=90, tries=3):
    """fetch() url in the page, keep the parsed JSON there (responses run to ~11 MB) and return pick(json) to Python.
    pick is a JS arrow function that trims the payload. None on 400/404 (unknown slug or chain); backs off on 429/5xx; else raises."""
    u = json.dumps(url)
    for attempt in range(tries):
        if js(START_JS % u) == "started":
            t0 = time.time()
            while js("(() => { const x = window.__llama[%s]; return x ? x.status : null; })()" % u) is None:
                if time.time() - t0 > timeout:
                    raise RuntimeError(f"{url}: no response in {timeout}s")
                time.sleep(0.5)
            time.sleep(PAUSE)
        st = js("window.__llama[%s].status" % u)
        if st == 200:
            return js("(%s)(window.__llama[%s].data)" % (pick, u))
        if st in (400, 404):
            return None
        if st not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {st} {js('window.__llama[%s].text' % u)!r}; stopping")
        time.sleep(5 * 2 ** attempt)

on_llama_tab()

# 1. Chains ranked by current TVL. /v2/chains also carries legacy duplicate rows with tvl 0 (Binance, Optimism).
chains = get("https://api.llama.fi/v2/chains", "d => d.map(c => ({name: c.name, tvl: c.tvl, symbol: c.tokenSymbol, chainId: c.chainId, gecko_id: c.gecko_id}))")
chains.sort(key=lambda c: c["tvl"], reverse=True)
print(f"{len(chains)} chains; top {TOP} by TVL:")
for i, c in enumerate(chains[:TOP], 1):
    print(f"{i:>2}. {c['name']:<16} ${c['tvl']/1e9:>7.2f}B  {c['symbol'] or ''}")

# 2. /protocols names chains by legacy keys (BSC -> Binance, OP Mainnet -> Optimism, Gnosis -> xDai): collect the aliases.
#    Binance and Optimism are tvl-0 rows in /v2/chains sharing the gecko_id; xDai is not a row there, so it sits in ALIASES.
ALIASES = {"Gnosis": ["xDai"]}   # add more if the check below raises
row = next((c for c in chains if c["name"].lower() == CHAIN.lower()), None)
if row is None:
    raise ValueError(f"{CHAIN!r} is not a chain name in /v2/chains")
keys = [row["name"]] + [c["name"] for c in chains if row["gecko_id"] and c["gecko_id"] == row["gecko_id"] and c["name"] != row["name"]]
keys += ALIASES.get(row["name"], [])

# 3. Protocols: overall ranking and ranking on CHAIN. `tvl` and chainTvls[<chain>] exclude borrowed, staking and pool2.
#    Keys match case-insensitively: /protocols says "zkSync Era" where /v2/chains says "ZKsync Era".
PICK = """d => d.filter(p => p.category !== 'CEX' && (%s === null || p.category === %s)).map(p => {
  const ks = %s.map(s => s.toLowerCase()), k = Object.keys(p.chainTvls).find(k => ks.includes(k.toLowerCase()));
  return {name: p.name, slug: p.slug, category: p.category, tvl: p.tvl || 0, change_1d: p.change_1d, change_7d: p.change_7d,
          chains: p.chains.length, parent: p.parentProtocol || null, on_chain: k ? p.chainTvls[k] : 0};
})""" % (json.dumps(CATEGORY), json.dumps(CATEGORY), json.dumps(keys))
protocols = get("https://api.llama.fi/protocols", PICK)
pct = lambda x: "   n/a" if x is None else f"{x:+6.1f}%"

top = sorted(protocols, key=lambda p: p["tvl"], reverse=True)[:TOP]
print(f"\n{len(protocols)} protocols ({CATEGORY or 'all categories except CEX'}); top {TOP} by TVL:")
for i, p in enumerate(top, 1):
    print(f"{i:>2}. {p['name']:<22} {p['category']:<15} ${p['tvl']/1e9:>6.2f}B  1d {pct(p['change_1d'])}  7d {pct(p['change_7d'])}  {p['chains']} chains  slug={p['slug']}")

on = sorted((p for p in protocols if p["on_chain"] > 0), key=lambda p: p["on_chain"], reverse=True)
if not on and row["tvl"] > 0 and CATEGORY is None:
    raise RuntimeError(f"no /protocols chainTvls key matched {keys}: /protocols uses another name for {row['name']}; add it to ALIASES")
print(f"\nTop {TOP} on {row['name']} (chain keys {keys}); {len(on)} protocols with TVL there:")
for i, p in enumerate(on[:TOP], 1):
    print(f"{i:>2}. {p['name']:<22} {p['category']:<15} ${p['on_chain']/1e6:>9,.1f}M  ({p['on_chain']/p['tvl']:.0%} of its TVL)")

out = os.path.join(tempfile.gettempdir(), "defillama_tvl.json")
json.dump({"chains": chains, "protocols": protocols, "chain": row["name"], "chain_keys": keys}, open(out, "w"), indent=1)
print("saved", out)
```

Output observed on 2026-11-04 UTC:

```text
420 chains; top 10 by TVL:
 1. Ethereum         $  43.76B  ETH
 2. Base             $   5.94B  
 3. Solana           $   5.41B  SOL
 4. BSC              $   5.15B  BNB
 5. Tron             $   5.01B  TRX
 6. Bitcoin          $   4.10B  BTC
 7. Hyperliquid L1   $   2.58B  HYPE
 8. Arbitrum         $   1.45B  ARB
 9. Robinhood Chain  $   1.08B  
10. Monad            $   0.91B  MON

8843 protocols (all categories except CEX); top 10 by TVL:
 1. Lido                   Liquid Staking  $ 21.92B  1d   +0.0%  7d   -3.6%  5 chains  slug=lido
 2. LayerZero V2           Bridge          $ 16.87B  1d   +2.9%  7d   +1.3%  91 chains  slug=layerzero-v2
 3. Aave V3                Lending         $ 15.23B  1d   -1.2%  7d   -8.3%  21 chains  slug=aave-v3
 4. SSV Network            Staking Pool    $ 11.81B  1d   -0.0%  7d   -3.8%  1 chains  slug=ssv-network
 5. Morpho Blue            Lending         $ 11.08B  1d   +1.4%  7d   -1.7%  45 chains  slug=morpho-blue
 6. WBTC                   Bridge          $  8.97B  1d   -0.1%  7d   -4.6%  1 chains  slug=wbtc
 7. Binance staked ETH     Liquid Staking  $  8.78B  1d   +1.2%  7d   -2.6%  2 chains  slug=binance-staked-eth
 8. Coinbase Bridge        Bridge          $  7.70B  1d   -0.0%  7d   -3.7%  5 chains  slug=coinbase-bridge
 9. Hyperliquid Bridge     Bridge          $  6.34B  1d   -0.4%  7d   -4.1%  2 chains  slug=hyperliquid-bridge
10. EigenCloud             Restaking       $  5.77B  1d   -0.6%  7d   -4.8%  1 chains  slug=eigencloud

Top 10 on BSC (chain keys ['BSC', 'Binance']); 804 protocols with TVL there:
 1. PancakeSwap AMM        Dexs            $  1,444.7M  (100% of its TVL)
 2. Venus Core Pool        Lending         $  1,134.9M  (100% of its TVL)
 3. Lista Lending          Lending         $    904.1M  (99% of its TVL)
 4. Lista Liquid Staking   Liquid Staking  $    708.0M  (100% of its TVL)
 5. PancakeSwap AMM V3     Dexs            $    631.9M  (91% of its TVL)
 6. Gauntlet               Risk Curators   $    522.7M  (34% of its TVL)
 7. Binance staked ETH     Liquid Staking  $    479.1M  (5% of its TVL)
 8. Aster Bridge           Bridge          $    283.4M  (56% of its TVL)
 9. Solv Basis Trading     Basis Trading   $    194.0M  (100% of its TVL)
10. Aave V3                Lending         $    193.8M  (1% of its TVL)
saved <tempdir>/defillama_tvl.json
```

### 2. Protocol TVL history, per-chain split, and chain history (browser)

`/protocol/<slug>` works for a single protocol (`aave-v3`) and for a parent (`aave`, which sums its 7 children and is not a row in `/protocols`).

```python
import json, os, tempfile, time
from datetime import datetime, timezone

SLUGS = ["aave-v3", "aave", "no-such-protocol"]   # protocol slugs from /protocols (`slug`); "aave" is a parent
CHAIN = "Ethereum"                                 # also print this chain's DeFi TVL history
MONTHS = 6                                         # month-start points to print

PAUSE = 0.5

def on_llama_tab():
    """Run fetch() from a logged-out defillama.com tab (robots.txt: Allow /). Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://defillama.com":
            return
    except Exception:
        pass
    new_tab("https://defillama.com/robots.txt")
    wait_for_load()
    if "User-agent" not in (js("document.body.innerText.slice(0, 200)") or ""):
        raise RuntimeError(f"defillama.com did not serve robots.txt (title {js('document.title')!r}): stop, do not retry around it")

START_JS = """(() => { const u = %s; window.__llama = window.__llama || {};
  if (window.__llama[u] && window.__llama[u].status === 200) return 'cached';
  window.__llama[u] = null;
  fetch(u, {credentials: 'omit'}).then(async r => { const t = await r.text(); let d = null; try { d = JSON.parse(t); } catch (e) {}
      window.__llama[u] = {status: r.status, data: d, text: t.slice(0, 200)}; })
    .catch(e => { window.__llama[u] = {status: 0, data: null, text: String(e)}; });
  return 'started'; })()"""

def get(url, pick="d => d", timeout=90, tries=3):
    """fetch() url in the page, keep the parsed JSON there and return pick(json). None on 400/404; backs off on 429/5xx; else raises."""
    u = json.dumps(url)
    for attempt in range(tries):
        if js(START_JS % u) == "started":
            t0 = time.time()
            while js("(() => { const x = window.__llama[%s]; return x ? x.status : null; })()" % u) is None:
                if time.time() - t0 > timeout:
                    raise RuntimeError(f"{url}: no response in {timeout}s")
                time.sleep(0.5)
            time.sleep(PAUSE)
        st = js("window.__llama[%s].status" % u)
        if st == 200:
            return js("(%s)(window.__llama[%s].data)" % (pick, u))
        if st in (400, 404):
            return None
        if st not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {st} {js('window.__llama[%s].text' % u)!r}; stopping")
        time.sleep(5 * 2 ** attempt)

day = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")

def month_starts(series, n):
    """series: [(ts, usd)] ascending -> the first point of each of the last n months, plus the latest point."""
    seen, out = set(), []
    for ts, v in series:
        m = day(ts)[:7]
        if m not in seen:
            seen.add(m)
            out.append((ts, v))
    return out[-n:] + [series[-1]]

# The 11 MB /protocol/<slug> payload stays in the page; only the series and current breakdown come back.
PICK = """d => ({name: d.name, id: d.id, category: d.category || null, parent: d.parentProtocol || null,
  children: d.isParentProtocol ? d.otherProtocols.slice(1) : null,
  tvl: d.tvl.map(x => [x.date, x.totalLiquidityUSD]),
  current: Object.fromEntries(Object.entries(d.currentChainTvls).filter(([k]) => !k.includes('-') && !['borrowed', 'staking', 'pool2', 'vesting', 'treasury', 'doublecounted', 'liquidstaking', 'dcAndLsOverlap'].includes(k))),
  borrowed: d.currentChainTvls.borrowed || null})"""

on_llama_tab()
saved = {}
for slug in SLUGS:
    p = get(f"https://api.llama.fi/protocol/{slug}", PICK)
    if p is None:
        print(f"\n{slug}: not found (HTTP 400 'Protocol not found')")
        continue
    s = p["tvl"]
    now_ts, now = s[-1]
    ath_ts, ath = max(s, key=lambda x: x[1])
    ago = lambda days: next((v for ts, v in reversed(s) if ts <= now_ts - days * 86400), None)
    chg = lambda old: f"{(now / old - 1) * 100:+.1f}%" if old else "n/a"
    print(f"\n{p['name']} [{slug}] {p['category'] or 'parent of ' + str(p['children'])}")
    print(f"TVL ${now/1e9:.3f}B at {datetime.fromtimestamp(now_ts, timezone.utc):%Y-%m-%d %H:%M} UTC | 30d {chg(ago(30))} | 365d {chg(ago(365))} | ATH ${ath/1e9:.2f}B on {day(ath_ts)} | {len(s)} points since {day(s[0][0])}")
    if p["borrowed"]:
        print(f"borrowed (not in TVL): ${p['borrowed']/1e9:.2f}B")
    cur = sorted(p["current"].items(), key=lambda kv: kv[1], reverse=True)
    print("by chain now:", ", ".join(f"{k} ${v/1e6:,.0f}M" for k, v in cur[:6]), f"(+{len(cur) - 6} more)" if len(cur) > 6 else "")
    print("chain sum vs TVL:", f"${sum(v for _, v in cur)/1e9:.3f}B vs ${now/1e9:.3f}B")
    print("month starts:", " | ".join(f"{day(ts)} ${v/1e9:.2f}B" for ts, v in month_starts(s, MONTHS)))
    saved[slug] = p

c = get(f"https://api.llama.fi/v2/historicalChainTvl/{CHAIN}", "d => d.map(x => [x.date, x.tvl])")
if c is None:
    print(f"\n{CHAIN}: unknown chain (HTTP 404)")
else:
    print(f"\n{CHAIN} DeFi TVL: {len(c)} daily points, latest {day(c[-1][0])} ${c[-1][1]/1e9:.2f}B, peak ${max(v for _, v in c)/1e9:.2f}B on {day(max(c, key=lambda x: x[1])[0])}")
    print("month starts:", " | ".join(f"{day(ts)} ${v/1e9:.2f}B" for ts, v in month_starts(c, MONTHS)))
    saved["chain:" + CHAIN] = c

out = os.path.join(tempfile.gettempdir(), "defillama_history.json")
json.dump(saved, open(out, "w"))
print("saved", out)
```

Output observed on 2026-11-04 UTC:

```text

Aave V3 [aave-v3] Lending
TVL $15.226B at 2026-11-04 02:19 UTC | 30d -18.2% | 365d -55.9% | ATH $45.44B on 2025-10-07 | 1698 points since 2022-03-14
borrowed (not in TVL): $11.25B
by chain now: Ethereum $12,648M, Base $513M, Arbitrum $492M, Plasma $431M, Monad $281M, Avalanche $280M (+15 more)
chain sum vs TVL: $15.226B vs $15.226B
month starts: 2026-06-01 $13.32B | 2026-07-01 $11.63B | 2026-08-01 $13.70B | 2026-09-01 $17.46B | 2026-10-01 $18.13B | 2026-11-01 $15.24B | 2026-11-04 $15.23B

Aave [aave] parent of ['Aave V3', 'Aave V4', 'Aave Horizon RWA', 'Aave V2', 'Aave V1', 'Aave Aptos', 'Aave Arc']
TVL $16.297B at 2026-11-04 02:19 UTC | 30d -17.2% | 365d -53.6% | ATH $45.81B on 2025-10-07 | 2361 points since 2020-05-20
borrowed (not in TVL): $11.79B
by chain now: Ethereum $13,438M, Base $527M, Arbitrum $492M, Plasma $431M, Avalanche $373M, Monad $281M (+17 more)
chain sum vs TVL: $16.297B vs $16.297B
month starts: 2026-06-01 $13.88B | 2026-07-01 $12.17B | 2026-08-01 $14.27B | 2026-09-01 $18.19B | 2026-10-01 $19.17B | 2026-11-01 $16.24B | 2026-11-04 $16.30B

no-such-protocol: not found (HTTP 400 'Protocol not found')

Ethereum DeFi TVL: 3326 daily points, latest 2026-11-04 $43.67B, peak $107.42B on 2021-11-09
month starts: 2026-06-01 $40.08B | 2026-07-01 $34.21B | 2026-08-01 $38.73B | 2026-09-01 $46.36B | 2026-10-01 $50.18B | 2026-11-01 $43.70B | 2026-11-04 $43.67B
saved <tempdir>/defillama_history.json
```

### 3. Yield pools by chain, asset and TVL, plus one pool's APY history (browser)

Works until 2026-11-13 (free yield endpoints end, see Quick summary).

```python
import json, os, tempfile, time
from statistics import mean

CHAIN = "Base"          # pool `chain` uses /v2/chains display names (BSC, OP Mainnet, ...)
SYMBOL = "USDC"         # exact pool symbol; multi-asset pools look like "USDC-WETH"; None = any
STABLE_ONLY = True      # pool `stablecoin` flag
MIN_TVL = 1_000_000     # USD
TOP = 10

PAUSE = 0.5

def on_llama_tab():
    """Run fetch() from a logged-out defillama.com tab (robots.txt: Allow /). Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://defillama.com":
            return
    except Exception:
        pass
    new_tab("https://defillama.com/robots.txt")
    wait_for_load()
    if "User-agent" not in (js("document.body.innerText.slice(0, 200)") or ""):
        raise RuntimeError(f"defillama.com did not serve robots.txt (title {js('document.title')!r}): stop, do not retry around it")

START_JS = """(() => { const u = %s; window.__llama = window.__llama || {};
  if (window.__llama[u] && window.__llama[u].status === 200) return 'cached';
  window.__llama[u] = null;
  fetch(u, {credentials: 'omit'}).then(async r => { const t = await r.text(); let d = null; try { d = JSON.parse(t); } catch (e) {}
      window.__llama[u] = {status: r.status, data: d, text: t.slice(0, 200)}; })
    .catch(e => { window.__llama[u] = {status: 0, data: null, text: String(e)}; });
  return 'started'; })()"""

def get(url, pick="d => d", timeout=90, tries=3):
    """fetch() url in the page, keep the parsed JSON there and return pick(json). None on 400/404; backs off on 429/5xx; else raises."""
    u = json.dumps(url)
    for attempt in range(tries):
        if js(START_JS % u) == "started":
            t0 = time.time()
            while js("(() => { const x = window.__llama[%s]; return x ? x.status : null; })()" % u) is None:
                if time.time() - t0 > timeout:
                    raise RuntimeError(f"{url}: no response in {timeout}s")
                time.sleep(0.5)
            time.sleep(PAUSE)
        st = js("window.__llama[%s].status" % u)
        if st == 200:
            return js("(%s)(window.__llama[%s].data)" % (pick, u))
        if st in (400, 404):
            return None
        if st not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {st} {js('window.__llama[%s].text' % u)!r}; stopping")
        time.sleep(5 * 2 ** attempt)

YIELDS = "https://yields.llama.fi"   # NOT api.llama.fi: /pools and /chart there answer 404 "Route not found"

on_llama_tab()
total = get(YIELDS + "/pools", "d => [d.status, d.data.length]")
print(f"/pools: {total[0]}, {total[1]} pools")

# Filter the ~11 MB pool list inside the page; outliers are pools DefiLlama itself flags as anomalous APY.
PICK = """d => d.data.filter(p => (%s === null || p.chain === %s) && (%s === null || p.symbol === %s)
                       && (!%s || p.stablecoin) && p.tvlUsd >= %d && !p.outlier)
  .map(p => ({pool: p.pool, project: p.project, chain: p.chain, symbol: p.symbol, meta: p.poolMeta, tvl: p.tvlUsd,
              apy: p.apy, base: p.apyBase, reward: p.apyReward, mean30d: p.apyMean30d, il: p.ilRisk, exposure: p.exposure,
              outlook: p.predictions && p.predictions.predictedClass}))""" % (
    json.dumps(CHAIN), json.dumps(CHAIN), json.dumps(SYMBOL), json.dumps(SYMBOL), json.dumps(STABLE_ONLY), MIN_TVL)
pools = sorted(get(YIELDS + "/pools", PICK), key=lambda p: p["apy"] or 0, reverse=True)
f = lambda x: "  -  " if x is None else f"{x:5.2f}"
print(f"{len(pools)} pools match chain={CHAIN} symbol={SYMBOL} stable={STABLE_ONLY} tvl>=${MIN_TVL:,}; top {TOP} by APY:")
print(f"{'project':<22}{'symbol':<10}{'meta':<16}{'TVL $M':>9}{'apy':>7}{'base':>7}{'reward':>7}{'30d avg':>8}  outlook")
for p in pools[:TOP]:
    print(f"{p['project'][:21]:<22}{p['symbol'][:9]:<10}{(p['meta'] or '')[:15]:<16}{p['tvl']/1e6:>9.1f}{f(p['apy']):>7}{f(p['base']):>7}{f(p['reward']):>7}{f(p['mean30d']):>8}  {p['outlook']}")

# History of the largest matching pool: daily APY and TVL since launch.
if pools:
    big = max(pools, key=lambda p: p["tvl"])
    h = get(f"{YIELDS}/chart/{big['pool']}", "d => d.data.map(x => [x.timestamp.slice(0, 10), x.tvlUsd, x.apy])")
    last30 = [a for _, _, a in h[-30:] if a is not None]
    print(f"\n{big['project']} {big['symbol']} on {big['chain']} [{big['pool']}]: {len(h)} daily points since {h[0][0]}")
    old = h[-min(31, len(h))]
    print(f"30-day APY mean {mean(last30):.2f}% (min {min(last30):.2f}, max {max(last30):.2f}); TVL {old[0]} ${old[1]/1e6:.1f}M -> {h[-1][0]} ${h[-1][1]/1e6:.1f}M")
    print("last 3:", h[-3:])
    print("pool page:", f"https://defillama.com/yields/pool/{big['pool']}")

print("unknown pool id:", get(YIELDS + "/chart/00000000-0000-0000-0000-000000000000", "d => d"))
out = os.path.join(tempfile.gettempdir(), "defillama_pools.json")
json.dump(pools, open(out, "w"), indent=1)
print("saved", out)
```

Output observed on 2026-11-04 UTC:

```text
/pools: success, 15932 pools
17 pools match chain=Base symbol=USDC stable=True tvl>=$1,000,000; top 10 by APY:
project               symbol    meta               TVL $M    apy   base reward 30d avg  outlook
veranta               USDC      vault                 9.7  26.03  26.03    -     22.92  Down
harvest-finance       USDC      40 Acres              1.7  22.54  22.54    -     26.68  Down
zerobase-cedefi       USDC                           10.5   9.00   7.00   2.00    9.00  Stable/Up
autofinance           USDC      baseUSD               3.0   8.94   5.37   3.57    8.88  Down
aave-v3               USDC                           15.8   8.18   5.37   2.81    5.59  Down
midas-rwa             USDC      mGLO                106.2   7.48   7.48    -      6.70  Down
spectra-metavaults    USDC      Gami Spectra US       3.0   7.29   4.01   3.28    4.00  Stable/Up
gami-labs             USDC      Gami Spectra US       3.0   7.29   4.01   3.28    3.99  Stable/Up
centrifuge-protocol   USDC      Janus Henderson      22.8   6.78   6.78    -      4.69  Down
beefy                 USDC      Morpho                1.4   5.79    -      -      5.28  Down

midas-rwa USDC on Base [70267deb-6203-537d-b013-c861e063419c]: 55 daily points since 2026-09-11
30-day APY mean 6.75% (min 6.20, max 7.48); TVL 2026-10-05 $51.5M -> 2026-11-04 $106.2M
last 3: [['2026-11-02', 109336615, 7.48], ['2026-11-03', 106182289, 7.48], ['2026-11-04', 106182289, 7.48]]
pool page: https://defillama.com/yields/pool/70267deb-6203-537d-b013-c861e063419c
unknown pool id: {'status': 'success', 'data': []}
saved <tempdir>/defillama_pools.json
```

The pool page (`/yields/pool/<id>`, robots-allowed) showed the same TVL, $106.18m, and "Supply APY 30d avg 6.69%" against the API's `apyMean30d` 6.70.

### 4. Same API over plain HTTP (no browser)

The API hosts answer plain HTTP with no key. The block sends a truthful User-Agent through `urllib` rather than the harness `http_get()`, which sends `Mozilla/5.0` and, with `BROWSER_USE_API_KEY` set, routes through a proxy service.

```python
import json, time, urllib.error, urllib.request
from datetime import datetime, timezone

UA = "browser-harness-defillama-skill/1.0 Python-urllib"   # truthful client name, no browser UA
PAUSE = 0.5

def api(url):
    """GET a DefiLlama free-API URL. None on 400/404; one 60 s wait on 429, then raise."""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                time.sleep(PAUSE)
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read()[:120].decode(errors="replace")
            if e.code in (400, 404):
                return None
            if e.code == 429 and attempt == 0:
                time.sleep(60)
                continue
            raise RuntimeError(f"HTTP {e.code} {body!r} on {url}; stop, do not retry around it") from e

day = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")

for slug in ["aave", "lido", "no-such-protocol"]:
    print(f"/tvl/{slug}:", api(f"https://api.llama.fi/tvl/{slug}"))          # one number, current TVL in USD

total = api("https://api.llama.fi/v2/historicalChainTvl")                      # all chains, DeFi TVL (no liquid staking, no double counting)
print("DeFi TVL all chains:", [(day(x["date"]), round(x["tvl"] / 1e9, 2)) for x in total[-3:]])

chart = api("https://yields.llama.fi/chart/747c1d2a-c668-4682-b9f9-296708a3dd90")  # Lido stETH pool, the docs' example id
print("Lido stETH:", [(x["timestamp"][:10], round(x["apy"], 3), round(x["tvlUsd"] / 1e9, 2)) for x in chart["data"][-3:]])
```

Output observed on 2026-11-04 UTC:

```text
/tvl/aave: 16296818831.7889
/tvl/lido: 22020132819.716663
/tvl/no-such-protocol: None
DeFi TVL all chains: [('2026-11-02', 82.68), ('2026-11-03', 81.93), ('2026-11-04', 81.81)]
Lido stETH: [('2026-11-02', 2.278, 21.82), ('2026-11-03', 2.3, 22.16), ('2026-11-04', 2.3, 21.9)]
```

```bash
curl -s "https://api.llama.fi/tvl/aave"; echo
curl -s -w " HTTP %{http_code}\n" "https://api.llama.fi/protocol/no-such-protocol"
curl -s -w " HTTP %{http_code}\n" "https://api.llama.fi/pools"
```

Output observed on 2026-11-04 UTC:

```text
16296818831.7889
Protocol not found HTTP 400
Route not found HTTP 404
```

## Fields

| Field | Source | Notes |
|---|---|---|
| `tvl` | `/protocols` row | current USD TVL; excludes borrowed, staking and pool2; `null` for 2,415 of 8,927 rows (listings with no TVL, e.g. `aave-labs`) |
| `chainTvls` | `/protocols` row | `{chain: usd}` with legacy chain names, plus suffixed keys `<Chain>-borrowed`, `-staking`, `-pool2`, `-OwnTokens` and bare `borrowed` / `staking` / `pool2` totals |
| `change_1h`, `change_1d`, `change_7d` | `/protocols` row | percent, can be `null` |
| `slug`, `category`, `parentProtocol` | `/protocols` row | `slug` is the path for `/protocol/<slug>` and `/tvl/<slug>`; children of a parent carry `parentProtocol: "parent#aave"` |
| `name`, `tvl`, `gecko_id`, `chainId` | `/v2/chains` row | display chain name; legacy duplicates (`Binance`, `Optimism`) share the `gecko_id` and have `tvl` 0 |
| `tvl[]` | `/protocol/<slug>` | `[{date, totalLiquidityUSD}]`, unix seconds, daily at 00:00 UTC; the last point is intraday (02:19 UTC here) |
| `chainTvls.<Chain>.tvl[]` | `/protocol/<slug>` | per-chain daily history, same shape; also `tokens` and `tokensInUsd` |
| `currentChainTvls` | `/protocol/<slug>` | current per-chain split with the same suffixed keys as `chainTvls` |
| `otherProtocols`, `isParentProtocol` | `/protocol/<parent>` | parent first, then its children |
| `[{date, tvl}]` | `/v2/historicalChainTvl[/<chain>]` | daily, unix seconds; excludes liquid staking and double counting |
| `pool` | `/pools` row | UUID for `/chart/<pool>` and `defillama.com/yields/pool/<pool>` |
| `apy`, `apyBase`, `apyReward`, `apyMean30d` | `/pools` row | percent; `apy = apyBase + apyReward`, either part can be `null` |
| `tvlUsd`, `chain`, `project`, `symbol`, `poolMeta` | `/pools` row | `project` is the yields slug (`aave-v3`); `poolMeta` names the vault or market (`mGLO`, `Umbrella`) |
| `stablecoin`, `ilRisk`, `exposure`, `outlier` | `/pools` row | `outlier: true` marks pools DefiLlama flags as anomalous; block 3 drops them |
| `predictions.predictedClass` | `/pools` row | `Stable/Up` or `Down`, DefiLlama's own APY outlook |
| `data[]` | `/chart/<pool>` | `[{timestamp, tvlUsd, apy, apyBase, apyReward, il7d, apyBase7d}]`, `timestamp` is an ISO string, not unix |

## Gotchas

- **Do not sum `/protocols` for a total.** Non-CEX `tvl` summed to $265B because bridges, liquid staking and restaking hold tokens that are deposited again elsewhere. The homepage said "Total Value Locked in DeFi $82.317b" and `/v2/historicalChainTvl` said $81.81B. Use the chain endpoints for totals.
- **CEX rows are in `/protocols`.** 84 rows with category `CEX` ($248B), and `Binance CEX` is the first row. Block 1 drops them.
- **Error shapes differ.** Unknown slug on `/protocol/` and `/tvl/`: HTTP 400, body `Protocol not found` (text, not JSON). Unknown chain on `/v2/historicalChainTvl/`: HTTP 404 nginx HTML page. Unknown pool on `/chart/`: HTTP 200 `{"status":"success","data":[]}`.
- **`/v2/historicalChainTvl/<chain>` is forgiving:** `BSC` and `Binance`, `OP%20Mainnet` and `Optimism`, `Gnosis` and `xDai`, `ethereum` and `Ethereum` returned the same series. `/protocols` `chainTvls` is not: `chainTvls["BSC"]` matched 0 protocols, `chainTvls["Binance"]` matched 1,040.
- **Parent and child use different chain names.** `/protocol/aave` (parent) lists `OP Mainnet`, `BSC`, `Gnosis`; `/protocol/aave-v3` lists `Optimism`, `Binance`, `xDai` for the same markets.
- **Per-chain split needs the suffixes stripped.** Summing `currentChainTvls` keys without a `-` and without `borrowed` / `staking` / `pool2` equals `tvl` exactly (Aave V3: $15.226B both). Lending protocols report `borrowed` separately (Aave V3 $11.25B), not in TVL.
- **Numbers lag a little and disagree slightly.** `/protocols` and `/v2/chains` send `cache-control: public, max-age=1798`. In the same minute `/tvl/lido` said $22.02B and `/protocols` said $21.93B; the Aave V3 page showed $15.381b against $15.226B from the API, and the Ethereum chain page $44.099b against $43.76B from `/v2/chains`. Take all numbers in one comparison from one endpoint.
- **Pool `symbol` is the deposit asset, not the vault.** The midas-rwa pool above has `symbol: "USDC"`, `poolMeta: "mGLO"`, and its page title says "mGLO APY on Midas RWA (Base)". `symbol` filters are exact matches; multi-asset pools look like `USDC-WETH`.
- **High APY rows can be real or not.** `outlier: false` still let through a 26% USDC vault; compare `apy` with `apyMean30d` and `apyReward` before trusting it.
- **Rate limits are not published for the free tier.** llms.txt says only "Standard"; the paid plan ($300/mo) gives higher limits. None was hit at 0.5 s serial pacing; on a 429 back off, do not parallelize around it.
- **Fetch from a defillama.com tab.** Cross-origin `fetch()` from that tab worked for both api.llama.fi and yields.llama.fi; it is the origin the site itself uses.

## What does not work

- **Plain HTTP to defillama.com pages:** `curl https://defillama.com/`, `/protocol/aave-v3` and `/yields` got HTTP 403 (robots.txt itself returned 200). Not worked around; the cloud browser loaded the same pages normally, and the API hosts do not do this.
- **`https://api.llama.fi/pools` and `https://api.llama.fi/chart/<pool>`:** HTTP 404 `Route not found`, even though llms-free.txt documents them on that host. Use `yields.llama.fi`.
- **Endpoints marked "API Plan" in the docs** (`/api/inflows/...`, `/api/chainAssets`, `/api/v2/chart/tvl/protocol/.../chain-breakdown`, MCP server) need the paid key. Not used.
