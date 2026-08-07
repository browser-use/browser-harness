browser-harness is a thin layer that connects agents to browsers via an editable CDP harness.

# Code priorities
- Clarity
- Precision
- Low verbosity
- Versatility

# Overview
Core code lives in `src/browser_harness/`:
- `admin.py` — daemon lifecycle, diagnostics, updates, profile management
- `daemon.py` — the long-lived middleman process between the browser and the agent
- `helpers.py` — CDP wrapper and core browser primitives auto-imported into `-c` scripts
- `run.py` — the `browser-harness` CLI

`SKILL.md` tells agents how to use the harness and CLI.
`install.md` tells agents how to install it, attach a browser, and troubleshoot.
In this checkout, invoke the current source with `./browser-harness`; do not use
a globally installed `browser-harness` binary.

For recording or video tasks, follow `SKILL.md` and
`interaction-skills/make-video.md`. A natural request to show, record, or demo
the work opts in; significant work alone does not. Keep the exact path returned
by `start_recording()` and never reenact a finished task.

An agent operating the harness only edits inside `agent-workspace/`:
- `agent_helpers.py` — task-specific browser helpers the agent adds
- `domain-skills/` — skills the agent writes and reads

# Contributing
Consider what is really needed. Prefer the smallest diff that fixes the bug.
