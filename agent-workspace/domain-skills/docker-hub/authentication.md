# Docker Hub — password and MFA sign-in

- Sign-in can pass through `login.docker.com/u/login/identifier`, then
  `/u/login/password`, before reaching `app.docker.com/auth/mfa`.
- Username/password acceptance is distinct from completion of Docker's MFA step.
  Wait for the destination's form to render; URL changes alone can precede its DOM.
- The MFA form uses `input[name=code]` and Verify. Try another way to sign in can
  return to the identifier page rather than offer another MFA method.
- I've lost my authentication device leads to `/auth/mfa/recovery`. This is an
  account-recovery action: Docker says consuming the recovery code signs in,
  disables two-factor authentication, and deletes the code. Obtain authorization
  for that security change and plan re-enrollment; do not treat it as an ordinary
  substitute for a missing authenticator code.

Source: [Docker account recovery](https://docs.docker.com/security/authentication/2fa/recover-hub-account/).

## Tokens and private repositories

- Account settings live at `app.docker.com/accounts/<username>`; Hub repositories
  live at `hub.docker.com/repositories/<username>`. Verify the authenticated account
  after navigation. A generic `/auth/error` screen can coexist with a valid session;
  Sign In may return directly to the authenticated account.
- Hidden/mobile navigation duplicates can precede visible links in the DOM. Require
  nonzero element bounds before clicking a text match.
- Personal access token creation uses `input[name=description]`, and comboboxes
  backed by `input[name=expirationType]` and `input[name=repoScope]`. The read/write
  option has value `repo:write`; `90days` is an expiration option. Cloud Sandboxes
  permission is a separate checkbox.
- Preflight secret storage before Generate. On the once-only `/copy` result, read
  the exact token `pre` element. A regex over `body.textContent` can append adjacent
  Copy button text to the credential, producing a saved but invalid value. Never
  screenshot or log the result; read-verify storage and test authentication.
- Registry JWT subjects need not equal a Docker username. Verify the requested
  repository's granted actions rather than assuming a username-shaped subject.
- Hub creation at `/repository/create` uses `input[name=name]`,
  `textarea[name=description]`, and `input[name=privacy]` (`private`/`public`). A
  private repository's detail page can show only a lock icon. Verify `is_private`
  through the API or repository settings, not by requiring visible Private text.
