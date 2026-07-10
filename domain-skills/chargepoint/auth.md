# ChargePoint — session auth (driver.chargepoint.com)

## Datadome blocks programmatic password login

ChargePoint fronts its login API with Datadome bot protection. Server-side
password logins (e.g. from the Home Assistant `chargepoint` custom integration,
or any script POSTing credentials) get blocked with a bot challenge even when
the credentials are correct. Don't retry the password path — use a session
token from a real browser instead.

## The session token is the `coulomb_sess` cookie

- Domain: `.chargepoint.com` (shared across driver.chargepoint.com and na.chargepoint.com)
- Name: `coulomb_sess` (~43-char opaque value)
- Present whenever the user is logged in at https://driver.chargepoint.com
- Related cookies you'll see alongside it: `auth-session`, `ci_ui_session`,
  `datadome` — `coulomb_sess` is the one API clients (python-chargepoint,
  ha-chargepoint) accept as a session token.

Grab it from the user's logged-in browser without navigating anywhere:

```python
cookies = cdp("Storage.getCookies")["cookies"]
tok = next(c["value"] for c in cookies
           if c["name"] == "coulomb_sess" and "chargepoint" in c["domain"])
```

If no `coulomb_sess` cookie exists, the user isn't logged in — stop and ask
them to log in at driver.chargepoint.com first (don't type credentials).

## Trap

The HA chargepoint integration's reauth dialog offers both a password field
and a token field. The password path fails through HA's server (Datadome
again); paste the `coulomb_sess` value into the token field instead —
succeeds immediately.
