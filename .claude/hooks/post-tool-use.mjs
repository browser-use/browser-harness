#!/usr/bin/env node
// ORGAN 7 (trace) + deterministic fixups.
// Everything here is something you would otherwise nag the model about in a prompt.
// PostToolUse stderr is shown to Claude regardless of exit code.
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { hookInput, normalizePath, PROJECT_DIR, P } from '../harness/guardrails.mjs';
import { traceTool } from '../harness/trace.mjs';

const input = hookInput();
const tool = input.tool_name || '';
const ti = input.tool_input || {};
const target = ti.file_path || ti.notebook_path || ti.command || '';
const resp = typeof input.tool_response === 'string' ? input.tool_response : JSON.stringify(input.tool_response ?? '');
const failed = /^(error|Error)|is_error|"error"/.test(resp || '');

traceTool({ tool, target, outcome: failed ? 'error' : 'ok', detail: failed ? resp : undefined, session: input.session_id });

// .last-verify carries the fingerprint of the tree it validated, so any write
// invalidates it automatically at the Stop gate. Nothing to delete here.

const rel = normalizePath(ti.file_path || ti.notebook_path || '');
const problems = [];
if (rel && /^(Edit|Write|MultiEdit|NotebookEdit)$/.test(tool) && existsSync(join(PROJECT_DIR, rel))) {
  if (rel.endsWith('.md')) {
    const r = spawnSync(process.execPath, [resolve(P.contract, '..', 'validate-skills.mjs'), rel], { cwd: PROJECT_DIR, encoding: 'utf8' });
    if (r.status !== 0) problems.push(`skill structure:\n${(r.stderr || r.stdout || '').trim()}`);
  } else if (rel.endsWith('.py')) {
    for (const cand of [process.env.HARNESS_PYTHON, 'python3', 'python']) {
      if (!cand) continue;
      const probe = spawnSync(cand, ['--version'], { encoding: 'utf8' });
      if (probe.status !== 0) continue;
      const r = spawnSync(cand, ['-m', 'py_compile', rel], { cwd: PROJECT_DIR, encoding: 'utf8' });
      if (r.status !== 0) problems.push(`python syntax:\n${(r.stderr || r.stdout || '').trim()}`);
      break;
    }
  }
}

if (problems.length) {
  console.error(`HARNESS — the file you just wrote does not pass its structural check:\n\n${problems.join('\n\n')}\n\nFix ${rel} before doing anything else. This is the same check the verify gate runs, so it will block completion too.`);
  process.exit(2);
}
process.exit(0);
