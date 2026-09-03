# Zapier Editor

Field-tested against `zapier.com/editor` in a logged-in Chrome session on 2026-07-21.

## URL patterns

```text
/editor/<zap-id>/published
/editor/<zap-id>/draft
/editor/<zap-id>/draft/<step-id>/fields
/editor/<zap-id>/draft/<step-id>/sample
/editor/<zap-id>/run/<run-id>/<step-id>/run-details
/app/history
```

Step cards have stable `data-testid="step-node-<step-id>"` attributes. The step panel tabs use `aria-label="Show Setup"`, `Show Configure`, `Show Test`, and `Show Run details`.

## Compare published and draft definitions before publishing

The page's `#__NEXT_DATA__` JSON contains both definitions:

```javascript
const page = JSON.parse(document.querySelector("#__NEXT_DATA__").textContent)
const zap = page.props.pageProps.zap
const published = zap.current_version.zdl
const draft = zap.draft.zdl
```

`zdl.steps` contains step ids, apps, actions, authentication ids, and params. Compare the published and draft trees before publishing; Zapier permits only one draft, so replacing a draft can discard unrelated unpublished work.

Do not print or commit raw ZDL. It can contain private mappings, addresses, phone numbers, destination ids, and webhook data. Emit only diff paths or carefully redacted values.

The in-document `#__NEXT_DATA__` is initial page state and can be stale after an autosave. Get a server readback without reloading the tab:

```javascript
fetch(location.href, {cache: "no-store"})
  .then(r => r.text())
  .then(html => {
    const doc = new DOMParser().parseFromString(html, "text/html")
    return JSON.parse(doc.querySelector("#__NEXT_DATA__").textContent)
  })
```

## Edit contenteditable fields reliably

Zapier uses Slate contenteditable elements for many text fields. To replace the full value, select the field's DOM contents before inserting text:

```javascript
const field = document.querySelector('[aria-label="Search terms, required"]')
field.focus()
const range = document.createRange()
range.selectNodeContents(field)
const selection = getSelection()
selection.removeAllRanges()
selection.addRange(range)
```

Then use `type_text(...)`, click `Continue`, and verify the saved param from a fresh server readback. A synthetic Command-A can leave trailing Slate text behind.

## Safe trigger testing

On a trigger step's Test tab, `Find new records` refreshes trigger samples only. It does not run downstream actions. Inspect the returned sample subject/sender/body fields before proceeding.

Do not click the top-level `Test run`, `Replay`, or an action step's `Test step` during read-only verification. Those controls can execute webhooks, sends, or data writes. Action Test tabs describe the mutation they would perform; use `Skip test` when preserving an unpublished draft without creating test data.

## Zap history

Open `/app/history`, filter with `input[aria-label="Zap Search"]`, and select the matching `role="option"`. Run rows load asynchronously after the filter applies, so wait and re-read the page before concluding that no runs exist.
