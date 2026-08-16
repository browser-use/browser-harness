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

That keeps the command global while still pointing at the real repo checkout, so when the agent edits `agent-workspace/agent_helpers.py` the next `browser-harness` uses the new code immediately. Prefer a stable path like `~/Developer/browser-harness`, not `/tmp`.

## Make browser-harness global for the current agent

After the repo is installed, register this repo's `SKILL.md` with the agent you are using:

- **Codex**: add this file as a global skill at `$CODEX_HOME/skills/browser-harness/SKILL.md` (often `~/.codex/skills/browser-harness/SKILL.md`). A symlink to this repo's `SKILL.md` is fine.

  ```bash
  mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness" && ln -sf "$PWD/SKILL.md" "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"
  ```

- **Claude Code**: add an import to `~/.claude/CLAUDE.md` that points at this repo's `SKILL.md`, for example `@~/Developer/browser-harness/SKILL.md`.

- **OpenCode**: add this repo's `SKILL.md` as a global skill under `$OPN_HOME/skill/browser-harness/SKILL.md` (typically `~/.opencode/skill/browser-harness/SKILL.md`). A symlink is fine; on Windows without admin, copy the file instead.

- **OpenCode**: add this repo's `SKILL.md` as a global skill under `~/.config/opencode/skills/browser-harness/SKILL.md`. A symlink is fine; on Windows without admin, copy the file instead.

  ```bash
  # Unix (symlink preferred)
  mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills/browser-harness" && ln -sf "$PWD/SKILL.md" "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills/browser-harness/SKILL.md"

  # Windows (PowerShell, symlink needs admin — fall back to copy)
  $opn="$env:USERPROFILE\.config\opencode\skills\browser-harness"; New-Item -ItemType Directory -Force -Path $opn | Out-Null; try { New-Item -ItemType SymbolicLink -Path "$opn\SKILL.md" -Target "$PWD\SKILL.md" -Force } catch { Copy-Item "$PWD\SKILL.md" "$opn\SKILL.md" -Force }

This makes new Codex, Claude Code, or OpenCode sessions in other folders load the runtime browser harness instructions automatically.
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
