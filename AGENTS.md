browser-harness is a thin layer that connects agents to browsers via an editable CDP harness.

# Code priorities
- Clarity
- Precision
- Low verbosity
- Versatility

# Overview
Core code lives in `go/`, built into one `browser-harness` binary (CLI, daemon and MCP server):
- `internal/admin/` — daemon lifecycle, diagnostics, cloud browsers, profile management
- `internal/daemon/` — the long-lived middleman process between the browser and the agent
- `internal/helpers/` — CDP wrapper and core browser primitives
- `internal/jsrun/` — runs the JavaScript snippets the CLI reads from stdin, with the helpers as globals
- `internal/cli/` — the `browser-harness` CLI
- `internal/mcpserver/` — the `browser-harness mcp` server

`SKILL.md` tells agents how to use the harness and CLI.
`install.md` tells agents how to install it, attach a browser, and troubleshoot.

An agent operating the harness only edits inside `agent-workspace/`:
- `agent_helpers.js` — task-specific browser helpers the agent adds
- `domain-skills/` — skills the agent writes and reads

Package/CLI name = `browser-harness`. Skill identity (`name` + trigger) = `browser-use` (do not rename).

# Commands

From a **git checkout** (no global install required for local testing):

```bash
# doctor — install/daemon/browser state
./browser-harness --doctor

# smoke — CDP attach + page_info (Chrome remote debugging must be allowed)
./browser-harness <<'JS'
print(page_info())
JS

# unit tests (no live browser)
(cd go && go test ./...)

# after Go edits: the launcher rebuilds; reload the daemon so the next call runs the new code
./browser-harness --reload
```

Notes:
- `./browser-harness` = local tree launcher. Agents/docs outside this repo use the installed `browser-harness` command.
- First-time install / blocked Chrome: follow `install.md` (`chrome://inspect/#remote-debugging`).

# Security
- Do not commit secrets, Browser Use Cloud tokens, or session cookies.
- Prefer the smallest change that fixes the bug; do not expand CDP surface without need.

# Contributing
Consider what is really needed. Prefer the smallest diff that fixes the bug.
Domain skills under `agent-workspace/domain-skills/` are agent-generated when possible — hand-author only when necessary.
