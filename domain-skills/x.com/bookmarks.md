# x.com — Bookmarks (`/i/bookmarks`)

How to extract a user's bookmarked tweets reliably.

## URL & API

- Page: `https://x.com/i/bookmarks`
- Private GraphQL endpoint hit on initial load and on every pagination:
  `https://x.com/i/api/graphql/<hash>/Bookmarks?variables=...&features=...`
  - Match with `/\/Bookmarks\?/` — note: there is also a separate
    `BookmarkFoldersSlice` request which is unrelated (folder list).
  - The hash in `<hash>/Bookmarks` rotates; do not pin it.

## Transport: XHR, not fetch

X uses **`XMLHttpRequest`** for the Bookmarks call. Patching only `window.fetch`
will see zero hits. Hook both XHR and fetch to be safe.

## Inject the hook BEFORE page scripts

`document.body`-level `js(...)` patches arrive too late — X has already issued
the initial Bookmarks XHR by then. Use:

```python
cdp("Page.addScriptToEvaluateOnNewDocument", source=PATCH_JS)
cdp("Page.reload", ignoreCache=False)   # if already on /i/bookmarks
# or new_tab("https://x.com/i/bookmarks")
wait_for_load()
```

`Page.addScriptToEvaluateOnNewDocument` runs before the page's own scripts on
every navigation/reload, so the very first Bookmarks XHR is captured.

## Pagination: `End` key, not mouseWheel

X's lazy-load only fires on a real "scroll near bottom" signal. The harness's
`scroll(x, y, dy=-N)` (CDP `Input.dispatchMouseEvent` mouseWheel) does **not**
trigger pagination — confirmed: 150 mouseWheel iterations yielded only the
initial 20 tweets.

What works:

```python
js("window.scrollTo(0, document.body.scrollHeight)")
press_key("End")
time.sleep(1.5)
```

This consistently fires the next `/Bookmarks` XHR. Empirically 1.2–1.6s between
scrolls is enough; faster than that and X coalesces.

## Response shape

```
data.bookmark_timeline_v2.timeline.instructions[].entries[]
  .content.entryType == "TimelineTimelineItem"
  .content.itemContent.tweet_results.result
      .rest_id                           # tweet id
      .legacy.id_str
      .legacy.full_text                  # tweet body
      .legacy.created_at                 # "Mon Apr 20 04:25:49 +0000 2026"
      .legacy.entities.urls[].expanded_url  # outbound links
      .core.user_results.result.core.screen_name        # NEW path
      .core.user_results.result.legacy.screen_name      # legacy path (also present)
```

Tombstoned tweets sometimes wrap the result in a `{"tweet": ...}` outer object
— always do `tweet = ir.get("tweet", ir)` defensively.

## What's NOT exposed

- **`bookmarked_at`** — Twitter does not expose when the user bookmarked the
  tweet, only the tweet's own `created_at`. If you need to time-bound a sync
  (e.g. "last 4 months"), use tweet `created_at` as a coarse signal and
  tolerate a few consecutive old tweets before stopping (bookmark-time order
  ≠ post-time order, so you can briefly slip below the cutoff and recover).

## Stop conditions

Two independent counters:
- **consecutive_old**: tweets older than cutoff seen in a row → end of useful
  range. ~4 tolerated before stopping.
- **consecutive_empty**: scroll iterations that produced no new tweets → end
  of bookmarks. ~5 tolerated before stopping.

## Reference implementation

See `bookmark-sync/twitter/pull.py` in the user's Projects dir.
