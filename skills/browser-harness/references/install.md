# browser-harness CLI — one-time install prerequisite

This is a **one-time prerequisite**, not part of the regular AI workflow. Do it once; after `browser-harness` prints page info, never repeat install/connection steps during normal browser work.

## Install the command

```bash
os=$(uname -s | tr '[:upper:]' '[:lower:]'); arch=$(uname -m)
case "$arch" in x86_64) arch=amd64 ;; aarch64) arch=arm64 ;; esac
command -v uv >/dev/null && uv tool uninstall browser-harness 2>/dev/null || true  # old Python install
mkdir -p ~/.local/bin
curl -fsSL -o ~/.local/bin/browser-harness.new \
  "https://github.com/browser-use/browser-harness/releases/latest/download/browser-harness-$os-$arch"
chmod +x ~/.local/bin/browser-harness.new && mv -f ~/.local/bin/browser-harness.new ~/.local/bin/browser-harness
command -v browser-harness   # should print a path
```

This downloads one self-contained binary; rerun it to upgrade. Keep `~/.local/bin` on `PATH`. On Windows, download `browser-harness-windows-amd64.exe` from the [latest release](https://github.com/browser-use/browser-harness/releases/latest) instead. The first line removes an older Python install, if any, so it cannot shadow the binary.

For browser-harness development, clone the repo and run `./browser-harness` from the checkout; it rebuilds the Go binary from the working tree when Go is installed.

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
browser-harness <<'JS'
print(page_info())
JS
```

If that prints page info, you're done. If not, run `browser-harness --doctor` and follow the connection cases. The two connection methods:

- **Way 1 (real browser):** open Chrome normally, then open `chrome://inspect/#remote-debugging` and tick "Allow remote debugging for this browser instance". On Chrome 144+, click Allow on the first-attach popup. Inherits your logins/extensions — best when the agent acts in your everyday browser.
- **Way 2 (isolated profile, no popups):** launch Chrome with `--remote-debugging-port=9222 --user-data-dir=<non-default path>`, then set `BU_CDP_URL=http://127.0.0.1:9222`. Best for unattended automation.

If the quick path fails after `--doctor`, inspect `go/internal/admin/`, `go/internal/daemon/`, and `go/internal/ipc/` in the source repo.

## Keeping current

To upgrade, rerun the install commands above; `browser-harness --version` prints the installed version. Telemetry is anonymous and opt-out with `browser-harness telemetry disable`.

State lives under `${XDG_CONFIG_HOME:-~/.config}/browser-harness` by default: auth, agent workspace, runtime sockets, logs, screenshots, and temp files. Override with `BH_HOME`.
