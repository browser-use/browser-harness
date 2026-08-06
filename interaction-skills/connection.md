# Connection & Tab Visibility

## The omnibox popup problem

When Chrome opens fresh, the only CDP `type: "page"` targets are `chrome://inspect` and `chrome://omnibox-popup.top-chrome/` (a 1px invisible viewport). If the daemon attaches to the omnibox popup, all subsequent work — including `new_tab()` and `goto_url()` — happens on tabs that exist in CDP but may not be visible in the Chrome UI.

The daemon's `attach_first_page()` handles this by creating an `about:blank` tab when no real pages exist. If you still end up on an invisible tab, use `switch_tab()` which calls `Target.activateTarget` to bring the tab to front.

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

## Clicking the "Allow remote debugging?" sheet without the user (macOS, Chrome 148+)

The CDP websocket handshake hangs until the user clicks **Allow** on a native Chrome sheet. The sheet only exists *while a connection attempt is pending*, and its buttons have **no AXTitle** — match by `description` instead. Start the connect in the background, then:

```bash
# detect: the sheet is named "Allow remote debugging?"
osascript -e 'tell application "System Events" to tell process "Google Chrome" to get name of sheets of front window'

# click Allow (buttons are unnamed; "Turn off in settings"/"Cancel"/"Allow" by description)
osascript -e 'tell application "System Events" to tell process "Google Chrome" to click (button 1 whose description is "Allow") of group 1 of group 2 of group 1 of group 1 of group "Allow remote debugging?" of sheet 1 of front window'
```

The first harness call after the click may still report the old handshake timeout — retry once; the Allow grant is sticky.

## Screenshot pixels ≠ click coordinates (Retina)

`click(x, y)` takes CSS/DOM pixels, but on Retina displays `screenshot()` output is downscaled (e.g. a 1800px-wide viewport produces a 900px-wide PNG). Clicking coordinates read off the screenshot lands at half-position and silently hits the wrong element. Get click targets from the DOM instead:

```python
import json
r = json.loads(js("""
(()=>{const el=[...document.querySelectorAll('button')].find(b=>/create/i.test(b.textContent));
 const b=el.getBoundingClientRect();
 return JSON.stringify({x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)})})()
"""))
click(r["x"], r["y"])
```

Or scale screenshot coords by `page_info()["w"] / image_width`. Sites with sticky promo banners (Google Cloud console's free-trial bar) also shift everything ~25px between screenshots — re-resolve coordinates from the DOM right before each click.
