---
name: browser-harness
description: Direct browser control via CDP. Use when the user wants to automate, scrape, test, or interact with web pages. Connects to the user's already-running Chrome.
---

# browser-harness

Easiest and most powerful way to interact with the browser.

## Fast start

Read `helpers.py` first. For first-time install or reconnect/bootstrap, read `install.md` first. For normal use, stay in this file.

```bash
uv run bh <<'PY'
goto("https://browser-use.com")
wait_for_load()
print(page_info())
PY
```

The code is the doc.

Available interaction skills:
- `interaction-skills/connection.md` — startup sequence, tab visibility, omnibox popup fix

Available domain skills:
- `tiktok/upload.md`

## Tool call shape

```bash
browser-harness <<'PY'
# any python. helpers pre-imported. daemon auto-starts.
PY
```

`run.py` calls `ensure_daemon()` before `exec` — you never start/stop manually unless you want to.

### Remote browsers

Remote is optional. Use it for parallel agents, sub-agents, or deployment.

If `BROWSER_USE_API_KEY` is already present in `.env` or the environment, start a remote daemon with:

Run this from the repo root:

```bash
uv run python - <<'PY'
from admin import start_remote_daemon
print(start_remote_daemon("work"))
PY
BU_NAME=work uv run browser-harness <<'PY'
print(page_info())
PY
```

Leaving a remote daemon running bills until the session timeout.

Parallel agents should use distinct `BU_NAME`s and can share the same `helpers.py`; shared improvements are expected, and changes should stay general enough that other agents benefit rather than break.

## Search first

After cloning the repo, search `domain-skills/` first for the domain you are working on before inventing a new approach.

Only if you start struggling with a specific mechanic while navigating, look in `interaction-skills/` for helpers. The available interaction skills are:
- `cookies.md`
- `cross-origin-iframes.md`
- `dialogs.md`
- `downloads.md`
- `drag-and-drop.md`
- `dropdowns.md`
- `iframes.md`
- `network-requests.md`
- `print-as-pdf.md`
- `screenshots.md`
- `scrolling.md`
- `shadow-dom.md`
- `tabs.md`
- `uploads.md`
- `viewport.md`

Useful commands:

```bash
rg --files domain-skills
rg -n "tiktok|upload" domain-skills
```

## Post-task ritual (self-improving harness)

If needed, modify your own helper functions to fix tools that do not work well on a task, make repeated actions more efficient, or fix recurring browser-interaction problems.

If you spend a couple of corrective steps learning things you would want to know on the next similar task for the same domain, add or update a Markdown skill under `domain-skills/<domain>/` (create the directory if needed) with all reusable learnings that would speed up the next run, such as where to wait for network requests, which interaction patterns worked, and what traps matter. `domain-skills/` is shared across users, so include only sanitized, reusable guidance and never include sensitive data, secrets, or user-specific details. Then open a PR to this public repo.

## What actually works

- **Screenshots first**: use `screenshot()` to understand the current page quickly, find visible targets, and decide whether you need a click, a selector, or more navigation.
- **Clicking**: `screenshot()` → look → `click(x, y)` → `screenshot()` again to verify the result. Coordinate clicks pass through iframes/shadow/cross-origin at the compositor level.
- **Bulk HTTP**: `http_get(url)` + `ThreadPoolExecutor`. No browser for static pages (249 Netflix pages in 2.8s).
- **After goto**: `wait_for_load()`.
- **Wrong/stale tab**: `ensure_real_tab()`. Use it when the current tab is stale or internal; the daemon also auto-recovers from stale sessions on the next call.
- **Verification**: `print(page_info())` is the simplest "is this alive?" check, but screenshots are the default way to verify whether a visible action actually worked.
- **DOM reads**: use `js(...)` for inspection and extraction when the screenshot shows that coordinates are the wrong tool.
- **Iframe sites** (Azure blades, Salesforce): `click(x, y)` passes through; only drop to iframe DOM work when coordinate clicks are the wrong tool.
- **Auth wall**: redirected to login → stop and ask the user. Don't type credentials from screenshots.
- **Raw CDP** for anything helpers don't cover: `cdp("Domain.method", **params)`.

## Design constraints

- **Coordinate clicks default.** `Input.dispatchMouseEvent` goes through iframes/shadow/cross-origin at the compositor level.
- **Connect to the user's running Chrome.** Don't launch your own browser.
- **`cdp-use` is only for `CDPClient.send_raw`.** Prefer raw CDP strings over typed wrappers.
- **`run.py` stays tiny.** No argparse, subcommands, or extra control layer.
- **Helpers stay short.** Browser primitives in `helpers.py`; daemon/bootstrap and remote session admin live in `admin.py`.
- **Don't add a manager layer.** No retries framework, session manager, daemon supervisor, config system, or logging framework.

## Architecture

```text
Chrome / Browser Use cloud -> CDP WS -> daemon.py -> /tmp/bu-<NAME>.sock -> run.py
```

- Protocol is one JSON line each way.
- Requests are `{method, params, session_id}` for CDP or `{meta: ...}` for daemon control.
- Responses are `{result}` / `{error}` / `{events}` / `{session_id}`.
- `BU_NAME` namespaces socket, pid, and log files.
- `BU_CDP_WS` overrides local Chrome discovery for remote browsers.
- `BU_BROWSER_ID` + `BROWSER_USE_API_KEY` lets the daemon stop a Browser Use cloud browser on shutdown.

## Gotchas (field-tested)

- **Chrome 144+ `chrome://inspect/#remote-debugging` does NOT serve `/json/version`.** Read `DevToolsActivePort` instead.
- **Try attaching before asking for setup.** If `uv run browser-harness` already works, skip the remote-debugging instructions entirely.
- **The first connect may block on Chrome's Allow dialog.** If setup hangs, explicitly tell the user to click `Allow` in Chrome if it appears, then keep polling for up to 30 seconds instead of treating follow-on errors as a new failure.
- **`DevToolsActivePort` can exist before the port is actually listening.** Treat connection refused as "still enabling" and keep polling for up to 30 seconds.
- **Chrome may open the profile picker before any real tab exists.** If Chrome opens both a profile picker and the remote-debugging page, tell the user to choose their normal profile first, then tick the checkbox and click `Allow` if shown.
- **On macOS, if Chrome is already running, prefer AppleScript `open location` over `open -a ... URL`.** It reuses the current profile and avoids creating an extra startup path through the profile picker.
- **Omnibox popups are fake `page` targets.** Filter `chrome://omnibox-popup...` and other internals when you need a real tab.
- **CDP target order != Chrome's visible tab-strip order.** Use UI automation when the user means "the first/second tab I can see"; `Target.activateTarget` only shows a known target.
- **Default daemon sessions can go stale.** `ensure_real_tab()` re-attaches to a real page.
- **`no close frame received or sent` usually means a stale daemon / websocket.** Restart the daemon once with:
  `uv run python - <<'PY'`
  `from admin import restart_daemon`
  `restart_daemon()`
  `PY`
  before assuming setup is wrong.
- **Browser Use API is camelCase on the wire.** `cdpUrl`, `proxyCountryCode`, etc.
- **Remote `cdpUrl` is HTTPS, not ws.** Resolve the websocket URL via `/json/version`.
- **Stop cloud browsers with `PATCH /browsers/{id}` + `{\"action\":\"stop\"}`.**
- **After every meaningful action, re-screenshot before assuming it worked.** Use the image to verify changed state, open menus, navigation, visible errors, and whether the page is in the state you expected.
- **Use screenshots to drive exploration.** They are often the fastest way to find the next click target, notice hidden blockers, and decide if a selector is even worth writing.
- **Prefer compositor-level actions over framework hacks.** Try screenshots, coordinate clicks, and raw key input before adding DOM-specific workarounds.
- **If you need framework-specific DOM tricks, check `interaction-skills/` first.** That is where dropdown, dialog, iframe, shadow DOM, and form-specific guidance belongs.

## Interaction notes

- `interaction-skills/` holds reusable UI mechanics such as dialogs, tabs, dropdowns, iframes, and uploads.
- `domain-skills/` holds site-specific workflows and should be updated when you discover reusable patterns for a website.
