# Gemini (gemini.google.com) — image generation with a reference photo

Drive the Gemini web app to generate/edit images from an uploaded reference photo. Works logged-in with the user's Chrome profile.

## URL patterns

- `https://gemini.google.com/app` — fresh chat. Navigate here again to start a new chat (each generation in its own chat keeps the reference image the original, not a prior edit).

## Uploading an image (no file input exists)

There is **no** `input[type=file]` in the DOM — the "+" menu opens a native picker (blocks CDP). Instead, dispatch a synthetic paste on the editor; Gemini handles pasted image files:

```js
const res = await fetch('data:image/jpeg;base64,' + window.__b64);
const file = new File([await res.blob()], 'ref.jpg', {type:'image/jpeg'});
const dt = new DataTransfer();
dt.items.add(file);
const editor = document.querySelector('div[contenteditable="true"]');
editor.focus();
editor.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
```

**Trap:** sending the whole base64 in one `js()` call breaks the daemon socket (~>500KB single JSON line → BrokenPipeError). Chunk it in:

```python
js("window.__b64 = ''")
for i in range(0, len(b64), 60000):
    js("window.__b64 += '%s'" % b64[i:i+60000])
```

Wait for the attachment thumbnail (`img.preview-image` / `uploader-file-preview-container`) before typing the prompt, then `type_text(prompt)` + `press_key("Enter")`.

## Detecting generation completion

Poll for the download button — it only appears when the image is done (~30–90s):

```python
btn = "Array.from(document.querySelectorAll('button')).find(b => (b.getAttribute('aria-label')||'') === 'Download full size image')"
# poll js("!!(%s)" % btn) every few seconds, timeout ~240s
```

While generating, the response area shows "Creating your image". Generated `<img>` gets class `image animate loaded` (blob: src, 768×1024 preview).

## Getting the image out — use the download button, not canvas

- `fetch(img.src)` on the blob URL fails ("Failed to fetch" — revoked/other context).
- Canvas `drawImage` + `toDataURL` works but only yields the 768×1024 preview.
- **The "Download full size image" button yields ~1792×2390** — much higher quality. Route the download:

```python
cdp("Browser.setDownloadBehavior", behavior="allow", downloadPath=DIR, eventsEnabled=True)
js("(%s).click()" % btn)
# poll DIR for a new file named Gemini_Generated_Image_*.png (ignore *.crdownload), then rename
```

## Notes

- Reference-photo likeness (faces) is preserved well when the prompt says to keep face/skin tone/features the same.
- Occasional generation stalls happen; a retry in a fresh chat (`goto /app` again) usually succeeds.
- Account/model matters: the "Pro" model selector was active in testing; image gen limits are per-account.
