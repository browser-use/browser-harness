# Cathedral runbook — Domain stack audit

Use this when auditing a domain spread across:
- GoDaddy or another registrar
- Cloudflare DNS
- Vercel hosting
- Microsoft 365 mail

## Goal

Produce a single evidence-backed ownership map:
- registrar
- authoritative DNS
- website hosting
- website SSL
- inbound mail
- outbound mail authorization
- leftovers that still depend on legacy vendors

## Browser lane plan

Use separate `BU_NAME`s if running in parallel:
- `godaddy`
- `cloudflare`
- `vercel`
- `m365`

## Order of operations

1. **GoDaddy / registrar first**
   - confirm expiry, lock state, auto-renew, attached products
2. **Cloudflare second**
   - confirm zone, DNS records, proxy state, SSL mode, nameservers
3. **Vercel third**
   - confirm project, production domain assignment, latest healthy deploy
4. **Microsoft 365 fourth**
   - confirm domain present, mailbox ownership, DKIM/readiness surfaces
5. **Terminal/API cross-check last**
   - `whois`, `dig`, `curl`, cert inspection

## Output contract

For each console, return:
- account/tenant
- object inspected
- key state
- screenshot summary
- risk
- approval boundary

Then synthesize:
- what still depends on vendor A
- what is safe now
- what must be verified first
- what must not be touched blindly

## Best use

This is the default browser-harness runbook for registrar / DNS / deploy / mail uncertainty.