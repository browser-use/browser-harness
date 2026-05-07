---
name: browser
description: Direct browser control via CDP. Use when the user wants to automate, scrape, test, or interact with web pages. Connects to the user's already-running Chrome.
---

# browser-harness

Direct browser control via CDP. For task-specific edits, use `agent-workspace/agent_helpers.py`. For setup, install, or connection problems, read install.md.

Domain skills (community-contributed per-site playbooks under `agent-workspace/domain-skills/`) are off by default. Set `BH_DOMAIN_SKILLS=1` to enable them; see the bottom section.

**If `BH_DOMAIN_SKILLS=1` and the task is site-specific, read every file in the matching `agent-workspace/domain-skills/<site>/` directory before inventing an approach.**

## Usage

```bash
browser-harness -c '
new_tab("https://docs.browser-use.com")
wait_for_load()
print(page_info())
'
```

- Invoke as browser-harness — it's on $PATH. No cd, no uv run.
- First navigation is new_tab(url), not goto_url(url) — goto runs in the user's active tab and clobbers their work.

## Tool call shape

```bash
browser-harness -c '
# any python. helpers pre-imported. daemon auto-starts.
'
```

run.py calls ensure_daemon() before exec — you never start/stop manually unless you want to.

### Remote browsers

Use remote for parallel sub-agents (each gets its own isolated browser via a distinct BU_NAME) or on a headless server. BROWSER_USE_API_KEY must be set. start_remote_daemon, list_cloud_profiles, list_local_profiles, sync_local_profile are pre-imported.

```bash
browser-harness -c '
start_remote_daemon("work")                               # default — clean browser, no profile
# start_remote_daemon("work", profileName="my-work")      # reuse a cloud profile (already logged in)
# start_remote_daemon("work", profileId="<uuid>")         # same, but by UUID
# start_remote_daemon("work", proxyCountryCode="de", timeout=120)   # DE proxy, 2-hour timeout
# start_remote_daemon("work", proxyCountryCode=None)      # disable the Browser Use proxy
'

BU_NAME=work browser-harness -c '
new_tab("https://example.com")
print(page_info())
'
```

start_remote_daemon prints liveUrl and auto-opens it in the local browser (if a GUI is detected) so the user can watch along. Headless servers print only — share the URL with the user. The daemon PATCHes the cloud browser to stop on shutdown, which persists profile state. Running remote daemons bill until timeout.

Profiles (cookies-only login state) live in interaction-skills/profile-sync.md — covers list_cloud_profiles(), the chat-driven "which profile?" pattern, and sync_local_profile() for uploading a local Chrome profile.

## Interaction skills

If you start struggling with a specific mechanic while navigating, look in interaction-skills/ for helpers. They cover reusable UI mechanics like dialogs, tabs, dropdowns, iframes, and uploads. The available interaction skills are:
- connection.md
- cookies.md
- cross-origin-iframes.md
- dialogs.md
- downloads.md
- drag-and-drop.md
- dropdowns.md
- iframes.md
- network-requests.md
- print-as-pdf.md
- profile-sync.md
- screenshots.md
- scrolling.md
- shadow-dom.md
- tabs.md
- uploads.md
- viewport.md

## What actually works

- Screenshots first: use capture_screenshot() to understand the current page quickly, find visible targets, and decide whether you need a click, a selector, or more navigation.
- Clicking: capture_screenshot() → read the pixel off the image → click_at_xy(x, y) → capture_screenshot() to verify. Suppress the Playwright-habit reflex of "locate first, then click" — no getBoundingClientRect, no selector hunt. Drop to DOM only when the target has no visible geometry (hidden input, 0×0 node). Hit-testing happens in Chrome's browser process, so clicks go through iframes / shadow DOM / cross-origin without extra work.
- Bulk HTTP: http_get(url) + ThreadPoolExecutor. No browser for static pages (249 Netflix pages in 2.8s).
- After goto: wait_for_load().
- Wrong/stale tab: ensure_real_tab(). Use it when the current tab is stale or internal; the daemon also auto-recovers from stale sessions on the next call.
- Verification: print(page_info()) is the simplest "is this alive?" check, but screenshots are the default way to verify whether a visible action actually worked.
- DOM reads: use js(...) for inspection and extraction when the screenshot shows that coordinates are the wrong tool.
- Iframe sites (Azure blades, Salesforce): click_at_xy(x, y) passes through; only drop to iframe DOM work when coordinate clicks are the wrong tool.
- Auth wall: redirected to login → stop and ask the user. Don't type credentials from screenshots.
- Raw CDP for anything helpers don't cover: cdp("Domain.method", params).

## Design constraints

- Coordinate clicks default. Input.dispatchMouseEvent goes through iframes/shadow/cross-origin at the compositor level.
- Connect to the user's running Chrome. Don't launch your own browser.
- cdp-use is only for CDPClient.send_raw. Prefer raw CDP strings over typed wrappers.
- run.py stays tiny. No argparse, subcommands, or extra control layer.
- Core helpers stay short. Put task-specific helper additions in `agent-workspace/agent_helpers.py`; daemon/bootstrap and remote session admin live in the core package.
- Don't add a manager layer. No retries framework, session manager, daemon supervisor, config system, or logging framework.

## Gotchas (field-tested)

- Omnibox popups are fake page targets. Filter chrome://omnibox-popup... and other internals when you need a real tab.
- CDP target order != Chrome's visible tab-strip order. Use UI automation when the user means "the first/second tab I can see"; Target.activateTarget only shows a known target.
- Default daemon sessions can go stale. ensure_real_tab() re-attaches to a real page.
- Browser Use API is camelCase on the wire. cdpUrl, proxyCountryCode, etc.
- Remote cdpUrl is HTTPS, not ws. Resolve the websocket URL via /json/version.
- Stop cloud browsers with PATCH /browsers/{id} + {"action":"stop"}.
- After every meaningful action, re-screenshot before assuming it worked. Use the image to verify changed state, open menus, navigation, visible errors, and whether the page is in the state you expected.
- Use screenshots to drive exploration. They are often the fastest way to find the next click target, notice hidden blockers, and decide if a selector is even worth writing.
- Prefer compositor-level actions over framework hacks. Try screenshots, coordinate clicks, and raw key input before adding DOM-specific workarounds.
- If you need framework-specific DOM tricks, check interaction-skills/ first. That is where dropdown, dialog, iframe, shadow DOM, and form-specific guidance belongs.

## Domain skills (opt-in)

Only applies when `BH_DOMAIN_SKILLS=1`. Otherwise ignore — `agent-workspace/domain-skills/` is dormant and `goto_url` won't surface skill files.

When enabled, search `agent-workspace/domain-skills/<host>/` before inventing an approach. `goto_url` returns up to 10 skill filenames for the navigated host.

If you learn anything non-obvious — a private API, stable selector, framework quirk, URL pattern, hidden wait, or site-specific trap — open a PR to `agent-workspace/domain-skills/<site>/`. Capture the durable shape of the site (the map, not the diary). Don't write pixel coordinates (break on layout), task narration, or secrets — the directory is public.
