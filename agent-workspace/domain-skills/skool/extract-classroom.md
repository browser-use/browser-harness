# Skool - extract classroom content (courses, lessons, rich text)

Field-tested 2026-06-10 on a paid community (member access). Login required for everything;
anonymous visitors get 404/redirect-to-home even for community About pages.

## The private API: Next.js data routes

Skool is Next.js. DOM scraping is the wrong tool - lesson pages hydrate client-side and
`main` is nearly empty before hydration. Use the `/_next/data/` JSON routes with the page's
cookies via in-page `fetch(..., {credentials:'include'})`.

- buildId: `JSON.parse(document.getElementById('__NEXT_DATA__').textContent).buildId`
- Course list: the `/<group>/classroom` page's `__NEXT_DATA__` -> `props.pageProps.allCourses`
  (each: `id`, `name` = URL slug, `metadata.title`, `metadata.hasAccess`, `metadata.numModules`)
- Lesson content: `GET /_next/data/<buildId>/<group>/classroom/<courseSlug>.json?md=<moduleId>`
  -> `pageProps.course` tree with THAT module's `metadata.desc` hydrated

## Traps

- **`?md=` takes the module ID (32-hex), not the slug.** Slug 404s.
- **Direct browser navigation to `?md=` URLs is a server-side 404.** The route only exists
  client-side. Fetch the data route instead; no navigation needed per lesson.
- **Without `?md=`, the course data route returns a redirect envelope**, not data:
  `pageProps.__N_REDIRECT = "/<group>/classroom/<slug>?md=<id>"`. Follow it once - extract
  the `md` from the redirect target and refetch.
- **`pageProps.selectedModule` is just the module ID string**, not an object. The content
  lives on the module node inside `pageProps.course` -> `children` tree -> `metadata.desc`.
- **Tree shape**: course -> `children` (type `set`) -> `children` (type `module`). Nodes are
  sometimes wrapped: use `u.course || u` before reading `metadata`.
- **`metadata.desc` is TipTap/ProseMirror JSON prefixed with `[v2]`.** Strip the prefix,
  parse, walk nodes. Skool uses the NON-standard type `unorderedList` (not `bulletList`) -
  miss it and every bullet list silently flattens to run-on text.
- **Locked tiers**: courses without `metadata.hasAccess` are higher-tier; their data routes
  won't return content. Skip them - do not try to circumvent.
- **Useful metadata per module**: `videoLink` (YouTube/Loom/etc), `videoLenMs`,
  `videoThumbnail`, `resources` (JSON string array of attachment links).

## Pacing

One data-route fetch per lesson, ~300ms apart, all from one logged-in tab. ~85 lessons in
about 2 minutes. No headless browser, no per-lesson navigation.
