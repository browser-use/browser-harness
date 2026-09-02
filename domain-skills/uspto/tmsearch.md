# USPTO Trademark Search (tmsearch.uspto.gov) — wordmark screening

Field-tested on 2026-09-02, 41 wordmark queries in one local Chrome session, no CAPTCHA. TESS is gone; this is the Angular replacement.

## Why the browser is required

The app sits behind an AWS WAF challenge (`challenge.js`) and the static host answers `405` to direct API calls, so plain HTTP cannot query it. Drive the UI.

## Query flow

- Entry: `https://tmsearch.uspto.gov/search/search-information`. The results URL is stateless (`/search/search-results`), so you cannot deep-link a query; type it every time.
- Input: the only text input with placeholder `Search for marks that contain a specific word`. Focus it via `js`, then `type_text(q)` and `press_key("Enter")`.
- Ready signal: poll `document.body.innerText` for `r'\d+ results? for'` (about 3–8 s). Wordmark search is a **contains** search: `millwright` returns `HOTEL MILLWRIGHT`, `MD MILLWRIGHT DESIGN`, etc.

## Reading results from `innerText` (no DOM selectors needed)

Each card is delimited by `Check to tag for <serial>` and reads:

```
Check to tag for 88364198
Wordmark
wordmark
THE MILLWRIGHT
Status

LIVEREGISTERED          # or DEADABANDONED, DEADCANCELLED, LIVEPENDING

Goods & services
IC 011: Electric light bulbs; ...
Class
011                     # comma-separated when several: "037, 040, 042"
Serial
88364198
Owners
Fanlight Corp. (CORPORATION; CALIFORNIA, USA)
```

The status filter sidebar gives totals as `Live\nA live trademark filing is active\n<n>` and `Dead\n...\n<n>`. Up to 50 cards render per page.

## Traps

- **A single-result search skips the list and opens the detail page** (`Result 1 of 1 for <q>`), with a different layout: `Trademark\nWordmark\n<MARK>` ... `Status\nDEADABANDONED`. Parse both shapes.
- `0 results for <q>` is the empty-state text.
- Keep the wait loop tolerant: pages sometimes take >10 s under the WAF, and a stalled websocket keepalive on the harness side is the usual cause of mid-batch failures (see the daemon keepalive fix).

## Screening heuristic used

Classes 41 (education/training), 42 (software/consulting), 35 (business services), 9 (software) as "the category" for a consultancy or SaaS. Exact live mark in the category = conflict; live composite mark in the category or exact mark in an adjacent class = caution; live marks only elsewhere = clear-with-note. A signal, not clearance.
