# testfol.io — synthetic LETFs & backtester automation

Portfolio backtester for ETFs / asset allocation. Built on Quasar (Vue). Main backtester at `https://testfol.io/`, tactical/signal backtester at `https://testfol.io/tactical`.

## Synthetic leveraged tickers

Tickers accept inline params: `UNDERLYING?L=2&E=0.95&SP=0.30` (case-insensitive). The field is an autocomplete but accepts arbitrary literal text — type the string, then press **Escape** to dismiss the dropdown without selecting a suggestion.

| Param | Meaning |
|---|---|
| `L` | daily-reset leverage multiple (`L=2` → 2× daily) |
| `E` | expense ratio %/yr (flat). Default if omitted: 0.5%/yr per leverage point above 1× |
| `SP` | financing **spread** %/yr over the auto-supplied base rate (≈ Fed Funds), charged on the borrowed `(L−1)` portion |
| `SW` | swap exposure per unit leverage (rarely needed) |

### ⭐ Non-obvious: SP default is exactly 0.40%
Omitting `SP` is **not** zero — testfol bakes in a **0.40%** spread. Verified empirically: `SP=0.40` reproduces the omitted-SP backtest to the penny; `SP=0` raises the result. To model a realistic 2× LETF, **`SP≈0.30`** matches real **QLD** (ProShares 2× QQQ) over the high-rate 2022–2026 window better than the 0.40 default (real funds earn lending income, so net cost < gross spread). Calibrate by comparing a synthetic of the underlying (`qqq?l=2&e=0.95&sp=?`) against the real LETF and sweeping SP.

## Driving the UI (CDP harness)

- **Add portfolios:** click the `ADD EMPTY` button (one per portfolio). Ticker inputs have `placeholder="Ticker"`, weight inputs are `type=number` with `placeholder="0"`.
- **Run:** click the `BACKTEST` button (re-query its rect each time — page reflows after results render and the button moves).
- **Date / ticker inputs resist synthetic input.** `Input.insertText` and `Input.dispatchKeyEvent` do **not** populate the `type=date` start/end fields, and retyping into the ticker autocomplete is fragile. Use the native-setter trick so Vue's model updates:

```js
js("""(()=>{const el=document.querySelectorAll('input[type=date]')[0];
const set=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value').set;
set.call(el,'2022-01-01');
el.dispatchEvent(new Event('input',{bubbles:true}));
el.dispatchEvent(new Event('change',{bubbles:true}));el.blur();})()""")
```

Same pattern sets a ticker value (find the `input[placeholder="Ticker"]` whose `.value` starts with your underlying).

- **Results are NOT an HTML `<table>`.** They render as a div grid. Scrape by finding the smallest `div/section` whose `innerText` contains both `CAGR` and `Max Drawdown`, then split its text on `\n` / `\t`. Columns: Name, Ending Value, Total Contributions, Cumulative Return, CAGR, MWRR, Max Drawdown, … The benchmark row is labelled `Benchmark (SPYSIM)`.
- Backtest completes in <1s; a green "Backtest complete" banner appears. `wait(3)` after the click is ample.

## Traps
- The `Drag` field inside each portfolio card is a per-portfolio annual fee (tooltip: "taxes, expenses, trading costs") — separate from a ticker's `E`. Leave at 0 unless modelling account-level costs.
- testfol may auto-shorten the start date if a ticker's real data begins later than the requested start (e.g. GDE launched Jul 2022).
- Real-fund data updates 6:00 PM & 9:30 PM EST.
