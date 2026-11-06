---
name: invicti-api
description: Query and reason about Invicti Enterprise (Netsparker Cloud) via its Web API (netsparkercloud.com). Use whenever the user mentions Invicti/Netsparker, scan schedules, scheduled scans, scan profiles, websites, website groups, vulnerabilities/issues, technologies, agents, teams/roles/members, or asks questions like “Schedules”, “does website X have a schedule?”, or “does website X have vulnerabilities?”.
---

# Invicti Enterprise API (Netsparker Cloud)
Use the documented Invicti Enterprise API:
- Docs UI: https://www.netsparkercloud.com/docs/index
- Swagger JSON: https://www.netsparkercloud.com/swagger/docs/v1
- Base path for API calls: `https://www.netsparkercloud.com/api/1.0`

## Authentication (required)
The API uses HTTP Basic Auth:
- username: `INVICTI_USER_ID`
- password: `INVICTI_TOKEN`

Prefer setting these as environment variables (or in a local `.env`, which this repo already ignores):
- `INVICTI_BASE_URL` (optional; default `https://www.netsparkercloud.com`)
- `INVICTI_USER_ID`
- `INVICTI_TOKEN`

Do not print or commit credentials.

## Read-only first (avoid surprises)
Default to GET/read-only endpoints.
If the user asks for a write action (schedule/unschedule scans, update issues, create websites, etc.), ask for explicit confirmation before sending POST/PUT/DELETE.

## Built-in helper functions (recommended)
If you are operating inside this `browser-harness` repo, prefer the Invicti helpers in `agent-workspace/agent_helpers.py`:
- `invicti_get(path, params=...)`
- `invicti_paged_list(path, params=..., page_size=..., max_pages=...)`
- `invicti_resolve_website(query)`
- `invicti_list_scheduled_scans()` / `invicti_schedules_for_website(query)`
- `invicti_issue_counts(website_name)` / `invicti_issues_sample(website_name, ...)`

These helpers intentionally avoid printing secrets and default to `rawDetails=false` for issues.

## How to answer common user questions
### “Schedules” / “List scheduled scans”
Use:
- `GET /api/1.0/scans/list-scheduled?page=&pageSize=`

Return a compact list with (at minimum):
- `Name`
- `TargetUrl`
- `NextExecutionTime`
- `ScheduleRunType`
- `Disabled` / `EnableScheduling`

Note: `list-scheduled` returns *scheduled scan entries* (often scan-profile-like objects). Filter client-side.

### “Does website <X> have a schedule?”
Steps:
1. Resolve the website (accept URL, root URL, or display name):
   - `GET /api/1.0/websites/get?query=<name-or-url>`
   - If not found, fallback to `GET /api/1.0/websites/searchlist?searchTerm=<term>` and pick the best match.
2. List scheduled scans.
3. Match schedules to the website primarily by URL:
   - Compare `schedule.TargetUrl` to `website.RootUrl` (normalize trailing `/`, ignore scheme differences when needed).
   - Also check `schedule.AdditionalWebsites` when present.
4. Report:
   - whether a schedule exists
   - which schedule(s) matched
   - next run time(s)

### “Does website <X> have vulnerabilities?”
Use the Issues API with the website name:
- `GET /api/1.0/issues/allissues?webSiteName=<website.Name>&severity=<...>&page=&pageSize=&rawDetails=false`

Practical pattern:
- Query `TotalItemCount` across severities (`Critical`, `High`, `Medium`, `Low`, `Information`, `BestPractice`).
- If all are 0, the website has no issues recorded for those severities.
- If non-zero, optionally fetch a small sample and group by:
  - `Type` (stable, good for dedup)
  - `Title` (human readable)

Avoid `rawDetails=true` unless the user explicitly asks for proof-of-concept / request-response payloads.

### “What vulnerabilities does website <X> have?”
Use the same Issues endpoint, but pull a bounded sample (or multiple pages when requested) and summarize:
- counts by severity
- top `Type` / `Title`
- last seen / first seen dates for a few representative findings

### “Technologies for website <X>”
Use:
- `GET /api/1.0/technologies/list?webSiteName=<website.Name>&page=&pageSize=`

Summarize:
- total technology records
- number out-of-date (`IsOutofDate`)
- top tech by critical/high issue counts

## Endpoint quick reference
Websites:
- `GET /api/1.0/websites/get?query=...`
- `GET /api/1.0/websites/searchlist?searchTerm=...`
- `GET /api/1.0/websites/list?page=&pageSize=`
- `GET /api/1.0/websites/get/{id}`

Schedules (scheduled scans):
- `GET /api/1.0/scans/list-scheduled?page=&pageSize=`
- `GET /api/1.0/scans/get-scheduled/{id}`

Issues (vulnerabilities):
- `GET /api/1.0/issues/allissues` (filter by `webSiteName`, `severity`)
- `GET /api/1.0/issues/todo`
- `GET /api/1.0/issues/addressedissues`
- `GET /api/1.0/issues/report` (CSV export)

Stacks:
- `GET /api/1.0/technologies/list`
- `GET /api/1.0/vulnerability/list` (definitions/templates)
- `GET /api/1.0/vulnerability/types` (type strings)

## Swagger discovery workflow (when you need a new endpoint)
When unsure which endpoint supports a feature, search the Swagger JSON for tags/paths/keywords:
- https://www.netsparkercloud.com/swagger/docs/v1

Example approach:
1. Fetch Swagger JSON.
2. Filter paths by keyword (e.g., `schedule`, `scan`, `issues`, `website`).
3. Read `parameters` to learn required query/body fields.
4. Prefer endpoints that support server-side filtering; otherwise page and filter locally.
