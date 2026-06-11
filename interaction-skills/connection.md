# Connection & Tab Visibility

## The omnibox popup problem

When Chrome opens fresh, the only CDP `type: "page"` targets are `chrome://inspect` and `chrome://omnibox-popup.top-chrome/` (a 1px invisible viewport). If the daemon attaches to the omnibox popup, all subsequent work — including `new_tab()` and `goto()` — happens on tabs that exist in CDP but may not be visible in the Chrome UI.

The daemon's `attach_first_page()` handles this by creating an `about:blank` tab when no real pages exist. If you still end up on an invisible tab, use `switch_tab()` which calls `Target.activateTarget` to bring the tab to front.

## Startup sequence

1. Check if a daemon is already running with `daemon_alive()`
2. If stale sockets exist but daemon is dead, clean them up
3. List open tabs with `list_tabs()` to see what's available
4. `ensure_real_tab()` attaches to a real page
5. `switch_tab(target_id)` both attaches AND activates (brings to front)

```python
if not daemon_alive():
    import os
    for f in ["/tmp/bu-default.sock", "/tmp/bu-default.pid"]:
        if os.path.exists(f): os.unlink(f)
    ensure_daemon()

tabs = list_tabs()
for t in tabs:
    print(t["url"][:60])

tab = ensure_real_tab()
```

## Brave (and Chromium 144+) on a fixed debug port

The brave://settings "Remote debugging" checkbox opens CDP on `127.0.0.1:9222`, but the HTTP discovery endpoints (`/json/version`, `/json/list`) return **404** — an empty curl response does NOT mean the port is dead. Read the websocket path from the profile dir instead:

```bash
cat "$HOME/Library/Application Support/BraveSoftware/Brave-Browser/DevToolsActivePort"
# line 1: port, line 2: /devtools/browser/<uuid>
```

Then connect with an explicit ws override and a dedicated daemon namespace:

```bash
BU_NAME=brave BU_CDP_WS="ws://127.0.0.1:9222/devtools/browser/<uuid>" browser-harness <<'PY'
new_tab("https://example.com")
PY
```

If the first call fails with `no close frame received or sent`, remove the stale `/tmp/bu-brave.sock` and `/tmp/bu-brave.pid` and retry — the daemon reconnects cleanly. The browser uuid changes on every Brave restart, so re-read `DevToolsActivePort` when reconnecting after a restart.

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
goto("https://example.com")
```
