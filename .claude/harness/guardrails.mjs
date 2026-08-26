#!/usr/bin/env node
// ORGAN 4 — Guardrails, plus the shared primitives every other harness script uses.
// Zero dependencies. Node >= 18. Runs identically on Windows, macOS and Linux.
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';

// --- locations -------------------------------------------------------------
// Resolved from this file's own location, so it is correct even when
// CLAUDE_PROJECT_DIR is absent (Cowork, CI, a human running it by hand).
export const HARNESS_DIR = dirname(fileURLToPath(import.meta.url));
export const PROJECT_DIR = resolve(HARNESS_DIR, '..', '..');
export const P = {
  contract: join(HARNESS_DIR, 'contract.json'),
  state: join(HARNESS_DIR, 'state.md'),
  trace: join(HARNESS_DIR, 'trace.jsonl'),
  lastVerify: join(HARNESS_DIR, '.last-verify'),
  baseline: join(HARNESS_DIR, '.session-baseline'),
  stopAttempts: join(HARNESS_DIR, '.stop-attempts'),
  budget: join(HARNESS_DIR, '.budget'),
  compactFlush: join(HARNESS_DIR, '.compact-flush'),
  backup: join(HARNESS_DIR, 'backup'),
};

export const contract = JSON.parse(readFileSync(P.contract, 'utf8'));

// --- small helpers ---------------------------------------------------------
export function git(args, opts = {}) {
  return execFileSync('git', args, { cwd: PROJECT_DIR, encoding: 'utf8', ...opts });
}
export function readJson(p, fallback = null) {
  try { return JSON.parse(readFileSync(p, 'utf8')); } catch { return fallback; }
}
export function writeJson(p, obj) {
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(obj, null, 2) + '\n');
}
// Counters are ZEROED, never deleted. Some checkouts (network mounts, the Cowork
// device bridge, read-only-ish shares) refuse unlink, and a swallowed delete failure
// would silently carry an attempt count across sessions. A write always works where
// the harness can write at all.
export function clearCounter(p) { try { writeJson(p, { count: 0, clearedAt: new Date().toISOString() }); } catch { /* never break the run */ } }
export function unlinkQuiet(p) { try { rmSync(p, { force: true }); } catch { clearCounter(p); } }
export function readStdin() {
  try { return readFileSync(0, 'utf8'); } catch { return ''; }
}
export function hookInput() {
  const raw = readStdin();
  if (!raw.trim()) return {};
  try { return JSON.parse(raw); } catch { return { _unparsed: raw }; }
}

// --- change detection ------------------------------------------------------
// Content hashing, not `git status`. Three reasons: it is immune to mtime churn
// from formatters; it does not depend on how a given checkout is configured for
// line endings (this Windows tree reads clean under Git for Windows and dirty
// under a Linux git on the same bytes); and it makes verify-staleness structural
// — a green result carries the hash of the tree it validated, so any write
// invalidates it with nothing to delete by hand.
//
// state.md is EXCLUDED. It is the harness's own working memory and the contract
// requires updating it as the last step of a cycle. If it were hashed, writing
// it after a green verify would immediately make that verify stale, and the
// Stop gate's own release path (which appends a blocker note) would guarantee
// the next turn starts un-green. Working memory must not be able to fail a gate.
export const FINGERPRINT_EXCLUDE = ['.claude/harness/state.md'];
export function trackedFiles() {
  const tracked = git(['ls-files', '-z']).split('\0').filter(Boolean);
  const untracked = git(['ls-files', '--others', '--exclude-standard', '-z']).split('\0').filter(Boolean);
  return [...new Set([...tracked, ...untracked])]
    .filter(f => !FINGERPRINT_EXCLUDE.includes(f))
    .sort();
}
export function fingerprint() {
  const h = createHash('sha256');
  for (const f of trackedFiles()) {
    const abs = join(PROJECT_DIR, f);
    let body = '';
    try { body = createHash('sha256').update(readFileSync(abs)).digest('hex'); }
    catch { body = 'MISSING'; }
    h.update(f).update('\0').update(body).update('\n');
  }
  return h.digest('hex');
}
export function gitHead() {
  try { return git(['rev-parse', 'HEAD']).trim(); } catch { return 'no-head'; }
}

// --- path guardrails -------------------------------------------------------
export function normalizePath(p) {
  if (!p) return '';
  let s = String(p).replace(/\\/g, '/');
  const root = PROJECT_DIR.replace(/\\/g, '/').replace(/\/$/, '');
  if (s.toLowerCase().startsWith(root.toLowerCase() + '/')) s = s.slice(root.length + 1);
  return s.replace(/^\.\//, '');
}
// gitignore-flavoured glob -> RegExp. Supports ** (any depth), * (one segment), ? .
function globToRe(glob) {
  let re = '';
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === '*') {
      if (glob[i + 1] === '*') { re += '.*'; i++; if (glob[i + 1] === '/') i++; }
      else re += '[^/]*';
    } else if (c === '?') re += '[^/]';
    else re += c.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  }
  return new RegExp('^' + re + '$');
}
export function matchGlob(path, glob) {
  const p = normalizePath(path);
  if (globToRe(glob).test(p)) return true;
  // bare-filename patterns match at any depth, like gitignore
  if (!glob.includes('/')) return globToRe('**/' + glob).test(p);
  return false;
}
export function checkPath(rawPath) {
  const p = normalizePath(rawPath);
  if (!p) return { blocked: false };
  let hit = null;
  for (const rule of contract.forbidden_paths) {
    if (rule.startsWith('!')) { if (matchGlob(p, rule.slice(1))) return { blocked: false }; }
    else if (!hit && matchGlob(p, rule)) hit = rule;
  }
  return hit ? { blocked: true, rule: hit, path: p } : { blocked: false, path: p };
}

// --- command guardrails ----------------------------------------------------
const SEPARATORS = /\s*(?:&&|\|\||;|\|&|\||\n|(?<!&)&(?!&))\s*/;
const WRAPPERS = new Set(['timeout', 'time', 'nice', 'nohup', 'stdbuf', 'command', 'builtin', 'noglob', 'xargs', 'sudo', 'env']);
export function splitSegments(cmd) {
  return String(cmd || '').split(SEPARATORS).map(s => s.trim()).filter(Boolean);
}
export function stripWrappers(segment) {
  let s = segment.trim();
  for (let guard = 0; guard < 8; guard++) {
    const before = s;
    s = s.replace(/^[A-Za-z_][A-Za-z0-9_]*=[^\s]*\s+/, '');       // FOO=bar cmd
    const first = s.split(/\s+/)[0];
    if (WRAPPERS.has(first)) s = s.slice(first.length).trim().replace(/^-[^\s]*\s+/, '');
    if (s === before) break;
  }
  return s;
}
export function checkCommand(cmd) {
  const whole = String(cmd || '');
  // Pipe-to-shell and redirection rules must see the WHOLE string; the others
  // are evaluated per segment so `safe && dangerous` cannot smuggle anything.
  const wholeOnly = new Set(['pipe-to-shell', 'chained-harness-edit']);
  for (const rule of contract.forbidden_commands) {
    const re = new RegExp(rule.pattern, 'i');
    if (wholeOnly.has(rule.id)) { if (re.test(whole)) return { blocked: true, rule, matched: whole }; continue; }
    for (const seg of splitSegments(whole)) {
      const bare = stripWrappers(seg);
      if (re.test(seg) || re.test(bare)) return { blocked: true, rule, matched: seg };
    }
  }
  // Redirection targets are file writes; check them against forbidden paths.
  for (const m of whole.matchAll(/(?:^|\s)\d?>>?\s*("[^"]+"|'[^']+'|[^\s|&;]+)/g)) {
    const target = m[1].replace(/^["']|["']$/g, '');
    if (target === '/dev/null' || target === 'NUL') continue;
    const r = checkPath(target);
    if (r.blocked) return { blocked: true, rule: { id: 'redirect-to-forbidden-path', why: `redirects output into ${r.rule}`, instead: 'write somewhere the contract allows' }, matched: target };
  }
  return { blocked: false };
}

// --- budget (organ 4): tool calls per objective ----------------------------
export function currentObjective() {
  try {
    const m = readFileSync(P.state, 'utf8').replace(/\r\n/g, '\n')
      .match(/##\s*Current objective\s*\n+([^\n]*)/i);
    return (m && m[1].trim()) || '(none recorded)';
  } catch { return '(none recorded)'; }
}
export function bumpBudget(delta = 1) {
  const objective = currentObjective();
  let b = readJson(P.budget, null);
  if (!b || b.objective !== objective) b = { objective, count: 0, since: new Date().toISOString() };
  b.count += delta;
  b.limit = contract.max_tool_calls_per_objective;
  writeJson(P.budget, b);
  return b;
}
export function readBudget() {
  const objective = currentObjective();
  const b = readJson(P.budget, null);
  if (!b || b.objective !== objective) return { objective, count: 0, limit: contract.max_tool_calls_per_objective };
  return { ...b, limit: contract.max_tool_calls_per_objective };
}
export function resetCounters() {
  for (const p of [P.budget, P.stopAttempts]) clearCounter(p);
  try { writeJson(P.compactFlush, { blocked: false }); } catch { /* ignore */ }
}

// --- verify freshness ------------------------------------------------------
export function lastVerify() { return readJson(P.lastVerify, null); }
export function verifyIsGreenForTree(fp) {
  const lv = lastVerify();
  if (!lv) return { ok: false, why: 'no verify has run in this tree' };
  if (lv.exitCode !== 0) return { ok: false, why: `last verify FAILED at step "${lv.failedStep || '?'}"` };
  if (lv.fingerprint !== fp) return { ok: false, why: 'last verify is stale — the tree changed after it ran' };
  return { ok: true, lv };
}

// --- CLI -------------------------------------------------------------------
if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const [, , cmd, ...rest] = process.argv;
  const arg = rest.join(' ');
  if (cmd === 'check-path') { const r = checkPath(arg); console.log(JSON.stringify(r)); process.exit(r.blocked ? 2 : 0); }
  else if (cmd === 'check-command') { const r = checkCommand(arg); console.log(JSON.stringify(r)); process.exit(r.blocked ? 2 : 0); }
  else if (cmd === 'fingerprint') console.log(fingerprint());
  else if (cmd === 'budget') console.log(JSON.stringify(readBudget()));
  else if (cmd === 'reset') { resetCounters(); console.log('counters cleared'); }
  else { console.log('usage: node guardrails.mjs <check-path|check-command|fingerprint|budget|reset> [arg]'); process.exit(1); }
}
