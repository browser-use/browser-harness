# LinkCentre submissions

- Entry: `https://www.linkcentre.com/addurl/`. Entering a URL can lead to `/get-started/create/` on the main host.
- Free account creation can offer optional marketing consent. Account activation uses `secure.linkcentre.com/account/`; keep activation tokens private.
- Successful activation can take the browser straight to `secure.linkcentre.com/onboarding/add-listing/`, preserving the submitted website URL.
- The onboarding form imports generated copy and a category suggestion. Review and replace unsupported claims before submission.
- Stable fields include `title`, `description`, `category`, and `country`.
- An apparent **Business phone (required)** control named `business_phone_confirm` can be an offscreen one-pixel honeypot. Inspect visibility and actual validation before asking the owner for a phone number. Do not populate bot traps.
- Optional feedback is separate from the listing description. Leave it empty unless a real testimonial is authorized.
- The free plan can display only the first 255 description characters even when the input accepts 1000. Put the essential description first.
- **Submit Listing for Review** leads to `/status/<id>/`. **LISTING RECEIVED** and **Pending review** establish entry into the queue, not publication.
- A submission may appear on a public member profile before directory acceptance. The status page expressly distinguishes that from a directory listing.
