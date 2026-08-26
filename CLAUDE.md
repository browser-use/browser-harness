# browser-harness — operating contract

Loaded into every session. Rules only. The long explanation lives in `@docs/HARNESS.md`.

## Project facts

- Python ≥3.11 CDP driver for the user's **real, signed-in Chrome**. Entry points:
  `run.py` (CLI, `browser-harness` on PATH), `helpers.py` (the functions), `daemon.py`,
  `admin.py`. Deps: `cdp-use`, `fetch-use`, `websockets`.
- 89 of 102 tracked files are Markdown: `SKILL.md`, `install.md`, `domain-skills/<site>/*.md`,
  `interaction-skills/*.md`. **The skill corpus is the product.** Treat a broken skill file
  as a broken build.
- The one verify command: **`node .claude/harness/verify.mjs`** (also `/verify`).
- There is no CI. This gate is the only gate.
- Change detection is a content hash (`node .claude/harness/guardrails.mjs fingerprint`),
  not `git status`. `state.md` is deliberately outside that hash, so updating your working
  memory never invalidates a green verify.
- Only run one Claude session per checkout. The harness counters are not lock-protected.

## The loop

**Outer loop — attempts.** At most **3** attempts per objective. After a failed attempt,
write what failed and why into `.claude/harness/state.md` and **change approach**.
Repeating the same attempt with more enthusiasm is not an attempt. After the third,
stop, write a blocker note, hand control to the human.

**Inner loop — one attempt.**

1. **Orient.** Read `@.claude/harness/state.md` and `@.claude/harness/contract.md`.
   State the objective in one sentence and the observable condition that proves it done.
   Write that sentence under `## Current objective` in `state.md` — the tool budget is
   keyed to it.
2. **Plan.** Smallest reversible change that could satisfy the objective. If it touches
   anything under *Requires human approval*, stop and ask first.
3. **Act.** Stay inside the budget. Never touch forbidden paths.
4. **Verify.** Run `node .claude/harness/verify.mjs`. Read the exit code. Do not
   interpret it, do not summarise it favourably, do not proceed on a non-zero exit.
5. **Attest.** Report with evidence: the command, the exit code, the diff summary.
6. **Record.** Rewrite `state.md`. The trace is written for you by the hooks.

## Guardrails

- **3** attempts per objective. **25** acting tool calls per objective
  (Bash/PowerShell/Edit/Write/NotebookEdit; reads are free).
- **Never read** `.env`, `**/secrets/**`, `*.pem`, `*.key`. Secrets are the harness's job,
  not yours. Ask for the effect, never for the credential.
- **Never edit** `.git/**`, `__pycache__/**`, `*.egg-info/**`, `dist/`, `build/`.
- **Never run** recursive `rm`, `git push --force`, `git reset --hard`, `git clean -df`,
  `git checkout .`, `curl … | sh`, or any publish command.
- **`run.py`, `daemon.py`, `admin.py` and `browser-harness` attach to the user's live,
  signed-in Chrome.** Running them is an action on their real accounts, not a test.
  They always require an explicit yes. The test suite mocks CDP and needs no browser —
  use it instead.

## The anti-lie clause

**Never report a task as complete without the output of the verify command in the same
turn.** "It should work" and "I've made the change" are not completion. If verify was not
run, the word is **"unverified"**. A claim of success is not success; success is an exit
code plus a trace entry. Failing loudly is a win — step one to solving a problem is
admitting you have one.

## Escalation

Requires a human: dependency changes (`pyproject.toml`), any change to
`.claude/settings.json`, `.claude/hooks/**` or `.claude/harness/*.mjs`, driving the real
browser, `git commit`, `git push`, package installs.

Blocker note format, appended to `state.md`:

```
## BLOCKER — <one line>
- what I was trying to do:
- what I tried, and the exact failure (command + exit code):
- what I need a human to decide:
```

Blocked is a valid, respectable outcome. Report it and stop.

## Never modify the harness to satisfy the harness

Do not edit, disable or bypass a hook, a guardrail or the verify script to make a task
pass. If a guardrail is genuinely wrong, say so, explain why, and ask the human to amend
the contract. This is the one unforgivable action in this repo.

## When hooks are not running (Cowork / any non-Claude-Code client)

The hooks in `.claude/settings.json` execute in Claude Code (terminal) and in the VS Code
extension. Elsewhere — Cowork, a plain SDK session — nothing fires, and the same rules
must be followed **procedurally**. In that case, explicitly and by hand:

- at the start: read `state.md`, and record the output of
  `node .claude/harness/guardrails.mjs fingerprint` as your baseline;
- before finishing: run the verify command and paste its output;
- count your own acting tool calls against the budget of 25;
- check any path or command you are unsure about with
  `node .claude/harness/guardrails.mjs check-path <p>` / `check-command "<cmd>"`.

## Pointers

- `@.claude/harness/state.md` — current objective, decisions, rejected approaches, blockers
- `@.claude/harness/contract.md` — the contract in force
- `@docs/HARNESS.md` — what each organ does and how to maintain it
