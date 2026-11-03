// Package browser finds local Chromium-family profiles and their DevTools
// endpoints, for the daemon and admin.
package browser

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/proc"
)

var macProfiles = []string{
	"Library/Application Support/Google/Chrome",
	"Library/Application Support/Google/Chrome Canary",
	"Library/Application Support/Comet",
	"Library/Application Support/Arc/User Data",
	"Library/Application Support/Dia/User Data",
	"Library/Application Support/Microsoft Edge",
	"Library/Application Support/Microsoft Edge Beta",
	"Library/Application Support/Microsoft Edge Dev",
	"Library/Application Support/Microsoft Edge Canary",
	"Library/Application Support/BraveSoftware/Brave-Browser",
	"Library/Application Support/BraveSoftware/Brave-Origin",
}

var linuxProfiles = []string{
	".config/google-chrome",
	".config/chromium",
	".config/chromium-browser",
	".config/microsoft-edge",
	".config/microsoft-edge-beta",
	".config/microsoft-edge-dev",
	".var/app/org.chromium.Chromium/config/chromium",
	".var/app/com.google.Chrome/config/google-chrome",
	".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser",
	".var/app/com.microsoft.Edge/config/microsoft-edge",
}

var windowsProfiles = []string{ // relative to %LOCALAPPDATA%; SxS = Canary
	"Google/Chrome/User Data",
	"Google/Chrome SxS/User Data",
	"Google/Chrome Beta/User Data",
	"Google/Chrome Dev/User Data",
	"Chromium/User Data",
	"Microsoft/Edge/User Data",
	"Microsoft/Edge Beta/User Data",
	"Microsoft/Edge Dev/User Data",
	"Microsoft/Edge SxS/User Data",
	"BraveSoftware/Brave-Browser/User Data",
}

// GOOS picks the profile layout; tests override it.
var GOOS = runtime.GOOS

// ProfileDirs lists the user-data dirs scanned for DevToolsActivePort.
func ProfileDirs() []string {
	home, _ := os.UserHomeDir()
	var rel []string
	root := home
	switch GOOS {
	case "windows":
		root = os.Getenv("LOCALAPPDATA")
		if root == "" {
			root = filepath.Join(home, "AppData", "Local")
		}
		rel = windowsProfiles
	case "darwin":
		rel = macProfiles
	default:
		rel = linuxProfiles
	}
	out := make([]string, len(rel))
	for i, r := range rel {
		out[i] = filepath.Join(root, filepath.FromSlash(r))
	}
	return out
}

func readActivePort(base string) (port, wsPath string, ok bool) {
	raw, err := os.ReadFile(filepath.Join(base, "DevToolsActivePort")) //nolint:gosec // Read the DevTools port from a discovered browser profile.
	if err != nil {
		return "", "", false
	}
	lines := strings.Split(strings.ToValidUTF8(string(raw), "�"), "\n")
	port = strings.TrimSpace(lines[0])
	if len(lines) > 1 {
		wsPath = strings.TrimSpace(lines[1])
	}
	return port, wsPath, true
}

// DevtoolsPortLive is true when something listens on the profile's DevToolsActivePort.
func DevtoolsPortLive(ctx context.Context, base string) bool {
	port, _, ok := readActivePort(base)
	if !ok {
		return false
	}
	if _, err := strconv.Atoi(port); err != nil {
		return false
	}
	c, err := (&net.Dialer{Timeout: 500 * time.Millisecond}).DialContext(ctx, "tcp", "127.0.0.1:"+port)
	if err != nil {
		return false
	}
	_ = c.Close()
	return true
}

func remoteDebuggingFlag(base string) (val bool, set bool) {
	raw, err := os.ReadFile(filepath.Join(base, "Local State")) //nolint:gosec // Read Local State from a discovered browser profile.
	if err != nil {
		return false, false
	}
	var st struct {
		Devtools struct {
			RemoteDebugging struct {
				UserEnabled *bool `json:"user-enabled"`
			} `json:"remote_debugging"`
		} `json:"devtools"`
	}
	if json.Unmarshal(raw, &st) != nil || st.Devtools.RemoteDebugging.UserEnabled == nil {
		return false, false
	}
	return *st.Devtools.RemoteDebugging.UserEnabled, true
}

// RemoteDebuggingUserEnabled reports chrome://inspect's toggle: true only when a
// toggle-on profile also has a live port; false if a profile records it off;
// nil when no profile records it.
func RemoteDebuggingUserEnabled(ctx context.Context) *bool {
	var seen *bool
	for _, base := range ProfileDirs() {
		v, set := remoteDebuggingFlag(base)
		if !set {
			continue
		}
		if v && DevtoolsPortLive(ctx, base) {
			t := true
			return &t
		}
		if !v {
			f := false
			seen = &f
		}
	}
	return seen
}

// RemoteDebuggingToggleProfiles lists profiles whose toggle is recorded on.
func RemoteDebuggingToggleProfiles() []string {
	var out []string
	for _, base := range ProfileDirs() {
		if v, set := remoteDebuggingFlag(base); set && v {
			out = append(out, base)
		}
	}
	return out
}

// SupportedBrowserRunning reports whether any scanned browser is running.
func SupportedBrowserRunning(ctx context.Context) bool {
	if GOOS == "windows" {
		out, err := exec.CommandContext(ctx, "tasklist").Output()
		if err != nil {
			return true // can't tell: keep recovery on the popup/toggle path
		}
		low := strings.ToLower(string(out))
		for _, n := range []string{"chrome.exe", "msedge.exe", "chromium.exe", "brave.exe", "helium.exe"} {
			if strings.Contains(low, n) {
				return true
			}
		}
		return false
	}
	for _, base := range ProfileDirs() {
		if runningForProfile(base) {
			return true
		}
	}
	return false
}

func runningForProfile(base string) bool {
	target, err := os.Readlink(filepath.Join(base, "SingletonLock"))
	if err != nil {
		return false
	}
	i := strings.LastIndex(target, "-")
	pid, err := strconv.Atoi(target[i+1:])
	if err != nil {
		return false
	}
	return proc.Alive(pid)
}

const blockedMsg = "permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted"

// statusError is a non-2xx reply from /json/version; 403 and 404 mean different things.
type statusError int

func (e statusError) Error() string {
	return fmt.Sprintf("/json/version: %d %s", int(e), http.StatusText(int(e)))
}

// WebSocketURL is the browser websocket that base's /json/version advertises.
func WebSocketURL(ctx context.Context, base string, timeout time.Duration) (string, error) {
	u := strings.TrimRight(base, "/") + "/json/version"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return "", err
	}
	resp, err := (&http.Client{Timeout: timeout}).Do(req)
	if err != nil {
		return "", err
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode >= 400 {
		return "", statusError(resp.StatusCode)
	}
	var v struct {
		WS string `json:"webSocketDebuggerUrl"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&v); err != nil || v.WS == "" {
		return "", fmt.Errorf("%s has no webSocketDebuggerUrl", u)
	}
	return v.WS, nil
}

// WSFromActivePort matches a profile's DevToolsActivePort by port when
// /json/version returns 404 (Chrome 147+ default profile).
func WSFromActivePort(httpURL string) string {
	u, err := url.Parse(httpURL)
	if err != nil || u.Port() == "" {
		return ""
	}
	host := u.Hostname()
	if host == "" {
		host = "127.0.0.1"
	}
	if strings.Contains(host, ":") {
		host = "[" + host + "]"
	}
	for _, base := range ProfileDirs() {
		port, ws, ok := readActivePort(base)
		if ok && port == u.Port() && ws != "" {
			return fmt.Sprintf("ws://%s:%s%s", host, port, ws)
		}
	}
	return ""
}

// localPorts are the DevTools ports a local Chrome is looked for on.
var localPorts = []int{9222, 9223}

// CDPEndpoint is the explicit CDP endpoint getenv gives, BU_CDP_WS before BU_CDP_URL;
// "" means the browser is a local Chrome found by discovery.
func CDPEndpoint(getenv func(string) string) string {
	if v := getenv("BU_CDP_WS"); v != "" {
		return v
	}
	return getenv("BU_CDP_URL")
}

// LocalChromeListening is whether Chrome answers on a local DevTools port; an unrelated
// listener there does not count.
func LocalChromeListening() bool {
	for _, p := range localPorts {
		if _, err := WebSocketURL(context.Background(), fmt.Sprintf("http://127.0.0.1:%d", p), 300*time.Millisecond); err == nil {
			return true
		}
	}
	return false
}

// WSURL resolves the CDP websocket from BU_CDP_WS, BU_CDP_URL or local discovery.
func WSURL(ctx context.Context) (string, error) {
	if u := os.Getenv("BU_CDP_WS"); u != "" {
		return u, nil
	}
	if u := os.Getenv("BU_CDP_URL"); u != "" {
		deadline := time.Now().Add(30 * time.Second)
		var last error
		for time.Now().Before(deadline) {
			ws, err := WebSocketURL(ctx, u, 5*time.Second)
			if err == nil {
				return ws, nil
			}
			last = err
			var hs statusError
			if errors.As(err, &hs) {
				if hs == 403 {
					return "", errors.New(blockedMsg)
				}
				if hs == 404 {
					if ws := WSFromActivePort(u); ws != "" {
						return ws, nil
					}
				}
			}
			time.Sleep(time.Second)
		}
		hint := "is the dedicated automation Chrome running? Launch it with --remote-debugging-port=<port> --user-data-dir=<dedicated dir>"
		if GOOS == "windows" {
			hint += "; on Windows also check that a firewall/antivirus isn't blocking localhost connections"
		}
		return "", fmt.Errorf("BU_CDP_URL=%s unreachable after 30s: %w -- %s", u, last, hint)
	}
	start := time.Now()
	deadline := start.Add(30 * time.Second)
	var nextLiveness time.Time
	for time.Now().Before(deadline) {
		for _, base := range ProfileDirs() {
			port, wsPath, ok := readActivePort(base)
			if !ok || port == "" {
				continue
			}
			// Resolve via /json/version instead of trusting the stored path, which can
			// be stale when another --user-data-dir once used the same port.
			ws, err := WebSocketURL(ctx, "http://127.0.0.1:"+port, time.Second)
			if err == nil {
				return ws, nil
			}
			var hs statusError
			if errors.As(err, &hs) {
				if hs == 403 {
					return "", errors.New(blockedMsg)
				}
				if hs == 404 && wsPath != "" {
					return "ws://127.0.0.1:" + port + wsPath, nil
				}
			}
		}
		now := time.Now()
		if !now.Before(nextLiveness) {
			if !SupportedBrowserRunning(ctx) {
				return "", errors.New("chrome-not-running: no supported Chromium-family browser is running -- start Chrome, then retry")
			}
			nextLiveness = now.Add(2 * time.Second)
		}
		grace := 3 * time.Second
		if len(RemoteDebuggingToggleProfiles()) > 0 {
			grace = 12 * time.Second
		}
		if now.Sub(start) > grace {
			break
		}
		time.Sleep(200 * time.Millisecond)
	}
	for _, p := range localPorts {
		ws, err := WebSocketURL(ctx, fmt.Sprintf("http://127.0.0.1:%d", p), time.Second)
		if err == nil {
			return ws, nil
		}
		var hs statusError
		if errors.As(err, &hs) && hs == 403 {
			return "", errors.New(blockedMsg)
		}
	}
	if v := RemoteDebuggingUserEnabled(ctx); v != nil && !*v {
		return "", errors.New(`remote debugging is turned off for this browser instance — enable chrome://inspect/#remote-debugging (tick "Allow remote debugging for this browser instance")`)
	}
	return "", fmt.Errorf("DevToolsActivePort not found in %s — enable chrome://inspect/#remote-debugging, or set BU_CDP_WS for a remote browser", strings.Join(ProfileDirs(), ", "))
}
