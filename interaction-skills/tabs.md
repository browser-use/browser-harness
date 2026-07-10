# Tabs

Use **CDP for control**, **UI automation for user-visible order**.

## Pure CDP (portable: macOS / Linux / Windows)

```python
tabs = list_tabs()                    # includes chrome:// pages too
real_tabs = list_tabs(include_chrome=False)
tid = new_tab("https://example.com")  # create + attach (activates the tab)
tid = new_tab("https://example.com", background=True)  # create + attach WITHOUT stealing the user's focus
switch_tab(tid)                       # activate + attach
attach_tab(tid)                       # attach only — never activates
cdp("Target.activateTarget", targetId=tid)  # show it in Chrome
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

- `switch_tab()` is **not enough** if the user expects Chrome to visibly change.
- `Target.activateTarget` is the CDP-side "show this tab".
- Driving a user's **live** browser? Use `new_tab(url, background=True)` / `attach_tab()` so automation doesn't yank them out of the tab they're working in.
- `list_tabs()` includes `chrome://newtab/` by default; ask for `include_chrome=False` when you want only real pages.
- `chrome://omnibox-popup.top-chrome/` can appear as a fake page target; ignore it for user-facing tab lists.
- If a page has `w=0 h=0`, you may be attached to the wrong target or a non-window surface.
- For dynamic UIs, re-read element rects after opening dropdowns / modals before coordinate-clicking.
