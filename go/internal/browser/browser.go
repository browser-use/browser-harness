// Package browser finds local Chromium-family profiles and their DevTools
// endpoints (the discovery half of daemon.py, shared with admin).
package browser

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
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

// ProfileDirs lists the user-data dirs scanned for DevToolsActivePort.
func ProfileDirs() []string {
	home, _ := os.UserHomeDir()
	var rel []string
	root := home
	switch runtime.GOOS {
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
	raw, err := os.ReadFile(filepath.Join(base, "DevToolsActivePort"))
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
func DevtoolsPortLive(base string) bool {
	port, _, ok := readActivePort(base)
	if !ok {
		return false
	}
	if _, err := strconv.Atoi(port); err != nil {
		return false
	}
	c, err := net.DialTimeout("tcp", "127.0.0.1:"+port, 500*time.Millisecond)
	if err != nil {
		return false
	}
	c.Close()
	return true
}

func remoteDebuggingFlag(base string) (val bool, set bool) {
	raw, err := os.ReadFile(filepath.Join(base, "Local State"))
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
func RemoteDebuggingUserEnabled() *bool {
	var seen *bool
	for _, base := range ProfileDirs() {
		v, set := remoteDebuggingFlag(base)
		if !set {
			continue
		}
		if v && DevtoolsPortLive(base) {
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
func SupportedBrowserRunning() bool {
	if runtime.GOOS == "windows" {
		out, err := exec.Command("tasklist").Output()
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
	return processExists(pid)
}

const blockedMsg = "permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted"

type httpStatusError int

func (e httpStatusError) Error() string { return "HTTP Error " + strconv.Itoa(int(e)) }

func jsonVersionWS(base string, timeout time.Duration) (string, error) {
	c := &http.Client{Timeout: timeout}
	resp, err := c.Get(strings.TrimRight(base, "/") + "/json/version")
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return "", httpStatusError(resp.StatusCode)
	}
	body, _ := io.ReadAll(resp.Body)
	var v struct {
		WS string `json:"webSocketDebuggerUrl"`
	}
	if err := json.Unmarshal(body, &v); err != nil || v.WS == "" {
		return "", errors.New("no webSocketDebuggerUrl")
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

// WSURL resolves the CDP websocket from BU_CDP_WS, BU_CDP_URL or local discovery.
func WSURL() (string, error) {
	if u := os.Getenv("BU_CDP_WS"); u != "" {
		return u, nil
	}
	if u := os.Getenv("BU_CDP_URL"); u != "" {
		deadline := time.Now().Add(30 * time.Second)
		var last error
		for time.Now().Before(deadline) {
			ws, err := jsonVersionWS(u, 5*time.Second)
			if err == nil {
				return ws, nil
			}
			last = err
			var hs httpStatusError
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
		if runtime.GOOS == "windows" {
			hint += "; on Windows also check that a firewall/antivirus isn't blocking localhost connections"
		}
		return "", fmt.Errorf("BU_CDP_URL=%s unreachable after 30s: %v -- %s", u, last, hint)
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
			ws, err := jsonVersionWS("http://127.0.0.1:"+port, time.Second)
			if err == nil {
				return ws, nil
			}
			var hs httpStatusError
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
			if !SupportedBrowserRunning() {
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
	for _, p := range []int{9222, 9223} {
		ws, err := jsonVersionWS(fmt.Sprintf("http://127.0.0.1:%d", p), time.Second)
		if err == nil {
			return ws, nil
		}
		var hs httpStatusError
		if errors.As(err, &hs) && hs == 403 {
			return "", errors.New(blockedMsg)
		}
	}
	if v := RemoteDebuggingUserEnabled(); v != nil && !*v {
		return "", errors.New(`remote debugging is turned off for this browser instance — enable chrome://inspect/#remote-debugging (tick "Allow remote debugging for this browser instance")`)
	}
	return "", fmt.Errorf("DevToolsActivePort not found in %s — enable chrome://inspect/#remote-debugging, or set BU_CDP_WS for a remote browser", pyList(ProfileDirs()))
}

func pyList(items []string) string {
	q := make([]string, len(items))
	for i, s := range items {
		q[i] = "'" + s + "'"
	}
	return "[" + strings.Join(q, ", ") + "]"
}
