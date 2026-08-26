#!/usr/bin/env node
// ORGAN 6 — THE GATE. Deterministic, executable, exit-code driven.
// A human running `node .claude/harness/verify.mjs` gets the identical answer.
// No model is involved anywhere in this file.
import { spawnSync } from 'node:child_process';
import { existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { PROJECT_DIR, P, contract, git, fingerprint, gitHead } from './guardrails.mjs';
import { trace } from './trace.mjs';

const TAIL = 30;
const isWin = process.platform === 'win32';

function run(cmd, args) {
  const r = spawnSync(cmd, args, { cwd: PROJECT_DIR, encoding: 'utf8', shell: false });
  return { code: r.status === null ? 1 : r.status, out: `${r.stdout || ''}${r.stderr || ''}`, error: r.error };
}

// Interpreter discovery — the reason this gate is portable. Never assume `python`.
function findPython() {
  const candidates = [];
  if (process.env.HARNESS_PYTHON) candidates.push([process.env.HARNESS_PYTHON, []]);
  candidates.push(
    [join(PROJECT_DIR, '.venv', isWin ? 'Scripts' : 'bin', isWin ? 'python.exe' : 'python'), []],
    ['python3', []], ['python', []],
  );
  if (isWin) candidates.push(['py', ['-3']]);
  for (const [cmd, pre] of candidates) {
    if (cmd.includes('/') || cmd.includes('\\')) { if (!existsSync(cmd)) continue; }
    const r = run(cmd, [...pre, '--version']);
    if (r.code === 0) return { cmd, pre, version: r.out.trim() };
  }
  return null;
}

const py = findPython();
const pyFiles = git(['ls-files', '*.py']).trim().split('\n').filter(Boolean);

const STEPS = {
  // cheapest first, fail fast
  skills: () => run(process.execPath, [join(P.contract, '..', 'validate-skills.mjs')]),
  compile: () => py
    ? run(py.cmd, [...py.pre, '-m', 'compileall', '-q', ...pyFiles])
    : { code: 1, out: 'no Python interpreter found (tried $HARNESS_PYTHON, .venv, python3, python, py -3)' },
  tests: () => {
    if (!py) return { code: 1, out: 'no Python interpreter found' };
    const probe = run(py.cmd, [...py.pre, '-c', 'import pytest']);
    if (probe.code !== 0) return { code: 1, out: `pytest is not installed for ${py.cmd}.\nInstall it with:  uv sync --group dev\n           or:  ${py.cmd} -m pip install pytest\n(pytest is declared in pyproject.toml under [dependency-groups] dev)` };
    return run(py.cmd, [...py.pre, '-m', 'pytest', '-q']);
  },
};

const results = [];
let failedStep = null;
console.log(`verify: ${contract.verify_steps.join(' -> ')}   [python: ${py ? `${py.cmd} ${py.version}` : 'NOT FOUND'}]`);
for (const name of contract.verify_steps) {
  const step = STEPS[name];
  if (!step) { console.error(`verify: unknown step "${name}" in contract.json`); failedStep = name; results.push({ name, code: 1 }); break; }
  const started = Date.now();
  const r = step();
  results.push({ name, code: r.code, ms: Date.now() - started });
  if (r.code === 0) { console.log(`  PASS  ${name} (${Date.now() - started}ms)`); continue; }
  failedStep = name;
  console.error(`  FAIL  ${name} (exit ${r.code})`);
  console.error('  ---- last ' + TAIL + ' lines ----');
  for (const line of (r.out || '(no output)').replace(/\r\n/g, '\n').split('\n').slice(-TAIL)) console.error('  ' + line);
  console.error('  --------------------------');
  break; // fail fast
}

const exitCode = failedStep ? 1 : 0;
const record = {
  exitCode, failedStep, steps: results,
  fingerprint: fingerprint(), head: gitHead(),
  python: py ? `${py.cmd} ${py.version}` : null,
  timestamp: new Date().toISOString(),
};
writeFileSync(P.lastVerify, JSON.stringify(record, null, 2) + '\n');
trace({ kind: 'verify', exitCode, failedStep, steps: results.map(s => `${s.name}:${s.code}`) });

console.log(exitCode === 0
  ? `verify: PASS (exit 0)  fingerprint ${record.fingerprint.slice(0, 12)}`
  : `verify: FAIL (exit 1) at step "${failedStep}"`);
process.exit(exitCode);
