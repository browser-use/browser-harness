# CivicSource — Louisiana adjudicated / tax property auctions (`www.civicsource.com`)

Runs the online sales of parish- and city-owned (adjudicated) property for Louisiana tax authorities (City of New Orleans `CNO`, East Baton Rouge, Caddo, …). The listing site is a Gatsby app; the search is a plain JSON GET with no auth.

## Data call

```
GET https://www.civicsource.com/api/search?state=22&politicalSubDivision=<parish FIPS>&saleType=Adjudication&page=N
header: Accept: application/json
-> {"auctions":[...], "page":1, "pageSize":10, "totalCount":45}
```

Parish FIPS: Orleans `22071`, East Baton Rouge `22033`, Caddo `22017`. Jefferson `22051` returns 404 — the parish does not sell through CivicSource. `api/search/filters?...` returns the facet counts.

Auction fields: `lotNumber` (`CNO162392`), `taxAuthority.name`, `address{address1, city, state.value, postalCode}`, `location{latitude, longitude}`, `price` (opening bid / offer price), `depositPrice`, `startDate`/`endDate` (`9999-12-31` = not yet scheduled), `status` (`Public` = open, `Researching`, `ResearchComplete`), `link` (`/CNO162392`), `accountNumber`, `alternateAccountNumber`.

Listing page: `https://www.civicsource.com/auctions/<lotNumber>/`.

## Traps

- `auction.civicsource.com/auctions/...` (what the bidding UI calls) needs a bearer token — 401 anonymously. Use `www.civicsource.com/api/search` instead.
- The server sends its leaf certificate without the intermediate: Python/OpenSSL fails `CERTIFICATE_VERIFY_FAILED` while browsers succeed (AIA fetch). Retry with verification off only after the strict attempt fails.
- The page's `fetch` is replaced by a polyfill loaded from cdn.polyfill.io, so a `window.fetch` hook installed before load never sees the calls — use CDP `Network.enable` to observe them.
