# Cathedral runbook — Public site smoke

Use this after deploys or content/config changes to verify public-facing surfaces.

Best targets:
- home page
- pricing page
- nav/footer
- primary CTA paths
- contact / lead forms
- login entrypoints

## Goal

Confirm that the public site:
- loads
- renders the intended IA/content
- exposes the intended primary actions
- does not visibly regress

## Pattern

1. open site in a real tab
2. capture screenshot at load
3. verify title, hero, nav, CTA, footer
4. follow one or two primary actions
5. capture evidence packet

## Great pairings

- browser-harness for visual truth
- terminal `curl` for headers/status
- deploy-proof runbook when tied to a release

## Output

- page checked
- visible regressions
- CTA/form state
- pass/fail with screenshot references