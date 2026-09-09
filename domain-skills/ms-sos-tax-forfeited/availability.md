# Mississippi SoS — tax-forfeited land inventory

The authoritative list of Mississippi parcels the State currently holds and will
sell. Use it to answer "is this parcel actually still available?" — county tax
rolls do not answer that, because a parcel stays printed in the county's report
long after it has been bought.

## Don't scrape the map

`https://tflgis.sos.ms.gov/` is an ArcGIS JS 4.32 WebMap viewer. There is
nothing useful in its HTML — the parcel list is fetched at runtime, and
`curl` of the page yields no service URLs. Go to the FeatureServer instead.

## The service

```
https://gisserver.its.ms.gov/arcgis/rest/services/Hosted/Active_Tax_Forfeited_Properties/FeatureServer/0
```

Standard ArcGIS REST. `/query` supports `where`, `outFields`, `resultOffset`,
`resultRecordCount` (page size 1000), `returnCountOnly`, `returnGeometry=false`.

**It requires a token** — an unauthenticated request returns
`{"error":{"code":499,"message":"Token Required"}}`. The viewer obtains an
anonymous portal token on load, so the cheapest way in is to run the query from
inside the page:

```python
new_tab("https://tflgis.sos.ms.gov/")
wait_for_load(); wait(10)          # the token appears with the first portal call
out = js("""
(async () => {
  const t = performance.getEntriesByType('resource').map(r=>r.name)
     .find(n => n.includes('portals/self') && n.includes('token='));
  const token = decodeURIComponent(t.split('token=')[1].split('&')[0]);
  const B = 'https://gisserver.its.ms.gov/arcgis/rest/services/Hosted/'
          + 'Active_Tax_Forfeited_Properties/FeatureServer/0';
  const r = await (await fetch(B + '/query?f=json&token=' + token
      + '&where=' + encodeURIComponent("county='Hinds'")
      + '&outFields=sosparno,parcel_number,ppin,legal_description,activeapplications'
      + '&returnGeometry=false&resultRecordCount=1000&resultOffset=0')).json();
  return JSON.stringify(r.features.map(f => f.attributes));
})()
""")
```

`js()` already awaits promises — do not pass `await_promise`, it is not a
parameter.

The WebMap definition itself lives at
`gisportal.its.ms.gov/portal/sharing/rest/content/items/d74c6b741a83487e8ca56bc8ceafbd27/data`
and also needs the token (403 without it). That is where the layer URL came
from; re-read it if the layer ever moves.

## Scale

7,272 active parcels statewide; 2,359 in Hinds alone (Aug 2026).

## Fields that matter

| field | why |
|---|---|
| `sosparno` | county parcel number, usually hyphenated (`855-18`) — the join key |
| `parcel_number` / `ppin` | same parcel, digits-only. Formats are inconsistent between records, so **normalise by stripping non-digits and match against all three** |
| `legal_description` | carries `P# 613-260`; a fourth identifier form worth harvesting |
| `parcel_status_description` | `Active` |
| `activeapplications` | **someone is already applying to buy it.** Non-zero means contested — 455 of 2,359 Hinds parcels, and 215 of the 445 we were listing |
| `county`, `municipality_name` | filter/label |

There is no situs address field. Match on parcel identifiers, not addresses.

## The trap this exists for

A county tax roll keeps printing a parcel after it has been sold. Checking a
2025 Hinds roll against this service: **63 of 508 parcels (12%) were no longer
in the active inventory** — already gone, still printed. Listing them offers
property that is not for sale.

Two identifier caveats found the hard way:
- `sosparno` is hyphenated for some records and not for others, so a string
  compare misses most matches. Normalise to digits.
- Build the key set from `sosparno`, `parcel_number`, `ppin` **and** the `P#`
  inside `legal_description` — 2,359 records yield ~2,020 distinct identifier
  forms, and any single field alone under-matches.

## Update 2026-09-09 — the inventory is a plain ArcGIS query, no browser needed

- `www.sos.ms.gov` is Akamai-gated (403 to non-browser clients), but the map app `https://tflgis.sos.ms.gov/` is not, and its HTML embeds an anonymous ArcGIS portal token in `<input id="tk" …>`.
- Inventory: `GET https://gisserver.its.ms.gov/arcgis/rest/services/Hosted/Active_Tax_Forfeited_Properties/FeatureServer/0/query?f=json&token=<tk>&where=county='Hinds'&outFields=*&returnGeometry=false&resultOffset=N&resultRecordCount=2000` — standard ArcGIS paging. Contrary to the note above, the layer DOES carry situs fields: `street_line_1`, `city`, `zip`, `propertyaddress`, plus `market_value`, `sumoftaxfees`, `activeapplications`.
- Multi-part parcels repeat rows: dedupe on `parcel_id`. Rows whose address ends in "(Lot)" are unimproved. `activeapplications > 0` means someone already applied.
- Per-parcel page `https://www.sos.ms.gov/tfsearch/default.aspx?parcel_id=<id>` is a JS shell fed by `LandsSearch.asmx/ProcessSearchDetail` (browser-only); it renders address, owner, legal description, county market value and taxes owed.
- The token-free `Hinds_Tax_Forfeit_Properties_May_2026` layer on the same server is a stale snapshot — don't use it.
