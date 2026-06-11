# BulkPe Dashboard (app.bulkpe.in)

**Flutter Web app rendered to canvas — there is NO DOM.** `document.querySelectorAll('input')` returns nothing; the body only has `flt-semantics-placeholder`. Forget selectors and JS clicks entirely: drive it with `screenshot()` → `click(x, y)` → `screenshot()` at the compositor level. Screenshots here are 1:1 CSS px (no retina scaling observed), but always re-screenshot to verify a click landed.

The operating company behind BulkPe virtual accounts is **Chaseout Technologies** (bank NEFTs to a BulkPe VA show as `CHASEOUT TECHNOLOGIES` / IFSC `YESB0CMSNOC`).

## Getting a statement (Virtual Account report)

1. Sidebar → `Report` (`/app/reports`).
2. Top-right `Generate` button → modal with `Generate Report for: Virtual Account | PG Collection | …`, quick filters, and From/To date fields.
3. Date fields open a Material date picker. The month back-chevron clicks are flaky — clicks may appear ignored but actually register; alternatively the **pencil icon** (bottom-left of picker) switches to typed input. After picking From it flows into To, then submits.
4. Report row appears with status `Pending` → `Completed` (~1 min). Click `Refresh`, then the download icon in the row. Direct CSV download.

## Report CSV traps

- Contains **NUL bytes** mid-file and non-UTF8 chars: read binary, `.replace(b'\x00', b'')`, decode `latin-1`.
- Columns: `Transaction Id, Reference Id, Beneficiary Name, ..., Amount, Payment Mode, Status, Status Description, UTR, Payment type (Credit/Debit), Charges, GST, Settelment Amount [sic], VA Closing Balance, ...`.
- `Payment type` = `Credit` (VA loads) vs `Debit` (payouts). Status `SUCCESS` / `FAILED` (`Insufficient Balance` is common — failed rows have Amount but were never paid; exclude them from payout totals).
- Penny-drop verification rows appear as `BulkpePenny…` beneficiaries with Amount 0.
- Charges + GST columns are per-transfer fees (only on SUCCESS rows).
