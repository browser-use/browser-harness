# Self-modifying Browser Harness

Browser Harness is intentionally small. The core helpers cover navigation,
screenshots, raw CDP, JavaScript, coordinates, keyboard input, and files. When a
site needs something more specific, the agent should extend the harness while it
works instead of treating the site as an unsolved edge case.

The loop is:

1. Inspect the page with `capture_screenshot()` and `page_info()`.
2. Try the smallest built-in primitive: `click_at_xy`, `type_text`,
   `press_key`, `upload_file`, `js`, or raw `cdp`.
3. If the missing operation is reusable, add a helper to
   `agent-workspace/agent_helpers.py`.
4. Call the helper from `browser-harness -c`.
5. Verify with another screenshot or direct page state check.
6. If the helper teaches a durable site-specific trick, save it as a domain
   skill under `agent-workspace/domain-skills/<site>/`.

This is the main difference from a fixed browser automation wrapper: the agent
can patch the harness during the task, then immediately retry with the new
primitive.

## Example 1: file upload behind a styled button

Many sites hide the real `<input type="file">` and expose a styled button. If a
visual click opens the file picker, do not ask the user to handle it. Find the
input and set the file through CDP.

```python
# browser-harness -c '...'
from pathlib import Path

new_tab("https://example.com/profile")
wait_for_load()

avatar = Path("/tmp/avatar.png").resolve()
upload_file("input[type=file]", str(avatar))

print(js("""
const input = document.querySelector('input[type=file]');
return input && input.files.length;
"""))
capture_screenshot("/tmp/uploaded.png", max_dim=1800)
```

If the selector is unstable, add a task helper:

```python
# agent-workspace/agent_helpers.py
def upload_first_file_input(path):
    inputs = js("""
    return [...document.querySelectorAll('input[type=file]')]
      .map((el, i) => ({ i, accept: el.accept, name: el.name, id: el.id }));
    """)
    if not inputs:
        raise RuntimeError("no file input on page")
    upload_file("input[type=file]", path)
```

The helper is intentionally narrow: it solves the current page shape without
adding a framework around uploads.

## Example 2: drag-and-drop that ignores simple clicks

For visual drag handles, use compositor-level mouse events first. These pass
through shadow DOM, iframes, and framework wrappers because Chrome receives a
real pointer sequence.

```python
# browser-harness -c '...'
capture_screenshot("/tmp/before-drag.png", max_dim=1800)

cdp("Input.dispatchMouseEvent", type="mousePressed", x=180, y=420,
    button="left", clickCount=1)
cdp("Input.dispatchMouseEvent", type="mouseMoved", x=340, y=420,
    button="left")
cdp("Input.dispatchMouseEvent", type="mouseMoved", x=520, y=420,
    button="left")
cdp("Input.dispatchMouseEvent", type="mouseReleased", x=520, y=420,
    button="left", clickCount=1)

capture_screenshot("/tmp/after-drag.png", max_dim=1800)
```

If the app only responds to DOM `dragover` / `drop`, add a helper that performs
that site's expected event sequence:

```python
# agent-workspace/agent_helpers.py
def dom_drag_between(source_selector, target_selector):
    return js(f"""
    const source = document.querySelector({source_selector!r});
    const target = document.querySelector({target_selector!r});
    if (!source || !target) throw new Error("missing drag source or target");

    const data = new DataTransfer();
    for (const type of ["dragstart", "dragenter", "dragover", "drop", "dragend"]) {{
      const node = type === "dragstart" || type === "dragend" ? source : target;
      node.dispatchEvent(new DragEvent(type, {{
        bubbles: true,
        cancelable: true,
        dataTransfer: data
      }}));
    }}
    return true;
    """)
```

Use the DOM path only after the low-level pointer path fails; the pointer path
is closer to what a user does.

## Example 3: signature field or canvas drawing

Canvas widgets often have no useful DOM children. Treat them as coordinate
surfaces. Locate the canvas, draw through CDP mouse events, and verify with a
screenshot or by checking the backing canvas pixels.

```python
# agent-workspace/agent_helpers.py
def sign_canvas(selector="canvas", points=None):
    points = points or [
        (0.15, 0.65), (0.30, 0.35), (0.45, 0.70),
        (0.62, 0.32), (0.80, 0.58),
    ]
    rect = js(f"""
    const el = document.querySelector({selector!r});
    if (!el) throw new Error("canvas not found");
    const r = el.getBoundingClientRect();
    return {{ x: r.x, y: r.y, w: r.width, h: r.height }};
    """)
    absolute = [
        (rect["x"] + x * rect["w"], rect["y"] + y * rect["h"])
        for x, y in points
    ]
    first = absolute[0]
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=first[0], y=first[1],
        button="left", clickCount=1)
    for x, y in absolute[1:]:
        cdp("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y,
            button="left")
    last = absolute[-1]
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=last[0], y=last[1],
        button="left", clickCount=1)
```

Then call it:

```python
# browser-harness -c '...'
sign_canvas("canvas.signature")
capture_screenshot("/tmp/signature.png", max_dim=1800)
```

The reusable part is not the exact signature shape. It is the conversion from a
canvas selector to real pointer coordinates.

## Example 4: coordinate-only controls

Some controls are visible but hostile to selectors: canvas maps, custom sliders,
SVG editors, image crop boxes, or cross-origin iframe buttons. Use the
screenshot as the source of truth, convert device pixels to CSS pixels when
needed, and click the visible target.

```python
# browser-harness -c '...'
path = capture_screenshot("/tmp/target.png", max_dim=1800)
info = page_info()
dpr = js("window.devicePixelRatio") or 1
print({"screenshot": path, "viewport": info, "devicePixelRatio": dpr})

# If the target was measured at image pixel (960, 540) on a 2x screenshot:
click_at_xy(960 / dpr, 540 / dpr)
capture_screenshot("/tmp/clicked.png", max_dim=1800)
```

If the same coordinate pattern repeats, add a helper with semantic names:

```python
# agent-workspace/agent_helpers.py
def click_canvas_percent(selector, x_pct, y_pct):
    rect = js(f"""
    const el = document.querySelector({selector!r});
    if (!el) throw new Error("target not found");
    const r = el.getBoundingClientRect();
    return {{ x: r.x, y: r.y, w: r.width, h: r.height }};
    """)
    click_at_xy(rect["x"] + rect["w"] * x_pct, rect["y"] + rect["h"] * y_pct)
```

Now the task can say `click_canvas_percent("canvas.map", 0.72, 0.41)` instead of
carrying brittle absolute coordinates through the rest of the run.

## Edge-case benchmark

Use [edge-case-benchmark.html](edge-case-benchmark.html) to test the four
patterns on a single page: hidden file upload, drag/drop event payloads,
signature canvas, and a coordinate-only canvas target.

For a normal local browser session:

```python
# browser-harness -c '...'
from pathlib import Path

new_tab(Path("docs/edge-case-benchmark.html").resolve().as_uri())
wait_for_load()
print(page_info())
```

On a remote Browser Use Cloud browser, local `file://` URLs are not available.
Load the HTML into `about:blank` instead:

```python
# browser-harness -c '...'
from pathlib import Path

html = Path("docs/edge-case-benchmark.html").read_text()
new_tab("about:blank")
frame_id = cdp("Page.getFrameTree")["frameTree"]["frame"]["id"]
cdp("Page.setDocumentContent", frameId=frame_id, html=html)
```

The benchmark exposes `window.bhBenchmarkResults()` so an agent can verify
completion without relying on a visual guess.

## What to commit back

Commit helpers that are durable and general enough to help the next run:

- site-specific login, upload, checkout, export, or scraping flows go in
  `agent-workspace/domain-skills/<site>/`;
- reusable interaction mechanics go in `interaction-skills/`;
- one-off task glue can stay in `agent-workspace/agent_helpers.py` on the
  user's machine.

Do not commit secrets, user data, screenshots of private sessions, or fixed
pixel coordinates from one viewport. Commit the durable map of how the site
works, not the diary of one run.
