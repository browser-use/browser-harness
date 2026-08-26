---
description: Run the harness gate and report the exit code verbatim
allowed-tools: Bash(node .claude/harness/verify.mjs:*)
---

Run the gate:

!`node .claude/harness/verify.mjs`

Report the result with no interpretation:

- exit **0** — say "verify PASS (exit 0)" and name the steps that ran.
- non-zero — say "verify FAIL", name the failing step, and paste the tail it printed.
  Do not summarise the failure favourably. Do not claim the change works.

Never edit `.claude/harness/**` or `.claude/hooks/**` to change this outcome.
