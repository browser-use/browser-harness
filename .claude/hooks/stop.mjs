#!/usr/bin/env node
// ORGAN 6 enforcement — THE anti-lie gate. The single most important file here.
// It cannot be satisfied by a claim; only by an exit code recorded against
// this exact tree.
import { readFileSync, writeFileSync, existsSync, appendFileSync } from 'node:fs';
import { hookInput, P, contract, fingerprint, gitHead, readJson, writeJson, verifyIsGreenForTree, clearCounter } from '../harness/guardrails.mjs';
import { trace } from '../harness/trace.mjs';

const input = hookInput();

// Platform escape hatch: Claude Code force-overrides a Stop hook after 8
// consecutive blocks. Respect stop_hook_active so we never fight it.
if (input.stop_hook_active === true) process.exit(0);

const fp = fingerprint();
const baseline = readJson(P.baseline, null);

// 1. No session baseline (Cowork, a resumed session, a hand-run) — record one
//    and let this turn end. We refuse to guess at a change we cannot bound.
if (!baseline) {
  writeJson(P.baseline, { fingerprint: fp, head: gitHead(), at: new Date().toISOString(), note: 'written by stop.mjs; no SessionStart baseline existed' });
  process.exit(0);
}

// 2. Nothing changed this session — nothing to verify.
if (baseline.fingerprint === fp) {
  clearCounter(P.stopAttempts);
  process.exit(0);
}

// 3. Something changed. Is there a green verify against THIS tree?
const green = verifyIsGreenForTree(fp);
if (green.ok) {
  clearCounter(P.stopAttempts);
  trace({ kind: 'stop', decision: 'allow', reason: 'verify green for current tree' });
  process.exit(0);
}

// 4. Not verified. Count the block; release control once the contract's
//    attempt budget is spent. A harness that can never release control is broken.
const att = readJson(P.stopAttempts, { count: 0 });
att.count += 1;
att.lastFingerprint = fp;
writeJson(P.stopAttempts, att);

if (att.count > contract.max_attempts) {
  const note = [
    '',
    `## BLOCKER — harness gave up after ${contract.max_attempts} attempts`,
    `- when: ${new Date().toISOString()}`,
    `- tree fingerprint: ${fp.slice(0, 12)}  (HEAD ${gitHead().slice(0, 8)})`,
    `- reason verify is not green: ${green.why}`,
    `- what a human must do: run \`node .claude/harness/verify.mjs\`, read the failing step,`,
    `  and decide whether the change or the contract is wrong.`,
    '',
  ].join('\n');
  try { appendFileSync(P.state, note); } catch { /* never break the release */ }
  trace({ kind: 'stop', decision: 'release', attempts: att.count, why: green.why });
  console.error(`HARNESS RELEASED CONTROL — the Stop gate blocked ${contract.max_attempts} times without verify going green (${green.why}). A blocker note was written to .claude/harness/state.md. This turn is ending UNVERIFIED; a human needs to look.`);
  clearCounter(P.stopAttempts);
  process.exit(0);
}

trace({ kind: 'stop', decision: 'block', attempt: att.count, why: green.why });
console.error([
  `HARNESS BLOCK — you are trying to finish an unverified change. (attempt ${att.count} of ${contract.max_attempts})`,
  ``,
  `  the tree changed this session: ${baseline.fingerprint.slice(0, 12)} -> ${fp.slice(0, 12)}`,
  `  verify status: ${green.why}`,
  ``,
  `  Run:   node .claude/harness/verify.mjs`,
  `  Then:  fix whatever step it names and run it again until it exits 0.`,
  ``,
  `  Definition of done: ${contract.definition_of_done}`,
  `  Do NOT edit .claude/harness/** or .claude/hooks/** to make this pass.`,
  `  If verify is genuinely wrong, say so, stop, and ask the human to amend the contract.`,
].join('\n'));
process.exit(2);
