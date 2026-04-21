# Cathedral runbook — Browser evidence packet schema

Use this whenever browser-harness work needs to produce a reusable artifact instead of a loose summary.

## Why

Browser work is most valuable when it returns:
- repeatable evidence
- screenshot references
- exact UI truth
- approval boundaries

Without a packet, browser sessions become anecdotes.

## Required fields

- `packet_id`
- `created_at`
- `operator`
- `node`
- `lane` (`BU_NAME`)
- `workflow`
- `objective`
- `console`
- `page_title`
- `page_url`
- `object_under_inspection`
- `observed_state`
- `expected_state`
- `drift_or_issue`
- `risk_level`
- `recommended_next_action`
- `approval_required`
- `screenshot_paths`
- `supporting_artifacts`

## Canonical output pair

Create both:
- markdown packet for humans
- JSON packet for machines

## Suggested locations

- `~/Cathedral/state/browser-observatory/packets/...`
- keep screenshots referenced, not embedded in raw markdown

## Minimal judgment rubric

### Risk levels
- `low` — observation only, no urgent user action
- `medium` — mismatch or warning with bounded blast radius
- `high` — likely breakage, billing risk, security risk, or production drift
- `critical` — active outage, imminent expiry, destructive misconfiguration, or exposed security issue

### Approval field
- `false` for observation/inventory/verification only
- `true` for destructive, external, billing, registrar, identity, or production-changing action

## Best practice

Every browser task should end with one evidence packet, even if the result is “no drift found.”