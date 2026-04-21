# Supabase — Dashboard truth and configuration verification

`https://supabase.com/dashboard`

Use browser-harness for:
- project inventory
- environment/config truth checks
- Auth / Database / Edge Functions / Storage / Logs surface verification
- dashboard state that is awkward to confirm purely by API

## Default stance

Supabase browser work is mainly for **config truth**, not data-plane work.

Use API/SQL/terminal for:
- querying data
- migrations
- schema diffs
- automated deployments

Use the dashboard for:
- project selection confirmation
- environment/settings review
- Auth provider status
- Edge Function deployment visibility
- secrets/config presence checks
- storage bucket / policy sanity checks

## Reliable workflow

1. confirm org/team
2. open exact project
3. screenshot overview
4. navigate to the specific surface:
   - Database
   - Auth
   - Edge Functions
   - Storage
   - Logs
   - Project Settings

## High-value Cathedral use cases

- verify OEE vs AGM project selection before making claims
- confirm Auth/provider settings visually
- inspect whether edge functions are present and healthy
- compare dashboard configuration with repo assumptions
- grab visual proof for broken settings or environment drift

## Common traps

- **Wrong project** — always state project ID/name explicitly.
- **Wrong environment/context** — if multiple browser tabs exist, activate and rescreenshot before extracting facts.
- **UI confirms presence, not runtime correctness** — combine dashboard truth with live endpoint/API checks.
- **Secret values** — never exfiltrate secrets from the UI unless Mahuki explicitly asks.

## Approval boundary

Approval required before:
- changing auth providers
- rotating secrets
- deleting tables/buckets/functions
- running destructive SQL from the browser