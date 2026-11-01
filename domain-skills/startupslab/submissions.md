# Startups Lab submissions

- `/submit-product` starts with `#name` and `#website`, then Generate Launch Listing. Authentication may open a modal whose Continue to Sign In control is an anchor, not a button.
- `/login?redirectTo=%2Fsubmit-product` offers Google for automatic account creation. Email fields are for existing email accounts only.
- Google sign-in imports a personal public display name and avatar. `/profile` lets the maker edit `fullName`, `role`, `bio`, and `websiteUrl`, with a file input for the profile photo.
- The founder username is derived from the account email and cannot be changed in the profile form. Confirm it does not expose an unwanted identity before proceeding.
- Launch readiness requires profile photo, display name, role and short bio. Optional social links and skills affect the percentage indicator but are distinct from the essential launch-readiness fields.
- Profile Save Changes and submission are separate actions. Verify the saved brand identity before generating or publishing a launch.
- Generated products persist as drafts at `/my-products/<slug>/edit?new=true`. Auto-generated category, tags, pricing and features need review; a generic or unrelated category can be filled even when the source is a data-service website.
- The Free launch section can require both three other-product upvotes and three product-page visits before scheduling. A 100% product-completeness indicator does not establish that the free launch is eligible or submitted.

## Completing a free launch

- Launch availability and participation are lazy-loaded. Bring the Launch plan section into view before interpreting zero counts or No available Free launch Mondays; these can be placeholder states before requests fire.
- The observed read routes are `/api/user/participation` and `/api/launch-slots`. Respect the actual eligibility returned and the UI; do not bypass prerequisites.
- Visits can mean clicks on a product’s Visit Website link, not simply opening its platform detail page. Allow account hydration to finish before upvoting; optimistic button state alone does not prove the vote persisted. Reload and verify the action and participation count.
- A 100% product-completeness indicator can coexist with an insufficient launch description. The launch validator can require at least 200 words even when the draft saves a shorter description. Confirm & Save Launch Date reports this error; save the corrected factual copy before scheduling.
- Separate product Save Changes from Confirm & Save Launch Date. Verify status, plan and saved date after the scheduling action; a selected date is not a confirmed launch.
- The scheduled preview at `/product/<slug>` can be public before launch while carrying `noindex, nofollow`. Verify robots metadata separately from public accessibility and the presence of website links.
