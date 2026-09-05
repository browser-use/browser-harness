# Cigars Daily — product inventory and variants

`https://cigarsdaily.com` runs WooCommerce. For catalog, price, and stock
checks, use the public Store API before scraping the rendered search page.

## Search the catalog

```python
import json
from urllib.parse import quote

products = json.loads(http_get(
    "https://cigarsdaily.com/wp-json/wc/store/v1/products"
    f"?search={quote('Padron')}&per_page=100"
))
```

Useful parent fields are `name`, `permalink`, `type`, `prices`, `variations`,
`is_purchasable`, and `is_in_stock`. Money in `prices` is expressed in minor
units; divide by `10 ** currency_minor_unit`.

## Verify each pack size separately

Do not use the variable parent's `is_in_stock` to claim that a particular box
or pack is available. Each object in `variations` has an `id`; fetch that ID as
a product:

```python
variant = json.loads(http_get(
    f"https://cigarsdaily.com/wp-json/wc/store/v1/products/{variation_id}"
))

result = {
    "pack": variant["variation"],
    "price": variant["prices"]["price"],
    "purchasable": variant["is_purchasable"],
    "in_stock": variant["is_in_stock"],
    "stock_text": variant["stock_availability"]["text"],
    "max_quantity": variant["add_to_cart"]["maximum"],
}
```

The variation endpoint supplies the exact pack price, pack-specific stock, and
maximum purchasable quantity. The HTML search page can show only the first 25
results behind a `LOAD MORE` control, so the API is both faster and more
complete.

## Visual verification

For a first visit use `new_tab()`, then capture a screenshot. Search pages use
the standard WordPress route:

```python
new_tab("https://cigarsdaily.com/?s=Padron&post_type=product")
wait_for_load()
wait(2)
screenshot("/tmp/cigarsdaily-search.png")
```

The page explicitly appends `- Out of Stock` to unavailable variation labels,
which is a useful visual cross-check against the Store API.
