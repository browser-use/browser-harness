---
name: neon-console
description: Neon Postgres console (console.neon.tech) — project/branch navigation, finding compute endpoint hostnames, extracting connection strings without picking up the UI's display-whitespace.
---

# Neon Console — console.neon.tech

Serverless Postgres dashboard. Auth via SSO; treat as already-logged-in. The UI is a SPA (Next.js).

## Routes

| Route | What |
|---|---|
| `/app/org-<org-id>/projects` | Org-scoped project list (default landing) |
| `/app/projects/<project-id>` | Project dashboard (Connect button lives here) |
| `/app/projects/<project-id>/branches` | Branches table: name, parent, compute hours, primary compute endpoint, storage |
| `/app/projects/<project-id>?branchId=<branch-id>&database=<db>` | Project dashboard scoped to a branch — what the left-nav BRANCH picker switches between |

## Branches table — what the columns actually mean

Free plan typically shows two branches (`production` + `test`). **Each branch has its own primary compute endpoint** with its own hostname (`ep-<random>-<region>.<region>.aws.neon.tech`) — they are NOT shared. Earlier docs/folklore claiming "free plan shares one compute across branches" is wrong.

- `Compute` column = CU-hrs consumed in current period.
- `Primary compute` column shows autoscale range (e.g. `.25 ↔ 2 CU`) and an **Idle/Active** pill. The `.25 ↔ 2 CU` text *looks* like a link but it's actually a clickable cell that opens the **Edit primary compute** drawer — that drawer shows the endpoint name (`ep-<...>`) in an editable input.

### Getting an endpoint hostname for a branch

```python
# On /app/projects/<id>/branches
rect = js("""
  (() => {
    const rows = [...document.querySelectorAll('tr')].filter(tr => /production/i.test(tr.textContent || '') && /Default/.test(tr.textContent || ''));
    if (!rows.length) return null;
    const tr = rows[0];
    // Find the .25 ↔ 2 CU compute cell
    const all = [...tr.querySelectorAll('*')];
    const cu = all.find(el => /CU/.test((el.textContent || '').trim()) && /↔/.test(el.textContent || '') && el.children.length <= 1);
    if (!cu) return null;
    const r = cu.getBoundingClientRect();
    return {x: r.x + r.width/2, y: r.y + r.height/2};
  })()
""")
click(rect["x"], rect["y"])
wait(1)
endpoint = js("document.querySelector('input[value^=\"ep-\"]')?.value")
press_key("Escape")  # close drawer
```

The compute cell wraps to two visual lines on rows with multi-digit CU-hrs; clicking the centre of the cell sometimes lands between lines and opens a tooltip instead of the drawer. If `endpoint` is `None`, retry by clicking the row's cell at `r.x + 30, r.y + r.height/2` (left-justified, single-line target).

## Branch picker (left nav, "BRANCH" combobox)

Below the PROJECT nav. Currently selected branch's name is shown in a button at roughly `x=124, y=310` for a default 1442×1508 viewport. Clicking opens a dropdown listing all branches with a checkmark on the current one.

```python
# Switch the dashboard to the production-branch context
js("""
(() => {
  const btn = [...document.querySelectorAll('button')].find(b => /^test$/i.test((b.textContent || '').trim()) && b.getBoundingClientRect().x < 200);
  btn?.click();
})()
""")
wait(1)
js("""[...document.querySelectorAll('div')].find(el => (el.textContent || '').trim() === 'production' && el.getBoundingClientRect().x < 250)?.click()""")
wait(1)  # URL updates to ?branchId=...
```

The branch picker scopes the **Connect** dialog (and most dashboard widgets) to that branch — so to get a branch's connection string, switch the picker first, then click Connect.

## Getting a connection string — the whitespace trap

Project dashboard → **Connect** button (top-right) opens "Connect to your database". Branch + Compute dropdowns let you pick role/database/pooled-vs-direct. **Show password** is a button that toggles password visibility.

The connection string is rendered inside a `<div>` (NOT a `<textarea>`) where the host is split across multiple inline elements styled with `word-break`. Reading `el.textContent` returns the visible string — which has invisible inter-element whitespace baked in (e.g. `aws    .neon.tech` with 4 spaces). You will get DNS `ENOTFOUND` if you pass that string to a postgres client.

**Don't read textContent.** Either:

1. **Walk text nodes and strip all whitespace.** Postgres URLs cannot legally contain whitespace anywhere, so a global `/\s+/g` strip is safe (special chars in passwords are %-encoded per RFC 3986):

   ```python
   url_data = js("""
     (() => {
       function walkText(root, out) {
         if (root.nodeType === 3) { out.push(root.nodeValue); return; }
         for (const c of root.childNodes) walkText(c, out);
       }
       const candidates = [...document.querySelectorAll('*')].filter(el => {
         const t = el.textContent || '';
         return /postgresql:\\/\\//.test(t) && /neon\\.tech/.test(t) && el.children.length < 50;
       });
       candidates.sort((a, b) => (a.textContent || '').length - (b.textContent || '').length);
       if (!candidates.length) return null;
       const parts = [];
       walkText(candidates[0], parts);
       return parts.join('');
     })()
   """)
   import re
   url = re.sub(r"\s+", "", url_data)  # strip the layout whitespace
   ```

2. **Or click "Copy snippet" and read the clipboard** (more robust if the markup changes).

Sanity-check before use: the URL should start with `postgresql://`, contain a host matching `ep-[a-z0-9-]+\.[a-z0-9-]+\.aws\.neon\.tech`, contain `?sslmode=require`, and contain no `*` characters (asterisks mean Show password didn't get clicked).

### Pooled vs direct host

When "Connection pooling" is on (default), the host has a `-pooler` suffix: `ep-<random>-pooler.<region>.aws.neon.tech`. Use the pooler for normal app traffic; use the un-pooled host for DDL/migrations only if the migration runner needs session-level features (most don't, including drizzle-kit).

## Quirks and traps

- **Compute auto-suspends after idle (5 min on free plan)**, then needs ~1–2s to cold-start on the next connection. First connection from a fresh session may time out (`ETIMEDOUT`); retry once. Long-running clients (workers, pg-boss) keep it warm.
- **The "production" branch on a Neon project is just a default name**, not a guarantee that production data lives there. People often develop on a `test` branch and never cut over — so always confirm which branch holds the live data (look at CU-hrs and recency, not the name).
- **Each branch fork copies parent data + schema + drizzle migrations table at fork time**. If you ran `bun run db:migrate` against a branch that's never been migrated, drizzle will run all migrations from `0000` forward, not just the new one. Pre-check with `SELECT count(*) FROM drizzle.__drizzle_migrations` against the target branch URL before applying.
- **Org-id changes per Neon account** (`/app/org-<id>/projects`) — never hardcode it; navigate to the projects list and click through.
- **Project dashboard "Connect" button is branch-scoped** via the left-nav BRANCH picker, not via the Compute dropdown inside the dialog. The Compute dropdown only switches between primary/replica; it doesn't switch branches.
- **Branch row clicks (`<tr>`) don't navigate** — there is no anchor on the branch name. The kebab (3-dot) menu at the row's right edge has the only branch-level actions: rename, set-default, set-protected, delete. There is no "set as primary compute" because each branch already owns its own compute.

## What's not in this skill

- Programmatic API key + Neon REST API (`api.neon.tech/api/v2/...`) — preferable to the dashboard for repeatable ops, but out of scope here.
- Branch creation/deletion via UI (one-shot ops; just use the kebab menu).
- Billing surface.
