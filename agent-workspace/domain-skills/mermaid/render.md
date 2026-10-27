# mermaid.live — render & validate arbitrary Mermaid

Use this when you need to **render a Mermaid diagram and confirm it actually parses**
(e.g., after editing a `.md`/`.html` that embeds Mermaid) without a local mermaid CLI.
mermaid.live renders client-side, so it doubles as a free validator.

## URL format (the non-obvious part)

The editor state lives entirely in the URL hash, **not** a query param:

```
https://mermaid.live/edit#pako:<data>
```

`<data>` is the editor state JSON, **zlib-compressed then URL-safe base64**. It is
NOT plain base64 of the code — skipping the deflate step gives a blank editor. Build it
in Python (the harness already runs Python):

```python
import json, zlib, base64

def mermaid_live_url(code: str) -> str:
    state = {"code": code, "mermaid": '{\n  "theme": "default"\n}',
             "autoSync": True, "updateDiagram": True}
    raw = json.dumps(state).encode("utf-8")
    data = base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")
    return "https://mermaid.live/edit#pako:" + data
```

This example uses a zlib-wrapped stream and removes base64 padding. Verify the loaded editor code after navigation; a decoder change can invalidate the URL.

## Confirming the render (headless-safe, no screenshot needed)

`capture_screenshot()` saves an image for visual inspection.
Check the page structure for a graph, then inspect the image when appearance matters.

```python
import time

new_tab(mermaid_live_url(code))
wait_for_load()
deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    state = js("""(() => {
      const graphs = [...document.querySelectorAll('svg[id^="graph-"]')]
        .filter(el => el.getClientRects().length);
      const editor = document.querySelector('.cm-content');
      return {
        rendered: graphs.length > 0,
        editorCode: editor ? [...editor.querySelectorAll('.cm-line')].map(el => el.textContent).join('\\n') : null,
        syntaxErr: graphs.some(graph => graph.querySelector('.error-icon, .error-text'))
      };
    })()""")
    if state["syntaxErr"]:
        raise RuntimeError("The editor reports a Mermaid syntax error")
    if state["rendered"] and state["editorCode"] == code:
        break
    time.sleep(0.25)
else:
    raise RuntimeError("The requested diagram did not render with matching editor code")
```

Check that the editor contains the submitted code before treating a graph as the requested result.
Use the graph ID prefix to exclude toolbar icons.
Do not reject small diagrams based on group count.

## Traps

- **`#pako:` is a hash, not a query.** `wait_for_load()` won't catch the client-side
  render. Poll the editor and graph until the bounded deadline.
- **Do not trust error text alone.** Require a visible graph SVG that matches the submitted code.
  A blank editor (bad encoding) shows neither an error nor a graph.
- Theme/look-and-feel never affects parse success; keep the `mermaid` state minimal.
