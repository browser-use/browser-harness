# Harness state

Working memory that survives context compaction. Small, rewritten in place,
never appended forever. Update it at the end of every work cycle.

## Current objective

(none — set this to one sentence before starting work)

## Decisions made

- 2026-08-26 — Verify chain is `skills -> compile -> tests`. ruff is deliberately
  excluded: it reports 68 errors and 75 unformatted files on the tree as inherited,
  so including it would have built the gate on top of red.
- 2026-08-26 — Change detection uses content hashing, not `git status`: git status gives
  opposite answers for the same bytes depending on the git that reads them, and content
  hashing also survives mtime churn and makes verify-staleness structural.
- 2026-08-26 — CORRECTION: the original recon claimed `core.autocrlf=false` and a broken
  tree. Wrong — it misread a two-command shell output; `false` was `core.filemode`.
  Under Git for Windows this tree is clean. Do NOT renormalise line endings.
- 2026-08-26 — `.claude/harness/state.md` is excluded from the fingerprint. Otherwise the
  contract's own "update state.md" step invalidated the verify that preceded it, and the
  Stop gate's release path (which appends a blocker note) guaranteed an un-green next turn.
- 2026-08-26 — Command rules are anchored to the head of a shell segment, so `grep -r "rm -rf"`
  is a search, not a delete. A `nested-shell` rule covers the `bash -c "..."` hole that
  anchoring would otherwise open.
- 2026-08-26 — Hooks are Node `.mjs` in exec form (`args` set). Shell-form hooks on
  Windows run under Git Bash, or PowerShell when Git Bash is absent; exec form spawns
  the script directly with no shell on any platform.
- 2026-08-26 — pytest declared in `pyproject.toml` under `[dependency-groups] dev`.
- 2026-08-26 — Gate CONFIRMED on Windows: `.venv\Scripts\python.exe` (Python 3.13.2),
  all three steps PASS, exit 0. The tree fingerprint was byte-identical to the one
  produced on Linux (`c2de755df8f2`) despite CRLF on disk, so the gate is genuinely
  platform-independent.

## Approaches already tried and rejected

- Using `git status --porcelain` for "did the tree change" — not portable across gits.
- Hashing `state.md` as part of the tree — makes the contract self-invalidating.
- Unanchored destructive-command regexes — they fire on arguments, not just on the command.
- Adding `ruff` to the gate immediately — would require a 75-file reformat first.
- `Write(path)` permission rules — Claude Code accepts them but never consults them;
  file guarding must use `Edit(path)` and `Read(path)`.

## Open blockers

- None. Known limitation, not a blocker: no cross-session locking — run one Claude
  session per checkout (see Known gaps in docs/HARNESS.md).

## Attempt counter

0 / 3 for the current objective.




