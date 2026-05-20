# Side-effect Boundaries And Legacy Selenium

## Classification

Treat these as side-effecting:

- Supplier Hub registration.
- Save buttons.
- File upload.
- Download flows that also rename, merge, upload to S3, or write Google Sheets.
- Slack/UI completion notifications.

Treat these as read/status only:

- Table extraction.
- Saved-state verification.
- Preflight row counts.
- Login-state detection.

## No Selenium Fallback Rule

For side-effecting Supplier Hub public methods, CDP failure must capture artifacts, close the CDP session, and raise. Do not start Selenium after a failed CDP action. A second browser stack can duplicate downloads, S3 uploads, sheet writes, registrations, or saves.

For idempotent read-only legacy paths, Selenium compatibility may remain temporarily, but the public route should make the boundary obvious.

## Saved-state Verification

Before deciding to click a business save button again, verify state:

- Bulk milkrun registration: `completeRegistration_*` count.
- Split milkrun: milkrun list has the expected `양주시_1` row.
- Pallet company: saved form/list shows the expected pallet rental company.
- Downloads: deterministic target file exists, has non-zero size, and downstream merge/upload saw the expected file.

If the saved state cannot be proven, fail fast and report artifacts instead of retrying through a fallback.

## Current Legacy Map

Known retained Selenium areas in `bot_coupang_1p.py` include:

- Login/cookie compatibility helpers.
- Older milkrun Selenium helper variants retained for comparison.
- Shipment registration/upload/status helpers.
- Some raw order/SKU/order-list Selenium variants retained as legacy helper code even when public routes are CDP.
- Non-Supplier-Hub or adjacent automation such as Sabanet/fullfillment should be classified separately before applying this skill.

Do not infer that a retained `_selenium` helper is safe to call from a side-effecting public method. The public method's CDP wrapper and tests define the contract.
