# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Browser Harness is a minimal (~600 LOC) Python harness for controlling a real Chrome/Edge instance via the Chrome DevTools Protocol (CDP). It runs a small daemon that holds the CDP WebSocket and exposes a simple JSON-over-UNIX-socket protocol to user scripts.

## Common commands

### Install / run locally

This repo is meant to be installed as an editable tool so `browser-harness` is available globally:

```bash
git clone https://github.com/browser-use/browser-harness
cd browser-harness
uv tool install -e .
```

Run a script (helpers are pre-imported):

```bash
browser-harness <<'PY'
new_tab("https://docs.browser-use.com")
wait_for_load()
print(page_info())
PY
```

Attach/re-attach to the user’s running browser:

```bash
browser-harness --setup
```

Diagnostics:

```bash
browser-harness --doctor
```

Reload daemon (stop it so the next run starts fresh):

```bash
browser-harness --reload
```

Update to latest release (agents should pass `-y`):

```bash
browser-harness --update -y
```

### Dev (running from source)

Sync deps:

```bash
uv sync
```

Run from source via `uv`:

```bash
uv run browser-harness <<'PY'
print(page_info())
PY
```

## Architecture (big picture)

### Data flow

```text
Chrome/Edge (local)
  -> CDP WebSocket
  -> daemon.py (one per BU_NAME)
  -> /tmp/bu-<BU_NAME>.sock (JSON lines)
  -> helpers.py (CDP convenience functions)
  -> run.py CLI entrypoint (execs user Python)
```

Key properties:

- **One daemon per BU_NAME**: `BU_NAME` namespaces `/tmp/bu-<name>.sock`, `.pid`, `.log`.
- **Protocol is one JSON line per request/response** over the UNIX socket.
  - CDP call: `{method, params, session_id}`
  - Daemon control: `{meta: "..."}` (e.g. `drain_events`, `shutdown`, `set_session`).
- `run.py` is intentionally tiny: it prints the update banner, ensures the daemon is up, then `exec`s the provided Python with helpers already imported.

### Core files

- `helpers.py`: main user-facing API.
  - Navigation primitives (`new_tab`, `goto_url`, `wait_for_load`).
  - Input primitives (`click_at_xy`, `type_text`, `press_key`, `scroll`).
  - Debugging (`page_info`, `capture_screenshot`, `drain_events`).
  - Tab/session control (`list_tabs`, `switch_tab`, `ensure_real_tab`).
- `daemon.py`: long-lived process that:
  - Discovers local Chrome/Edge CDP endpoint via `DevToolsActivePort`.
  - Holds the CDP websocket (`cdp_use.client.CDPClient`).
  - Re-attaches if the session goes stale and keeps a bounded event buffer.
- `admin.py`: lifecycle + maintenance utilities.
  - `ensure_daemon()` starts/self-heals the daemon (and can open `chrome://inspect/#remote-debugging` when needed).
  - Update + doctor commands.

### Local browser

- **Local**: daemon searches known Chrome/Edge profile directories for `DevToolsActivePort`.

## Browser profile

Always use the **@ebaychina.com corporate Chrome profile** when opening the browser. This is the user's work profile and all browsing tasks should happen there.

- Only use the local browser. Never use remote browsers (`start_remote_daemon`, Browser Use cloud, `BROWSER_USE_API_KEY`).
- For Google services (Drive, Docs, Sheets), use `authuser=2` to ensure the eBay corporate account is active.
- Verify by checking for the eBay logo in the top-right corner or "0 bytes of 15 GB" storage indicator.
- Never use the personal Chrome profile for work-related browsing.

## Project conventions / constraints

These are explicit design constraints (see `SKILL.md`):

- Prefer compositor-level interactions (screenshots + coordinate clicks) before DOM selectors.
- Keep `run.py` small; no extra control layer or framework.
- Keep `helpers.py` short and focused on browser primitives; daemon/bootstrap/admin stays in `daemon.py`/`admin.py`.

## Where the “usage rules” live

- `install.md` — first-time install + attach workflow and troubleshooting.
- `SKILL.md` — day-to-day usage guidance (tab discipline, when to use screenshots vs DOM, contributing domain skills).
- `domain-skills/` and `interaction-skills/` are referenced by `SKILL.md` and `helpers.py` (`goto_url` returns suggested domain skills for the hostname).
