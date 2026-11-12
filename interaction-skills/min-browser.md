# Min browser (Electron-based browsers generally)

Driving [Min](https://minbrowser.org/) (and most Electron-shell browsers) with the harness via `BU_CDP_WS`.

## Enabling CDP

- Min has no persistent remote-debugging setting — it must be **launched** with the flag:
  `/Applications/Min.app/Contents/MacOS/Min --remote-debugging-port=9224 &`
- Min holds a **single-instance lock**: if it's already running, launching with the flag just pings the existing instance and CDP never comes up. Kill first, then relaunch.
- Min **ignores AppleScript `quit`** (`osascript -e 'quit app "Min"'` is a no-op). Use `pkill -f "Min.app/Contents/MacOS/Min"`, poll until the process is gone, then relaunch. Tabs restore automatically.
- Resolve the ws URL from `http://127.0.0.1:9224/json/version` → `webSocketDebuggerUrl`, then:
  `BU_NAME=min BU_CDP_WS=<ws url> browser-harness <<'PY' ...`

## Target landscape (the trap)

`Target.getTargets` shows several `page` targets that are NOT normal tabs:

- `min://app/index.html` — Min's own UI (the browser chrome). Don't drive it.
- `file://.../Min.app/.../placesService.html` — internal history service.
- An **empty-URL `page` target** — a hidden background webContents. You *can* attach and navigate it and JS eval works, but `page_info()` reports a **0×0 viewport**, `Page.captureScreenshot` times out, and coordinate clicks are meaningless. Easy to mistake for a real tab.

## Opening real tabs

- `new_tab()` / `Target.createTarget` is unreliable in Electron shells — it may create a hidden webContents instead of a visible tab.
- Open pages as visible tabs from the shell instead: `open -a Min "<url>"` (works for `file://` too).
- Then pick the target where `type == "page"`, the URL matches what you opened, and the URL is neither `min://` nor under `/Applications/Min.app/`. `switch_tab()` to it.
- **Sanity-check `page_info()` shows a non-zero viewport before clicking or screenshotting** — that's the reliable "this is a visible tab" test.

Everything else (js, click_at_xy, capture_screenshot, wait_for_load) works normally once you're attached to a visible tab.
