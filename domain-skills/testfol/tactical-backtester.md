# testfol.io — Portfolio & Tactical Allocation Backtester

`https://testfol.io` — free/Pro portfolio backtester with deep synthetic history (S&P to ~1885). Two tools:

- `https://testfol.io/` — **main backtester**: static / fixed-weight portfolios. Where synthetic-LETF ticker params live.
- `https://testfol.io/tactical` — **tactical tool**: signal-driven switching (timing overlays, 200-SMA, regime rotation).
- `https://testfol.io/tactical?s=<id>` and `https://testfol.io/?s=<id>` — **share links**: load a saved config and **auto-render results**. Best path for read-only analysis.

**Stack:** Vue 3 + **Quasar** SPA. Config is NOT in the URL (localStorage holds only theme). Guides/help pages are client-rendered — raw `http_get` returns an empty shell; read `document.body.innerText` in the browser instead.

---

## Fastest workflow: share links, not rebuilding

Building the tactical UI by automation is slow and fragile (see traps). If the user can build + share a `?s=` link, just load it and scrape the table:

```python
new_tab("https://testfol.io/tactical?s=dB66NgTK9AF")
wait_for_load(); wait(3)               # Vue hydrates the saved config ~3s after load
# share links auto-run, but a fresh BACKTEST click is safe (see two-button trap)
stats = js(r"""(()=>{for(const t of document.querySelectorAll('table')){
  const h=[...t.querySelectorAll('thead th')].map(c=>c.innerText.trim());
  if(/CAGR|Sharpe/.test(h.join('|'))){
    const rows=[...t.querySelectorAll('tbody tr')].map(r=>[...r.querySelectorAll('th,td')].map(c=>c.innerText.trim()));
    return JSON.stringify({head:h, rows});}}})()""")
```

Results tables also have CSV export buttons: `Statistics-Table`, `Annual-Returns-Table`, `Metrics-Table-All`, `Data-Table`.

---

## Synthetic LETF ticker params (main backtester)

Format: `TICKER?L=<lev>&E=<expense>&SW=<swap>&SP=<spread over FFR>`

| Param | Meaning | Notes |
|---|---|---|
| `L` | daily-reset leverage | `L=3` → 3× |
| `E` | extra annual expense drag % | If omitted, auto-adds **0.5%/yr per leverage point above 1×** (so `L=3` ≈ 1.0% built-in), 0.333% per point of negative leverage |
| `SW` | swap exposure per unit leverage | calibrated from real LETF holdings; rarely changed |
| `SP` | financing spread over Fed Funds | **the borrowing-cost assumption — huge in high-rate regimes** |

Base on the **total-return** index series so dividends are included:
```
SPYTR?L=3&E=1.0   ≈ UPRO (3× S&P)
SPYTR?L=2&E=0.9   ≈ SSO  (2× S&P)
QQQTR?L=3&E=0.95  ≈ TQQQ (3× Nasdaq-100)
```
Parametrized tickers are typed literally; the autocomplete will NOT offer an option for them (see ticker-commit trap).

## `*SIM` preset tickers — long synthetic history

Autocomplete shows these as `… Preset: Simulated …`. Use them to extend a backtest before a real fund existed:
```
SPYSIM   S&P 500 (default benchmark)
GLDSIM   gold        IEFSIM  7-10y Treasuries
KMLMSIM  managed futures (Mt Lucas / KraneShares — longest MF history, ~1990s)
DBMFSIM  managed futures (iMGP DBi)
```
**Window auto-clips to the LATEST inception among all tickers in the run.** e.g. adding real `AQMIX` (2010) or `PSLDX` (2007) forces the whole backtest to start there. Swap in `*SIM` tickers to push the start date back through 2008 / 2000-02.

---

## Tactical tool — model semantics

- **Top "Trading Frequency"** = how often signals are evaluated and the strategy can SWITCH allocations (Daily / Monthly / …). This is the real cadence lever.
- **Per-allocation "Rebalance"** = internal rebalancing of that allocation's holdings only. For a single-100%-ticker leg it's a near no-op. *Do not* mistake it for the switch cadence — a "Monthly" allocation rebalance under a "Daily" top frequency still switches daily.
- **Allocations are evaluated left→right; first matching clause wins.** Put the broad **fallback** (a clause with "No conditions") as the **rightmost** allocation; put conditional regimes (e.g. `Invest if: SignalA`) to the left.
- **Signal block:** the ticker fields appear only *after* you pick an indicator (Price / SMA / EMA / …). `Use total return` defaults **ON** — uncheck it for a textbook price-based SMA. `Delay` (Pro) adds per-indicator "Delay days" = execution lag (set 1 to avoid same-bar look-ahead).
- A 200-SMA trend filter reads: `SPYTR Price  >  SPYTR 200-day SMA`.
- **Pro-gated:** SAVE STRATEGY, LOAD SAVED, cashflow legs, `Delay`, `Drag`.

Stats table rows: each allocation standalone (`RISK-ON`/`RISK-OFF` = "always in that leg"), `Benchmark` (defaults to `SPYSIM`), and the **named strategy row** (your actual tactical result).

---

## Automation traps (hard-won — read before driving the UI)

1. **Ticker inputs are Quasar autocomplete; programmatic `.value` does NOT commit.** Setting value + dispatching `input`/`change` updates the DOM but Vue clears it on the next render → the ticker silently reverts to empty and the backtest runs the OLD model. **Commit pattern:** click field → `type_text(sym)` → `wait(1.3)` → click the first `.q-menu [role=option]`. For parametrized tickers (`SPYTR?L=2`) there's no option to click — type then `press_key("Escape")` to keep the raw text.

   ```python
   def set_ticker(field_xy, sym):
       click(*field_xy); wait(0.3); type_text(sym); wait(1.3)
       opt = js(r"""(()=>{const o=document.querySelector('.q-menu [role=option]');
         if(!o)return''; const r=o.getBoundingClientRect();
         return JSON.stringify([Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)]);})()""")
       if opt: import json; c=json.loads(opt); click(c[0],c[1]); wait(0.5)
   ```

2. **Number/weight inputs:** native setter is also unreliable. Use **triple-click to select** (`click(x,y,clicks=3)`) then `type_text(...)` then `press_key("Tab")`.

3. **There are TWO "BACKTEST" buttons; only the SECOND recomputes.** Filter buttons by text `BACKTEST` and click index `[1]` (the one at the bottom of the Parameters block). The first does nothing visible — you'll read a stale/cached table and think your edits didn't take.

4. **Don't retype a row that already holds the target ticker.** Share-link bases come with row 0 pre-filled (`SSO`/`CASHX`). Clicking+typing into it appends/garbles (`SSO`→`SOSO`) → nonsense results (e.g. 4,000% volatility = corrupted ticker). Set only its weight; type tickers only into rows you ADD.

5. **Card-finding:** climb the DOM from the `input[aria-label="Allocation N"]` until an ancestor contains `input[placeholder="Ticker"]` — don't stop at the first multi-input container (it's too high and lacks the ticker rows).
   ```js
   let c=nameInput; for(let k=0;k<10;k++){ if(c.querySelector?.('input[placeholder="Ticker"]')) break; c=c.parentElement; }
   ```

6. **Waits:** ~3s after share-link / goto for Vue hydration; ~1.3s for the autocomplete menu; ~5-6s after a BACKTEST click before scraping.

7. **Exec scope:** if running multi-step builds via the harness, wrap all helper functions inside ONE outer function (closures). Top-level `def`s in an exec'd snippet can't see each other's names (they resolve `__globals__`, which only holds the pre-imported `js`/`click`/etc.).

8. **Autocomplete lists the `*SIM` preset FIRST.** Typing `DBMF` and clicking option `[0]` selects `DBMFSIM` (the long-history sim), not the real `DBMF` ETF — same for `KMLM`, `GLD`, `IEF`, `VT`, `RSSB`. If you want the REAL fund (short live history), click the option whose text exactly equals the symbol (usually `[1]`), not `[0]`. If you want long history, `[0]` (the SIM) is what you want. The run's clipped Start Date / benchmark CAGR tells you which window you actually got.

---

## Trap summary
- Two BACKTEST buttons → use the **second**.
- Tickers commit only via **type + click autocomplete option**, never `.value`.
- Window **clips to the latest ticker inception** — use `*SIM` presets for long history.
- Top **Trading Frequency** is the switch cadence; allocation Rebalance is not.
- `Use total return` defaults ON; uncheck for price-based SMA.
