# Changelog

## 0.1.14

### Captchas
- `solve_captcha()`: on a Browser Use Cloud browser, waits for the built-in captcha solver on the current tab and returns `{solved, detail, seconds}`: `solved`, `still solving` (call again), `the solver failed`, `no captcha solve started`, or `solver unavailable` on a local browser (never raises). After a solve it names the page that was solved, so the agent re-checks for a second challenge.
- Script output ends with `[Captcha solver ...]` lines while a solve runs and once when it finishes, so CLI agents see it without asking. `captcha_note()` returns the same line for embedding code.
- MCP: new `browser_solve_captcha` tool. Captcha notes come in their own text block, so the JSON block still parses.
- Off switch: `BU_CAPTCHA_SOLVER=off` keeps the solver off for that caller; `solve_captcha()` then returns `solver unavailable`.

### Pages and HTTP
- `page_info()` right after `new_tab(url)` / `goto_url(url)` waits for the new document instead of throwing on a null `<html>`.
- `http_get()` returns `bytes` for binary bodies (zip, pdf, image) and `str` for text, on both the local and the fetch-use path. Localhost, private and intranet hosts, and requests with `Authorization`/`Cookie` headers, never go through the fetch-use proxy.
- `new_tab(url)` prints `new_tab: <targetId> <url>`, so a script that only opens a tab no longer looks like it did nothing.
- Navigation and `js()` wait up to 30 s for the browser instead of 5 s. `BH_IPC_TIMEOUT=<seconds>` raises that on very slow remote browsers. Other calls keep 5 s, so a dead daemon still fails fast.
- `wait_for_network_idle()` no longer runs to its 10 s cap on pages with an ad, captcha or chat iframe or a Web Worker: it stops waiting for requests that finish on another target.

### Daemon
- IPC requests up to 32 MiB (a 10 MB upload as base64), with a clear error above that instead of a broken pipe.
- The daemon exits when its CDP connection closes, on SIGTERM/SIGHUP (stopping its cloud browser), and when `BH_OWNER_PID` dies.
- After a remote daemon ends, a local call under the same name fails with `remote-browser-ended` instead of starting local Chrome under it.
- `ensure_daemon` refuses a live daemon attached to a different CDP endpoint (`cdp-mismatch`) instead of silently driving the other browser.
- Opt-in idle exit: `BH_IDLE_TIMEOUT=<seconds>`. A daemon spawned with `BH_OWNS_BROWSER=1` defaults to 30 min and closes the browser it launched. Default unchanged: never exits, never closes a user's Chrome.
- Daemon files are always `bu-<name>.*`, also under `BH_RUNTIME_DIR`.
- A daemon that crashed or was killed under the process that started it is started again at once, instead of being waited on for 60 s as a daemon "still starting" (it was an unreaped zombie with the same pid and start time).
- Clients before 0.1.14 (protocol 2, `set_session` after a raw attach) keep working on a 0.1.14 daemon: `set_session` takes the tab like `switch_tab`.
- `Browser.download*` events reported on a `Target.attachToBrowserTarget` session reach the owner of the tab the download came from.

### macOS and local Chrome
- Cold start: with Chrome closed, the harness launches it in the background (`open -g`) and pre-ticks chrome://inspect's "Allow remote debugging for this browser instance" in Local State (never-set pref only; `BH_PRESET_INSPECT_TOGGLE=0` disables). Chrome's one "Allow remote debugging?" dialog per Chrome run remains; the daemon retries the 403 Chrome sends before it has a window.
- `mac-approve` returns `accessibility-required` at once instead of hanging on macOS's consent prompt, matches the Chrome 153+ sheet (title in a heading), and works for Chrome Canary/Beta/Dev, Chromium, Brave, Edge, Arc and the other launchable browsers.

### Many agents, one Chrome
- Agents share one local Chrome through one daemon and each drives only its own tabs (`BH_OWNER`, else the host session id). Another agent's tab fails with `tab-taken`; a lost tab is `tab-closed`, never silently another tab. New: `name_session`, `mark_tab`, `release_tabs`, `list_browsers`, `use_browser`; idle tabs are given back after `BH_OWNER_IDLE` (30 min) and `BH_OWNER_FORGET` (24 h).
- One "Allow remote debugging?" per Chrome run: one daemon per browser, started under a lock; `--update` no longer restarts it; a `BU_NAME` with no browser of its own becomes an owner instead of a second connection (`BH_NAMED_LOCAL_DAEMON=1` for a separate one). Sub-agents need their own `BH_OWNER`.

### For tools that embed the harness
- `BH_CLI_NAME` / `run.main(prog=...)`: help, usage and hint text name the wrapping CLI (for example `browser-use`) instead of `browser-harness`.
- `telemetry.set_sink(...)`: an embedding CLI sends harness telemetry through its own pipeline and consent setting.

### Dependencies and docs
- Pillow 12.3.0 -> 13.0.0 (fixes five published advisories).
- install.md: `remote-debugging-setup` errors from the `browser-use` CLI mean upgrade browser-use to 1.0.3+.

### Behavior changes to know
- `http_get()` can now return `bytes`. Code that assumed `str` for a binary URL must handle it.
- `new_tab()` prints one line to stdout. Code that parses all of stdout as JSON must skip it.
