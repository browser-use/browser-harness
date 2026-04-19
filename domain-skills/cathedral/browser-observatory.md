# Cathedral runbook — Browser observatory checks

Use this to convert browser-harness from a one-off tool into an observatory layer.

## Principle

Browser checks should be:
- low-noise
- high-signal
- anomaly-oriented
- evidence-backed

Do **not** run chatty browser sweeps that spam Mahuki.

## Best recurring checks

### Daily / on-change checks
- Vercel latest successful vs latest attempted deployment
- Cloudflare zone warnings / custom domain health
- Supabase project/project-selection drift
- GitHub Actions/red workflow review for key repos
- Microsoft 365 domain setup / DKIM readiness for active domains

### Weekly checks
- GoDaddy renewal / transfer-lock / attached product inventory
- vendor billing/product inventory snapshots
- cross-console domain stack consistency review

## Trigger model

Preferred triggers:
- after deploy
- after DNS change
- before registrar/billing action
- when an anomaly is detected elsewhere

Acceptable scheduled triggers:
- one compact sweep per domain or product family
- only emit if changed, risky, or decision-worthy

## Output discipline

Each check produces:
- one evidence packet
- risk rating
- change/no-change result
- recommended next action

If nothing changed, store locally and do not spam the user.

## Best Cathedral observatory packs

- `deploy-proof`
- `domain-stack-audit`
- `m365-mail-hardening-audit`
- `supabase-config-drift-audit`
- `vendor-billing-inventory`