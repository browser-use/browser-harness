# Google Trends + Glimpse — Scraping & Trend Extraction

Two layers on `trends.google.com`: **raw Google Trends** (relative 0-100 index — Google's real data) and the **Glimpse** browser extension (paid) which overlays *modeled absolute monthly volume*, YoY growth, related-with-growth, breakout discovery, alerts, and CSV export. If Glimpse is installed in the connected Chrome, its data renders automatically — no separate site.

## URL patterns (explore)

- Single term: `https://trends.google.com/trends/explore?date=today%205-y&geo=US&q=<urlenc>`
- Compare (≤5 terms, one normalized axis): `...&q=term1,term2,term3` (comma-separated, each URL-encoded)
- Time window via `date=`: `today%205-y` (5y), `today%2012-m` (12mo), **`all`** (2004→present — best for structural breaks), `now%207-d`, or custom `YYYY-MM-DD%20YYYY-MM-DD`
- Geo via `geo=`: `US`, `GB`, … ; **omit `geo` entirely for Worldwide**
- Property: `&gprop=youtube|news|images|froogle`; category: `&cat=<id>`

## Glimpse overlay — detect & time it

- When Glimpse injects, the **tab title gains a " - Glimpse" suffix** — cheap "is it active?" check via `page_info()["title"]`.
- Glimpse fetches its volume model *after* the Trends chart paints. `wait_for_load()` is NOT enough — add `wait(5)`–`wait(7)`, or poll until the volume text appears.

## Extraction (single term, from innerText)

```python
EXTRACT = r'''
const out={};
let txt=document.body.innerText.replace(/[−–—]/g,'-');           // normalize unicode minus FIRST
let m=txt.match(/([\d.]+\s*[KMB])\s+searches past month/i);
out.volume=m?m[1].replace(/\s+/g,''):(/Undetermined volume/i.test(txt)?'undet':null);
m=txt.match(/(-?\d+(?:\.\d+)?)%\s*past year/i); out.yoy=m?(m[1]+'%'):null;  // -? captures DOWN terms
out.dir=null;
if(out.yoy){ out.dir=out.yoy.startsWith('-')?'down':'up';
  const leaf=[...document.querySelectorAll('*')].find(e=>e.children.length===0 && e.textContent.trim().replace('−','-')===out.yoy);
  if(leaf){const c=getComputedStyle(leaf).color;const mm=c.match(/\d+/g);
    if(mm){const r=+mm[0],g=+mm[1];out.color=(r>g+15)?'red':(g>r+15)?'green':'gray';}}}
return out;
'''
data = js(EXTRACT)   # -> {volume:'44K', yoy:'50%', dir:'up', color:'green'}
```

- Poll: loop `wait(1.2); js(EXTRACT)` up to ~12× until `volume` or `yoy` is non-null.
- **Direction = sign AND color.** Green `rgb(118,191,80)` = up, red = down. The percent is rendered *unsigned* in some views, so the unicode-minus normalization + color check are BOTH needed — a naive `\d+%` silently misreads down-terms as up.
- Low-volume terms render **"Undetermined volume"** (no absolute estimate) but still show a YoY trajectory; down-terms frequently have no absolute volume at all.

## Glimpse features worth scripting

- **People Also Search**: related queries sortable by Search Volume, each with a growth bar — rising-related discovery for a seed term (channel switch: Google / YouTube / Amazon).
- **Discover Trends** (top nav): category → drill-down table *Keyword / Graph-5Y / Growth-YoY / Search Volume*, paginated, + **Download CSV**. Surfaces breakout terms you didn't guess. Click a category by matching its row text+count; results **lazy-load (~9s)** — wait before reading innerText. Row text parses as repeating `keyword \n "Get Alerts" \n "N%"`.
- **Get Alerts**: one click opens a "Tracking" popover with **Auto pre-checked + ✓ Saved** — i.e. one click == a saved auto-alert on significant movement. The "Saved" text lags ~1-2s; verify via the button flipping to "✓ Tracking", not an immediate innerText check.
- **Export Data**: CSV of the monthly series (highest fidelity; needs download handling).

## Traps

- **Glimpse absolute volume is a MODEL, not ground truth** — independent verification rates its absolute-volume accuracy as unreliable. Trust *relative shape, direction, head-to-head*; treat absolute numbers as rough.
- **Raw Trends is a relative 0-100 index** (each point ÷ the term's own peak) — never absolute. **Compare mode normalizes ALL terms to the single highest peak**, so a high-volume term visually crushes low-volume ones — only compare terms of similar magnitude.
- **Reuse one controlled tab + loop `goto_url`** (Page.navigate forces a fresh load and re-triggers Glimpse) rather than `new_tab` per query — no tab clutter, never touches the user's tabs.
- The chart is **not recharts and exposes no JSON / `__react*` props** — the monthly series isn't cleanly in the DOM (SVG path only). For exact numbers use Export Data CSV; for shape, screenshot.
- The Glimpse nav's **"Discover Trends" / "Tracking Dashboard" are overlays**, not URL routes — click the nav `div` by exact text; "Tracking Dashboard" can be finicky to trigger.
