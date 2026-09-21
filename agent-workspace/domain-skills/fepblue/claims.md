# FEPBlue — stage a domestic medical claim

Field-tested against the authenticated MyBlue domestic medical-claim wizard.
Use the existing local Chrome session and stop for login or MFA. Never perform a
final attestation or Submit action unless the user explicitly authorizes that
specific action.

## Safe staging boundary

A resumable staging flow should:

1. Snapshot every claim field locally before browser entry.
2. Complete the patient, coverage, employment, diagnosis, provider, date, and
   charge steps.
3. Upload already-validated attachments.
4. Continue to the final review screen.
5. Re-read patient, provider, service range, total, disclosures, and uploaded
   filenames from the review page.
6. Stop before final attestation and Submit.

The wizard may not retain attachments in drafts. Keep the local snapshot and
attachment checksums so a lost tab or expired session can be reconstructed
without re-discovering source documents.

## Stable charge fields

The first charge section has used these ids:

| Field | Selector |
|---|---|
| Provider making charge | `#nameOfProviderMakeingCharge-1` |
| Description | `#descriptionOfCharge-1` |
| From date | `#fromDate-1` |
| To date | `#toDate-1` |
| Charge | `#charge-1` |

Prefer accessible labels for the earlier patient and coverage steps. Verify
each value after input and after every Continue action. Do not silently rewrite
a provider or employer value when the portal reports a validation error; a
portal-safe alias must be an explicit, saved configuration value.

## Uploads

The attachment control may be visually hidden. Set it directly through CDP:

```python
paths = ["/absolute/path/attachment-1.pdf"]
upload_file('input[type="file"]', paths)
wait_for_element("body", timeout=10)
if "File uploaded" not in (js("document.body.innerText") or ""):
    raise RuntimeError("portal did not confirm the attachment")
```

Observed native limits are five files, 5 MB per file, and 25 MB total. Validate
limits, page counts, renderability, and checksums before opening the wizard.

## Outcome handling

- A visible success result is durable evidence even when no confirmation number
  is shown. Record it as accepted and block retries.
- A timeout or navigation loss with no knowable result is uncertain and also
  blocks retries.
- Reconcile accepted submissions later from claim history using patient,
  provider, amount, and service range. Mutate state only on one unambiguous
  match.
- A generic provider-name validation message proves only that the submitted
  value was rejected; do not infer the portal's hidden validation algorithm.
