# Pyramid Cigars deal verification

Pyramid Cigars is a Shopify storefront. Product and collection HTML can lag behind live variant inventory, so verify limited cigar deals through Shopify's JSON endpoints and the cart rather than trusting search snippets or rendered list prices.

## Live inventory endpoints

- Product variants: `https://pyramidcigars.com/products/<handle>.js`
- Collection products: `https://pyramidcigars.com/collections/<collection>/products.json?limit=250`

For each variant, check `available`, `price`, and the variant `id`. Do not infer box availability from an available single or 5-pack on the same product page.

## Referral discounts

Some Cigar Deal Hunters / Smoking Hub offers use a referral session instead of a visible coupon. Visiting:

`https://pyramidcigars.com/collections/premium-rares?ref=cigardeals`

can establish an automatic discount for eligible Premium Rares items. The product page continues to show the original price. Add the exact variant to an isolated cart and inspect `final_line_price` from `/cart.js` to confirm the actual discount.

Use an isolated cookie jar or a clean browser session so verification does not alter the user's existing cart. Never report the discount from the banner alone; compare `original_line_price` and `final_line_price` after the item is in the cart.

## Common trap

Search indexes and cached product HTML can claim a box is in stock while the live `.js` variant has `available: false`. The live variant JSON and a successful cart add are the authoritative checks.
