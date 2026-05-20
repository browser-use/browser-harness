# Failure Artifacts

## Path Contract

For Coupang 1P bot workflows, artifacts should land under:

```text
coupang-1p-auto/logs/<arrival_or_workflow_label>/browser-harness/
```

The generic CDP default may be:

```text
coupang-1p-auto/logs/browser-harness/
```

Prefer the workflow/date-specific path from the bot wrapper when available.

## Required Evidence

Capture before closing the failed CDP session:

- Screenshot PNG.
- DOM HTML.
- Summary JSON.
- Selector probe JSON.
- Current URL with query stripped.
- Exception type and message.
- CDP URL, profile dir, download folder, and browser-harness name when available.

The selector probe list should include login, search, download, modal, upload, save, and known blocker selectors relevant to the workflow.

## Reporting

When reporting a portal failure:

- Include the sanitized URL, never a full URL with business query params.
- Include the artifact directory and the failure label.
- Include whether the session was closed.
- State whether the workflow performed any external mutation before the failure.

## Common Probe Selectors

Useful Supplier Hub probes include:

```text
[name='username']
[name='password']
text=로그인
#search
#milkrunListTable
#batchRegisterMilkrun
#supplierMilkrunLocationBtn
#saveButton
#saveMilkrun
#checkbox
.modal.show
.bootstrap-dialog
.modal-backdrop
.blockUI
#edd
#shipment-search-btn
input[type='file']
```

Keep the global probe list broad, but add workflow-specific selectors when debugging a new failure.
