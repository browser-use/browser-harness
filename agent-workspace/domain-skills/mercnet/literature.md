# Mercury MercNET - Literature Lookup

Field-tested on the authenticated MercNET literature page in July 2026.

## Scope and access

- Literature page: `https://mercnet.mercurymarine.com/us/en/service-and-warranty/literature.html`
- Attach to the user's existing authenticated browser session.
- If MercNET redirects to an authentication wall, stop and ask the user to sign in. Do not source or type credentials from screenshots, files, or logs.
- MercNET may require acceptance of a copyright notice before search results are available. Treat retrieved dealer literature as authorized service material. Do not assume it can be republished, redistributed, or exposed on a public site.
- Keep the workflow read-only. Literature lookup and authorized internal download do not require cart, order, account, warranty, or profile changes.

## Search by document number

The stable selector values on the literature form are:

- Search type: `#searchBy`
- `Document Item Number`: value `4`
- Document-number input: `#documentPartNumber`

Mercury publication covers often print a publication prefix such as `90-`. Omit that prefix in the search field while retaining the intrinsic document number. For example, search `8M0237508`, not `90-8M0237508`.

Use the exact document item number. A valid historical number can return no records after Mercury removes or supersedes it, so a zero-result search is not proof that the publication never existed.

## Read-only literature endpoint

The page calls a same-origin JSON endpoint:

```text
GET /bin/mercnet/literature
    ?actionType=retrieveLiterature
    &consumerFlag=false
    &language=EN
    &documentNumber={DOCUMENT_NUMBER}
```

Equivalent lookups are available with one of these parameters in place of `documentNumber`:

```text
serialNumber={SERIAL_NUMBER}
modelNumber={MODEL_NUMBER}
```

From an authenticated MercNET page:

```python
import json

document_number = "8M0000000"
url = (
    "/bin/mercnet/literature"
    "?actionType=retrieveLiterature"
    "&consumerFlag=false"
    "&language=EN"
    f"&documentNumber={document_number}"
)
data = js(f"fetch({url!r}).then(r => r.json())")
print(json.dumps(data, indent=2))
```

Useful response fields:

- `literature`: documents matched to the requested document, serial, or model.
- `productLineLiterature`: broader product-line documents returned with a serial or model lookup.
- `docHost`: base URL for document files.
- `docPartNbr`: Mercury document item number.
- `docName`: publication title.
- `dtpDescription`: document type such as `SERVICE MANUALS` or `OWNERS MANUALS`.
- `docWorldviewFile`: file path relative to `docHost`.

Prefer `docHost + docWorldviewFile` when building a file URL. On the current site, same-origin paths also use `/mnetdata/` followed by `docWorldviewFile`.

## Finding the current manual when an old number is missing

If an exact document-number search returns no records:

1. Search a known engine serial number when available.
2. Otherwise search an exact Mercury model number.
3. Inspect the engine-specific `literature` bucket before the broader `productLineLiterature` bucket.
4. Filter by `dtpDescription`, title, engine family, horsepower, and starting serial number.
5. Validate the PDF title page before treating the result as a replacement.

Do not infer supersession from title similarity alone. A service manual, diagnostic manual, owner manual, and service advisory can overlap in engine scope while serving different purposes.

## Product selector endpoints

The literature page's cascading product selector uses these read-only endpoints:

```text
/bin/mercnet/flatrateinquiry/productlines
/bin/mercnet/flatrateinquiry/productyears?productline={PRODUCT_LINE}
/bin/mercnet/flatrateinquiry/producthpgroups?productline={PRODUCT_LINE}&productyear={PRODUCT_YEAR}
/bin/mercnet/flatrateinquiry/productitemnumbers?productline={PRODUCT_LINE}&productyear={PRODUCT_YEAR}&producthpgroup={HP_GROUP}
```

Values such as year buckets and horsepower groups must be passed exactly as returned. URL-encode spaces and punctuation instead of normalizing display labels.

## Authorized internal download

For a file the authenticated user is authorized to retain internally, let Chromium handle the download:

```python
output_dir = "/absolute/approved/output"
file_url = "/mnetdata/" + result["docWorldviewFile"]
file_name = result["docPartNbr"] + ".pdf"

cdp(
    "Browser.setDownloadBehavior",
    behavior="allow",
    downloadPath=output_dir,
    eventsEnabled=True,
)

meta = js(f"""
fetch({file_url!r}).then(async r => {{
  if (!r.ok) throw new Error(`HTTP ${{r.status}}`);
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = {file_name!r};
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 30000);
  return {{name: {file_name!r}, size: blob.size, type: blob.type}};
}})
""")
print(meta)
```

After download, confirm that no `.crdownload` remains and validate the PDF with `pdfinfo` plus title-page text extraction. Check publication number, date, engine family, horsepower, starting serial, page count, encryption status, and file size.

## Gotchas

- The document number displayed on a cover may include a `90-` publication prefix that the search field does not want.
- Search results can include both engine-specific and product-line-wide literature. Do not mistake a generic network or rigging manual for the engine diagnostic manual.
- A current service advisory may revise fault behavior after the diagnostic manual's publication date. Search the serial or model result for newer advisories before treating a manual's fault table as current.
- PDF filename capitalization is inconsistent. Always use the exact `docWorldviewFile` returned by MercNET.
- A successful HTTP response and plausible filename are not enough; validate the PDF's internal title page.
