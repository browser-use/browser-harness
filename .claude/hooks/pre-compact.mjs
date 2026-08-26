#!/usr/bin/env node
// ORGAN 3 — flush before the context is cut.
// Compaction keeps the ends and drops the middle, so anything that must
// survive has to be on disk first. This hook cannot know your decisions —
// only you do — so it does two things it CAN do deterministically:
//   1. blocks compaction ONCE if state.md is stale relative to your edits,
//      forcing the flush to happen while the context still exists;
//   2. stamps a machine checkpoint into state.md either way.
import { appendFileSync, existsSync, statSync, readFileSync } from 'node:fs';
import { hookInput, P, fingerprint, gitHead, readJson, writeJson, readBudget, lastVerify, currentObjective } from '../harness/guardrails.mjs';
import { trace } from '../harness/trace.mjs';

const input = hookInput();
const fp = fingerprint();
const baseline = readJson(P.baseline, null);
const treeChanged = baseline && baseline.fingerprint !== fp;
const alreadyBlocked = readJson(P.compactFlush, { blocked: false }).blocked === true;

const stateMtime = existsSync(P.state) ? statSync(P.state).mtimeMs : 0;
const traceMtime = existsSync(P.trace) ? statSync(P.trace).mtimeMs : 0;
const stateIsStale = treeChanged && stateMtime < traceMtime;

if (stateIsStale && !alreadyBlocked) {
  writeJson(P.compactFlush, { blocked: true, blockedAt: new Date().toISOString(), fingerprint: fp });
  trace({ kind: 'pre-compact', decision: 'block', reason: 'state.md stale' });
  console.error([
    `HARNESS BLOCK — context is about to be compacted and .claude/harness/state.md is stale.`,
    `Compaction drops the middle of the conversation. Anything not on disk is gone.`,
    ``,
    `Before compacting, rewrite state.md with:`,
    `  - Current objective (one sentence)`,
    `  - Decisions made, with reasons`,
    `  - Approaches already tried and rejected  <-- this is the one you will otherwise re-litigate`,
    `  - Open blockers`,
    `  - Attempt counter`,
    ``,
    `Then let compaction proceed. This hook blocks only once per session.`,
  ].join('\n'));
  process.exit(2);
}

const checkpoint = [
  ``,
  `<!-- machine checkpoint written by pre-compact.mjs — do not hand-edit -->`,
  `> compaction (${input.trigger || 'unknown'}) at ${new Date().toISOString()}`,
  `> HEAD ${gitHead().slice(0, 8)} | tree ${fp.slice(0, 12)}${treeChanged ? ' (CHANGED this session)' : ''}`,
  `> objective at compaction: ${currentObjective()}`,
  `> tool budget: ${readBudget().count}/${readBudget().limit}`,
  `> last verify: ${(() => { const lv = lastVerify(); return lv ? `exit ${lv.exitCode}${lv.fingerprint === fp ? ' (valid)' : ' (STALE)'}` : 'never run'; })()}`,
  ``,
].join('\n');
try { appendFileSync(P.state, checkpoint); } catch { /* never block compaction on a write failure */ }
trace({ kind: 'pre-compact', decision: 'allow', trigger: input.trigger });
process.exit(0);
