# Skool Classroom — reading and editing course/lesson content

Skool communities (`skool.com/<group>`) have a Classroom of courses; each course contains
modules (lessons). As a group admin you can read and write every lesson programmatically —
no editor UI automation needed.

## URL patterns

- Classroom index: `/{group}/classroom`
- Course page: `/{group}/classroom/{courseName}` where `courseName` is an 8-hex slug
  (`metadata` calls it `name`; the long hex `id` is a different field).
- A specific lesson: `?md={moduleId}` (the long 32-hex module id).
- Edit mode: `&e=1`.

## Reading course data (Next.js)

Everything is in `__NEXT_DATA__` / the `/_next/data/` endpoint:

- Classroom index page props: `pageProps.allCourses` — every course's `{id, name, metadata}`.
- Course tree: `pageProps.course` = `{course, children: [{course, children}, ...]}`.
  Course unit `unitType` is `course` | `module` (Skool calls lessons "modules"; `set` exists
  for sections in bigger classrooms).
- Data endpoint: `/_next/data/{buildId}/{group}/classroom/{courseName}.json?md={moduleId}&group={group}&course={courseName}`
  with cookies. Grab `buildId` from any captured `/_next/data/` request or `__NEXT_DATA__`.
- **Redirect trap:** without `md=`, the JSON comes back as
  `{"pageProps":{"__N_REDIRECT":"/{group}/classroom/{name}?md=<firstModuleId>"}}` — parse the
  `md` out of it and refetch.
- **Lazy-desc trap:** the course tree only hydrates `metadata.desc` for the module selected
  by `md=`. All other modules show `desc: ""` even when they have content. To dump a whole
  course you must fetch once per module id.

## Lesson content format

`metadata.desc` is `"[v2]" + JSON.stringify(tiptapNodes)` — a TipTap/ProseMirror node array
(no wrapping `{type:"doc"}`; the array is the document).

Supported by the editor toolbar (and confirmed rendering): `heading` (attrs.level 1–4),
`paragraph`, `bulletList`/`orderedList` (+`listItem` containing `paragraph`), `blockquote`
(renders as a styled callout), `codeBlock` (`attrs:{language:null}` is fine),
`horizontalRule`, `hardBreak`; marks: `bold`, `italic`, `strike`, `code`, and
`link` (`attrs:{href, target:"_blank", rel:"noopener noreferrer nofollow", class:null}`).
Content written this way round-trips cleanly through Skool's own editor.

**Trap:** pasting markdown into the Skool editor stores it as literal text — `# `, `- `,
`**bold**` all show verbatim to members, often as one `paragraph` full of `hardBreak`s.
To fix, split paragraph content on `hardBreak`, parse the markdown yourself, and write real
nodes back.

## Writing a lesson

```text
PUT https://api2.skool.com/courses/{moduleId}
content-type: application/json  (cookie auth — do it via in-page fetch with credentials:'include')
{"title": "...", "desc": "[v2][...]", "transcript": null, "video_id": ""}
```

- This is exactly what the editor's SAVE sends. It does NOT touch `metadata.resources`
  (attached files/links survive).
- **Preserve `video_id`** — if the lesson has a video attached, send its existing id, not `""`.
  (Check `metadata.videoLink` before writing.)
- The server re-serializes `desc` with its own JSON key order, so verify writes by parsing
  and comparing structurally, not by string equality.

## Waits

- Lesson body is client-rendered after hydration; large descs (≥15 KB) can take 10–30 s to
  appear on a long-lived automation tab while the title + Resources render immediately.
  Poll `document.body.innerText` for a known phrase before concluding a lesson is broken.
