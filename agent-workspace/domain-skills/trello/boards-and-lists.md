# Trello — boards and lists

Read-only pattern for Trello: land on a board URL, scrape lists and their
cards. Works for signed-in agents that inherit Tom's Chrome session —
no login dance, no captcha.

## URL patterns

- `https://trello.com/` — marketing home for anonymous; when signed in,
  redirects to `https://trello.com/u/<username>/boards` (the dashboard).
  Note: `https://trello.com/boards` (no `/u/<username>`) returns an
  error page for signed-in users. Always route via `/u/<username>/boards`.
- Board URL: `https://trello.com/b/<8-char-boardId>/<slug>`. The `slug`
  is cosmetic — the boardId is the canonical identifier.
- Card URL: `https://trello.com/c/<8-char-cardId>/<n>-<slug>`, where
  `<n>` is the card's 1-based position within its list at creation time.

## Stable selectors

- List: `[data-testid="list"]` — or `[data-list-id]` for the id. Returns
  exactly the lists on the board, no sidebar noise.
- List header: within a list, `[data-testid="list-header-name"]`.
  Falling back to `h2` inside the list also works, but the board's
  outer chrome has h2s too (sidebar plans etc.) — stay scoped to the
  list element.
- Card: `a[href*="/c/"]` — scoped to each list element. The `href` is
  the canonical link; the visible text is the card name.
- Card name within the anchor: `[data-testid="card-name"]`. Anchor
  `innerText` is a reasonable fallback.

## Site structure

The board page is a single-page React app. All lists render in one pass
into horizontally scrolling columns. Cards within a list are vertical.
Count via `document.querySelectorAll('[data-testid="list"]').length` —
matches the visible column count.

## Framework / interaction quirks

- `goto_url('https://trello.com/')` redirects asynchronously to the user's
  boards dashboard. After `wait_for_load()`, the URL in `page_info()`
  will be `.../u/<username>/boards`. Don't hard-code the username;
  read it back from `page_info()['url']` if you need it.
- On initial load the board's lists can take ~1-2 s to render after
  `wait_for_load()` returns. A brief `time.sleep(2)` before scraping is
  reliable; alternatively, wait for `[data-testid="list"]` to be
  present with a count > 0.

## Waits

- `wait_for_load()` on the board URL returns before all lists/cards are
  in the DOM. The list containers appear first (empty), then cards
  populate. Wait for a non-zero card count inside a list before
  declaring "done".

## Traps

- A board user-link scrape (`a[href^="/b/"]`) on the dashboard returns
  each board twice (recent + starred/all). Deduplicate by `href`.
- Sidebar h2 headings include plan names ("Standard", "Premium") —
  don't treat them as list names. Scope header reads to elements
  inside `[data-testid="list"]`.

## Read-only, one-hit scrape (JS-as-extract, fast path)

```js
(() => Array.from(document.querySelectorAll('[data-testid="list"]'))
  .map(list => ({
    name: list.querySelector('[data-testid="list-header-name"]')?.innerText?.trim(),
    cards: Array.from(list.querySelectorAll('a[href*="/c/"]'))
      .map(a => ({
        href: a.getAttribute('href'),
        title: (a.querySelector('[data-testid="card-name"]')
                ?? a).innerText.trim()
      }))
      .filter(c => c.title)
  })))()
```

Wrap in `js(...)` + `json.loads()` and you have structured board data
in one round trip.

## What NOT to capture here

Private API endpoints (Trello exposes `https://trello.com/1/...` REST
endpoints, but those need a token). Keep this file DOM-only. If you
discover public API shapes worth documenting, put them in a
separate `api.md` under this skill folder.
