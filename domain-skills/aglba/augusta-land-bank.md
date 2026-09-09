# Augusta Land Bank Authority (`aglba.org`) — available inventory

WordPress + MyListing theme. Every parcel is a `job_listing` post titled by its PIN.

- Enumerate: `GET https://aglba.org/feed/?post_type=job_listing&orderby=title&order=asc&paged=N` (RSS, 10 per page, 404 past the last page). `orderby=title` is load-bearing: the explore page, the plain feed and the AJAX "Available" filter all page on a tied post date and return different rows on each request (two crawls agreed on fewer than half the pages). Title sort is stable and complete (543/543).
- Reservation status: `GET /?mylisting-ajax=1&action=get_listings&security=<CASE27.ajax_nonce from the explore page>&listing_type=land-bank-properties&form_data[reservation_status]=Under+Review` → `found_posts`. Available = all − Under Review.
- Per-parcel page: `https://aglba.org/listing/<PIN>/` — "Property Details" table with street number/name when the county layer has no match.
- Situs, value and geometry come from the county parcel layer: `POST https://gismap.augustaga.gov/arcgis/rest/services/Map_LayersTS/MapServer/316/query` with `where=pin IN (...)` (100 per call, no auth).
- No asking price is published; offers go through an application.
- Trap: the host rate-limits bursts. A 55-page crawl followed by per-PIN detail fetches drew HTTP 429 on the very next request; keep it to about 2 requests/second.

Tax levy sales (Tax Commissioner): `POST http://appweb2.augustaga.gov/TaxLevySales/Service/TaxLevyService.svc/GetSales` with body `{}` → double-encoded JSON `{"TLS":[{SaleDate, ParcelID, Owner, Address, AmountDue}]}`; lists only the next first-Tuesday sale. Record page `https://gismap.augustaga.gov/AugustaTS/?pin=<PIN>`.
