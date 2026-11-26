# Entra sign-in: HTTP 400 request headers too long

## Recognize the boundary

- A popup on `login.microsoftonline.com` can fail on a tenant's `/reprocess`
  path with `Bad Request - Request Too Long` and `HTTP Error 400. The size of
  the request headers is too long.`
- This page is served by the identity provider, before returning to the app.
  Inspect the popup's hostname and error text before changing application code.
- Never print the full URL: query parameters can carry authentication state.

## Inspect without exposing credentials

Use `Network.getCookies` scoped to the failing popup URL. Report only cookie
count, aggregate name/value lengths, and names/domains/paths where needed.
Never print cookie values, auth query values, or authorization headers.

Accumulated session cookies named `esctx-<suffix>` can contribute to an oversized
Cookie header. These are distinct from established SSO cookies such as
`ESTSAUTH` and `ESTSAUTHPERSISTENT`, and device/broker credential cookies.
The observed recovery removed abandoned `esctx-` context cookies while
preserving those established cookies, reducing the header enough for a fresh
account picker to load. This is a targeted recovery observation, not a guarantee
that every header-size error has the same cause.

## Recover a failed attempt

Only clean up abandoned contexts within the authorized browser profile and
exact sign-in domain/path. Coordinate with the user if another sign-in flow is
active. Delete selected cookies by exact name/domain/path, then close the failed
popup so the opener's MSAL interaction can settle. Start a fresh sign-in from
the application; reloading an old `/reprocess` URL can reuse stale state.

Confirm the new popup shows the account picker instead of HTTP 400. Account
selection, credentials, and MFA remain with the user. The picker loading alone
does not prove the application is signed in: verify the opener after completion.

Do not clear all browser storage or all Microsoft sign-in cookies by default.

Reference: https://learn.microsoft.com/en-us/answers/questions/858716/http-error-400-the-size-of-the-request-headers-is
