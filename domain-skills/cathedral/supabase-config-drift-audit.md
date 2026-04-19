# Cathedral runbook — Supabase config drift audit

Use this when repo assumptions, environment variables, and Supabase dashboard state may have drifted apart.

## Goal

Answer:
- are we in the right project?
- does the dashboard match repo/env assumptions?
- are Auth / Edge Functions / settings configured as expected?
- where is the drift?

## Workflow

1. **Supabase dashboard**
   - confirm org/project
   - inspect relevant surfaces (Auth, Edge Functions, Settings, Storage)
2. **Repo/config comparison**
   - compare project IDs, URLs, expected providers, function names
3. **Endpoint verification**
   - test live endpoint/health from terminal

## Good audit targets

- OEE vs AGM project confusion
- missing auth providers
- functions deployed in one project but not another
- secrets/env mismatch between platform and repo assumptions

## Output

- project inspected
- expected state
- observed state
- drift found
- probable blast radius
- next fix