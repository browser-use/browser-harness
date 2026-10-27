# Slack: downloading shared files

Fetching files behind a Slack workspace login, given a permalink like
`https://<ws>.slack.com/files/<USERID>/<FILEID>/<name>`.

The contributor supplied these internal API observations without a validation date. Verify each response before relying on its fields.

Current discovery uses the first hostname label, which can be the workspace name or `app`.
Read this file directly for Slack file tasks when automatic discovery does not list it.

Only download files that the user requests and their session can access.
Keep cookies and tokens in memory. Never print them or put them in command arguments, files, or logs.
Allow credential requests only to the requested `<ws>.slack.com` workspace and `files.slack.com` over HTTPS. Check the parsed hostname before each request. Disable automatic redirects for credential requests. Validate each redirect destination before following it; never forward cookies or tokens to another host.

## URL structure

- The `FILEID` segment routes; the filename segment is cosmetic. Two permalinks that
  differ only in the filename (e.g. `…/F123/shot1.png` vs `…/F123/shot2.png`) return the
  **same** file. Users often hand you "same URL, just change the number" — resolve each
  real file ID instead.
- The `USERID` segment is not necessarily the uploader (share links keep the sharer's id),
  so `files.list?user=<USERID>` can come back empty for the file you're after. Use
  `search.files?query=<filename>` to resolve real per-file IDs.
- Raw bytes live at `https://files.slack.com/files-pri/<TEAMID>-<FILEID>/<name>` and need
  cookie auth.

## Auth without an app token

1. The `d` cookie on `.slack.com` is the session. It's HttpOnly, so in-page JS can't read
   it — read it over CDP from any workspace tab:

   ```python
   r = cdp("Network.getCookies", urls=["https://<ws>.slack.com/"])
   d = next((c["value"] for c in r["cookies"] if c["name"] == "d"), None)
   if d is None:
       raise RuntimeError("Sign in to the requested Slack workspace before downloading its files")
   ```

2. Fetching the permalink HTML with that cookie (an in-process HTTP request, no browser needed)
   yields a page embedding `"api_token":"xoxc-…"` and `team_id = "T…"`. No need to load
   `app.slack.com` or dig through localStorage (`localConfig_v2` only exists on the
   `app.slack.com` origin anyway).
   Require both fields in the response. Compare `team_id` with the requested workspace ID from its signed-in UI. Stop if the workspace differs or either field is absent; a Slack cookie alone does not prove workspace access.

3. API calls: POST to `https://<ws>.slack.com/api/<method>` with `token=<xoxc>` as a form
   field **and** the `d` cookie — xoxc web tokens are only valid together with the cookie.
   The contributor used `files.info`, `files.list`, and `search.files`. These internal session flows can change; inspect API errors before continuing.

4. Download `url_private` (or the files-pri URL) with just the `d` cookie.

## Traps

- The permalink page in a real browser tab sticks on "Redirecting…" forever (it's waiting
  to open the desktop app) — don't wait for it; you only need it as an HTML fetch.
- File lists and searches can omit results because of filtering or delayed indexing. Prefer `files.info` when the user supplies a file ID. Treat an empty search as inconclusive and inspect the workspace UI.
