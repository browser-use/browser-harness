# Skool — reading community and classroom content

Skool (skool.com) communities are login-walled Next.js apps. Do not scrape the DOM for
classroom content — the structured data is already on the page.

## URL patterns

- Community feed: `skool.com/<group>`
- Classroom (course list): `skool.com/<group>/classroom`
- Course: `skool.com/<group>/classroom/<courseSlug>` (slug is 8 hex chars, not the course id)
- Lesson: `skool.com/<group>/classroom/<courseSlug>?md=<lessonId>` (32-hex module id)

## Private data source: `__NEXT_DATA__`

All classroom data lives in `window.__NEXT_DATA__.props.pageProps`:

- `allCourses` — every course in the group (id, name/slug, metadata.title, metadata.desc,
  metadata.hasAccess). Available on any classroom page.
- `course` — populated ONLY on a course page (`/classroom/<slug>`): full tree of
  `{course: {id, metadata: {title, desc, videoLink}}, children: [...]}` covering modules
  and lessons. This gives you every module/lesson title and id in one read.
- Lesson body: `metadata.desc` of the lesson node — but it is only populated for the
  lesson currently loaded via `?md=<id>`. To pull N lessons, do N full-page navigations
  (`?md=` each id) and read that lesson's `desc` from the refreshed `course` tree each time.

`desc` format: the string starts with `[v2]` followed by ProseMirror-style rich-text JSON
(`{"type":"paragraph","content":[{"type":"text","text":...}]}` nodes, plus `codeBlock`,
`image` with `src` on assets.skool.com, `heading`, lists). Strip the `[v2]` prefix and
walk `content` recursively collecting `text` nodes to get plain text.

## Traps

- Course cards on `/classroom` are NOT `<a href>` links — `querySelectorAll('a[href*="/classroom/"]')`
  returns nothing. Click the card (locate by its title text, click the bounding-box centre),
  or navigate directly by URL once you know the slug.
- SPA sidebar lesson clicks are unreliable for switching lessons; full-page navigation to
  `?md=<lessonId>` always works and repopulates `__NEXT_DATA__`.
- `metadata.hasAccess` gates paid tiers — lessons in locked courses have no `desc`.
- Community feed posts also live in `pageProps` (renderData) — check there before DOM-scraping.
