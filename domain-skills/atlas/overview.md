---
name: atlas-recruit
description: Atlas recruitment platform (my.recruitwithatlas.com) — routes, filters, GraphQL bootstrap for authenticated UI probes.
---

# Atlas — my.recruitwithatlas.com

Gated recruitment SaaS. Auth via Google SSO (WebAuthn/passkey). GraphQL backend at `/graphql` (NextAuth session cookie, `credentials: 'include'` from the tab).

## Routes

| Route | What |
|---|---|
| `/home` | Dashboard (default landing after login) |
| `/sign-in` | Redirect target when unauthenticated |
| `/business-development/opportunities` | BD opportunities (kanban / list view) |
| `/business-development/leads` | Leads |
| `/business-development/prospects` | Prospects |
| `/business-development/playbook` | Playbook |
| `/candidates` | Candidate pipeline |
| `/projects/<id>` | Specific job / project |
| `/graphql` | Authenticated GraphQL endpoint (POST) |

## Filters in URL

BD opportunities uses `?filters=[JSON]` (URL-encoded). Example "Me" filter:

```json
[{"id":"opportunity_owner","selectedOptions":[{"id":"<USER_UUID>","title":"Me","excludeFromSearch":false}]}]
```

Filter IDs seen: `opportunity_owner`, `stage`, `industry`, `segment`, `conversion_probability`.

## Finding your own user UUID

- Apply a filter like "owner = Me" in `/business-development/opportunities`, then read `selectedOptions[0].id` out of the URL `filters=` param.
- Or: `query { me { id email } }` via the GraphQL endpoint (see below).
- User UUIDs are tenant-stable; keep them in a local secret store, not in this shared skill.

## Stages (BD funnel)

`Identified` → `Initial Outreach` → `Late Stage` → `Converted` → `Archived`. Seen as tab labels on `/business-development/opportunities`.

## Auth quirks

- Google SSO flows through `accounts.google.com/signin/oauth/id?...` — passkey / WebAuthn only, no password fallback visible.
- Session state lives in multiple cookies (JWE session + CSRF). Injecting only the JWE into a fresh Chrome profile is **not sufficient** for UI access — you land in a login loop. For UI work: log in once inside a persistent Chrome profile and let all cookies settle. For backend-only GraphQL calls: the `__Secure-authjs.session-token` JWE alone is enough when sent with `cookie: __Secure-authjs.session-token=<jwe>` from an external HTTP client.

## GraphQL endpoint

POST `https://my.recruitwithatlas.com/graphql` using the tab's own cookies:

```python
js("""
fetch('/graphql', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'apollo-require-preflight': 'true'},
  credentials: 'include',
  body: JSON.stringify({query: 'query { me { id email } }'})
}).then(r => r.json()).then(j => JSON.stringify(j))
""")
```

This reuses the session cookies of the current tab — no JWE juggling needed when browsing from inside browser-harness.

Known mutations (verified against production schema, April 2026): `opportunityCreate`, `opportunityUpdate`, `companyCreate`, `projectCreate`, `projectUpdate`, `opportunityAddLead`, `createOpportunityNote`. Create mutations return placeholder names; follow with an `opportunityUpdate` / `projectUpdate` to set the final name or description. `opportunityAddLead` side-effects `Project.company` onto `Opportunity.targetCompany` when the opp had none.

## Page titles

The app sets a green-dot emoji prefix on titles: `🟢 Atlas Agency` (sign-in), `🟢 Business development` (BD overview), etc. Useful for `wait_for` conditions — the emoji is consistent across routes.
