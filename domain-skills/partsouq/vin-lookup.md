# partsouq.com — OEM parts lookup by VIN (live EPC mirror)

Validated 2026-08-12 (Toyota/Lexus, brand-new 2026 VIN resolved perfectly).

## The one URL that matters

```
https://partsouq.com/en/search/all?q=<17-char VIN>
```

Redirects straight into the manufacturer EPC catalog for that exact vehicle
(region/year/model/modelcode, e.g. `GYU15L-BWXGBA`), with production date, color
code, trim code shown. No login needed for browsing.

## Search inside the vehicle

The vehicle page has a "Search in vehicle" box — accepts part names, 5-digit
Toyota base codes (e.g. `44250`), or callouts. Results give full part numbers
with qty + production-date applicability windows and link to the exploded
diagram (figure) pages.

## Why this beats the alternatives

- **Toyota TIS (techinfo.toyota.com) does NOT include the parts catalog** on
  standard subscriptions — `t3Portal/resources/jsp/partscatalog/index.jsp`
  just errors ("There was an error in the page you requested"). Don't chase it.
- US dealer e-commerce sites (RevolutionParts network: lexuspartsnow,
  parts.<dealer>.com) lag months behind on new models — their VIN decoders
  reject brand-new VINs ("unable to process") and new-model catalogs may list
  accessories only. They also 403 non-browser fetchers (WebFetch/curl); they
  load fine in a real browser.
- PartSouq's EPC data is near-live (had a 2026 PHV weeks after production).

## Traps

- Diagram footnote `N01` callouts = parts not supplied individually.
- Fitment differs across trims of the same model line (e.g. TX500h rack =
  44250-0E230, TX550h+ rack = 44250-0E220) — always resolve via the VIN, not
  the model name.
