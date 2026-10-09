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

## Multiple Chrome profiles

Verified live on 2026-09-20; the attach options on 2026-09-21.

One Chrome process serves **all** open profiles, and `Target.getTargets` lists tabs from every one of them. Each target's `browserContextId` identifies its profile for that Chrome run. The ids change on every launch, so never persist them.

```python
targets = cdp("Target.getTargets")["targetInfos"]
pages = [t for t in targets if t["type"] == "page"]
by_profile = {}
for t in pages:
    by_profile.setdefault(t.get("browserContextId"), []).append(t)
```

What does not work:

- `Target.createTarget(browserContextId=<another profile's id>)` fails with "Failed to find browser context". Regular profiles are not CDP-creatable contexts.
- `Target.createTarget` without a context lands in whichever profile Chrome considers default. You cannot choose which one.

So to work inside a specific profile:

1. Attach to a tab the user **already has open** in that profile. There are two ways, and they behave differently:
   - `switch_tab(tab["targetId"])` attaches **and** makes that tab the daemon's active session, so every helper (`page_info()`, `js()`, `click_at_xy()`, `capture_screenshot()`, ...) follows it. It also prefixes the tab's title with the harness marker, so match titles with `in`, not `startswith`.
   - Raw `Target.attachToTarget` with `flatten=True` returns a session id and leaves the daemon's active tab alone. Helpers take **no** session id and keep acting on the previously attached tab, so after a raw attach only `cdp(method, session_id=sid, ...)` reaches the new tab. Use this when a watcher must read a tab without taking over the active one, and never mix it with helpers expecting them to follow.
   - For one-off reads, `js(expr, target_id=tab["targetId"])` does the attach, evaluate and detach for you and also leaves the active tab alone.
2. Identify the right profile by page title. For example, the Gmail title contains the account address.
3. Reuse that tab's `browserContextId` to filter the other tabs that belong to the same profile.

```python
tab = next(t for t in pages if "<account marker>" in t["title"])
same_profile = [t for t in pages if t.get("browserContextId") == tab.get("browserContextId")]

# Option A: take over. All helpers now act on this tab.
switch_tab(tab["targetId"])
print(page_info())

# Option B: read on the side. The active tab is untouched; helpers still point at the old tab.
title = js("document.title", target_id=tab["targetId"])      # one-off read
# or hold a session for several raw CDP calls:
sid = cdp("Target.attachToTarget", targetId=tab["targetId"], flatten=True)["sessionId"]
title = cdp("Runtime.evaluate", session_id=sid, expression="document.title", returnByValue=True)["result"]["value"]
cdp("Target.detachFromTarget", sessionId=sid)
```

### Always-on agents: use a dedicated Chrome

For an agent that runs continuously, skip profile juggling and give it its own Chrome:

```bash
"<chrome binary>" --user-data-dir=<own dir> --remote-debugging-port=<port>
BU_NAME=<name> BU_CDP_WS=<ws from /json/version> browser-harness <<'PY'
print(page_info())
PY
```

A non-default `--user-data-dir` opens the debugging port with no "Allow" prompt, and it keeps the agent out of the user's everyday browser.
