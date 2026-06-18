# browser-harness — Codex plugin

This directory packages the browser-harness skill for **Codex**. Install with:

```bash
codex plugin marketplace add browser-use/browser-harness
codex plugin add browser-harness@browser-harness
```

It still needs the `browser-harness` **CLI** (a one-time `uv`/pip install — see `install.md`
at the repo root). The plugin ships the skill; the CLI is the tool it drives.

## Why the skill is duplicated here

Codex requires a plugin to be a self-contained subdirectory with `skills/<name>/SKILL.md`
(it copies the directory into its cache), so the skill can't point back at the repo's root
`SKILL.md` the way the Claude plugin does. **The canonical skill is the repo-root `SKILL.md`;
`skills/browser/SKILL.md` here is a copy.** Keep them in sync until a build step generates this
copy automatically.
