# Bunjang search scraping

## Search route

Use the mobile-web search route:

```text
https://m.bunjang.co.kr/search/products?order=date&page=1&q=<url-encoded-query>
```

The `page` query parameter does not reliably expose deep results. Repeatedly changing it can return nearly the same first result set.

## Cursor pagination

The initial page server-renders roughly 50 product cards. Scroll to the bottom, dismiss the app-install bottom sheet via the `모바일 웹에서 볼게요` action if it appears, then click the exact `더보기` button once.

That click calls:

```text
GET https://api.bunjang.co.kr/api/search/v8/web/search
  ?q=<query>
  &policyKey=mw.product.keyword
  &cursor=<opaque-cursor>
  &size=60
```

Read products from:

```text
data.responses.mainGrid.searchResponse.data[]
```

Keep entries where `type == "PRODUCT"` and `pid` exists. External ads also appear in the same array.

Continue with the opaque `nextCursor` returned at:

```text
data.responses.mainGrid.searchResponse.nextCursor
```

Stop when `nextCursor` is absent. Deduplicate by `pid`; `totalCount` includes non-product and repeated entries, so it may be larger than the final unique product count.

## Product details

Unauthenticated product details are available at:

```text
GET https://api.bunjang.co.kr/api/pms/v3/products-detail/<pid>?viewerUid=-1
```

Important fields are under `data.product` and `data.shop`. Product images use the `imageUrl` template; replace `{cnt}` with `1..imageCount` and `{res}` with a desired width such as `840`.

## Traps

- Do not infer price from a whole card's concatenated text. Years, denominations, and ages can be appended to the price.
- Do not treat a title as reliable material or authenticity evidence. Read the detail description and inspect all images.
- A single scroll only exposes the first result set. The exact `더보기` button is the transition to cursor pagination.
