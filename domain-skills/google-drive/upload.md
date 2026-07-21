# Google Drive — uploading a local file into a folder

Tested 2026-06 on drive.google.com (logged-in session, 75 MB mp4).

## The reliable flow: intercept the file chooser

Drive keeps **zero** `<input type="file">` elements in the DOM until the upload
menu is used, and clicking "New → File upload" opens the **native** macOS file
picker, which CDP cannot drive. Intercept the chooser instead:

```python
goto("https://drive.google.com/drive/folders/<FOLDER_ID>")
wait_for_load(20); wait(2)

cdp("Page.enable")
cdp("Page.setInterceptFileChooserDialog", enabled=True)
drain_events()  # clear buffer

# "New" button — stable hook: guidedhelpid attribute
r = js("""(()=>{const b=document.querySelector('[guidedhelpid="new_menu_button"]');
  if(!b)return null;const x=b.getBoundingClientRect();
  return {x:x.x+x.width/2,y:x.y+x.height/2}})()""")
click(int(r["x"]), int(r["y"])); wait(1.0)

# menu item — MUST filter for visible rects (see traps)
item = js("""(()=>{
  const els=[...document.querySelectorAll('[role=menuitem]')].filter(e=>{
    const r=e.getBoundingClientRect();return r.width>0&&r.height>0});
  const it=els.find(e=>/file upload/i.test(e.textContent||''));
  if(!it)return null;const x=it.getBoundingClientRect();
  return {x:x.x+x.width/2,y:x.y+x.height/2}})()""")
click(int(item["x"]), int(item["y"])); wait(1.5)

evs = drain_events()
p = [e for e in evs if e.get("method")=="Page.fileChooserOpened"][-1]["params"]
cdp("DOM.setFileInputFiles", files=["/abs/path/file.mp4"], backendNodeId=p["backendNodeId"])
cdp("Page.setInterceptFileChooserDialog", enabled=False)  # ALWAYS restore
```

Upload starts immediately into the folder the tab is viewing.

## Waiting for completion

Drive shows a bottom-right toast: "Uploading 1 item" → "1 upload complete".
Poll its text instead of guessing timing:

```python
js("""(()=>[...document.querySelectorAll('div,span')].map(e=>e.textContent||'')
  .filter(x=>/upload (complete|cancelled)|Uploading \\d/i.test(x)).slice(-3))()""")
```

A 75 MB file completed in well under 30 s on a normal connection.

## Verifying for real

If a Google Drive MCP is connected, confirm out-of-band and compare byte size:
`search_files` with `title contains '<name>' and parentId = '<FOLDER_ID>'` —
the returned `fileSize` should equal the local file exactly.

## Traps

- **Stale invisible menus.** `[role=menuitem]` matches items from menus that
  were closed earlier in the session (and even video-player context menus).
  Always filter `getBoundingClientRect().width > 0` before text-matching, or
  you'll click a coordinate from a hidden node.
- **Keyboard shortcuts are unreliable cold.** Drive's documented upload
  shortcuts (Shift+U / "c then u") did not fire via CDP key events on a fresh
  folder view — focus lives in an offscreen container until the user interacts.
  The New-menu path works every time; don't burn cycles on shortcuts.
- **`Page.setInterceptFileChooserDialog` is sticky.** Turn it OFF after setting
  files or every later user-initiated picker in that tab silently breaks.
- **The user shares the browser.** Drive is usually open in their active
  session; between your tool calls they may navigate, select rows, or preview
  files in YOUR tab (it's activated and visible). Do the whole
  navigate→menu→intercept→set-files sequence in ONE script run, and verify
  via API rather than re-screenshotting the (possibly user-modified) tab.
- **`fileChooserOpened` carries `backendNodeId`** — pass it straight to
  `DOM.setFileInputFiles`; no DOM.getDocument/querySelector needed.
- The Drive MCP's `create_file` takes inline base64 only — fine for small
  files, not for videos (75 MB ≈ 101 MB base64, far past tool-call limits).
  That's why the browser path exists.
