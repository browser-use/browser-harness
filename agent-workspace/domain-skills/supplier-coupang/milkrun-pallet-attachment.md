# Milkrun Pallet Attachment Labels

## List Button

Selector:

```text
xpath=//span[@name='printMilkrunLabalForPda' and @milkrun-seq='{milkrun_seq}']
```

The original browser behavior is:

```text
Coupang JS builds HTML -> window.open -> new window document.write -> print() -> Chrome auto-save
```

The CDP/browser-harness path captures this more directly:

```text
stub window.open -> capture document.write HTML -> render captured HTML in temporary CDP tab -> Page.printToPDF
```

Do not assume byte-identical output versus Chrome's print dialog. Treat it as acceptable only when:

- The captured HTML contains the expected marker, currently `Milkrun(밀크런) 팔레트 부착 리스트`.
- A focused PDF/content regression or manual inspection confirms the rendered document is functionally equivalent.
- Filename, merge, and S3 upload contracts remain unchanged.

## Handler Pitfall

The label click handler may be bound through jQuery or inline script. The current harness helper tries:

1. Native click on the element.
2. Invoke jQuery click handlers from `$._data(element, "events").click`.
3. Locate the inline `span[name='printMilkrunLabalForPda']` handler and call it with the target element.

If the helper fails, capture failure artifacts with the label selector before changing the print path again.

## Merge And Upload

After individual pallet attachment PDFs are renamed, merge by active origin using the existing PDF merge helper. If a given origin has no files, log and skip upload.

Do not change merge filenames or S3 key shape unless the downstream contract is updated with tests.
