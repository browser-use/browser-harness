# browser-harness CLI — one-time install prerequisite

This is a **one-time prerequisite**, not part of the regular AI workflow. Do it once; after `browser-harness` prints page info, never repeat install/connection steps during normal browser work.

## Install the command

```bash
uv tool install --python 3.12 --upgrade --force browser-harness
command -v browser-harness   # should print a path
```

`--python 3.12` prevents uv from selecting old releases that support older Python versions. `--upgrade --force` replaces any previous `browser-harness` tool install with the latest stable release. It does not uninstall unrelated commands such as `browser-use-Browser` or `browser-use-Terminal`.

For browser-harness development, clone the repo into a durable path and run `uv tool install -e .` from the checkout.

## Register the skill

Install/register a skill named `browser-harness` using this command for the body:

```bash
browser-harness skill
```

For Codex:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness"
browser-harness skill > "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"
```

If an old user-installed `browser` or `browser-use` skill is being picked instead, remove that stale skill directory manually. Never edit bundled/vendor plugin caches.

## Connect to a browser

`browser-harness` attaches to a Chrome you already have running, or to a Browser Use cloud browser. Quick check:

```bash
browser-harness <<'PY'
print(page_info())
PY
```

If that prints page info, you're done. If not, run `browser-harness --doctor` and follow the connection cases. The two connection methods:

- **Way 1 (real browser):** open Chrome normally, then open `chrome://inspect/#remote-debugging` and tick "Allow remote debugging for this browser instance". On Chrome 144+, click Allow on the first-attach popup. Inherits your logins/extensions — best when the agent acts in your everyday browser.
- **Way 2 (isolated profile, no popups):** launch Chrome with `--remote-debugging-port=9222 --user-data-dir=<non-default path>`, then set `BU_CDP_URL=http://127.0.0.1:9222`. Best for unattended automation.

If the quick path fails after `--doctor`, inspect `src/browser_harness/admin.py`, `src/browser_harness/daemon.py`, and `src/browser_harness/_ipc.py`.

## Keeping current

`browser-harness` prints an update banner when a newer PyPI release exists; run `browser-harness --update -y` when you decide to upgrade. `browser-harness --doctor` also checks the latest version. Telemetry is anonymous and opt-out with `browser-harness telemetry disable`.

State lives under `${XDG_CONFIG_HOME:-~/.config}/browser-harness` by default: auth, agent workspace, runtime sockets, logs, screenshots, and temp files. Override with `BH_HOME` or `BROWSER_HARNESS_HOME`.
