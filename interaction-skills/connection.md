# Connection & Tab Visibility

## The omnibox popup problem

When Chrome opens fresh, the only CDP `type: "page"` targets are `chrome://inspect` and `chrome://omnibox-popup.top-chrome/` (a 1px invisible viewport). If the daemon attaches to the omnibox popup, all subsequent work — including `new_tab()` and `goto_url()` — happens on tabs that exist in CDP but may not be visible in the Chrome UI.

The daemon's `attach_first_page()` handles this by creating an `about:blank` tab when no real pages exist. If you still end up on an invisible tab, use `switch_tab()` which calls `Target.activateTarget` to bring the tab to front.

## Auto-reconnect

If the CDP websocket drops mid-session (Chrome closed/restarted, a remote
endpoint hiccup), the daemon rebuilds the connection and retries the failing
call once — for a local Chrome it re-resolves the live websocket via
`get_ws_url()`, so it also recovers from a Chrome restart on the same port. The
call the caller made succeeds transparently; a follow-up call re-attaches any
tab-specific session. Only if the rebuild itself fails (e.g. a remote
`BU_CDP_WS` whose endpoint is gone) do you get an error back. No manual
`--reload` needed for a plain drop.

## Command timeout

Every helper→daemon CDP call has a read budget (default 30s, screenshots 60s),
tunable via `BH_CMD_TIMEOUT` or per-call `cdp(..., _timeout=N)` /
`js(..., timeout=N)`. This is separate from the short socket-connect budget, so
a slow-but-valid navigation or awaited promise no longer fails at connect time.

## Startup sequence

1. Check if a daemon is already running with `daemon_alive()`
2. If stale sockets exist but daemon is dead, clean them up
3. List open tabs with `list_tabs()` to see what's available
4. `ensure_real_tab()` attaches to a real page
5. `switch_tab(target_id)` both attaches AND activates (brings to front)

```python
if not daemon_alive():
    import os, ipc
    ipc.cleanup_endpoint("default")
    pid = ipc.pid_path("default")
    if pid.exists(): pid.unlink()
    ensure_daemon()

tabs = list_tabs()
for t in tabs:
    print(t["url"][:60])

tab = ensure_real_tab()
```

## Bringing Chrome to front

If Chrome is behind other windows or on another desktop:

```python
import subprocess
subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'])
```

## Navigating

Prefer navigating an existing tab over `new_tab()`. Tabs created via CDP's `Target.createTarget` are visible but may open behind the active tab.

```python
tab = ensure_real_tab()
goto_url("https://example.com")
```
