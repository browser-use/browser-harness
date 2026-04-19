# Microsoft 365 — Admin-center workflows for Cathedral

Primary surfaces:
- `https://admin.microsoft.com/`
- Exchange / Defender / Entra admin centers as linked from the main portal

Use browser-harness here for:
- domain and mailbox inventory
- admin-center truth checks
- Exchange / mail-flow surface verification
- DKIM / domain / connector readiness review

## Default stance

Use the browser to verify:
- what domains are present
- domain health / setup state
- mailbox existence
- user/license assignment presence
- whether DKIM or mail security surfaces are available

Prefer PowerShell/API/CLI for bulk user or mailbox mutation.

## Reliable workflow

1. land on `admin.microsoft.com`
2. confirm tenant/account first
3. use global search when possible
4. open Domains / Users / Teams / Exchange / Billing only after tenant confirmation
5. screenshot every final evidence page

## High-value pages

- Settings / Domains
- Active users
- Shared mailboxes (often via Exchange admin)
- Exchange admin → mail flow / accepted domains / DKIM-related surfaces
- Billing / licenses when dependency questions exist

## What to collect

- tenant name
- domain list
- target domain status
- whether mailboxes are visibly hosted there
- whether shared mailboxes/aliases exist
- whether DKIM/configuration surfaces exist for the domain
- whether licenses appear to be direct Microsoft 365 vs third-party managed

## Common traps

- **Wrong admin center** — many mail settings are not in the main M365 center; they live in Exchange admin.
- **Tenant confusion** — Microsoft loves cross-tenant context drift. Confirm tenant banner/account before drawing conclusions.
- **License presence != operational ownership** — record both license view and domain/mailbox view.
- **DKIM surface can be buried** — do not conclude “not supported” until search + Exchange path are checked.

## Best Cathedral uses

- verify whether Microsoft 365 is the real mail platform
- inventory mailbox/domain state before DNS changes
- check if DKIM/domain hardening can be completed
- determine whether GoDaddy is still involved or only billing-proxy residue remains

## Approval boundary

Approval required before:
- changing users/licenses
- changing mail flow/connectors
- enabling security policies with blast radius
- altering domains / federation / identity state