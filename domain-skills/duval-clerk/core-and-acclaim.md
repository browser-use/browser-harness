# Duval County Clerk (Jacksonville, FL) — CORE court cases and Acclaim official records

## CORE (`core.duvalclerk.com`) — court case search, JSON web service, no captcha enforced
- `POST /internal/CoreWebSvc.asmx/PublicLogin` body `{}` → public token.
- `CaseSearchBegin {token, returnTabId, inputs:{__type:"DuvalClerk.Web.Core.UserSearchInput", CaseYear:"2026", CaseType:"CA", CaseTypeList:"491,492,493,627,628,629,494,495,496,304,305,306,307"}, captcha:"captchaPH"}` → 25 cases per page, newest first. `CaseSearchUpdate {operation:"NextPage", requestState:<hidden field>}` pages. There is no filed-date filter: walk newest-first until File Date passes the cutoff.
- `GetCaseById {caseID, simCtrl:0}` (the int 0 is required; null → 500) → parties with `STREET<br/>CITY, FL32277` addresses and docket lines. Foreclosure (CA) defendants carry street addresses; probate (`CaseType:"CP", CaseTypeList:"440"` formal administration) has party names but addresses and roles are blanked for public users.
- `CaptchaChallenge` came back null across ~120 calls; treat a non-null value as a stop signal.
- Record link: `https://core.duvalclerk.com/CoreCms.aspx?mode=PublicAccess...` (from the case page).

## Acclaim official records (`or.duvalclerk.com`, Harris) — lis pendens index
- `POST /search/Disclaimer` `Disclaimer=true` (cookie) → `POST /search/SearchTypeDocType?Length=6` with hidden `DocTypes=104` (numeric id; the display name alone errors) + `RecordDateFrom/To` → `POST /Search/GridResults sort=&page=N&pageSize=50` → JSON `{Data:[…], Total}`.
- Detail `GET /Details/documentdetails/<TransactionItemId>/1/1/50` opens cold and carries grantor/grantee, case number and the legal description — no street address on the index.

## Other Florida counties (probed 2026-09-09)
- Hillsborough: official records `ORIPublicAccess` (OnBase JSON, no captcha, legal descriptions only); court search HOVER has reCAPTCHA v3 on every date search.
- Volusia: `app02.clerk.org/or_m` WebForms, no captcha, 500-row cap (slice weekly), legal descriptions only.
- Marion / Polk: Pioneer BrowserView with `useRecaptchaV3=1` on `api/search`. Lee: LandmarkWeb (host-blocked from some IPs). Escambia: LandmarkWeb behind Cloudflare, Benchmark court search with captcha. Leon: Akamai 403.
