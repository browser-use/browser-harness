# browser-harness CLI — one-time install prerequisite

This is a **one-time prerequisite**, not part of the regular AI workflow. Do it once; after `browser-harness` prints page info, never repeat install/connection steps during normal browser work.

## Install the command

```bash
git clone https://github.com/browser-use/browser-harness
cd browser-harness
uv tool install -e .
command -v browser-harness   # should print a path
```

Editable (`-e`) keeps the command global while pointing at the real checkout, so edits to `agent-workspace/agent_helpers.py` take effect on the next call. Prefer a durable path (e.g. `~/Developer/browser-harness`), not `/tmp`.

## Connect to a browser

`browser-harness` attaches to a Chrome you already have running, or to a Browser Use cloud browser. Quick check:

```bash
browser-harness <<'PY'
print(page_info())
PY
```

If that prints page info, you're done. If not, run `browser-harness --doctor` and follow the connection cases. The two connection methods:

- **Way 1 (real profile):** in your Chrome, open `chrome://inspect/#remote-debugging` and tick "Allow remote debugging for this browser instance" (sticky, per-profile). On Chrome 144+, click Allow on the first-attach popup. Inherits your logins/extensions — best when the agent acts in your everyday browser.
- **Way 2 (isolated profile, no popups):** launch Chrome with `--remote-debugging-port=9222 --user-data-dir=<non-default path>`, then set `BU_CDP_URL=http://127.0.0.1:9222`. Best for unattended automation.

The canonical, fully-detailed connection reference and troubleshooting live in the repo root's `install.md`. Read it if the quick path above fails.

## Keeping current

`browser-harness` prints an update banner when a newer release exists; run `browser-harness --update -y` to pull it.
