# RBC Online Banking - Account Statements

Verified against `www1.royalbank.com` in August 2026.

## Direct Route

The central document page is:

`https://www1.royalbank.com/sgw1/olb/profile-hub/documents-en`

It can list statements for deposit accounts and credit cards without navigating
through each account's detail page.

## Stable Controls

- Account picker: `button[data-testid="multi-select-expand"]`
- Account labels: `.rbc-checkbox-label`
- Apply account filter: `button[data-testid="multi-select-done"]`
- Show results: `button[data-testid="button-show-docs"]`
- PDF links: `a[data-testid="desktop-document-download-link"]`

The month and year controls are native `select` elements, but their IDs can
change between sessions. Locate them from their labels/options instead of
hard-coding an ID. The month control includes an `All months` option. Year
option values are positional, so select the option whose visible text is the
desired year rather than assuming the value equals the year.

Each PDF link's `aria-label` includes its statement date and masked account
description, for example `Download Feb. 14, 2025 Statement for ...`. This is a
reliable source for the destination filename and coverage checks.

## Downloads

Set the CDP download path before clicking statement links:

```python
cdp(
    "Browser.setDownloadBehavior",
    behavior="allow",
    downloadPath="/absolute/output/path",
    eventsEnabled=True,
)
```

After changing the account, month, or year filters, click the Show results
button and wait for the PDF link `aria-label` dates to match the requested
period. `wait_for_load()` alone is insufficient because the route does not
change while results refresh.
