# Scrolling

Separate page scrolling from scrolling inside a nested container or iframe.

## Inside an iframe

`scroll(x, y, dy=...)` sends `Input.dispatchMouseEvent` (`mouseWheel`) at compositor level, so a wheel over an iframe scrolls the iframe's own document, cross-origin and sandboxed (`srcdoc`, opaque origin) frames included. Verified on a `sandbox="allow-scripts"` srcdoc frame inside an `overflow:hidden` box: one `scroll(..., dy=400)` moved the frame's `scrollY` to ~630.

Other automation may not: a browser extension's synthetic wheel (e.g. an extension-driven "scroll" action) can scroll the top page while never reaching the iframe, which looks like "this frame cannot scroll". Before concluding a frame is broken, check it directly: for a same-origin frame, `contentDocument.scrollingElement.scrollHeight > clientHeight` and setting `scrollTop` works; for a cross-origin one, use `scroll()` here.
