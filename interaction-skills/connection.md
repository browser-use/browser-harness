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

## The Allow-dialog race (agents)

Every NEW WebSocket connection to Chrome's CDP port pops a per-connection "Allow remote
debugging?" dialog, and the daemon's handshake gives up after ~10s (websockets'
`open_timeout`). Clicking Allow on a *stale* dialog does nothing for the next attempt —
each retry spawns a fresh dialog tied to that one connection. For an agent whose
tool-call roundtrips are slower than the timeout, sequencing "connect, then click" as
two separate steps always loses the race.

Win it inside ONE shell command: launch the connection in the background, then click
the dialog with `cliclick` (or any native clicker) while the handshake is pending.
The dialog renders at a fixed position — centred horizontally, vertically offset —
with Allow at the bottom right (on a 1920×1080 screen that's ≈ `1017,592`; derive it
from the dialog window bounds: x+391, y+201 of a 448×240 window).

```bash
( browser-harness <<'PY' > /tmp/bu-race.out 2>&1 &
ensure_real_tab()
print("CONNECTED:", page_info())
PY
) ; sleep 3.5 && cliclick c:1017,592 && sleep 2 && cliclick c:1017,592 && sleep 6 && cat /tmp/bu-race.out
```

The second click covers a late-rendering dialog. Stacked leftover dialogs from earlier
failed attempts can be dismissed at the same coordinates — they're harmless either way.

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
