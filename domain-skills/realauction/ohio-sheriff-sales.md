# RealAuction — Ohio sheriff sales (`<county>.sheriffsaleauction.ohio.gov`)

Franklin, Montgomery, Mahoning, Hamilton, Stark, Lucas, Lake, Summit, Geauga and most other Ohio counties run sheriff foreclosure sales on this ColdFusion app (vendor: Realauction.com). The auction grid is JS-rendered, but every data call is a plain GET that only needs the site's own session cookie. No browser needed.

## URL patterns

- Calendar: `index.cfm?zaction=USER&zmethod=CALENDAR` — current month. Other months: `&selCalDate={ts 'YYYY-MM-01 00:00:00'}` (URL-encode the braces/quotes).
- Auction-day preview (sets `cfid` / `cftoken` cookies and the page state): `index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=MM/DD/YYYY`
- Item loader (needs the cookies from the preview call): `index.cfm?zaction=AUCTION&zmethod=UPDATE&FNC=LOAD&AREA=W&PageDir=0&doR=1&AuctionDate=MM/DD/YYYY`
- Item details: `index.cfm?zaction=auction&zmethod=details&AID=<aid>` — plaintiff/defendant only render for logged-in bidders; anonymous gets the shell.

## Calendar markup

One `<div tabindex='0' … class='CALBOX CALW5 CALSELF' dayid='09/18/2026'>` per day. Days with sales carry `<span class="CALACT">n</span> / <span class="CALSCH">m</span> FC` (active / scheduled counts) and a `CALTIME`. Split the page on the `<div tabindex='0'` openers; a lazy regex across boxes swallows neighbours.

## Item loader response

JSON `{"retHTML": "...", "rlist": "aid,aid,..."}`. `retHTML` is token-compressed HTML: `@A`=`<div class="AUCTION`, `@B`=`</div>`, `@C`=` class="`, `@E`=`AUCTION`, `@G`=`</td></tr>`, `@I`=`table`. After decoding, each item starts at `aid="NNN"` and holds a label/value table: `Case Status`, `Case #` (`25CV3315 (19840)` — the number in parentheses is the internal case id), `Parcel ID`, `Property Address`, an unlabeled row `CITY , ZIP0000` (zip is padded to 9 digits), `Appraised Value`, `Opening Bid`, `Deposit Requirement`.

## Paging

The first call uses `doR=1` (reset). Then repeat with `PageDir=1&doR=0` — the session remembers the current page — until the returned aids stop being new. Roughly 10 items per page. Counts match the calendar's `CALSCH` figure minus cancelled cases.

## Traps

- Without the PREVIEW call first, UPDATE answers `{"retHTML":"", "rlist":""}` — it looks like an empty day.
- Only `AREA=W` returns the grid; `AREA=C` is the countdown strip.
- `zaction=AUCTION&zmethod=UPDATE&VALUE=<aids>&LUDATE=` (what the page polls) is the bid-status refresher, not the listing.
- The home page has no calendar link in its anchors (it's a JS menu); go to the calendar URL directly.

## Florida: `<county>.realforeclose.com` and `<county>.realtaxdeed.com`

Same app, same calendar and item-loader calls (the vendor is Realauction.com). Differences:

- Two sites per county: `realforeclose.com` (mortgage foreclosures) and `realtaxdeed.com` (tax deeds). Not every county uses both — the calendar of an unused one is empty, not an error. Counties seen active 2026-09: Hillsborough, Duval, Pinellas, Polk, Volusia, Marion, Escambia, Lee, Orange, Broward, Miami-Dade, Palm Beach, Brevard, Pasco, Leon, Alachua, Manatee, Sarasota, Seminole, Osceola, St. Lucie, Bay, Charlotte, Hernando, Citrus, Clay.
- Different token dictionary in `retHTML` (`@H`, `@F`, …). Don't decode tokens; read pairs by the `AD_LBL` / `AD_DTA` class names — every site uses those.
- Labels: tax deed = `Auction Type` (TAXDEED), `Case #`, `Certificate #`, `Opening Bid`, `Parcel ID` (links to the property appraiser), `Property Address`, unlabeled `CITY, FL- 32207` row, `Assessed Value`. Foreclosure = `Auction Type` (FORECLOSURE), `Case #`, `Final Judgment Amount` (no opening bid), `Parcel ID`, `Property Address`, city row, `Assessed Value`.
- Many tax-deed parcels have address `NO SITUS` or `0 <STREET>` (vacant land) — Marion is 95% of those.
- The site returns HTTP 403 to non-browser user agents; send a normal Chrome UA.
- Auction days can carry 200+ items; paging works the same (`doR=1` then `PageDir=1`).
