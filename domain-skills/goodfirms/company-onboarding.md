# GoodFirms company onboarding

- Account and company-management flows may use different hosts. Inspect navigation to the current `myaccount.goodfirms.co` application instead of assuming the older `account.goodfirms.co` signup route is still the main flow.
- Company management can lead to `/users/update-listing` with General, Locations, Services and Client Industries stages.
- A rich description uses `.ck-editor__editable[contenteditable=true]`; trusted typing updates editor state more reliably than replacing innerHTML.
- Save & Next validation can require tagline, founding year, employee range and hourly-rate category. A label asterisk alone does not establish which validation stage enforces a field such as phone; inspect the actual error before declaring a blocker.
- Employee categories may split an approximate user-provided range. Preserve uncertainty rather than choosing a category that adds an unsupported fact.
