# macOS Remote-Debugging Approval

Use this only when browser-harness reports that Chrome is waiting for its
"Allow remote debugging?" sheet. The sheet is native Chrome UI, outside CDP.

Leave the browser command running. In a second shell, use AppleScript UI
automation to press only the Allow button inside the exact sheet:

```bash
osascript <<'APPLESCRIPT'
using terms from application "System Events"
    on pressAllow(nodeRef)
        try
            if (role of nodeRef as text) is "AXButton" and ¬
                (description of nodeRef as text) is "Allow" then
                perform action "AXPress" of nodeRef
                return true
            end if
        end try
        try
            repeat with childRef in UI elements of nodeRef
                if my pressAllow(childRef) then return true
            end repeat
        end try
        return false
    end pressAllow
end using terms from

tell application "System Events"
    if exists process "Google Chrome" then
        tell process "Google Chrome"
            repeat with w in windows
                repeat with s in sheets of w
                    if (name of s as text) is "Allow remote debugging?" then
                        if my pressAllow(s) then return "ready"
                    end if
                end repeat
            end repeat
        end tell
    end if
end tell
return "not-found"
APPLESCRIPT
```

For Chromium, Edge, or Brave, substitute its macOS process name. Do not use a
generic coordinate click or activate Chrome unnecessarily. When the script
returns `ready`, the waiting browser command should continue; if it already
timed out, retry it once.

If macOS denies assistive access, do not inspect TCC or try another UI wrapper.
When the task needs the user's existing logins/profile, stop and ask them to
grant the launching app Accessibility permission in System Settings > Privacy
& Security > Accessibility.

Otherwise, continue unattended with a temporary dedicated Chrome: create its
profile with `mktemp -d`, launch the real Chrome binary with that exact
`--user-data-dir`, `--remote-debugging-port=0`, and
`--remote-debugging-address=127.0.0.1`, then read its chosen port from
`DevToolsActivePort` and pass `BU_CDP_URL=http://127.0.0.1:<port>` on every
browser-harness call. Tell the user it is a separate profile with none of their
logins, cookies, or tabs. Retain the launched PID and exact temp path; when the
task ends, reload its named daemon, terminate only that PID, wait for exit, and
remove only that temp profile.
