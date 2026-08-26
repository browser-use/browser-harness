---
description: Show budgets, attempts, last verify result and the trace tail
allowed-tools: Bash(node .claude/harness/guardrails.mjs:*), Bash(node .claude/harness/trace.mjs:*), Read
---

Current tree fingerprint:

!`node .claude/harness/guardrails.mjs fingerprint`

Tool-call budget for the current objective:

!`node .claude/harness/guardrails.mjs budget`

Last verify result:

@.claude/harness/.last-verify

Last ten trace entries:

!`node .claude/harness/trace.mjs tail 10`

Report compactly: is the last verify **valid for this tree** (its `fingerprint` equals
the fingerprint above) or **stale**? How many of the 25 acting calls are spent? Does the
trace show anything that contradicts what was claimed in the session so far?
