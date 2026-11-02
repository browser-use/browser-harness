---
name: browser-install
description: Install browser-harness and connect it to a browser fast.
---

# browser-harness install

Use once. For browser work, read `SKILL.md`.

## Fast Path

```bash
os=$(uname -s | tr '[:upper:]' '[:lower:]'); arch=$(uname -m)
case "$arch" in x86_64) arch=amd64 ;; aarch64) arch=arm64 ;; esac
command -v uv >/dev/null && uv tool uninstall browser-harness 2>/dev/null || true  # old Python install
mkdir -p ~/.local/bin
curl -fsSL -o ~/.local/bin/browser-harness.new \
  "https://github.com/browser-use/browser-harness/releases/latest/download/browser-harness-$os-$arch"
chmod +x ~/.local/bin/browser-harness.new && mv -f ~/.local/bin/browser-harness.new ~/.local/bin/browser-harness
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness"
browser-harness skill > "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"
browser-harness <<'JS'
print(page_info())
JS
```

If `page_info()` prints, configure recording consent below, then stop.

This downloads one self-contained binary; rerun it to upgrade. Keep `~/.local/bin` on `PATH`. On Windows, download `browser-harness-windows-amd64.exe` from the [latest release](https://github.com/browser-use/browser-harness/releases/latest) instead. The first line removes an older Python install, if any, so it cannot shadow the binary.

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

In Chrome:

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
(for example Terminal, iTerm, Codex, or an IDE) in System Settings.

## Cloud Browsers

Cloud is optional. Local Chrome does not need a Browser Use API key.

Use any short made-up name; `r7k2` below is just a placeholder.

```bash
browser-harness auth login
browser-harness <<'JS'
start_remote_daemon("r7k2")
JS
```

Then use it by name:

```bash
BU_NAME=r7k2 browser-harness <<'JS'
print(page_info())
JS
```

## If Still Broken

```bash
browser-harness --doctor
```

Use the output:

- `chrome running` FAIL: ask the user to open Chrome, or use isolated/cloud browser.
- `daemon alive` FAIL: Chrome remote debugging permission is missing, Chrome is closed, or the CDP endpoint is not reachable.

For a machine-readable health check, an orchestrator can set `BU_NAME` to an
already-provisioned daemon and run:

```bash
browser-harness doctor --json --require-existing-daemon
```

This prints a versioned JSON report and exits nonzero unless that exact daemon
has a live browser connection. It never starts or discovers another browser.

If this still fails, inspect `go/internal/admin/`, `go/internal/daemon/`, and `go/internal/ipc/` in the source repo.

To upgrade, rerun the install commands above. To opt out of anonymous telemetry:

```bash
browser-harness telemetry disable
```

State lives under `${XDG_CONFIG_HOME:-~/.config}/browser-harness` by default: auth, telemetry id, agent workspace, runtime sockets, logs, screenshots, and temp files. Override with `BH_HOME` or `BROWSER_HARNESS_HOME`.
