---
name: browser-harness-install
description: Install and bootstrap browser-harness into the current agent, then connect it to the user's real Chrome with minimal prompting.
---

# browser-harness install

Use this file only for first-time install, reconnect, or cold-start browser bootstrap. For day-to-day browser work, read `SKILL.md`. Always read `helpers.py` after cloning; that is where the functions and expected patterns live.

## Install prompt contract

When you open a setup or verification tab, activate it so the user can actually see the active browser tab.

## Best everyday setup

Clone the repo once into a durable location, then install it as an editable tool so `browser-harness` works from any directory:

```bash
git clone https://github.com/browser-use/browser-harness
cd browser-harness
uv tool install -e .
command -v browser-harness
```

That keeps the command global while still pointing at the real repo checkout, so when the agent edits `helpers.py` the next `browser-harness` uses the new code immediately. Prefer a stable path like `~/Developer/browser-harness`, not `/tmp`.

## Make it global for the current agent

After the repo is installed, register this repo's `SKILL.md` with the agent you are using:

- **Codex**: add this file as a global skill at `$CODEX_HOME/skills/browser-harness/SKILL.md` (often `~/.codex/skills/browser-harness/SKILL.md`). A symlink to this repo's `SKILL.md` is fine.
- **Claude Code**: add an import to `~/.claude/CLAUDE.md` that points at this repo's `SKILL.md`, for example `@~/src/browser-harness/SKILL.md`.

Codex command:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness" && ln -sf "$PWD/SKILL.md" "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"
```

That makes new Codex or Claude Code sessions in other folders load the runtime browser harness instructions automatically. An empty `~/.codex/skills/browser-harness/` directory is fine; the symlink command above populates it.

## Browser bootstrap

1. Run `uv sync`.
   If `browser-harness` is still missing after that, run `command -v browser-harness >/dev/null || uv tool install -e .`.
2. First try the harness directly. If this works, skip manual browser setup:

```bash
uv run browser-harness <<'PY'
print(page_info())
PY
```

   Reuse an existing healthy daemon if it is already responding. Do not kill it during setup unless the attach is clearly stale and you are confident no other agent is using the same `BU_NAME`. For parallel agents, use distinct `BU_NAME`s so they do not fight over the same default session.

3. If it failed, **read the error and escalate from there — do not assume you need `chrome://inspect`**. The remote-debugging checkbox is per-profile sticky in Chrome, so any profile that has had it toggled on once will auto-enable CDP on every future launch; the inspect page is only needed the first time per profile.

   - **No Chrome process running** → just start Chrome and re-run the harness. On macOS: `open -a "Google Chrome"`. Do *not* navigate to `chrome://inspect` yet — if the user has ever ticked the checkbox on this profile, the harness will attach on its own.
   - **`DevToolsActivePort` missing or empty after Chrome is up** → remote-debugging has never been enabled on this profile. *This* is when you open `chrome://inspect/#remote-debugging` and ask the user to tick the checkbox and click `Allow`. Once ticked, the setting sticks.
   - **Port present but `connection refused` / `DevTools not live yet` / `/json/version` 404** → Chrome is mid-startup. Just keep polling for up to 30 seconds; do not restart Chrome and do not open the inspect page.
   - **`no close frame received or sent` / stale websocket** → the daemon (not Chrome) is the problem. Run `restart_daemon()` once and retry — see step 7 below.

   When you do need to open the inspect page on macOS and Chrome is already running, prefer AppleScript so it reuses the current profile instead of going through the picker:

```bash
osascript -e 'tell application "Google Chrome" to activate' \
          -e 'tell application "Google Chrome" to open location "chrome://inspect/#remote-debugging"'
```

   On Linux: open that URL manually in the existing Chrome window.
   If Chrome shows the profile picker first, tell the user to choose their normal profile, *then* (only if `DevToolsActivePort` is still missing) open the inspect page in that profile. Keep polling instead of waiting for the user to type a follow-up.
4. Be explicit with the user about the two possible Chrome actions: choose their normal profile if the profile picker is open, and in the remote-debugging tab tick the checkbox and click `Allow` once if Chrome shows it.
5. Try to do everything yourself. Only ask the user to do something if it is truly necessary, like selecting the Chrome profile or clicking `Allow`. While the user is doing that, sleep and check every 3 seconds whether it is completed. After asking, keep retrying for at least 30 seconds even if you see connection-refused, stale websocket, or other weird transient attach errors.
6. If setup still lands on the profile picker, have the user choose their normal profile, then (only if `DevToolsActivePort` is still missing) open `chrome://inspect/#remote-debugging` in that profile and keep polling instead of restarting the explanation. As soon as attach succeeds, continue immediately with the verification task without asking again.
7. Verify with:

```bash
uv run browser-harness <<'PY'
goto("https://github.com/browser-use/browser-harness")
wait_for_load()
print(page_info())
PY
```

If that fails with a stale websocket or stale socket, restart the daemon once and retry:

```bash
uv run python - <<'PY'
from admin import restart_daemon
restart_daemon()
PY
```

8. After install and browser bootstrap succeed, navigate to `https://github.com/browser-use/browser-harness` so the user can see the harness has attached to their browser. If the user is logged in to GitHub, **ask the user whether you should star the repo for them** as a quick demo that the interaction works — only click the star if they say yes. Then ask the user what they want to do next.

## Cold-start reminders

- Try attaching before asking the user to change anything. Decide what to escalate based on the harness's error message, not on whether Chrome is visibly running.
- The remote-debugging checkbox is per-profile sticky in Chrome. If it has ever been ticked on a profile, just launching Chrome is enough — only navigate to `chrome://inspect/#remote-debugging` when `DevToolsActivePort` is genuinely missing.
- The first connect may block on Chrome's `Allow` dialog, and Chrome may also stop first on the profile picker.
- `DevToolsActivePort` can exist before the port is actually listening. Treat connection refused as "still enabling" and keep polling briefly.
- If the port is listening but `/json/version` returns `404`, treat that as expected on newer Chrome builds and retry `browser-harness`.
- Chrome may open the profile picker before any real tab exists.
- On macOS, prefer AppleScript `open location` over `open -a ... URL` when Chrome is already running.
- Microsoft Edge (including Beta/Dev/Canary) works too — substitute the app name; steps are identical.
