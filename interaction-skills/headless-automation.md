# Headless automation

The default setup in `install.md` assumes a user is sitting at the machine to launch Chrome, tick the `chrome://inspect/#remote-debugging` checkbox once, and click `Allow` if it appears. For unattended jobs (cron, launchd, systemd) there is no one to click anything. This file documents the setup that makes the harness work end-to-end with zero interactive input.

## Three things to know

### 1. Chrome 148+ silently ignores `--remote-debugging-port` on the default profile

Chromium added a hardening that drops the debug-port flag whenever `--user-data-dir` is the OS default location. Chrome logs one line on stderr and continues without opening the port:

```
DevTools remote debugging requires a non-default data directory. Specify this using --user-data-dir.
```

Workaround: always pass `--user-data-dir` pointing somewhere other than the default. A sibling directory next to the normal profile is fine.

### 2. `--headless=new` does not write `DevToolsActivePort`

The harness discovers Chrome via the `DevToolsActivePort` file the GUI Chrome drops in its user-data-dir. Headless Chrome opens the debug port but never writes that file, so the harness's discovery loop falls through and reports `DevToolsActivePort not found`.

Workaround: synthesise the file yourself after Chrome is up. Poll `http://127.0.0.1:<port>/json/version`, take the `webSocketDebuggerUrl` it returns, and write a two-line `DevToolsActivePort` of `<port>\n<ws-path>\n` into the user-data-dir.

### 3. A fresh user-data-dir has no logins

A new profile dir means Twitter, LinkedIn, AngelList, etc. all log you out. The pragmatic fix is to clone your everyday profile once:

```bash
# do this with the GUI Chrome fully quit, otherwise SingletonLock breaks
ditto "$HOME/Library/Application Support/Google/Chrome" \
      "$HOME/Library/Application Support/Google/Chrome-CDP"
rm -f "$HOME/Library/Application Support/Google/Chrome-CDP/SingletonLock" \
      "$HOME/Library/Application Support/Google/Chrome-CDP/SingletonCookie" \
      "$HOME/Library/Application Support/Google/Chrome-CDP/SingletonSocket"
```

Caveats:
- Cookies drift over time. Sites with short session windows (LinkedIn, Twitter) will log out of the cloned profile every few months. Re-clone when that happens, or launch the cloned profile non-headless once to log in manually.
- The harness already supports `BU_CDP_WS` as an explicit override if you don't want to write `DevToolsActivePort` at all; the synthesis approach is just easier to wire into a launchd plist that doesn't get to see env vars set at runtime.

## Make the harness find the dedicated profile

Add the cloned dir to `PROFILES` in `daemon.py`. Order matters: put it first so a stale `DevToolsActivePort` left in the default Chrome profile (from a previous interactive session) doesn't shadow the headless one.

```python
PROFILES = [
    Path.home() / "Library/Application Support/Google/Chrome-CDP",
    Path.home() / "Library/Application Support/Google/Chrome",
    # ...
]
```

## Launcher script

A small wrapper does Chrome startup + `DevToolsActivePort` synthesis in one process. launchd/systemd run this; the harness picks up Chrome through the file.

```bash
#!/bin/bash
set -u
PROFILE="$HOME/Library/Application Support/Google/Chrome-CDP"
PORT=9222
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

: > "$PROFILE/DevToolsActivePort"           # clear any stale value

"$CHROME" \
  --user-data-dir="$PROFILE" \
  --headless=new \
  --remote-debugging-port="$PORT" \
  --remote-allow-origins=* \
  --no-first-run --no-default-browser-check &
CHROME_PID=$!
trap 'kill -TERM "$CHROME_PID" 2>/dev/null; wait "$CHROME_PID"; exit' INT TERM

WS_PATH=""
for _ in $(seq 1 60); do
  WS_PATH=$(curl -sf --max-time 1 "http://127.0.0.1:$PORT/json/version" \
    | /usr/bin/python3 -c 'import json,sys,urllib.parse as u; print(u.urlparse(json.load(sys.stdin)["webSocketDebuggerUrl"]).path)' 2>/dev/null) \
    && [ -n "$WS_PATH" ] && break
  sleep 0.5
done
[ -n "$WS_PATH" ] && printf '%s\n%s\n' "$PORT" "$WS_PATH" > "$PROFILE/DevToolsActivePort"

wait "$CHROME_PID"
```

## macOS launchd worked example

Drop the wrapper at `~/.local/bin/chrome-cdp-launcher.sh` (`chmod +x`) and the plist below at `~/Library/LaunchAgents/com.you.chrome-cdp.plist`. Bootstrap with `launchctl bootstrap "gui/$(id -u)" <plist>`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>           <string>com.you.chrome-cdp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOU/.local/bin/chrome-cdp-launcher.sh</string>
    </array>
    <key>RunAtLoad</key>       <true/>
    <key>KeepAlive</key>       <true/>
    <key>ThrottleInterval</key><integer>60</integer>
    <key>StandardOutPath</key> <string>/tmp/chrome-cdp.log</string>
    <key>StandardErrorPath</key><string>/tmp/chrome-cdp.log</string>
</dict>
</plist>
```

`KeepAlive=true` keeps the headless Chrome up across the day so any harness consumer can attach to `:9222` on demand without waiting for a scheduled trigger. `ThrottleInterval=60` puts a one-minute floor on respawn loops if something is wrong.

XML-comment caveat: launchd parses the plist with libxml2, which rejects `--` anywhere inside `<!-- ... -->`. If you keep prose comments in the plist, do not write CLI flags like `--remote-debugging-port` inside them — drop the leading dashes or move the explanation to the launcher script.

## Verifying

```bash
nc -z localhost 9222 && curl -s http://127.0.0.1:9222/json/version | python3 -m json.tool
cat "$HOME/Library/Application Support/Google/Chrome-CDP/DevToolsActivePort"
```

Then run any harness invocation; it should attach without prompting.
