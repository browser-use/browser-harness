# Cigar Place — product inventory and cart checks

`https://www.cigarplace.biz` uses a Magento-style catalog. Its rendered search
and category tables expose price and availability per packaging option.

## Find canonical product URLs

The root sitemap is complete and is easier than guessing slugs:

```python
import re

xml = http_get("https://www.cigarplace.biz/sitemap.xml")
urls = re.findall(r"<loc>(.*?)</loc>", xml)
matches = [u for u in urls if "late-hour" in u.lower()]
```

Useful brand-category routes include:

- `/all-brands/padron-cigars/padron-1964-anniversary-maduro.html`
- `/all-brands/padron-cigars/padron-1926-serie-maduro.html`
- `/all-brands/padron-cigars/padron-family-reserve.html`
- `/all-brands/padron-cigars/padron-maduro.html`
- `/all-brands/winston-churchill-the-late-hour.html`

## Extract pack-specific rows

Each product's first table row contains `.product-name a` and
`.product-size`; subsequent rows for other pack sizes omit those cells because
of `rowspan`. Carry the most recent product name and URL forward while walking
all `tr` elements.

Stable selectors:

- name and URL: `.product-name a`
- size: `.product-size`
- packaging: `.col-packaging`
- MSRP: `.col-msrp`
- displayed price: `.col-price`
- availability/action: `.col-action`

Within `.col-action`, `Add to Cart` means that exact packaging row is
purchasable; `Notify Me` means it is out of stock. Do not infer all variations'
stock from the product detail page: that page displays one selected pack at a
time.

## Cart confirmation

On a product detail page the selected pack can be added with the visible
`.button.btn-cart` control. Verify the result with a screenshot of
`/checkout/cart/`; the cart lists product, packaging, MSRP, price, quantity,
subtotal, sales tax, and excise tax. Shipping requires a country and postal
code, so do not report a final shipping or tax total before those values are
provided.

Current shipping rules and recurring promotions are described at these stable
routes:

- `/shipping/`
- `/first-of-the-month-shipping/`
- `/early-bird-special/`

Check the homepage banner before treating a time-limited shipping promotion as
active.
