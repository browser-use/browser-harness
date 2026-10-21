# tax-sale.info — Michigan county treasurer tax-foreclosure auctions (Title Check LLC)

One statewide site runs the treasurer auctions for most Michigan counties. Server-rendered, no auth, normal UA.

- Auction list: `GET https://www.tax-sale.info/auctions` → `<div class="entry clearfix">` blocks with the date and `/listings/catalog/<cid>` links named `<County>`, `<County> Re-Offer`, `<County> DNR`. A county's first sale is typically August/September; unsold lots roll into a later "Re-Offer" / no-reserve catalog.
- Catalog CSV: `GET /catalog/getCsv/id/<cid>` — one row **per parcel** (a lot can span several parcels), address as `STREET␣␣CITY` with no zip, `Minimum Bid`, `Current Taxes`, SEV, parcel id, lat/lon (longitude written `W83.91…`), inspector comment.
- Sold status only exists on the catalog HTML: `GET /listings/catalog/<cid>` → `<article class="portfolio-item pf-…">` with `Minimum Bid: $X` or `Sold for $X`; `pf-vacantLot` class marks vacant lots. The CSV and lot pages never say sold.
- Record link: `https://www.tax-sale.info/lot/show/id/<lot_id>` (server-rendered).
- Open-for-bidding feed statewide: `GET /map/geoJson[?county=<MI county number>&filter=n]` — empty once a county's sale has closed.
