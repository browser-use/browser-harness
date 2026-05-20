# Downloads

Separate real browser-triggered downloads from native OS save/open dialogs and direct `http_get(...)` fetches.

## What Browser Harness can save directly

Use CDP `Browser.setDownloadBehavior` when clicking a page control causes Chromium to start an actual download (`Content-Disposition: attachment`, `<a download>`, blob URL download, app-generated file download, etc.). This avoids the browser's normal download prompts and writes into a known folder.

```python
import os, time

DL = "/abs/path/to/downloads"
os.makedirs(DL, exist_ok=True)

cdp("Browser.setDownloadBehavior",
    behavior="allow",
    downloadPath=DL,
    eventsEnabled=True)
drain_events()  # clear stale download/network events

before = set(os.listdir(DL))

# Trigger the site's download: coordinate click, JS click, form submit, etc.
# click_at_xy(x, y)
# js("document.querySelector('a.download').click()")

deadline = time.time() + 60
completed = None
while time.time() < deadline:
    for e in drain_events():
        if e["method"] == "Browser.downloadProgress":
            p = e["params"]
            if p.get("state") == "completed":
                completed = p.get("filePath")
                break
            if p.get("state") == "canceled":
                raise RuntimeError(f"download canceled: {p}")
    if completed:
        break

    after = set(os.listdir(DL))
    new = [f for f in after - before if not f.endswith(".crdownload")]
    if new and not any(f.endswith(".crdownload") for f in after):
        completed = os.path.join(DL, sorted(new)[-1])
        break
    time.sleep(0.5)

if not completed:
    raise TimeoutError("download did not complete")

print("downloaded:", completed)
```

Rename after completion when the task requires a specific filename:

```python
target = os.path.join(DL, "report_2026-04_short.pdf")
os.replace(completed, target)
print(target)
```

## Signals that prove a download happened

- `Browser.downloadWillBegin` / `Browser.downloadProgress` events after `eventsEnabled=True`.
- A new file appears in `downloadPath`.
- No `.crdownload` files remain in the folder.
- The final file has a plausible extension/size; for PDFs, verify the header or run `pdftotext` when accuracy matters.

## Filename control

CDP can choose the folder reliably. The filename usually comes from the server (`Content-Disposition`), an `<a download>` attribute, or Chromium's blob/download naming logic. For deterministic task names, let the download finish, then `os.replace(...)` it to the requested name.

`behavior="allowAndName"` is useful for collision-free bulk downloads, but it names files by GUID. Use it only when you plan to map events and rename every file yourself.

## When to use `http_get(...)` instead

If the file URL is static and does not require browser-only state, skip the browser:

```python
data = http_get("https://example.com/file.csv")
open("/abs/path/file.csv", "w").write(data)
```

For authenticated apps, first check Network/XHR for the actual export request. If it can be replayed with cookies/headers, direct HTTP is faster and less fragile than driving the UI. If the file is generated only by page JS or a blob URL, use browser-triggered download instead.

## Native dialogs are not browser downloads

macOS/Windows file chooser and save sheets are outside the page DOM and are not JavaScript dialogs. Browser Harness cannot inspect or fill their fields through `page_info()`, `js(...)`, or normal CDP DOM commands.

Use Computer Use when the site flow opens a native OS sheet, for example:

- `Save As...` / `Save as PDF` from the browser print UI.
- A macOS save sheet asking for filename and folder.
- An OS file picker not backed by an accessible `<input type=file>` path.

Avoid Computer Use when possible by finding an actual download button, a private export endpoint, or a blob URL that triggers Chromium's download manager. If none exists, Harness can drive the web page up to the native sheet, then Computer Use handles the sheet.
