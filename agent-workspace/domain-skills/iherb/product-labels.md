# iHerb — exact product labels and lifecycle

Observed on public, signed-out US/English product pages in September 2026.
Use a plain fetch first; if it times out or returns an incomplete page, inspect
the rendered product page. No account or cart operation is needed for labels.

## Identity and layout

- Product URLs use `/pr/<descriptive-slug>/<numeric-item-id>`. Slugs can change
  on redirect, including an added `discontinued-item`, while the numeric ID stays
  the same. Verify the final ID, selected package and UPC; a similar name is not
  sufficient to substitute another item.
- `#name` / `[data-testid="product-name"]` is the selected product heading.
- `#product-specs-list` contains product code, UPC and package quantity.
- A package selector can offer several counts or strengths. Retain the selected
  variant's identity alongside any extracted facts or prices.

## Supplement Facts: two observed layouts

1. Active pages may have an already-visible `.supplement-facts-container` with a
   table containing serving size, servings per container and labeled amounts.
2. A discontinued page used a collapsed `[data-toggle-type="product-supplement-facts"]`
   header and `#product-supplement-facts` body. Find the visible header's button
   in the accessibility tree, scroll it into view, click, then verify that the
   facts body is visible before extracting it.

Do not require an accordion on every page. Do not try to click the zero-sized
rectangle of a hidden body. After scrolling or expanding, allow layout to settle
and verify the full table visually. Capture the facts container, not just its
heading. Other ingredients may be in an adjacent block.

## Discontinued-product and price traps

- `.product-summary-unbuyable-message` can explicitly say the item is
  discontinued and no longer available. `#product-action` may be empty in this
  layout; it is not a reliable lifecycle source on its own.
- The same page can prominently show a **Similar Recommendation** with a price.
  That price belongs to another product, not the discontinued item.
- Active buying panels can show subscription, one-time and promotional prices
  together. Keep purchase type, package, currency/region and capture time
  attached; do not treat the lowest visible number as the one-time price.
- Page-wide text includes categories, recommendations and reviews. Searching the
  entire body for an ingredient can falsely attribute another product's formula
  to the selected item. Use its actual Supplement Facts and other ingredients.
- A retailer discontinuation notice concerns that retailer listing; it does not
  establish that the manufacturer discontinued the product globally.

Preserve label wording and serving basis. A salt amount, an ingredient amount
"as" a salt and a free-form amount are not automatically interchangeable.
