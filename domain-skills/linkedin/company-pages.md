# LinkedIn company pages (create + admin)

Field notes from creating a company page end-to-end and uploading logo/cover via CDP. LinkedIn's flagship web app is Ember with `artdeco-*` components.

## URL patterns

- Create flow: `https://www.linkedin.com/company/setup/new/` (page-type chooser, then one form).
- Slug availability: `GET /company/<slug>/` redirects to `/company/unavailable/` if the slug is free. If you administer the page, the same URL redirects to `/company/<id>/admin/dashboard/`.
- Public view while logged in as admin: append `?viewAsMember=true` (lands on `/company/<slug>/about/`).
- Edit overlay: left-nav "Edit Page" navigates to `/company/<id>/admin/dashboard?editPage=true`. Navigating to `/admin/edit/` directly just bounces back to the dashboard.

## Creation form traps

- The "verified work email on the company domain" requirement in LinkedIn's docs is NOT enforced by this flow (tested on an account whose emails were all on unrelated domains).
- **Slug auto-fill trap**: typing the company name auto-fills the slug field. If you then type into the slug field it appends rather than replaces, giving `nameName`. Cmd+A via `Input.dispatchKeyEvent` does not trigger native select-all; instead `el.focus(); el.select()` via JS, then `Input.insertText` replaces the selection.
- Industry is a typeahead: type, wait ~1s, click the suggestion row (committing requires selecting from the list; the preview pane updating does not mean it's committed).
- Organization size/type are native `<select>`s with ids like `text-entity-list-form-component-urn-li-fsu-pageCreationFormItem-ORGANIZATION-SIZE`. Set `.value` + dispatch `change`. Note the size option values use an en dash: `2–10 employees`.
- Logo: plain `input[type=file]`, use `DOM.setFileInputFiles`. 300×300 PNG works (16-bit PNG was accepted here, unlike the cover).
- The "I verify that I am an authorized representative" checkbox + "Create page" button finish the flow; success lands on `/company/<id>/admin/dashboard/`.

## Admin dashboard

- A **Premium upsell modal appears on nearly every admin dashboard load** and silently swallows coordinate clicks aimed at the page behind it. Dismiss it first (`button[aria-label*=dismiss i]`) before any other interaction.
- The edit overlay's sections (Page info, Buttons, Featured, Details, Workplace, Locations) are plain buttons/links matched by exact text, e.g. `Details` holds the About/Overview textarea (placeholder contains "About Us", 2000 char max). A `Save` button appears in the overlay header once dirty.

## Cover image upload

- Trigger: button `aria-label="Edit background"` (an `artdeco-dropdown__trigger`), then dropdown item with text `Add cover image`.
- That item is a `<label>` ("Upload single photo") wired to a hidden `input#org-admin-background-image-single-file-input` (`accept="image/*"`), which is only mounted after the dropdown item is clicked and is consumed after each attempt. Set files directly on it with `DOM.setFileInputFiles`; no need to intercept the file chooser.
- A Crop/Filters/Adjust modal opens; the confirm button is `Apply` (not Save).
- **Trap: "Cover image upload failed. Please try again."** after Apply, repeatedly, even though the image previews fine in the crop modal. The page state goes stale after the create-page flow + edit-overlay interactions in the same document. The fix is literally what the second error variant says: reload the dashboard URL, then redo dropdown → input → Apply. Same file succeeded immediately after a refresh. (Re-encoding 16-bit PNG → 8-bit JPEG was tried first and was not the fix, but covers are safer as 8-bit JPEG ≥1128×191; 2256×382 works.)
- Success toast: "Cover image updated".

## Settings (personal account, related)

- Adding an email address under Settings → Sign in & security fires a two-step challenge first: `/mypreferences/d/two-step-challenges?challengeType=EPC&...` sends a 6-digit code to the **primary** email before showing the add-email form. Abandoning the challenge is harmless.
