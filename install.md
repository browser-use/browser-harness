---
name: browser-install
description: Install browser-harness and connect it to a browser fast.
---

# browser-harness install

Use once. For browser work, read `SKILL.md`.

## Fast Path

```bash
uv tool install browser-harness
for root in "${CODEX_HOME:-$HOME/.codex}/skills" "$HOME/.agents/skills"; do
  rm -rf "$root/browser-harness" "$root/browser" "$root/browser-use"
done
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness"
browser-harness skill > "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"
browser-harness <<'PY'
print(page_info())
PY
```

If `page_info()` prints, stop. Setup is done.

For Claude Code or other agents: install `browser-harness`, register a skill named `browser-harness`, use `browser-harness skill` as the body, and use this trigger:

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

Only remove stale user-installed browser skills. Do not edit bundled/vendor plugin caches.

## If Chrome Blocks It

In Chrome:

1. Open `chrome://inspect/#remote-debugging`.
2. Tick "Allow remote debugging for this browser instance".
3. Click Allow on the popup if it appears.
4. Retry `page_info()`.

The checkbox and popup require the user.

## Cloud Browsers

Cloud is optional. Local Chrome does not need a Browser Use API key.

```bash
browser-harness auth login
browser-harness <<'PY'
start_remote_daemon("work")
PY
```

Then use it by name:

```bash
BU_NAME=work browser-harness <<'PY'
print(page_info())
PY
```

## If Still Broken

```bash
browser-harness --doctor
```

Use the output:

- `chrome running` FAIL: ask the user to open Chrome, or use isolated/cloud browser.
- `daemon alive` FAIL: Chrome remote debugging permission is missing, Chrome is closed, or the CDP endpoint is not reachable.
- update available: run `browser-harness --update -y` when you decide to upgrade.

If this still fails, inspect `src/browser_harness/admin.py`, `src/browser_harness/daemon.py`, and `src/browser_harness/_ipc.py`.

Useful:

```bash
browser-harness --update -y
browser-harness telemetry disable
```

State lives under `${XDG_CONFIG_HOME:-~/.config}/browser-harness` by default: auth, telemetry id, agent workspace, runtime sockets, logs, screenshots, and temp files. Override with `BH_HOME` or `BROWSER_HARNESS_HOME`.
