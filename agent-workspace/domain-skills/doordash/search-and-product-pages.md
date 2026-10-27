# DoorDash — cross-store product search, product pages, store info (logged-in Chrome)

The contributor tested `doordash.com` on 2026-09-26 through browser-harness with a logged-in desktop Chrome session.
The contributor reports approximately 600 searches and 100 product pages.
Each request uses in-page `fetch()` from an open `doordash.com` tab.
The requests use the existing session and delivery address.

---

## Traps first

- ⚠️ **The search page never calls its search API from the client.** `/search/store/<query>/` is SSR;
  hooking `window.fetch` and typing in the search box only shows `autocompleteFacetFeed` and
  `externalStores`. The results come from `searchWithFilterFacetFeed`, executed server-side. Its query
  document is embedded in the page's RSC payload as a GraphQL **AST** (`{"kind":"Document",...}` next to
  `"variables":{"cursor":"","filterQuery":"","query":"<q>",...}`), so print the AST back to a query
  string once and POST it yourself (below). It works as-is: no persisted-query hash.
- ⚠️ **`products`-style fields are not where items are.** Item cards are FacetV2 nodes with
  `component.category == "card.retail_item"`; the data is the JSON *string* in `custom`.
- ⚠️ **The product-page endpoint answers 502 without a cursor** in its "item first" form, and only the
  "Get it now" section's cards carry one. The cursor can be built (see below).
- ⚠️ **browser-harness `js()` times out after 5s.** A batch of searches takes longer: start an async job
  that stores its result on `window`, return immediately, then poll with short `js()` calls.
- A handful of `HTTP 429` (HTML body, not JSON) appeared at 3 concurrent requests over ~600 searches;
  a retry after ~10–40s succeeds. Treat 401/403 as logged-out / bot check and stop.

## Delivery address (what every result is relative to)

```
POST /graphql/consumer?operation=consumer
{"operationName":"consumer","variables":{},
 "query":"query consumer { consumer { id defaultAddress { street city state zipCode printableAddress lat lng } } }"}
```

Headers for every GraphQL call: `content-type: application/json`, `x-channel-id: marketplace`,
`x-experience-id: doordash` (cookies come from the page). Arbitrary GraphQL documents are accepted.
Search results, store distances and ETAs follow `defaultAddress`, not the IP: a non-US exit IP with a
US delivery address searched that address's stores. Check the ZIP before trusting any result.

## Search across all nearby stores

```
POST /graphql/searchWithFilterFacetFeed?operation=searchWithFilterFacetFeed
variables: {"cursor":"", "filterQuery":"", "query":"<text>", "isDebug":false, "searchType":""}
```

Root: `searchWithFilterFacetFeed { body { id header {...FacetV2} body {...FacetV2} } page header footer custom logging }`
with the usual `FacetV2Fragment` (`id component{id category} name text{title subtitle ...} images events style
layout custom logging childrenMap{...}`). Walk `body[].header`, `body[].body` and every `childrenMap`.

- Sections (by `logging.item_first_search_section_id` of the cards): `get_it_now`, `top_savings`,
  `all_results`, then one carousel per store ("All stores"). One query returns ~150–700 cards from ~15
  stores (Target, Best Buy, Staples, Office Depot, Walgreens, CVS, Lowe's, Home Depot, Kohl's...). The
  same item repeats across sections: dedupe on `store_id:item_id`.
- Relevance is loose: "JBL Flip 6" put JLab earbuds first in "Get it now". Filter yourself.
- ~1–4 s per search, 1–2.5 MB of JSON (mostly the `custom` strings).

`JSON.parse(card.custom)` gives:

| field | path |
|---|---|
| ids | `item_data.item_id`, `item_data.store_id`, `item_data.menu_id`, `logging.business_id` |
| cross-store product id | `item_data.dd_sic` (`urpc_...` / `ugp_...`), same across stores |
| name / store | `item_data.item_name`, `item_data.store_name` |
| price | `item_data.price.display_string`, `.unit_amount` (cents); list price `logging.non_discount_price` |
| product rating | `logging.item_star_rating`, `item_num_star_rating`, `item_num_of_reviews` (also `price_name_info.default.base.ratings`) |
| badges | `logging.badge_entries[]` → `badgeType` / `badgeUseCase` / `badgeText` |
| link | `on_click.deep_link_navigate.path` (`browse/products/<dd_sic>?cursor=...` only in "Get it now") |

**Stores name one product differently**: for one `dd_sic`, Best Buy said "JBL Flip Portable
Waterproof Drop-Proof Black Speaker" while Staples said "JBL Flip 7 Portable Waterproof Bluetooth
Speaker". When matching products by name, pool the names of every card with the same `dd_sic`.

Badge use cases seen on retail items: `recently_bought` ("700+ recently sold", type `social_proof`),
`percent_discount` ("27% off"), `loyalty_price`, `item_promo_canonical`, `map_item` ("Promo excluded"),
stock (`high_stock_3p`, `x_in_stock`, `low_stock_3p` = "Likely out of stock", `out_of_stock_3p`) and
`item_ratings`. There is no "Best seller" badge on retail items.

## Product page (the modal a result opens)

```
POST /unified-gateway/retail/v1/pdp
{"screen_type":"SCREEN_TYPE_MOBILE","request_fields":{"_type":"item_first_request_fields","dd_sic":"<dd_sic>","cursor":"<cursor>"}}
{"screen_type":"SCREEN_TYPE_DESKTOP","request_fields":{"_type":"store_request_fields","store_id":"<s>","item_id":"<i>",
  "aggregate_store_ids":[],"should_enable_navigate_to_store":false}}
```

- `product_page[]` has one entry per store selling the product (item-first form) or just the one store
  (store form): `product.name`, `product.price_list[0].price`, `product.breadcrumbs_category_list.categories[].name`
  (`["Target","Electronics","Audio"]`), `logging.badge_entries`, `components[]` (`_type` `brand`,
  `item_price`, `metadata_entry` → `badge.ratings.ratings{average,count_of_ratings,count_of_reviews}`,
  `collapsible_sections` → "Specifications" table with Brand / Model Number / ...).
- `store_selector.store_list[]`: every nearby store with that product, its price and ETA.
- ⚠️ **Only the item-first form has breadcrumbs**; the store form returns `categories: []` and no store list.
- ⚠️ **Item-first needs a cursor.** It is base64url( 4-byte big-endian length + an LZ4 block ) of text:

  ```
  {{<store_id>|t|~|~}}|{{<item_id>|<menu_id>|<store_id>|<business_id>|t}}|{GLOBAL_SEARCH_PAGE}|<query>|all_results
  ```

  (real ones list more stores in the second group). An LZ4 block of one literal-only sequence is valid,
  so no compressor is needed: token `0xF0` + length-15 in 255-steps (or `len<<4` under 15), then the
  bytes. A built cursor returned the full page with breadcrumbs for every store.

## Store info

```
query storepageFeed($storeId: ID!, $menuId: ID, $isMerchantPreview: Boolean, $fulfillmentType: FulfillmentType) {
  storepageFeed(storeId: $storeId, menuId: $menuId, isMerchantPreview: $isMerchantPreview, fulfillmentType: $fulfillmentType) {
    storeHeader { id name business { id name } address { street city state displayAddress lat lng }
                  ratings { numRatings numRatingsDisplayString averageRating } distanceFromConsumer { value label } } } }
```

Works for retail/convenience stores (Best Buy, Target, Staples, Walgreens...), `fulfillmentType: "Delivery"`.

## URLs

- `https://www.doordash.com/convenience/store/<store_id>/product/<item_id>` → redirects to
  `/convenience/store/<store_id>?product_id=<item_id>` and opens that product's modal at that store.
- `https://www.doordash.com/browse/products/<dd_sic>` → `/products/<slug>/<dd_sic>`, the cross-store page.
- `/convenience/store/<store_id>/item/<item_id>` is a 404.
