---
name: harnesless
description: Direct browser control via CDP. Use when the user wants to automate, scrape, test, or interact with web pages. Connects to the user's already-running Chrome.
allowed-tools: Bash, Read, Edit, Write
---

# Harnesless

Project: `/Users/greg/Documents/browser-use/hackathons/harnesless/`

**Read `helpers.py` first.** ~120 lines, one tool call. The code is the doc.

**Fix as you go.** If a helper's missing or broken, edit `helpers.py` right now. Same for `daemon.py` if startup's flaky (then `pkill -f harnesless/daemon.py && uv run daemon.py &`).

## Tool call shape

```bash
cd /Users/greg/Documents/browser-use/hackathons/harnesless && uv run run.py <<'PY'
# any python. helpers pre-imported.
PY
```

## Setup if daemon not running

`uv sync` → `uv run daemon.py &`. User must enable `chrome://inspect/#remote-debugging` once. Errors in `/tmp/harnesless.log`.

## What actually works

- **Scraping**: `js("...custom query...")`. Bespoke selectors beat generic DOM helpers every time.
- **Clicking**: `screenshot()` → look → `click(x, y)`. Passes through iframes/shadow/cross-origin.
- **Bulk HTTP**: `http_get(url)` + `ThreadPoolExecutor`. No browser needed for static pages (249 Netflix pages in 2.8s).
- **After goto**: `wait_for_load()` not `wait(5)`.
- **Wrong tab**: `ensure_real_tab()`.
- **Auth wall**: if redirected to login, stop and ask user — don't try to type credentials.
- **Raw CDP** for anything helpers don't cover: `cdp("Domain.method", **params)`.
