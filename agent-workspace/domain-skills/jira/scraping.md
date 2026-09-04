---
name: jira-cloud-scraping
description: Jira Cloud (*.atlassian.net) — REST API via in-tab fetch with session cookies, site discovery, JQL search, traps.
---

# Jira Cloud — *.atlassian.net

Skip DOM scraping entirely. Every logged-in Jira tab can call the REST API with session
cookies via `js()` fetch — far faster and more complete than reading the board UI.

## The pattern

Open a tab on the Jira site, then fetch same-origin with `credentials: "include"`.
`js()` doesn't await promises, so stash the result on `window` and poll:

```python
js("""
window.__r = null;
fetch("/rest/api/3/search/jql?jql=" + encodeURIComponent("assignee = currentUser() ORDER BY updated DESC")
      + "&maxResults=50&fields=summary,status,assignee,priority,issuetype,duedate,updated,project",
      {headers: {"Accept": "application/json"}, credentials: "include"})
  .then(r => r.json()).then(d => { window.__r = JSON.stringify(d); })
  .catch(e => { window.__r = JSON.stringify({error: String(e)}); });
""")
result = None
for _ in range(40):
    time.sleep(0.5)
    result = js("window.__r")
    if result: break
```

## Endpoints (all same-origin GET unless noted)

| Endpoint | What |
|---|---|
| `/rest/api/3/myself` | Who the session is logged in as (displayName, emailAddress, accountId) |
| `/rest/api/3/search/jql?jql=<JQL>&maxResults=50&fields=...` | JQL search — the workhorse. Paginates via `nextPageToken`; `isLast` flags the final page |
| `/rest/api/3/project/search?maxResults=50` | List visible projects |
| `/rest/api/3/issue/<KEY>` | Full single issue incl. description/comments |
| `/gateway/api/available-sites` | POST `{"products": ["jira-software.ondemand","jira-core.ondemand","jira-servicedesk.ondemand"]}` → all Atlassian sites this account can access |

## Traps

- **The obvious site may be empty.** An account often spans several `*.atlassian.net`
  sites (e.g. a company site plus a vendor's). If `assignee = currentUser()` returns 0,
  don't conclude "no tickets" — POST `/gateway/api/available-sites` and check the others.
  Session cookies are per-subdomain: open a new tab on the other site before fetching.
- `/jira/your-work` redirects (e.g. to `/jira/projects`) after load; injecting `js()`
  before the redirect settles loses your `window` state. `wait_for_load()` then sleep ~2s,
  or just fetch from whatever page it lands on — same origin is all that matters.
- Empty search results come back as `{"issues": [], "isLast": true}` with HTTP 200 —
  also check `errorMessages` in the body for JQL errors, which are 200s too on some paths.
- Service-desk projects (`projectTypeKey: service_desk`) are searchable with plain JQL —
  no need for the separate Service Management API just to list/read tickets.
- The old `/rest/api/3/search` (no `/jql`) endpoint is deprecated; use `/search/jql`.
