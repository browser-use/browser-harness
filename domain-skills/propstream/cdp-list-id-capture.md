# PropStream — virtual-scroll fix: capture list ID via CDP Network

The PropStream sidebar Marketing-Lists tree uses **virtual scrolling**. Once an account has more than ~9–10 saved lists, a newly-created list is rendered below the visible viewport and the harness can't click it via DOM queries or coordinate clicks — `scrollIntoView` doesn't work because the off-screen DOM node has no bounding rect, and the sidebar's outer scroller has no `overflow:auto` ancestor that we can scroll programmatically.

## Solution — bypass the sidebar entirely

PropStream's saved-list URL pattern is `https://app.propstream.com/property/group/<numeric_id>`. The Save modal's `POST` returns the new list's ID. We capture that response via CDP Network domain and navigate directly to the list URL.

## Implementation pattern

```python
from helpers import cdp, drain_events, click_at_xy, js

def save_list_capture_id(modal_save_coords):
    """Click the modal Save button and return the new list ID."""
    # Enable network capture + drain backlog right before the click
    cdp("Network.enable", {})
    drain_events()

    click_at_xy(*modal_save_coords)

    # Poll until we see a 200 from a list-create endpoint
    for _ in range(180):  # ~4.5 min max for large lists
        time.sleep(1.5)
        for e in drain_events():
            if e.get("method") != "Network.responseReceived":
                continue
            p = e.get("params", {})
            r = p.get("response") or {}
            url = r.get("url", "")
            if r.get("status") != 200:
                continue
            if not any(k in url for k in (
                "/api/group", "/api/marketing-list",
                "/api/property/group", "/groups",
            )):
                continue
            # Fetch + parse the response body
            body = cdp("Network.getResponseBody", {"requestId": p["requestId"]})
            text = body.get("body", "")
            if body.get("base64Encoded"):
                import base64
                text = base64.b64decode(text).decode("utf-8", "replace")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            # PropStream returns {id: <int>} (or {data: {id: <int>}})
            cand = payload.get("id")
            if cand is None and isinstance(payload.get("data"), dict):
                cand = payload["data"].get("id")
            if isinstance(cand, int) and cand > 1000:
                return cand
    return None
```

## Once you have the ID

```python
from helpers import goto_url, wait_for_load
goto_url(f"https://app.propstream.com/property/group/{list_id}")
wait_for_load()
# now the list is the active view — proceed with select-all + Export as
# documented in export-cash-buyers.md from step 12 onward.
```

## Why this is more reliable than the sidebar path

| Failure mode | Sidebar approach | This approach |
|---|---|---|
| List below the visible fold | `scrollIntoView` returns 0,0 because virtual node is unmounted — click misses | URL navigation works regardless of sidebar render state |
| Search input not present (account has only 1–2 lists) | Sidebar search button doesn't render — heuristics fail | No dependency on sidebar |
| User has many similarly-named lists | "Find by text" matches the wrong row | ID is unique by construction |
| Welcome modal re-fires on every nav | Modal blocks the sidebar click | Modal still has to be dismissed but the list URL bypasses sidebar entirely |

## Caveats

- `Network.enable` is a per-tab session setting; call it after `switch_tab` to the PropStream tab, not before.
- Drain the backlog (`drain_events()`) immediately before clicking Save — otherwise unrelated background API responses pollute the candidate list.
- PropStream's list-create endpoint URL is currently undocumented; the regex in the implementation matches a generous set of paths. Re-confirm the actual URL via the CDP capture itself on first run.
- For very large saves (≥5,000 records), the response can take up to a minute. The poll loop in the example above caps at ~4.5 minutes.
