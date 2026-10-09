# Isolated instance

Too many daemons on one Chrome's single debug port is its own failure mode. Past roughly a dozen, new CDP handshakes start
timing out — consistently, for ten minutes at a stretch. A distinct `BU_NAME` does not help, because
every daemon still dials the same port on the same process.

The fix is a second Chrome: its own process, its own profile, its own port.

```bash
harness-iso <<'PY'
print(list_tabs())
PY
```

The script is `harness-iso` in the repo root. Put it on your `PATH` once, e.g.
`ln -s "$PWD/harness-iso" ~/.local/bin/harness-iso`.

`harness-iso` resolves the websocket from the port and execs `browser-harness`. Everything else —
`new_tab()`, `js()`, `screenshot()` — behaves exactly as normal.

## Launching it

One command, once per Chrome lifetime:

```bash
open -na "Google Chrome" --args \
  --remote-debugging-port=9333 \
  --user-data-dir="$HOME/.chrome-harness-profile" \
  --no-first-run --no-default-browser-check \
  "https://example.com"
```

- `-na` forces a genuinely new process. Without `-n` you get another window of the contended one.
- `--user-data-dir` is what makes it a separate browser: its own cookie jar, its own logins.
- Any free port. `harness-iso` defaults to 9333; `BU_ISO_PORT` overrides.

**The profile directory must be persistent.** macOS clears `/private/tmp` on boot, and this profile
holds both the signed-in sessions and the remote-debugging grant below — neither of which a script
can recreate. Keep it under `$HOME`.

## Gotchas

- **The flag alone is not enough on a fresh profile.** Chrome 144+ ignores `--remote-debugging-port`
  from the command line until a human opens `chrome://inspect/#remote-debugging` in that window and
  ticks "Allow remote debugging for this browser instance". It then sticks for the life of that
  `--user-data-dir`. This cannot be automated: computer-use grants browsers read-only access, and the
  harness cannot attach before the port exists. Ask the user; it is a one-time click.
- **Do not wait on `DevToolsActivePort`.** It is what `daemon.py:get_ws_url()` reads, and for a
  manually flagged instance it never reliably lands on disk. Read the HTTP endpoint instead — this
  instance *does* serve it, even though the main Chrome now 404s on `/json/version`:

  ```bash
  curl -s http://127.0.0.1:9333/json/version   # -> webSocketDebuggerUrl
  ```

- **File discovery can never find this instance**, so `BU_CDP_WS` is mandatory, not merely faster:
  `PROFILES` is a fixed list of stock install paths and a custom `--user-data-dir` is not in it.
- **`BU_CDP_WS` binds once, at daemon birth.** `ensure_daemon()` returns early when the socket is
  live, so exporting a fresh URL past a running daemon is silently ignored. Chrome mints a new browser
  id every launch, so a daemon that outlives its Chrome dials a dead id until you kill it.
  `harness-iso` compares the daemon's env against the resolved URL and retires it when they differ.
- **Each Chrome is a separate cookie jar.** A site logged in on the main Chrome is logged out here.
  That is the point, but it means "it asked me to sign in" is expected, not a bug.

## Doing it by hand

`harness-iso` is two env vars. When you need them inline:

```bash
BU_NAME=iso \
BU_CDP_WS="$(curl -s http://127.0.0.1:9333/json/version | python3 -c 'import sys,json;print(json.load(sys.stdin)["webSocketDebuggerUrl"])')" \
browser-harness <<'PY'
print(page_info())
PY
```
