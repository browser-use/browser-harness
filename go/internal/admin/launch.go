package admin

import (
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/auth"
	"github.com/browser-use/browser-harness/go/internal/browser"
	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/proc"
)

type launchSpec struct {
	macApp    string
	posix     []string
	winTarget string
}

var launchTable = []struct {
	frag string
	spec launchSpec
}{
	{"chrome canary", launchSpec{"Google Chrome Canary", []string{"google-chrome-canary"}, "chrome"}},
	{"chromium", launchSpec{"Chromium", []string{"chromium", "chromium-browser"}, "chromium"}},
	{"chrome", launchSpec{"Google Chrome", []string{"google-chrome-stable", "google-chrome"}, "chrome"}},
	{"edge", launchSpec{"Microsoft Edge", []string{"microsoft-edge", "microsoft-edge-stable"}, "msedge"}},
	{"brave-origin", launchSpec{"Brave Origin", nil, ""}},
	{"brave", launchSpec{"Brave Browser", []string{"brave-browser", "brave"}, "brave"}},
	{"arc", launchSpec{"Arc", nil, ""}},
	{"dia", launchSpec{"Dia", nil, ""}},
	{"comet", launchSpec{"Comet", nil, ""}},
}

var defaultLaunch = launchSpec{"Google Chrome", []string{"google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "microsoft-edge"}, "chrome"}

func specFor(base string) launchSpec {
	parts := strings.Split(filepath.ToSlash(base), "/")
	if len(parts) > 2 {
		parts = parts[len(parts)-2:]
	}
	tail := strings.ToLower(strings.Join(parts, "/"))
	for _, row := range launchTable {
		if strings.Contains(tail, row.frag) {
			return row.spec
		}
	}
	return defaultLaunch
}

func alnum(s string) string {
	var b strings.Builder
	for _, r := range strings.ToLower(s) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r > 127 {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func binaryMatchesProfile(binary, base string) bool {
	name := alnum(strings.TrimSuffix(strings.ToLower(filepath.Base(binary)), ".exe"))
	s := specFor(base)
	for _, c := range append([]string{s.macApp, s.winTarget}, s.posix...) {
		if c != "" && name == alnum(c) {
			return true
		}
	}
	return false
}

// profileDirectoryArgs skips Chrome's profile picker on relaunch.
func profileDirectoryArgs(base string) []string {
	if base == "" {
		return nil
	}
	last := "Default"
	if raw, err := os.ReadFile(filepath.Join(base, "Local State")); err == nil { //nolint:gosec // Read Local State from a discovered browser profile.
		var st struct {
			Profile struct {
				LastUsed any `json:"last_used"`
			} `json:"profile"`
		}
		if json.Unmarshal(raw, &st) == nil {
			if s, ok := st.Profile.LastUsed.(string); ok && s != "" {
				last = s
			} else if st.Profile.LastUsed != nil {
				return nil
			}
		}
	}
	if fi, err := os.Stat(filepath.Join(base, last)); err != nil || !fi.IsDir() {
		return nil
	}
	return []string{"--profile-directory=" + last}
}

type launchResult struct {
	proc    *os.Process
	profile string
}

func hasLocalState(base string) bool {
	_, err := os.Stat(filepath.Join(base, "Local State"))
	return err == nil
}

// launchBrowser prefers the browser whose profile already has the inspect toggle on.
// openApp runs macOS `open`; tests override it.
var openApp = func(args ...string) error {
	_, err := proc.Output(10*time.Second, "open", args...)
	return err
}

func launchBrowser() *launchResult {
	enabled := browser.RemoteDebuggingToggleProfiles()
	known := append([]string{}, enabled...)
	for _, b := range browser.ProfileDirs() {
		if !slices.Contains(enabled, b) && hasLocalState(b) {
			known = append(known, b)
		}
	}
	for _, key := range []string{"BH_CHROME_PATH", "CHROME_PATH"} {
		raw := strings.TrimSpace(os.Getenv(key))
		if raw == "" {
			continue
		}
		if strings.HasPrefix(raw, "~/") {
			h, _ := os.UserHomeDir()
			raw = filepath.Join(h, raw[2:])
		}
		if fi, err := os.Stat(raw); err != nil || fi.IsDir() {
			continue
		}
		cmd := exec.CommandContext(context.Background(), raw) //nolint:gosec // The operator selects the browser executable.
		proc.Detach(cmd)
		if cmd.Start() != nil {
			continue // exists but cannot execute: fall through to discovery
		}
		go func() { _ = cmd.Wait() }()
		profile := ""
		if browser.GOOS != "darwin" && browser.GOOS != "windows" {
			for _, b := range known {
				if binaryMatchesProfile(raw, b) {
					profile = b
					break
				}
			}
		}
		return &launchResult{proc: cmd.Process, profile: profile}
	}
	base := ""
	if len(enabled) > 0 {
		base = enabled[0]
	} else {
		for _, b := range browser.ProfileDirs() {
			if hasLocalState(b) {
				base = b
				break
			}
		}
	}
	spec := defaultLaunch
	if base != "" {
		spec = specFor(base)
	}
	args := profileDirectoryArgs(base)
	switch browser.GOOS {
	case "darwin":
		cmdArgs := []string{"-a", spec.macApp}
		if len(args) > 0 {
			cmdArgs = append(cmdArgs, append([]string{"--args"}, args...)...)
		}
		if err := openApp(cmdArgs...); err != nil {
			if spec.macApp == "Google Chrome" {
				return nil
			}
			// A different app's profile dir may not match; launch plain Chrome.
			if err := openApp("-a", "Google Chrome"); err != nil {
				return nil
			}
		}
		return &launchResult{profile: base}
	case "windows":
		target := spec.winTarget
		if target == "" {
			target = "chrome"
		}
		cmd := exec.CommandContext(context.Background(), "cmd", append([]string{"/c", "start", "", target}, args...)...) //nolint:gosec // Launch a known browser target with profile arguments.
		proc.Detach(cmd)
		if cmd.Start() != nil {
			return nil
		}
		go func() { _ = cmd.Wait() }()
		return &launchResult{profile: base}
	}
	cmds := spec.posix
	if len(cmds) == 0 {
		cmds = defaultLaunch.posix
	}
	for _, c := range cmds {
		if p, err := exec.LookPath(c); err == nil {
			cmd := exec.CommandContext(context.Background(), p, args...) //nolint:gosec // Launch a discovered browser executable with profile arguments.
			proc.Detach(cmd)
			if cmd.Start() != nil {
				return nil
			}
			go func() { _ = cmd.Wait() }()
			return &launchResult{proc: cmd.Process, profile: base}
		}
	}
	return nil
}

// cleanupUnattachedLaunch stops a browser we launched when the daemon attached elsewhere.
func cleanupUnattachedLaunch(l *launchResult) {
	if l == nil || l.proc == nil || l.profile == "" || !proc.Alive(l.proc.Pid) {
		return
	}
	if browser.DevtoolsPortLive(context.Background(), l.profile) {
		return
	}
	proc.TerminateGroup(l.proc)
}

func openChromeInspect() bool {
	const u = "chrome://inspect/#remote-debugging"
	if runtime.GOOS == "darwin" {
		if _, err := proc.Output(5*time.Second, "osascript", "-e", `tell application "Google Chrome" to activate`,
			"-e", `tell application "Google Chrome" to open location "`+u+`"`); err == nil {
			return true
		}
	}
	return auth.Opener(u) == nil
}

// openChromeInspectOnce opens chrome://inspect at most once per 180 s across invocations.
func openChromeInspectOnce() {
	marker := paths.InspectMarker()
	if fi, err := os.Stat(marker); err == nil && time.Since(fi.ModTime()) < 180*time.Second {
		return
	}
	if !openChromeInspect() {
		return
	}
	_ = os.MkdirAll(filepath.Dir(marker), 0o700)
	now := time.Now()
	if f, err := os.OpenFile(marker, os.O_CREATE|os.O_WRONLY, 0o600); err == nil { //nolint:gosec // Create the inspect marker in the configured directory.
		_ = f.Close()
	}
	_ = os.Chtimes(marker, now, now)
}

// chromeRunning is a best-effort check for any running Chromium-based browser.
func chromeRunning() bool {
	var out string
	var err error
	var names []string
	if runtime.GOOS == "windows" {
		out, err = proc.Output(5*time.Second, "tasklist")
		names = []string{"chrome.exe", "msedge.exe", "helium.exe"}
	} else {
		out, err = proc.Output(5*time.Second, "ps", "-A", "-o", "comm=")
		names = []string{"Google Chrome", "chrome", "chromium", "Microsoft Edge", "msedge", "helium"}
	}
	if err != nil {
		return false
	}
	low := strings.ToLower(out)
	for _, n := range names {
		if strings.Contains(low, strings.ToLower(n)) {
			return true
		}
	}
	return false
}
