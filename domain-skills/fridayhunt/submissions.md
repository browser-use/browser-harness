# FridayHunt project submissions

- `/projects/submit` redirects to `/sign-in?redirect=/projects/submit`. Email magic-link authentication is available; observe the expiry notice and use the intended mailbox.
- New accounts reach `/onboarding`, with `#name` and optional `#image`. Set the intended public maker identity before proceeding; `/dashboard` then confirms it.
- The four-step submission wizard covers essentials, details, launch date and review. IDs include `name`, `websiteUrl` and `shortDescription`. The short description has a 50–160 character limit and the detailed `.tiptap` editor requires 200–4500 characters.
- Logo and product image file inputs disappear after successful upload. Re-query before the next upload.
- Category/platform/pricing controls expose IDs such as `cat-ai`, `platform-web`, and `pricing-freemium`. Optional alternatives and affiliate-program claims should remain empty unless supported.
- The launch selector can default to Premium even though a Free Launch card is visible. Explicitly choose the free card and verify the final review says $0 before submitting.
- Week options can display only Available, with no visible date. Their hidden native select options contain ISO date values; the selected schedule summary supplies the UTC date before final submission. Do not infer a date from the option label.
- Free launches may provide a public listing without a dofollow backlink. The advertised enhanced backlink can require a top-three weekly ranking plus an embedded platform badge.
- Choosing the free card can open a Premium upsell modal and reset a previously selected premium date. Close the upsell, re-query availability, and respect disabled options; all currently offered free dates can have zero slots.
