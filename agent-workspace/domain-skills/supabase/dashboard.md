# Supabase dashboard — SQL editor and permission inspection

## Navigation and identity

- Organization projects: `/dashboard/org/{organization_id}`.
- Project home: `/dashboard/project/{project_ref}`. Confirm the project name,
  branch/environment and visible project URL before any database action.
- SQL editor: follow the **SQL Editor** navigation link. The project also has
  a top-bar button with the same name, so use the link role when disambiguating.
- A signed-in organization tab can coexist with an older tab still showing the
  sign-in page. Inspect current user tabs before concluding login failed.

## Editor mechanics

The SQL editor exposes a textbox named **Editor content**, but it is a code
editor, not an ordinary full-document textarea. Its accessible value can contain
only the window around the cursor. Generic textarea replacement can leave a
prefix from the old SQL, producing a concatenated invalid query.

For replacement, focus the editor, send the platform Select All shortcut,
Backspace, then insert the new SQL as text/paste. Read the rendered code before
Run. Do not rely on the textbox value alone to verify the entire query. Avoid
framework/model mutation workarounds.

- **Run** executes SQL; inspect the Results panel afterward.
- Successful DDL can show **Success. No rows returned**. Follow with independent
  read-only checks; a success message is not a substitute for verification.
- Results are a virtualized ARIA grid. A label saying 20 rows can coexist with
  fewer rendered rows. Do not infer missing records from the DOM window. For
  permission assertions, prefer a bounded aggregate query returning one row.
- The editor can automatically append a result limit (typically 100). Read the
  displayed SQL error before changing a valid query to work around that limit.

## Safe audit patterns

Read catalog metadata first (pg_class, pg_namespace, pg_proc and privilege
functions), not sensitive business rows. SQL ownership/permission changes need
explicit task authorization, exact scope and transaction/verification plans.

`has_table_privilege(role, table, 'SELECT,INSERT')` means **any listed privilege**,
not all: use separate checks joined with AND to prove full backend CRUD. For
proving denial, checking that none of a combined list is granted is appropriate.

Public API HEAD with count can verify read access without returning row bodies.
A positive count proves rows are visible; an empty result alone cannot establish
whether a table has effective RLS. Admin RLS/grant inspection resolves that.

Never include keys, tokens, customer data, project identifiers or organization
state in reusable skills or public issue reports.
