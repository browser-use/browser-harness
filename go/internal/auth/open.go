package auth

import (
	"context"
	"os/exec"
	"runtime"
)

func openURL(u string) error {
	switch runtime.GOOS {
	case "darwin":
		return exec.CommandContext(context.Background(), "open", u).Start() //nolint:gosec // Open the login URL in the system browser.
	case "windows":
		return exec.CommandContext(context.Background(), "rundll32", "url.dll,FileProtocolHandler", u).Start() //nolint:gosec // Open the login URL in the system browser.
	default:
		return exec.CommandContext(context.Background(), "xdg-open", u).Start() //nolint:gosec // Open the login URL in the system browser.
	}
}
