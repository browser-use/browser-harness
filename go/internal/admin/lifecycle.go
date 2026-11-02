// Package admin is daemon lifecycle, cloud browsers and profiles, and diagnostics.
package admin

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"sort"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/auth"
	"github.com/browser-use/browser-harness/go/internal/browser"
	"github.com/browser-use/browser-harness/go/internal/ipc"
	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/proc"
)

func pick(name string) string {
	if name == "" {
		return ipc.Name()
	}
	return name
}

func DaemonAlive(name string) bool { return ipc.Ping(pick(name), time.Second) }

// DaemonBrowserKind is cloud|cdp|local as self-reported, or "" when unknown.
func DaemonBrowserKind(name string) string {
	m, err := ipc.Call(pick(name), time.Second, map[string]any{"meta": "ping"})
	if err != nil {
		return ""
	}
	switch k, _ := m["browser_kind"].(string); k {
	case "cloud", "cdp", "local":
		return k
	}
	return ""
}

// Connection is one live daemon with a healthy browser connection.
type Connection struct {
	Name   string            `json:"name"`
	Page   map[string]string `json:"page"`
	Kind   string            `json:"kind,omitempty"`   // local, cloud or cdp
	Tabs   int               `json:"tabs,omitempty"`   // open page targets
	Names  []string          `json:"names,omitempty"`  // named tabs
	Agents []AgentTab        `json:"agents,omitempty"` // each agent's own current tab
}

// AgentTab is one agent's current tab in a daemon.
type AgentTab struct {
	Agent string `json:"agent"`
	Title string `json:"title"`
	URL   string `json:"url"`
}

func daemonConnection(name string) *Connection {
	m, err := ipc.Call(name, time.Second, map[string]any{"meta": "connection_status"})
	if err != nil {
		return nil
	}
	if _, bad := m["error"]; bad {
		return nil
	}
	c := &Connection{Name: name}
	if p, ok := m["page"].(map[string]any); ok && p != nil {
		title, _ := p["title"].(string)
		if title == "" {
			title = "(untitled)"
		}
		u, _ := p["url"].(string)
		c.Page = map[string]string{"title": title, "url": u}
	}
	c.Kind, _ = m["kind"].(string)
	if n, ok := m["tabs"].(float64); ok {
		c.Tabs = int(n)
	}
	if names, ok := m["names"].(map[string]any); ok {
		for n := range names {
			c.Names = append(c.Names, n)
		}
		sort.Strings(c.Names)
	}
	if agents, ok := m["agents"].([]any); ok {
		for _, a := range agents {
			am, _ := a.(map[string]any)
			at := AgentTab{}
			at.Agent, _ = am["agent"].(string)
			at.Title, _ = am["title"].(string)
			at.URL, _ = am["url"].(string)
			c.Agents = append(c.Agents, at)
		}
		sort.Slice(c.Agents, func(i, j int) bool { return c.Agents[i].Agent < c.Agents[j].Agent })
	}
	return c
}

// staleEndpoints are daemon names whose socket or port file outlived the daemon.
func staleEndpoints(live []Connection) []string {
	up := map[string]bool{}
	for _, c := range live {
		up[c.Name] = true
	}
	var out []string
	for _, n := range endpointNames() {
		if !up[n] && !DaemonAlive(n) {
			out = append(out, n)
		}
	}
	return out
}

func DaemonBrowserReady(name string) bool { return daemonConnection(pick(name)) != nil }

func endpointNames() []string {
	suffix := ".sock"
	if ipc.IsWindows {
		suffix = ".port"
	}
	if ipc.Isolated() {
		if _, err := os.Stat(ipc.EndpointPath("")); err == nil {
			return []string{ipc.Name()}
		}
		return nil
	}
	entries, _ := os.ReadDir(paths.RuntimeDir())
	var names []string
	for _, e := range entries {
		if raw, ok := strings.CutPrefix(e.Name(), "bu-"); ok {
			if raw, ok = strings.CutSuffix(raw, suffix); ok && ipc.Check(raw) == nil {
				names = append(names, raw)
			}
		}
	}
	return names
}

// BrowserConnections lists live daemons with healthy CDP connections.
func BrowserConnections() []Connection {
	out := []Connection{}
	for _, n := range endpointNames() {
		if c := daemonConnection(n); c != nil {
			out = append(out, *c)
		}
	}
	return out
}

// healthy is a real CDP round trip: stale daemons still answer meta requests.
func healthy(name string, timeout time.Duration) error {
	m, err := ipc.Call(name, timeout, map[string]any{"method": "Target.getTargets", "params": map[string]any{}})
	if err != nil {
		return err
	}
	if _, ok := m["result"]; !ok {
		return errors.New("no CDP result")
	}
	return nil
}

func isLocalMode(env map[string]string) bool {
	return env["BU_CDP_WS"] == "" && env["BU_CDP_URL"] == "" && os.Getenv("BU_CDP_WS") == "" && os.Getenv("BU_CDP_URL") == ""
}

func needsRemoteDebuggingPrompt(msg string) bool {
	low := strings.ToLower(msg)
	return strings.Contains(low, "devtoolsactiveport not found") || strings.Contains(low, "enable chrome://inspect") ||
		strings.Contains(low, "not live yet") ||
		(strings.Contains(low, "ws handshake failed") && (strings.Contains(low, "403") || strings.Contains(low, "opening handshake") ||
			strings.Contains(low, "timed out") || strings.Contains(low, "timeout")))
}

func needsPermissionPopup(msg string) bool {
	return strings.Contains(strings.ToLower(msg), "permission-blocked")
}
func chromeNotRunning(msg string) bool {
	return strings.Contains(strings.ToLower(msg), "chrome-not-running")
}

// Self is the path of this binary, used to spawn daemons.
func Self() string {
	if p := os.Getenv("BH_CORE"); p != "" {
		return p
	}
	p, _ := os.Executable()
	return p
}

type spawned struct {
	pid  int
	done chan struct{}
}

func spawnDaemon(name string, env map[string]string) (*spawned, error) {
	cmd := exec.CommandContext(context.Background(), Self(), "__daemon") //nolint:gosec // Start this binary as the local daemon.
	e := os.Environ()
	if name != "" {
		e = append(e, "BU_NAME="+name)
	}
	for k, v := range env {
		e = append(e, k+"="+v)
	}
	cmd.Env = e
	if f, err := os.OpenFile(ipc.LogPath(pick(name)), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600); err == nil {
		cmd.Stderr = f
		defer func() { _ = f.Close() }()
	}
	proc.Detach(cmd)
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	s := &spawned{pid: cmd.Process.Pid, done: make(chan struct{})}
	go func() { _ = cmd.Wait(); close(s.done) }()
	return s, nil
}

func (s *spawned) exited() bool {
	if s == nil {
		return false
	}
	select {
	case <-s.done:
		return true
	default:
		return false
	}
}

// EnsureDaemon is idempotent: it heals stale daemons, launches a closed Chrome,
// and walks the user through chrome://inspect when remote debugging is off.
// wait<0 means "default".
func EnsureDaemon(wait float64, name string, env map[string]string) error {
	return ensureDaemon(wait, name, env, false)
}

// ensureDaemon is EnsureDaemon; startLocked means the caller holds the start lock.
func ensureDaemon(wait float64, name string, env map[string]string, startLocked bool) error {
	n := pick(name)
	if err := ipc.Check(n); err != nil {
		return err
	}
	if DaemonAlive(name) {
		for i := 0; i < 2; i++ {
			if healthy(n, 3*time.Second) == nil {
				return nil
			}
			if i == 0 {
				time.Sleep(500 * time.Millisecond)
			}
		}
		// A stale cloud (or unclassifiable) daemon still owns a billable browser;
		// only its own shutdown stops that browser before acknowledging.
		if k := DaemonBrowserKind(name); k == "cloud" || k == "" {
			if err := StopRemoteDaemon(n); err != nil {
				return err
			}
		} else {
			_ = RestartDaemon(name, false)
		}
	}
	local := isLocalMode(env)
	startupWait := 60.0
	explicit := wait >= 0
	if explicit {
		startupWait = wait
	}
	// Only a local Chrome handshake parked on the approval sheet drops the deadline.
	approvalUnbounded := local && !explicit
	var launched *launchResult
	for attempt := 0; attempt < 3; attempt++ {
		var child *spawned
		pending := 0
		if local {
			lk, err := lockStart(n, "spawn", time.Duration(startupWait*float64(time.Second)))
			if err != nil {
				return err
			}
			if DaemonAlive(name) {
				lk.release()
				return nil
			}
			pending = parkedDaemonPid(n)
			if pending == 0 {
				pending = startingDaemonPid(n)
			}
			if pending == 0 {
				p, err := spawnDaemon(name, env)
				if err != nil {
					lk.release()
					return err
				}
				ipc.WritePid(n, p.pid)
				child, pending = p, p.pid
			}
			lk.release()
		} else {
			// Held until the daemon answers, so concurrent callers find it instead of spawning more.
			if !startLocked {
				lk, err := lockStart(n, "start", time.Duration((startupWait+5)*float64(time.Second)))
				if err != nil {
					return err
				}
				defer lk.release()
				startLocked = true
				if DaemonAlive(name) {
					return nil
				}
			}
			p, err := spawnDaemon(name, env)
			if err != nil {
				return err
			}
			child = p
		}
		spawned := time.Now()
		deadline := spawned.Add(time.Duration(startupWait * float64(time.Second)))
		unbounded := false
		hinted := !local
		approvalWaiting := false
		pendingDied := false
		for unbounded || time.Now().Before(deadline) {
			if DaemonAlive(name) {
				cleanupUnattachedLaunch(launched)
				return nil
			}
			if child.exited() {
				pendingDied = true
				break
			}
			if child == nil && pending != 0 && startingDaemonPid(n) != pending {
				pendingDied = true
				break
			}
			tail := logTail(n)
			if local && !approvalWaiting && strings.HasPrefix(tail, "handshake-wait") {
				approvalWaiting = true
				if approvalUnbounded {
					unbounded = true
				}
			}
			if !hinted && time.Since(spawned) > 2*time.Second && strings.HasPrefix(tail, "handshake-wait") {
				approve := "browser-harness mac-approve"
				if n != "default" {
					approve = "BU_NAME=" + n + " browser-harness mac-approve"
				}
				action := "click Allow"
				if runtime.GOOS == "darwin" {
					action = fmt.Sprintf("run `%s` in another shell or click Allow", approve)
				}
				fmt.Fprintf(os.Stderr, "browser-harness: Chrome is asking \"Allow remote debugging?\" — %s to continue.\n", action)
				hinted = true
			}
			time.Sleep(200 * time.Millisecond)
		}
		msg := logTail(n)
		permissionWait := local && (strings.HasPrefix(msg, "handshake-wait") || needsPermissionPopup(msg))
		if local && pendingDied {
			// Remove only the generation we observed; a successor may already be live.
			if lk, err := lockStart(n, "spawn", time.Second); err == nil {
				if pid, _ := ipc.ReadPid(n); pid == pending {
					_ = os.Remove(ipc.PidPath(n))
				}
				lk.release()
			}
			if permissionWait {
				// Never auto-spawn a replacement: that raises another Chrome prompt.
				return errors.New("permission-blocked: the pending Chrome connection ended before approval; browser-harness did not retry or create another connection.")
			}
			continue
		}
		if local && strings.HasPrefix(msg, "handshake-wait") {
			// Leave it running: its connection is what keeps the popup on screen.
			return errors.New("permission-blocked: Chrome's Allow popup is still open and the pending daemon was left running. " +
				"Approve that exact popup; browser-harness did not retry or create another connection.")
		}
		if local && needsPermissionPopup(msg) {
			fmt.Fprintln(os.Stderr, "browser-harness: Chrome is asking \"Allow remote debugging?\". Approve that exact popup; no replacement connection was started.")
			return errors.New("permission-blocked: Chrome did not approve the connection; browser-harness did not retry or create another connection.")
		}
		if local && launched == nil && chromeNotRunning(msg) {
			_ = RestartDaemon(name, false)
			launched = launchBrowser()
			if launched == nil {
				return errors.New("chrome-not-running: no supported browser is running and none could be launched -- ask the user to open Chrome, then retry.")
			}
			fmt.Fprintln(os.Stderr, "browser-harness: Chrome isn't running — launching it. If Chrome shows an \"Allow remote debugging?\" popup, click Allow.")
			boot := time.Now().Add(15 * time.Second)
			for time.Now().Before(boot) && !browser.SupportedBrowserRunning(context.Background()) {
				time.Sleep(300 * time.Millisecond)
			}
			continue
		}
		if local && needsRemoteDebuggingPrompt(msg) {
			if v := browser.RemoteDebuggingUserEnabled(context.Background()); v != nil && *v {
				fmt.Fprintln(os.Stderr, "browser-harness: Chrome is asking \"Allow remote debugging?\". Approve that exact popup; no replacement connection was started.")
				return errors.New("permission-blocked: Chrome did not approve the connection; browser-harness did not retry or create another connection.")
			}
			_ = RestartDaemon(name, false)
			openChromeInspectOnce()
			todo := `tick "Allow remote debugging for this browser instance" and click Allow on the popup`
			if len(browser.RemoteDebuggingToggleProfiles()) > 0 {
				todo = `click Allow on Chrome's "Allow remote debugging?" popup (the checkbox is already ticked; if no popup appears, untick and re-tick it)`
			}
			return fmt.Errorf("remote-debugging-setup: opened chrome://inspect/#remote-debugging in Chrome -- ask the user to %s. "+
				"Warn them Chrome shows ONE more Allow popup when the harness connects on the next attempt (per-connection approval; it is expected, not a re-ask). "+
				"Retry after the user confirms; do not retry before.", todo)
		}
		if msg != "" {
			return errors.New(msg)
		}
		return fmt.Errorf("daemon %s didn't come up -- check %s", n, ipc.LogPath(n))
	}
	return fmt.Errorf("daemon %s didn't come up -- check %s", n, ipc.LogPath(n))
}

// RequireExistingDaemon fails closed instead of spawning or reconnecting.
func RequireExistingDaemon(name string) error {
	n := pick(name)
	if !DaemonAlive(n) {
		return fmt.Errorf("required daemon %q is not running", n)
	}
	if err := healthy(n, 3*time.Second); err != nil {
		return fmt.Errorf("required daemon %q is unhealthy: %w", n, err)
	}
	return nil
}

// Connect makes sure name's daemon runs: with BH_REQUIRE_EXISTING_DAEMON=1 it must
// already, otherwise it is started.
func Connect(name string) error {
	if os.Getenv("BH_REQUIRE_EXISTING_DAEMON") == "1" {
		return RequireExistingDaemon(name)
	}
	if DaemonAlive(name) {
		return nil
	}
	return EnsureDaemon(-1, name, nil)
}

// ConnectDefault health-checks the default daemon and starts or heals it, first provisioning
// a cloud browser when BU_AUTOSPAWN is set and there is no daemon, local Chrome or CDP endpoint.
func ConnectDefault() error {
	if os.Getenv("BH_REQUIRE_EXISTING_DAEMON") == "1" {
		return RequireExistingDaemon("")
	}
	if os.Getenv("BU_AUTOSPAWN") != "" && os.Getenv("BU_CDP_URL") == "" && os.Getenv("BU_CDP_WS") == "" &&
		!DaemonAlive("") && !localChromeListening() {
		if _, err := auth.APIKey(); err == nil {
			if _, err := StartRemoteDaemon(ipc.Name(), "", nil); err != nil {
				return err
			}
		}
	}
	return EnsureDaemon(-1, "", nil)
}

// localChromeListening is whether Chrome answers on 9222 or 9223; an unrelated
// listener there must not skip the cloud bootstrap.
func localChromeListening() bool {
	for _, p := range []int{9222, 9223} {
		if _, err := browser.WebSocketURL(context.Background(), fmt.Sprintf("http://127.0.0.1:%d", p), 300*time.Millisecond); err == nil {
			return true
		}
	}
	return false
}

// StopRemoteDaemon cleanly stops a daemon and its billable cloud browser.
func StopRemoteDaemon(name string) error {
	if name == "" {
		name = "remote"
	}
	return RestartDaemon(name, true)
}

// RestartDaemon stops a daemon (callers re-spawn via EnsureDaemon). Signals are
// only sent to a process whose identity is verified by IPC or start fingerprint.
func RestartDaemon(name string, requireClean bool) error {
	n := pick(name)
	if err := ipc.Check(n); err != nil {
		return err
	}
	var pendingGen generation
	pending := false
	if strings.HasPrefix(logTail(n), "handshake-wait") {
		pendingGen, pending = liveGeneration(n)
	}
	daemonPid := ipc.Identify(n, 5*time.Second)
	isAlive := daemonPid != 0 || ipc.Ping(n, time.Second)
	if requireClean && !isAlive {
		return fmt.Errorf("daemon %q is unavailable for required clean shutdown", n)
	}
	if !isAlive && pending {
		lk, err := lockStart(n, "spawn", 5*time.Second)
		if err != nil {
			return fmt.Errorf("pending daemon %q is changing ownership; it was not signaled", n)
		}
		defer lk.release()
		if cur, ok := liveGeneration(n); !ok || cur != pendingGen {
			return fmt.Errorf("pending daemon %q changed ownership; the successor was not signaled and its records were preserved", n)
		}
		if ipc.Ping(n, 200*time.Millisecond) {
			return fmt.Errorf("pending daemon %q became ready during cancellation; run --reload again", n)
		}
		proc.Terminate(pendingGen.PID)
		ipc.CleanupEndpoint(n)
		_ = os.Remove(ipc.PidPath(n))
		return nil
	}
	// The socket can vanish before the process exits (slow cloud stop), so keep a
	// start-time fingerprint as a second identity check before any SIGTERM.
	startFP := proc.StartTime(daemonPid)
	if isAlive {
		cloud := DaemonBrowserKind(n) == "cloud"
		timeout := 5 * time.Second
		if requireClean || cloud {
			timeout = 50 * time.Second
		}
		m, err := ipc.Call(n, timeout, map[string]any{"meta": "shutdown"})
		if cloud && !requireClean && err == nil && m["ok"] != true {
			// Killing it now would leave the cloud browser billing with nobody left to stop it.
			return fmt.Errorf("daemon %q could not stop its cloud browser and was left running so you can retry: %v", n, m["error"])
		}
		if requireClean {
			if err != nil {
				return fmt.Errorf("daemon %q did not confirm clean shutdown: %w", n, err)
			}
			if m["ok"] != true {
				if e, ok := m["error"].(string); ok && e != "" {
					return errors.New(e)
				}
				return fmt.Errorf("daemon %q did not confirm clean shutdown", n)
			}
		}
	}
	if daemonPid != 0 {
		gone := false
		for i := 0; i < 75; i++ {
			if !proc.Alive(daemonPid) {
				gone = true
				break
			}
			time.Sleep(200 * time.Millisecond)
		}
		if !gone {
			verified := ipc.Identify(n, time.Second)
			if verified == daemonPid || (startFP != "" && proc.StartTime(daemonPid) == startFP) {
				proc.Terminate(daemonPid)
			}
		}
	}
	ipc.CleanupEndpoint(n)
	_ = os.Remove(ipc.PidPath(n))
	return nil
}
