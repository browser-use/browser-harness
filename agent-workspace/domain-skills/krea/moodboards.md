# Krea public moodboard discovery

Verified September 2026. Use this for read-only inspiration research and the text guidance attached to preset boards.

## Entry points

- Gallery: `https://www.krea.ai/app?gallery=moodboards`
- Public preset detail: `/moodboard-feed/<slug>-<uuid>?gallery=moodboards`
- The slug is the lowercase board name with non-alphanumeric runs replaced by hyphens, trimmed, truncated to 60 characters, then trimmed again. Use links returned by the page when available.
- Gallery controls expose names such as `Open <board name> moodboard` and `Back to previous`. Refresh state after opening a board: the URL may update before its content.

## Public read endpoints

The gallery's client loads preset boards with:

```text
GET https://www.krea.ai/api/preset-moodboards?limit=30&search=story%20book
GET https://www.krea.ai/api/preset-moodboards/<uuid>
```

Both returned JSON without authentication in the verified session. Use ordinary unauthenticated requests; do not extract cookies or credentials. If access changes, use the normal UI and stop at any authentication wall.

List parameters: `limit`, optional `cursor`, `seed`, `search`, and `imageUrl`. Do not transmit a private image URL merely to explore a gallery. Pagination returns `nextCursor`; treat it as opaque and pass it back unchanged. The response includes `datasetName`, `items`, `nextCursor`, and `total`. The `total` field remained the same across very different searches, so do not describe it as an exact count of matching boards.

List entries include `id`, `name`, `styleName`, `styleDescription`, `styleKeywords`, `previewImages`, and `images`. Image entries contain URLs and dimensions. Limit review to a useful sample instead of downloading entire boards.

The detail response includes `tasteProfile`, `keywords`, `generationGuidance`, `images`, and `imageUrls`. The names differ from the list response. Read the detail guidance as well as looking at images: a title can cover several quite different visual treatments.

Public detail HTML also contains those fields in hydration data. Prefer the JSON endpoint. Never evaluate hydration text or downloaded JavaScript. A regular `curl` GET can work when a Node fetch of the full HTML fails with a response-header size error.

## Boundaries and traps

- `/api/preset-moodboards` is the public preset feed; `/api/moodboards` concerns account boards. Do not confuse inspiration research with saving, cloning or changing account collections.
- Generated images are served at `https://gen.krea.ai/images/<uuid>.<extension>`. Public visibility does not establish permission to redistribute them as a product's assets.
- Inspect multiple images before concluding a board defines one consistent style. Some boards contain noticeably different character treatments or media.
- Search may be semantic ranking rather than exact filtering. Verify returned names and content, and try separate phrases such as `story`, `story book`, and `illustration`.
- On a controlled search input, confirm its displayed value after replacing text; native input actions can append instead. Confirm changed result names rather than assuming the typing succeeded.
- Avoid hardcoding versioned `_app/.../immutable/chunks/` URLs. They change with frontend deployments. The read endpoints above were verified from the gallery client itself.
