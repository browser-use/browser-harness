# Google Cloud Console — service accounts & API keys

## Deep links (skip all menu navigation)

- Enable an API: `https://console.cloud.google.com/apis/library/<service>.googleapis.com?project=<PROJECT_ID>` — one `Enable` button, redirects to the API overview when done.
- Create a service account: `https://console.cloud.google.com/iam-admin/serviceaccounts/create?project=<PROJECT_ID>`
- Keys page for an SA: `https://console.cloud.google.com/iam-admin/serviceaccounts/details/<SA_UNIQUE_ID>/keys?project=<PROJECT_ID>` — the unique id is shown as "OAuth 2 Client ID" in the SA list right after creation.

## Traps

- The console URL after login includes the currently selected project as `?project=...` — reuse it instead of asking the user which project to use for throwaway integrations.
- SA creation: typing the display name auto-fills the account ID; the resulting email is shown live under the ID field (`<id>@<project>.iam.gserviceaccount.com`). Grab it from there — you need it to share resources with the SA.
- "Create and close" (skip steps 2–3) is enough when access will be granted by sharing a resource (e.g. a Google Sheet) rather than IAM roles.
- Key creation: Add key → Create new key → JSON (preselected) → Create. The JSON downloads silently to `~/Downloads/<project>-<hex>.json` — no save dialog. Poll `ls -t ~/Downloads/<project>-*.json`.
- Sheets/Drive access for an SA needs NO project roles: just share the document with the SA's email as Editor. The SA can't accept invites; sharing is enough.
