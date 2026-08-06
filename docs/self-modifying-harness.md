# Self-modifying browser harness

Browser Harness is intentionally thin: it gives the agent direct Chrome
DevTools Protocol access plus an editable workspace. When a browser task hits a
missing mechanic, the agent should add the smallest helper or skill that makes
the task work, use it, and keep that reusable code in `agent-workspace/`.

That changes how to think about edge cases. A signature pad, a canvas-only UI,
a custom drag target, or a hidden file input is not a permanent product limit.
It is a prompt to inspect the page, patch the harness, retry, and save the
working path.

## The loop

1. Reproduce the blocked interaction in the browser.
2. Inspect with screenshots first, then DOM and raw CDP only when needed.
3. Add a focused helper in `agent-workspace/agent_helpers.py` or a durable
   site note in `agent-workspace/domain-skills/<site>/`.
4. Run the helper against the real page.
5. Verify with a screenshot or page-state read.
6. Keep the helper small enough that the next agent can understand and edit it.

Core helpers stay generic. Site-specific selectors, timing, and private API
knowledge belong in the agent workspace or domain skills.

## Example: signature or canvas field

Problem: there is no real `<input>` to fill. The site expects pointer events on
a canvas.

Patch shape:

```python
def draw_signature_on_canvas(selector, points):
    box = js(f"""
    (() => {{
      const c = document.querySelector({selector!r});
      const r = c.getBoundingClientRect();
      return {{x:r.left, y:r.top, w:r.width, h:r.height}};
    }})()
    """)
    for i, (x, y) in enumerate(points):
        event_type = "mousePressed" if i == 0 else "mouseMoved"
        cdp("Input.dispatchMouseEvent", type=event_type,
            x=box["x"] + x, y=box["y"] + y, button="left", clickCount=1)
    cdp("Input.dispatchMouseEvent", type="mouseReleased",
        x=box["x"] + points[-1][0], y=box["y"] + points[-1][1],
        button="left", clickCount=1)
```

Use screenshot coordinates to choose the visible stroke path, then verify by
reading the page state or taking another screenshot.

## Example: file upload

Problem: the visible button opens an OS picker, which an agent cannot use
directly.

Patch shape:

```python
def upload_visible_or_hidden_file(selector, path):
    upload_file(selector, path)
    js(f"""
    (() => {{
      const input = document.querySelector({selector!r});
      input.dispatchEvent(new Event("input", {{bubbles:true}}));
      input.dispatchEvent(new Event("change", {{bubbles:true}}));
    }})()
    """)
```

Prefer `DOM.setFileInputFiles` through `upload_file()`. If the file input is
created lazily, first click the visible upload button, wait for the input, then
set the file.

## Example: drag and drop

Problem: the site uses custom drag events or a drop zone that does not respond
to a simple click.

Patch shape:

```python
def drag_center_to_center(source_selector, target_selector):
    boxes = js(f"""
    (() => {{
      const s = document.querySelector({source_selector!r}).getBoundingClientRect();
      const t = document.querySelector({target_selector!r}).getBoundingClientRect();
      return {{
        sx: s.left + s.width / 2, sy: s.top + s.height / 2,
        tx: t.left + t.width / 2, ty: t.top + t.height / 2
      }};
    }})()
    """)
    cdp("Input.dispatchMouseEvent", type="mousePressed",
        x=boxes["sx"], y=boxes["sy"], button="left", clickCount=1)
    cdp("Input.dispatchMouseEvent", type="mouseMoved",
        x=boxes["tx"], y=boxes["ty"], button="left")
    cdp("Input.dispatchMouseEvent", type="mouseReleased",
        x=boxes["tx"], y=boxes["ty"], button="left", clickCount=1)
```

If compositor-level movement does not trigger the app, inspect whether the app
expects HTML5 `DataTransfer` events and add a DOM-specific helper for that
site.

## Example: coordinate-only target

Problem: a visible control has no stable selector, sits inside a canvas, or is
inside cross-origin UI where DOM inspection is the wrong tool.

Patch shape:

```python
def click_visible_point(x, y):
    click_at_xy(x, y)
    wait(0.2)
    capture_screenshot()
```

Use `capture_screenshot()` to locate the visible target. Keep the coordinate in
the task script, not in a public domain skill, unless the layout is fixed and
the skill also records viewport assumptions.

## Local benchmark

`docs/edge-case-benchmark.html` is a standalone page that exercises the four
mechanics above:

- canvas signature
- file upload
- drag and drop
- coordinate click

Open it with Browser Harness when changing helpers:

```bash
browser-harness -c '
new_tab("file:///absolute/path/to/docs/edge-case-benchmark.html")
wait_for_load()
print(page_info())
'
```

The page exposes `window.edgeBenchmark.results` for quick verification from
`js(...)`.

