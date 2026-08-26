#!/usr/bin/env node
// ORGAN 4 — the deterministic denier. Runs BEFORE the tool does.
// Blocks loudly and specifically: what was blocked, which rule blocked it,
// and the legitimate alternative. Exit 2 is an unconditional block; a JSON
// decision on exit 0 can be overridden by schema-validation failure, so we
// never rely on it for a deny.
import { hookInput, checkPath, checkCommand, bumpBudget, contract } from '../harness/guardrails.mjs';
import { trace } from '../harness/trace.mjs';

const ACTING_TOOLS = /^(Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit)$/;
const PATH_FIELDS = ['file_path', 'notebook_path', 'path'];

const input = hookInput();
const tool = input.tool_name || '';
const ti = input.tool_input || {};

function deny(reason) {
  trace({ kind: 'blocked', tool, reason, session: input.session_id });
  console.error(reason);
  process.exit(2);           // hard block
}

// 1. Path guardrails — checked for every tool that names a file.
for (const field of PATH_FIELDS) {
  if (!ti[field]) continue;
  const r = checkPath(ti[field]);
  if (r.blocked) {
    deny([
      `HARNESS BLOCK — forbidden path`,
      `  tool:  ${tool} (${field} = ${ti[field]})`,
      `  rule:  forbidden_paths contains "${r.rule}" in .claude/harness/contract.json`,
      `  why:   this path holds secrets, generated output, or git internals.`,
      `  do:    work on a source file instead. If this path genuinely must change,`,
      `         stop and ask the human to amend the contract — do NOT edit the harness.`,
    ].join('\n'));
  }
}

// 2. Command guardrails — every segment of a compound command is checked.
const command = ti.command || '';
if (command) {
  const r = checkCommand(command);
  if (r.blocked) {
    deny([
      `HARNESS BLOCK — forbidden command`,
      `  command: ${String(command).slice(0, 300)}`,
      `  segment: ${String(r.matched).slice(0, 200)}`,
      `  rule:    forbidden_commands["${r.rule.id}"] — ${r.rule.why}`,
      `  do:      ${r.rule.instead}`,
    ].join('\n'));
  }
}

// 3. Tool-call budget, per objective (objective read from state.md).
if (ACTING_TOOLS.test(tool)) {
  const b = bumpBudget(1);
  if (b.count > b.limit) {
    deny([
      `HARNESS BLOCK — tool-call budget exhausted`,
      `  objective: ${b.objective}`,
      `  used:      ${b.count} of ${b.limit} acting tool calls (Bash/Edit/Write/NotebookEdit)`,
      `  why:       ${b.count - b.limit} calls past the contract limit means this approach is thrashing.`,
      `  do:        STOP. Write what you tried and why it failed into .claude/harness/state.md,`,
      `             then either change approach and run /harness-reset, or escalate to the human`,
      `             with a blocker note. Do not keep going.`,
    ].join('\n'));
  }
  if (b.count === b.limit) {
    console.error(`HARNESS WARNING — this is call ${b.count} of ${b.limit} for objective "${b.objective}". The next acting call will be blocked.`);
  }
}
process.exit(0);
