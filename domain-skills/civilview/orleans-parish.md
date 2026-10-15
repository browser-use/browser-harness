# Tyler CivilView SalesWeb — Orleans Parish sheriff sales (`salesweb.civilview.com`)

Same host and URL scheme as the Ohio counties (`Sales/SalesSearch?countyId=N`, `Sales/SaleDetails?PropertyId=N`), but a different table layout. Orleans Parish Sheriff (New Orleans) is `countyId=28`; real-estate auctions every Thursday at noon.

## Table layout (countyId=28)

`Sort Order | Case # | Sales Date | Property Status | Case Title | Address/Description | Picture | Plaintiff | Judgment | Terms | Details`

- The `Details` link (the row's `SaleDetails?PropertyId=`) is the **last** cell; on Ohio counties it is the first. Locate the link cell by content, not position.
- `Case Title` is `PLAINTIFF vs DEFENDANT`; there is no separate Defendant column.
- `Address/Description` is one comma-less string: `5405 WEST END BD NEW ORLEANS LA 70124`. Corner lots read `7831 HICKORY ST AND 1801 FERN ST NEW ORL…` — take the first address.
- Suffixes are abbreviated their own way: `BD` = Blvd, `AV` = Ave, `PKY` = Pkwy.
- `Property Status` is `Scheduled`; cancelled/sold rows carry other statuses.
- Plaintiffs are mostly `CITY OF NEW ORLEANS` (code-enforcement lien foreclosures) and lenders — no treasurer tax cases.
