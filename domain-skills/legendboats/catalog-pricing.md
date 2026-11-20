# Legend Boats catalogue and pricing

`https://www.legendboats.com/` is a WordPress catalogue with a separate Next.js builder at `https://build.legendboats.com/`. Public model years, prices, packages, and promotions are volatile; fetch them live and preserve the exact URL and retrieval time.

## Discover active series from the main menu

Do not treat every series link as current. The same menu contains active families and clearance/retired series.

- In the `data-menu="boats"` menu, active family/fishing and Uttern cards are in tab `0` and tab `1`; tab `2` is clearance.
- In the `data-menu="pontoons"` menu, tab `0` is active and tab `1` is clearance.
- Each `a.s-mega-menu__card` exposes the series URL, model year, title, starting-price display, and weekly display.

Use a real HTML parser that tracks ancestor `data-menu` and `data-tab` values. Treat HTML void elements such as `img` and `source` correctly; naively pushing them onto an element stack causes the first card (currently Pulse) to disappear.

## Standard series and model pages

Most series pages expose one `<article class="card">` per model:

- `.card_year`
- `a.card_name`
- `.card_vitals_standards`
- `.card_vitals_retail`
- `.card_vitals_weekly`
- paired `.card_specs_name` and `.card_specs_detail`
- an optional `buildbuy.legendboats.com/builder?sku=...` link

Exact model pages expose:

- `.modelYear`, `.modelName`, and `.vitals_includes`
- the Ontario All-In base price and weekly display
- each motor as `figure.motor[data-name][data-retail][data-weekly]`

`data-retail` on a motor is the total package price with that motor, not the upgrade delta. Compute the delta as `motor total - base package` if needed.

## Builder fallback

Some active series do not use standard model cards. The XT landing page is a redesigned marketing page, and the public Uttern menu link has returned 404 while the series remains in the active menu. Fall back to Legend's official builder rather than guessing or using an old price table.

The builder's server-rendered HTML contains Next.js RSC payloads in `self.__next_f.push(...)`. Decode each JSON push payload, then extract balanced JSON product objects. Relevant fields include:

- `Make == "Legend"`
- `PublicName`, `ProductNameEN`, `ModelYear`, and `Series`
- `LegendSKU`, `RetailPrice`, and `WeeklyPrice`
- `FeaturedInBoatBuilder` and `IsAvailableForBoatBuilder`
- `StandardMotorId` and `StandardTrailerId`

Filter records to the model year shown in the active main-menu card and to `FeaturedInBoatBuilder == true`. Colour variants share a public model name; deduplicate by `(Series, PublicName, ModelYear)`, preferring an available variant. Use `RetailPrice` for the current base display. Do not interpret a zero `RetailSpecialPrice` plus a full-price `Savings` value as a free boat; those fields are not reliable enough to apply a promotion automatically.

## Reliability traps

- `/boat-model-sitemap.xml` has intermittently returned WordPress critical errors or HTTP 500; do not make it the only discovery path.
- The menu can link to a currently broken series route. A verified builder record is an acceptable official fallback.
- Cache-bust every live verification and reject short/error pages.
- The public footer says price, rate, specification, equipment, and model details may change without notice and that final details are available at purchase.
- Ontario All-In pricing is completed by adding taxes, but in-stock displays and ordered-product pricing can differ or receive surcharges.
- Promotions require their own date and eligibility verification; never infer one from `RetailSpecialPrice` alone.

For quoting, fail closed if neither the exact live model page nor an official current builder record can be verified.
