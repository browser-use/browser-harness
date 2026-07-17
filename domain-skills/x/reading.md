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
