# Mighty Networks (*.mn.co) — reading community feeds

Applies to any Mighty Networks community on `<community>.mn.co` (or a custom domain running Mighty).

## No usable API

- The feed is server-rendered and hydrates without JSON XHR — `performance.getEntriesByType('resource')` shows no data fetches after load.
- Guessing REST paths fails: `/api/web/v1|v2/...`, `/api/v2/...`, `/api/mobile/v2/...` all return 404 JSON. Scrape the DOM.

## URL patterns

- `/feed` — the logged-in member's personal feed (aggregates followed spaces).
- `/spaces/<id>/feed` — a space's feed. Spaces have three types and the server redirects to the real one:
  - discussion space → stays on `/feed` (has `li.feed-item` cards)
  - chat space → redirects to `/spaces/<id>/chat` (message list, no feed items)
  - static page space → redirects to `/spaces/<id>/page` (no posts at all)
  A space returning zero `li.feed-item` is not necessarily empty — check `location.href` for `/chat` or `/page`.
- `/posts/<id>` — post permalink; `/posts/<id>/comments` — its comments.
- Not logged in → redirect to `/landing`. Detect this instead of scraping a sign-in page.

## Stable selectors (feed)

Each post card is `li.feed-item`:

- `.feed-attribution-container` — author name + space + post age ("2w ago" = when the post was **created**)
- `.feed-item-story` — activity line ("X reacted to this 1w ago") = why it's ranked here; null if no recent activity
- `.feed-item-post-description` — body snippet (also `.feed-item-post` for the title link text)
- `a[href*="/posts/"]` — permalink
- `a[href$="/comments"]` — comments link

Default feed sort is **last activity**, so post age (attribution) and activity age (story) differ — use attribution for "how old is this post".

Sidebar space list: `a[href*="/spaces/"]` (dedupe — links repeat inside feed cards).

## Chat spaces

The chat view loads near the bottom but the newest messages can still be below the fold — scroll down (`scroll(x, y, dy=800)` a few times) before concluding what the latest message is. Date separators ("Fri, Jul 24") are plain text rows between messages.
