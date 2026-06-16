# QuickBooks Online Custom Report PDF Export

Field-tested on QBO custom reports in a logged-in Chromium-family browser on 2026-05-06.

## Fast Path

For clean QBO custom-report PDFs, use the visible QBO export flow, then save the PDF blob directly:

1. Open the saved custom report.
2. Set the visible date inputs, then click `refresh-report`.
3. Set the required report expansion state.
4. Click QBO report toolbar `Export` -> `Export to PDF`.
5. Wait for the generated `blob:https://qbo.intuit.com/<uuid>` PDF target.
6. Fetch that blob from the QBO page origin and write the bytes locally.
7. Validate with `pdftotext` when report content matters.

Do not use CDP `Page.printToPDF` for QBO reports. It prints the surrounding QBO shell, not the clean report body. Do not use the native `Save as PDF` sheet unless the QBO PDF blob is unavailable.

## Browser Attachment

- Use the real logged-in browser profile that has the QBO session.
- If that session is in a non-default Chromium browser, start it with a known remote-debugging port and pass `BU_CDP_URL` or `BU_CDP_WS` to Browser Harness.
- Computer Use is only a fallback for native OS sheets, visual confirmation, or unexpected QBO UI blockers. It is not part of the normal fast path.
- After a browser restart, QBO may restore a stale report tab. Always read the visible report period before exporting.

Example attachment pattern for a dedicated browser endpoint:

```bash
BU_NAME=qbo BU_CDP_URL=http://127.0.0.1:9223 browser-harness -c 'print(page_info())'
```

## Report State

- Custom reports list route: `https://qbo.intuit.com/app/customreports`.
- Saved custom report builder routes look like `/app/report/builder?rptId=sbg:<uuid>&type=user`.
- Date fields are normal visible inputs. Their format follows the QBO/user locale; one tested locale used `dd.mm.yyyy`.
- After setting dates, click the report toolbar `refresh-report`.
- Verify report readiness from visible text: `<report name> report is ready`.
- QBO can move toolbar buttons when the report width/state changes. Locate `Export` from the current screenshot/DOM instead of reusing old coordinates.

## Compact Menu

Use the report toolbar `Compact` dropdown. It commonly contains:

- `Compact View`
- `Normal View`
- `Expand All`
- `Collapse All`

For a summary PDF with one visible grouping layer, choose `Collapse All`, then expand the top report group manually. Verify summary rows are visible and transaction-detail rows are not.

For a detailed PDF, choose `Expand All` and verify transaction rows are visible.

Useful post-state check:

```python
rows = js("""
return Array.from(document.querySelectorAll("table tr, [role=row], div"))
  .map(r => r.innerText.trim().replace(/\s+/g, " "))
  .filter(Boolean)
  .slice(0, 200)
""")
```

## PDF Export

- QBO `Export` -> `Export to PDF` produces the clean report PDF.
- This path may not fire a normal Chromium `Browser.downloadProgress` event, so `Browser.setDownloadBehavior` alone is not enough.
- QBO opens an in-page PDF modal using Chromium's built-in PDF viewer. The actual report PDF appears as a child `blob:https://qbo.intuit.com/<uuid>` target.
- The modal's `Save as PDF` button can open a native OS save sheet. Avoid that by fetching the blob directly.
- Fetching the blob too early can return no value; wait briefly after clicking `Export to PDF`.

Blob-save template:

```python
import base64, json, os, time

def latest_qbo_pdf_blob():
    blobs = [
        t["url"]
        for t in cdp("Target.getTargets")["targetInfos"]
        if t.get("url", "").startswith("blob:https://qbo.intuit.com/")
    ]
    return blobs[-1] if blobs else None

def save_qbo_pdf_blob(out_path, timeout=30):
    deadline = time.time() + timeout
    blob = None
    while time.time() < deadline:
        blob = latest_qbo_pdf_blob()
        if blob:
            break
        wait(0.5)
    if not blob:
        raise RuntimeError("QBO PDF blob did not appear")

    wait(2)  # let the PDF viewer finish loading the blob
    meta = js(f"""
    return fetch({json.dumps(blob)}).then(async r => {{
      const b = await r.blob();
      const ab = await b.arrayBuffer();
      const u8 = new Uint8Array(ab);
      let s = "";
      for (let i = 0; i < u8.length; i += 0x8000) {{
        s += String.fromCharCode(...u8.subarray(i, i + 0x8000));
      }}
      window.__qbo_pdf_b64 = btoa(s);
      return {{
        ok: r.ok,
        status: r.status,
        type: b.type,
        size: b.size,
        b64len: window.__qbo_pdf_b64.length
      }};
    }});
    """)
    if not meta or meta.get("type") != "application/pdf":
        raise RuntimeError(f"unexpected QBO blob metadata: {meta}")

    parts = []
    for i in range(0, meta["b64len"], 8000):
        parts.append(js(f"return window.__qbo_pdf_b64.slice({i},{i + 8000})"))

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    pdf = base64.b64decode("".join(parts))
    with open(out_path, "wb") as f:
        f.write(pdf)
    return {"path": out_path, "size": len(pdf), "blob": blob}
```

End-to-end outline:

```python
# 1. Use screenshot/DOM to click report toolbar Export.
# 2. Click menu item "Export to PDF".
# 3. Save the latest QBO PDF blob.
save_qbo_pdf_blob("/abs/output/report.pdf")
```

## Validation

Use local PDF tools for high-confidence runs:

```bash
pdfinfo /abs/output/report.pdf
pdftotext /abs/output/report.pdf -
```

Checks that catch common failures:

- PDF header starts with `%PDF`.
- `pdftotext` includes the expected report title and date range.
- Summary exports include the expected summary rows.
- Detailed exports include transaction-date/detail rows.
- The text does not include QBO shell/navigation labels, which indicates `Page.printToPDF` was used accidentally.
