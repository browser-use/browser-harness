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

## Hung attached session (every helper call blocks forever)

If `page_info()` / `js()` hang with no error while the daemon log looks healthy ("attached ... listening on ..."), the attached tab's renderer is not answering `Runtime.evaluate` (long-idle SPA tabs, e.g. Mighty Networks feeds, can get into this state). Browser-level CDP still works — the hang is session-scoped, and `restart_daemon()` won't fix it because the daemon re-attaches to the same first page target.

Diagnose and recover by talking to the daemon socket directly with a timeout — helper calls would just block:

```python
import socket, json

def send(req, timeout=15):
    s = socket.socket(socket.AF_UNIX); s.settimeout(timeout)
    s.connect("/tmp/bu-default.sock")
    s.sendall((json.dumps(req) + "\n").encode())
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = s.recv(65536)
        if not chunk: break
        buf += chunk
    return json.loads(buf)

# browser-level call works -> daemon + Chrome fine, attached session is hung
send({"method": "Target.getTargets", "params": {}, "session_id": None})

# re-point the daemon's default session at a fresh tab (never evaluates on the hung one)
tid = send({"method": "Target.createTarget", "params": {"url": "about:blank"}, "session_id": None})["result"]["targetId"]
sid = send({"method": "Target.attachToTarget", "params": {"targetId": tid, "flatten": True}, "session_id": None})["result"]["sessionId"]
send({"meta": "set_session", "session_id": sid})
```

Don't use `switch_tab()` for this — its unmark step runs `Runtime.evaluate` on the hung session first and blocks. Trap within the trap: `restart_daemon()` only STOPS the daemon (cleanup is deliberate; `run.py`'s `ensure_daemon()` restarts it on the next harness call) — if you're working over the raw socket, call `ensure_daemon()` yourself or the socket is just gone.

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
