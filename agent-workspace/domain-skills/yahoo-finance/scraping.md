# Yahoo Finance - Quote Summary and Historical OHLCV

Field-tested against finance.yahoo.com on 2026-10-31 using a Browser Use cloud browser (logged out, US exit IP).

robots.txt (checked 2026-10-31) for `User-agent: *` has no rule matching `/quote/<T>/` or `/quote/<T>/history/` (it disallows `/quotes/*`, `/lookup?s=*`, `/lookup/` and `/quote/*/earnings/*.html`), and query1.finance.yahoo.com/robots.txt is `Disallow: /`, so this skill reads only the rendered quote and history pages and never calls query1/query2 itself.

## Quick summary

- **Quote summary**: open `https://finance.yahoo.com/quote/<T>/` in a browser and read the DOM. Price, change and change % are `[data-testid="qsp-price"]`, `qsp-price-change`, `qsp-price-change-percent`; after-hours/pre-market values are the `qsp-post-*` twins. The stats list is `[data-testid="quote-statistics"] li` (`.label` + `.value`), 16 rows for a stock, 6 for an index, 14 for a crypto.
- **Historical OHLCV**: open `https://finance.yahoo.com/quote/<T>/history/?period1=<unix>&period2=<unix>[&frequency=1wk|1mo]`. This is the exact URL the page's own date picker and frequency menu write. The whole range renders as one `<table>` inside `[data-testid="history-table"]`, no pagination: AAPL from 1980 to today was 11,564 price rows + 97 dividend/split rows in one load (12.5 s and 19.6 s in two runs).
- Dividend and split rows sit inline in the price table as 2-cell rows (`0.24 Dividend`, `4:1 Stock Splits`). Block 2 splits them out.
- The "Download" (CSV) link is paywalled (`/plus/gold/...`) when logged out. Read the table instead.
- No consent wall, login wall or challenge was hit from the cloud browser. Both blocks stop (raise) if they land anywhere other than the requested page.

## What works

### 1. Quote summary (browser, DOM)

```python
import json, time, urllib.parse

TICKERS = ["AAPL", "MSFT", "^GSPC", "BTC-USD"]   # Yahoo symbols you already know are valid

READ_QUOTE = r"""(() => {
  const q = s => document.querySelector(s);
  const txt = s => (q(s) && q(s).innerText.trim()) || null;
  const hdr = q('[data-testid="quote-hdr"]');
  const price = q('[data-testid="quote-price"]');
  const hdrLines = hdr ? hdr.innerText.split('\n').map(s => s.trim()).filter(Boolean) : [];
  const stats = {}, fields = {};   // label -> shown text; label -> Yahoo field name
  for (const li of document.querySelectorAll('[data-testid="quote-statistics"] li')) {
    const label = li.querySelector('.label'), value = li.querySelector('.value');
    if (!label || !value) continue;
    const key = label.innerText.trim();
    stats[key] = value.innerText.trim();
    const fs = value.querySelector('fin-streamer[data-field]');
    if (fs) fields[key] = fs.dataset.field;   // e.g. "Volume" -> "regularMarketVolume"
  }
  return {
    url: location.href,
    title: document.title,
    name: txt('[data-testid="quote-title"] h1'),
    exchange_line: hdrLines[0] || null,
    currency: hdrLines.find(s => /^[A-Z]{3}$/.test(s)) || null,
    price: txt('[data-testid="qsp-price"]'),
    change: txt('[data-testid="qsp-price-change"]'),
    change_pct: txt('[data-testid="qsp-price-change-percent"]'),
    post_price: txt('[data-testid="qsp-post-price"]'),
    post_change: txt('[data-testid="qsp-post-price-change"]'),
    post_change_pct: txt('[data-testid="qsp-post-price-change-percent"]'),
    times: price ? price.innerText.split('\n').map(s => s.trim()).filter(s => /^(At close|As of|After hours|Pre-Market|Overnight)/i.test(s)) : [],
    stats, fields,
  };
})()"""

def open_page(url, tries=3):
    # Yahoo pages are heavy (ads, live quotes). goto_url() gives up after ~5 s while the tab is busy;
    # the navigation usually still lands, so wait and retry only on that timeout.
    for i in range(tries):
        try:
            goto_url(url)
            break
        except Exception as e:
            if "timed out" not in str(e) or i == tries - 1:
                raise
            time.sleep(5)
    for i in range(tries):   # wait_for_load() polls js(), which also times out while a big page renders
        try:
            wait_for_load()
            return
        except (TimeoutError, RuntimeError) as e:
            if (not isinstance(e, TimeoutError) and "timed out" not in str(e)) or i == tries - 1:
                raise
            time.sleep(2)

def js_retry(expr, tries=3):
    # A busy page makes js() time out (TimeoutError, or RuntimeError "... timed out ..."); retry only that.
    for _ in range(tries):
        try:
            return js(expr)
        except (TimeoutError, RuntimeError) as e:
            if not isinstance(e, TimeoutError) and "timed out" not in str(e):
                raise
            time.sleep(2)
    raise TimeoutError(f"js() timed out {tries} times")

def quote_summary(symbol):
    url = f"https://finance.yahoo.com/quote/{urllib.parse.quote(symbol, safe='')}/"   # ^GSPC -> %5EGSPC
    open_page(url)
    d = None
    for _ in range(20):   # the price header and stats list render client-side; wait up to ~20 s
        d = js_retry(READ_QUOTE)
        if not d["url"].startswith(url):
            # consent page (guce.yahoo.com), a redirect for an unknown symbol, or a challenge: stop, do not work around it
            raise RuntimeError(f"{symbol}: landed on {d['url']} ({d['title']!r}); stopping")
        if d["price"] and d["stats"]:
            return d
        time.sleep(1)
    raise RuntimeError(f"{symbol}: no price/stats after 20 s at {d['url']} ({d['title']!r}); stopping")

tab = new_tab()
try:
    for i, sym in enumerate(TICKERS):
        if i:
            time.sleep(3)   # polite pacing between pages
        d = quote_summary(sym)
        print(json.dumps({k: d[k] for k in ("name", "exchange_line", "currency", "price", "change", "change_pct", "post_price", "times")}))
        print(f"  {len(d['stats'])} stats:", json.dumps(d["stats"]))
        print("  fields:", json.dumps(dict(list(d["fields"].items())[:4])))
finally:
    close_tab(tab)
```

Observed output (2026-10-31, a Saturday, so the last session is Oct 30; trimmed):

```
{"name": "Apple Inc. (AAPL)", "exchange_line": "NasdaqGS - Nasdaq Real Time Price", "currency": "USD", "price": "344.63", "change": "-4.28", "change_pct": "(-1.23%)", "post_price": "345.10", "times": ["At close: October 30 at 4:00:01 PM EDT", "After hours: October 30 at 7:59:55 PM EDT"]}
  16 stats: {"Previous Close": "348.91", "Open": "346.68", "Bid": "343.03 x 400", "Ask": "350.00 x 2000", "Day's Range": "342.35 - 349.19", "52 Week Range": "243.42 - 351.73", "Volume": "67,842,804", "Avg. Volume": "41,866,653", "Market Cap (intraday)": "5.03T", "Beta (5Y Monthly)": "1.07", "PE Ratio (TTM)": "39.52", "EPS (TTM)": "8.72", "Earnings Date": "Nov 2, 2026", "Forward Dividend & Yield": "1.08 (0.31%)", "1y Target Est": "332.39", "Yahoo Finance Rating": "Rating available with Stock Picks access"}
  fields: {"Previous Close": "regularMarketPreviousClose", "Open": "regularMarketOpen", "Day's Range": "regularMarketDayRange", "52 Week Range": "fiftyTwoWeekRange"}
{"name": "Microsoft Corporation (MSFT)", ... "price": "521.91", ... "Earnings Date (est.)": "Jan 27, 2027", ... "Morningstar Rating": "Rating available with Stock Picks access"}
{"name": "S&P 500 (^GSPC)", "exchange_line": "SNP - Delayed Quote", "currency": "USD", "price": "7,580.07", "change": "-140.32", "change_pct": "(-1.82%)", "post_price": null, "times": ["At close: October 30 at 4:47:43 PM EDT"]}
  6 stats: {"Previous Close": "7,720.39", "Open": "7,631.07", "Volume": "4,268,617,000", "Day's Range": "7,527.56 - 7,637.48", "52 Week Range": "6,316.91 - 7,844.52", "Avg. Volume": "5,088,826,875"}
{"name": "Bitcoin USD Price (BTC-USD)", "exchange_line": "Cryptocurrency", "currency": "USD", "price": "77,547.22", "change": "+1,064.71", "change_pct": "(+1.39%)", "post_price": null, "times": ["As of 6:44:33 PM UTC. Market Open."]}
  14 stats: {"Market Cap": "1.56T", "Fully Diluted Valuation": "1.63T", "Volume (24hr)": "15.90B", ..., "Circulating Supply": "20.11M", "Max Supply": "21.00M", "All-time high": "126,198.07", "All-time low": "171.51"}
```

### 2. Historical OHLCV table (browser, DOM)

```python
import json, time, calendar, urllib.parse
from datetime import date, datetime, timedelta

SYMBOL = "AAPL"
START, END = date(2024, 1, 1), date(2024, 3, 31)   # inclusive calendar dates
FREQUENCY = "1d"                                    # the page's own menu values: 1d, 1wk, 1mo

READ_TABLE = r"""(() => {
  const t = document.querySelector('[data-testid="history-table"] table');
  if (!t) return {url: location.href, title: document.title, head: null, rows: []};
  return {
    url: location.href,
    title: document.title,
    range_label: ([...document.querySelectorAll('main button')].map(b => b.innerText.trim()).find(s => /\d{4} - /.test(s)) || null),
    head: [...t.querySelectorAll('thead th')].map(th => th.innerText.trim()),
    rows: [...t.querySelectorAll('tbody tr')].map(r => [...r.cells].map(c => c.innerText.trim())),
  };
})()"""

def open_page(url, tries=3):
    # Yahoo pages are heavy (ads, live quotes). goto_url() gives up after ~5 s while the tab is busy;
    # the navigation usually still lands, so wait and retry only on that timeout.
    for i in range(tries):
        try:
            goto_url(url)
            break
        except Exception as e:
            if "timed out" not in str(e) or i == tries - 1:
                raise
            time.sleep(5)
    for i in range(tries):   # wait_for_load() polls js(), which also times out while a big page renders
        try:
            wait_for_load()
            return
        except (TimeoutError, RuntimeError) as e:
            if (not isinstance(e, TimeoutError) and "timed out" not in str(e)) or i == tries - 1:
                raise
            time.sleep(2)

def js_retry(expr, tries=3):
    # A busy page makes js() time out (TimeoutError, or RuntimeError "... timed out ..."); retry only that.
    for _ in range(tries):
        try:
            return js(expr)
        except (TimeoutError, RuntimeError) as e:
            if not isinstance(e, TimeoutError) and "timed out" not in str(e):
                raise
            time.sleep(2)
    raise TimeoutError(f"js() timed out {tries} times")

def num(s):
    s = (s or "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None   # "-" = no value on that row

def history(symbol, start, end, frequency="1d"):
    """OHLCV rows for start..end (inclusive), newest first, plus dividend/split rows, from /quote/<T>/history/."""
    # Same URL the page's own date picker writes: unix seconds, period2 exclusive.
    p1 = calendar.timegm(start.timetuple())
    p2 = calendar.timegm((end + timedelta(days=1)).timetuple())
    base = f"https://finance.yahoo.com/quote/{urllib.parse.quote(symbol, safe='')}/history/"   # ^GSPC -> %5EGSPC
    url = f"{base}?period1={p1}&period2={p2}"
    if frequency != "1d":
        url += f"&frequency={frequency}"
    open_page(url)
    last_n, d = -1, None
    for _ in range(25):   # rows render client-side; wait until the count is non-zero and stable
        d = js_retry(READ_TABLE)
        if not d["url"].startswith(base):
            raise RuntimeError(f"{symbol}: landed on {d['url']} ({d['title']!r}); stopping")
        if d["rows"] and len(d["rows"]) == last_n:
            break
        last_n = len(d["rows"])
        time.sleep(1)
    else:
        raise RuntimeError(f"{symbol}: table did not settle ({last_n} rows) at {d['url']}; stopping")
    head = [h.lower() for h in d["head"]]
    if head != ["date", "open", "high", "low", "close", "adj close", "volume"]:
        raise RuntimeError(f"{symbol}: unexpected columns {d['head']}; layout changed?")
    prices, events = [], []
    for cells in d["rows"]:
        day = datetime.strptime(cells[0], "%b %d, %Y").date().isoformat()
        if len(cells) == 7:
            o, h, l, c, ac, v = (num(x) for x in cells[1:])
            prices.append({"date": day, "open": o, "high": h, "low": l, "close": c, "adj_close": ac,
                           "volume": int(v) if v is not None else None})
        else:   # "0.25 Dividend" or "4:1 Stock Splits" spans the row
            events.append({"date": day, "event": cells[1]})
    return {"url": d["url"], "range_label": d["range_label"], "prices": prices, "events": events}

tab = new_tab()
try:
    h = history(SYMBOL, START, END, FREQUENCY)
    p = h["prices"]
    print(h["url"])
    print("range shown:", h["range_label"], "|", len(p), "price rows,", len(h["events"]), "events")
    print("newest:", json.dumps(p[0]))
    print("oldest:", json.dumps(p[-1]))
    print("events:", json.dumps(h["events"]))
finally:
    close_tab(tab)
```

Observed output:

```
https://finance.yahoo.com/quote/AAPL/history/?period1=1704067200&period2=1711929600
range shown: Jan 01, 2024 - Apr 01, 2024 | 61 price rows, 1 events
newest: {"date": "2024-03-28", "open": 171.75, "high": 172.23, "low": 170.51, "close": 171.48, "adj_close": 169.63, "volume": 65672700}
oldest: {"date": "2024-01-02", "open": 187.15, "high": 188.44, "low": 183.89, "close": 185.64, "adj_close": 183.4, "volume": 82488700}
events: [{"date": "2024-02-09", "event": "0.24 Dividend"}]
```

61 rows = every NYSE trading day of Q1 2024 (Mar 29 was Good Friday). The same `history()` function, called in one tab with 3 s between pages, returned:

| Call | Price rows | Events | Notes |
|---|---|---|---|
| `("AAPL", date(2020,8,24), date(2020,9,4), "1d")` | 10 | 1 | `{"date": "2020-08-31", "event": "4:1 Stock Splits"}` |
| `("^GSPC", date(2025,1,1), date(2025,12,31), "1mo")` | 12 | 0 | one row per month, dated the 1st |
| `("BTC-USD", date(2026,10,20), date(2026,10,31), "1d")` | 12 | 0 | crypto trades every day, newest row is today (live) |
| `("MSFT", date(2026,9,1), date(2026,10,31), "1wk")` | 10 | 0 | 9 weeks + 1 live row, see Gotchas |
| `("AAPL", date(1980,1,1), date(2026,10,31), "1d")` | 11,564 | 97 | oldest row 1980-12-12, whole table in one load |

## Fields

Block 1 (`quote_summary`), all values are the strings shown on the page:

| Key | Source | Example |
|---|---|---|
| name | `[data-testid="quote-title"] h1` | `"Apple Inc. (AAPL)"` |
| exchange_line | first line of `[data-testid="quote-hdr"]` | `"NasdaqGS - Nasdaq Real Time Price"`, `"SNP - Delayed Quote"`, `"Cryptocurrency"` |
| currency | 3-letter line in the header | `"USD"` |
| price / change / change_pct | `qsp-price`, `qsp-price-change`, `qsp-price-change-percent` | `"344.63"`, `"-4.28"`, `"(-1.23%)"` |
| post_price / post_change / post_change_pct | `qsp-post-price*` | after-hours or pre-market; `null` for indexes and crypto |
| times | lines under the price | `"At close: October 30 at 4:00:01 PM EDT"`, `"As of 6:44:33 PM UTC. Market Open."` |
| stats | `quote-statistics li` `.label` -> `.value` | dict; labels differ by symbol type and even by stock |
| fields | `fin-streamer[data-field]` inside a stat value | label -> stable Yahoo field name (`regularMarketVolume`, `marketCap`, ...); only stats that stream live have one |

Block 2 (`history`): `prices` is a list of `{date (ISO), open, high, low, close, adj_close, volume}`, newest first, floats with commas removed, `volume` int; `events` is `{date, event}` with the row text as shown (`"0.27 Dividend"`, `"4:1 Stock Splits"`); `range_label` is the date-picker button text; `url` is the final page URL.

## Gotchas

- **Stats labels are not stable keys.** AAPL had "Earnings Date" and "Yahoo Finance Rating", MSFT had "Earnings Date (est.)" and "Morningstar Rating"; indexes have 6 stats, crypto has its own set (Circulating Supply, All-time high, ...). Use `fields` (the `data-field` names) when you need a stable key; values in both are the formatted page text (`"5.03T"`, `"67,842,804"`).
- **Close is split-adjusted, Adj Close is split and dividend adjusted.** Header tooltips: "Close price adjusted for splits." and "Adjusted close price adjusted for splits and dividend and/or capital gain distributions." The 1980 AAPL row shows Close 0.13.
- **History volume differs slightly from the quote page.** Oct 30 AAPL: history row 67,797,500, quote page "Volume" 67,842,804; OHLC also differed (history low 334.35, quote Day's Range low 342.35). Pick one source.
- **Weekly/monthly ranges that include the current period get an extra live row.** MSFT `1wk` to Oct 31 started with a row dated Oct 30 (that day's open/high/low/volume) above the Oct 26 week row. Drop the first row if its date falls inside the next row's week/month.
- **period2 is exclusive** and the picker label shows it as the end date (`Jan 01, 2024 - Apr 01, 2024` for Q1). Block 2 adds one day so `END` is inclusive. Times are UTC midnight; the picker itself writes "now minus N years" timestamps.
- **Symbols must be URL-encoded.** The browser reports `^GSPC` as `%5EGSPC` in `location.href`; both blocks quote the symbol so the landing check matches.
- **Heavy pages.** One cloud browser stopped answering CDP (`Page.navigate timed out after 5s`, then the daemon reported "unhealthy: timed out") after a crypto history page took 32 s to load; stopping and restarting the same named browser fixed it and the identical sequence then ran clean (each page 9 to 14 s). While the 11,564-row AAPL table rendered, `wait_for_load()` itself raised `Runtime.evaluate timed out; expression: document.readyState`. `open_page` retries both the 5 s navigate timeout and that `wait_for_load()` timeout; it cannot revive a hung browser.
- **Unknown symbols** were not tested: the site's symbol search lives under `/lookup`, which robots.txt disallows. Pass symbols you already know, and both blocks raise if the page ends up anywhere other than the requested `/quote/<T>/` URL.
- **`document.title`** carries the harness tab marker (horse emoji) in front of the site title when `BH_TAB_MARKER` is on.
- **Pacing.** About 25 page loads over roughly 30 minutes at 3 s or more apart, no 429, consent page or challenge. Heavier rates were not tested.

## What does not work

- **CSV download**: the "Download" link on the history page goes to a Yahoo Finance Plus upsell (`/plus/gold/...`) when logged out.
- **Calling `query1.finance.yahoo.com` (or query2) directly**: robots.txt there is `Disallow: /`; this skill does not do it.
- **`/quotes/...`, `/lookup...`, `/quote/<T>/earnings/*.html`** (except the dated 2025/2026 earnings pages robots.txt re-allows): disallowed, not used.
