# Google Trends (trends.google.com) — explore/compare for keyword research

Field-tested 2026-07-24. Useful for getting *relative* search-interest signal and Rising-query breakouts when you don't have Ahrefs/SEMrush access.

## `pytrends` (unofficial API) gets rate-limited fast

`pip install pytrends` works, but `related_queries()` / `interest_over_time()` frequently return `TooManyRequestsError: 429` even on a single cold call from a fresh IP — Google is aggressive about blocking the raw HTTP client's fingerprint. **Prefer driving the real trends.google.com UI via browser-harness** — a real Chrome session with normal headers/cookies does not get blocked, and you get the "Rising" breakout data pytrends struggles to fetch reliably.

## URL pattern — single term

```
https://trends.google.com/trends/explore?q=<term>&geo=US&hl=en
```

## URL pattern — compare up to 5 terms at once (this is the valuable trick)

Comma-separate terms in `q=`, no URL-encoding needed for the comma itself (spaces still need `%20` or `+`):

```
https://trends.google.com/trends/explore?date=today%2012-m&geo=US&q=term one,term two,term three,term four,term five&hl=en
```

This renders one shared "Interest over time" line chart with all terms **normalized to the same 0-100 scale** — this is the single fastest way to sanity-check relative demand between a candidate keyword cluster (e.g. is "schulte table" bigger or smaller than "reaction time test"?). Hover a point on the chart (or read the tooltip that appears) to get exact per-term index values for that week.

Below the chart, each term gets its own "Related queries" panel (Top / Rising toggle, defaults vary — some panels default to Rising, some to Top, seemingly based on data availability) and its own "Related topics" panel. Scroll down — in 5-term compare mode this is a long page (~5x the single-term page height), one section per term, in the same order as entered in `q=`.

## Rendering timing

The page is an SPA — after `new_tab()` + `wait_for_load()`, `document.body.scrollHeight` is still small (initial ~1000px shell). Sleep ~2-3s for the charts/panels to hydrate before `window.scrollTo(0, document.body.scrollHeight)` — the page grows to its full height (thousands of px in compare mode) only after data loads. Re-check `page_info()['ph']` growth as a signal that content has rendered before screenshotting.

## Reading "Rising" data — this is what actually matters for keyword research

"Rising" related queries show a `+N%` badge instead of a 0-100 bar — this is a breakout/new-demand signal, exactly what you want for finding low-competition emerging keywords. "Top" queries show a 0-100 relative-popularity bar instead (no growth signal, just current relative volume within that term's related set).

**Caveat — ambiguous/small-base terms produce noisy Rising lists.** If a seed term has very low absolute volume, Google Trends' Rising algorithm surfaces near-random breakout queries unrelated to your topic (e.g. for `attention training`, real observed Rising results included "walmart near me" and "dog training tips" — pure noise from a tiny/ambiguous base, not signal). Cross-check Rising queries against the base term's own relative interest level (from the compare chart) before trusting them — low-index terms (near 0 on the shared chart) have unreliable Related-queries panels.

## Screenshot-driven reading beats DOM scraping here

Trends' DOM uses obfuscated/generated class names with no stable selectors worth hardcoding — this page changes often. Screenshot + read is faster and more robust than trying to write a `querySelectorAll` scraper for chart tooltips or the related-queries table.
