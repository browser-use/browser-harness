---
name: browser-install
description: Install browser-harness and connect it to a browser fast.
---

# browser-harness install

Use once. For browser work, read `SKILL.md`.

## Fast Path

```bash
uv tool install --python 3.12 --upgrade --force browser-harness
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness"
browser-harness skill > "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"
browser-harness <<'PY'
print(page_info())
PY
```

If `page_info()` prints, stop. Setup is done.

`--python 3.12` prevents uv from selecting old releases that support older Python versions. `--upgrade --force` replaces any previous `browser-harness` tool install with the latest stable release. It does not uninstall unrelated commands such as `browser-use-Browser` or `browser-use-Terminal`.

For Claude Code or other agents: install `browser-harness`, register a skill named `browser-harness`, use `browser-harness skill` as the body, and use this trigger:

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

If an old user-installed `browser` or `browser-use` skill is being picked instead, remove that stale skill directory manually. Do not edit bundled/vendor plugin caches.

## If Chrome Blocks It

In Chrome:

1. Open `chrome://inspect/#remote-debugging`.
2. Tick "Allow remote debugging for this browser instance".
3. Click Allow on the popup if it appears.
4. Retry `page_info()`.

The checkbox and popup require the user.

## Cloud Browsers

Cloud is optional. Local Chrome does not need a Browser Use API key.

Use any short made-up name; `r7k2` below is just a placeholder.

```bash
browser-harness auth login
browser-harness <<'PY'
start_remote_daemon("r7k2")
PY
```

Then use it by name:

```bash
BU_NAME=r7k2 browser-harness <<'PY'
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
