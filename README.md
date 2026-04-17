# harnesless

LLM-first browser control via CDP. No CLI, no wrappers, just Python and CDP.

## Setup

1. Install deps (uses `uv`):
   ```
   uv sync
   ```

2. Enable Chrome remote debugging: open `chrome://inspect/#remote-debugging`, check the box. Chrome now listens at `127.0.0.1:9222`.

3. (Optional) For remote browsers: `cp .env.example .env` and fill in `BROWSER_USE_API_KEY`.

4. Start the daemon:
   ```
   uv run daemon.py &
   ```

## Usage

```
uv run run.py <<'PY'
goto("https://example.com")
wait(1)
screenshot("/tmp/shot.png")
print(page_info())
PY
```

Parallel agents / remote browsers: `HARNESLESS_NAME=<n> uv run run.py`. See `SKILL.md`.

Read `SKILL.md` for the full LLM workflow. Read `AGENTS.md` if you're an agent working ON this codebase (extending helpers, debugging the daemon). Read `helpers.py` for every function — they're all ~5 lines each and you can edit any of them.

## Files

- `daemon.py` — holds the WebSocket, listens on `/tmp/harnesless.sock`
- `helpers.py` — ~250 lines of transparent helpers
- `run.py` — 3 lines: `from helpers import *; exec(stdin)`
- `SKILL.md` — how an agent *uses* harnesless to drive a browser
- `AGENTS.md` — how an agent *modifies* harnesless (code structure, extension points)

## Stop

```
uv run python -c "from helpers import kill_daemon; kill_daemon()"        # default daemon
uv run python -c "from helpers import kill_daemon; kill_daemon('work')"  # named daemon (also stops remote browser)
# or
pkill -f harnesless/daemon.py
```
