# Jefferson Parish Sheriff (LA) — judicial real-estate sales (`eservices2.jpso.com/JudpSale`)

Covers Metairie, Kenner, Gretna, Harvey, Marrero, Westwego, Avondale, Waggaman and the rest of Jefferson Parish. Sales are Wednesdays.

## URL patterns

- List (current sale date): `GET /JudpSale/Home/RealEstate` — a plain HTML table plus a `<select name="SaleDateString">` listing every upcoming sale date and a `<select name="StartDate">`.
- Other dates: `POST /JudpSale/Home/DateSelectorPartial` form-encoded `Type=RE&SaleDateString=M/D/YYYY&Keyword=` — returns that date's table. A GET on this URL is 404.
- Detail: `/JudpSale/Home/SelectREProperty?CSSHNBR=<n>` — case, full case style, attorney, writ amount, appraisal flag, sale date.

## Table

`Case Number | Case Style | Sale Date | Address | Writ Amount | Appraisal`

- `Case Style` is `PLAINTIFF VS DEFENDANT` (may be truncated in the list; the detail page has the full text).
- `Address` is `1909 STAFFORD STREET GRETNA, LA` — street and city run together with no comma; split on the parish's municipality names (longest first). About two thirds of rows are `Address Not Available`.
- `Writ Amount` is the judgment amount, not an opening bid.
- Dates further than ~4 weeks out usually have no rows posted yet; the same writ can appear under more than one date, so dedupe on case number.
