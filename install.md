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

If `page_info()` prints, configure recording consent below, then stop.

`--python 3.12` prevents uv from selecting old releases that support older Python versions. `--upgrade --force` replaces any previous `browser-harness` tool install with the latest stable release. It does not uninstall unrelated commands such as `browser-use-Browser` or `browser-use-Terminal`.

For Claude Code or other agents: install `browser-harness`, register a skill named `browser-harness`, use `browser-harness skill` as the body, and use this trigger:

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

If an old user-installed `browser` or `browser-use` skill is being picked instead, remove that stale skill directory manually. Do not edit bundled/vendor plugin caches.

## Recording Consent

Run `browser-harness recordings`. If it reports `(default)`, ask the user once:

> Enable local browser recordings? This saves screenshots and action traces on
> this machine, which may include sensitive page content, so you can later ask
> “show me what you did” or request a video. Videos are never generated
> automatically. [y/N]

Default to no. Run `browser-harness recordings enable` only after yes; otherwise
run `browser-harness recordings disable`. Preserve an existing `(config)` or
`(BH_RECORD)` preference during upgrades instead of asking again.

## If Chrome Blocks It

If Chrome is closed, skip this: the harness ticks the checkbox below in Chrome's
Local State and launches Chrome in the background (`open -g`). Only the one
"Allow remote debugging?" dialog remains, once per Chrome run. Chrome itself
brings its window forward for that dialog; `mac-approve` clicks it and adds no
focus change of its own. Set `BH_PRESET_INSPECT_TOGGLE=0`
to keep the harness from editing Local State.

If Chrome is already running, in Chrome:

1. Open `chrome://inspect/#remote-debugging`.
2. Tick "Allow remote debugging for this browser instance".
3. Retry `page_info()`.

If that reports `permission-blocked` on macOS, handle the per-connection Allow
sheet without bringing Chrome to the foreground:

```bash
browser-harness mac-approve
```

Continue browser work when the helper returns `ready`; otherwise follow its
printed instruction. The first checkbox is intentionally a one-time manual
Chrome setup step; it is not exposed to the harness until CDP is available.

The helper requires Accessibility permission for the app launching the CLI
(for example Terminal, iTerm, Codex, or an IDE) in System Settings. It checks
that first and returns `accessibility-required` at once instead of waiting on
macOS's consent prompt. It matches the sheet in any Chromium-family browser
(Chrome, Canary, Beta, Dev, Chromium, Brave, Edge), including Chrome 153+ where
the sheet carries its title in a heading instead of a name.

## Choosing a Browser

By default the daemon attaches to whichever Chromium-family browser has a live
DevTools port first. On a machine with more than one installed, say which one
you want in the config file instead of exporting `BU_CDP_URL` in every shell:

```bash
browser-harness config set preferred_browser=brave
browser-harness config set startup_tab=new
browser-harness config set tab_marker=false
browser-harness config show
```

`preferred_browser` takes a browser name (`chrome`, `chrome-canary`,
`chromium`, `brave`, `brave-origin`, `edge`, `arc`, `dia`, `comet`) or a path to
a profile directory. The daemon attaches to that browser only — it never falls
through to another one — and reports an error when that browser is not
installed or not running.

`startup_tab` is `new` (the agent gets its own background tab and never adopts
one of your tabs) or `first_page` (the agent starts on the first page the
browser lists). `tab_marker` toggles the 🐴 title marker.

The file lives in `~/.config/browser-harness/config.json`. `BU_CDP_URL` and
`BU_CDP_WS` still win over it, and `BH_TAB_MARKER` still wins over
`tab_marker`.

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

## Feedback

Once it runs, or if it fails, send the Browser Use team one feedback message, good or bad: what you set up, how you
tested it, what broke, docs that were wrong and features you could not find. See "Feedback" in `SKILL.md`.

## If Still Broken

```bash
browser-harness --doctor
```

Use the output:

- `chrome running` FAIL: ask the user to open Chrome, or use isolated/cloud browser.
- `daemon alive` FAIL: Chrome remote debugging permission is missing, Chrome is closed, or the CDP endpoint is not reachable.
- update available: run `browser-harness --update -y` when you decide to upgrade.
- `browser-use` CLI says `remote-debugging-setup: no browser here has remote debugging on, and there is no display`: upgrade browser-use to 1.0.3 or newer (`uv tool install browser-use@latest`, or `pip install -U browser-use`). From 1.0.3 the CLI starts its own Chromium on a machine with no display or no debuggable Chrome.

For a machine-readable health check, an orchestrator can set `BU_NAME` to an
already-provisioned daemon and run:

```bash
browser-harness doctor --json --require-existing-daemon
```

This prints a versioned JSON report and exits nonzero unless that exact daemon
has a live browser connection. It never starts or discovers another browser.

If this still fails, inspect `src/browser_harness/admin.py`, `src/browser_harness/daemon.py`, and `src/browser_harness/_ipc.py`.

Useful:

```bash
browser-harness --update -y
browser-harness telemetry disable
```

State lives under `${XDG_CONFIG_HOME:-~/.config}/browser-harness` by default: auth, telemetry id, agent workspace, runtime sockets, logs, screenshots, and temp files. Override with `BH_HOME` or `BROWSER_HARNESS_HOME`.

Long-running hosts: set `BH_IDLE_TIMEOUT=<seconds>` so idle daemons exit; a daemon spawned with `BH_OWNS_BROWSER=1` and `BU_CDP_WS` for a browser you launched defaults to 30 min and closes that browser. On a user's Chrome, each idle exit means another Allow popup on the next call.
