# EventHub (event.eventhub.jp) — participant/exhibitor scraping

Japanese B2B event matching platform (used by Tokyo Game Show, etc). Next.js SPA
backed by a clean private JSON API. **Never scrape the DOM** — hit the API.

## URLs
- Event pages: `https://event.eventhub.jp/e/<EVENT_ID>/participant` (SPA route).
  `<EVENT_ID>` is an opaque short code, e.g. `3a7SOKkxY`. `/login` alone (no event id) 404s.
- API root: `https://client-api.eventhub.jp/api/client`

## Auth
Cookie-based (session cookie in the logged-in Chrome). No token in localStorage.
**All API calls must run in-browser** via `js()` with `credentials:"include"`.
If a call returns 401 / redirects to login, the session expired — user must re-login.

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/user/searchcount/<EVENT_ID>` | total record count `{count}` |
| POST | `/user/search/<EVENT_ID>` | paginated record list (array) |
| GET  | `/customfield/<EVENT_ID>?isNetworkingEnabled=true` | custom field defs |
| GET  | `/customfieldoption/find/<EVENT_ID>` | dropdown option defs |

### Search/count payload (both endpoints)
```json
{"userTypes":["exhibitor","participant"], "tags":[], "limit":100, "offset":0}
```
`userTypes` and `tags` are **required** — omitting either → HTTP 400 with a helpful
validation message. Paginate `offset` in steps of `limit` (100 works). Stop when a
page returns `< limit` rows.

### Record fields (`/user/search`)
`userId, userType (participant|exhibitor), language, portraitUrl, name, familyName,
givenName, affiliation, department, position, shortComment, companyId, businessCardUrl,
isStaff, isFavorite, isPopular, userCustomFieldValues:[{customFieldId,value}],
userCustomFieldOptions:[{customFieldId,customFieldOptionId}]`.

### Resolving custom fields
- `/customfield` items: `{customFieldId, itemId, inputType, labelEn, labelJa,
  isSupportedParticipant, isSupportedExhibitor}`. Build `customFieldId -> labelEn||labelJa`.
- `/customfieldoption/find` items: `{customFieldId, customFieldOptionId, valueEn, valueJa,
  displayOrder}`. Build `customFieldOptionId -> valueEn||valueJa`.
  **GOTCHA — key mismatch:** field defs use `labelEn/labelJa` but option defs use
  `valueEn/valueJa`. Using `labelEn` on options silently falls back to the numeric id, so
  tag columns fill with `326880;326881;...` instead of names. Always resolve options via
  `valueEn||valueJa`, then assert no tag cell is all-digits before shipping.
- **Field input types matter:** a `checkbox`/`select` field (e.g. Business Intentions,
  inputType `checkbox`) stores data ONLY in `userCustomFieldOptions`, never in
  `userCustomFieldValues` — so its text-value column is always blank. Emit ONE column per
  field: text fields → value, checkbox/select → joined option labels. Don't emit both.

## Gotchas
- A single in-browser `js()` loop over ~20 sequential fetches exceeds the Runtime.evaluate
  timeout. **Batch it**: accumulate pages into a `window.__all` global across multiple
  `browser-harness` invocations (same tab persists the global), or ~5 pages per call.
- Write CSV as **UTF-8 with BOM** — records are heavily Japanese, Excel needs the BOM.
- TGS 2026 (`3a7SOKkxY`): 1962 records = 1367 exhibitors + 595 participants.
- Native fields `shortComment` and `businessCardUrl` came back empty for all records —
  drop all-empty columns after building rather than assuming they'll populate.
- **QA every scrape column-by-column**: print per-column fill %, cross-check totals
  against a userType split, and assert option cells contain no raw numeric ids. Row-count
  == searchcount is necessary but NOT sufficient.
