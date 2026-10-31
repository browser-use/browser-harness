# Finviz - Stock fundamentals and preset screeners

Field-tested against finviz.com on 2026-10-31 using a Browser Use cloud browser, logged out (plus plain HTTP for robots.txt).

robots.txt (fetched 2026-10-31) has no rule matching `/stock?t=<T>`, so stock pages are allowed; it disallows `/screener?*`, `/screener/stocks?*`, `/export` and `/api/v1/screener-export-csv` (custom screeners and CSV export) but explicitly allows 35 preset screeners such as `/screener/stocks?v=340&s=ta_topgainers`, and the site's pager only appends `&r=<n>`, which still matches the longer Allow rule.

## Quick summary

- **Stock page** `https://finviz.com/stock?t=<T>` is server-rendered: 6 `table.js-snapshot-table` tables hold 84 label/value cells (valuation, growth, ownership, margins, technicals, performance), plus a header with company, sector, industry, country, exchange, website and last price. A `<script id="income-breakdown-init-data-0">` JSON block adds a 2-year annual income statement summary.
- The old `/quote.ashx?t=AAPL` 301s to `/quote?t=AAPL`, which 301s to `/stock?t=AAPL`; the browser lands on `/stock?t=AAPL&p=d`.
- **Preset screeners**: each page embeds its rows in a `<script type="application/json">` block (`"screenerType"` key). Views `v=340` (snapshot) and `v=320` (news) carry 10 rows per page with price, change %, volume, avg volume, market cap. View `v=210` (charts) carries 12 tickers per page with company, industry, country and market cap only.
- Only the 35 presets robots.txt names are usable, each with its fixed view. Changing `v`, adding filters `f=` or sort `o=` turns it into a disallowed custom screener.
- Plain Python `urllib` gets HTTP 403 (Cloudflare error 1010) on stock and screener pages. Use the browser.
- Pages are ad-heavy. Close the task tab when done: leftover Finviz tabs stalled the cloud browser twice in testing.

## What works

### 1. Stock fundamentals table (browser)

Self-contained. Opens one tab, reads 3 tickers about 3 s apart, closes the tab, saves JSON. Returns `None` for a ticker Finviz does not know (it redirects to `/search`, which robots.txt disallows, so the page is not read). Raises on a Cloudflare challenge or a short table.

```python
import json, os, re, tempfile, time, urllib.parse

def js_retry(expr, tries=6):
    # Finviz pages are ad-heavy; CDP calls sometimes miss the 5 s daemon timeout while the page is busy.
    for _ in range(tries):
        try:
            return js(expr)
        except TimeoutError:
            pass
        except RuntimeError as e:
            if "timed out" not in str(e):
                raise
        time.sleep(2)
    raise RuntimeError(f"page stayed busy for {tries} tries: {expr[:60]}")

def fv_open(url, timeout=45, settle=2.5):
    """Open url; return the landed URL. Raises on a Cloudflare challenge or if the page never loads."""
    prev = js_retry("location.href")
    try:
        goto_url(url)
    except TimeoutError:
        pass  # Page.navigate can exceed 5 s while the previous page unloads; the navigation still runs
    end = time.time() + timeout
    while True:
        if time.time() > end:
            raise RuntimeError(f"{url} did not finish loading in {timeout}s")
        time.sleep(1)
        href, state = js_retry("[location.href, document.readyState]")
        if state == "complete" and (href != prev or prev == url):
            break
    time.sleep(settle)
    title = js_retry("document.title") or ""
    challenge = js_retry("!!document.querySelector('#challenge-form, iframe[src*=\"challenges.cloudflare.com\"]')")
    if "Just a moment" in title or challenge:
        raise RuntimeError(f"Cloudflare challenge on {url}: stop and tell the user; do not retry around it")
    return js_retry("location.href")

SNAPSHOT_JS = """(() => {
  const rows = [];
  for (const t of document.querySelectorAll('table.js-snapshot-table'))
    for (const tr of t.rows) {
      const c = [...tr.cells];
      for (let i = 0; i + 1 < c.length; i += 2)
        rows.push([c[i].innerText.trim(), c[i + 1].innerText.trim(), c[i].getAttribute('data-boxover-html') || '']);
    }
  const txt = s => { const e = document.querySelector(s); return e ? e.innerText.trim() : null; };
  const link = p => { const a = document.querySelector(`a[href*="f=${p}_"]`); return a ? a.innerText.trim() : null; };
  const site = [...document.querySelectorAll('.quote-header a[href^="http"]')].map(a => a.href)[0] || null;
  const inc = document.getElementById('income-breakdown-init-data-0');
  return {rows, company: txt('.quote-header h2'), price: txt('.quote-price_price'), price_date: txt('.quote-price_date'),
          sector: link('sec'), industry: link('ind'), country: link('geo'), exchange: link('exch'), website: site,
          income: inc ? JSON.parse(inc.textContent).statement : null};
})()"""

def finviz_stock(ticker):
    """Snapshot fundamentals for one ticker from /stock?t=<T>. None if Finviz does not know the ticker."""
    t = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.\-]{1,10}", t):
        raise ValueError(f"bad ticker {ticker!r}")
    url = "https://finviz.com/stock?" + urllib.parse.urlencode({"t": t})
    landed = urllib.parse.urlparse(fv_open(url))
    if landed.path != "/stock":
        return None  # unknown tickers redirect to /search?p=..., which robots.txt disallows: not read
    if urllib.parse.parse_qs(landed.query).get("t", [""])[0].upper() != t:
        raise RuntimeError(f"asked for {t}, landed on {landed.geturl()}")
    d = js_retry(SNAPSHOT_JS)
    if len(d["rows"]) < 80:
        raise RuntimeError(f"{t}: only {len(d['rows'])} snapshot cells; layout changed?")
    snap = {}
    for label, value, tip in d["rows"]:
        key = label if label not in snap else (tip or label + " #2")  # 'EPS next Y' appears twice
        snap[key] = value
    return {"ticker": t, "company": d["company"], "url": landed.geturl(), "sector": d["sector"], "industry": d["industry"],
            "country": d["country"], "exchange": d["exchange"], "website": d["website"],
            "last_price": d["price"], "price_time": d["price_date"],
            "snapshot": snap, "income_statement": d["income"]}  # last 2 fiscal years, millions of income["currency"]

tab = new_tab("about:blank")
out = {}
try:
    for i, t in enumerate(["AAPL", "NVDA", "ZZZZQ"]):
        if i:
            time.sleep(3)
        s = finviz_stock(t)
        if s is None:
            print(t, "-> not on Finviz")
            continue
        out[t] = s
        k = s["snapshot"]
        print(t, s["company"], s["exchange"], s["sector"], "/", s["industry"], "| price", s["last_price"], s["price_time"],
              "| cells", len(k), "| P/E", k["P/E"], "| Market Cap", k["Market Cap"], "| EPS next Y", k["EPS next Y"],
              "| EPS growth next year", k["EPS growth next year"])
finally:
    cdp("Target.closeTarget", targetId=tab)  # an open Finviz tab keeps running ads and can stall a small browser
print(json.dumps({x: out["AAPL"]["snapshot"][x] for x in list(out["AAPL"]["snapshot"])[:12]}, indent=1))
inc = out["AAPL"]["income_statement"]
print(inc["currency"], inc["data"]["Period"], "Total Revenue", inc["data"]["Total Revenue"], "Net Income", inc["data"]["Net Income"])
path = os.path.join(tempfile.gettempdir(), "finviz_stocks.json")
with open(path, "w") as f:
    json.dump(out, f, indent=1)
print("saved", path)
```

Output from the test run (saved path shortened):

```
AAPL Apple Inc NASD Technology / Consumer Electronics | price 344.63 Oct 30 • 3:59 PM ET | cells 84 | P/E 39.51 | Market Cap 5029.59B | EPS next Y 9.56 | EPS growth next year 8.13%
NVDA NVIDIA Corp NASD Technology / Semiconductors | price 204.64 Oct 30 • 3:59 PM ET | cells 84 | P/E 25.87 | Market Cap 4931.82B | EPS next Y 15.81 | EPS growth next year 70.15%
ZZZZQ -> not on Finviz
{
 "Index": "DJIA, NDX, S&P 500",
 "Market Cap": "5029.59B",
 "Enterprise Value": "5051.54B",
 "Income": "128.93B",
 "Sales": "466.82B",
 "Book/sh": "7.36",
 "Cash/sh": "4.28",
 "Dividend Est.": "1.10 (0.32%)",
 "Dividend TTM": "1.06 (0.31%)",
 "Dividend Ex-Date": "Aug 10, 2026",
 "Dividend Gr. 3/5Y": "4.26% 4.98%",
 "Payout": "13.66%"
}
USD ['2025FY', '2024FY'] Total Revenue ['416,161.00', '391,035.00'] Net Income ['112,010.00', '93,736.00']
saved <tempdir>/finviz_stocks.json
```

### 2. Preset screeners, the site's own pages (browser)

Self-contained. Refuses any preset robots.txt does not list, reads the page's embedded JSON, follows the site's pager (`&r=11`, `&r=21` ... for 10-row views; `&r=13`, `&r=25` ... for the 12-row chart view) up to `max_pages`, and marks the result `truncated` when rows remain. About 3 s between page loads.

```python
import html, json, os, re, tempfile, time

def js_retry(expr, tries=6):
    # Finviz pages are ad-heavy; CDP calls sometimes miss the 5 s daemon timeout while the page is busy.
    for _ in range(tries):
        try:
            return js(expr)
        except TimeoutError:
            pass
        except RuntimeError as e:
            if "timed out" not in str(e):
                raise
        time.sleep(2)
    raise RuntimeError(f"page stayed busy for {tries} tries: {expr[:60]}")

def fv_open(url, timeout=45, settle=2.5):
    """Open url; return the landed URL. Raises on a Cloudflare challenge or if the page never loads."""
    prev = js_retry("location.href")
    try:
        goto_url(url)
    except TimeoutError:
        pass  # Page.navigate can exceed 5 s while the previous page unloads; the navigation still runs
    end = time.time() + timeout
    while True:
        if time.time() > end:
            raise RuntimeError(f"{url} did not finish loading in {timeout}s")
        time.sleep(1)
        href, state = js_retry("[location.href, document.readyState]")
        if state == "complete" and (href != prev or prev == url):
            break
    time.sleep(settle)
    title = js_retry("document.title") or ""
    challenge = js_retry("!!document.querySelector('#challenge-form, iframe[src*=\"challenges.cloudflare.com\"]')")
    if "Just a moment" in title or challenge:
        raise RuntimeError(f"Cloudflare challenge on {url}: stop and tell the user; do not retry around it")
    return js_retry("location.href")

# The presets robots.txt allows (checked 2026-10-31). Every other /screener?... or /screener/stocks?... URL is disallowed,
# so the view (v) and signal (s) pair must be exactly one of these; nothing here changes v, filters or sort order.
ALLOWED_PRESETS = {
    "ta_topgainers": 340, "ta_toplosers": 340, "ta_newhigh": 340, "ta_newlow": 340, "n_upgrades": 340,
    "n_downgrades": 340, "n_earningsbefore": 340, "n_earningsafter": 340, "it_latestbuys": 340,
    "it_latestsales": 340, "f_ssr": 340, "f_halted": 340,
    "ta_mostvolatile": 320, "ta_mostactive": 320, "ta_unusualvolume": 320, "n_majornews": 320,
    "ta_overbought": 210, "ta_oversold": 210, "ta_p_tlsupport": 210, "ta_p_tlresistance": 210,
    "ta_p_horizontal": 210, "ta_p_wedgeup": 210, "ta_p_wedge": 210, "ta_p_wedgedown": 210,
    "ta_p_wedgeresistance": 210, "ta_p_wedgesupport": 210, "ta_p_channelup": 210, "ta_p_channel": 210,
    "ta_p_channeldown": 210, "ta_p_doubletop": 210, "ta_p_multipletop": 210, "ta_p_doublebottom": 210,
    "ta_p_multiplebottom": 210, "ta_p_headandshoulders": 210, "ta_p_headandshouldersinv": 210,
}

STATE_JS = """(() => { const s = [...document.scripts].find(s => s.type === 'application/json' && s.textContent.includes('"screenerType"'));
  return s ? s.textContent : null })()"""
TOTAL_JS = """(() => { const e = [...document.querySelectorAll('span')].find(e => /^#\\d+ \\/ \\d+ Total$/.test(e.innerText.trim()));
  return e ? e.innerText.trim() : null })()"""

def finviz_preset_page(signal, row=1):
    """One page of a robots-allowed preset. row is the site's own pager offset: 1, 11, 21 ... (v=340/320) or 1, 13, 25 ... (v=210)."""
    if signal not in ALLOWED_PRESETS:
        raise ValueError(f"{signal}: not a robots.txt-allowed preset")
    v = ALLOWED_PRESETS[signal]
    url = f"https://finviz.com/screener/stocks?v={v}&s={signal}" + (f"&r={row}" if row > 1 else "")
    landed = fv_open(url)
    if landed != url:
        raise RuntimeError(f"asked for {url}, landed on {landed}; not reading it")
    raw = js_retry(STATE_JS)
    if not raw:
        raise RuntimeError(f"{url}: no screener state JSON; layout changed?")
    st = json.loads(raw)
    if "data" in st:  # v=340 snapshot and v=320 news views: full rows with price, change, volume
        d = st["data"]
        num = lambda r, k, nd=2: None if r["numbers"].get(k) is None else round(r["numbers"][k], nd)
        rows = [{"ticker": r["text"]["ticker"], "company": r["text"]["company"], "industry": r["text"].get("industry"),
                 "country": r["text"].get("country"), "exchange": r["text"].get("exchange"),
                 "price": num(r, "price", 4), "change_pct": num(r, "change"),
                 "volume": r["numbers"].get("volume"), "avg_volume": num(r, "averageVolume", 0),
                 "market_cap_musd": num(r, "marketCap"), "pe": num(r, "PE")} for r in d["rows"]]
        total, first, size = d["totalCount"], d["firstRow"] + 1, d["pageSize"]
    else:  # v=210 chart views: tickers only (price data is in chart images)
        rows = []
        for c in st["charts"]["charts"]:
            # boxoverHtml: "<b>Century Casinos Inc</b><br>Resorts &amp; Casinos • USA • 14.63M"
            name, _, rest = html.unescape(c["boxoverHtml"]).partition("<br>")
            rows.append({"ticker": c["ticker"], "company": re.sub(r"<[^>]+>", "", name).strip()}
                        | dict(zip(("industry", "country", "market_cap"), rest.split(" • "))))
        m = re.fullmatch(r"#(\d+) / (\d+) Total", js_retry(TOTAL_JS) or "")
        if not m:
            raise RuntimeError(f"{url}: no '#n / N Total' counter")
        first, total, size = int(m.group(1)), int(m.group(2)), 12
    if first != row:
        raise RuntimeError(f"{url}: page starts at row {first}, expected {row}")
    return {"url": url, "view": v, "total": total, "first_row": first, "page_size": size, "rows": rows}

def finviz_preset(signal, max_pages=2, pause=3):
    pages = [finviz_preset_page(signal)]
    size, total = pages[0]["page_size"], pages[0]["total"]
    while len(pages) < max_pages and len(pages) * size < total:
        time.sleep(pause)
        pages.append(finviz_preset_page(signal, row=len(pages) * size + 1))
    rows = [r for p in pages for r in p["rows"]]
    return {"signal": signal, "view": pages[0]["view"], "total": total, "rows": rows, "truncated": len(rows) < total}

tab = new_tab("about:blank")
out = {}
try:
    for i, (sig, n) in enumerate([("ta_topgainers", 2), ("ta_unusualvolume", 1), ("ta_oversold", 2)]):
        if i:
            time.sleep(3)
        p = finviz_preset(sig, max_pages=n)
        out[sig] = p
        print(f'{sig:17} v={p["view"]} total={p["total"]:<4} rows={len(p["rows"]):<3} truncated={p["truncated"]}')
        for r in p["rows"][:3]:
            print("   ", r)
finally:
    cdp("Target.closeTarget", targetId=tab)  # an open Finviz tab keeps running ads and can stall a small browser
print("top gainers, change % in page order:", [r["change_pct"] for r in out["ta_topgainers"]["rows"]])
try:
    finviz_preset_page("cap_mega")  # a custom filter, not a preset: refused before any request
except ValueError as e:
    print("refused:", e)
path = os.path.join(tempfile.gettempdir(), "finviz_presets.json")
with open(path, "w") as f:
    json.dump(out, f, indent=1)
print("saved", path)
```

Output from the test run (saved path shortened):

```
ta_topgainers     v=340 total=130  rows=20  truncated=True
    {'ticker': 'ONEG', 'company': 'OneConstruction Group Ltd', 'industry': 'Engineering & Construction', 'country': 'Hong Kong', 'exchange': 'NASD', 'price': 1.63, 'change_pct': 108.15, 'volume': 109703824, 'avg_volume': 40697.0, 'market_cap_musd': 26.08, 'pe': None}
    {'ticker': 'CHOW', 'company': 'ChowChow Cloud International Holdings Ltd', 'industry': 'Software - Infrastructure', 'country': 'Hong Kong', 'exchange': 'AMEX', 'price': 4.4, 'change_pct': 106.57, 'volume': 68954414, 'avg_volume': 907398.0, 'market_cap_musd': 15.62, 'pe': None}
    {'ticker': 'SLGB', 'company': 'Smart Logistics Global Ltd', 'industry': 'Integrated Freight & Logistics', 'country': 'Hong Kong', 'exchange': 'NASD', 'price': 0.3051, 'change_pct': 48.97, 'volume': 301221208, 'avg_volume': 4367960.0, 'market_cap_musd': 13.12, 'pe': None}
ta_unusualvolume  v=320 total=200  rows=10  truncated=True
    {'ticker': 'ONEG', 'company': 'OneConstruction Group Ltd', 'industry': 'Engineering & Construction', 'country': 'Hong Kong', 'exchange': 'NASD', 'price': 1.63, 'change_pct': 108.15, 'volume': 109703824, 'avg_volume': 40697.0, 'market_cap_musd': 26.08, 'pe': None}
    {'ticker': 'HUBC', 'company': 'Hub Cyber Security Ltd', 'industry': 'Software - Infrastructure', 'country': 'Israel', 'exchange': 'NASD', 'price': 0.1134, 'change_pct': -16.0, 'volume': 196784643, 'avg_volume': 1320169.0, 'market_cap_musd': 0.2, 'pe': None}
    {'ticker': 'ABOS', 'company': 'Acumen Pharmaceuticals Inc', 'industry': 'Biotechnology', 'country': 'USA', 'exchange': 'NASD', 'price': 0.2101, 'change_pct': -90.83, 'volume': 68105173, 'avg_volume': 517579.0, 'market_cap_musd': 15.2, 'pe': None}
ta_oversold       v=210 total=94   rows=24  truncated=True
    {'ticker': 'CNTY', 'company': 'Century Casinos Inc', 'industry': 'Resorts & Casinos', 'country': 'USA', 'market_cap': '14.63M'}
    {'ticker': 'ADBT', 'company': 'Advasa Holdings Inc', 'industry': 'Software - Application', 'country': 'Japan', 'market_cap': '51.97M'}
    {'ticker': 'CTNT', 'company': 'Cheetah Net Supply Chain Service Inc', 'industry': 'Integrated Freight & Logistics', 'country': 'USA', 'market_cap': '2.81M'}
top gainers, change % in page order: [108.15, 106.57, 48.97, 40.78, 30.53, 30.15, 29.82, 29.68, 27.95, 27.68, 27.54, 27.34, 26.34, 26.15, 24.31, 22.22, 20.71, 19.4, 19.25, 18.75]
refused: cap_mega: not a robots.txt-allowed preset
saved <tempdir>/finviz_presets.json
```

## Fields

| Field | Source | Notes |
|---|---|---|
| `snapshot` | `table.js-snapshot-table` label/value cells | 84 keys, values are display strings (`"5029.59B"`, `"39.51"`, `"4.26% 4.98%"`, `"-"` when missing) |
| `snapshot["EPS next Y"]` / `["EPS growth next year"]` | same label twice | first is the EPS estimate, second the growth %; the helper keys the second by its tooltip (`data-boxover-html`) |
| `snapshot["Trades"]` | | empty string when logged out |
| `last_price`, `price_time` | first `.quote-price_price`, `.quote-price_date` | regular-session last price; an aftermarket price follows it on the page. Quotes are delayed (page footer: "Stock quotes delayed by 1 minute") |
| `sector`, `industry`, `country`, `exchange` | header links `f=sec_`, `f=ind_`, `f=geo_`, `f=exch_` | text only; the links go to `/screener?v=111&f=...`, which robots.txt disallows |
| `income_statement` | `#income-breakdown-init-data-0` `.statement` | `currency`, `data.Period` (e.g. `2025FY`, `2024FY`), rows as strings in millions (`"416,161.00"`) |
| preset `price`, `change_pct`, `volume`, `avg_volume` | JSON `data.rows[].numbers` | v=340/320 only; `change_pct` is percent |
| preset `market_cap_musd` | `numbers.marketCap` | millions USD (26.08 shows as "26.08M" on the page) |
| preset `total` | `data.totalCount` or the `#1 / N Total` counter | v=210 has no `data`, so the counter is parsed |
| chart-view `market_cap` | `charts.charts[].boxoverHtml` | string such as `"14.63M"` |

## Gotchas

- CDP calls on Finviz sometimes exceed browser-harness's 5 s daemon timeout while ads load. The helpers retry (`js_retry`) and treat a timed-out `Page.navigate` as still running. With several Finviz tabs left open the cloud browser stopped answering ("required daemon ... is unhealthy: timed out") and had to be restarted; after closing the tab in `finally`, 6 consecutive runs of the two blocks below completed (25 to 39 s each).
- `ta_topgainers` rows come in descending `change_pct` order (20 of 20 rows checked across 2 pages).
- `ta_unusualvolume` reported `totalCount` 200 on 2026-10-31.
- `/screener?v=340&s=ta_topgainers` 302s to `/screener/stocks?v=340&s=ta_topgainers`; robots.txt allows the same 35 presets under both paths. The helper requests the `/screener/stocks` form directly and refuses to read a page whose final URL differs from the one requested.
- On a weekend the header shows "Last Close" for the last session (Oct 30 on Saturday Oct 31) and the aftermarket close.
- Chart images on screener pages come from `charts2-node.finviz.com`; the helpers do not fetch them (`/chart` on finviz.com is disallowed).
- No Cloudflare challenge appeared in more than 40 browser page loads at 2 to 3 s spacing. If one does, the helpers raise: stop and tell the user.

## What does not work

- Plain HTTP with Python `urllib` (its default user agent): HTTP 403, body `error code: 1010`, on `/stock?t=AAPL` and `/screener/stocks?...` (2026-10-31). Not worked around by changing the user agent.
- Custom screeners (`f=` filters, other views such as the `v=111` table, `o=` sort), name search (`/search`), and CSV export (`/export`, `/api/v1/screener-export-csv`): disallowed by robots.txt. Not used.
- Price on `v=210` chart-view presets: not in the page data, only in chart images. Use the stock page for a ticker's price.
