# Google Sheets — sharing dialog & API-first workflows

## Share a sheet with a service account

Share button (top right) → type the SA email → pick the autocomplete entry → chip appears with a role dropdown (defaults to Editor) → optionally uncheck "Notify people" (SAs can't read mail) → `Share`.

- **Workspace orgs show an external-share interstitial** ("...is external to <org>... Share anyway?"). Click `Share anyway`, which returns you to the share dialog — you must click `Share` AGAIN. The dialog closing is the success signal.
- Trap: after the dialog closes, stray clicks land on the grid and put a cell into edit mode. If that happens press Escape (twice is safe) — verify the formula bar shows the original value before moving on.

## Prefer the API over DOM scraping

The Sheets grid is canvas-rendered — DOM selectors are useless for cell data. Once a service account (or OAuth token) exists, read/write via `sheets.googleapis.com/v4` with plain `fetch`; a service-account JWT is ~20 lines of `node:crypto`/`python` with scope `https://www.googleapis.com/auth/spreadsheets`, no SDK needed.

- Read dropdown (data validation) options without clicking anything: `GET /v4/spreadsheets/<id>?ranges=Sheet1!B2:B2&includeGridData=true&fields=sheets.data.rowData.values.dataValidation` → `ONE_OF_LIST` values. `strict: true` means unlisted values are rejected chips.
- Track "your" rows robustly with **row-level developer metadata** (`createDeveloperMetadata` on a ROWS dimensionRange, then `POST /developerMetadata:search`). Row numbers shift when humans sort/insert/delete; metadata moves with the row. `values.append` returns `updates.updatedRange` — parse the row number from it to tag the row you just appended.
- The sign-in wall (`accounts.google.com/v3/signin`) means the whole Chrome profile is logged out, not just Sheets — stop and ask the user; there may be no account chooser at all.
