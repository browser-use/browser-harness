# RevenueCat dashboard (app.revenuecat.com)

React SPA. Logged out, it redirects to `/login` (email first, then password). Don't touch `/forgot_password`, which sends a reset email.

## URL shape

Project IDs are 8 hex characters.

- `/overview`: all-projects overview with one chip per project. Chips are `a[href="/projects/{projectId}/overview"]`; read the IDs from those rather than using the project-switcher dropdown, whose items didn't respond to coordinate clicks.
- `/projects/{projectId}/apps`: the apps table (name, app ID, bundle ID, masked public key), SDK version stats, and the "Test configuration" card.
- `/projects/{projectId}/apps/{appId}`: app config. The App Store app page has an "In-app purchase key configuration" section. When a key is uploaded, it shows the `.p8` filename, a "Valid credentials" badge, the Key ID and the Issuer ID. A sticky "Save changes" button stays disabled until something is edited.
- `/projects/{projectId}/product-catalog/{offerings|products|entitlements}`.
- `/projects/{projectId}/product-catalog/entitlements/{entitlementId}`: the "Associated products" list.
- `/projects/{projectId}/paywalls`: empty state offers "Use a template", "Create from scratch" and "Generate using AI". A paywall attaches to an offering, so it needs one first.
- `/projects/{projectId}/targeting`: placements and targeting rules. On plans below Pro, it shows "Unlock Targeting / Upgrade to Pro" instead.
- `/projects/{projectId}/api-keys`: secret keys and SDK (public) keys, masked. The eye icon next to a key reveals it, and clicking again hides it. Public SDK keys are prefixed `appl_` (App Store) or `test_` (Test Store).

List pages (offerings, products, entitlements) have an All / Active / Inactive filter. Offerings default to Active, so check All before concluding there are none.

## Don't steal the user's keyboard

`switch_tab()` calls `Target.activateTarget`, which brings the tab to the front. If the user is typing in Chrome at the same time, their keystrokes land in your form. For long form-filling sessions, work in a background window instead:
`cdp("Target.createTarget", url=..., newWindow=True, background=True)`, then attach with `Target.attachToTarget` + `_send({"meta": "set_session", ...})` (no activate). Also call `cdp("Emulation.setFocusEmulationEnabled", enabled=True)` so dropdowns and inputs behave as if focused. Screenshots and coordinate clicks still work because the window stays visible.

## Waits and navigation

- A full `goto()` from one app.revenuecat.com page to another often takes 60–120 s to return. Navigating inside the SPA is instant: click the sidebar link from JS, e.g. `document.querySelector('a[href="/projects/{id}/paywalls"]').click()`, then wait a few seconds. Read page text with `document.querySelector('main').innerText`.
- Sub-items appear in the sidebar only after "Product catalog" is expanded, but the `a[href]` elements exist either way.

## Creating an offering (`/product-catalog/offerings/new`)

- "New offering" is a menu: "Create from scratch" or "Create with Rico" (AI).
- Package type is a `div[role=combobox]`. Its options (`[role=option]`) are Monthly, Annual, Six Months, Three Months, Two Months, Weekly, Lifetime and Custom, which map to `$rc_monthly`, `$rc_annual`, ... and `$rc_lifetime`. The resolved `$rc_*` value shows up as a hidden input's value.
- Product is an `input[placeholder="Select product"]` combobox. Option text starts with the product ID.
- **"+ New Package" inserts the new block at the top, not the bottom.** Address blocks by index after each insert, and check all inputs before saving.
- The first offering in a project becomes the Default (current) offering automatically. A check icon next to its identifier has the tooltip "Default Offering". The row's `...` menu offers Duplicate / Make Default / Make Inactive / Delete.

## Paywall editor (`/paywalls/{id}/builder`)

- Clicking a template card in "Select template" **immediately creates a draft paywall** ("Untitled Paywall"). Nothing goes live until Publish, but backing out leaves a draft to delete.
- The top bar has an issues badge ("N issue"). Its popover links each issue to the component. A new paywall's first issue is "Select an offering for the connected paywall": the screen's properties panel has an "Offering" dropdown.
- The left rail has Add step, Layers, AI Editor, Branding, Media gallery, Localization, Paywall logic and Settings. Only some buttons have an `aria-label`. The Layers tree rows are plain text leaves such as "Package", "Button" and "Package stack". Click one to get its properties panel on the right. For a package, that's the Package dropdown ("Lifetime ($rc_lifetime)") and a "Selected by default" checkbox; for a button, Action ("Navigate to" + Terms of Service / Privacy Policy + URL + open method, or "Restore purchases").
- The AI Editor (textarea "What do you want to edit?") handles multi-step edits reliably, e.g. deleting template content, retitling, re-mapping packages and setting footer URLs. A "Stop" button shows while it works (roughly 1–2 minutes). It may also touch Paywall logic rules and says so ("Rules updated: ..."). Verify the result in Layers and properties afterwards.
- Templates can include an "Offer type → Introductory" rule. It changes CTA text when the selected package has an intro offer. The top-bar "Preview a rule" selector only changes the preview.
- Publish shows a "Published successfully!" toast. The button then becomes "Publish changes" (disabled until there are edits). The offering page then shows "Paywall: Components-based Paywall".

## Test Store

"Create Test Store" on the Apps page creates a separate Test Store app with its own `test_` key. It isn't a toggle: its products must be created separately and attached to entitlements.
