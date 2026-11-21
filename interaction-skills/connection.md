# Connection & Tab Visibility

## The omnibox popup problem

When Chrome opens fresh, the only CDP `type: "page"` targets are `chrome://inspect` and `chrome://omnibox-popup.top-chrome/` (a 1px invisible viewport). If the daemon attaches to the omnibox popup, all subsequent work — including `new_tab()` and `goto_url()` — happens on tabs that exist in CDP but may not be visible in the Chrome UI.

The daemon's `attach_first_page()` handles this by creating an `about:blank` tab when no real pages exist. If you still end up on an invisible tab, use `switch_tab()` to attach to the real tab. Call `activate_tab()` only when the user explicitly asks Chrome to visibly show it.

## Startup sequence

1. Check if a daemon is already running with `daemon_alive()`
2. If stale sockets exist but daemon is dead, clean them up
3. List open tabs with `list_tabs()` to see what's available
4. `ensure_real_tab()` attaches to a real page
5. `switch_tab(target_id)` attaches without changing the visible Chrome tab; use `activate_tab(target_id)` only for a user-requested visible switch

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

If Chrome is behind other windows or on another desktop and the user explicitly wants it shown:

```python
import subprocess
subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'])
```

For normal agent work, do not activate Chrome. Screenshots and CDP input work
on the attached background tab; activate only for a page that demonstrably
pauses visibility-dependent rendering while hidden.

## A selected Chrome tab reports `hidden` on Windows

Check that the harness is attached to the selected tab and that the Chrome
window is focused, uncovered, and not minimized. Read both values over CDP
with `js()`, which calls `Runtime.evaluate` on the attached tab.

```python
print(js("({ visibility: document.visibilityState, focused: document.hasFocus() })"))
```

On Windows 11 with headed Chrome 156.0.8078.80 and browser-harness 0.1.13,
the [reporter of #973](https://github.com/browser-use/browser-harness/issues/973)
observed `hidden` with `focused: true` even in an uncovered window.

For a diagnostic comparison, use a separate test profile with CDP enabled.
Record a baseline, then relaunch Chrome with
`--disable-features=CalculateNativeWinOcclusion` as the only launch flag change.
Reattach and repeat the probe with the same page and window conditions. The
reporter observed `visible` with the flag, even when a covering window took
focus. Remove the flag after the comparison. Its effect may vary by Chrome
version and launch environment, and the result alone does not establish the cause.

## Navigating

Prefer navigating an existing tab over `new_tab()`. Harness-created tabs open in the background.

```python
tab = ensure_real_tab()
goto_url("https://example.com")
```
