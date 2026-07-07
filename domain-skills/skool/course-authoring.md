# Skool — classroom course authoring (api2.skool.com)

Create and fill classroom courses via Skool's private API. Auth is httpOnly cookies, so make
credentialed `fetch(..., {credentials:"include"})` calls **from a logged-in Skool page context**
(run them via `js(...)` / `Runtime.evaluate`). Must be a group admin.

## IDs you need first

Load any classroom page, then read the SSR blob:
```js
const pp = window.__NEXT_DATA__.props.pageProps;
pp.currentGroup.id     // group_id
pp.self.id             // user_id  (must be group-admin: pp.self.member.role)
```

## Content format: `[v2]` bare array (NOT doc-wrapped)

A lesson body (`desc`) is the literal string `[v2]` followed by compact JSON of a **top-level ARRAY**
of TipTap block nodes — NOT `{"type":"doc","content":[...]}`. If you have a doc-wrapped TipTap doc,
unwrap it: `"[v2]" + JSON.stringify(doc.content)`. Supported nodes seen in the editor toolbar:
paragraph, text (marks: bold, italic, strike, code, link), heading (H1–H4), bulletList/orderedList/
listItem, blockquote, codeBlock, horizontalRule, hardBreak, image, video. Simplest reliable subset:
paragraphs of text+marks, with `• `-prefixed lines for bullets.

## The three calls

**Create course (root):** `POST https://api2.skool.com/courses` → 200, returns the object incl. `id`.
```json
{"group_id":G,"user_id":U,"unit_type":"course","state":2,"is_afl_comp_eligible":false,
 "metadata":{"title":"...","desc":"...","cover_image":"","privacy":0,"min_tier":0}}
```
`state:2` = published (state:1 = draft/unpublished). `privacy:0` = Open (all members).

**Create module/lesson:** same `POST /courses` → 200, returns `id`. `unit_type` is `"module"` for
BOTH section headers and lessons — the hierarchy is by `parent_id`:
```json
{"group_id":G,"user_id":U,"parent_id":<parent id>,"root_id":<course id>,
 "unit_type":"module","state":2,"metadata":{"title":"...","resources":"[]"}}
```
- Section under the course: `parent_id = root_id = course id`.
- Lesson under a section: `parent_id = section id`, `root_id = course id`.
- **3-level nesting (course → section → lesson) works and renders** as sidebar sections with lessons.
- **Display order = creation order.** There is no order field — create sequentially (await each).

**Set lesson content:** `PUT https://api2.skool.com/courses/<id>` → **204**. Body is a FLAT 4-field
object — NOT the metadata-wrapped create shape (sending the create shape returns 200 but silently
no-ops):
```json
{"title":"...","desc":"[v2][...]","transcript":null,"video_id":""}
```

**Delete:** `DELETE /courses/<id>` → 200. Deleting a section cascades to its lessons.

## Traps (field-tested)

- **Title max = 50 chars.** Titles ≥ 51 fail the create with **HTTP 422** (silent in the UI). Keep
  sidebar titles ≤ 49; put the full title as an H1 in the body if needed. 50 exactly passed, but stay under.
- **Update needs the flat body.** The create body's `{...,metadata:{desc}}` shape does nothing on PUT.
  Discover/confirm by editing one lesson in the UI and capturing the PUT (see below).
- **Do NOT navigate the page while a fetch loop is running** — a reload kills the JS context and the
  loop dies mid-way, leaving a partial course. Run the whole loop in one page context.
- **Large payloads break the harness socket.** Injecting >~100KB in a single `Runtime.evaluate`, or
  awaiting a 60+ call loop synchronously, times out the unix socket. Instead: push the payload in
  chunks (per module), then FIRE the loop without `awaitPromise` while it writes progress to a global
  (`window.__PROGRESS`), and POLL that global with short separate calls until `done`.
- **`__NEXT_DATA__` is a stale SSR snapshot** — it does not reflect creates/deletes made this session.
  For live tree state, `GET /courses/<course id>?group_id=G` → `{course, children:[{course, children}]}`.
- **URL scheme:** course landing `/<group>/classroom/<course 8-char name slug>`; a specific lesson is
  `?md=<lesson FULL id>` (the full 32-char id, NOT the short name). Wrong md → 404/Oops page.

## Reference: capture any create/update call

Enable `Network`, do the action once in the UI, drain events, filter `api2.skool.com` requests for
`postData` + status. The "Add course" dialog's Published toggle + Open radio map to `state:2`,
`privacy:0`. Editing a lesson and clicking SAVE emits the flat `PUT /courses/<id>`.
