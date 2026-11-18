# X (x.com) — search posts

## URL pattern

- `https://x.com/search?q=<url-encoded query>&src=typed_query&f=top` shows the top posts.
- `f=live` shows the latest posts. `f=media` shows posts with media.
- Search needs a logged-in Chrome session. A logged-out session redirects to the login page.

## Query operators that work in the URL

- `"exact phrase"`, `A OR B`, `(A OR B) C`, `-word`
- `from:<handle>`, `min_faves:<n>`, `min_retweets:<n>`
- `-"some.domain"` removes posts that name a site. Use it to find posts about a topic without its main source.

## Read the results

Each result is an `article` element. `[data-testid=tweetText]` can return empty text, so use `article.innerText`.

```python
js("""JSON.stringify([...document.querySelectorAll('article')].map(a => {
  const u = [...a.querySelectorAll('a[href*="/status/"]')].map(x => x.href)
    .find(h => /status\\/\\d+$/.test(h)) || '';
  return {u, t: a.innerText.slice(0, 900)};
}))""")
```

- The permalink is the first `a[href*="/status/"]` whose URL ends in the numeric id. Other matches end in `/photo/1` or `/analytics`.
- The last lines of `innerText` are the counts in this order: replies, reposts, likes, views.
- A quoted post is inside the same `article`, so its text follows the main text.
- Outbound links are `t.co` short links. The visible text holds the shortened display URL.

## Scroll

- The result list is virtualized. Only about 5 to 10 `article` elements exist at one time.
- Collect after each scroll and remove duplicates by permalink: `js("window.scrollBy(0, 2400)")`, then wait about 2 seconds.
- Six scrolls give about 30 to 40 posts for a common query.

## Traps

- Wait about 4 seconds after `wait_for_load()`. The results load after the page load event.
- Long posts are cut at "Show more" in the result list. Open the permalink to read the full text.
- `from:<handle> <word>` also returns posts by other accounts in the `top` tab. Filter by the permalink.
- `min_faves` removes most small accounts. Run the query a second time without it to find small projects.
