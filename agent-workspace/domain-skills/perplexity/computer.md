# Perplexity Computer — Dashboard, Task Runs, Artifacts, Sharing

"Perplexity Computer" is Perplexity's long-running agent product that lives under `https://www.perplexity.ai/computer/*`. It runs multi-step research/build tasks in a cloud sandbox and produces a plan (Todo), tool invocations, and file artifacts (charts, PDFs, code). Distinct from regular Perplexity Search/chat — don't confuse the URL paths.

You must be signed in before the harness can drive it. Computer is a paid feature; tasks consume credits, and stalled tasks show an "Insufficient credits" banner until the user tops up.

## URL patterns

- Dashboard / task list: `https://www.perplexity.ai/computer/tasks`
- Task detail (run page): `https://www.perplexity.ai/computer/tasks/<slug>-<id>`
  - `<slug>` is a kebab-case auto-summary of the prompt (typically 3–6 words from the title).
  - `<id>` is a 22-char base62-ish opaque id (character set includes letters, digits, `-`, and `_`).
  - The full last segment is `<slug>-<id>` joined with a `-`; there's no separator character beyond that. To recover the id, parse with `URL` and take the last 22 chars of the pathname's final segment — **never slice the raw href**, because query/hash (e.g. `?view=thread`) will corrupt the result:
    ```python
    # JS:  new URL(href).pathname.split('/').filter(Boolean).pop().slice(-22)
    # Python: urlparse(href).path.rstrip('/').rsplit('/', 1)[-1][-22:]
    ```
- Connectors: `https://www.perplexity.ai/computer/connectors`
- Custom skills: `https://www.perplexity.ai/computer/skills`
- Public share: the same task URL with `?view=thread` appended (e.g. `https://www.perplexity.ai/computer/tasks/<slug>-<id>?view=thread`). There is **no separate `/share/<id>` path** — the access level is toggled server-side and the `view=thread` query just opens the thread view for unauthenticated viewers.

The task title in the top bar (`<h1>` region) is the human-readable prompt summary; the URL slug is the kebab-cased version. Always key tasks by the id (last 22 chars of the URL) — slug and title both drift across Perplexity releases.

## Background: wire format

Task state is **not** in `window.__NEXT_DATA__` on the task detail page (`__NEXT_DATA__` is `null`), and the page does **not** fire any `api.perplexity.ai`-style fetches on load — task content hydrates from an inline RSC payload / streaming response. A `wss://suggest.perplexity.ai/suggest/ws` WebSocket opens on the dashboard but only carries the typeahead suggestions for the composer; it is not the task stream.

If you need the wire format for task streaming, install the fetch + WebSocket hooks from the Debugging section while submitting a new task — the streaming transport opens lazily on submit. Browser DOM extraction (below) is the supported path.

## Dashboard: `/computer/tasks`

The task list is a CSS-grid table with proper ARIA roles — these are the most durable selectors on the whole product.

| Target | Selector | Notes |
| --- | --- | --- |
| Task row | `div[role="row"]` in the main content | Each row is `tabindex="0"` and clickable (not an `<a>`). Click anywhere on the row to open the task. |
| Task cell | `div[role="cell"]` inside a row | Columns: title + slug, relative date ("6d ago"), status. |
| Start-a-task composer | `[data-ask-input-container]` | Unique on the page. Contains the Lexical editor. |
| Composer editor | `[data-lexical-editor="true"]` inside the container | `contenteditable="true"`. Focus + `type_text()` via CDP — **not** a `<textarea>`. |
| Send button | last `<button>` inside `[data-ask-input-container]` (round, arrow-right icon) | Disabled until the editor has content. Pressing Enter in the editor also submits. |
| "Computer" mode chip | button with text `"Computer"` inside the composer | Indicates the mode is Computer (as opposed to regular Perplexity Search). For Computer tasks it should already be pinned. |

```bash
browser-harness <<'PY'
new_tab("https://www.perplexity.ai/computer/tasks")
wait_for_load()
wait(1.5)
# List existing tasks — use ARIA row/cell semantics
tasks = js(r"""
[...document.querySelectorAll('div[role="row"]')].slice(0,20).map(row => ({
  cells: [...row.querySelectorAll('[role="cell"]')].map(c => (c.innerText||'').trim()),
  rect: (()=>{const r=row.getBoundingClientRect(); return {x:r.x+r.width/2|0, y:r.y+r.height/2|0}})()
}))
""")
print(tasks)  # cells[0] = title + slug + status, cells[1] = "6d ago", cells[2] = (empty / actions)
PY
```

## Submitting a new task

The task title on the left side of the composer is just a mode chip; typing goes into the Lexical editor.

```bash
browser-harness <<'PY'
new_tab("https://www.perplexity.ai/computer/tasks")
wait_for_load()
wait(1.5)
# Focus the editor via bounding rect of the container
rect = js("""(()=>{const c=document.querySelector('[data-ask-input-container]');
const r=c.getBoundingClientRect();return {x:r.x+r.width/2|0,y:r.y+0.4*r.height|0}})()""")
click(rect["x"], rect["y"])
wait(0.3)
type_text("Summarize the three most recent earnings calls from NVDA in under 300 words.")
wait(0.4)
press_key("Enter")  # or click the arrow-right send button
wait(3)
print(page_info())  # URL becomes /computer/tasks/<slug>-<id>
PY
```

Tasks typically take minutes to tens of minutes. Poll the completion marker (see next section) or poll `location.href` — the slug-with-id URL appears almost immediately after submit.

## Task detail page

A running or completed task page has four distinct regions:

1. **Top bar** — back arrow, title (`<h1>`), "Usage" button, "Todo" button, "Share" button. These are stable across all Computer task URLs.
2. **Main thread** — interleaves tool invocations ("Writing to chart.py", "Generating the comparison chart"), inline images, and markdown report sections.
3. **Command input** — a secondary Lexical composer at the bottom, "Type a command..." — for follow-up instructions to the running agent. Same `[data-lexical-editor="true"]` selector.
4. **Side panels** — Todo (plan) and Usage overlays, summoned from the top-right buttons.

### Top bar buttons (coordinate-free)

```python
def top_button_rect(label):
    return js(f"""
    (()=>{{const b=[...document.querySelectorAll('button,[role="button"]')]
      .find(x=>x.innerText?.trim()==={label!r});
    if(!b)return null;const r=b.getBoundingClientRect();
    return {{x:r.x+r.width/2|0,y:r.y+r.height/2|0}}}})()
    """)

for lbl in ("Usage", "Todo", "Share"):
    r = top_button_rect(lbl)
    print(lbl, r)
```

### Tool-invocation rows (the thread body)

Each tool step is rendered as a collapsible row with a leading icon, a short label, a timestamp, and a duration. The wrapper carries the group tailwind class `group/tool-wrapper` — that's the best anchor.

| Target | Selector | Notes |
| --- | --- | --- |
| Tool-invocation wrapper | `[class*="group/tool-wrapper"]` | One per tool call; includes expand toggle, label button, metadata. |
| Tool label | the only `<button>` direct child of the wrapper | Text = human-readable action, e.g. `"Writing to chart.py"`, `"Generating the comparison chart"`, `"Researching: <query>"`. |
| Timestamp + duration | sibling text node with `Apr 17, 4:00 AM · 9s` format | Durations stop updating when the tool completes. |
| Inline image artifact | `<img src="https://pplx-res.cloudinary.com/...">` or `<img src="https://d2z0o16i8xm8ak.cloudfront.net/...">` | Cloudinary is the persistent URL; CloudFront URLs are presigned (expire) — if you want to archive, download via Cloudinary or copy the image to `/tmp`. |
| Report markdown body | scroll the main thread and grab the `<main>`'s rendered prose | Perplexity renders markdown with a `data-renderer="lm"` marker on the LM-output block. |
| Citation favicons | `<img src="https://www.google.com/s2/favicons?domain=...">` | Google's favicon proxy; the hostnames next to them are the actual citation sources. |

### Todo panel (agent plan)

Click the `"Todo"` top-bar button — a floating panel opens with the plan items. The Todo button is a Radix trigger: it carries `data-state="closed"|"open"`, `aria-expanded`, and `aria-controls="<radix-id>"`. The open panel is mounted as a portal element whose `id` equals the button's `aria-controls` — use that to scope queries to the panel only.

```python
def todo_panel():
    return js(r"""
    (()=>{
      const btn = [...document.querySelectorAll('button')].find(x=>x.innerText?.trim()==='Todo');
      if(!btn || btn.getAttribute('data-state') !== 'open') return null;
      const id = btn.getAttribute('aria-controls');
      return id ? document.getElementById(id) : null;
    })()
    """)

# Open and read the plan
click(*top_button_rect("Todo").values())
wait(1)
plan = js(r"""
(()=>{
  const btn = [...document.querySelectorAll('button')].find(x=>x.innerText?.trim()==='Todo');
  const id = btn?.getAttribute('aria-controls');
  const panel = id ? document.getElementById(id) : null;
  return panel ? (panel.innerText||'').trim() : null;
})()
""")
print(plan)
```

Plan items render with a green check SVG (completed — `<use xlink:href="#pplx-icon-check">`) or an empty circle (pending). The plan title sits at the top of the panel as plain text; each step is a separate row with one status icon.

### Detecting task completion

There is no single `"Task completed"` marker like Manus. Terminal state is inferred by:

- the `"Insufficient credits"` banner (failure due to billing) containing the text `"Insufficient credits"` + an `Add credits` button, or
- the final tool invocation's duration stops ticking and a markdown report section appears, or
- polling the Todo panel — every row's status icon is `#pplx-icon-check` (no pending circles or alerts).

If you are driving Computer tasks programmatically, prefer polling the Todo panel. **Do not query `svg use` on `document`** — the page has dozens of icons outside the Todo panel (tool-invocation rows, sidebar, top bar), and a global count produces meaningless completion state. Scope every icon query to the Radix panel:

```python
def all_todo_done():
    return js(r"""
    (()=>{
      const btn = [...document.querySelectorAll('button')].find(x=>x.innerText?.trim()==='Todo');
      if(!btn || btn.getAttribute('data-state') !== 'open') return null;  // panel closed — open it first
      const id = btn.getAttribute('aria-controls');
      const panel = id ? document.getElementById(id) : null;
      if(!panel) return null;
      const icons = [...panel.querySelectorAll('svg use')]
        .map(u => u.getAttribute('xlink:href')||'');
      if(icons.length === 0) return null;   // panel still hydrating
      return icons.every(h => /#pplx-icon-check/.test(h));
    })()
    """)
```

This returns `None` when the panel is closed (you need to open it first) or still hydrating, `True` only when every row in the Todo panel shows the check icon.

### Extracting the final report

The report body is the tail of the main thread. Scroll to the bottom and read the innerText of the last `data-renderer="lm"` block, or just grab the whole main content:

```python
report = js(r"""
(()=>{
  const main = document.querySelector('main') || document.body;
  // The LM-rendered content blocks — concatenate them
  const lm = [...main.querySelectorAll('[data-renderer="lm"]')];
  return lm.map(b => b.innerText).join('\n\n---\n\n');
})()
""")
```

## Sharing a task

The Share popover has **three privacy levels**, each marked with a stable `data-testid`:

| Privacy level | Selector | Effect |
| --- | --- | --- |
| Private | `[data-testid="access-level-private"]` | Only the author can view. |
| Specific people | `[data-testid="access-level-specific-people"]` | Invite specific accounts. |
| Anyone with the link | `[data-testid="access-level-public"]` | Anyone with the URL can view (public). |

```bash
browser-harness <<'PY'
# On a /computer/tasks/<slug>-<id> page
click(*[v for v in js("""(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText?.trim()==='Share');
const r=b.getBoundingClientRect();return {x:r.x+r.width/2|0,y:r.y+r.height/2|0}})()""").values()])
wait(1)
# Flip to public
rect = js("""(()=>{const el=document.querySelector('[data-testid="access-level-public"]');
const r=el.getBoundingClientRect();return {x:r.x+r.width/2|0,y:r.y+r.height/2|0}})()""")
click(rect["x"], rect["y"])
wait(0.3)
# Copy link — the button with exact text "Copy Link"
rect = js("""(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText?.trim()==='Copy Link');
const r=b.getBoundingClientRect();return {x:r.x+r.width/2|0,y:r.y+r.height/2|0}})()""")
click(rect["x"], rect["y"])
# The URL copied is (page URL) + "?view=thread" — compute directly if you can't read the clipboard:
print(page_info()['url'] + '?view=thread')
PY
```

Clipboard writes go through `navigator.clipboard.writeText` (**not** `document.execCommand('copy')` like Manus). If you need to intercept the URL, hook `navigator.clipboard.writeText`.

## Gotchas

- **`__NEXT_DATA__` is `null` on `/computer/tasks/<slug>-<id>`.** Don't try to pull task content out of inline JSON — it isn't there. Hydrate comes via streaming RSC.
- **No `api.perplexity.ai` fetches on page load.** The visible fetch log is mostly Datadog RUM + `wss://suggest.perplexity.ai` (typeahead). Real task transport opens on submit, not on load — install hooks before submitting if you want the wire shape.
- **Composer is Lexical, not TipTap.** Marker is `[data-lexical-editor="true"]`. Same contenteditable behavior — set via `type_text()` after focusing, **never** `.value = ...`.
- **Task rows use ARIA `role="row"` / `role="cell"`, but the row itself is not an `<a>`.** Click the row's bounding rect; don't `document.querySelector('a[href*="/computer/tasks/"]')` — there is none.
- **Sidebar items (New / Computer / Spaces / Customize / History) are `<div>`, not `<a>`.** Find them by exact text match, same as Manus.
- **The Share popover uses a floating portal (`data-type="portal"`), not `role="dialog"`.** A generic `[role="dialog"]` query misses it. Use `[data-testid="access-level-*"]` or match by the text `"Share this task"` + `"Private"` + `"Anyone"` co-occurring in an element.
- **Share URL = task URL + `?view=thread`.** No separate domain or path. Computing it client-side is often simpler than clicking "Copy Link" and reading clipboard.
- **Task slugs drift.** A task renamed by the user or re-summarized after a new run can change the slug in the URL — the 22-char id at the end is the durable handle.
- **"Insufficient credits" is a terminal-but-recoverable state.** The task isn't failed, it's paused. DOM marker: the literal text `"Insufficient credits"` paired with an `"Add credits to continue"` headline. Don't treat this as normal completion.
- **`[data-erp="tab"]`, `[data-modality="mouse"]`, `[data-renderer="lm"]`** are internal-looking but stable — `data-renderer="lm"` in particular is a reliable marker for LM-generated content blocks in the thread.
- **File-artifact URLs from Cloudinary (`pplx-res.cloudinary.com`) are persistent; CloudFront presigned URLs (`d2z0o16i8xm8ak.cloudfront.net/?Policy=...&Signature=...`) expire.** If you need to archive, use the Cloudinary URL or `http_get` the CloudFront URL immediately.

## Debugging

Install hooks before submitting a task to capture the streaming transport:

```python
js(r"""
(()=>{
  if(window.__bu_hooked) return;
  window.__bu_hooked = true;
  window.__bu_fetch_log = [];
  window.__bu_ws_log = [];
  const of = window.fetch;
  window.fetch = async function(input, init){
    const url = typeof input === 'string' ? input : input.url;
    const r = await of.apply(this, arguments);
    window.__bu_fetch_log.push({t:Date.now(), url, method:(init?.method||'GET'), status:r.status, ct:r.headers.get('content-type')||''});
    return r;
  };
  const OrigWS = window.WebSocket;
  window.WebSocket = new Proxy(OrigWS, {construct(t,a){
    const ws = new t(...a);
    window.__bu_ws_log.push({t:Date.now(), type:'open', url:a[0]});
    ws.addEventListener('message', e => {
      const s = typeof e.data === 'string' ? e.data.slice(0,200) : '<<bin>>';
      window.__bu_ws_log.push({t:Date.now(), type:'msg', url:a[0], data:s});
    });
    return ws;
  }});
})()
""")
# ...submit a task...
print(js("window.__bu_fetch_log.filter(e=>e.url.includes('perplexity.ai')&&!e.url.includes('datadog'))"))
print(js("window.__bu_ws_log"))
```
