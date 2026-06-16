---
name: browser-harness
description: Direct browser control via CDP — automate, scrape, test, or interact with web pages by driving the user's already-running Chrome (or a Browser Use cloud browser). Use when the user wants to click, screenshot, fill forms, extract data, or navigate real web pages. Default to screenshots + coordinate clicks, not selector hunting. Requires the one-time `browser-harness` CLI install (see references/install.md).
---

# browser-harness

Direct browser control via CDP. You drive the user's real browser with Python helpers run through the `browser-harness` command.

## Prerequisite (one-time — NOT part of the AI workflow)

This skill is instructions only. It assumes the `browser-harness` command is already on `$PATH`. If `command -v browser-harness` fails, do the one-time install in [references/install.md](references/install.md) first, then continue. Installation and browser-connection setup are a prerequisite; once `browser-harness <<'PY' … PY` prints page info, never run install/connection steps again as part of normal work.

## Usage

```bash
browser-harness <<'PY'
new_tab("https://docs.browser-use.com")
wait_for_load()
print(page_info())
PY
```

- Invoke as `browser-harness` — it's on `$PATH` after install. No `cd`, no `uv run`.
- Use the heredoc form for every multi-line command. It prevents shell quote mangling inside Python strings and JavaScript snippets.
- First navigation is `new_tab(url)`, not `goto_url(url)` — goto runs in the user's active tab and clobbers their work.
- Helpers are pre-imported and the daemon auto-starts; you never start/stop it manually unless you want to.

## What actually works

- **Screenshots first.** `capture_screenshot()` to understand the page, find visible targets, and decide whether you need a click, a selector, or more navigation.
- **Clicking.** `capture_screenshot()` → read the pixel off the image → `click_at_xy(x, y)` → `capture_screenshot()` to verify. Suppress the Playwright-habit reflex of "locate first, then click" — no `getBoundingClientRect`, no selector hunt. Drop to DOM only when the target has no visible geometry. Hit-testing happens in Chrome's browser process, so clicks pass through iframes / shadow DOM / cross-origin without extra work.
- **Bulk HTTP.** `http_get(url)` + `ThreadPoolExecutor`. No browser needed for static pages.
- **After goto:** `wait_for_load()`.
- **Wrong/stale tab:** `ensure_real_tab()`.
- **Verification:** `print(page_info())` is the simplest "is this alive?" check; screenshots are the default way to verify whether a visible action worked.
- **DOM reads:** use `js(...)` for inspection/extraction when a screenshot shows coordinates are the wrong tool.
- **Auth wall:** redirected to login → stop and ask the user. Don't type credentials from screenshots.
- **Raw CDP** for anything helpers don't cover: `cdp("Domain.method", params)`.

After every meaningful action, re-screenshot before assuming it worked.

## Remote / cloud browsers

Use remote for parallel sub-agents (each gets an isolated browser via a distinct `BU_NAME`) or on a headless server. `BROWSER_USE_API_KEY` must be set.

```bash
browser-harness <<'PY'
start_remote_daemon("work")   # clean cloud browser; profileName=/profileId= to reuse a logged-in profile
PY

BU_NAME=work browser-harness <<'PY'
new_tab("https://example.com")
print(page_info())
PY
```

`start_remote_daemon` prints a `liveUrl` so the user can watch. Running remote daemons bill until timeout.

## Interaction skills (progressive disclosure)

If you struggle with a specific UI mechanic, read the matching file under `${CLAUDE_PLUGIN_ROOT}/interaction-skills/` before inventing an approach. Available: browser-wall, connection, cookies, cross-origin-iframes, dialogs, downloads, drag-and-drop, dropdowns, iframes, network-requests, print-as-pdf, profile-sync, screenshots, scrolling, shadow-dom, tabs, uploads, viewport.

## Task-specific edits

For task-specific helper additions, edit `${CLAUDE_PLUGIN_ROOT}/agent-workspace/agent_helpers.py`. Keep core helpers short.

## Domain skills (opt-in)

Community per-site playbooks live in `${CLAUDE_PLUGIN_ROOT}/agent-workspace/domain-skills/<host>/` and are **off by default**. Set `BH_DOMAIN_SKILLS=1` to enable them; when enabled and the task is site-specific, read every file in the matching `<site>/` directory before inventing an approach.

## Design constraints

- Coordinate clicks default. `Input.dispatchMouseEvent` goes through iframes/shadow/cross-origin at the compositor level.
- Connect to the user's running Chrome. Don't launch your own browser.
- Prefer compositor-level actions (screenshots, coordinate clicks, raw key input) over framework/DOM hacks. Reach for `interaction-skills/` only when those are the wrong tool.
