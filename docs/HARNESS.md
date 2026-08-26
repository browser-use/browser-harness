# The harness

> An agent harness is everything around the model that gives it grounding in reality.

A climber anchors to the rock so they cannot drift. A dog walks on a harness so it cannot
run into traffic. The harness is not the agent, not the loop, and not the prompt — it is
the stable structure the agent is tied to.

The premise of everything in this directory is that **you do not fix reliability by
prompting harder**. Every failure mode gets a mechanism: a hook, a script, an exit code, a
permission rule. Prose is the last resort, and where prose is all we have, this document
says so out loud.

## Why this repo needed one

Three things about `browser-harness` specifically:

1. **`run.py`, `daemon.py` and `admin.py` attach over CDP to the user's real, signed-in
   Chrome.** An agent running them is taking authenticated actions on live accounts. That
   is the largest blast radius in the repo by a wide margin, and nothing guarded it.
2. **89 of 102 tracked files are Markdown skills — the product itself — and nothing
   validated them.** A skill with an unclosed code fence or a dead cross-reference ships
   silently and degrades every future agent that reads it.
3. **"Is the tree dirty?" is not a question `git status` answers portably.** Read through
   a Linux git, this Windows checkout reports 99 modified files and a 27,101-line diff of
   pure line endings; read through Git for Windows, where `core.autocrlf` is set at system
   level, the same bytes are clean. Same tree, opposite answers, depending on which git
   asks. A gate built on `git status` inherits that. Content hashing does not — and it also
   survives formatter mtime churn and makes verify-staleness structural rather than a
   marker file someone has to remember to delete.

   *(Correction, 2026-08-26: the first version of this document asserted `core.autocrlf=false`
   and presented the dirty tree as a defect in the repo. It is not — it was an artefact of
   the environment the recon ran in, and the claim was wrong. The mechanism was right for
   other reasons; the evidence given for it was not. An independent audit caught it.)*

Also: there is no CI, no linter config, no formatter, no typechecker and no dev dependency
group. There was no verify command to inherit. The gate here was built, not found.

## The seven organs

| # | Organ | Where it lives |
|---|---|---|
| 1 | Tool registry | `.claude/settings.json` → `permissions.allow` / `ask` / `deny` |
| 2 | Model boundary | Assume a weaker model than you hope. Nothing here depends on model capability; every check is code |
| 3 | Context primitives | `harness/state.md`, `hooks/session-start.mjs`, `hooks/pre-compact.mjs` |
| 4 | Guardrails | `harness/contract.json`, `harness/guardrails.mjs`, `hooks/pre-tool-use.mjs` |
| 5 | Agent loop + outer loop | `CLAUDE.md` (the protocol) + the attempt counter in `hooks/stop.mjs` |
| 6 | Verify step | `harness/verify.mjs`, `harness/validate-skills.mjs`, enforced by `hooks/stop.mjs` |
| 7 | Trace | `harness/trace.mjs` → `harness/trace.jsonl` (gitignored) |

## Running the gate by hand

```bash
node .claude/harness/verify.mjs        # exit 0 = pass, 1 = fail (names the failing step)
```

No model is involved. A teammate, a cron job and the Stop hook all get the identical
answer. Useful adjuncts:

```bash
node .claude/harness/guardrails.mjs fingerprint          # content hash of the tree
node .claude/harness/guardrails.mjs budget               # acting calls used this objective
node .claude/harness/guardrails.mjs check-path .env      # would this path be blocked?
node .claude/harness/guardrails.mjs check-command "rm -rf ."
node .claude/harness/trace.mjs tail 20
```

`verify.mjs` finds Python in this order: `$HARNESS_PYTHON`, `.venv/Scripts/python.exe`
(Windows) or `.venv/bin/python`, `python3`, `python`, `py -3`. Set `HARNESS_PYTHON` if you
keep the interpreter somewhere unusual.

If the `tests` step says pytest is missing: `uv sync --group dev`, or
`python -m pip install pytest`. It is declared in `pyproject.toml` under
`[dependency-groups] dev`.

## How the Stop gate actually works

`hooks/stop.mjs` runs when Claude tries to end a turn.

1. `stop_hook_active` true → exit 0. Claude Code force-overrides a Stop hook after eight
   consecutive blocks; the harness never fights that.
2. No session baseline → write one, exit 0. It refuses to guess at a change it cannot bound.
3. Current fingerprint equals the session-start fingerprint → nothing changed, exit 0.
4. `.last-verify` exists, `exitCode` is 0, **and** its `fingerprint` equals the current one
   → exit 0. Staleness is structural: any write changes the fingerprint, so a green result
   from before the write cannot satisfy the gate. There is nothing to invalidate by hand.
5. Otherwise exit 2, which blocks and feeds the reason back to Claude.
6. After `max_attempts` blocks (3), it writes a blocker note into `state.md`, prints
   "HARNESS RELEASED CONTROL", and exits 0. **A harness that can never release control is
   a broken harness.**

## Adding a guardrail

Forbidden paths and commands live in `harness/contract.json` — one place, read by the hook
and by the CLI. Add a path glob to `forbidden_paths` (a leading `!` makes an exception, as
with `!**/.env.example`), or an object to `forbidden_commands`:

```json
{ "id": "short-name", "pattern": "regex", "why": "one line", "instead": "the legitimate alternative" }
```

`why` and `instead` are not decoration — they are what the block message shows. A guardrail
that blocks silently teaches the agent nothing. Then check your work:

```bash
node .claude/harness/guardrails.mjs check-command "the thing you want blocked"   # expect exit 2
node .claude/harness/guardrails.mjs check-command "a legitimate neighbour"       # expect exit 0
```

Commands are matched **per shell segment** (`&&`, `||`, `;`, `|`, `&`, newline) after
stripping wrappers (`timeout`, `nice`, `sudo`, `env`, leading `FOO=bar` assignments), so
`safe && dangerous` cannot smuggle anything past. Two rules — pipe-to-shell and redirection
into the harness — are matched against the whole string instead, because that is where the
danger lives.

Permission rules are the coarser, faster net in `.claude/settings.json`. Two things that
cost real time to learn:

- **`Write(path)` and `NotebookEdit(path)` rules are accepted and never consulted.** Use
  `Edit(path)` for write guarding and `Read(path)` for read guarding. Anything else is a
  guardrail that looks present and does nothing.
- **A deny rule cannot carry an allow exception.** `Read(.env.*)` in deny would also block
  `.env.example`. That is why the deny list here is narrow and the *hook* carries the
  precise `**/.env.*` + `!**/.env.example` logic.

## Where the harness is mechanical, and where it is only protocol

| Environment | Hooks | Permissions | Verify |
|---|---|---|---|
| Claude Code (terminal) | enforced | enforced | enforced |
| Claude in VS Code | enforced — settings, hooks, commands and subagents are shared with the CLI | enforced | enforced |
| Cowork / SDK / plain CI | **not enforced** — nothing executes `.claude/settings.json` hooks | not enforced | runnable by hand |

In Cowork the same rules must be followed by hand; `CLAUDE.md` states them as explicit
steps for exactly that reason. This distinction is the honest measure of how strong the
harness really is, so it is written down rather than glossed.

## Disabling it, and why not to

Rename `.claude/settings.json`, or run `claude --settings /dev/null`. Do that to debug the
harness itself, never to get a task past it. Modifying the harness to satisfy the harness
is the one unforgivable action in this repo — `permissions.ask` makes every such edit
require a human yes, and the `verifier` subagent is told to report it first and loudly.

Personal overrides go in `.claude/settings.local.json`, which is gitignored.

## First maintenance action

Introduce `ruff` as a ratchet. Right now it reports 68 errors and would reformat 75 of 95
files, which is why it is not in the gate. The cheap path:

```bash
uv run ruff format .            # or: python -m pip install ruff && ruff format .
uv run ruff check --fix .
```

Commit that as one isolated reformat, add `ruff` to the dev dependency group, then add
`"lint"` to `verify_steps` in `contract.json` and a matching entry in the `STEPS` object of
`verify.mjs`. Do it as its own change with nothing else in the diff.

**Do not** go renormalising line endings. An earlier draft of this document told you to,
on the strength of a misread `git config` output. Under Git for Windows this tree is clean;
adding a `.gitattributes` and running `git add --renormalize .` would rewrite all 102 files
for no benefit. If you ever add Linux or macOS teammates, revisit it then — as a deliberate
decision, not as maintenance.

## Known gaps

Stated plainly, because hiding them is the same failure as lying about success.

- **No cross-session locking.** Two Claude sessions in the same checkout share
  `.claude/harness/{.budget,.stop-attempts,.last-verify,.session-baseline}` with no lock.
  The gate's design assumes it owns those counters. Concurrent sessions can overwrite each
  other's `.last-verify` and each other's attempt counts. Symptoms are confusing rather
  than dangerous — a turn released early, or blocked when it should not be. **Run one
  session per checkout.** If you need two, give the second its own clone.
- **The gate never drives the browser.** It proves syntax, tests and skill structure. That
  CDP still attaches to a real Chrome is a human check.
- **The deny list is a net, not a wall.** Command rules are anchored to the head of a shell
  segment so that searching for a string is not treated as running it. A sufficiently
  creative invocation shape will still get through; `nested-shell` closes the obvious one
  (`bash -c "..."`), not every one.
- **Hooks do not run outside Claude Code and the VS Code extension.** See the table above.
