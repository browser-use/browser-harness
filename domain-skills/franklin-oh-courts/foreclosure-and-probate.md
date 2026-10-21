# Franklin County, Ohio (Columbus) — clerk foreclosure docket + probate estate index

## Clerk of Courts "Case Information Online" (`fcdcfcjs.co.franklin.oh.us/CaseInformationOnline/`)
- Disclaimer is a cookie: `POST acceptDisclaimer?-xxx` with `fromPage=index&Accept=ACCEPT` → `CaseInformationOnlineSessionID` (24 h).
- There is no case-type search. Enumerate foreclosures with a name search on the county treasurer, who is a party to essentially every foreclosure: `POST nameSearch` with `lname=TREASURER selType=Civil txtCalendar1=MM/DD/YYYY txtCalendar2=MM/DD/YYYY recs=350`. Rows include a `CASE TYPE` column (`FORECLOSURES`). 350 is a hard cap with no paging — split the date window.
- Detail: `GET caseSearch?caseYear=26&caseType=CV&caseSeq=007629&reallySubmit=true`. No property field; the premises is the individual defendant's service address (skip institutions / courthouse addresses; docket service entries are the fallback).
- Rate limit: HTTP 429 after ~8 fast requests, then about a minute of host block. Pace 3 s. ToS mentions bulk-mining detection.
- Per-record links work, but a cold browser is bounced to the disclaimer, lands on the search page after accepting, and must reload the link once.

## Probate Court general case index (`probatesearch.franklincountyohio.gov/netdata/`)
- IBM Net.Data, no cookie or disclaimer. `PBODateInx.ndm/input?string=YYYYMMDD` lists cases opened that day (40 per page; "Next Cases >>" cursor is `input?stringf=YYYYMMDD<caseno>`).
- `ESTATE_DETAIL?caseno=N;;` → decedent street/city/zip (the record link). `PBFidy.ndm/input?caseno=N;;` → fiduciary name, title, appointment/termination dates, attorney. Fiduciary mailing address is not published.
- Case classes: FULL ADMINISTRATION and REAL ESTATE ONLY are the ones with property. The open-date index re-lists old estates that received a new docket entry — compare the open date.
- `probate.franklincountyohio.gov` itself is Akamai-gated (403 to curl); the netdata host is not.

Other Ohio counties use different vendors (Montgomery in-house, Summit clerkweb, Stark CJIS, Mahoning Tyler Odyssey, Hamilton in-house); only the treasurer-as-party trick transfers.
