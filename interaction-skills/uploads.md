# Uploads

Use `upload_file(selector, path)` for native file inputs, including inputs that
are visually hidden. The helper calls CDP `DOM.setFileInputFiles`, so it does
not need to open or automate an operating-system file picker.

```python
upload_file('input[type="file"]', "/absolute/path/document.pdf")
```

Pass a list for a multi-file control:

```python
upload_file(
    'input[type="file"][multiple]',
    ["/absolute/path/one.pdf", "/absolute/path/two.pdf"],
)
```

## Before upload

- Resolve every path to an absolute path.
- Verify the file exists, is nonzero, and satisfies the site's type, file-count,
  per-file-size, and total-size limits.
- Compute checksums when the workflow needs resumability or audit evidence.
- Scope the selector to the active form when stale dialogs or minimized
  composers may contain additional file inputs.

## After upload

Do not treat a successful CDP call as proof that the application accepted the
file. Wait for the site's durable success signal: an uploaded filename, file
row, progress completion, or explicit success message. Re-read that signal and
compare it with the expected filenames before continuing.

If an upload disappears after navigation, reconstruct it from the saved local
paths; never assume a draft retained attachments.
