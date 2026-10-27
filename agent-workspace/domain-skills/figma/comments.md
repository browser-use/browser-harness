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
(async () => {
  const response = await fetch("/api/file/<FILE_KEY>/comments");
  if (!response.ok) throw new Error("Comments request failed: " + response.status);
  const data = await response.json();
  if (!Array.isArray(data.meta)) throw new Error("Comments response has no list");
  const byId = Object.fromEntries(data.meta.map(c => [c.id, c]));
  return data.meta.filter(c => !c.is_deleted)
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
    .map(c => ({
      at: c.created_at, who: c.user?.handle ?? null, msg: c.message,
      reply_to: c.parent_id ? (byId[c.parent_id]?.message ?? null) : null,
      resolved: !!c.resolved_at
    }));
})()
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
- The current `js()` helper awaits returned promises and accepts an async function expression.
