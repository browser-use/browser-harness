# PitchWall free submissions

- Free entry can use `/product/submit?plan=free`; authentication redirects through `/auth/login`.
- A stalled Microsoft callback is not an account-creation receipt. When the owner authorizes an alternative, Google sign-in can complete the flow.
- New accounts can land on `/account/profile` with a required username. Stable field names are `name`, `username`, and `about`. **Save changes** confirms profile readiness.
- Entering the product URL starts asynchronous product-detail generation. Wait for the actual detail form; its presence is not tied to document load completion.
- Review generated claims. Stable field IDs include `slug`, `title`, `summary`, `description`, and `video`.
- Tag chips are buttons. Clicking a selected chip removes it; the separate combined-label button opens the selector.
- **Next** creates an editable product draft. Upload images and a logo, save changes, and then use **Submit for Review**.
- A successful review submission leads to `/product/<slug>/status` with **Product Status: Under Review**. The free queue can exceed 30 days; paid upsells on this page are separate from the accepted free submission.
- Account sign-in terms can include newsletters. Inspect current terms and account notification controls.
