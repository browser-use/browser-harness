# Harness contract — browser-harness

In force for every session in this repository. The **machine-readable source of
truth is `contract.json`**; this file is its human mirror. If the two disagree,
`contract.json` is what actually runs — fix this file.

Changing either requires human approval (`permissions.ask` in `.claude/settings.json`).

## Definition of done

`node .claude/harness/verify.mjs` exits 0 against the current tree, the diff has
been reviewed, and `state.md` is updated. Anything short of that is **unverified**,
and "unverified" is the word to use — never "done".

The three are independent: `state.md` is excluded from the tree fingerprint, so writing
it after a green verify does not make that verify stale. Order them however you like.

## The gate

| Step | What it runs | Why it exists |
|---|---|---|
| `skills` | `validate-skills.mjs` over all 89 tracked Markdown files | The product of this repo *is* the skill corpus. Frontmatter keys, H1 titles, balanced code fences, and dead cross-references were previously checked by nothing. |
| `compile` | `python -m compileall` over the 6 tracked `.py` files | Catches a broken edit without needing the browser or the network. |
| `tests` | `python -m pytest -q` | The 4 existing tests mock CDP, so they need no live Chrome and no network. |

Not in the gate: **ruff**. On the tree as inherited it reports 68 lint errors and
would reformat 75 of 95 files. Adding it would mean building a gate on red. See
"First maintenance action" in `docs/HARNESS.md`.

## Budgets

| Field | Value |
|---|---|
| `max_attempts` | **3** — after three Stop-gate blocks on the same tree, the harness writes a blocker note and hands control to the human |
| `max_tool_calls_per_objective` | **25** *acting* calls (Bash, PowerShell, Edit, Write, MultiEdit, NotebookEdit). Reads are not counted. Reset by `/harness-reset` or by changing the objective line in `state.md` |

## Forbidden

**Paths** (`forbidden_paths`): `.env` and `.env.*` except `.env.example`, `**/secrets/**`,
`*.pem`, `*.key`, `*.egg-info/**`, `__pycache__/**`, `.git/**`, `dist/`, `build/`,
`node_modules/`.

**Commands** (`forbidden_commands`, matched per shell segment so `safe && dangerous`
cannot smuggle anything past): recursive `rm`, force push, `git reset --hard`,
`git clean -df`, `git checkout .`, pipe-to-shell (`curl … | sh`), package publish,
history rewriting, and shell redirection into `.claude/hooks/` or `.claude/harness/`.

## Requires human approval

- Any change to `pyproject.toml` — dependency additions.
- Any change to `.claude/settings.json`, `.claude/hooks/**`, or `.claude/harness/*.mjs`.
- Any invocation that drives the real Chrome profile: `run.py`, `daemon.py`, `admin.py`,
  `browser-harness`. These attach over CDP to a signed-in browser; they are actions on
  live accounts, not tests.
- `git commit`, `git push`, and any package install.

## Secrets

Read from environment variables and `.env`, which the harness **denies to the model
outright**. The model requests an effect; the harness or the human performs it. A
credential never enters context.

## Escalation

Stop in-session. Write a blocker note into `state.md` in this shape:

```
## BLOCKER — <one line>
- what I was trying to do:
- what I tried, and the exact failure (command + exit code):
- what I need a human to decide:
```

Then hand control back. **Blocked is a valid, respectable outcome.**

## The one unforgivable action

Editing, disabling or bypassing a hook, a guardrail or the verify script to make a
task pass. If a guardrail is genuinely wrong, say so, explain why, and ask for the
contract to be changed.
