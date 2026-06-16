# The Tech Geeks AU — Ubiquiti pricing

`https://thetechgeeks.com` — Shopify Online Store 2.0, AU Ubiquiti reseller. Prices GST-inclusive ("All Prices Include Australian GST At 10%" in footer).

## Do this first

**Hit the `.js` endpoint, not the DOM.** Shopify exposes canonical product JSON — no scraping, no screenshots.

```python
import json
d = json.loads(http_get(f"https://thetechgeeks.com/products/{handle}.js"))
# {'title', 'price' (AUD cents — divide by 100), 'available', 'variants', 'compare_at_price', ...}
```

Use this for title / SKU / price. One `http_get` replaces `goto + wait_for_load + screenshot + regex`.

## Do NOT trust `.js.available` for stock

Tech Geeks marks many in-stock products `available: false` (backorder / order-from-supplier). Verified counterexample: UDM-Pro-Max `available: true`, U6-LR `available: false` but Add-to-cart live. To know real stock, cross-check the DOM:

- `document.querySelector('.price--sold-out')` present → truly sold out
- Body text contains "Sold out" (case-insensitive) near the product title → sold out
- `document.querySelector('product-form__submit[disabled]')` → sold out

Only if `.js.available = false` AND one of the above fires is the product actually unbuyable.

## Sold-out pages have junk prices

Confirmed: UACC-Rack-12U-Wall listed **$3,080 AUD** (real AU street ~$420–$630). The sold-out listing carries stale / data-entry prices that nobody cleans up.

**Sanity gate before reporting any Tech Geeks price:**

1. If `.js.available = false`, treat the price as unverified.
2. If the price deviates >2× from another AU vendor or the `store.ui.com` MSRP for the same SKU, assume Tech Geeks is wrong — not the other source.
3. Only in-stock prices should land in a final table.

## Finding the right product URL

Slugs are long marketing titles, not SKUs. Don't guess. Two reliable shortcuts:

- `https://thetechgeeks.com/search?q=<SKU>` → scrape first `a[href*="/products/"]` link
- Google `site:thetechgeeks.com <SKU>` when the internal search misses

## Known gaps in their Ubiquiti catalogue (as of 2026-04)

- **USP-PDU-Pro** — not stocked (no AU-plug Ubiquiti SKU exists anywhere in AU; region-wide gap, not a Tech Geeks issue)
- **U-Cable-C6-CMP** (plenum Cat6) — only **U-Cable-C6-CMR** (riser) is carried
- `available: false` is common even on items they'll still order in

## Don't use a browser for this

Product pages are static HTML + one JSON endpoint. `http_get` over `asyncio`/`ThreadPoolExecutor` fetches all SKUs in <5s. CDP is wasted here unless you need to click through a cart / checkout flow.
