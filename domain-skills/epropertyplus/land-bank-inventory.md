# ePropertyPlus — land-bank public portals (`public-<tenant>.epropertyplus.com`)

Tyler's ePropertyPlus hosts the public inventory for many land banks: Columbus/COCIC (`cbus`), Shelby County / Memphis (`sctn`), Kalamazoo County (`kzoo`), Atlanta, Lansing. The search page is a jQuery DataTables app; its data call is an unauthenticated GET.

## Data call

```
GET /landmgmtpub/remote/public/property/getPublishedProperties
    ?limit=100&iDisplayStart=0&iDisplayLength=100&mDataProp_0=parcelNumber&page=1
    &json={"criterias":[]}&customFields=[]&sort=[{"property":"propertyAddress1","direction":"ASC"}]&favoriteProperties=
header: X-Requested-With: XMLHttpRequest
-> {"success":true,"size":<total>,"rows":[...]}
```

Row fields: `propertyAddress1, city, state, postalCode, parcelNumber, askingPrice, currentStatus, propertyClass, latitude, longitude, thumbImgUrl, legalDescription, yearBuilt, bedrooms, squareFootage, id`. Page with `iDisplayStart`; `size` is the total. POSTing to the same URL returns HTTP 500 — it is a GET.

## Per-tenant status vocab

- `cbus`: no `currentStatus` at all; everything published is for sale (43 rows, 2026-09).
- `kzoo`: `Acquired` (priced inventory), `Reserved`, `Disposed` (218 rows).
- `sctn`: `FOR SALE`, `SALE COMPLETE`, `Rescinded`, `2511 Hold`, `IN REDEMPTION`, `Redeemed` … (12,878 rows — filter to `FOR SALE`). Many Memphis parcels have house number `0` / `0000`.

## Other endpoints

- `remote/public/property/getPublishedProperty` (POST `propertyId=<id>`) — one property with photos.
- `remote/public/property/viewSummary?parcelNumber=<parcel>` — human-readable summary page, good as a listing URL.
- `remote/public/referenceData/getKeyValues?classification=Property Status` — the tenant's status vocabulary.
- Relative photo paths `/landmgmt/remote/image/...` map to `/landmgmtpub/remote/public/property/...`.

## Finding tenants

Hostnames are `public-<code>.epropertyplus.com`; unknown codes fail DNS. Known: `cbus`, `sctn`, `kzoo`; `dlba` and `indy` resolve but TLS-fail (retired).
