# Screenshots

`capture_screenshot()` writes a PNG of the current viewport. The file is in **device pixels** — on a 2× display a 2296×1143 CSS viewport produces a 4592×2286 PNG.

That matters for two reasons:

1. **Click coordinates are CSS pixels.** Don't read a target off the image and pass it to `click_at_xy()` directly without dividing by `devicePixelRatio`. The simplest workflow is to take the screenshot, look at it in a viewer that shows CSS coordinates, or measure relative positions and use `js("window.devicePixelRatio")` to convert.

2. **Some LLMs reject images > 2000 px per side.** Long sessions on 2× displays will eventually hit this. Pass `max_dim=1800` to downscale the file before it gets into the conversation:

```python
capture_screenshot("/tmp/shot.png", max_dim=1800)
```

The downscale only happens when the image actually exceeds `max_dim`, so it's safe to leave on for every shot.

Use full-page screenshots (`full=True`) only when you need to see content below the fold — they are much larger and slower than viewport-only.

## `full=True` never returns when the window is hidden

`full=True` sets CDP's `captureBeyondViewport`, which needs the compositor to produce a fresh frame covering the whole scrollable area. A minimized or fully occluded window never produces one, so the call does not come back — measured past two minutes on Windows 11 / Chrome 150, with the socket timeout raised to 90s to rule the client out.

Viewport-only capture is unaffected: it still returns in about two seconds on that same hidden window. And once the window is visible, the full-page capture of the same page finishes in well under a second — so this is a stall, not slowness.

Raise the window before a full-page shot, or stay on viewport captures and scroll between them.

## Every CDP call has a five-second ceiling

`_send()` opens its socket with `timeout=5.0`, so *any* call needing longer than that fails. This is not screenshot-specific — a `js()` expression that blocks for three seconds returns normally, while the same expression blocked for seven fails at exactly 5.0s. Given a longer timeout, that seven-second call succeeds.

It surfaces as a bare traceback ending in `_ipc.py`:

```text
TimeoutError: timed out
```

That names the IPC layer rather than the call you made, so it reads like a dropped connection or a dead tab. It is neither — it means "that call needed more than five seconds." Both the daemon and the tab are still healthy afterwards, and the next call works.
