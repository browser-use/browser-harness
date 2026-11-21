# Tabs

Use **CDP for control**, **UI automation for user-visible order**.

## Pure CDP (portable: macOS / Linux / Windows)

```python
tabs = list_tabs()                    # includes chrome:// pages too
real_tabs = list_tabs(include_chrome=False)
tid = new_tab("https://example.com")  # create + attach in the background
switch_tab(tid)                       # attach harness, move the horse marker
activate_tab(tid)                     # optional: explicitly show it in Chrome
print(current_tab())
print(page_info())
```

What CDP is good at:
- attach to a tab
- open a tab
- activate a known target
- inspect URL/title/viewport
- capture the attached tab's screenshot even if another tab is visibly frontmost

What CDP is bad at:
- matching the **left-to-right tab strip order** the user sees
- telling whether the attached target is an omnibox popup / internal page without URL filtering

## Resume a known task tab (fail closed)

For tasks that span CLI invocations, save the **exact** `targetId`, URL, and a
**caller-assigned, task-unique marker in the tab title** while the task owns
the tab. The horse marker is a movable indicator of the attached tab, **not**
proof that an agent owns it. If the tab still exists, use its exact ID; if its
ID became stale, only recover when **exactly one** tab matches the expected
URL **and** the caller's marker. Do not select the first of multiple
lookalikes, switch visibly to another tab, or close an unowned tab.

```python
# On initial task setup, after creating a dedicated agent-owned tab:
tid = new_tab("https://example.com/work")
# The caller must add its own unique marker, e.g. "[task-4831]", to the
# task page title before relying on stale-ID rediscovery.
# Persist tid, expected URL and the marker as task state.

# After a daemon/attachment disruption:
tid = reconnect_tab(
    tid,
    expected_url="https://example.com/work",
    owned_marker="[task-4831]",
)
# Work only after the returned ID has been verified.
```

`reconnect_tab()` lists real page targets, verifies URL/title before
attaching, and re-checks the attached page afterwards. It does **not**
activate/foreground the tab or open/close browser targets. It raises
`RuntimeError` on missing, changed or ambiguous identity; the caller must
then seek explicit user input or start a *new* authorized task-owned tab
instead of guessing. A live ID may be used with an exact URL alone, optionally
with `expected_title="..."`. Stale-ID recovery requires
`owned_marker="..."` as well as the URL. The title marker is a cooperative
convention, **not a cryptographic security or access-control boundary**;
do not use this helper as multi-tenant authorization. Chrome target IDs can
change after a tab/browser restart. Concurrent agents must still serialize
actions on the shared daemon to avoid a switch-between-check-and-use race.
The underlying `switch_tab()` retains its usual horse-title-marker behavior
(unless `BH_TAB_MARKER=0`); it never requests visible tab activation.

## Visible order (platform UI)

### macOS

```applescript
tell application "Google Chrome"
  set out to {}
  set i to 1
  repeat with t in every tab of front window
    set end of out to {tab_index:i, tab_title:(title of t), tab_url:(URL of t)}
    set i to i + 1
  end repeat
  return out
end tell
```

```applescript
tell application "Google Chrome"
  set active tab index of front window to 2
  activate
end tell
```

### Linux

No AppleScript. Same split still applies:
- use CDP for `new_tab`, attach, inspect, activate known targets
- use window-manager / browser UI automation when the user means visible order

Typical tools:
- `xdotool`
- `wmctrl`
- desktop-environment scripting (`gdbus`, KWin, GNOME Shell extensions, etc.)

## Rules that held up in practice

- `switch_tab()` intentionally does **not** change Chrome's visible tab.
- Static screenshots and normal CDP input work on the attached background tab.
- `activate_tab()` is only for a user-requested visible switch. Rendering or
  input trouble is not permission to foreground Chrome; use background CDP and
  temporary focus emulation first.
- `Target.activateTarget` is the CDP-side "show this tab".
- `list_tabs()` includes `chrome://newtab/` by default; ask for `include_chrome=False` when you want only real pages.
- `chrome://omnibox-popup.top-chrome/` can appear as a fake page target; ignore it for user-facing tab lists.
- If a page has `w=0 h=0`, you may be attached to the wrong target or a non-window surface.
- For dynamic UIs, re-read element rects after opening dropdowns / modals before coordinate-clicking.
