<img src="https://raw.githubusercontent.com/browser-use/media/main/browser-harness/banner-ink.svg" alt="Browser Harness" width="100%" />

# Browser Harness ♞

Connect an LLM directly to your real browser with a thin, editable CDP harness. For browser tasks where you need **complete freedom**.

One websocket to Chrome, nothing between. The agent writes what's missing during execution. The harness improves itself every run.

Try browser-harness in [Browser Use Cloud](https://cloud.browser-use.com/v4?utm_campaign=browser-harness-use-in-cloud&utm_source=github) or paste the setup prompt into your coding agent.

```
  ● agent: wants to upload a file
  │
  ● agent-workspace/agent_helpers.py → helper missing
  │
  ● agent writes it                         agent_helpers.py
  │                                                       + custom helper
  ✓ file uploaded
```

**You will never use the browser again.**

## Setup prompt

Paste into Claude Code or Codex:

```text
Install or upgrade browser-harness to the latest stable version with uv using Python 3.12, register the skill from `browser-harness skill`, and connect it to my browser. Follow https://github.com/browser-use/browser-harness/blob/main/install.md if setup or connection fails.
```

The agent will open `chrome://inspect/#remote-debugging`. Tick the checkbox so the agent can connect to your browser:

<img src="docs/setup-remote-debugging.png" alt="Remote debugging setup" width="520" style="border-radius: 12px;" />

Click Allow when the per-attach popup appears (Chrome 144+):

<img src="docs/allow-remote-debugging.png" alt="Allow remote debugging popup" width="520" style="border-radius: 12px;" />

See [agent-workspace/domain-skills/](agent-workspace/domain-skills/) for example tasks.

## Built-in agent (Browser Harness TUI)

Browser Harness ships its own agent: a fork of OpenAI Codex with a Terminal-style
TUI and native browser-harness tool integration, published at
[browser-use/browser-harness-tui](https://github.com/browser-use/browser-harness-tui).

### Run it now (from this branch)

This agent lives on the `codex-embed-browser-harness` branch (not yet on PyPI), so
run it straight from a checkout. Prereqs: **Python ≥ 3.11**, [`uv`](https://docs.astral.sh/uv/),
and a Chrome to drive (local, or a Browser Use Cloud browser).

```bash
# 1. Get this branch
git clone -b codex-embed-browser-harness https://github.com/browser-use/browser-harness
cd browser-harness

# 2. Install the package into a venv
uv sync            # (or: python3.11 -m venv .venv && .venv/bin/pip install -e .)

# 3. Launch the TUI — the first run auto-downloads the prebuilt agent binary
#    for your platform (~86 MB, cached under ~/.browser-harness/agent-bin/).
#    From a checkout, ./browser-harness runs the working tree directly:
./browser-harness tui
#    or dispatch a task headlessly:
./browser-harness agent "open example.com and tell me the page title"
```

Prebuilt binaries are published for **macOS (Apple Silicon & Intel)** and **Linux
(x86_64 & arm64)** — the download is auto-selected for your platform, so there's no
toolchain and no long build.

**Authenticate the agent (one-time).** The agent is a Codex fork, so it signs in
exactly like Codex — either a ChatGPT login or an API key. After the first run has
downloaded the binary:

```bash
# ChatGPT sign-in (opens a browser):
~/.browser-harness/agent-bin/agent-v0.1.0/codex login
# …or use an API key instead:
export OPENAI_API_KEY=sk-...
```

If you already use OpenAI Codex on this machine, its `~/.codex` login is reused —
no separate sign-in needed.

**Connect a browser.** Local Chrome must expose CDP: open
`chrome://inspect/#remote-debugging`, tick *Allow remote debugging for this browser
instance* (and click Allow on the Chrome 144+ popup), then rerun the command. Run
`browser-harness --doctor` to diagnose connection issues. For headless servers or
parallel runs, use a Browser Use Cloud browser instead (see below).

Both commands create an isolated browser-harness run workspace, present the
browser-harness skill, and make `./bin/browser-harness` available to the agent
inside that workspace.

Once this branch is released to PyPI, the same commands work as `browser-harness
tui` / `browser-harness agent "…"` from any install.

### Building from source (optional)

The agent is vendored as the [`codex-agent`](codex-agent) git submodule. A
locally-built binary takes precedence over the download, so contributors can:

```bash
git submodule update --init
cd codex-agent/codex-rs && cargo build --release -p codex-cli && cd ../..
```

Resolution order for the agent binary: explicit `--codex-bin` → a locally-built
submodule binary → the cached/downloaded prebuilt release. No environment
variables, no sibling-directory guessing.

## Free Browser Use Cloud browsers

Stealth, sub-agents, or headless deployment.<br>
**Browser Use Cloud free tier: 3 concurrent browsers, proxies, captcha solving, and more. No card required.**

- Grab a key at [cloud.browser-use.com/new-api-key](https://cloud.browser-use.com/new-api-key)
- Or let the agent sign up itself via [docs.browser-use.com/llms.txt](https://docs.browser-use.com/llms.txt) (setup flow + challenge context included).

## Architecture (~1k lines across 4 core files)

- `install.md` — first-time install and browser bootstrap
- `SKILL.md` — day-to-day usage
- `src/browser_harness/` — protected core package
- `${XDG_CONFIG_HOME:-~/.config}/browser-harness/agent-workspace/agent_helpers.py` — helper code the agent edits
- `${XDG_CONFIG_HOME:-~/.config}/browser-harness/agent-workspace/domain-skills/` — reusable site-specific skills the agent edits

Plain `browser-harness` helper calls attach to the running Chrome/Chromium CDP endpoint. For isolated automation, launch Chrome yourself with `--remote-debugging-port` and pass `BU_CDP_URL`, or use a Browser Use cloud browser.

## Development

From a checkout, use `./browser-harness` to run the current working tree without activating a virtualenv or depending on the globally installed command:

```bash
./browser-harness <<'PY'
print(page_info())
PY
```

Normal agent-facing docs should keep using `browser-harness`; the `./browser-harness` launcher is only for local repo testing.

## Contributing

PRs and improvements welcome. The best way to help: **contribute a new domain skill** under [agent-workspace/domain-skills/](agent-workspace/domain-skills/) for a site or task you use often (LinkedIn outreach, ordering on Amazon, filing expenses, etc.). Each skill teaches the agent the selectors, flows, and edge cases it would otherwise have to rediscover.

- **Skills are written by the harness, not by you.** Just run your task with the agent — when it figures something non-obvious out, it files the skill itself (see [SKILL.md](SKILL.md)). Please don't hand-author skill files; agent-generated ones reflect what actually works in the browser.
- Open a PR with the generated `domain-skills/<site>/` folder copied into this repo's `agent-workspace/domain-skills/` examples — small and focused is great.
- Bug fixes, docs tweaks, and helper improvements are equally welcome.
- Browse existing skills (`github/`, `linkedin/`, `amazon/`, ...) to see the shape.

If you're not sure where to start, open an issue and we'll point you somewhere useful.

## Domain skills

Set `BH_DOMAIN_SKILLS=1` to enable domain skills from the agent workspace. This repo's [agent-workspace/domain-skills/](agent-workspace/domain-skills/) directory contains examples to contribute via PR.

---

[The Bitter Lesson of Agent Harnesses](https://browser-use.com/posts/bitter-lesson-agent-harnesses) · [Web Agents That Actually Learn](https://browser-use.com/posts/web-agents-that-actually-learn)
