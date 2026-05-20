# Milkrun Bulk Registration

## URL

```text
https://supplier.coupang.com/milkrun/batchRegister?warehousingPlannedAt={arrival_date}
```

Expected ready selector:

```text
#batchRegisterMilkrun
```

## Blocking Notice Modal

The page may show a visible `접수 주의사항` Bootstrap dialog. This modal is async and can keep the close button disabled until `#checkbox` is checked.

Reliable close pattern:
- Find visible `.modal` / `.bootstrap-dialog`.
- Click/check `input#checkbox` or visible checkbox inputs.
- Dispatch `input` and `change`.
- If the close/confirm button is still disabled while `input#checkbox:checked` is true, remove the disabled state.
- Click close/confirm.
- Remove stale `.modal-backdrop`.
- Wait for a quiet period with no visible `접수 주의사항`.

Do not click through the business form while this modal is still visible.

## Per-row Entry

For each Supplier Hub row:

1. Match the center name to Google Sheet data.
2. Compare Supplier Hub PO numbers with sheet PO numbers before entering data.
3. If `#completeRegistration_{row_index}` exists, treat the row as already registered and skip it.
4. Click `#releaseAddressImport_{row_index}` and wait for the visible `출고지 선택` dialog.
5. Find the warehouse cell in `#purchaseOrderTable` and extract the location seq from `locationName_<seq>`.
6. Click `button[name='selectLocation'][data-supplier-milkrun-location-seq='<seq>']`.
7. Wait until `#supplierLocationSeq_{row_index}` equals the seq and the dialog is closed.
8. Fill boxes, pallet rows, weight, contents, allocation reply, and pallet rental company.

## Pallet Add Button Pitfall

`#addPallet_{row_index}` can log as clicked while no row is added. The stable sequence is:

1. Wait for the element.
2. Prefer waiting for a jQuery click handler via `$._data(element, "events").click`.
3. Click the button and then trigger the jQuery click if the row count did not increase.
4. Verify `#palletBody_{row_index} tr` increased.
5. If the site handler is absent or does not add a row, use the local DOM fallback that inserts the same input shape (`length`, `width`, `height`, `count`) expected by the save endpoint.

Do not proceed to save unless the row count and pallet inputs are verified.

## Guidelines Checkboxes

The guidance checkbox count is dynamic. Do not assume fixed IDs `milkrunGuidCheck1..4`.

Find:

```text
input[name='milkrunGuideCheckBox'], input[id^='milkrunGuidCheck']
```

Click unchecked boxes and dispatch `change`. Raise if no checkbox is found or a checkbox remains unchecked.

## Save

Save selector:

```text
#batchRegisterMilkrun
```

Reliable save pattern:
- Install dialog capture before save.
- Wait for jQuery click handler on `#batchRegisterMilkrun`.
- Use JS click.
- Accept the completion alert if it appears.
- If no alert appears, verify `completeRegistration_*` markers instead of retrying blindly.

If zero rows changed because all matching rows already have completion markers, skip save. This avoids duplicate registration.

Field-tested lesson: 입고예정일 `2026-05-26` completed 12/12 rows through this path.
