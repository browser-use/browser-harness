# car-rental

Searching car rental aggregators and direct suppliers. Norway-focused but the structural notes apply broadly.

## Trap: aggregator "currency toggle" lies about the search list

**DiscoverCars** (`discovercars.com`) renders price chips in the search results as bare `$1,032.52` even when the currency selector is set to AUD. The number is **USD**. The full offer-detail page (one click into "View deal") renders the real local currency as `A$1,563.91`. Ratio is the USD/AUD spot rate (~1.51 in 2026-05).

This means search-list prices look ~33% cheaper than reality. Always:

1. Click into the actual offer page before comparing, **or**
2. Multiply list prices by current USD→AUD if you must compare from the list.

The cookie `Currency=AUD` and the visible header chip both say "AUD". The offer page is the source of truth.

Suspected cause: DiscoverCars treats `$` as a generic symbol for affiliate-network display in the list. Sub-aggregators (Kayak, etc.) likely have the same hazard — verify before trusting.

## DiscoverCars search URL shape

```
https://www.discovercars.com/search/<session-uuid>?sq=<base64-json>&searchVersion=2
```

The `sq` param is base64-encoded JSON:

```json
{"PickupLocationId":2085,"DropOffLocationId":2085,"PickupDateTime":"2026-07-12T10:00:00","DropOffDateTime":"2026-07-16T17:00:00","ResidenceCountry":"AU","DriverAge":35,"Hash":""}
```

- `PickupLocationId` 2085 = Bergen Flesland Airport (BGO). Submit the form once to discover the ID for any airport.
- The path UUID is required — bare `/search?sq=...` returns 404. Submit the homepage form once to get a session UUID, then reuse it with edited `sq` to change dates/locations.
- Editing `sq` after page load does not update the visible form — the React store keeps the previously-set times. Open the time `CustomSelect` dropdowns and re-pick to actually shift to a 5-day billing window (10:00 → 17:00 is 4d 7h, billed as 5 calendar days; 10:00 → 10:00 is 4 days flat).

### Date picker quirks

- The pickup-date display uses `.DatePickerOld-CalendarField` on results page, `.DatePicker-CalendarField` on homepage.
- The calendar widget is `react-date-range`. Day cells are `.rdrDay`; passive (other-month) cells carry `.rdrDayPassive`. Day numbers live in `.rdrDayNumber span`.
- The visible month names live in `.rdrMonthName`. The library renders two months but the underlying state can show a *third* "phantom" month name from before navigation — always filter by visible `rdrMonthName` text (e.g. `'Jul 2026'`) when picking a day.
- `.rdrDay.click()` via JS does NOT trigger the React handler. Use compositor `click(x, y)` via `getBoundingClientRect()`.
- Time selector is a `.CustomSelect` (not a native `<select>`). Open with `.CustomSelect-SelectHandler[N].click()`, then scrollIntoView the visible `.CustomSelect-SelectOption` and compositor-click it.

## Hyre.no — direct supplier, almost always cheaper than aggregators in Norway

Hyre is a Norwegian peer-keyless car-share (think Zipcar). Phone-unlock cars at airport short-stay parking. Self-service, no counter queue, free additional drivers, free cancellation up to 24hr before.

### Deep-link URL (works without form fill)

```
https://www.hyre.no/en/flesland/?fd=YYYY-MM-DD&fh=HH:mm&td=YYYY-MM-DD&th=HH:mm&hg=<vehicle-uuid>
```

- `flesland` = Bergen Airport. Other locations: `gardermoen` (Oslo OSL), `vaernes` (Trondheim TRD), city locations like `oslo-sentrum`.
- `fd/fh` = from date/hour, `td/th` = to date/hour. 24-hour time.
- `hg` = vehicle group UUID. Found by browsing without it, then copying the selected car's URL.

### Pricing format

```
NOK <base>  + N days × NOK <per-day>  =  TOTAL
e.g. NOK 2,000 + 5 × NOK 999 = NOK 6,995 for a VW ID.4 over 4d 7h
```

The flat base price is essentially a booking fee. Per-day rate varies by car. The total on the page is honest — no hidden extras unless you toggle:

- "Reduced insurance deductible" — NOK 125/day to drop deductible from NOK 12,000 → 2,000. Cannot be added after booking.
- Fuel + tolls are auto-charged via the app.
- NOK 1,000 holding deposit at booking.

### Why it beats aggregators in Norway

For a Bergen Airport 5-day VW ID.4 rental (2026-07-12 to 2026-07-16):

| Source | Total AUD | Extra-driver fee | Cancellation | Deposit |
|---|---|---|---|---|
| Hyre direct | **~A$1,015** | free | 24hr | NOK 1,000 (~A$145) |
| DiscoverCars (Alamo) | A$1,564 | typically ~A$15/day | 48hr | A$3,010 |
| Rent-a-Wreck (BYD Atto, smaller car) | A$1,650 | NOK 1,000 paid | varies | varies |

The pattern: legacy aggregators sell the brand-name suppliers (SIXT, Alamo, Avis) at airport-counter rates. Hyre/Move About/local players undercut by ~30-40% on Norwegian airport rentals specifically because they have no counter and no fleet repositioning costs.

## URL patterns for other sites

- **Kayak** (`kayak.com.au/cars`): no usable deep link found — `cars.kayak.com/cars/<location>/<dates>` 302's to `/cars` and loses params. Form-fill is required.
- **Rentalcars.com** (Booking-owned): `SearchResults.do?pickupLocation=...&pickupYear=...&pickupMonth=...&dropoffYear=...&preferredCurrency=AUD` accepts URL params but the SPA frequently 500s on direct nav. Form-fill from the homepage is more reliable.

## Verification step

When an aggregator price looks suspiciously low, click "View deal" / "Continue" to the supplier's full breakdown — that's where USD-vs-AUD and mandatory-extras get added back. Treat the offer-page total as ground truth, not the chip price.
