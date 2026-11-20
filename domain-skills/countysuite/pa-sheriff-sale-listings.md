# Teleosoft CountySuite — Pennsylvania sheriff "Sale Listings"

Luzerne (`sheriffsale.luzernecounty.org/Sheriff.Salelisting/`), Dauphin (`sheriffportal.dauphinc.org/SaleListing/`) and other PA counties publish sheriff real-estate sales on this product. Server-rendered, no auth.

## URL patterns

- Landing: `<base>/` — carries `<select name="SaleCategory">` (8 = Real Estate Sale) and `<select name="SaleId">` listing every sale date (`Thursday, October 15, 2026`) with its id; the page pre-selects the next upcoming date.
- Table for a date: `GET <base>/PropertySales/SaleListingDetails?activeOnly=false&crierSort=false&id=<SaleId>&searchAllSales=false&searchText=` — returns the `<tbody>` HTML the page injects. This is the only way to get another date; `?SaleId=` on the landing URL is ignored and always shows the default date.
- Sale dates as JSON: `POST <base>/PropertySales/SalesForCategory` with `id=8` → `[{SaleId, SaleDate:"/Date(ms)/", SaleDisplayName}]`.
- Poster (legal notice PDF, the stable per-property record link): `<base>/PropertySales/Poster/<n>` — the row's anchor.

## Table

`Case No. | Case Participants | Attorney | Property Address | Judgment | Status`

- `Case Participants` is `PLAINTIFF vs. DEFENDANT`, truncated in the list.
- `Property Address` cell is `street<br>CITY, PA 18702`; strip tags naively and the street runs into the city. Split on the `<br>`.
- `Status`: `Active (P)`, `Postponed( 10/5/2026 )`, `Cancelled( 8/4/2026 )`. Postponed rows carry the new date in the parentheses; cancelled rows stay listed for months.
- The same case appears under successive dates when postponed — dedupe on case number.
