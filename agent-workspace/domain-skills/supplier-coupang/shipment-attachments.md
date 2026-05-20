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

## Remaining Legacy Area

Shipment registration/upload/status helpers still have retained Selenium variants in the bot. Treat them as legacy boundaries until each workflow has:

- A fake CDP/session contract test.
- A side-effect-safe saved-state verification marker.
- Failure artifacts on all CDP errors.
- No Selenium fallback for the public side-effecting route.

Do not use the shipment attachment download conversion as proof that shipment registration/upload is already browser-harness complete.
