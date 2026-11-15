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
