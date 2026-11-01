package admin

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/browser"
)

const approveScript = `using terms from application "System Events"
    on clickAllow(nodeRef)
        try
            if (role of nodeRef as text) is "AXButton" and ¬
                (description of nodeRef as text) is "Allow" then
                perform action "AXPress" of nodeRef
                return true
            end if
        end try
        try
            repeat with childRef in UI elements of nodeRef
                if my clickAllow(childRef) then return true
            end repeat
        end try
        return false
    end clickAllow
end using terms from

set resultText to "not-found"
tell application "System Events"
    if exists process "Google Chrome" then
        tell process "Google Chrome"
            repeat with w in windows
                try
                    repeat with s in sheets of w
                        if (name of s as text) is "Allow remote debugging?" then
                            if my clickAllow(s) then
                                set resultText to "ready"
                                exit repeat
                            end if
                        end if
                    end repeat
                end try
                if resultText is "ready" then exit repeat
            end repeat
        end tell
    end if
end tell
return resultText
`

const accessibilityDetail = "allow the app launching browser-harness (for example Terminal, iTerm, or Codex) " +
	"in System Settings > Privacy & Security > Accessibility"

// Seams for tests.
var (
	macGOOS           = runtime.GOOS
	macDaemonReady    = func() bool { return DaemonBrowserReady("") }
	macToggleProfiles = browser.RemoteDebuggingToggleProfiles
	macChromeRoot     = func() string {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, "Library/Application Support/Google/Chrome")
	}
	runOsascript = func(ctx context.Context, script string) (string, string, error) {
		cmd := exec.CommandContext(ctx, "osascript")
		cmd.Stdin = strings.NewReader(script)
		var stdout, stderr strings.Builder
		cmd.Stdout, cmd.Stderr = &stdout, &stderr
		err := cmd.Run()
		return stdout.String(), stderr.String(), err
	}
)

// approveRemoteDebugging clicks Chrome's exact per-connection Allow sheet without activating Chrome.
func approveRemoteDebugging() (string, string) {
	if macGOOS != "darwin" {
		return "unsupported", "mac-approve is only available on macOS"
	}
	if macDaemonReady() {
		return "ready", ""
	}
	if !contains(macToggleProfiles(), macChromeRoot()) {
		return "setup-required", `first enable "Allow remote debugging for this browser instance" at ` +
			"chrome://inspect/#remote-debugging, then run `browser-harness mac-approve` again"
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	stdout, stderr, err := runOsascript(ctx, approveScript)
	if errors.Is(ctx.Err(), context.DeadlineExceeded) {
		return "accessibility-required", accessibilityDetail
	}
	if err != nil {
		var ee *exec.ExitError
		if !errors.As(err, &ee) {
			return "error", err.Error()
		}
		detail := strings.TrimSpace(stderr)
		if detail == "" {
			detail = "osascript failed"
		}
		low := strings.ToLower(detail)
		if strings.Contains(low, "not authorized") || strings.Contains(low, "assistive") {
			return "accessibility-required", accessibilityDetail
		}
		return "error", detail
	}
	switch status := strings.TrimSpace(stdout); status {
	case "ready":
		return "ready", ""
	case "not-found":
		// The user may have accepted the sheet while AppleScript was looking.
		if macDaemonReady() {
			return "ready", ""
		}
		return "not-found", "retry the browser command and run `browser-harness mac-approve` when the prompt appears"
	case "":
		return "error", "unexpected osascript result: <empty>"
	default:
		return "error", "unexpected osascript result: " + status
	}
}

func MacApprove(args []string) int {
	if len(args) > 0 {
		fmt.Println("usage: browser-harness mac-approve")
		return 2
	}
	status, detail := approveRemoteDebugging()
	if detail != "" {
		fmt.Printf("%s: %s\n", status, detail)
	} else {
		fmt.Println(status)
	}
	if status == "ready" {
		return 0
	}
	return 1
}
