# Uploads

A file chooser is a native window. CDP cannot click in it, so give the files to the page in one of two ways.

## The page has a file input

Set the files on the `<input type=file>` directly. You do not need to open a chooser.

```python
upload_file("input[type=file]", "/abs/path/report.pdf")
upload_file("#photos", ["/abs/a.jpg", "/abs/b.jpg"])   # input with the multiple attribute
```

`DOM.setFileInputFiles` fires the `change` event, so most pages react as if the user picked the file.

## The page reacts only to its own button

Many apps arm their upload state in the click handler of a button, then call `input.click()`. When you set files on the input directly, nothing happens. Other apps create the input only in that handler. In both cases, let the button open the chooser, and answer the chooser through CDP:

```python
cdp("Page.enable")
cdp("Page.setInterceptFileChooserDialog", enabled=True)
drain_events()

# A real mouse click. A JS click() has no user gesture, and Chrome opens no chooser for it.
x, y = js("""(() => {
  const b = document.querySelector('button.upload');
  b.scrollIntoView({block: 'center'});
  const r = b.getBoundingClientRect();
  return [r.x + r.width / 2, r.y + r.height / 2];
})()""")
click_at_xy(x, y)

opened = None
for _ in range(50):
    opened = next((e for e in drain_events() if e["method"] == "Page.fileChooserOpened"), None)
    if opened:
        break
    wait(0.2)
cdp("DOM.setFileInputFiles", files=["/abs/path/mod.zip"], backendNodeId=opened["params"]["backendNodeId"])
cdp("Page.setInterceptFileChooserDialog", enabled=False)
```

While the interception is on, Chrome does not show the native chooser. It sends `Page.fileChooserOpened` instead. The event names the input in `backendNodeId` and tells you in `mode` if the input takes one file or more.

## Traps

- When a click opens a native chooser that nothing intercepts, the chooser blocks the page. Then `capture_screenshot()` times out. Turn the interception on before the click.
- Turn the interception off when you finish, or the user cannot pick files in this tab.
- Check the result on the page (a file name, a progress bar). Some apps upload in the background and enable their Save button only when the upload is complete.
