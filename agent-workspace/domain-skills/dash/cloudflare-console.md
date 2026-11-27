# Cloudflare — scoped credentials and Turnstile checks

Applies to `dash.cloudflare.com`.

## Navigation and readiness

- User tokens live at `/profile/api-tokens`; account API tokens are a different surface.
- Zone routes use `/<account-id>/<zone-name>/...`; Turnstile uses
  `/<account-id>/turnstile` and `/turnstile/widget/<site-key>` beneath the account.
- A route can change while the old page body remains visible. Wait for a page-specific
  landmark or field, not just `document.readyState` or the new pathname.
- Scroll action buttons into view and measure their current bounds before clicking.

## Token creation

- The custom-token flow exposes a JSON Payload tab on its summary. Validate the exact
  resource restriction and permission groups there before creating the token.
- Zone permission choices use checkbox roles and semantic labels; generated IDs vary.
- Preflight the intended secret store before creating a token. Capture its value only
  in memory, save and read-verify it, then leave the result page before screenshots.

## Zone settings and widgets

- Full and Full (strict) are distinct encryption choices. Reload the SSL overview after
  saving and verify the displayed mode; do not assume automatic mode implies strict.
- Turnstile's hostname search supports custom names through an asynchronously displayed
  `Add … as a custom hostname` option. Wait and click that option. Enter can submit the
  whole form without adding the hostname. Confirm the configured-hostname count.
- Edit Widget exposes `input[name=site_key]` and `input[name=secret]`; the latter is a
  password field. Comparing hashes in memory can verify a deployed pair without
  revealing or rotating it. Never screenshot a revealed secret.

## Interpreting the siteverify warning

- Inspect the widget's Token validation analytics: requests, valid tokens and invalid
  tokens. A warning can coexist with requests when no valid token has been recorded.
- Invalid diagnostic tokens prove connectivity, not successful form verification.
  A controlled human submission and a recorded valid token establish the full path;
  analytics and the warning can update after the submission.
- `600*` client errors indicate generic challenge failure/bot detection. Hand the
  challenge to a human; do not weaken protection, rotate matching keys, or automate a
  challenge solution to make a test pass.
- Official error reference:
  https://developers.cloudflare.com/turnstile/troubleshooting/client-side-errors/error-codes/
