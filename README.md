# Browser Harness

The simplest, thinnest, and most powerful harness to control your real browser with your agent.

This repo makes you never use your browser again.

## Setup prompt

Paste this into Claude Code or Codex:

```text
Set up https://github.com/browser-use/harnessless for me.

Read `SKILL.md` and follow its instructions to install and connect this repo to my real browser.

After it is installed, if I am already logged in to GitHub, star this repository as a small verification task.
```


## Example task

```text
Star this repository.
```


## How It Works

- `SKILL.md` (~100 lines) explains how the harness should be used.
- `run.py` (~4 lines) executes plain Python with helpers preloaded.
- `helpers.py` (~260 lines) holds the primitives the agent calls and constantly modifies to sharpen its own harness.
- `daemon.py` (~200 lines) keeps the CDP websocket and socket bridge alive.


## Get inspiration

See [domain-skills/](domain-skills/) for examples on other websites.


## Optional: Remote browsers

Useful for sub-agents or deployment.

- Get a Browser Use API key: [cloud.browser-use.com/new-api-key](https://cloud.browser-use.com/new-api-key)
- The agent can also sign up by itself by fetching [docs.browser-use.com/llms.txt](https://docs.browser-use.com/llms.txt), which contains the setup flow and challenge context for getting a Browser Use API key.
