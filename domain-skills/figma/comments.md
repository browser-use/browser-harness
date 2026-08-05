# Figma — reading file comments

Figma comments are invisible to the Plugin API — plugins cannot read them at
all. The official REST endpoint (`api.figma.com/v1/files/:key/comments`) needs a
personal access token and is metered. But the web app's own internal API serves
the full comment set with nothing but the session cookies already in the
browser.

## The endpoint

```
GET https://www.figma.com/api/file/<FILE_KEY>/comments
```

Same-origin from any `www.figma.com` page, so call it with `js()` from
wherever you already are:

```python
r = js("""
const xhr = new XMLHttpRequest();
xhr.open("GET", "/api/file/<FILE_KEY>/comments", false);
xhr.send();
const d = JSON.parse(xhr.responseText);
const byId = {}; d.meta.forEach(c => byId[c.id] = c);
return JSON.stringify(d.meta
  .filter(c => !c.is_deleted)
  .sort((a,b) => b.created_at.localeCompare(a.created_at))
  .slice(0, 15)
  .map(c => ({
    at: c.created_at, who: c.user.handle, msg: c.message,
    reply_to: c.parent_id ? (byId[c.parent_id]?.message ?? null) : null,
    resolved: !!c.resolved_at
  })), null, 1)
""")
```

The file key is the middle segment of any share URL:
`figma.com/design/<FILE_KEY>/<slug>`.

## Response shape

`{ meta: [...] }` — one flat array, every comment in the file (threads
included). Useful fields per comment:

- `message` — plain text; `message_meta` is the structured form
- `user.handle` / `user.img_url` — author display name
- `parent_id` — non-null on replies; join against `id` to rebuild threads
- `created_at`, `resolved_at`, `is_deleted`
- `client_meta` — the pin: node id + offset when anchored to a node
- `thumbnail_url` — pre-rendered crop around the pin (`commentx`/`commenty`
  query params carry the pin position)

## Traps

- `figma.com/design/<key>` URLs auto-launch the **desktop app** and leave the
  tab on an interstitial ("Opened ... in Figma app" / "Open here instead").
  No need to click through — the interstitial is on `www.figma.com`, so the
  comments XHR works right there without ever loading the heavy editor.
- `/api/comments?file_key=<key>` does **not** exist (404). The file-scoped path
  above is the real one.
- Don't wrap your expression in your own IIFE with an inner `return` — the
  `js()` helper wraps anything containing `return ` in its own function, and a
  self-wrapped IIFE gets double-wrapped into an expression whose outer wrapper
  returns nothing. Write a bare top-level `return` and let the helper do it.
