# Nordic Naturals — Supplement Facts drawer

Observed on `nordic.com` public product pages in September 2026.

- Product route: `/products/<slug>/`; the selected Shopify variant may be in
  `?variant=<id>`. Preserve that variant when recording the source.
- A visible **Supplement Facts** button opens a right-hand drawer. Locate its
  button by accessible name, click, and verify the open drawer before reading.
- The open dialog is exposed as `[role="dialog"][aria-label="Supplement Facts"]`;
  `#supplement-facts-dialog` contains the label HTML.
- `button[aria-label="Close supplement facts sidebar"]` closes the drawer.
- The label includes serving size, servings per container, amounts, ingredient
  qualifiers and other ingredients. Read the whole label, not only the product
  description or search-result snippet.

Indexed or fetch-extracted text can omit this drawer's table. An absent table in
a search result is not evidence of an empty label. Similarly named mushroom
blends can have different formulas; a multi-product search snippet can mix them.
Verify the exact product and selected variant before attributing ingredients.
