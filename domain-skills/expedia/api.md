# Expedia — typeahead API, property URLs, affiliate shortlink chain

Field-tested 2026-06 against `www.expedia.mx` (applies to other POS domains —
`www.expedia.com`, etc. — with the same paths).

## Hotel typeahead API (no auth, no cookies)

```
GET https://www.expedia.mx/api/v4/typeahead/{url-encoded query}
    ?client=SearchForm&lob=HOTELS&personalize=false&regiontype=2047
    &dest=true&features=ta_hierarchy&maxresults=10
```

- Works with plain `curl_cffi` chrome impersonation (`impersonate="chrome120"`)
  — no session, no PerimeterX/Akamai challenge observed at low volume.
- Response `sr[]` items of `"@type": "gaiaHotelResult"` carry exactly what you
  need to identify a property: `hotelId` (the `.h{id}.` in property URLs),
  `regionNames.shortName`/`fullName`, and `coordinates.lat/long`.
- Querying `"{hotel name} {city}"` reliably puts the right property first;
  retry with the bare hotel name if the combined query returns nothing.
- 10× faster and more robust than scraping the search results page.

## Property page URLs

- Canonical shape: `https://www.expedia.mx/{slug}.h{hotelId}.Informacion-Hotel`
  (`.Hotel-Information` on the English POS). **Routing is by `.h{id}.` only —
  the slug is cosmetic** and Expedia 301s to the canonical slug (it even
  rewrote `Roma-…` → `Rome-…` in tests).
- Useful query params: `startDate=YYYY-MM-DD`, `endDate=YYYY-MM-DD`,
  `rm1=a{adults}[:c{age}...]` (e.g. `rm1=a2:c8:c5`), `expediaPropertyId={id}`.
  These pre-fill dates and occupancy on the page.
- Search fallback: `https://www.expedia.mx/Hotel-Search?destination={name},
  {city}&startDate=…&endDate=…&adults=N&rooms=1`.

## Trap: property pages 429 datacenter-ish IPs

`GET` on property pages returned HTTP 429 from a residential-but-curl client
while the **typeahead kept returning 200**. If you only need to *construct*
URLs for a human to open, never fetch the property page at all; if you must
read one, do it through the user's real browser session (coordinate clicks),
not `http_get`.

## Affiliate shortlink chain (`expedia.tpx.lv` / `expedia.tp.st`)

`expedia.tpx.lv/<code>` links are **Travelpayouts** partner shortlinks. The
redirect chain (observed):

```
expedia.tpx.lv/<code>
  → deals.vio.com?label=…-<TP marker>&ofd=book_uri=destination=<expedia URL>
  → r.vio.com (same params)
  → prf.hn/click/camref:…/pubref:…/destination:<expedia URL>   (Partnerize)
  → r.bttn.io (Button attribution)
  → www.expedia.mx/<City>-Hoteles-<Name>.h<id>.Informacion-Hotel?…&affcid=…PHG…
```

- The Travelpayouts marker is recoverable from the `label=`/`utm_content=`
  params on the vio.com hop.
- To mint these programmatically, don't reconstruct the chain — use the
  Travelpayouts links API:
  `POST https://api.travelpayouts.com/links/v1/create` with
  `{"trs": <project id>, "marker": <partner id>, "shorten": true,
  "links": [{"url": "<full expedia URL>", "sub_id": "…"}]}` and the
  account's API token (header `X-Access-Token`). Limits: 100 req/min/marker,
  ≤10 links per request. Returns `partner_url` shortlinks. Full-length brand
  URLs only (no shortened input).
- HEAD requests die mid-chain (some hops 405 HEAD); use GET with
  `allow_redirects` or walk `Location` headers manually.
