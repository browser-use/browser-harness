---
name: browser-harness-install
description: Install and bootstrap browser-harness into the current agent, then connect it to the user's real Chrome with minimal prompting.
allowed-tools: Bash, Read, Edit, Write
---

# browser-harness install

Use this file only for first-time install, reconnect, or cold-start browser bootstrap. For day-to-day browser work, read `SKILL.md`. Always read `helpers.py` after cloning; that is where the functions and expected patterns live.

## Install prompt contract

When the user asks to set up this repo, read this file first, then `SKILL.md`.

When you open a setup or verification tab, bring it to the foreground so the user can actually see the active browser tab.

## Best everyday setup

Clone the repo once, then install it as an editable tool so `bh` works from any directory:

```bash
git clone https://github.com/browser-use/harnessless
cd harnessless
uv tool install -e .
command -v bh
```

That keeps the command global while still pointing at the real repo checkout, so when the agent edits `helpers.py` the next `bh` run uses the new code immediately. `browser-harness` is the readable alias for the same command.

## Make it global for the current agent

After the repo is installed, register this repo's `SKILL.md` with the agent you are using:

- **Codex**: add this file as a global skill at `$CODEX_HOME/skills/browser-harness/SKILL.md` (often `~/.codex/skills/browser-harness/SKILL.md`). A symlink to this repo's `SKILL.md` is fine.
- **Claude Code**: add an import to `~/.claude/CLAUDE.md` that points at this repo's `SKILL.md`, for example `@~/src/harnessless/SKILL.md`.

That makes new Codex or Claude Code sessions in other folders load the runtime browser harness instructions automatically.

## Browser bootstrap

1. Run `uv sync`.
2. First try the harness directly. If this works, skip manual browser setup:

```bash
uv run bh <<'PY'
ensure_real_tab()
print(page_info())
PY
```

3. If that fails and Chrome is already running, open `chrome://inspect/#remote-debugging` in the existing Chrome profile instead of launching a fresh Chrome process.
   On macOS:

```bash
osascript -e 'tell application "Google Chrome" to activate' \
          -e 'tell application "Google Chrome" to open location "chrome://inspect/#remote-debugging"'
```

   On Linux: use the already-running Chrome window and open that URL manually.
4. If Chrome is not running, start Chrome first and let the user choose their normal profile if Chrome opens the profile picker. Only after that, open `chrome://inspect/#remote-debugging`.
   On macOS: `open -a "Google Chrome"`
5. Tell the user to tick the remote-debugging checkbox. If Chrome shows `Allow`, tell the user to click it once.
6. Do not ask the user to say "continue". Poll every few seconds and retry the same connect attempt once the permission flow finishes.
7. If setup still lands on the profile picker, have the user choose their normal profile, then open `chrome://inspect/#remote-debugging` in that profile and keep polling instead of restarting the explanation.
8. Verify with:

```bash
uv run bh <<'PY'
ensure_real_tab()
if not current_tab()["url"] or current_tab()["url"].startswith(INTERNAL):
    new_tab("about:blank")
print(page_info())
PY
```

If that fails with a stale websocket or stale socket, restart the daemon once and retry:

```bash
uv run python - <<'PY'
from helpers import kill_daemon
kill_daemon()
PY
```

## Cold-start reminders

- Try attaching before asking the user to change anything.
- The first connect may block on Chrome's `Allow` dialog.
- Chrome may open the profile picker before any real tab exists.
- On macOS, prefer AppleScript `open location` over `open -a ... URL` when Chrome is already running.
