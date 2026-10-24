# gemini.google.com — Nano Banana image generation/editing

## Model picker
- Composer dropdown offers Flash-Lite / Flash / Pro tiers. Pick **Pro** before an image task to route to Nano Banana Pro (higher fidelity, runs a "Verifying Label Accuracy" thinking stage on product photos).
- There is no explicit "Nano Banana" entry; attaching an image + asking for an edit invokes it.

## CSP traps (field-tested)
- Page CSP blocks `fetch`/XHR **and** `img-src` to `http://localhost:*`. You cannot inject local files by fetching from a local server inside page JS.
- There is **no persistent `input[type=file]`** in the DOM. The "+" menu's "Upload files" item opens a native picker — dead end for automation.
- Synthetic `DragEvent` with a `DataTransfer` file on `rich-textarea` does not attach (and you can't build the File without bytes anyway, per CSP).

## Attaching a local image (works)
1. Put the image on the OS clipboard (macOS: `osascript -e 'set the clipboard to (read (POSIX file "/path/img.jpg") as JPEG picture)'`).
2. Make the Gemini tab frontmost and click into the composer.
3. Trigger `await navigator.clipboard.read()` in page context via CDP. First call may hang ~45s on a permission grant; after it resolves the image appears as a composer attachment.

## Extracting generated images (works, no download dialog)
- Generated images are `blob:` URLs, typically 825x1024. `curl` can't fetch them.
- In page JS: draw the `<img>` to a canvas (same-origin, not tainted), `canvas.toBlob('image/png')`, then `navigator.clipboard.write([new ClipboardItem({'image/png': blob})])`.
- On the host: save clipboard to file — `osascript -e 'write (the clipboard as «class PNGf») to f'`. Repeat per image.
- Select images with `document.querySelectorAll('img')` filtered by `naturalWidth > 700`; DOM order is chronological.

## Waits / verification
- Generation takes 60–120s. Poll `get_page_text`-style DOM text: the trailing "Gemini said" block stays empty until the response lands. Screenshots of a long thread can appear frozen while streaming — trust the DOM text.
- Nano Banana reproduces large label text faithfully but **garbles small print** (bilingual sublines, nutrition text) and repeated "fix the spelling" prompts do not converge on tiny text. Plan to crop, blur, or composite real labels if small print must be exact.

## Misc traps
- An "Animate this image" suggestion chip appears near the composer after an image result; a stray click generates a 10s video.
- Enter submits; verify a new "You said" bubble exists before waiting on a response — typed text can silently fail to submit if focus moved.
