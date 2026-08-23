# Scotiabank Online Banking - Account Statements

Verified against `secure.scotiabank.com` in August 2026.

## Direct Route

Statement pages use an opaque account key already present in the signed-in
account URL:

`https://secure.scotiabank.com/my-accounts/{accountType}/{accountKey}/statements`

`accountType` is typically `chequing` for deposit accounts and `credit` for
credit cards and lines of credit. Preserve the opaque key exactly; never record
it in a shared domain skill.

## Stable Controls

- Year filter: `select#yearFilter`
- Select all: `input[aria-label="Select all"]`
- Per-statement view buttons: `button[aria-label^="View PDF"]`
- Initial bulk button: `#buttonDownloadAll`
- Selected-items download button: `#buttonDownloadPdf`

Changing the native year select requires a bubbling `change` event. Wait until
the dates embedded in the View button `aria-label` values match the selected
year; the SPA does not perform a full navigation.

```python
js("""(()=>{
  const select = document.querySelector('#yearFilter');
  select.value = '2025';
  select.dispatchEvent(new Event('change', {bubbles: true}));
})()""")
```

## Statement API

Each View button ID is `StatementView-{documentToken}`. The page fetches the PDF
from this authenticated endpoint:

`GET /my-accounts/api/statements/{documentToken}`

The response is `application/pdf`. Fetch it from the signed-in page context
with `credentials: 'include'`; do not copy tokens, cookies, or account keys into
logs or documentation.

This endpoint is more reliable for bulk archival than the visible bulk control:
the bulk flow can report multiple selected items yet return a ZIP containing
only one generically named entry (`manage.statements.pdfFilename`). Download
each View button's token separately, name it from the ISO date in its
`aria-label`, and validate every result as a PDF.

The View action opens a `blob:` URL in a new tab. That blob can be revoked or
unavailable to another CDP target, so use the authenticated statement endpoint
instead of trying to save the PDF viewer tab.
