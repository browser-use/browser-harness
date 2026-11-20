# Medium — Publishing a Story

Composing and publishing a Medium story by driving the editor. For *reading* Medium, see `scraping.md` (APIs) and `article-hydration.md` (DOM extraction) — this file is the write path.

There is **no public API for publishing** (the legacy Medium API stopped issuing integration tokens), so the editor must be browser-driven.

## URLs

- `https://medium.com/new-story` — creates a draft; once it autosaves it redirects to `/p/<id>/edit`. **If it never redirects, the draft isn't saving** (see throttle trap).
- `https://medium.com/p/<id>/edit` — the editor for one draft.
- `https://medium.com/p/<id>/submission?...` — the publish panel (preview card, topics/tags, Publish button).
- `https://medium.com/me/stories/drafts` — drafts list; each row's hover "Toggle actions" (kebab) menu has **Delete story**.
- Published canonical: `https://medium.com/@<handle>/<slug>-<id>` (short form `https://medium.com/p/<id>`).

## Editor structure (classic "graf" editor)

One big contenteditable: `div.js-postField` (class `postArticle-content js-postField … editable`, `role=textbox`, `data-default-value="Title\nTell your story…"`). Blocks are `.graf` elements whose class names carry the type:

| graf class | meaning |
| :-- | :-- |
| `graf--title` | the story title — the FIRST block (an `h3` styled as title) |
| `graf--h3` | big heading |
| `graf--h4` | small heading |
| `graf--p` | paragraph |
| `graf--li` | list item |
| `graf--pre graf--preV2` | code block (syntax-highlighted) |
| `graf--blockquote` | quote |

Inline runs: `<strong>`, `<em>`, and **`<code>` (inline code is preserved as monospace)**.

## The key mechanic: inject content via a synthetic paste

Medium converts pasted HTML into `.graf` blocks. Focus the contenteditable, then dispatch a `paste` `ClipboardEvent` with a `DataTransfer` holding `text/html` (run via `js(...)`):

```js
var ed  = document.querySelector('.js-postField,[contenteditable="true"]');
var tgt = document.activeElement && document.activeElement.isContentEditable ? document.activeElement : ed;
var dt = new DataTransfer();
dt.setData('text/html', htmlString);
dt.setData('text/plain', plainString);
tgt.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles:true, cancelable:true}));
```

HTML → graf mapping (verified):

- **First `<h1>` of a paste into a *fresh* editor → `graf--title`** (the title). Subsequent `<h1>/<h2>/<h3>` → `graf--h3` (big heading); `<h4>` → `graf--h4` (small heading).
- `<p>` with `<strong>/<em>/<code>` → paragraph with inline runs.
- `<ul><li>` → bullet list; `<blockquote>` → blockquote.
- `<pre>` → code block (`graf--pre`). **Newlines inside one `<pre>` are collapsed** — and so are `<br>` and `<pre><code>…</code></pre>`. For multi-line code, emit **one `<pre>` per line** (consecutive `<pre>` stay as separate code blocks).

Converting markdown for this editor: `##`→`<h3>`, `###`→`<h4>`, inline code `` `x` ``→`<code>`, `**x**`→`<strong>`, tables → bullet list (`<li><code>cmd</code> — desc</li>`), code fences → one `<pre>` per line.

## Setting the title reliably

The title is finicky. Two working options:

1. **Prepend `<h1>{title}</h1>`** to the body HTML and paste into a *fresh* editor with the caret at the top — the first `<h1>` becomes `graf--title`. (If you click into the body first, that `<h1>` becomes a body heading instead and the title stays empty.)
2. **Place the caret in the title block via JS, then `type_text`:**
   ```js
   var t = document.querySelector('.graf--title');
   var ed = document.querySelector('.js-postField'); ed.focus();
   var r = document.createRange(); r.selectNodeContents(t); r.collapse(true);
   var s = getSelection(); s.removeAllRanges(); s.addRange(r);
   ```
   Clicking the empty title block does **not** focus it (it has near-zero height when empty). If this leaves a duplicate heading, select that block's contents with a JS range and delete it with **real** `Backspace` key events (not `execCommand`).

## Adding tags (publish panel)

Topic input is `input[placeholder^="Add a topic"]` (becomes `Add more topics…` after the first tag). Commit each tag with **JS `.focus()` + a char-less trusted Enter**:

```python
js("document.querySelector('input[placeholder^=\"Add\"]').focus()")
cdp("Input.dispatchKeyEvent", type="keyDown", windowsVirtualKeyCode=13, key="Enter", code="Enter")
cdp("Input.dispatchKeyEvent", type="keyUp",   windowsVirtualKeyCode=13, key="Enter", code="Enter")
```

`press_key("Enter")` does **not** commit (its synthetic `char` event defeats it), and **comma is rejected** ("Tags only support letters, numbers, spaces and dashes"). Up to 5 tags.

## Publish flow

1. Click the top-bar **Publish** → the submission page opens.
2. Preview title/subtitle auto-populate from the story title; add tags.
3. Click the **Publish** ("Publish now") button at the bottom of the panel.
4. Redirects to `/p/<id>?postPublishedType=initial`; read `link[rel="canonical"]` for the public URL.

## Traps

- **No publishing API** — browser-drive only.
- **New-draft creation throttles.** After creating several drafts quickly, `/new-story` stops redirecting to `/p/<id>/edit` and won't save (no error, just no persistence). **Editing an existing draft still saves fine** — reuse a known-good draft, or space out creation.
- **`execCommand('delete')` to clear the editor corrupts Medium's save model** → red banner "Something is wrong and we cannot save your story." Don't clear that way. A single clean paste into a fresh/empty editor saves fine; for edits use real key events.
- **`Cmd+A` select-all doesn't register via CDP** (even with `commands:["selectAll"]`), same as other rich editors.
- **`beforeunload` freezes navigation** when there are unsaved changes — `Page.navigate`/`goto_url` times out. Recover with `cdp("Page.handleJavaScriptDialog", accept=True)`, then continue. Opening a fresh tab avoids the dialog entirely.
- The per-code-block **"Auto (C#)" language label is an in-editor hover artifact** — the published view is clean.
- **Retina DPR=2**: read coordinates from `getBoundingClientRect`, never off a screenshot (`click_at_xy` takes CSS pixels).
