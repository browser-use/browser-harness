# GitHub — Settings/admin workflows for Cathedral

`https://github.com`

This complements `github/scraping.md`.

Use browser-harness here for:
- org/repo settings verification
- branch protection / ruleset visibility
- Actions / secrets / environments review
- GitHub UI-only admin surfaces

Prefer API/gh CLI for normal repo metadata. Use the browser when the truth is in Settings.

## Reliable workflow

1. confirm logged-in account/org first
2. open the exact repo or org
3. navigate to Settings / Actions / Secrets / Rulesets / Environments as needed
4. screenshot the evidence page before summarizing

## High-value Cathedral uses

- confirm repo visibility and org placement
- inspect Actions state and failures
- verify environment names and protection rules exist
- check branch protections/rulesets visually
- review Pages/app settings where CLI coverage is poor

## Common traps

- **Wrong org or personal account context**
- **Settings permissions missing** — lack of UI access is itself evidence; report it clearly.
- **Secret presence only** — verify existence/scope, not values.
- **Actions tab vs workflow run page confusion** — state exactly which screen you are using.

## Approval boundary

Approval required before:
- changing repo visibility
- deleting environments/secrets
- modifying rulesets/branch protections
- changing app/webhook/security settings