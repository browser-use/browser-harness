# Kalshi - Market Prices, Order Books and Event Lists (official Trade API)

Field-tested against kalshi.com and api.elections.kalshi.com on 2026-11-02 using a Browser Use cloud browser, logged out. Every browser call is a `fetch()` from a kalshi.com tab to Kalshi's public Trade API. No CAPTCHA, 403 or 429 across about 110 browser API calls.

robots.txt (kalshi.com, fetched 2026-11-02 in the browser): `User-agent: *` disallows only `/ideas` (except `/ideas/profiles/` and `/ideas/posts/`), `/sign-up?` and `/search`, so `/robots.txt` and `/markets/...` are allowed; api.elections.kalshi.com has no robots.txt (HTTP 404) and this skill uses its `/trade-api/v2` market-data endpoints under the official-API exception, because Kalshi's docs ("Quick Start: Market Data", https://docs.kalshi.com/getting_started/quick_start_market_data) say these endpoints need no API key, and https://kalshi.com/AGENTS.md names `https://api.elections.kalshi.com` as the production API host.

## Quick summary

- **No scraping.** Five public JSON endpoints cover the task. No key, no cookies:
  - `GET /trade-api/v2/series?category=<C>&include_volume=true` - every series (recurring market family) in a category, with all-time `volume_fp`.
  - `GET /trade-api/v2/events?series_ticker=<S>&status=open&with_nested_markets=true&limit=200&cursor=<c>` - event list, each with its markets.
  - `GET /trade-api/v2/events/<EVENT>` - one event plus its markets (top-level `markets`): bid, ask, last, volume, open interest, status, result.
  - `GET /trade-api/v2/markets/<TICKER>/orderbook?depth=<n>` - bids only, both sides, as `[price_dollars, contracts]` string pairs.
  - `GET /trade-api/v2/markets/trades?ticker=<TICKER>&limit=<n>` - recent fills.
- **Base host:** `https://api.elections.kalshi.com/trade-api/v2/` (Kalshi's AGENTS.md calls it production; the docs list `https://external-api.kalshi.com/trade-api/v2` first and this one as "also supported"; both returned the same events today). It serves all markets, not only elections.
- **Run `fetch()` from a kalshi.com tab.** The API's CORS answers `access-control-allow-origin: https://kalshi.com`. The blocks open `https://kalshi.com/robots.txt` (small, robots-allowed) once and reuse it.
- **Prices are dollar strings** (`"0.7300"` = 73c = 73% implied), sizes are fixed-point strings (`"2036.30"` contracts). The blocks convert them.
- **Do not walk all open events.** On 2026-11-02, 40 pages x 200 open events (8,000 events, 34,263 nested markets, 87 MB) still returned a next cursor. Narrow by `series_ticker`, found via `/series?category=`.

## What works

All browser blocks share the same helpers: `on_kalshi_tab()` opens `https://kalshi.com/robots.txt` once and later blocks reuse that tab; it raises if Vercel's "Security Checkpoint" page appears instead. `get(path, params)` fetches `https://api.elections.kalshi.com/trade-api/v2/<path>`, returns parsed JSON (`None` on 404), backs off on 429/5xx and otherwise raises, so a failed call never looks like an empty result. Calls are serial with a 0.25 s pause.

### 1. Event list for a category (browser)

Busiest series in a category, then every open event in them, sorted by close time.

```python
import json, os, tempfile, time, urllib.parse

CATEGORY = "Economics"   # a series category: Politics, Sports, Crypto, Financials, Climate and Weather, ...
TOP_SERIES = 3           # busiest series in the category (by all-time volume)
SHOW = 12                # event rows to print

API = "https://api.elections.kalshi.com/trade-api/v2/"
PAUSE = 0.25             # seconds between calls; keep calls serial

def on_kalshi_tab():
    """fetch() runs in a logged-out kalshi.com tab: the API's CORS allows that origin. Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://kalshi.com":
            return
    except Exception:
        pass
    new_tab("https://kalshi.com/robots.txt")   # small robots-allowed page on kalshi.com
    wait_for_load()
    if "Checkpoint" in (js("document.title") or ""):
        raise RuntimeError("Vercel Security Checkpoint on kalshi.com: stop and tell the user; do not retry around it")

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'}); return {status: r.status, text: await r.text()}; }
  catch (e) { return {status: 0, text: String(e)}; }
})()"""

def get(path, params=None, tries=4):
    """GET api.elections.kalshi.com/trade-api/v2/<path>. Returns parsed JSON, None on 404. Backs off on 429/5xx, else raises."""
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        if r["status"] in (200, 404):
            time.sleep(PAUSE)
            return json.loads(r["text"]) if r["status"] == 200 else None
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['text'][:200]}; stopping")
        time.sleep(2 * 2 ** attempt)   # 429 carries no Retry-After header

def cents(d):
    return None if d in (None, "") else round(float(d) * 100, 2)

on_kalshi_tab()
series = get("series", {"category": CATEGORY, "include_volume": "true"})["series"]
series.sort(key=lambda s: float(s.get("volume_fp") or 0), reverse=True)
print(f"{len(series)} series in {CATEGORY!r}; busiest:", [(s["ticker"], s["title"]) for s in series[:TOP_SERIES]])

rows = []
for s in series[:TOP_SERIES]:
    cursor = ""
    while True:
        p = {"series_ticker": s["ticker"], "status": "open", "with_nested_markets": "true", "limit": 200}
        if cursor:
            p["cursor"] = cursor
        page = get("events", p)
        for e in page["events"]:
            ms = e.get("markets") or []
            lead = max(ms, key=lambda m: float(m["last_price_dollars"] or 0), default=None)
            rows.append({
                "event_ticker": e["event_ticker"],
                "series_ticker": e["series_ticker"],
                "title": e["title"],
                "sub_title": e.get("sub_title"),
                "category": e.get("category"),
                "mutually_exclusive": e.get("mutually_exclusive"),
                "markets": len(ms),
                "closes": min((m["close_time"] for m in ms), default=None),
                "lead_outcome": lead and lead.get("yes_sub_title"),
                "lead_last_cents": lead and cents(lead["last_price_dollars"]),
                "volume_24h": round(sum(float(m.get("volume_24h_fp") or 0) for m in ms), 2),
                "url": f"https://kalshi.com/markets/{e['series_ticker'].lower()}/{e['event_ticker'].lower()}",
            })
        cursor = page.get("cursor") or ""
        if not cursor:
            break

rows.sort(key=lambda r: r["closes"] or "")
print(f"{len(rows)} open events across {TOP_SERIES} series")
for r in rows[:SHOW]:
    print(f"{(r['closes'] or '-')[:10]}  {r['event_ticker']:<24} {r['markets']:>2} mkts  {'top' if r['mutually_exclusive'] else 'ladder'}: {r['lead_outcome']} {r['lead_last_cents']}c  24h vol {r['volume_24h']:,.0f}  | {r['title']}")
out = os.path.join(tempfile.gettempdir(), "kalshi_events.json")
json.dump(rows, open(out, "w"), indent=1)
print("saved", out)
```

Output observed on 2026-11-02:

```text
873 series in 'Economics'; busiest: [('KXFEDDECISION', 'Fed meeting'), ('KXAAAGASM', 'US gas price'), ('KXFED', 'Fed funds rate')]
21 open events across 3 series
2026-11-30  KXAAAGASM-26NOV30        26 mkts  ladder: Above 3.50 97.0c  24h vol 71,516  | Gas prices in the US in Nov 2026?
2026-12-09  KXFED-26DEC              11 mkts  ladder: Above 3.00% 99.0c  24h vol 8,846  | Fed funds rate after Dec 2026 meeting?
2026-12-09  KXFEDDECISION-26DEC       5 mkts  top: Hike 25bps 73.0c  24h vol 93,706  | Fed decision in Dec 2026?
2027-01-27  KXFED-27JAN              25 mkts  ladder: Above 0.00% 99.0c  24h vol 11  | Fed funds rate after Jan 2027 meeting?
2027-01-27  KXFEDDECISION-27JAN       5 mkts  top: Fed maintains rate 71.0c  24h vol 197  | Fed decision in Jan 2027?
2027-03-17  KXFED-27MAR              25 mkts  ladder: Above 0.50% 99.0c  24h vol 0  | Fed funds rate after Mar 2027 meeting?
2027-03-17  KXFEDDECISION-27MAR       5 mkts  top: Hike 25bps 47.0c  24h vol 97  | Fed decision in Mar 2027?
2027-04-28  KXFED-27APR              25 mkts  ladder: Above 0.25% 99.0c  24h vol 5  | Fed funds rate after Apr 2027 meeting?
2027-04-28  KXFEDDECISION-27APR       5 mkts  top: Fed maintains rate 58.0c  24h vol 20  | Fed decision in Apr 2027?
2027-06-09  KXFED-27JUN              25 mkts  ladder: Above 0.50% 99.0c  24h vol 0  | Fed funds rate after Jun 2027 meeting?
2027-06-09  KXFEDDECISION-27JUN       5 mkts  top: Fed maintains rate 61.0c  24h vol 1  | Fed decision in Jun 2027?
2027-07-28  KXFED-27JUL              25 mkts  ladder: Above 0.00% 99.0c  24h vol 0  | Fed funds rate after Jul 2027 meeting?
saved <tempdir>/kalshi_events.json
```

### 2. Market prices for an event from a kalshi.com URL (browser)

Takes a series URL (`/markets/<series>`) or an event URL (`/markets/<series>/<slug>/<event>`), resolves it to an event ticker without loading the page, and prints every outcome's bid, ask, last price, 24 h volume and open interest.

```python
import json, time, urllib.parse

URLS = [
    "https://kalshi.com/markets/kxfeddecision",                                        # series page: soonest-closing open event
    "https://kalshi.com/markets/kxhighny/highest-temperature-in-nyc/kxhighny-26nov01", # event page, settled
    "https://kalshi.com/markets/kxhighny/kxhighny-25jan01",                            # settled before the historical cutoff
    "https://kalshi.com/markets/kxnosuchseries",
]

API = "https://api.elections.kalshi.com/trade-api/v2/"
PAUSE = 0.25

def on_kalshi_tab():
    """fetch() runs in a logged-out kalshi.com tab: the API's CORS allows that origin. Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://kalshi.com":
            return
    except Exception:
        pass
    new_tab("https://kalshi.com/robots.txt")
    wait_for_load()
    if "Checkpoint" in (js("document.title") or ""):
        raise RuntimeError("Vercel Security Checkpoint on kalshi.com: stop and tell the user; do not retry around it")

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'}); return {status: r.status, text: await r.text()}; }
  catch (e) { return {status: 0, text: String(e)}; }
})()"""

def get(path, params=None, tries=4):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        if r["status"] in (200, 404):
            time.sleep(PAUSE)
            return json.loads(r["text"]) if r["status"] == 200 else None
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['text'][:200]}; stopping")
        time.sleep(2 * 2 ** attempt)

def cents(d):
    return None if d in (None, "") else round(float(d) * 100, 2)

def event_ticker_from_url(url):
    """kalshi.com/markets/<series>[/<slug>]/<event> -> event ticker; a bare series URL -> its soonest-closing open event."""
    parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
    if len(parts) < 2 or parts[0] != "markets":
        raise ValueError(f"not a kalshi.com/markets/... URL: {url}")
    series = parts[1].upper()
    if len(parts) > 2 and parts[-1].upper().startswith(series + "-"):
        return parts[-1].upper()
    page = get("events", {"series_ticker": series, "status": "open", "with_nested_markets": "true", "limit": 200})
    evs = [e for e in (page or {}).get("events", []) if e.get("markets")]
    if not evs:
        return None
    return min(evs, key=lambda e: min(m["close_time"] for m in e["markets"]))["event_ticker"]

def event_prices(event_ticker):
    d = get(f"events/{event_ticker}")   # without with_nested_markets the markets come back top-level
    if d is None:
        return None
    ev = d["event"]
    return {
        "event_ticker": ev["event_ticker"], "title": ev["title"], "sub_title": ev.get("sub_title"),
        "category": ev.get("category"), "mutually_exclusive": ev.get("mutually_exclusive"),
        "settlement_sources": [s.get("name") for s in ev.get("settlement_sources") or []],
        "url": f"https://kalshi.com/markets/{ev['series_ticker'].lower()}/{ev['event_ticker'].lower()}",
        "markets": [{
            "ticker": m["ticker"], "outcome": m.get("yes_sub_title"), "status": m["status"], "result": m.get("result"),
            "yes_bid": cents(m["yes_bid_dollars"]), "yes_ask": cents(m["yes_ask_dollars"]),
            "no_bid": cents(m["no_bid_dollars"]), "no_ask": cents(m["no_ask_dollars"]),
            "last": cents(m["last_price_dollars"]), "prev_day": cents(m.get("previous_price_dollars")),
            "volume": float(m.get("volume_fp") or 0), "volume_24h": float(m.get("volume_24h_fp") or 0),
            "open_interest": float(m.get("open_interest_fp") or 0), "close_time": m["close_time"],
        } for m in d["markets"]],
    }

on_kalshi_tab()
for url in URLS:
    t = event_ticker_from_url(url)
    ev = event_prices(t) if t else None
    if ev is None:
        print(f"\n{url}: no open event found")
        continue
    print(f"\n{ev['title']} [{ev['event_ticker']}] {ev['category']} | mutually exclusive: {ev['mutually_exclusive']} | settles on {ev['settlement_sources']}")
    if not ev["markets"]:
        print("no markets: settled before the historical cutoff; use /historical/markets")
        continue
    print(f"{'outcome':<22}{'status':<11}{'bid':>6}{'ask':>6}{'last':>6}{'vol 24h':>10}{'OI':>10}")
    for m in ev["markets"]:
        print(f"{(m['outcome'] or '')[:21]:<22}{m['status']:<11}{m['yes_bid']:>6}{m['yes_ask']:>6}{m['last']:>6}{m['volume_24h']:>10,.0f}{m['open_interest']:>10,.0f}  {m['result']}")
    if ev["mutually_exclusive"] and all(m["status"] == "active" for m in ev["markets"]):
        print("sum of yes asks:", round(sum(m["yes_ask"] for m in ev["markets"]), 2), "c")
```

Output observed on 2026-11-02:

```text

Fed decision in Dec 2026? [KXFEDDECISION-26DEC] Economics | mutually exclusive: True | settles on ['Federal Reserve']
outcome               status        bid   ask  last   vol 24h        OI
Cut >25bps            active        0.0   1.0   1.0     4,676   163,091  
Cut 25bps             active        1.0   2.0   2.0     3,796   380,989  
Fed maintains rate    active       26.0  27.0  26.0    29,484   488,275  
Hike 25bps            active       72.0  73.0  73.0    50,546   378,368  
Hike >25bps           active        1.0   2.0   2.0     5,204   437,967  
sum of yes asks: 105.0 c

Highest temperature in New York City on Nov 1, 2026? [KXHIGHNY-26NOV01] Climate and Weather | mutually exclusive: True | settles on ['The Weather Company']
outcome               status        bid   ask  last   vol 24h        OI
59° or below          finalized     0.0 100.0  99.0    14,050    20,789  yes
60° to 61°            finalized     0.0 100.0   1.0    26,159    31,366  no
62° to 63°            finalized     0.0 100.0   1.0     3,916    13,708  no
64° to 65°            finalized     0.0 100.0   1.0    39,228    45,730  no
66° to 67°            finalized     0.0 100.0   1.0       486     3,431  no
68° or above          finalized     0.0 100.0   1.0        50       481  no

Highest temperature in NYC on Jan 1, 2025? [KXHIGHNY-25JAN01] Climate and Weather | mutually exclusive: True | settles on ['National Weather Service']
no markets: settled before the historical cutoff; use /historical/markets

https://kalshi.com/markets/kxnosuchseries: no open event found
```

### 3. Order book, implied asks, spread and recent trades (browser)

```python
import json, os, tempfile, time, urllib.parse

SERIES = "KXFEDDECISION"   # order book of the busiest (24h volume) market in this series' soonest-closing open event
TICKER = None              # or a market ticker, e.g. "KXFEDDECISION-26DEC-H25"
DEPTH = 10                 # price levels per side; 0 = all

API = "https://api.elections.kalshi.com/trade-api/v2/"
PAUSE = 0.25

def on_kalshi_tab():
    """fetch() runs in a logged-out kalshi.com tab: the API's CORS allows that origin. Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://kalshi.com":
            return
    except Exception:
        pass
    new_tab("https://kalshi.com/robots.txt")
    wait_for_load()
    if "Checkpoint" in (js("document.title") or ""):
        raise RuntimeError("Vercel Security Checkpoint on kalshi.com: stop and tell the user; do not retry around it")

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'}); return {status: r.status, text: await r.text()}; }
  catch (e) { return {status: 0, text: String(e)}; }
})()"""

def get(path, params=None, tries=4):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        if r["status"] in (200, 404):
            time.sleep(PAUSE)
            return json.loads(r["text"]) if r["status"] == 200 else None
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['text'][:200]}; stopping")
        time.sleep(2 * 2 ** attempt)

def busiest_market(series):
    page = get("events", {"series_ticker": series, "status": "open", "with_nested_markets": "true", "limit": 200})
    evs = [e for e in (page or {}).get("events", []) if e.get("markets")]
    if not evs:
        raise ValueError(f"no open event in series {series}")
    ev = min(evs, key=lambda e: min(m["close_time"] for m in e["markets"]))
    return max(ev["markets"], key=lambda m: float(m.get("volume_24h_fp") or 0))["ticker"]

def order_book(ticker, depth=10):
    """Market snapshot + order book. Kalshi returns bids only: a NO bid at p is a YES ask at 1 - p."""
    m = get(f"markets/{ticker}")
    if m is None:
        return None   # check first: /orderbook answers 200 with empty sides for unknown tickers
    m = m["market"]
    ob = get(f"markets/{ticker}/orderbook", {"depth": depth})["orderbook_fp"]
    lv = lambda side: [(float(p), float(q)) for p, q in reversed(ob.get(side) or [])]   # best first
    yes_bids, no_bids = lv("yes_dollars"), lv("no_dollars")
    best_yes_bid = yes_bids[0][0] if yes_bids else None
    best_yes_ask = round(1 - no_bids[0][0], 4) if no_bids else None
    trades = get("markets/trades", {"ticker": ticker, "limit": 5})["trades"]
    return {
        "ticker": ticker, "title": m["title"], "outcome": m.get("yes_sub_title"), "status": m["status"],
        "best_yes_bid": best_yes_bid, "best_yes_ask": best_yes_ask,
        "spread": round(best_yes_ask - best_yes_bid, 4) if best_yes_bid is not None and best_yes_ask is not None else None,
        "snapshot_yes_bid": float(m["yes_bid_dollars"]), "snapshot_yes_ask": float(m["yes_ask_dollars"]),
        "last": float(m["last_price_dollars"]),
        "yes_bids": yes_bids,                                         # (price, contracts), best first
        "yes_asks": [(round(1 - p, 4), q) for p, q in no_bids],       # implied from NO bids, best first
        "recent_trades": [(t["created_time"][:19], t["taker_side"], float(t["yes_price_dollars"]), float(t["count_fp"])) for t in trades],
    }

on_kalshi_tab()
for t in [TICKER or busiest_market(SERIES), "KXNOSUCH-26JAN01-X"]:
    b = order_book(t, DEPTH)
    if b is None:
        print(f"\n{t}: no such market")
        continue
    print(f"\n{b['title']} [{b['ticker']}] {b['status']}")
    print(f"book: bid {b['best_yes_bid']}  ask {b['best_yes_ask']}  spread {b['spread']} | snapshot: bid {b['snapshot_yes_bid']} ask {b['snapshot_yes_ask']} last {b['last']}")
    print(f"{'yes bid':>8}{'size':>10}   {'yes ask':>8}{'size':>10}")
    for i in range(min(DEPTH or 10, max(len(b['yes_bids']), len(b['yes_asks'])))):
        bp, bq = b["yes_bids"][i] if i < len(b["yes_bids"]) else ("", "")
        ap, aq = b["yes_asks"][i] if i < len(b["yes_asks"]) else ("", "")
        print(f"{bp:>8}{bq:>10}   {ap:>8}{aq:>10}")
    print("recent trades (time, taker side, yes price, contracts):", b["recent_trades"])
    out = os.path.join(tempfile.gettempdir(), f"kalshi_book_{b['ticker']}.json")
    json.dump(b, open(out, "w"), indent=1)
    print("saved", out)
```

Output observed on 2026-11-02:

```text

Will the Federal Reserve Hike rates by 25bps at their December 2026 meeting? [KXFEDDECISION-26DEC-H25] active
book: bid 0.72  ask 0.73  spread 0.01 | snapshot: bid 0.72 ask 0.73 last 0.73
 yes bid      size    yes ask      size
    0.72    2024.3       0.73    5802.1
    0.71    233.67       0.74  51103.51
     0.7  50859.93       0.75     656.0
    0.69    639.99       0.76    110.89
    0.68   4749.81       0.77    261.95
    0.67     395.0       0.78   4299.22
    0.66   1403.91       0.79    968.54
    0.65   1372.17        0.8  12605.07
    0.64     701.0       0.81     56.38
    0.63     800.0       0.83    741.47
recent trades (time, taker side, yes price, contracts): [('2026-11-02T19:30:57', 'yes', 0.73, 6.98), ('2026-11-02T19:19:15', 'yes', 0.73, 67.22), ('2026-11-02T19:06:11', 'yes', 0.73, 13.43), ('2026-11-02T18:59:03', 'yes', 0.73, 3.27), ('2026-11-02T18:58:59', 'yes', 0.73, 19.34)]
saved <tempdir>/kalshi_book_KXFEDDECISION-26DEC-H25.json

KXNOSUCH-26JAN01-X: no such market
```

### 4. Same endpoints over plain HTTP (no browser)

The API also answers plain `curl` with no key, which is what Kalshi's own quick start does. `/historical/markets` (no key either) returns markets that settled before the historical cutoff. The order book ticker below closes 2026-12-09; after that, take a current one from block 1 or 3.

```bash
curl -s "https://api.elections.kalshi.com/trade-api/v2/markets/KXFEDDECISION-26DEC-H25/orderbook?depth=3"; echo
curl -s "https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=KXHIGHNY-25JAN01" \
  | python3 -c 'import json, sys; [print(m["ticker"], m["result"], m["last_price_dollars"]) for m in json.load(sys.stdin)["markets"]]'
```

Output observed on 2026-11-02:

```text
{"orderbook_fp":{"no_dollars":[["0.2500","656.00"],["0.2600","51103.51"],["0.2700","5802.10"]],"yes_dollars":[["0.7000","50859.93"],["0.7100","233.67"],["0.7200","2024.30"]]}}
KXHIGHNY-25JAN01-T54 no 0.0100
KXHIGHNY-25JAN01-T47 no 0.0100
KXHIGHNY-25JAN01-B53.5 no 0.0100
KXHIGHNY-25JAN01-B51.5 yes 0.9900
KXHIGHNY-25JAN01-B49.5 no 0.0100
KXHIGHNY-25JAN01-B47.5 no 0.0100
```

## Fields

| Field | Source | Notes |
|---|---|---|
| `yes_bid_dollars`, `yes_ask_dollars` | market object | best YES bid and ask, dollar strings; `no_bid = 1 - yes_ask`, `no_ask = 1 - yes_bid` |
| `last_price_dollars` | market object | last trade; `previous_price_dollars` is the price 24 h earlier |
| `volume_fp`, `volume_24h_fp`, `open_interest_fp` | market object | contracts, fixed-point strings |
| `status` | market object | `active` while trading, `finalized` after settlement (the `/events` and `/markets` filter values are different, see Gotchas) |
| `result` | market object | `"yes"` / `"no"` once settled, `""` before |
| `yes_sub_title` | market object | outcome label as shown on the page (`"Hike 25bps"`, `"65° to 66°"`) |
| `close_time` | market object | ISO UTC; events have no close time of their own, the blocks take the earliest market's |
| `mutually_exclusive` | event object | `true` when exactly one outcome can win; `false` for threshold ladders (`"Above 3.00%"`), where many outcomes trade near 99c at once |
| `orderbook_fp.yes_dollars`, `.no_dollars` | `/orderbook` | `[price, contracts]` bids, ascending: best bid is the LAST element |
| `taker_side`, `yes_price_dollars`, `count_fp` | `/markets/trades` | newest first |
| `volume_fp` | `/series?include_volume=true` | all-time contracts for the series |

## Gotchas

- **Bids only in the order book.** A NO bid at p is a YES ask at 1 - p (Kalshi's "Orderbook Responses" doc). Today the computed best ask matched the market snapshot's `yes_ask_dollars` (0.73 / 0.73) and best bid matched `yes_bid_dollars` (0.72 / 0.72).
- **Unknown ticker on `/orderbook` is HTTP 200** with empty `yes_dollars` / `no_dollars`, not 404. Block 3 checks `/markets/<ticker>` first (that one returns 404 `{"error":{"code":"not_found",...}}`).
- **Status filter values differ from status field values.** Filter with `status=open` (`unopened`, `open`, `closed`, `settled`); market objects say `active` / `finalized`. `status=active`, which kalshi.com/AGENTS.md shows in its `/markets` curl example, returns HTTP 400 (`invalid status filter` on `/markets`, a bare `bad request` on `/events`).
- **`limit` max is 200.** `limit=500` returns HTTP 400 `bad request`.
- **`with_nested_markets=true` moves markets inside `event`.** On `/events/<EVENT>`, nested puts them in `event.markets` and leaves top-level `markets` empty; without it they are top-level (block 2 relies on that).
- **Settled markets show bid 0 / ask 1.00** (empty book). Read `result` instead of prices.
- **Historical cutoff.** Markets settled before the cutoff (`/historical/cutoff` said `market_settled_ts` 2026-09-03) vanish from `/events/<EVENT>`: KXHIGHNY-25JAN01 returned the event with `markets: []`. Fetch them from `/historical/markets?event_ticker=` (block 4). KXHIGHNY-24JAN01, the ticker in Kalshi's own orderbook doc example, is a 404.
- **Sum of YES asks exceeds 100c** in mutually exclusive events (on 2026-11-02: 105c for the Fed decision, 103c to 105c during the day for NYC high temperature on Nov 2): asks carry the spread. Use last or mid for an implied probability.
- **Page vs API.** On the event page, "Yes NNc" is the YES ask, "No NNc" the NO ask, and the big percent matched `last_price_dollars` in the row checked (65° to 66°: 92% / Yes 92c / No 10c vs API last 0.92, yes_ask 0.92, no_ask 0.10). Another row lagged the API by 2c, and in a background tab the page stopped updating. Use the API for numbers.
- **URLs.** `https://kalshi.com/markets/<series>/<event>` (lowercase) redirects to the canonical `/markets/<series>/<slug>/<event>`, and `/markets/<series>` redirects to its current event, so a URL can be built from tickers alone.
- **Rate limits.** Kalshi documents token buckets for authenticated keys only; a 429 has body `{"error": "too many requests"}` and no `Retry-After`. The blocks stay serial and back off; none was hit today.
- **Multivariate "combo" markets** (`KXMVE...` tickers) came first in an unfiltered `/markets?status=open`. `/events` excludes them; filter `/markets` by `series_ticker` or `event_ticker`.

## What does not work

- **Same-origin `fetch()` from an api.elections.kalshi.com tab:** `TypeError: Failed to fetch` on every path today, although navigating to the same URL showed the JSON. Fetch from a kalshi.com tab instead.
- **Other origins:** a request with `Origin: https://example.com` got HTTP 403, so `fetch()` from a non-Kalshi page fails.
- **Plain HTTP to kalshi.com pages:** `curl https://kalshi.com/robots.txt` got HTTP 429 with a "Vercel Security Checkpoint" page. Not worked around; the browser loaded the same URL normally. The API host does not do this.
- **Live streams without a key:** Kalshi's WebSocket feed needs an API key even for public channels (docs, "WebSocket Connection"). Not used.
- **`/search`, `/ideas` and `/sign-up?` pages:** disallowed by robots.txt. Not used; find markets with `/series?category=` and `/events?series_ticker=` instead.
