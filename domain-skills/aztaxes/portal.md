# AZTaxes.gov (Arizona DOR business portal)

Classic ASP.NET site — native selects, full-page posts, `element.click()` from `js()` works
everywhere. No React/iframe tricks needed. Field-tested 2026-06 on the TPT e-file flow.

## Routes

```text
https://www.aztaxes.gov/Home/Page                 # public home
https://www.aztaxes.gov/Home/Login                # Business User Login (email -> Next -> password)
https://www.aztaxes.gov/Home/BusinessList         # post-login landing
https://www.aztaxes.gov/Home/BusinessDetails?id_internal_business=<id>
https://www.aztaxes.gov/Home/LocationListStatic?...&licenseNumber=...&idAcct=...
https://www.aztaxes.gov/Home/EFileHistory         # all e-filed returns
https://www.aztaxes.gov/Home/FormDisplay?formId=<guid>&formType=FormTPT2&ViewerType=TptViewer
https://www.aztaxes.gov/Home/ChooseLicense        # File a TPT return: license/year/month
https://www.aztaxes.gov/Home/TPT2LocationList?formId=<guid>      # draft return: per-location
https://www.aztaxes.gov/Home/EnterLineItems?formId=<guid>&locationCd=001
https://www.aztaxes.gov/Home/AddLineItem?formId=<guid>&locationCd=001&regionCode=MAR&busClass=025&redirectCmd=Edit
```

`/Security/Login.aspx` redirects to `/Home/Login` — use the latter.

## Traps

- **DataTables pagination**: tables (e-file history, locations) keep only the CURRENT page's
  rows in the DOM. Searching rows by text silently misses entries on other pages. Fix first:

  ```js
  const s = document.querySelector('select');           // the "Show N entries" select
  s.value = s.options[s.options.length-1].value;
  s.dispatchEvent(new Event('change', {bubbles:true}));
  ```

- **Filed returns render on `<canvas>`** (PDF.js-style viewer, one canvas per page, ~5 pages
  for a TPT-2). Viewport clip-screenshots only catch page 1 — the rest scroll inside a
  container. Extract every page losslessly instead:

  ```python
  data = js("document.querySelectorAll('canvas')[0].toDataURL('image/png').slice(22)")
  open("/tmp/p1.png","wb").write(base64.b64decode(data))
  ```

- **Period selection selects** (`/Home/ChooseLicense`): ids `licenseId`, `yearId`, `monthId`.
  `licenseId` option VALUE is an internal account id, not the license number (label shows the
  license). `monthId` values are `1`–`12`, not zero-padded. Set value + dispatch `change`.

- **TPT-2 line-item form** (`AddLineItem`): inputs `gross_0`, `deduction_0`, `nettaxable_0`,
  `taxrate_0`, `totaltax_0`. Set `gross_0` and dispatch `input`+`change`+`blur` — the page
  recomputes net taxable and total tax automatically. "Save And Close" persists into the draft;
  nothing is filed until the separate review/submit flow.

- A filing-period banner (`Filing Period: MM/DD/YYYY - MM/DD/YYYY`) is on every draft screen —
  verify it before entering data; drafts for the wrong period look identical otherwise.
