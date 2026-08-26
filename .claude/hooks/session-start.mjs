#!/usr/bin/env node
// ORGAN 3 — context primitive. Snapshots the tree for the Stop gate and
// orients every new session from disk rather than from a fading transcript.
import { readFileSync, existsSync } from 'node:fs';
import { hookInput, P, contract, fingerprint, gitHead, writeJson, resetCounters, readBudget, lastVerify } from '../harness/guardrails.mjs';
import { trace } from '../harness/trace.mjs';
import { tail } from '../harness/trace.mjs';

const input = hookInput();
const fp = fingerprint();
writeJson(P.baseline, { fingerprint: fp, head: gitHead(), at: new Date().toISOString(), source: input.source || 'unknown' });
resetCounters();   // zeroes stop-attempts, tool budget and the compaction flush flag
trace({ kind: 'session-start', source: input.source, session: input.session_id, fingerprint: fp.slice(0, 12) });

const lv = lastVerify();
const budget = readBudget();
const state = existsSync(P.state) ? readFileSync(P.state, 'utf8').replace(/\r\n/g, '\n').trim() : '(no state.md)';

// SessionStart stdout is injected into the session as context.
console.log([
  `<harness-status>`,
  `Harness is ACTIVE in this repo. The gate is: node .claude/harness/verify.mjs`,
  `Contract: ${contract.verify_steps.join(' -> ')} | max_attempts=${contract.max_attempts} | tool budget=${contract.max_tool_calls_per_objective}/objective`,
  `Last verify: ${lv ? `exit ${lv.exitCode}${lv.failedStep ? ` (failed at "${lv.failedStep}")` : ''} at ${lv.timestamp}${lv.fingerprint === fp ? ' — STILL VALID for this tree' : ' — STALE, the tree has changed since'}` : 'never run'}`,
  `Tool budget used: ${budget.count}/${budget.limit} for objective "${budget.objective}"`,
  `Recent trace:`,
  ...tail(5).map(l => '  ' + l),
  ``,
  `--- .claude/harness/state.md ---`,
  state,
  `--- end state.md ---`,
  `Read .claude/harness/contract.md before changing how you work in this repo.`,
  `</harness-status>`,
].join('\n'));
process.exit(0);
