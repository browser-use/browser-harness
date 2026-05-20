# Milkrun Transaction Statement Downloads

## URL

```text
https://supplier.coupang.com/milkrun/previewPOFiles?milkrunSeq={comma_separated_milkrun_seq}
```

## Flow

1. Read milkrun rows from the date-filtered list.
2. Group by active origin from constants.
3. Sort by logistics center.
4. Split seqs by `Constants.MILKRUN_PREVIEW_BATCH_SIZE`.
5. Navigate to `previewPOFiles`.
6. Use `download_current_pdf()`.
7. Rename with the existing deterministic filename contract:
   - order type: milkrun
   - document name: transaction statement
   - origin
   - arrival date
   - `partNN` suffix only when chunked
8. Upload using the existing Coupang S3 key generator.

Do not Selenium fallback on failure. A fallback can create duplicate PDFs and duplicate S3 writes.

## Known Failure Shape

If `previewPOFiles` does not produce a PDF, capture artifacts with:

```text
download-milkrun-attached-files
```

Include `#milkrunListTable`, login selectors, and any PDF viewer/print selectors in selector probes.
