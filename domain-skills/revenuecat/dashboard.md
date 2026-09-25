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

## Waits and navigation

- A full `goto()` from one app.revenuecat.com page to another often takes 60–120 s to return. Navigating inside the SPA is instant: click the sidebar link from JS, e.g. `document.querySelector('a[href="/projects/{id}/paywalls"]').click()`, then wait a few seconds. Read page text with `document.querySelector('main').innerText`.
- Sub-items appear in the sidebar only after "Product catalog" is expanded, but the `a[href]` elements exist either way.

## Test Store

"Create Test Store" on the Apps page creates a separate Test Store app with its own `test_` key. It isn't a toggle: its products must be created separately and attached to entitlements.
