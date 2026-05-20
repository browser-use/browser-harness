# Self-modifying harness

Browser Harness works because the agent is not trapped behind a fixed browser API.
When a page has a new edge case, the agent can inspect the page, add the missing
helper in `agent-workspace/agent_helpers.py` or a domain skill, retry the task,
and keep the working code for the next run.

The loop is:

1. Use `capture_screenshot()` and `page_info()` to understand the current state.
2. Try the smallest existing primitive: `click_at_xy`, `type_text`, `press_key`,
   `upload_file`, `js`, or raw `cdp`.
3. If the primitive is missing, add a helper in `agent-workspace/agent_helpers.py`
   or a site-specific note in `agent-workspace/domain-skills/<site>/`.
4. Run the helper, then verify with a screenshot or page state.
5. Commit only durable knowledge: selectors, DOM events, CDP calls, endpoint
   shape, or framework quirks. Do not commit secrets or one-off pixel positions.

That is why browser edge cases are not permanent. They are usually just missing
local code.

## Example 1: file upload

Start with the built-in helper when there is a real file input:

```python
upload_file("input[type=file]", "/tmp/invoice.pdf")
js("""
const input = document.querySelector('input[type=file]');
input.dispatchEvent(new Event('input', {bubbles: true}));
input.dispatchEvent(new Event('change', {bubbles: true}));
""")
```

If the app hides the input behind a custom button, add a helper that finds the
real input once and then reuses the same path:

```python
# agent-workspace/agent_helpers.py
def upload_to_hidden_input(label_text, path):
    selector = js(f"""
    const labels = [...document.querySelectorAll('label,button,[role=button]')];
    const trigger = labels.find(e => e.innerText.trim().includes({label_text!r}));
    const root = trigger?.closest('form,section,div') || document;
    const input = root.querySelector('input[type=file]');
    if (!input) throw new Error('no file input near upload trigger');
    input.setAttribute('data-bh-upload-target', '1');
    return '[data-bh-upload-target="1"]';
    """)
    upload_file(selector, path)
```

Keep this in a domain skill if the selector is specific to one product.

## Example 2: drag and drop

Try compositor-level input first when the page responds to real pointer motion:

```python
cdp("Input.dispatchMouseEvent", type="mouseMoved", x=120, y=220)
cdp("Input.dispatchMouseEvent", type="mousePressed", x=120, y=220, button="left")
cdp("Input.dispatchMouseEvent", type="mouseMoved", x=500, y=260, button="left")
cdp("Input.dispatchMouseEvent", type="mouseReleased", x=500, y=260, button="left")
```

Some React or editor surfaces require DOM drag events with a `DataTransfer`
payload. Put that site-specific sequence in a helper:

```python
# agent-workspace/agent_helpers.py
def dom_drag_text(source_selector, target_selector, payload):
    js(f"""
    const source = document.querySelector({source_selector!r});
    const target = document.querySelector({target_selector!r});
    const dt = new DataTransfer();
    dt.setData('text/plain', {payload!r});
    for (const type of ['dragstart', 'dragenter', 'dragover', 'drop', 'dragend']) {{
      const node = type === 'dragstart' || type === 'dragend' ? source : target;
      node.dispatchEvent(new DragEvent(type, {{bubbles: true, cancelable: true, dataTransfer: dt}}));
    }}
    """)
```

The durable knowledge is not the one drag coordinate. It is whether that app
wants real pointer events, DOM drag events, or a hidden file input.

## Example 3: canvas signature

Canvas fields often have no useful DOM target inside the drawing area. Use the
canvas bounds plus raw mouse events:

```python
box = js("""
const r = document.querySelector('canvas.signature').getBoundingClientRect();
return {x: r.left, y: r.top, w: r.width, h: r.height};
""")

points = [
    (box["x"] + 20, box["y"] + box["h"] * 0.55),
    (box["x"] + 80, box["y"] + box["h"] * 0.35),
    (box["x"] + 150, box["y"] + box["h"] * 0.60),
    (box["x"] + 220, box["y"] + box["h"] * 0.40),
]
cdp("Input.dispatchMouseEvent", type="mousePressed", x=points[0][0], y=points[0][1], button="left")
for x, y in points[1:]:
    cdp("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y, button="left")
cdp("Input.dispatchMouseEvent", type="mouseReleased", x=points[-1][0], y=points[-1][1], button="left")
```

Verify by reading app state or screenshotting the canvas. If the page stores a
hidden signature value, add a site helper that checks that field too.

## Example 4: coordinate-only target

Some UI is only visible pixels: maps, whiteboards, games, image editors, or
custom canvas widgets. Do not hunt for selectors that do not exist. Let the
screenshot drive the next action:

```python
shot = capture_screenshot("/tmp/target.png", max_dim=1800)
info = page_info()
print(info)
# read the target position from the screenshot, convert image pixels to CSS
# pixels if devicePixelRatio > 1, then click:
click_at_xy(412, 318)
capture_screenshot("/tmp/after.png", max_dim=1800)
```

If the target is stable enough to compute, write the helper:

```python
# agent-workspace/agent_helpers.py
def click_canvas_target(canvas_selector, rel_x, rel_y):
    box = js(f"""
    const r = document.querySelector({canvas_selector!r}).getBoundingClientRect();
    return {{x: r.left, y: r.top, w: r.width, h: r.height}};
    """)
    click_at_xy(box["x"] + box["w"] * rel_x, box["y"] + box["h"] * rel_y)
```

The point is not that coordinates are magic. The point is that the agent can
choose coordinates, DOM, CDP, or a new helper after it sees the actual page.

## Benchmark page

`docs/edge-case-benchmark.html` contains a small local page with four tasks:

- file upload
- drag and drop
- canvas signature
- coordinate-only canvas click

Use it when changing helper behavior or when demonstrating the self-modifying
loop. A run is successful when `window.bhBenchmarkResults()` returns all four
checks as `true`.

