# Milkrun List And Table Extraction

## URLs

Milkrun list by receiving date:

```text
https://supplier.coupang.com/milkrun/milkrunList?page={page}&milkrunSearchType=RECEIVING_AT&startDate={arrival_date}&endDate={arrival_date}
```

Milkrun list by purchase order:

```text
https://supplier.coupang.com/milkrun/milkrunList?purchaseOrderSeq={purchase_order_seq}
```

## Table Contract

Selector:

```text
#milkrunListTable
```

Empty result marker:

```text
xpath=//td[normalize-space()='검색 결과가 없습니다.']
```

Extraction rules:
- Read `<th>` text for headers.
- For body rows, ignore `td` with `style="display:none"`.
- If a cell contains links, join link text with commas. This preserves purchase-order numbers the same way the previous parser expected them.
- Return a pandas `DataFrame` with the rendered headers.

## Pagination

For date-based list scans, start at page 1 and stop on an empty page. Do not reuse a previous page's table after navigation; wait for `#milkrunListTable` on every page.

## Flow Users

This table is shared by:
- Transaction statement downloads.
- Pallet attachment list downloads.
- Split milkrun precheck and saved-state verification.
- Pallet company saved-state verification.

Changing the parser can break filenames, split detection, and S3 upload grouping at the same time. Add focused tests before changing table extraction.
