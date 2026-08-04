# Knowify — vendor bills (`secure.knowify.com`)

AngularJS SPA. Reads/writes go to `api.knowify.com` over XHR with a `kAuth` bearer token, so
**prefer the private API over DOM work** — the DOM is only worth driving when you need to learn a
request shape.

## Discovering a request shape without a capture

The whole API registry plus every call site is in the main bundle — no auth, no browser:

```bash
curl -s https://secure.knowify.com/ | grep -oE 'main\.[^"]+\.js'   # current hash
curl -s "https://secure.knowify.com/main.<hash>.js" > main.js
grep -oE '[A-Za-z0-9_]+:\{[^{}]*verb:"Payables"[^{}]*\}' main.js | sort -u   # endpoints
grep -oE '.{200}callAPI\("updatePayableItem".{300}' main.js                  # literal body
```

`verb` is the path prefix, the key is the endpoint name → `api.knowify.com/<verb>/<name>`.

## URL patterns

- `#/bills/manage` — list; `#/bills/manage/{id}` — one bill
- `#/bills/edit?id={id}` — the edit form (Details + Items)
- `#/projects/details/plan/{projectId}` — job cost view
- `#/projects/details/contracts/del/{projectId}` — contract/invoice view

## Selectors that work on the bill edit form

- `input[name="payable-item-description-{rowIndex}"]` — a line's description. It's a
  `k-typeahead-field`: focusing it fires `ServiceCatalog/Search2` against the current value.
  Typing a value that matches no catalog item leaves no dropdown, so plain
  `Input.insertText` after Cmd+A is safe.
- Modals render inside `<k-modal-target>`. Query within it — a document-wide
  `input[type=checkbox]` scan misses them.

## Trap: the confirm dialog's checkbox is 0×0

The bill-edit confirm ("Bill Summary") has a **"Send to QuickBooks"** checkbox, `#invoice-qb-sync`
/ `ng-model="payable.NeedsToBeSynced"`, **checked by default**. The real `<input>` has a zero-size
bounding box (it's visually replaced by a styled `<label for=…>`), so `getBoundingClientRect()` on
the input returns 0,0 and clicking there does nothing. Click the label instead:

```python
r = js("""(() => {
  const inp = document.querySelector('#invoice-qb-sync');
  const lbl = document.querySelector(`label[for="${inp.id}"]`);
  const b = lbl.getBoundingClientRect();
  return {x: Math.round(b.x + 8), y: Math.round(b.y + b.height/2)};
})()""")
click(r["x"], r["y"])
```

Then assert `js("document.querySelector('#invoice-qb-sync').checked")` is what you intended —
submitting with it checked pushes the bill to QuickBooks, which is not reversible from here.

## Capturing a save payload

`window.__cap` wrapper around `XMLHttpRequest.prototype.open/send` catches everything; filter to
`api.knowify.com` because the app also POSTs to rollbar, vitally, and `developers.knowify.com`
(its own telemetry, which conveniently mirrors each API call's body under `Data`).

## Trap: `updatePayable` is replace-not-update

Saving the edit form POSTs `Payables/updatePayable`, then `Indexing/allocatePayable {Id}`. The
**old bill id stops existing** and every line-item id changes. `NewId` in the response is
populated only sometimes — a null `NewId` still means the bill was replaced. Two things do not
survive on their own: the attached PDF (echo `SupportingDocuments` verbatim) and the generated
billable (regenerate with `Payables/createBillablesBill {Id}`; `allocatePayable` reports
"Bill Has Been Indexed" without creating one).

`Payables/updatePayableItem` accepts `{Id, PayableId, ClientId, DepartmentId, ProjectId,
MilestoneId}` and returns `DidSucceed:true` — but it **silently ignores `Description`**. It is an
allocation-only endpoint; don't use it to edit text.

## Useful reads

- `Payables/Get {Id}` — one bill incl. `Payable.PayableItems`, `SupportingDocuments`, `Comments`
- `Payables/searchPayablesIds {Sort, SortAsc, Search}` — id lookup by invoice number
- `Invoices/GetBillablesForProject {ProjectId, ClientId, StartDate, EndDate, SkipDates:true}` —
  exactly what the invoicing screen offers. `OriginOfBillable` is `PayableItem` /
  `ResourceTimeEntry` / `FixedDeliverable` / `PurchaseRequestItem`; `OriginOfBillableId` points at
  that source row. Already-invoiced billables drop out of this read, so a lower count than you
  expect on a billed job is normal.
