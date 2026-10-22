# Railway credential forms

Use the user's authenticated browser. Do not print, screenshot, or persist secret
values, clipboard contents, cookies, or variable-diff bodies.

## Routes and ownership

- A service's variable page is
  `https://railway.com/project/<project>/service/<service>/variables?environmentId=<environment>`.
- Database configuration is under the database service's Database tab, then
  Config. Prefer the live tab labels over inferred route parameters.
- Bind the owned target explicitly with `switch_tab(target_id)` at the start of
  every harness invocation and check `location.origin` and the expected path
  before acting. A fresh invocation can attach to the user's active tab.
- `switch_tab` attaches without foregrounding by default. Use
  `cdp('Page.bringToFront')` when a screenshot or user handoff needs visibility.
  Background captures can time out or show a stale compositor frame.

## Variable editor

- The search toggle has `title="Filter variables"`; the filter field is
  `input[name="filter-service-variables"]`.
- Filter by the complete variable name and verify the field's value before
  opening a row menu. The row menu is a button with `aria-haspopup="menu"`;
  choose its `Edit` menu item.
- The editor is `textarea[name="value"]`. Its contents are plaintext. Use
  credential-safe DOM predicates when screenshots would reveal a secret.
- Editor controls have `title="Submit"` and `title="Cancel"`.
- Stars in the list also mask an empty value. A visible variable name and stars
  do not establish that a credential is populated.
- Await the actual filter/editor state after interactions. Document load alone
  does not establish SPA readiness, and a short fixed wait can miss a successful
  interaction that completes later.
- For Ctrl+A through raw CDP, send keyDown/keyUp with key `a`, code `KeyA`,
  modifiers `2`, and virtual key code `65`, without a `text` property. A shortcut
  carrying printable text can insert a character instead of selecting all.

## Applying and verifying

- Submitting a variable creates a staged change. Review variable names and the
  change count, then apply the changes with the deployment controls.
- The staged-change Details view can reveal old and new secret values. Avoid
  full-body extraction or screenshots there.
- Reload and reopen the target variable for a private equality check; cancel
  the read-only inspection afterward. An open editor is not proof of a save.
- An applied configuration is not proof that a running container has restarted.
  Check active deployment identity and startup/health evidence separately.
- Where private entry needs a user handoff, prepare the source and destination,
  let the user enter/submit the credential, then verify without exposing it.

## PostgreSQL rotation

Railway's supported flow is Database > Config > Connection > Regenerate. It
changes the database role password and linked variables, and restarts PostgreSQL.
Dependent services still need redeployment to read the new credential. Do not
change `POSTGRES_PASSWORD`/`PGPASSWORD` independently or assume an environment
edit changes an initialized database's role password. If the Database view is
stuck connecting, report that the rotation remains incomplete.

Sources: [Variables](https://docs.railway.com/variables),
[PostgreSQL rotation](https://blog.railway.com/p/security-disclosure-recommendation-rotate-postgresql-database-credentials).
