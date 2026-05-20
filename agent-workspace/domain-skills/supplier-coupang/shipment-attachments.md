# Shipment Attachment Downloads

## URL

```text
https://supplier.coupang.com/ibs/asn/active?type=parcel
```

Ready selector:

```text
#edd
```

Search:

1. Fill `#edd` with arrival date.
2. Click `#shipment-search-btn`.
3. Wait for load or table refresh.

## Download Contract

The public shipment attachment document path is CDP-only and must not fall back to Selenium on failure. It should:

1. Start with a clean download folder snapshot.
2. Search by arrival date.
3. Download generated shipment attachment files.
4. Preserve existing filenames, merge behavior if any, and S3 key generation.
5. Clear or reset download state after completion.

## Registration Boundary

Do not use the shipment attachment download conversion as proof for other shipment workflows. Shipment bulk registration is its own side-effecting route; use `shipment-bulk-register.md`.

Retained `_selenium` helper variants may still exist in the bot for legacy comparison, but the public shipment attachment download and public shipment bulk registration routes are CDP-only and should fail fast with artifacts rather than falling back.
