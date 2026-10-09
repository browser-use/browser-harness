# Bilbasen.dk — Used-car search data extraction

Field-tested against `www.bilbasen.dk` on 2026-09-21 from a logged-out, real Chrome session (CDP). Bilbasen is Denmark's largest used-car marketplace.

## Quick summary

- **Plain HTTP is blocked.** `http_get` / `curl` with a full Chrome UA returns **HTTP 202 with an empty body** (JS bot challenge). Use the user's real browser.
- **Search result pages embed every listing on the page as JSON** in `<script id="__NEXT_DATA__">` (Next.js SSR). No need to scrape cards or scroll.
- Search URL pattern: `https://www.bilbasen.dk/brugt/bil/<make>/<model>?pricefrom=<int>&priceto=<int>`. Make/model slugs are lowercase (`vw`, `id.4`). The site 302s to an internal model id (`/brugt/bil/vw/id2314`) and appends `includeengroscvr=true&includeleasing=false`; both URLs work.
- 30 listings per page; total hits in `hits`.
- This example reads one page. When `hits` exceeds the listing count, use the visible next-page control.
- Wait for listing IDs to change before reading the next page. Remove duplicates by `externalId`.
- Verify the final unique count against `hits`; report any shortfall instead of claiming complete results.

## Extracting listings

```python
import json
new_tab("https://www.bilbasen.dk/brugt/bil/vw/id.4?pricefrom=150000&priceto=195000")
wait_for_load()
raw = js("document.getElementById('__NEXT_DATA__').textContent")
queries = json.loads(raw)["props"]["pageProps"]["dehydratedState"]["queries"]
data = next((q.get("state", {}).get("data") for q in queries
             if isinstance(q.get("state", {}).get("data"), dict)
             and "listings" in q["state"]["data"]), None)
if data is None:
    raise RuntimeError("The page has no listings query")
print(data["hits"], len(data["listings"]))   # e.g. 48, 30
```

Top-level keys in `data`: `listings`, `filterOptions`, `sortOptions`, `searchRequest`, `pagination`, `breadcrumbs`, `canonicalUrl`, `hits`, `totalAbundance`.

### Fields in each listing

| Field | Example | Notes |
|---|---|---|
| `externalId` | `6999185` | listing id, also last path segment of `uri` |
| `uri` | `https://www.bilbasen.dk/brugt/bil/vw/id4/52-pure-5d/6999185` | detail page |
| `price.price` | `169900` | int DKK, use for math; `price.displayPrice` is formatted |
| `price.priceType` | `"Retail"` | |
| `make`, `model` | `"VW"`, `"ID.4"` | |
| `variant` | `"77 1ST Pro Performance 5d"` | trim string; use the battery field for capacity |
| `description` | Danish prose, 800–2900 chars | dealer boilerplate mixed with equipment highlights |
| `sellerType` | `"Forhandler"` / `"Privat"` | dealer vs private |
| `saleType` | | |
| `location` | object | seller location |
| `media[]` | `{mediaType: "Picture", url}` | images, `?class=S640X640` |
| `properties.firstregistrationdate` | `{displayTextShort: "10/2022"}` | month/year of first registration |
| `properties.mileage` | `"76.500 km"` | Danish thousands separator, parse in code |
| `properties.hk` | `"148 hk"` | horsepower |
| `properties.moth` | `"920 kr/år"` | annual ownership tax (ejerafgift) |
| `properties.trailer` | `"1.000 kg"` | tow rating |
| `properties.kmt` | `"10,9 sek"` | 0–100 acceleration |
| `properties.electricmotorrange` | `"343 km"` | WLTP range |
| `properties.batterycapacity` | `"52 kWh batteri"` (`displayTextLong`) | |
| `properties.geartype` | transmission text | gearbox type |
| `properties.fueltype` | `"El"` | fuel type |
| `features` | `[]` | **empty on search pages**; equipment list is not in the search JSON |

Each `properties.*` entry has both `displayTextLong` and `displayTextShort`. All numeric values are formatted strings; parse them in code.

## Traps

- **202 empty body from `http_get`** is the bot wall, not a transient error. Do not retry with headers; go through the browser.
- **`features` is always empty in search results.** Equipment lists must come from the detail page.
- **Seller descriptions are not spec sheets.** Descriptions were seen quoting DC charging speeds that did not match the variant's model year. Verify technical specs against the exact variant and model year. Use `properties.batterycapacity` for the listed battery capacity.
- **Danish number formats**: `76.500 km` is 76,500; `10,9 sek` is 10.9.
