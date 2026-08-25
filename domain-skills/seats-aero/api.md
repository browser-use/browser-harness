# seats.aero API (PRO)

PRO tier ($9.99/mo) unlocks the partner API. Up to 1,000 calls/calendar day. No commercial use without permission.

## Auth

```
Partner-Authorization: <API_KEY>
```

Generate at https://seats.aero/account.

### Josh's PRO key

`pro_3Dh9xl5hdNqguRqLQqQl7Fb0tCb` — paid PRO account, 1,000 calls/day. Verify it's still valid before heavy use (keys rotate). Do not share publicly or commit to public repos.

## Key endpoint: cached search

```bash
curl -s 'https://seats.aero/partnerapi/search?origin_airport=BCN&destination_airport=SYD&start_date=2026-08-01&end_date=2026-08-10&cabin=business&take=200' \
  -H 'Partner-Authorization: <KEY>' -H 'accept: application/json'
```

### Required-ish params

- `origin_airport` — single IATA (comma-separated does NOT work — returns 0; do one per request and parallelize)
- `destination_airport` — single IATA
- `start_date` / `end_date` — `YYYY-MM-DD`
- `cabin` — exactly one of `economy` / `premium` / `business` / `first` (NOT plural, NOT a list)

### Optional

- `take` — page size (default ~25, accepts up to 1000)
- `order_by` — typically `lowest_mileage` or `date`
- `disable_live_filtering` — passes through cached only
- `sources` — `qatar,velocity,delta,...` to limit programs

### Region params don't work

`origin_region=Europe`, `destination_region=Oceania`, `origin_region=EUR` all returned 0 in testing despite the response data containing `Route.OriginRegion: "Europe"`. Use individual airport queries and parallelize with `&`.

## Response shape

```json
{
  "data": [
    {
      "ID": "...",
      "Date": "2026-08-04",
      "Route": {
        "OriginAirport": "LHR",
        "DestinationAirport": "SYD",
        "OriginRegion": "Europe",
        "DestinationRegion": "Oceania",
        "Distance": 10587,
        "Source": "flyingblue"
      },
      "Source": "flyingblue",
      "YAvailable": true, "WAvailable": false, "JAvailable": true, "FAvailable": false,
      "YMileageCostRaw": 63000, "JMileageCostRaw": 126500,
      "YTotalTaxesRaw": 53920, "JTotalTaxesRaw": 101920,    // USD cents — divide by 100
      "TaxesCurrency": "USD",
      "YRemainingSeatsRaw": 1, "JRemainingSeatsRaw": 1,
      "YAirlines": "VN", "JAirlines": "VN",                  // operating airline IATA
      "YDirect": false, "JDirect": false,                    // is this a non-stop?
      "CreatedAt": "2025-08-11T...", "UpdatedAt": "2026-05-11T..."
    }
  ],
  "count": 46,
  "hasMore": false,
  "cursor": 1778723931
}
```

### Cabin prefix legend

- `Y` — economy
- `W` — premium economy
- `J` — business
- `F` — first

Each cabin has parallel fields: `{X}MileageCostRaw`, `{X}TotalTaxesRaw`, `{X}RemainingSeatsRaw`, `{X}Airlines`, `{X}Available`, `{X}Direct`.

### Tax field is USD cents

`JTotalTaxesRaw: 101920` = $1,019.20 USD. Convert: `raw / 100`. Multiply by ~1.51 for AUD as of mid-2026.

### "Source" = which program books it

`qatar` = Qatar Privilege Club (Avios). `velocity` = Virgin Australia Velocity. `qantas` = Qantas Frequent Flyer (Classic Rewards). `flyingblue` = Air France/KLM. `delta` = Delta SkyMiles. `american` = AAdvantage. `united` = MileagePlus. `aeroplan` = Air Canada. `alaska` = Mileage Plan. `turkish` = Miles&Smiles. Etc.

The same physical flight (e.g. LHR-CDG-HAN-SYD on Vietnam Airlines) can appear from *multiple* sources (Delta + Flying Blue both partner with VN, and seats.aero shows both with different mileage prices).

### "Airlines" is comma-separated IATA codes for the trip

`"JAirlines": "QR, VA"` = Qatar Airways + Virgin Australia codeshare (the typical DOH-SYD partner combo). `"VN"` = Vietnam Airlines only. `"EK"` = Emirates only.

## Common queries

### Cheapest economy: Europe → SYD over 2 weeks

```bash
for orig in BCN MAD AGP VLC LIS AMS LHR CDG FRA BRU; do
  curl -s "https://seats.aero/partnerapi/search?origin_airport=${orig}&destination_airport=SYD&start_date=2026-07-28&end_date=2026-08-10&cabin=economy&take=200" \
    -H "Partner-Authorization: $KEY" > "/tmp/seats/${orig}_econ.json" &
done; wait
```

### Business class hunting from any EU hub

Same shape but `cabin=business`. Expect very sparse results — most EU→AUS biz reward space comes from a handful of cached routes (mostly LHR, ZRH, IST).

### Sample known patterns (Jul 2026)

- **Qatar (qatar source) BCN/CDG/LHR → SYD economy**: 54k–90k pts, $0 fees (Qatar doesn't pass through YQ on awards via Privilege Club). 9 seats typical, very generous.
- **Delta → Vietnam Airlines LHR-SYD biz**: 90k SkyMiles + ~$327 fees. 1 seat. Outstanding deal if you can grab it.
- **Qantas → Emirates ZRH/FRA → SYD biz**: ~183k QFF pts + ~$1,000 fees. Emirates has high YQ.
- **Aeroplan partner LHR-SYD biz**: 485k pts + ~$609 fees. Lots of seats (6–9) but expensive in points.
- **Velocity QR+VA codeshare AMS/FRA/LHR-SYD economy**: 80k pts + $443–604 fees. 2–4 seats per day, very consistent inventory.

## Rate limits

1,000 calls/day on PRO. A "fan out to 20 origins" run uses 20 calls. Cheap.

## Gotchas

- **`origin_airport` does NOT accept lists** — splits into separate requests required. The web UI looks like it accepts lists but the API doesn't.
- **`origin_region` returns 0** despite the response containing region fields.
- **`cabin` must be singular** — `business,economy` returns `invalid_cabin` error.
- **0 results for a route doesn't mean no seats exist** — only that seats.aero doesn't currently track that route in the queried programs. e.g. MAD-SYD biz returns 0 from every source, but Qatar Privilege Club genuinely has biz space on MAD-DOH-SYD that the cache doesn't surface (because it's stitched, not a single route). For stitched availability use the airline's own website.
- **Tax values in `TaxesCurrency: USD`** even though the website displays AUD. Don't trust the AUD on the web UI — pull `JTotalTaxesRaw` and convert yourself.

## When the API misses things

The API tracks **published award space** that's been ingested. It doesn't synthesize itineraries. If your routing involves a positioning leg (e.g. MAD→DOH cash + DOH→SYD on points), search the long-haul leg only and book the short leg in cash separately.
