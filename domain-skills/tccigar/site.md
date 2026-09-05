# Treasure Coast Cigars (TCCigar.com)

## Promotion discovery

- Always screenshot the rendered homepage from scroll position zero. Major promotions can be presented only as hero-image text and may be absent from fetched HTML and `document.body.innerText`.
- Read the hero visually for the code, dates, and fine-print exclusions, then verify the code against exact products in the cart.
- Free shipping is advertised for orders of $76 or more.

## Shopify product and cart APIs

- Collection inventory is available at `/collections/<handle>/products.json?limit=250`; useful handles include `padron-cigars` and `arturo-fuente`.
- Apply a discount through `/discount/<CODE>?redirect=/cart`, then inspect the rendered cart total.
- Product variants use 14-digit Shopify IDs that exceed JavaScript's safe integer range. Pass variant IDs as strings to `/cart/change.js`; a numeric ID may be rounded and rejected.
- `/cart/add.js` can return `discounted_price` while also retaining an undiscounted `final_price`; trust the rendered cart total or `/cart.js` discount allocations for the applied total.
- Record the initial cart, add only test variants, and remove those exact variants afterward.

