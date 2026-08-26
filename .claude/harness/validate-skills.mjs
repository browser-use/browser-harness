#!/usr/bin/env node
// Verify step "skills" — deterministic structural validation of the Markdown corpus.
// 89 of this repo's tracked files are Markdown skills and nothing else checks them.
// Every rule below was measured green against the tree before being added.
//
// Two profiles:
//   corpus   — SKILL.md, install.md, README.md, domain-skills/**, interaction-skills/**, docs/**
//              (the product: frontmatter needs name+description, body opens with an H1)
//   config   — .claude/**  (commands and subagents: frontmatter needs a description,
//              and legitimately has no H1 and often no name)
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PROJECT_DIR, git, normalizePath } from './guardrails.mjs';

const EXEMPT_H1 = new Set(['README.md']);            // opens with an <img> banner
const NAME_REQUIRED = /^(SKILL\.md|\.claude\/agents\/[^/]+\.md)$/;
const REF_RE = /(?:^|[\s(`"'])((?:domain-skills|interaction-skills|docs)\/[A-Za-z0-9._\/-]+\.(?:md|png|py))/g;

export function allMarkdown() {
  const tracked = git(['ls-files', '-z', '*.md']).split('\0').filter(Boolean);
  const untracked = git(['ls-files', '--others', '--exclude-standard', '-z', '*.md']).split('\0').filter(Boolean);
  return [...new Set([...tracked, ...untracked])].sort();
}

export function validate(only = null) {
  const errors = [];
  const files = (only && only.length ? only.map(normalizePath) : allMarkdown()).filter(f => f.endsWith('.md'));
  for (const f of files) {
    const isConfig = f.startsWith('.claude/');
    let raw;
    try { raw = readFileSync(join(PROJECT_DIR, f), 'utf8'); }
    catch { continue; }                                 // deleted between listing and read
    const text = raw.replace(/\r\n/g, '\n');            // the tree is CRLF; normalise first
    const lines = text.split('\n');
    const err = (msg) => errors.push({ file: f, msg });

    if (!text.trim()) { err('file is empty'); continue; }

    // 1. Frontmatter, when present, must be closed and carry its required keys.
    let bodyStart = 0;
    if (lines[0].trim() === '---') {
      const close = lines.slice(1).findIndex(l => l.trim() === '---');
      if (close === -1) err('YAML frontmatter is opened but never closed');
      else {
        const fm = lines.slice(1, close + 1);
        bodyStart = close + 2;
        const need = (isConfig && !NAME_REQUIRED.test(f)) ? ['description'] : ['name', 'description'];
        for (const key of need) {
          const line = fm.find(l => new RegExp(`^${key}\\s*:`).test(l.trim()));
          if (!line) err(`frontmatter is missing required key "${key}"`);
          else if (!line.split(':').slice(1).join(':').trim()) err(`frontmatter key "${key}" is empty`);
        }
        const nameLine = fm.find(l => /^name\s*:/.test(l.trim()));
        if (nameLine) {
          const v = nameLine.split(':').slice(1).join(':').trim().replace(/^["']|["']$/g, '');
          if (v && !/^[a-z0-9][a-z0-9-]*$/.test(v)) err(`frontmatter name "${v}" is not lowercase-kebab`);
        }
      }
    } else if (NAME_REQUIRED.test(f)) {
      err('this file requires YAML frontmatter with name and description');
    }

    // 2. A corpus document must open with a single H1 title. Commands and subagents
    //    under .claude/ legitimately open with prose, so they are exempt.
    if (!isConfig && !EXEMPT_H1.has(f)) {
      const first = lines.slice(bodyStart).find(l => l.trim() !== '') || '';
      if (!/^#\s+\S/.test(first)) err(`first content line is not an H1 title (found: ${JSON.stringify(first.slice(0, 60))})`);
    }

    // 3. Every fenced code block must be closed — an unclosed fence silently swallows
    //    the rest of the skill when the model reads it.
    const fences = (text.match(/^```/gm) || []).length;
    if (fences % 2 !== 0) err(`unbalanced code fences (${fences} \`\`\` markers)`);

    // 4. Every reference to another skill/doc file must resolve on disk.
    for (const m of text.matchAll(REF_RE)) {
      try { readFileSync(join(PROJECT_DIR, m[1])); }
      catch { err(`dead reference to "${m[1]}"`); }
    }
  }
  return { errors, count: files.length };
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const { errors, count } = validate(process.argv.slice(2));
  if (!errors.length) { console.log(`skills: OK (${count} markdown file${count === 1 ? '' : 's'})`); process.exit(0); }
  for (const e of errors) console.error(`  ${e.file}: ${e.msg}`);
  console.error(`skills: ${errors.length} problem(s) in ${count} file(s)`);
  process.exit(1);
}
