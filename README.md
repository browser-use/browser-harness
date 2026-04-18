![Browser Harness](https://r2.browser-use.com/github/harness-banner.png)

# Browser Harness

The simplest, thinnest, and most powerful harness to control your real browser with your agent.

## Setup prompt

```text
Set up https://github.com/browser-use/browser-harness for me.

Read `install.md` first to install and connect this repo to my real browser. Then read `SKILL.md` for normal usage. Always read `helpers.py` because that is where the functions are. When you open a setup or verification tab, activate it so I can see the active browser tab. After it is installed, if I am already logged in to GitHub, star this repository as a small verification task; if I am not logged in, just go to browser-use.com.
```

When this page appears tick the checkbox so the agent can connect to the real browser.

<img src="docs/setup-remote-debugging.png" alt="Remote debugging setup" width="520" style="border-radius: 12px;" />

<br><br>

## Example task

```text
Star this repository.
```

See [domain-skills/](domain-skills/) for examples on other websites.

<br><br>

## Code Structure

- `install.md` explains first-time install and browser bootstrap.
- `SKILL.md` explains day-to-day browser harness usage.
- `run.py` (~13 lines) executes plain Python with helpers preloaded.
- `helpers.py` (~192 lines) holds the starting tool calls to interact with the browser and can be modified by the agent.
- `admin.py` (~139 lines) holds daemon bootstrap and optional remote-browser helpers.
- `daemon.py` (~220 lines) keeps the CDP websocket and socket bridge alive.

<br><br>

## Optional: Remote browsers

Useful for sub-agents or deployment.

- Get a Browser Use API key: [cloud.browser-use.com/new-api-key](https://cloud.browser-use.com/new-api-key)
- The agent can also sign up by itself by fetching [docs.browser-use.com/llms.txt](https://docs.browser-use.com/llms.txt), which contains the setup flow and challenge context for getting a Browser Use API key.
