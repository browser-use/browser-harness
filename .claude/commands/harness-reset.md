---
description: Archive the trace, clear attempt and budget counters, start a fresh objective
allowed-tools: Bash(node .claude/harness/trace.mjs:*), Bash(node .claude/harness/guardrails.mjs:*), Read, Edit
---

Use this when starting a genuinely new objective, or after the harness released control
and a human has resolved the blocker. It does **not** make a failing verify pass.

1. Archive the trace:

!`node .claude/harness/trace.mjs archive`

2. Clear the attempt and budget counters:

!`node .claude/harness/guardrails.mjs reset`

3. Rewrite `.claude/harness/state.md` with a fresh objective. Keep the **Decisions made**
   and **Approaches already tried and rejected** sections — those are the whole point of
   the file and are what stops the next session re-litigating settled ground. Reset only
   the objective, the open blockers, and the attempt counter.

Then confirm what you cleared and what you deliberately kept.
