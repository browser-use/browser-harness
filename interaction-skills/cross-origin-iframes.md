# Cross-Origin Iframes

A cross-origin iframe runs in a different renderer process than its parent. `js("...")` against the top-level page cannot reach into it (`document.querySelector` returns `null`, `contentDocument` throws SecurityError). Two ways through.

## Default: coordinate clicks pass through

`click_at_xy(x, y)` dispatches `Input.dispatchMouseEvent` at the browser process. Hit-testing happens on the compositor, so the click lands on whatever pixel is on top — the iframe's renderer receives it natively. No DOM work needed.

```python
capture_screenshot("/tmp/shot.png")
# read the pixel of the button inside the iframe
click_at_xy(420, 580)
capture_screenshot("/tmp/shot.png")  # verify
```

This is the right tool for buttons, links, tabs, menu items, and most UI inside web IDEs, embedded dashboards, payment forms, and SSO flows.

## When you need DOM access: `iframe_target()` + `js(target_id=...)`

For reading text out of the iframe, querying the structure, or focusing a specific element by selector:

```python
tid = iframe_target("vscode-web")          # substring match on the iframe's URL
title = js("document.title", target_id=tid)
# focus a specific input inside the iframe
js("document.querySelector('.monaco-editor textarea').focus()", target_id=tid)
```

`iframe_target()` returns the first `iframe`-type CDP target whose URL contains the substring, or `None`. Pick a substring that's unique to that iframe — a hostname or path fragment, not just `https://`.

If the page has multiple cross-origin iframes from the same origin, walk `cdp("Target.getTargets")["targetInfos"]` yourself and pick by URL or by parent.

## Typing into a cross-origin iframe

`type_text()` and `press_key()` dispatch through `Input.insertText` / `Input.dispatchKeyEvent` at the browser process. They go to whichever element currently has focus inside Chrome — the iframe boundary is not a barrier, but **focus must already be on an element inside the iframe**.

Two ways to give focus to the right element:

```python
# A) coordinate click into the iframe (preferred — same as a real user)
click_at_xy(420, 300)
type_text("hello world")

# B) focus by selector via the iframe's own target
tid = iframe_target("vscode-web")
js("document.querySelector('.monaco-editor textarea').focus()", target_id=tid)
type_text("hello world")
```

If keystrokes seem to land in the wrong place, take a screenshot — focus usually moved (a modal popped, the iframe blurred, an inspector panel opened). Re-click into the iframe and continue.

## Pitfalls

- `js("document.querySelectorAll('iframe')")` from the parent only sees the iframe **element**, not the document inside it. `querySelector(...).contentDocument` throws on cross-origin. Use `iframe_target()` instead.
- `iframe_target()` can return `None` if the iframe is still loading. Either `wait_for_load()` first or poll: `while iframe_target("...") is None: wait(0.5)`.
- A page can have nested cross-origin iframes (iframe-in-iframe). Each is its own CDP target — `iframe_target()` matches by URL substring, so use a path fragment specific to the inner one.
- After a navigation inside the iframe, the target ID changes. Re-fetch with `iframe_target()` rather than caching it across navigations.
- Some sandboxed iframes (`sandbox="allow-scripts"` without `allow-same-origin`) refuse focus events from `Input.dispatchKeyEvent` if focus was set via JS but never via user gesture. Click first, then type — don't try to skip the click.
- Drag, drop, and file-upload in cross-origin iframes need the iframe's own target. See `uploads.md`.

## Quick decision

| Want to | Use |
|---|---|
| Click a button / tab / menu item | `click_at_xy(x, y)` (no iframe code) |
| Type into a focused input | `click_at_xy(...)` then `type_text(...)` |
| Read text or DOM structure | `js("...", target_id=iframe_target("..."))` |
| Focus by selector (no visible target) | `js("...focus()", target_id=...)` then `type_text(...)` |
| File upload, drag, complex DOM | iframe target work — see `uploads.md` / `drag-and-drop.md` |
