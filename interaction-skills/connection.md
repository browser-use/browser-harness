# Connection & Tab Visibility

## The omnibox popup problem

When Chrome opens fresh, the only CDP `type: "page"` targets are `chrome://inspect` and `chrome://omnibox-popup.top-chrome/` (a 1px invisible viewport). If the daemon attaches to the omnibox popup, all subsequent work — including `new_tab()` and `goto_url()` — happens on tabs that exist in CDP but may not be visible in the Chrome UI.

The daemon's `attach_first_page()` handles this by creating an `about:blank` tab when no real pages exist. If you still end up on an invisible tab, use `switch_tab()` to attach to the real tab. Call `activate_tab()` only when the user explicitly asks Chrome to visibly show it.

## Shared connection

The CLI starts or reuses the default background connection automatically.
Multiple agents use the same daemon and separate tab IDs, not separate daemon
names. Do not remove socket/PID files yourself: another caller may be starting
the connection or waiting for Chrome's approval.

For a new task, print and retain `new_tab(url)`'s target ID. For later calls,
`switch_tab(target_id)` selects that exact tab for this script without changing
the visible Chrome tab or another agent's selection. If the user explicitly
asks to work in an existing tab, inspect `list_tabs()` and select its ID. A
matching URL alone is not proof that the tab is unused by another task.

Run `browser-harness --doctor` for connection trouble. A closed tab, slow
command, or truncated output does not mean the shared connection needs
restarting. A timed-out mutation may already have happened: inspect its result
before deciding what to do next. For a local Allow prompt, keep the original
command running and follow the platform-specific instructions in `SKILL.md`.

## Bringing Chrome to front

If Chrome is behind other windows or on another desktop and the user explicitly wants it shown:

```python
import subprocess
subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'])
```

For normal agent work, do not activate Chrome. Screenshots and CDP input work
on the attached background tab. Rendering trouble is not permission to
foreground Chrome; try temporary focus emulation as described in `SKILL.md`,
then report any remaining limitation.

## Navigating

Reuse a tab owned by this task. Harness-created tabs open in the background.

```python
switch_tab("TARGET_ID_RETAINED_BY_THIS_TASK")
goto_url("https://example.com")
```
