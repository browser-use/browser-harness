# Cathedral — Multi-console operator pack

Use this when a task spans multiple vendor consoles such as:
- Cloudflare
- Vercel
- GoDaddy
- Microsoft 365
- Supabase
- GitHub

This is the Cathedral pattern for browser-harness.

## Core doctrine

Use browser-harness for:
- evidence
- inventory
- UI truth
- preflight verification
- post-change verification

Do **not** default to using the browser for every mutation. Let terminal/API/MCP do the durable scripted work where possible.

## Best operating pattern

### 1. One session name per workstream

Use separate `BU_NAME` values such as:
- `cloudflare`
- `vercel`
- `godaddy`
- `m365`
- `supabase`
- `github`
- `agm-audit`
- `deploy`

This prevents agents from fighting over the same default browser socket.

### 2. One console, one evidence packet

For each console visited, return:
- page title / route
- screenshot summary
- exact state observed
- risk
- next action
- whether approval is required

### 3. Browser first for truth, API second for scale

Pattern:
1. use browser to confirm what the console really says
2. use terminal/API/MCP to do scalable extraction or mutation
3. use browser again to verify the result landed in the UI

This is the 1000000x loop.

## Highest-value Cathedral workflows

- domain stack audits (GoDaddy + Cloudflare + Vercel + M365)
- deploy verification (GitHub + Vercel + Cloudflare)
- auth/config truth checks (Supabase + Vercel + GitHub)
- post-change screenshot proof
- vendor billing/dependency inventory

## Output discipline

Never return a vague "looks right" summary.

Return:
- console
- object under inspection
- state observed
- proof artifact (screenshot summary / visible labels)
- recommended action
- approval boundary