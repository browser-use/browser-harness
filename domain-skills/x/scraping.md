# x.com (Twitter) — profile timeline scraping

Requires a logged-in session (use the user's Chrome). Logged-out x.com shows a login wall after ~2 tweets.

## Timeline extraction

- Each tweet is `article[data-testid="tweet"]`.
- Permalink + timestamp: the `a[href*="/status/"]` that contains a `time` element (`time.getAttribute('datetime')`).
- Text: `[data-testid="tweetText"]` innerText. Two of these in one article means the second is a quoted tweet.
- Engagement: the `[role="group"][aria-label]` aria-label carries "N replies, N reposts, N likes, N bookmarks, N views" in one string.
- Truncation: long posts show `[data-testid="tweet-text-show-more-link"]`. Timeline text stops mid-sentence at ~280 visible chars.
- Pinned/repost banner: `[data-testid="socialContext"]`.
- Media: `[data-testid="tweetPhoto"]`, `video`. Link cards: `[data-testid="card.wrapper"]`.

## Virtualized scroll loop

The timeline unloads offscreen tweets, so extract-then-scroll in a loop and dedupe by permalink in Python:

```python
seen = {}
for i in range(30):
    for tw in json.loads(js(EXTRACT_JS) or "[]"):
        seen.setdefault(tw["link"], tw)
    js("window.scrollBy(0, 2200)")
    wait(1.4)
```

~60 tweets in ~30 iterations. Faster scrolling skips tweets; 1.4s per step was reliable.

## Full text of long posts

Open the status page (`x.com/<user>/status/<id>`): the detail view renders the complete text in the first `article[data-testid="tweet"]`, no Show more click needed. Wait ~2.5s after load.

## Traps

- Standalone link-reply tweets (self-replies carrying just a URL card) have empty `tweetText`; filter on text length.
- Aria-label omits zero-count stats ("667 views" only), so parse defensively.
