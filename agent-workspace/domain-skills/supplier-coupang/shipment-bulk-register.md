# Shipment Bulk Registration Upload

## Public Route

The public workflow is CDP-only:

```text
register_shipment(arrival_date)
  -> _register_shipment_cdp(arrival_date)
  -> upload page
  -> set upload options
  -> upload shipment register file
  -> jobs page status verification
```

Do not add Selenium fallback to this route. It uploads a file to Supplier Hub and can create duplicate shipment jobs.

## Upload URL And Options

Upload page:

```text
https://supplier.coupang.com/ibs/shipment/parcel/bulk-creation/upload
```

Ready selector:

```text
#upload-btn
```

Current option contract:

- `#deliveryCompany` = `D000006`
- trigger Chosen UI update with `chosen:updated`
- `#shipLocation` = `81745`
- `#shipDate` = arrival date minus one day
- `#shipTime` = `18:00`

## File Source

The use case generates the Coupang shipment bulk-register workbook and uploads it to S3 first. The Supplier Hub upload step downloads the first S3 key matching:

- arrival date
- sanitized order type `쉽먼트`
- search key `일괄등록`

Then it uploads that local file through:

```text
input[type='file']
```

Wait until `#upload-btn` exists and is not disabled before clicking.

## Upload Click

Selector:

```text
#upload-btn
```

The upload alert is not a required success marker. If no alert appears after clicking, continue to jobs-page verification instead of clicking upload again.

## Status Verification

Jobs page:

```text
https://supplier.coupang.com/ibs/shipment/parcel/bulk-creation/jobs
```

Ready selector:

```text
#shipmentsTable table tbody
```

Use an anchor time captured immediately before the upload click. The jobs page may display minute-level timestamps, so the verifier accepts rows from two minutes before the anchor.

Success marker:

- latest relevant row status contains `완료`
- no `button[name='show-failure-btn']`
- has `button[name='show-generated-shipment-btn']`

In-progress marker:

- status contains `진행중`; reload/poll until timeout.

Failure marker:

- status is not complete, or a failure button exists.
- include seq, upload time, filename, status, fail/generated button presence, and `data-cause` if present.

## Login Recovery

If the workflow blocks on login before reaching the upload page, no Supplier Hub upload has happened yet. It is safe to complete or repair login and let the same process continue. Once `#upload-btn` is clicked, do not restart the upload path unless the jobs page proves there is no matching upload row.

Field-tested lesson: `2026-05-26` shipment bulk registration completed through CDP on `2026-05-20 17:30` KST. The run recovered from a login/password error before upload; after login recovery, the workflow clicked upload once and verified jobs status `완료`, no fail button, generated shipment button present.
