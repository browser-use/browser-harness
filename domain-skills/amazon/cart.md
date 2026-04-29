# Amazon — Shopping Cart

Field-tested against amazon.com on 2026-04-22 using a logged-in Chrome session.

## URL

```
https://www.amazon.com/gp/cart/view.html
```

## Empty-cart trap

**Do not use `[data-asin]` to detect whether the cart has items.** The cart page renders an "Items you may like" recommendation strip and other widgets that also carry `data-asin` attributes — a naive scrape returns 8–12 ASINs even on a fully empty cart.

Check the empty-state string first:

```python
empty = js("""
  document.body.innerText.includes('Your Amazon Cart is empty')
""")
```

If `empty` is true, stop — do not enumerate items.

## Subtotal

When the cart has items, the active subtotal lives at:

```
#sc-subtotal-amount-activecart   (or)   #sc-subtotal-amount-buybox
```

These elements are **absent from the DOM entirely on an empty cart** (not just empty-string). A `null` here is consistent with the empty-state check above; do not treat it as "subtotal hidden."

## Price-change banners

Amazon renders an "Important messages about items in your Cart" panel above the cart contents whenever a watched item's price has moved (up or down). The panel includes Saved-for-later items, not just active cart items. The text format is stable:

```
... has increased from $X to $Y
... has decreased from $X to $Y
```

These are worth surfacing to the user on every cart visit — they are not redundant with the cart contents themselves.

## Saved for later

The "Saved for later" section is on the same URL as the cart, rendered below the active cart. Item count is shown as `Saved for later (N items)` in the section header. For a user with many saved items this can be hundreds — do not assume the section is small.

## Gotchas

- **`[data-asin]` ≠ cart contents.** Recommendations and "Items you may like" carry `data-asin` too. Always anchor cart-item scrapes inside `[data-name="Active Items"]` (or check the empty string first), never on the bare attribute.
- **Subtotal selectors are absent, not empty, when the cart is empty.** `querySelector(...)` returns `null`, which is the correct signal.
- **The page is logged-in only.** If a non-cart "Sign in to see your cart" page appears, treat as auth wall and stop.
