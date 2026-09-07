# x.com — reading tweets & articles without login

## Tweets: syndication API (no auth, fastest)

`https://cdn.syndication.twimg.com/tweet-result?id=<TWEET_ID>&lang=en&token=<TOKEN>`

Token formula (mirror of the JS embed code): `((id / 1e15) * Math.PI).toString(36).replace(/(0+|\.)/g, '')`. In Python, emulate Number.toString(36) on the float (integer part base36 + ~12 fractional base36 digits), then strip `0` and `.`.

Returns JSON: `text`, `user`, `created_at`, `favorite_count`, `entities`, `conversation_count`, and for article tweets an `article` object with `title`, `preview_text`, `rest_id` — but **never the full article body**.

## Tweets: GraphQL guest token (no auth)

1. `POST https://api.x.com/1.1/guest/activate.json` with the public web bearer
   `Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA` → `guest_token`.
2. `GET https://api.x.com/graphql/2ICDjqPd81tulZcYrtpTuQ/TweetResultByRestId?variables=...&features=...` with headers `Authorization: <bearer>`, `x-guest-token: <token>`. Needs the long `features` flag dict (copy a current one; missing flags return explicit errors naming the missing flag, so it's self-correcting).

Works for regular tweets. For article tweets it again returns only `article.preview_text`.

## X Articles (x.com/i/article/<id>): login-walled — use mirrors

- Logged-out browser navigation to `/i/article/...` redirects to `x.com/i/jf/onboarding/web?...&mode=login`.
- The article GraphQL op is `ArticleByTweetId` (persisted query id found in `abs.twimg.com/x-web/x-web/assets/article-by-tweet-id-*.js`; variables `{restId: "<tweet_id>"}`, endpoint `https://api.x.com/graphql/<id>/ArticleByTweetId`). It returns `plain_text` + DraftJS `content_state.blocks` — but **404s for guest tokens**, both raw and from page context. Auth cookies (`auth_token` + `ct0`) required. Don't burn time here.
- **Fastest workaround: youmind.com mirrors viral X articles in full.** Web-search the article title + author handle; look for `youmind.com/landing/x-viral-articles/<slug>`. Plain `http_get` returns the entire article text in the HTML (no JS needed). Medium/plainenglish.io reposts also show up for viral posts.
- Wayback Machine generally has **no** snapshots of `x.com/i/article/...` URLs.

## Structure notes

- Tweet pages are the new `x-web` Rolldown/Relay app; bundles at `abs.twimg.com/x-web/x-web/assets/*.js`. Persisted GraphQL query ids live in per-route modules (`params:{id:\`...\`,name:\`OperationName\`}`); the endpoint template is in `environment-*.js` (`https://api.x.com/graphql/<id>/<name>`, GET with `?variables=` for queries).
- `x.com/<user>` profile HTML fetches fine logged-out with a desktop UA and lists all bundle URLs — useful for scraping current query ids.

## Reply threads (full conversation): logged-out page is walled — use the official API

- Logged-out `x.com/<user>/status/<id>` renders the root plus ONE reply, then a fixed
  "See all the replies / Continue to X" overlay. Scrolling loads nothing more. Don't fight it
  with coordinate clicks; the wall is a login redirect.
- `https://api.fxtwitter.com/<user>/status/<id>` gives the root tweet as clean JSON (text,
  author, counts, media, quoted tweet) with no auth — but no replies.
- For the replies, the reliable path is X API v2 recent search with a `conversation_id:` query.
  Needs an app with user-context OAuth1 (or a bearer) on a paid/pay-per-use plan:

  ```python
  # GET https://api.x.com/2/tweets/search/recent
  params = {"query": f"conversation_id:{ROOT_ID}", "max_results": 100,
            "tweet.fields": "author_id,created_at,referenced_tweets,note_tweet,public_metrics",
            "expansions": "author_id", "user.fields": "username"}
  # page with meta.next_token until absent; ~1s between pages is enough
  ```

  - Recent search only covers the last 7 days. Older threads need the full-archive endpoint.
  - Rebuild the tree from `referenced_tweets[type=replied_to].id`. Replies to a tweet that is
    not in the result set (deleted, or older than the window) come back as orphans — keep them.
  - Long posts arrive truncated in `text`; the full body is in `note_tweet.text`.
  - Volume reference: a 54-visible-reply post returned 262 tweets across 3 pages once nested
    replies were included.
