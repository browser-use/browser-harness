---
name: browser-harness
description: Direct browser control via CDP. Use when the user wants to automate, scrape, test, or interact with web pages. Connects to the user's already-running Chrome.
tags: [browser, automation, cdp, chrome, scraping]
---

# browser-harness — Hermes Agent Skill

> **Session start:** load this skill with `/skill browser-harness` or `hermes -s browser-harness`.

Direct browser control via CDP. For setup and connection troubleshooting, read `install.md` from the repo (or `hermes/install.md` if bundled). For task-specific helper code, see `agent-workspace/agent_helpers.py`.

Domain skills (`agent-workspace/domain-skills/`) are community-contributed per-site playbooks. Enable with `BH_DOMAIN_SKILLS=1`.

---

## Usage

```bash
# One-liner
browser-harness -c 'print(page_info())'

# Multi-line (single-quoted shell string)
browser-harness -c '
new_tab("https://docs.browser-use.com")
wait_for_load()
print(page_info())
'
```

- `browser-harness` is on `$PATH` after `pip install -e .` or `uv tool install -e .`
- **First navigation:** `new_tab(url)` — NOT `goto_url(url)` (which navigates the user's active tab)
- Helpers pre-imported; daemon auto-starts

### Remote browsers

Use remote for parallel sub-agents (each isolated browser via distinct `BU_NAME`) or headless deployment:

```bash
browser-harness -c 'start_remote_daemon("work")'
BU_NAME=work browser-harness -c 'new_tab("https://example.com"); print(page_info())'
```

Requires `BROWSER_USE_API_KEY`. See `install.md` for cloud browser setup.

---

## Core Helpers

| Helper | Purpose |
|---|---|
| `new_tab(url)` | Open a new tab (safe — doesn't clobber user's work) |
| `goto_url(url)` | Navigate the active tab (clobbers user's current page) |
| `capture_screenshot(path=None, full=False, max_dim=None)` | Take a screenshot, returns file path |
| `click_at_xy(x, y, button="left", clicks=1)` | Coordinate-level click (passes through iframes) |
| `fill_input(selector, text, clear_first=True)` | Fill a form field by CSS selector |
| `batch_fill([(selector, value), ...])` | Fill multiple fields at once |
| `js(expression)` | Run JavaScript, returns CDP `value` field |
| `page_info()` | Returns `{url, title, w, h, sx, sy, pw, ph}` |
| `list_tabs(include_chrome=True)` | List browser tabs |
| `switch_tab(target_id)` | Switch to a tab by `targetId` |
| `ensure_real_tab()` | Recover from stale/blank tab |
| `wait_for_load(timeout=15.0)` | Wait for `document.readyState == 'complete'` |
| `wait_for_network_idle(timeout=10.0, idle_ms=500)` | Wait for no network activity |
| `wait_for_element(selector, timeout=10.0)` | Wait for DOM element |
| `scroll(x, y, dy=-300, dx=0)` | Scroll by JS (`scrollBy`) — positional x,y first, kwargs dy/dx |
| `press_key(key, modifiers=0)` | Press a keyboard key |
| `type_text(text)` | Type into the focused element |
| `upload_file(selector, path)` | Upload a file to a file input |
| `http_get(url, headers=None, timeout=20.0)` | Pure HTTP GET (no browser) |
| `iframe_target(url_substr)` | Get targetId for an iframe by URL substring |

Custom helpers written during tasks go in `agent-workspace/agent_helpers.py` — check that file first before writing new ones.

---

## What Actually Works

- **Screenshots first** — `capture_screenshot()` to understand the page, find targets, decide the next action
- **Coordinate clicks** — `click_at_xy(x, y)` works through iframes, shadow DOM, and cross-origin at the compositor level
- **Bulk HTTP** — `http_get(url)` + `ThreadPoolExecutor` for static pages; no browser needed
- **Form filling** — prefer `fill_input()` over `type_text()` when you have a stable selector
- **After navigation** — always call `wait_for_load()` and optionally `wait_for_network_idle()`
- **Tab recovery** — `ensure_real_tab()` re-attaches to a real page when the current session is stale
- **Auth walls** — if redirected to login, **stop and ask the user** — never type credentials from screenshots
- **Verification** — screenshot after every meaningful visible action

---

## Design Constraints

- Coordinate clicks default (`Input.dispatchMouseEvent` — compositor-level)
- Connect to the user's running Chrome; don't launch your own browser
- `run.py` stays tiny — no argparse, subcommands, extra control layer
- No manager layer — no retries framework, session manager, daemon supervisor, config system, or logging framework

---

## Gotchas (Field-Tested)

- **Omnibox popups are fake page targets** — filter `chrome://omnibox-popup...` when listing tabs
- **CDP target order ≠ Chrome's tab-strip order** — `Target.activateTarget` only shows a known target
- **Default daemon sessions go stale** — run `ensure_real_tab()` to recover
- **Browser Use API is camelCase** — `cdpUrl`, `proxyCountryCode`, etc.
- **Remote `cdpUrl` is HTTPS, not ws** — resolve WebSocket URL via `/json/version`
- **Stop cloud browsers** with `PATCH /browsers/{id}` + `{"action": "stop"}`
- **`BU_NAME=local`** attaches to the user's running Chrome via CDP on `localhost:9222`
- **`BU_NAME=anything-else`** creates a fresh isolated browser (new `about:blank`)
- **Chrome 144+** — the first attach shows an in-browser Allow popup; the user must click Allow
- **`--update -y`** — when you see the update banner, run this yourself (don't ask the user)
- **Screenshot-first workflow** — fastest exploration strategy, not an afterthought

---

## Domain Skills (Opt-In)

Only applies when `BH_DOMAIN_SKILLS=1`. Set this in your shell or `config.yaml`:

```bash
export BH_DOMAIN_SKILLS=1
```

When enabled, `goto_url()` surfaces matching domain skill files from `agent-workspace/domain-skills/<host>/`. These are community-contributed per-site playbooks covering selectors, private APIs, and interaction quirks.

**Contribute back:** If you discover something non-obvious about a site, open a PR to `agent-workspace/domain-skills/<site>/`. Capture the durable shape (selectors, API endpoints, traps) — not pixel coordinates, task narration, or secrets.

---

## Common Environment Variables

| Var | Purpose |
|---|---|
| `BU_NAME` | Namespace for daemon IPC, pid, and log files (default: `local`) |
| `BU_CDP_WS` | Override local Chrome discovery for remote browsers |
| `BU_CDP_URL` | Specific DevTools HTTP endpoint (e.g. `http://127.0.0.1:9222`) |
| `BU_BROWSER_ID` | Browser Use cloud browser ID (for shutdown) |
| `BROWSER_USE_API_KEY` | API key for Browser Use cloud browsers |
| `BH_DOMAIN_SKILLS` | Set to `1` to enable community domain skills |
| `BH_RUNTIME_DIR` | Directory for socket/pid/port files (short path recommended on macOS) |
| `BH_TMP_DIR` | Directory for logs and screenshots |
