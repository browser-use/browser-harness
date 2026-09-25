# Screenshots

Separate full-page screenshots from targeted section screenshots, and note when screenshots are only for discovery versus verification.

## Full page with iframes

`screenshot(full=True)` (`captureBeyondViewport`) renders the top document past the viewport, but an out-of-process iframe (cross-origin or sandboxed) is painted only where it overlapped the original viewport — the rest of the frame comes out blank. To capture a whole page that contains such a frame, make the viewport as tall as the page, then take a normal screenshot:

```python
h = js("document.documentElement.scrollHeight")
cdp("Emulation.setDeviceMetricsOverride", width=1400, height=int(h), deviceScaleFactor=1, mobile=False)
wait(2)
screenshot("/tmp/full.png")
cdp("Emulation.clearDeviceMetricsOverride")
```

If the frame itself has a fixed height and scrolls internally, the page's height does not include the frame's content: size the frame to its content first (many apps offer a print or "fit" mode), or scroll inside it with `scroll()` and take several shots.
