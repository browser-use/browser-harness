# County ArcGIS layers behind "property map" pages (land banks, tax lists, city-owned inventories)

Many county "interactive map" pages are thin web maps over a public ArcGIS FeatureServer. Find the layer (page JS, web-map JSON, or the Hub item), then query it directly — no browser, no auth:

```
GET <FeatureServer>/<layer>/query?where=1%3D1&outFields=*&returnGeometry=false&f=json&resultOffset=0&resultRecordCount=2000
```

Seen 2026-09-09:
- **Baltimore DHCD city-owned for sale**: `https://baltegis.baltimorecity.gov/mapping/rest/services/Housing/DHCD_Open_Baltimore_Datasets/FeatureServer/7` (join `BLOCKLOT` to the Real Property layer for zip/owner/value; ~170 rows still privately titled). Per-record `…/7/query?where=ID_AcqFirefly=<id>&f=html` renders.
- **Macon-Bibb judicial in rem tax list**: `https://services2.arcgis.com/zPFLSOZ5HzUzzTQb/arcgis/rest/services/JIR<Month><Year>/FeatureServer/0` — the layer name rotates monthly; resolve it through the web app → web map each run. Record link is qPublic (Cloudflare challenge to non-browsers).
- **Peoria city land bank**: `…/City_of_Peoria__IL_Available_Parcels_WFL1/FeatureServer/61`; its city/zip fields are the owner's mailing address, so resolve situs by PIN from the county Cadastral layer (`gis.peoriacounty.gov …/DP/Cadastral/FeatureServer/1`, 10-digit PIN).
- **Augusta parcels**: `https://gismap.augustaga.gov/arcgis/rest/services/Map_LayersTS/MapServer/316/query` with `pin IN (...)` (100 per call) — situs, assessor value, vacant flag, beds/baths; `delinq_yrs` is queryable.
- **Saginaw land bank**: ePropertyPlus tenant `sclb` (no prices, all "Residential Vacant").

Traps: paging caps (`maxRecordCount`, usually 1000–2000); polygon layers repeat multi-part parcels (dedupe on the parcel id); snapshot layers with a month in the name go stale.
