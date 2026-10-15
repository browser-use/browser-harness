# Neptune Cigar

## Promotions and coupon detection

- Do not rely on homepage body text, search snippets, or product-list extraction alone. Take a screenshot of the rendered homepage/header and cart because active promotions can appear as a small coupon badge beside the cart.
- The active coupon badge is exposed at `#couponContent` / `#couponCode`. The coupon code is in `data-value`; the rendered text includes the percentage and expiration. Example shape: `<div id="couponCode" data-value="CODE"><span class="classValue">21%</span> ...`.
- Coupon state is session/cart dependent, so inspect the rendered badge after opening the site and again after adding an item.

## Product and cart verification

- Product variants use `button.pr_ddBtn` with IDs such as `btn<variantId>` and an inline `addToCart(this, <variantId>)` handler.
- The shopping cart route is `/shopping-cart`. Eligible products show a cash coupon line in totals. Restricted products are explicitly labeled `Excluded From Coupon` on their cart row.
- During percentage promotions, restricted products may receive `BONUS POINTS` instead of cash savings. Report bonus Smoke Rings separately from the cash-discount calculation.
- Gift-with-purchase items can be inserted automatically and appear as additional cart items at $0.
- Before testing, record the existing cart. Remove only test items and verify the original cart state afterward. Cart item detail IDs appear in trash handlers such as `RemoveItem('<detailId>')`; the underlying service is `NeptuneWebServices.UpdateShoppingCart(detailId, '0', callback)`.

