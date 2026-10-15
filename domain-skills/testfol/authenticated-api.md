# testfol.io — authenticated browser API

Use this note when a user asks to inspect, compare, or grid-test saved testfol.io runs. The reliable path is to execute `fetch()` from an authenticated browser tab on the `https://testfol.io` origin so the page can read the user's existing session token from `localStorage`.

## First principle

- Open a real `https://testfol.io/...` tab first. The auth token is origin-scoped, so a blank page, local file, or unrelated site cannot access it.
- Do not print, log, save, or commit the raw token. Use it only inside the in-page script.
- Keep calls low-volume and user-directed. These are private app endpoints, useful for personal research automation, not a public scraping interface.

## Minimal authenticated tactical replay

Replace `<share_id>` with the ID from a saved URL such as `https://testfol.io/tactical?s=2h96nLURf8z`.

```python
new_tab("https://testfol.io/tactical?s=<share_id>")
wait_for_load()

script = r"""
(async () => {
  const key = Object.keys(localStorage).find(k => k.includes("supabase") || k.includes("auth-token"));
  const raw = key ? localStorage.getItem(key) : null;
  const token = raw ? JSON.parse(raw).access_token : null;
  const authHeaders = token ? {Authorization: `Bearer ${token}`} : {};
  const headers = {"Content-Type": "application/json", ...authHeaders};

  const params = await (await fetch("/api/link/<share_id>?tool=tactical", {
    headers: authHeaders
  })).json();

  const result = await (await fetch("/api/tactical", {
    method: "POST",
    headers,
    body: JSON.stringify(params)
  })).json();

  const strategy =
    result.stats?.find(x => x.name === "LETF Strat") ||
    result.stats?.find(x => x.name === "Strategy") ||
    result.stats?.at(-1);

  return JSON.stringify({
    authenticated: Boolean(token),
    start_date: result.start_date,
    end_date: result.end_date,
    limiting_ticker: result.limiting_ticker,
    errors: result.errors,
    stats: result.stats,
    allocation_stats: result.allocation_stats,
    current_status_rows: result.current_status_rows,
    strategy
  });
})()
"""

print(js(script))
```

If `authenticated` is false, the active tab is probably not logged in or not on the `testfol.io` origin. Unauthenticated Tactical calls can return `{"detail":"Sign in with a free account to use Tactical Allocation."}` even when a share page is visible.

## Useful endpoints observed

- `GET /api/link/<id>?tool=tactical` returns the saved tactical parameters for a shared run. It does not run the backtest.
- `POST /api/link` with body `{tool:"tactical", params}` **creates** a new shareable saved run and returns `{link_id}`. The shareable URL is `https://testfol.io/tactical?s=<link_id>`. Set `params.name` to label it (the only title field; verified 2026-06-22). Round-trip-verify by GETting the new id and replaying through `/api/tactical`.
- `POST /api/tactical` runs a tactical allocation backtest from the saved or modified params JSON.
- `GET /api/limits` reports whether the logged-in session has access to Tactical features.
- Other observed endpoints include `/api/backtest`, `/api/backtest/example`, `/api/backtest/regression`, `/api/link`, `/api/tactical/example`, `/api/tactical/frontier`, `/api/tactical/what-if`, `/api/tactical/live`, `/api/tactical-grid-search`, `/api/saved-runs`, and `/api/user-series`.

## Fields to inspect

- `result.stats`: rows for benchmark, sleeves, and total strategy. The strategy row may be named `LETF Strat`, `Strategy`, or another user-provided label.
- `result.allocation_stats`: switching behavior, switches per year, and time spent in each sleeve.
- `result.current_status_rows`: latest live signal/status rows.
- `result.start_date`, `result.end_date`, `result.limiting_ticker`, `result.errors`: evidence quality and data-bound checks.
- `params.signals`, `params.signal_display_order`, and each allocation's `signals`: this is how to confirm the active signal. Do not assume the title or URL reflects the active rule; saved runs can contain unused signals.

## Safe variant testing

Clone the saved `params`, mutate only the intended fields, then send the clone to `POST /api/tactical`.

Common mutations:

- Trading cost: `params.trading_cost = 1.0`.
- Signal lookback: clone a signal, set `signal.name`, set `signal.indicator_2.lookback`, set `params.signals = [signal]`, set `params.signal_display_order = [signal.name]`, and set `params.allocations[0].signals = [signal.name]`.
- Risk-on sleeve: replace `params.allocations[0].tickers` with `{ticker, percent}` rows.
- Risk-off sleeve: replace `params.allocations[1].tickers`.
- Synthetic LETF spread: edit the ticker query string with `SP=0.30`, `SP=0.35`, or `SP=0.40` without assuming query-param order.

For strategy review, export or save the full JSON result for each important run. A compact table is good for the user, but durable conclusions should be backed by raw `stats`, `allocation_stats`, active signal params, date range, and limiting ticker.

## Building a tactical strategy from scratch (schema, field-verified 2026-06-22)

No local skeleton needed — `GET /api/link/2h96nLURf8z?tool=tactical` returns a valid
default params object to clone. Then POST the mutated clone to `/api/tactical`.
Validation is Pydantic, so a bad field returns HTTP 422 with `detail[]` naming the
exact `loc` and allowed enum — **always read `resp.json().detail` on failure**, the
errors are self-documenting.

**Allocations evaluate top-down, first-match-wins.** This is `if / elif / else`:
order allocations by priority; the **last** allocation with an empty `signals:[]` is
the unconditional fallback (e.g. cash/bonds). Each earlier allocation is gated by its
`signals` (referenced by `name`), combined via `ops`, each optionally negated via
`nots`.

Hard-won rules (each cost a 422 round-trip):

- **`comparison` enum is only `'<'`, `'>'`, `'='`** — there is **no `<=`/`>=`**. Use
  `<` (the off-by-epsilon vs `<=` is immaterial for a 25-level VIX gate etc.).
- **`indicator.type` enum**: `SMA, EMA, Price, Level, Return, CAGR, CMGR, Volatility,
  Drawdown, RSI, Win Rate, Correlation, VIX, VIX3M, T10Y, T2Y, T3M, T6M, T1Y, T3Y,
  T5Y, T7Y, T20Y, T30Y, Month, Day of Week, Day of Month, Day of Year, Threshold`.
  There is **no `Constant`** — a literal cutoff is type **`Threshold`** with `value` set.
- **`Price` cannot be compared to `Threshold`** ("indicator types are incompatible") —
  `Price` is a normalized growth index, not a level. To gate on an absolute number use a
  level-like type: VIX≤25 is `indicator_1.type:"VIX"` `<` `indicator_2.type:"Threshold",
  value:25`. (Treasury rates: `T10Y` etc. compared to a `Threshold`.)
- **`ticker` must be a string even when the type ignores it** (`VIX`, `Threshold`,
  `Month`…). `null` → 422. Pass any valid ticker string (e.g. `"SPYSIM"`) as a filler.
- **`ops` length must equal `signals` length − 1.** Single-signal allocation → `ops:[]`.
  Two signals AND'd → `ops:["AND"]` (`"OR"` also valid). `nots` length must equal
  `signals` length (`[false,false]` for two un-negated signals).
- **Builder trap:** when constructing an allocation object, spread the shared defaults
  **first** and put explicit `ops`/`signals`/`nots` **last**
  (`{...DEFAULTS, name, signals, ops, nots, tickers}`). If defaults (which carry
  `ops:[]`) are spread last they silently clobber your `ops`, and the failure is a
  confusing "ops must equal signals−1" — or, for single-signal strats, no error at all,
  so the bug hides until you add an AND.
- `trading_freq` (top level) = signal eval cadence (`"Monthly"` = month-end, `delay:1`
  avoids look-ahead). Per-allocation `rebalance_freq` only matters for multi-ticker sleeves.
- Synthetic LETFs as deep-history holdings: `SPYSIM?L=2&E=0.91&SP=0.30` (SSO),
  `SPYSIM?L=3&E=0.91&SP=0.30` (UPRO), `QQQSIM?L=3&E=0.84&SP=0.30` (TQQQ). `QQQSIM`
  exists (Nasdaq-100 → 1986); `VIXSIM` → 1990 (usually the limiting ticker for VIX-gated
  strats); `TLTSIM` → 1962. Check `result.limiting_ticker` to see what bounds the window.

`/api/tactical` returns `stats[]` (one row per allocation + `Benchmark (<ticker>)` +
the named strategy row, with `cagr, max_drawdown, max_drawdown_peak_date, sharpe,
sortino, calmar, std, ...`) and `allocation_stats[]` (`switches`, `switches_per_year`,
`percent` time-in-sleeve, per-sleeve cagr).

## RANKED allocations — cross-sectional momentum (field-verified 2026-07-31)

Allocations are not limited to fixed baskets. `allocation.kind` is `'FIXED'` or
`'RANKED'`; a RANKED allocation sorts a universe by a metric each period and holds the
top/bottom N. This is what makes dual-momentum rotations (HAA, DAA, VAA, Keller-family)
expressible without enumerating combinations.

```python
alloc.update({
  "kind": "RANKED",
  "tickers": [],                                  # ignored when RANKED
  "rank_universe_tickers": ["SPY","IWM","VEA"],    # PLAIN STRINGS, not {ticker,percent}
  "rank_metric": "TOTAL_RETURN",
  "rank_selection": "TOP",
  "rank_lookbacks": [21, 63, 126, 252],           # TRADING DAYS; validator rejects < 2
  "rank_lookback_aggregation": "EQUAL",           # EQUAL -> unweighted mean of the lookbacks
  "rank_lookback_weights": [],                    # only for WEIGHTED_MEAN
  "rank_top_n": 4,
  "rank_weighting": "EQUAL",
  "rank_freq": "Monthly",
  "rank_offset": 0,
  "rank_threshold_comparison": ">",               # only '>' or '<'
  "rank_threshold_value": 0.0,                    # drop selected assets failing the test
  "rank_fallback_ticker": "BIL",                  # single string, not a list
  "rank_threshold_fallback_mode": "FILL_EMPTY_SLOTS",
  "rebalance_freq": "Monthly",
})
```

Enums (all discovered from 422 `detail[]`, which names the allowed literals):

- `kind`: `FIXED`, `RANKED`
- `rank_metric`: `TOTAL_RETURN`, `RSI`, `PRICE_OVER_SMA`, `VOLATILITY`
- `rank_selection`: `TOP`, `BOTTOM`
- `rank_lookback_aggregation`: `EQUAL`, `WEIGHTED_MEAN`
- `rank_threshold_comparison`: `>`, `<`
- `rank_threshold_fallback_mode`: `ALL_OR_NOTHING`, `FILL_EMPTY_SLOTS`
- `rank_weighting`: `EQUAL`, `LINEAR_RANK`, `INVERSE_RANK`, `SCORE_TILT`, `INVERSE_VOL`,
  `INVERSE_VAR`, `RISK_PARITY`
- `rank_freq`: same cadence enum as `trading_freq`, plus `None`

`FILL_EMPTY_SLOTS` replaces each individually-failing slot with `rank_fallback_ticker`;
`ALL_OR_NOTHING` drops the whole allocation if the threshold fails. The response adds
`ranked_holdings[]` — one row per date per allocation with `{ticker, weight,
actual_weight, score}` plus `evaluation` / `rebalance` / `allocation_active` flags. That
array is the ground truth for auditing what the ranker actually chose, and
`allocation_active` is how to recover the active-sleeve timeline.

Gotcha: `rank_universe_tickers` takes **bare ticker strings**. Passing the
`{"ticker":…, "percent":…}` row shape used by `tickers` fails with a misleading
`Invalid ticker {'TICKER': 'DBC', 'PERCENT': 0}`.

## derived_signals and aggregate_derived_signals

Two signal families beyond the pairwise `signals[]`. Both take
`{name, expr, comparison, threshold}` where `comparison` is `>`/`<`/`=`.

**`derived_signals`** — arithmetic on two indicators. `expr` is a `SignalExpr`:

```python
{"name": "SPREAD",
 "expr": {"name": "SPREAD",
          "left":  {"ticker":"TLT","ticker_2":None,"type":"Return","value":None,
                    "lookback":252,"delay":1},
          "op": "SUB",                       # DIV, MUL, ADD, SUB
          "right": {"ticker":"IEF", ...}},
 "comparison": ">", "threshold": 0}
```

Binary only — `left`/`right` are Indicators, not nested expressions, so you cannot build
arbitrary trees here. `op`/`right` are optional (a bare `left` is a valid single-term expr).

**`aggregate_derived_signals`** — combines **1 to 4** indicators. `expr.left` is an
`AggregateIndicatorExpr`, which is where multi-lookback momentum scores live:

```python
{"name": "TIP_13612U",
 "expr": {"name": "TIP_13612U",
          "left": {"indicators": [ind("TIP","Return",21), ind("TIP","Return",63),
                                  ind("TIP","Return",126), ind("TIP","Return",252)],
                   "aggregation": "MEAN"}},   # MEAN, WEIGHTED_MEAN, MAX, MIN
 "comparison": ">", "threshold": 0}
```

`weights` accompanies `WEIGHTED_MEAN`. More than 4 indicators → `Value error, Aggregate
indicators must contain between 1 and 4 indicators`.

Reference these from an allocation by `name` in `signals`, exactly like plain signals.
`signal_display_order` uses a prefixed form:
`"aggregate_derived_signal:0:<name>"` / `"derived_signal:0:<name>"` /
`"signal:0:<name>"`.

## Reading errors, and rate limits

- **422** → Pydantic validation. Message is in `resp["detail"]`, a list of
  `{loc, msg, input}`. Self-documenting: send a junk enum value to have the API list the
  allowed literals. This is the fastest way to discover any field's domain.
- **400** → semantic failure *after* validation. The body is a full (empty) result object
  and the message is in **`result["errors"]`**, a list of strings — *not* in `detail`.
  Easy to miss; a `400` looks like a successful-shaped response.
- **429** → rate limited, returned with a null body. Sustained probing trips this within
  roughly a dozen rapid calls; ~5–8s between requests is comfortable. Batch ticker
  existence/history checks into one multi-ticker allocation and read `limiting_ticker`
  rather than one request per ticker.
- **`curl: (56)` / HTTP/2 connection reset on `/api/backtest`** → retry the same
  read-only request with `--http1.1` and a normal browser user-agent, for example
  `-H 'User-Agent: Mozilla/5.0'`. This has restored otherwise-identical requests that
  continued to fail after ordinary exponential-backoff retries. It is a transport
  workaround, not an authentication bypass; private aliases still need the in-page
  bearer-token flow above.
- There is **no** `/openapi.json` or `/docs` — the 422 probe loop is the schema reference.

## Ticker history bounds worth knowing

Checked 2026-07-31. `VNQSIM`, `EEMSIM`, `DBCSIM` **do not exist** — those sleeves are
real-ETF-only, which bounds any commodity/REIT rotation at ~2004–2007.

| real | start | sim | start |
|---|---|---|---|
| SPY | 1993-01-29 | SPYSIM | 1885-03-20 |
| IWM | 2000-05-26 | IWMSIM | 1978-12-29 |
| VEA | 2007-07-26 | VEASIM / EFASIM | 1969-12-31 |
| VWO | 2005-03-10 | VWOSIM | 1994-05-04 |
| EFA | 2001-08-17 | | |
| EEM | 2003-04-14 | — | — |
| VNQ | 2004-09-29 | — | — |
| TIP | 2003-12-05 | TIPSIM | 2000-06-29 |

A full real-ETF Keller-style universe (SPY/IWM/VEA/VWO/VNQ/DBC/IEF/TLT) starts
**2007-07-26**, limited by VEA; adding BIL moves the defensive leg to 2007-05-30.

## Tactical review checklist

1. Load the share link and replay it through `/api/tactical`.
2. Confirm the active signal from allocation `signals`, not from the run name.
3. Record headline strategy stats plus the risk-on and risk-off sleeve rows.
4. Record switching behavior from `allocation_stats`; high CAGR with too many switches may not be executable in a small account.
5. Stress the promising candidate across relevant signal windows, risk-off sleeves, trading costs, and synthetic LETF financing spread.
6. Keep canonical strategy docs separate from pending candidates until Rob explicitly locks a new sleeve.
