#!/usr/bin/env node
// ORGAN 7 — Append-only record of what actually happened. The only admissible
// evidence for a success claim, alongside a verify exit code.
import { appendFileSync, readFileSync, renameSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { P, gitHead } from './guardrails.mjs';

const MAX_FIELD = 400;
const clip = (v) => {
  if (v === undefined || v === null) return v;
  const s = typeof v === 'string' ? v : JSON.stringify(v);
  return s.length > MAX_FIELD ? s.slice(0, MAX_FIELD) + `…[+${s.length - MAX_FIELD} chars]` : s;
};

export function trace(entry) {
  const line = JSON.stringify({ ts: new Date().toISOString(), head: gitHead().slice(0, 8), ...entry }) + '\n';
  try { appendFileSync(P.trace, line); } catch { /* trace must never break the run */ }
}
export function traceTool({ tool, target, outcome, detail, session }) {
  trace({ kind: 'tool', tool, target: clip(target), outcome, detail: clip(detail), session });
}
export function tail(n = 10) {
  if (!existsSync(P.trace)) return [];
  return readFileSync(P.trace, 'utf8').replace(/\r\n/g, '\n').split('\n').filter(Boolean).slice(-n);
}
export function archive() {
  if (!existsSync(P.trace)) return null;
  mkdirSync(P.backup, { recursive: true });
  const dest = join(P.backup, `trace-${new Date().toISOString().replace(/[:.]/g, '-')}.jsonl`);
  renameSync(P.trace, dest);
  return dest;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const [, , cmd, arg] = process.argv;
  if (cmd === 'tail') tail(Number(arg) || 10).forEach(l => console.log(l));
  else if (cmd === 'archive') console.log(archive() || 'nothing to archive');
  else if (cmd === 'note') { trace({ kind: 'note', text: arg }); console.log('noted'); }
  else { console.log('usage: node trace.mjs <tail [n]|archive|note "text">'); process.exit(1); }
}
