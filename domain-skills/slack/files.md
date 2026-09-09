# Slack: downloading shared files

Fetching files behind a Slack workspace login, given a permalink like
`https://<ws>.slack.com/files/<USERID>/<FILEID>/<name>`.

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
   d = next(c["value"] for c in r["cookies"] if c["name"] == "d")
   ```

2. Fetching the permalink HTML with that cookie (plain `http_get`/curl, no browser needed)
   yields a page embedding `"api_token":"xoxc-…"` and `team_id = "T…"`. No need to load
   `app.slack.com` or dig through localStorage (`localConfig_v2` only exists on the
   `app.slack.com` origin anyway).

3. API calls: POST to `https://<ws>.slack.com/api/<method>` with `token=<xoxc>` as a form
   field **and** the `d` cookie — xoxc web tokens are only valid together with the cookie.
   `files.info`, `files.list`, `search.files` all work.

4. Download `url_private` (or the files-pri URL) with just the `d` cookie.

## Traps

- The permalink page in a real browser tab sticks on "Redirecting…" forever (it's waiting
  to open the desktop app) — don't wait for it; you only need it as an HTML fetch.
- `files.list` sorts/filters in ways that can silently omit recent files; when a named
  file must be found, `search.files` is the reliable path.
