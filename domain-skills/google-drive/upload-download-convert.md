# Google Drive / Slides: download, upload, convert

Field-tested mechanics for moving files in and out of Drive with an authenticated Chrome session.

## Download a Google Doc/Slides/Sheet as Office format

Export URLs: `https://docs.google.com/presentation/d/<id>/export/pptx` (also `/export?format=docx|xlsx` for docs/sheets).

- **Cookie replay does NOT work.** Reading cookies via `Network.getCookies` and replaying them through `urllib` returns the "Sign in - Google Accounts" wall, even with all `.google.com` cookies attached. Google's export endpoint needs more session state than the cookie jar carries.
- **What works: let Chrome download it.** Set a download directory, then navigate a tab to the export URL:

```python
cdp("Browser.setDownloadBehavior", behavior="allow", downloadPath=DL_DIR, eventsEnabled=True)
cdp("Page.navigate", url=export_url)
# poll DL_DIR until a non-.crdownload file appears and its size stabilizes
```

## Upload a local file to Drive

Drive has **no persistent `<input type="file">`** in its DOM — it's created on demand, so you can't just query and set it. Use file-chooser interception:

```python
cdp("Page.setInterceptFileChooserDialog", enabled=True)
drain_events()
click_at_xy(...)  # "+ New"
wait(1.5)
click_at_xy(...)  # "File upload" menu item
# poll drain_events() for Page.fileChooserOpened, then:
cdp("DOM.setFileInputFiles", files=[path], backendNodeId=evt["params"]["backendNodeId"])
```

An "Uploading 1 item" toast appears bottom-right with per-file progress. The uploaded file lands in My Drive root (`parentId` = the My Drive root id).

- Do the whole sequence (menu click → chooser event → set files) in ONE script invocation. Menus close and the daemon's attached tab can drift between invocations if the user is browsing.
- If the user is actively using Chrome, re-attach explicitly every script: find your tab via `list_tabs()` by URL substring, `switch_tab(targetId)`, and assert `page_info()["url"]` before any click.

## Convert an uploaded .pptx to a native Google Slides file

Open the uploaded file at `https://docs.google.com/presentation/d/<pptx-file-id>/edit` — Slides opens it in Office-compatibility mode (title shows a `.PPTX` badge, no Extensions menu). Two equivalent converters:

- **"Convert" button in the right rail** (bottom of the Slide/Image/Media/Uploads stack), or
- File → Save as Google Slides.

Either creates a NEW file (native Slides, `application/vnd.google-apps.presentation`) with the same title minus `.pptx`; the original .pptx stays behind.

**Trap: permissions do not carry over.** Sharing added to the .pptx (explicit user grants) is NOT inherited by the converted Slides file — it starts fresh with just the owner + domain default. Re-share the converted file.

## Renaming a Docs-editor file

Click the title field (top-left), `press_key('a', 4)` (cmd+A), `type_text(new_name)`, `press_key('Enter')`. Verified by the title box updating; no dialog involved.

## GAM note (not browser, but adjacent)

`gam user <email> add drivefile localfile <path> mimetype gpresentation` would upload+convert in one shot, but requires the GAM project to have Drive API service enabled — admin-directory-only GAM setups fail with "Drive API v3 Service/App not enabled". The browser path above is the fallback.
