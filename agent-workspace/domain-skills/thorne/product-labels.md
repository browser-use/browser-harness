# Thorne — rendered ingredients and future lifecycle notices

Observed on public `thorne.com/products/dp/<slug>` pages in September 2026.

## Rendering and labels

A web extraction may contain only a generic product shell while the rendered
Nuxt page shows the actual product. After a fetch-only result lacks the title or
label, inspect the browser and verify the product heading and displayed SKU.

- `[aria-label="Ingredients Information"]` identifies the ingredient navigation
  button; `#ingredients` is the corresponding section.
- `#transcript-ingredient-infodescription` contains the ingredient table.
- `#button-ingredient-info` exposes Show More / Show Less and `aria-expanded`.
  Verify the expanded state and visible table rather than assuming the first
  click or navigation immediately completed scrolling.
- Serving size and servings per container can sit above the table; other
  ingredients can be its final row. Capture these together.
- `#warnings` is separate from the ingredient section.

## Lifecycle is not one boolean

The observed product displayed **To be discontinued**, alongside disabled
**Out of Stock - Pre-Order** buttons. That is a future discontinuation notice and
an unavailable purchase control, not proof of completed discontinuation. Read
both the notice and the control's actual disabled state. Do not click checkout
or preorder merely to verify availability.

Keep the manufacturer's ingredient wording literal. Label matching does not
validate clinical effectiveness, dosing equivalence, product quality or broad
marketing safety claims.
