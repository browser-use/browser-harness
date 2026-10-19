# Google Docs: insert formatted content (headings, lists, tables, links)

## The fast path: a synthetic HTML paste into the text-event iframe
Docs draws its pages on a canvas, so `execCommand` and DOM edits on `.kix-page` do nothing. Keyboard input goes through a hidden contenteditable inside `iframe.docs-texteventtarget-iframe`. A **synthetic `ClipboardEvent('paste')`** carrying `text/html` in its `DataTransfer` is accepted, and Docs converts the HTML into real Docs formatting:
- `<h1>`–`<h3>` become Heading 1–3 and appear in the left outline;
- `<ul>`/`<ol>` (nested too) become real lists;
- `<table border="1">` becomes a real table (header row kept);
- `<a href>` becomes a clickable link; `<b>`/`<i>` are kept.

```python
import json
html = open("doc.html").read()          # an HTML fragment, e.g. `pandoc -f markdown+autolink_bare_uris x.md -t html`
js("""(h=>{
 const f=document.querySelector('iframe.docs-texteventtarget-iframe');
 const t=f.contentDocument.querySelector('[contenteditable=true]')||f.contentDocument.body;
 t.focus();
 const dt=new DataTransfer(); dt.setData('text/html',h); dt.setData('text/plain','');
 return t.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));
})(%s)""" % json.dumps(html))
```
- `dispatchEvent` returns **false**. That's expected: Docs calls `preventDefault()` and handles the paste itself. Check with `screenshot()`, not with the return value.
- ~18 KB of HTML (8 pages, 4 tables, 12 links) pasted in one event, in about 2 s.
- The paste lands at the cursor. To replace everything first, focus the iframe target, then `press_key("a", modifiers=2)` (Ctrl+A) and `press_key("Delete")`.
- Bare URLs in markdown only become links if pandoc gets `-f markdown+autolink_bare_uris`.

## Other stable handles
- **Signed-in account:** `[aria-label*="Google Account"]`. Its aria-label contains the email, so check it before writing to make sure you're in the intended account. `/document/u/N/` switches between the signed-in accounts.
- **Rename the doc:** click the title text at the top left (it becomes an input), Ctrl+A, `type_text(name)`, Enter. The tab title updates within about 1 s.
- **Scroll container:** `.kix-appview-editor` (set `scrollTop`). Window scrolling does nothing.
- An empty doc shows "Templates / Meeting notes / Email draft" chips. They vanish once there's content and need no dismissal.
