# claude.ai — internal chat API

Read recent conversations and full transcripts from a logged-in claude.ai
session. Verified live 2026-07-07.

## The trap: plain HTTP gets Cloudflare-challenged

`http_get()` (cookieless urllib, generic UA) against any `claude.ai/api/*`
endpoint returns a Cloudflare managed challenge, never JSON. Don't fight it
with headers — run `fetch()` **inside an authenticated claude.ai tab**
instead: same-origin, real session cookies, real browser fingerprint. GET
endpoints need no CSRF header.

```python
tabs = [t for t in list_tabs(include_chrome=False) if "claude.ai" in t["url"]]
if tabs:
    switch_tab(tabs[0]["targetId"])
else:
    new_tab("https://claude.ai/recents")
    wait_for_load(20)

org_uuid = js("fetch('/api/organizations').then(r => r.json()).then(o => o[0].uuid)")
```

`js()` awaits promises, so a full fetch chain returns the resolved value.
If the session is logged out, the promise rejects and `js()` returns
`None` — check for it.

A 2026-07-02 attempt saw challenges even on plain CDP-tab *navigation* to
claude.ai; by 2026-07-07 navigation was clean. Treat navigation challenges
as transient; the in-page fetch pattern works either way once a tab is open.

## Endpoints (all relative to the tab's origin)

- `GET /api/organizations` — array; `[0].uuid` is the org for personal
  accounts.
- `GET /api/organizations/{org_uuid}/chat_conversations?limit=30` — array
  of `{uuid, name, updated_at, ...}`, newest first. `updated_at` is ISO
  8601 with `Z` suffix.
- `GET /api/organizations/{org_uuid}/chat_conversations/{uuid}` — one
  conversation; `chat_messages` is the transcript array:
  `{uuid, text, sender, index, created_at, updated_at, truncated,
  attachments, files, parent_message_uuid}` with `sender` ∈
  `human | assistant`. `text` is usually populated; when empty, look for
  `content` blocks (`[{type, text, ...}]`) — same shape as the claude.ai
  data-export format.

## Notes

- Large transcripts (150+ messages) return fine through
  `js()`/`returnByValue` — no pagination needed at conversation level.
- Keep payload prints single-line (`JSON.stringify`) if a wrapper script
  parses marker lines from stdout; JSON escapes embedded newlines.
