# Comp AI (app.trycomp.ai) — reading a compliance program

Comp AI is a Next.js/Radix compliance platform (SOC 2, ISO 27001, HIPAA, GDPR). Everything below was verified against a live org in Oct 2026.

## URL patterns

All routes are under `/org_<id>/…`:

- `/frameworks` → `/frameworks/frm_<id>` (tabs via `?tab=controls|requirements|history`)
- `/frameworks/frm_<id>/controls/ctl_<id>` — control detail (policies / tasks / documents tabs)
- `/frameworks/frm_<id>/requirements/frk_rq_<id>` — requirement detail
- `/tasks` (sidebar label is "Evidence") → `/tasks/tsk_<id>` — task detail with status, assignee, frequency, attachments, comments
- `/policies` → `/policies/pol_<id>?tab=content` — the `?tab=content` param is required to get the policy text; the bare URL only shows settings
- `/documents/<form-type>` e.g. `rbac-matrix`, `infrastructure-inventory`, `tabletop-exercise`
- `/people/all`, `/people/mem_<id>`, `/risk/rsk_<id>`, `/vendors/vnd_<id>`, `/cloud-tests`, `/integrations`, `/overview?tab=findings` (auditor findings), `/settings/api-keys`, `/trust`

## Reading data

- `document.querySelector('main').innerText` gives clean text for every page; tables are plain `<table>` with `<tr>` rows whose first `<a href>` carries the entity id.
- On a control page all three tab tables (policies, tasks, documents) are in the DOM at once, so one `table tbody tr` scrape returns every row; split rows by whether the href contains `/policies/`, `/tasks/` or `/documents/`.
- The Requirements tab paginates 10 per page. The pager "Next" is `<a role="button" aria-label="Go to next page">`; click it via JS and re-scrape until it is missing. Buttons named "Next" do not exist.
- Task pages render "Status / Assignee / Frequency / Department / Review Date" as label-then-value lines; attachments are listed as `filename\ndd-Mon-yyyy`.

## Traps

- The "Framework updates (N)" button on `/policies` opens a Radix dialog whose Cancel/Close buttons ignore synthetic `.click()` and Escape. Use a compositor click (`click_at_xy` on the button's rect) or just navigate away. Do not click "Apply to all" — it creates draft versions of every policy.
- The `Content` tab of a policy page is lazy: text appears ~2 s after `?tab=content` loads.
- A task can be linked to many controls; the control list's TASKS counter counts those links, so a single "Done" task can lift every control's score.

## No-browser alternative

Comp AI has a full REST API (`https://api.trycomp.ai/v1`, header `X-API-Key`, OpenAPI at `https://www.trycomp.ai/docs/openapi.json`, ~400 paths) and a hosted MCP connector at `https://mcp.trycomp.ai/mcp`. Prefer those for anything beyond a one-off read.
