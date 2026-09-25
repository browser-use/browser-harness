# PostHog dashboard (us.posthog.com / eu.posthog.com)

React SPA. US and EU Cloud are separate hosts with separate accounts; use the host the account lives on. Logged out, any URL redirects to `/login` (has a data-region selector).

## URL shape

- `/project/{projectId}/home`: project home. The numeric project ID is also the environment ("team") ID.
- `/project/{projectId}/settings/project`: redirects to `/settings/project-details` (project token, project ID, region).
- `/project/{projectId}/settings/project-privacy`: "Discard client IP data" toggle.
- `/project/{projectId}/settings/project-error-tracking`: "Enable exception autocapture" toggle.
- `/project/{projectId}/feature_flags`: flag list (key, type, release conditions, status).
- `/organization/billing/overview`: plan, month-to-date bill, and a "Billing limit" row per product.

Settings toggles save immediately and show a toast ("... updated successfully"). There's no Save button.

## Private API (same-origin fetch from any logged-in page)

Session cookies authenticate reads. Writes also need header `X-CSRFToken` set to the value of the `posthog_csrftoken` cookie.

- `GET /api/users/@me/`: `organization.projects[]`, `organization.teams[]`, `organizations[]`.
- `GET /api/environments/@current/`: current project settings. It includes `api_token` (the `phc_` project token), `anonymize_ips` and `autocapture_exceptions_opt_in`. Handy for verifying toggles.
- `GET /api/billing/`: `subscription_level`, `products[]` and `custom_limits_usd` (a map from product type to its limit; a missing key means no limit).
- `GET|POST /api/projects/{projectId}/feature_flags/`. Create body:
  `{key, name, active: true, filters: {groups: [{properties: [], rollout_percentage: N}], multivariate: null | {variants: [{key, name, rollout_percentage}]}, payloads: {}}}`.
  `name` is shown as the description under the key. Creating flags by API is far more reliable than the flag editor for exact rollouts.

Verify what an SDK will actually receive with `POST https://us.i.posthog.com/flags?v=2` and body `{"api_key": "<phc_ token>", "distinct_id": "<anything>"}`. It returns `flags.{key}.enabled` and `.variant`. On a brand-new project, the first call can return `{}` for about a minute until the flag cache catches up.

## UI notes

- Project switcher: click the project name at the top left. The menu has a `+` next to "PROJECT" that opens "Create a project within <org>" (a single name field, then "Create project"). The app then switches to the new project.
- The settings page has its own left nav (Project → General, Privacy, Error tracking, ...), which is easier than scrolling.

## Traps

- The SPA rewrites `document.title` on every route change, which drops the harness's green marker, so `agent_tab()` returns None after a click-through. Keep the `targetId` from the first `navigate()` and use `switch_tab(targetId)`.
