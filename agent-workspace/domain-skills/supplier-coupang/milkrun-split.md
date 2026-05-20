# Milkrun Split And Pallet Company Save

## Entry Points

Start from a purchase order number:

```text
https://supplier.coupang.com/milkrun/milkrunList?purchaseOrderSeq={purchase_order_seq}
```

Split form:

```text
https://supplier.coupang.com/milkrun/splitform?milkrunSeq={milkrun_seq}
```

Pallet company edit form:

```text
https://supplier.coupang.com/milkrun/saveform?milkrunSeq={milkrun_seq}
```

## Precheck

- If the milkrun list already has a row with 출고지 `양주시_1`, treat the order as already split and skip split save.
- If no source row exists for 출고지 `이천시_4`, fail fast.
- Use the list table parser from `milkrun-list.md`.

## Location Modal Pitfall

The button:

```text
#supplierMilkrunLocationBtn
```

often logs a click but fails to load the modal content. Reliable sequence:

1. Wait for optional jQuery click handler.
2. JS click `#supplierMilkrunLocationBtn`.
3. Wait for actual location rows, not only for the text `정보 조회`.
4. If rows do not load, fetch the split location list endpoint and inject it into `#detailLayer`, then show `#location-modal`.
5. Retry the open/load path several times before failing.

Important: hidden modal DOM can still contain `h4 정보 조회`. Do not use text existence alone as proof that the modal is open or closed. Verify `#supplierMilkrunLocationSeq` value and visible modal state.

## Split Save Sequence

1. Select `양주시_1` from `#purchaseOrderTable` by extracting `locationName_<seq>`.
2. Click `button[name='selectLocation'][data-supplier-milkrun-location-seq='<seq>']`.
3. Wait until `#supplierMilkrunLocationSeq` equals the selected seq and `#location-modal` is no longer visible.
4. Read `tr[name='milkrunPalletDto']` and its `data-milkrunpalletseq`.
5. Use the bulk-fill buttons:
   - `button[name='milkrunPalletBtn']` then `#cntCopy_<pallet_seq>`
   - `button[name='milkrunBoxCountBtn']` then `#boxCntCopy`
   - `button[name='milkrunWeightBtn']` then `#weightCopy`
6. For each `tr[name='milkrunPoTr']`, remove the correct side:
   - PO being split: `#milkrunPoDelBtn{po}` and wait for `span[name='milkrunPoLabel{po}']` hidden.
   - PO staying behind: `#copyPoDelBtn{po}` and wait for `label[name='milkrunPoLabel{po}']` hidden.
7. Save with `#saveButton` using optional jQuery handler wait and JS click.

If no alert appears after save, verify the milkrun list shows the expected `양주시_1` row before treating the save as success.

## Pallet Company Change

For the split row:

1. Open `saveform?milkrunSeq=<split_row_seq>`.
2. Select `#pltRentalCompany`.
3. Check dynamic milkrun guideline checkboxes.
4. Save with `#saveMilkrun` using optional jQuery handler wait and JS click.
5. If no alert appears, verify the list/saveform shows the saved pallet company.

Field-tested lesson: `2026-05-26` split `마장1` to `양주시_1`, row `10235934`, pallet company `아주팔레트`.
