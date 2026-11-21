# BuiltByIndies product submissions

- `/submit` requires authentication. Profile editing is at `/profile/edit`; first/last name, username and bio IDs are `firstName`, `lastName`, `username`, and `bio`.
- Google authentication can import a personal name and username. Inspect and update public identity before submitting on behalf of a brand.
- Product fields include `name`, `url`, `tagline`, `.ql-editor[contenteditable=true]`, and `#logo-upload`. Category and technology stack are distinct custom searchable menus.
- Stack results can include a logo image inside the clickable item. A selector looking for a childless text node may miss it; locate the result by its current image alt or whole item text.
- A selected category changes its search input placeholder. Search inputs and menu overlays can retain focus after selection: dismiss the previous menu before entering another field.
- At least three cover images are required. Image inputs disappear/reorder after upload; re-query them for each file. Use separate actual project views rather than duplicate images.
- Save Draft persists the filled form before editing the profile elsewhere. Completing the product fields does not constitute a launch.
- Submit Product can redirect to `/upgrade?product_id=...`, offering free and paid plans. Join Queue on the free plan can reveal a mandatory five-other-product upvote gate. Inspect this final gate before claiming a free launch was accepted.
- A public maker/brand profile at `/<username>` can already contain website links while the separate product launch is gated. Verify it anonymously and inspect robots metadata and anchor rel attributes; report the brand profile and unsubmitted product launch as different outcomes.
