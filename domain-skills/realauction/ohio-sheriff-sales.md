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
