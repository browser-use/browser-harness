# Cathedral runbook — Microsoft 365 mail hardening audit

Use this when a domain appears to receive mail through Microsoft 365 but DNS/security posture is unclear.

## Goal

Determine:
- whether Microsoft 365 is the real inbound mail platform
- whether the domain is fully wired there
- what hardening is missing
- whether legacy GoDaddy or other sender traces still remain

## Console order

1. `m365`
2. `cloudflare`
3. optionally `godaddy` if legacy residue is suspected

## What to verify

### In Microsoft 365
- target domain present
- mailbox/domain ownership visible
- DKIM/config surfaces available
- shared mailbox / alias presence if relevant

### In Cloudflare
- MX
- SPF
- `_dmarc`
- DKIM selectors
- `autodiscover`
- any stale GoDaddy-ish records

### In GoDaddy if needed
- active email or Microsoft 365 products sold through GoDaddy
- forwarding / SMTP / legacy mail products

## Common outputs

- inbound mail owner
- outbound authorization owner
- missing hardening records
- legacy residue
- approval-required next steps

## Best use

Default runbook for “is this domain really on Microsoft 365 and what hardening is still missing?”