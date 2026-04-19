# Vercel — Operator workflows for Cathedral

`https://vercel.com/dashboard`

Use Vercel in browser-harness for:
- project inventory
- deployment verification
- domain assignment review
- environment variable confirmation
- build/runtime config truth checks

## Default stance

Prefer browser automation for:
- confirming the live project/dashboard state
- checking failed deploy details in the UI
- verifying environment variables exist
- checking domain bindings, aliases, redirects, and preview/prod state

Prefer CLI/API for:
- deploy execution
- logs export
- scripted environment changes

## High-value surfaces

- dashboard / team picker
- project overview
- Deployments
- Settings → Domains
- Settings → Environment Variables
- Functions / Runtime / Observability surfaces when present

## Reliable workflow pattern

1. confirm team scope first
2. search project by visible name
3. open project overview
4. capture screenshot
5. drill into Deployments or Settings as needed

## What to capture

For every Vercel check, record:
- team/account name
- project name
- production domain(s)
- latest deployment status
- latest deployment commit/branch if visible
- whether environment variables are present (do not expose secret values)
- whether domains are assigned and verified

## Environment-variable rule

Use the browser to verify that a variable exists in the expected scope:
- Production
- Preview
- Development

Do **not** reveal secret contents back into chat. Presence/absence and scope are enough unless Mahuki explicitly asks for value handling.

## Common traps

- **Wrong team scope** — many Vercel mistakes come from being inside the wrong team/org.
- **Preview vs Production confusion** — always name which environment you are looking at.
- **Latest successful vs latest attempted deploy** — the top deployment is not always the last healthy one.
- **Domain present but not healthy** — inspect status badges / warnings, not just presence in the list.

## Best Cathedral uses

- verify that Cathedral / OEE / AGM sites point at the intended project
- confirm env wiring after secret changes
- inspect failed deploy reasons before using terminal-heavy recovery
- check custom-domain health after DNS changes

## Approval boundary

Approval required before:
- changing environment variables
- deleting domains / projects
- promoting / rolling back manually
- changing production routing or team billing settings