# SharePoint / OneDrive file downloads

Downloading actual file bytes from `*.sharepoint.com` document libraries.

## What works

Open a tab on the tenant origin first, then fetch in page context with cookies:

```python
import json, base64
from urllib.parse import quote

new_tab("https://<tenant>.sharepoint.com/sites/<Site>")
wait_for_load()

url = "https://<tenant>.sharepoint.com/sites/<Site>/Shared Documents/<path>/<file>.pdf"
code = """(async () => {
  const r = await fetch(%s, {credentials: 'include'});
  if (!r.ok) return 'ERR:' + r.status;
  const bytes = new Uint8Array(await r.arrayBuffer());
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000)
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(bin);
})()""" % json.dumps(quote(url, safe=":/"))
data = base64.b64decode(js(code))
```

- The direct file `webUrl` under `/Shared Documents/` returns the binary when authenticated — no need for `?download=1` or the `download.aspx` route.
- `quote(url, safe=":/")` the URL: library paths contain spaces.
- Works for multi-MB files; base64 marshals fine through `js()`. Verify with the magic bytes (`%PDF-`, `PK`, ...).
- Personal OneDrive (`<tenant>-my.sharepoint.com`) is a different origin — open a tab there before fetching its files.

## Traps

- `http_get()` fails: SharePoint needs session cookies, which pure HTTP doesn't carry.
- The Microsoft Graph / ms365 MCP `read_resource` on a `file:///` URI returns *extracted text*, not bytes, and its search results carry `downloadUrl: null`. Don't burn time there if you need the real file.
