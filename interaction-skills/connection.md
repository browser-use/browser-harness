# Connection & Tab Visibility

## Your tabs

The daemon holds one connection to the browser and many owners on it. Your
first command opens a background `about:blank` tab that only you drive; it is
never the person's tab and never the invisible omnibox popup. Commands go to
your current tab until you `new_tab()` or `switch_tab()`.

```python
tab = current_tab()           # opens your background tab on first use
goto_url("https://example.com")
print(list_tabs())            # owner: "you", None (the person's) or "taken"
```

To work in a tab the person already has open, take it explicitly with
`switch_tab(tab)`; it fails with `tab-taken` while another agent holds it.

## Startup sequence

1. `browser-harness` calls `ensure_daemon()`; it reuses the running daemon, so Chrome asks to Allow only once per run.
2. `list_tabs()` to see what is open.
3. `new_tab(url)` for a fresh tab, or `switch_tab(target_id)` to take a listed one. Neither changes Chrome's visible tab; use `activate_tab(target_id)` only for a user-requested visible switch.

## Bringing Chrome to front

If Chrome is behind other windows or on another desktop and the user explicitly wants it shown:

```python
import subprocess
subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'])
```

For normal agent work, do not activate Chrome. Screenshots and CDP input work
on your background tab; activate only for a page that demonstrably pauses
visibility-dependent rendering while hidden.
