# LinkedIn — Feed extraction

Read posts off `https://www.linkedin.com/feed/`.

## Trap: every stable selector is gone

LinkedIn has stripped the well-known anchors used by older scrapers. As of
2026-04, on the logged-in feed, **none** of these match anything:

- `[data-urn^="urn:li:activity"]`, `[data-id^="urn:li:activity"]`
- `div.feed-shared-update-v2`, `article.feed-shared-update-v2`
- `.update-components-actor__title`, `.update-components-text`,
  `.feed-shared-update-v2__commentary`
- `.scaffold-finite-scroll__content > div`

The DOM still contains the post content, but every class is now an
obfuscated hash (e.g. `DIV.defd8bea c6cbe13b _36ab5d3a fb1c2865 …`) that
rotates across deploys. There are no `data-urn` / `data-id` attributes on
the cards, no `<article>` wrappers, no `role="region"` on individual posts.
**Do not invent a selector** — it will not survive the next deploy.

## What still works: split innerText on the "Feed post" label

The screen-reader label `Feed post` is rendered as a plain text node before
each card and is currently the only stable per-post boundary. Read the feed
container's `innerText` and split on it.

```python
import json

js_src = r"""(() => {
  const text = document.body.innerText;
  const parts = text.split(/\n\s*Feed post\s*\n/);
  // parts[0] is page chrome (nav, sidebar, "Sort by: Top"); skip it.
  return JSON.stringify(parts.slice(1));
})()"""
posts = json.loads(js(js_src))
```

Each chunk runs from the actor's name down to the next card's boundary, so
it includes the body, reactions count, and comment previews of the previous
post. Truncate at the first reaction-count line if you only want the body.

## Chunk shape

A typical organic post chunk:

```
<Actor Name>

 
 • <degree, e.g. 1st / 3rd+>

<Headline>

<Optional CTA: "View my services" / "Visit my website" / "Follow">

<time-ago, e.g. "1d •" or "6d • Edited •"> 

<body text>
… more

<optional structured card title, e.g. "Starting a new position">

<reactions int>
<reactions int>

<comments int> comments
<comments int> comments

Like
Comment
Repost
Send
<reaction emoji previews>
```

If the post surfaced because of a connection's activity, the chunk is
prefixed with a line like `Yuhong Sun likes this` or
`Yuhong Sun commented on this` *before* the actor name.

## Filtering ads and recommendations

`Feed post` is also emitted for promoted content and LinkedIn Learning
suggestions. Distinguish them by markers inside the chunk:

- **Promoted ad**: contains a line `Promoted` (after the company name and
  follower count, before the body). Skip if you want only organic posts.
- **LinkedIn Learning suggestion**: starts with
  `Popular course on LinkedIn Learning` and has no actor / time-ago.
- **Job recommendation**: starts with `Recommended for you` followed by a
  job-card layout (no time-ago, has `Apply` / `Save` buttons).

```python
def is_organic(chunk: str) -> bool:
    head = chunk.split("\n", 6)
    if any("Promoted" == ln.strip() for ln in head):
        return False
    if chunk.startswith(("Popular course on LinkedIn Learning",
                        "Recommended for you")):
        return False
    return True
```

## Sort order

The default feed is `Sort by: Top` (algorithmic), not chronological. If you
need recency, click the `Sort by: Top` dropdown and pick `Most recent` —
the URL does not change, so the only signal is the dropdown text.

## Pagination

The feed is an infinite scroller on the window itself (no inner scroll
container). To load more posts, scroll the window: `scroll(x, y, dy=2000)`
in `helpers.py` dispatches a wheel event that triggers the next batch.
Allow ~1.5s between scrolls for the new chunks to mount.
