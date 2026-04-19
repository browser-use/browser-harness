# Cathedral runbook — Vendor billing inventory

Use this when the question is:
- what are we still paying for?
- what still matters operationally?
- what can be safely cancelled later?

Best targets:
- GoDaddy
- Microsoft 365
- Cloudflare
- Vercel
- GitHub
- any vendor with account-level product clutter

## Goal

Split every visible product into one of four buckets:
- operationally critical now
- useful but non-critical
- probably stale / removable after verification
- obvious upsell / ignore

## Method

1. visit vendor billing/products page
2. screenshot product list
3. capture renewal names / plan names / attached domains or projects
4. cross-link each product to actual live dependencies seen elsewhere

## Key rule

Do not equate “billing exists” with “dependency exists.”
Do not equate “upsell visible” with “product active.”

## Output contract

For each product:
- vendor
- product name
- renewal risk
- live dependency evidence
- safe now / verify first / do not touch blindly

## Best use

This is the browser-harness runbook for cleanup and cost sovereignty without breaking production.