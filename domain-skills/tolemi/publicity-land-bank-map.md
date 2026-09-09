# Tolemi publiCity — land-bank / city-property maps (`<alias>-publicity.tolemi.com`)

Summit County (Akron), Birmingham, Indianapolis, Buffalo, Dallas, Savannah, Baton Rouge, Pittsburgh, Louisville, Baltimore, Rochester and others publish parcel inventories on this deck.gl map. The canvas shows nothing to a DOM scraper; the data is one unauthenticated GraphQL endpoint.

## Data call

```
POST https://cg.tolemi.com/q
headers: content-type: application/json, apollo-require-preflight: true, city-alias: <alias>, product: publiCity
body: {"operationName":"getAssetsWithPrograms","variables":{"params":{},"limit":500,"offset":0},
       "query":"query getAssetsWithPrograms($params: JSON, $limit: Int, $offset: Int) { assets(params: $params, limit: $limit, offset: $offset) { id alias commonName address zipCode latitude longitude parcelId showOpportunityBanner gisCity { name state { abbreviation } } city { name state { abbreviation } } programEligibles { program { id name alias } } } }"}
```

Page with `offset` in steps of 500 until a short page. The alias is the subdomain before `-publicity` and also the `city-alias` header. No price is published.

## Reading a tenant

- Tenants with sale programs (`Side Lots`, `Infill`, `Standard Sale`, `Welcome Home`, `Dallas Land Bank Program`, `Substandard Lots` …) are for-sale inventories: `summit-county-oh` (488), `birmingham-land-bank-al` (1,415), `indianapolis-in` (167), `buffalo-ny` (327), `dallas-tx` (42), `savannah-ga` (41).
- Tenants with **no** programs and thousands of parcels (`rochester-ny`, `albany-ny`, `louisville-ky`, `lancaster-pa`, `binghamton-ny`, `lorain-oh`, `rockford-il` with only `Rental Registration`, `baltimore-md` with `Water Access`) are whole-city parcel or code-enforcement registries, not sale lists. Do not treat them as inventory.
- `akron-oh` is a separate tenant from `summit-county-oh` (0 id overlap) and is mostly parcels without house numbers.
- An unknown alias returns an empty `assets` array, not an error.
- `gisCity` is often null; fall back to `city` or a caller-supplied city. Many rows lack `zipCode`, which hurts downstream address verification.
