# seats.aero

Award space aggregator across many frequent flyer programs (Aeroplan, Velocity, Qantas, Flying Blue, Qatar, United, AA, Alaska, Turkish, etc.). Free tier shows current snapshot; PRO ($9.99/mo) unlocks full year + alerts + PRO filters.

## Search URL params (no login required)

```
https://seats.aero/search
  ?min_seats=1
  &applicable_cabin=any|economy|premium|business|first
  &additional_days=true
  &additional_days_num=3        # ± days around date (0-7)
  &max_fees=40000               # AUD cents — 40000 = A$400 fees cap
  &disable_live_filtering=false
  &date=2026-07-08              # center date YYYY-MM-DD
  &origins=ANZ,SYD,PER          # region codes OR airport IATA
  &destinations=EUR,OSL,ARN,LHR # mix region codes + IATA
```

URL-driven search is by far the most reliable way to call this site — no form-filling.

### Region codes

- `ANZ` — Australia + New Zealand
- `EUR` — Europe
- `ASA` — Asia
- `USA` — United States
- `LON` — London
- Many more — explore via Routes menu

### Default param values seen in the wild

`min_seats=1&applicable_cabin=any&additional_days=true&additional_days_num=3&max_fees=40000&disable_live_filtering=false`

## Table columns

`Date | Last Seen | Program | Departs | Arrives | Economy | Premium | Business | First`

Each cabin cell either shows points (`182,900 pts`) or `Not Available`. A row may have *some* cabins available and others not — filter on the specific cabin column.

## Quirks

- **Pagination is broken / cached**: clicking the `›` next link often returns to the same data set. Trust what's shown after the initial search; if you need more dates, change the URL `additional_days_num` parameter and reload.
- The bottom-of-page filter chips (`Programs`, `Alliances`, `Transfer Partners`, `Points`, `Days`) are PRO-only — don't waste time clicking them logged out.
- "Last Seen" can be "Just now" / "1 hour ago" / "1 day ago" — for booking decisions, only trust rows under ~6h old. Older = high re-verification risk.
- The 25-per-page default truncates aggressive searches. Bump to 100 via the per-page select.

## Useful starter searches for Australia → Europe

```
# All Northern European hubs in business, ±4 days from Jul 8 2026
https://seats.aero/search?min_seats=1&applicable_cabin=business&additional_days=true&additional_days_num=4&max_fees=40000&date=2026-07-08&origins=ANZ&destinations=EUR

# Specific origin-pair: PER → AMS or OSL or CPH
https://seats.aero/search?...&origins=PER&destinations=AMS,OSL,CPH

# Region-to-region: Australia → All Europe
https://seats.aero/search?...&origins=ANZ&destinations=EUR
```

## What "Velocity" rows actually mean

Velocity rows on seats.aero typically surface Singapore Airlines KrisFlyer space (via Velocity-KrisFlyer transfer) or direct Velocity-bookable partner space. Always confirm at velocityfrequentflyer.com before transferring points.

## What "Qantas" rows mean

Qantas Classic Rewards on Qantas/oneworld partners + Emirates. Bookable at qantas.com.au with Qantas Frequent Flyer points.

## Live refresh

There's a small refresh icon on each row that queries the source program in real time. Use before transferring points or burning miles — the cached row is a snapshot.
