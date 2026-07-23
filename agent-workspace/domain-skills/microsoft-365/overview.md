# Microsoft 365 (SharePoint Online + Loop)

Enterprise tenants. Auth via Microsoft Entra. Useful surfaces:

- `https://<tenant>-my.sharepoint.com` — per-user OneDrive (personal Documents/Meetings)
- `https://<tenant>.sharepoint.com` — shared sites
- `https://loop.cloud.microsoft` — Loop document viewer
- `https://www.office.com` — M365 home / unified search

The two SharePoint origins are separate; SharePoint search from one won't always see content in the other.

## Auth cookie sync

When mirroring auth from a logged-in real Chrome via `Network.getCookies` → `Network.setCookies`, scope export to **all** Entra alias hosts. Missing any of these can cause silent re-auth redirects:

```python
M365_HOSTS = (
    "login.microsoftonline.com",
    "login.microsoft.com",      # Entra alias — easy to miss
    "login.windows.net",        # legacy alias still in rotation
    "office.com", "microsoft.com", "sharepoint.com",
    "loop.cloud.microsoft", "substrate.office.com",
)
cdp("Network.getCookies", urls=[f"https://{h}/" for h in M365_HOSTS])
```

On import, preserve modern `CookieParam` fields (`partitionKey` object form, `sourceScheme`, `sourcePort`, `priority`). Drop output-only `partitionKeyOpaque`.

MSAL token cache lives in `localStorage`/IndexedDB, not cookies. Cookie sync covers SharePoint REST and Loop viewer DOM only not MSAL flows.

Non-KMSI ESTSAUTH can expire in 24h, re-sync per run for long sessions.

## SharePoint REST search

Call `/_api/search/query` from a same-origin tab so cookies travel:

```python
new_tab("https://<tenant>-my.sharepoint.com/")
wait_for_load()
js("""
(async () => {
  const params = new URLSearchParams({
    querytext: "'Core AI Standup filetype:loop'",
    rowlimit: "5",
    selectproperties: "'Title,Path,ServerRedirectedURL,FileExtension,LastModifiedTime,Author,UniqueId,HitHighlightedSummary'"
  });
  const r = await fetch('/_api/search/query?' + params, {
    credentials: 'include',
    headers: {Accept: 'application/json;odata=nometadata'}
  });
  return JSON.stringify({status: r.status, data: await r.json()});
})()
""")
```

Per-row `Cells[].Key`: `Title`, `Path` (raw SharePoint URL — don't navigate), `ServerRedirectedURL` (use this for navigation), `HitHighlightedSummary` (strip `<c0>` / `<ddd/>` markers), plus stable IDs (`UniqueId`, `ListId`, `SiteId`, `WebId`, `DocId`).

Search ranking favors *recently touched* over *recently authored* a stale meeting can re-surface if someone reopened it. Filter by date derived from titles when stable ordering matters.

## Loop documents (`.loop` files)

Loop docs are a Fluid Framework binary container with no public decoder. **Don't navigate raw `.loop` SharePoint URLs** they return `application/octet-stream` and Chrome shows a download modal:

```python
from urllib.parse import urlsplit
def is_raw_loop(url):
    p = urlsplit(url)
    return p.path.lower().endswith(".loop") and "loop.cloud.microsoft" not in p.netloc
```

Navigate the **viewer** URL instead (the `ServerRedirectedURL` from search, hosted at `loop.cloud.microsoft/p/<id>`) and read `document.body.innerText` after content stabilizes:

```python
new_tab(viewer_url)
last = ""; stable = 0
for _ in range(30):
    wait(1)
    text = js("document.body ? document.body.innerText : ''") or ""
    if len(text) >= 500 and text == last:
        stable += 1
        if stable >= 2: break
    else:
        stable = 0
    last = text
```

The rendered DOM has Loop app chrome before the body. Slice from the first section header:

```python
import re
m = re.search(
    r"^(AI-generated content.*|Decisions\s*|Open questions\s*|Agenda\s*|Meeting notes\s*)$",
    last, flags=re.MULTILINE,
)
body = last[m.start():] if m else last
```

Page title is prefixed with a status emoji like `🟢 Standup: Core AI 2026-05-14` — strip it.

## Auth-redirect probe

Cookies-on-disk ≠ working auth. To verify, navigate a protected URL and check where you land:

```python
new_tab("https://<tenant>-my.sharepoint.com/")
wait_for_load()
auth_required = (
    js("location.hostname") == "login.microsoftonline.com"
    or js("document.title").lower().startswith("sign in")
)
```
