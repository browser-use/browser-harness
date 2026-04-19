# GoDaddy — Registrar and product inventory workflows

`https://account.godaddy.com/`

Use GoDaddy in browser-harness for:
- domain-registration truth checks
- product inventory
- auto-renew / lock / privacy review
- transfer-readiness review
- finding legacy email/SSL leftovers

## Default stance

GoDaddy is most valuable in Cathedral as an **inventory surface**.

Use the browser to answer:
- what products still exist?
- what renews?
- is the domain locked?
- is auto-renew enabled?
- are there stale mail / SSL / upsell dependencies still attached?

## What to capture on every visit

- account identity / tenant if visible
- domain list or searched domain
- expiration date
- transfer-lock state
- auto-renew state
- privacy / protection state
- any attached products:
  - SSL
  - email
  - Microsoft 365 via GoDaddy
  - forwarding / Workspace / Professional Email

## Recommended workflow

1. go to product/domain list first
2. search the exact domain
3. screenshot the product card / domain row
4. open the domain detail page
5. capture lock / renew / contact / protection / DNS hints
6. separately inspect product/billing list for attached leftovers

## High-value Cathedral use cases

- registrar-transfer readiness checks
- GoDaddy dependency audits
- confirming whether a domain is still operationally tied to GoDaddy
- finding legacy SSL and email products safe to retire later

## Common traps

- **Domain row vs billing row mismatch** — the domain can be active while stale add-ons still bill elsewhere.
- **Confusing DNS host with registrar** — GoDaddy can remain registrar even when DNS is elsewhere.
- **Transfer path buried in detail views** — inventory first, then locate transfer controls only after confirming ownership.
- **Support/upsell surfaces** — avoid interpreting upsell prompts as active dependencies.

## Approval boundary

Approval required before:
- unlocking for transfer
- requesting auth/EPP code
- disabling protection/privacy
- cancelling products
- changing contact/ownership/billing details

## Best Cathedral output

Return a clean split:
- registrar dependency
- renew-risk items
- attached products
- safe-to-ignore upsells
- approval-required next actions