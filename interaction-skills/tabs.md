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

## Background tab in a specific Chrome profile

Each Chrome profile is a separate CDP `browserContextId` with its own cookies
and logins. `new_tab()` and a plain `Target.createTarget` open the tab in the
default context, which may have no session for the site.

1. Find a tab that already belongs to the profile you need.
2. Read its `browserContextId`.
3. Create the new tab in that context with `background=True`.
4. Attach with `switch_tab()`. Do not call `activate_tab()`.

```python
tabs = list_tabs(include_chrome=False)
ref = next(t for t in tabs if "calendar.google.com" in t["url"])  # any tab of that profile
ctx = cdp("Target.getTargetInfo", targetId=ref["targetId"])["targetInfo"]["browserContextId"]
tid = cdp("Target.createTarget", url="about:blank", background=True,
          browserContextId=ctx)["targetId"]
switch_tab(tid)
goto_url("https://example.com/")
cdp("Emulation.setFocusEmulationEnabled", enabled=True)  # modals/inputs that wait for focus
```

Close the tab with `close_tab(tid)` when you finish.

Traps:

- CDP sees the tabs of a profile only while that profile has a window open.
  If no tab of the profile shows up in `Target.getTargets`, ask the user to open one window of it.
- `Target.getTargets` also returns `browserContextId`, so you can group tabs per profile without extra calls.
- Do not launch the Chrome binary with `--profile-directory=...` to reach a profile.
  When Chrome already runs, `open -g -a "Google Chrome" --args --profile-directory=...`
  does nothing, and a direct binary launch with a URL opens a focused window.
- Google sites accept `/u/<N>/` or `?authuser=<N>` to pick one of several accounts
  in the same profile. `N` follows the sign-in order, so confirm the account email on the page.

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
