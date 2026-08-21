# X (Twitter) — Long-form Articles

Publishing a formatted **Article** (headings, bold, lists, blockquotes) to X. For login and posting plain tweets, see `posting.md` — this file is only about the Article editor.

There is **no public API for Articles** — the v2 API can only post a plain long-form *post* (≤25k chars), not the Article object. So the editor must be driven through the browser.

## Access

- Available on **regular X Premium** (no longer Premium+-only). If the account lacks it, `/compose/articles` shows an upsell instead of the editor.
- Must be logged in (see `posting.md`). If redirected to login, stop and ask the user.

## URLs

- `https://x.com/compose/articles` — Articles landing: **Drafts** / **Published** tabs + a **Write** button.
- `https://x.com/compose/articles/edit/<id>` — the editor for one draft. Clicking **Write** creates a new draft and redirects here.
- `https://x.com/compose/articles/edit/<id>/preview` — private "only you can view" preview render.
- After publishing, redirects to `https://x.com/<handle>/status/<id>` — the Article becomes a normal post on the timeline.

## Editor structure (Draft.js)

The body is a **Draft.js** editor — `div[data-testid="composer"]`, class `public-DraftEditor-content`. Each block is a `[data-block="true"]` div whose own className carries the type:

| Block type class | Meaning |
| :-- | :-- |
| `longform-unstyled` | normal paragraph |
| `longform-header-one` | big heading |
| `longform-header-two` | smaller heading |
| `longform-unordered-list-item` | bullet |
| `longform-blockquote` | quote (left bar) |

- **Title** is a separate `textarea[placeholder="Add a title"]` (plain text — no inline formatting). Click it and `type_text`.
- Toolbar offers: bold, italic, strikethrough, a "Body" heading dropdown, blockquote, bullet/numbered lists, link, emoji, Insert (media). **No code-block button and no tables.**
- Top bar: **Preview**, **Publish**, Focus-mode, **More** (`aria-label="More"`) which holds **Delete Article**.

## The key mechanic: inject content via a synthetic paste

Typing the body and clicking toolbar buttons per line is slow and fragile. Draft.js converts **pasted HTML** into its block types, so dispatch a `paste` `ClipboardEvent` carrying a `DataTransfer` with `text/html`. Focus the composer first (place a caret), then run via `js(...)`:

```js
var b = document.querySelector('[data-testid="composer"]');
b.focus();
var dt = new DataTransfer();
dt.setData('text/html', htmlString);
dt.setData('text/plain', plainString);
b.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles:true, cancelable:true}));
```

HTML → Draft mapping (verified):

- `<h1>` → header-one, `<h2>` → header-two
- `<p>` with `<strong>`/`<em>` → paragraph with bold/italic inline runs
- `<ul><li>` → bullet list items
- `<blockquote>` → blockquote (newlines inside survive as soft breaks)
- `<pre>` → **plain** paragraph (collapses; no code styling exists)

Converting markdown for this editor:
- **Inline code** `` `x` `` and `**bold**` → both `<strong>` (no monospace style exists; bold makes commands stand out).
- **Fenced code blocks** → `<blockquote>` (closest "set apart" look) — join the lines with `\n`.
- **Tables** → a bullet list, one `<li>` per row with the first cell bolded (`<strong>cmd</strong> — description`).
- The document's top-level `#` title → the **title textarea**, not the body.

Verify the result by reading back `[data-block="true"]` classes and/or opening **Preview**.

## Publish flow

1. Click **Publish** (top bar). A **"Publish Article"** dialog opens: audience (default *Everyone*), who-can-reply (default *Everyone*), a timeline-card preview, optional "Copy link to clipboard".
2. Click the dialog's own **Publish** button — there are **two** Publish buttons on screen, so scope the selector to `[role="dialog"]`.
3. Page redirects to the live `/<handle>/status/<id>` URL; a "Success! Your Article has been published" toast appears.
4. A **"Try Boosting this post!"** promo (paid ad) pops up — dismiss with **Maybe Later** unless the user wants to pay.

## Locating buttons

Buttons have no stable `data-testid` here, so locate by visible text / `aria-label`, read the rect, and `click_at_xy` the center — same pattern as `posting.md`:

```python
import json
r = js(r'''
  var el = [...document.querySelectorAll('span,div,a,button')]
    .find(e => e.textContent.trim() === 'Write' && e.offsetParent !== null);
  if (!el) return null;
  var t = el.closest('a,button,[role=button]') || el;
  var b = t.getBoundingClientRect();
  return JSON.stringify({x: Math.round(b.x + b.width/2), y: Math.round(b.y + b.height/2)});
''')
pos = json.loads(r)
click_at_xy(pos["x"], pos["y"])
```

## Traps

- **No table / no code-block support** — plan the markdown→HTML conversion around it (see above).
- **Cmd+A doesn't clear the editor**: Draft intercepts select-all, and `press_key("a", modifiers=4)` emits a `char` event that defeats the shortcut anyway. Easiest reset: **More → Delete Article → Yes, delete** and start a fresh draft, rather than fighting Draft's selection model.
- **Read coords from `getBoundingClientRect`, not the screenshot.** On a retina display the screenshot is 2× CSS pixels but `click_at_xy` takes CSS pixels — a pixel read off the image lands at double the intended offset. `getBoundingClientRect` is already CSS-space.
- Layout shifts between the list view and the editor — re-locate buttons after navigating.
- Each **Write** click leaves a new draft behind — delete throwaway drafts so the user's Drafts tab stays clean.
