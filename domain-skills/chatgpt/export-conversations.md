# chatgpt.com — exporting conversations & projects via backend API

Scraping chat DOM is the wrong tool here. The page's own backend API returns full
conversation JSON, and the auth token is one fetch away.

## Auth

```js
const s = await fetch('/api/auth/session', {credentials:'include'}).then(r=>r.json());
const tok = s.accessToken;   // Bearer token for all /backend-api/* calls
```

`s.user` is null when logged out — poll this to detect login instead of reloading.
Note: from a logged-out tab this endpoint can return anon even right after the user
logs in elsewhere; reload the tab once before concluding they aren't logged in.

## Projects ("g-p-" gizmos)

Sidebar project chats link to `/g/g-p-<32hex>/c/<conv-uuid>` — sidebar items are NOT
`<a>` tags until a project is expanded (click the project name first, then query
`a[href*="/c/"]`).

- Project metadata (name, custom instructions, author): `GET /backend-api/gizmos/g-p-<id>`
- All conversations in a project (paginated by `cursor`):
  `GET /backend-api/gizmos/g-p-<id>/conversations` → `{items: [{id, title, update_time}], cursor}`

## Full conversation content

`GET /backend-api/conversation/<uuid>` → `{title, create_time, mapping, current_node}`.

- `mapping` is a node tree; the *active* thread = walk `current_node` → `parent` → … → root, then reverse.
- Message content types worth handling:
  - `text` — `content.parts[]` strings
  - `multimodal_text` — parts mix strings and dicts; dict `content_type`s include
    `audio_transcription` (**voice chats — the text is in `.text`**; skip
    `audio_asset_pointer` / `real_time_user_audio_video_asset_pointer`) and image
    asset pointers (`width`/`height` present)
  - `thoughts`, `reasoning_recap` — model reasoning, usually skip
- Filter `author.role` to `user`/`assistant` and drop messages with
  `metadata.is_visually_hidden_from_conversation`.
- Merge consecutive same-role turns — assistant answers often span several nodes.

## Traps

- Assistant text is littered with citation placeholders: `citeturnNsearchM` tokens
  wrapped in Unicode private-use chars (U+E200 range). Strip
  `/[-](?:cite|navlist|video)?[^-]*?[-]/g`.
- The `js()` helper evaluates an *expression* — wrap multi-statement fetch code in
  `(async () => { ... })()` or you silently get `None`.
- Rate: ~1 req/sec on /backend-api/conversation was fine for 11 conversations (~6MB).
