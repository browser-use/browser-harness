# Uploads

Order of attack for file uploads:

1. **Existing `input[type=file]`** — even hidden ones. `upload_file('input[type=file]', '/abs/path')` (CDP `DOM.setFileInputFiles`) works without any dialog appearing.
2. **No file input in the DOM** (input created on demand): enable interception *before* clicking the trigger, then feed the chooser from the event:

   ```python
   cdp("Page.setInterceptFileChooserDialog", enabled=True)
   click(x, y)  # the Upload button/tile
   wait(1)
   evs = [e for e in drain_events() if e.get("method") == "Page.fileChooserOpened"]
   if evs:
       cdp("DOM.setFileInputFiles", files=["/abs/path"],
           backendNodeId=evs[-1]["params"]["backendNodeId"])
   cdp("Page.setInterceptFileChooserDialog", enabled=False)
   ```

   Without interception the native macOS chooser opens and CDP cannot drive it.
3. **Click produced no `fileChooserOpened` event**: the thing you clicked is not the trigger. Common cause: a stale/stuck attachment preview occupying the slot — remove it first (look for a small X button) and a real `input[type=file]` often appears (see `domain-skills/openai-ads/ads-manager.md` for a field example).

Verify after upload: re-query the preview element (`img.naturalWidth > 0`, `complete === true`) or re-screenshot — do not assume the set call worked.

Drag-and-drop-only dropzones: see `drag-and-drop.md`; synthesize a `DataTransfer` via JS or fall back to `DOM.setFileInputFiles` on the dropzone's hidden input.
