# Uploads

Attach a local file to an `<input type="file">` without touching the OS file
picker. Never click the "Choose File" button — that opens a native dialog the
browser process owns and CDP cannot drive.

## The one move

`DOM.setFileInputFiles` sets the input's `FileList` directly and fires the
`change` event the page is listening for.

```python
import os

path = os.path.abspath("banner.png")          # must be absolute
doc  = cdp("DOM.getDocument", depth=-1)
node = cdp("DOM.querySelector",
           nodeId=doc["root"]["nodeId"],
           selector='input[name="about_us_banner"]')
cdp("DOM.setFileInputFiles", files=[path], nodeId=node["nodeId"])
```

Then verify from the page's own point of view:

```python
js("""
(() => {
  const e = document.querySelector('input[name="about_us_banner"]');
  return e.files.length + " " + (e.files[0] ? e.files[0].name : "-");
})()
""")
```

`files.length == 1` means the page really sees the file. A screenshot does
not prove this — many sites style the native input away and show their own
label, which does not update.

## Details that bite

- **Absolute paths only.** A relative path is resolved against the browser
  process's cwd, not yours, and usually fails silently with `files.length == 0`.
- **Multi-file inputs** take several entries: `files=[a, b, c]`. For a
  single-file input, passing more than one is an error.
- **The node must exist when you query it.** Inputs revealed by a toggle or
  inside a lazily-rendered tab are not in the DOM yet — reveal them, wait,
  then `DOM.querySelector`.
- **Node ids go stale on navigation.** Any save that reloads the page
  invalidates the `nodeId`. Re-run `DOM.getDocument` after every reload;
  reusing an old id raises "No node with given id found".
- **Hidden inputs still work.** `setFileInputFiles` does not require the
  input to be visible, so the common "invisible input + styled label" pattern
  needs no special handling — target the real input, ignore the label.
- **Drag-and-drop dropzones** that never render an `<input type="file">` are
  the exception; those need a synthetic `DataTransfer` in page JS instead.

## Generating a file to upload

Nothing stops you from creating the asset first — Pillow for images, a
heredoc for text/CSV — then pointing `setFileInputFiles` at it. Write it to
the scratchpad, not the repo.
