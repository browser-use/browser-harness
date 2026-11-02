// Package admin is daemon lifecycle, cloud browsers and profiles, and diagnostics.
package admin

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/browser"
	"github.com/browser-use/browser-harness/go/internal/ipc"
)

// Name is the default daemon name (BU_NAME or "default").
func Name() string {
	if n := os.Getenv("BU_NAME"); n != "" {
		return n
	}
	return "default"
}

func pick(name string) string {
	if name == "" {
		return Name()
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
	Name string            `json:"name"`
	Page map[string]string `json:"page"`
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
	return c
}

func DaemonBrowserReady(name string) bool { return daemonConnection(pick(name)) != nil }

func endpointNames() []string {
	suffix := ".sock"
	if ipc.IsWindows {
		suffix = ".port"
	}
	dir := ipc.RuntimeDir()
	if (os.Getenv("BH_RUNTIME_DIR") != "" || os.Getenv("BH_TMP_DIR") != "") && os.Getenv("BH_RUNTIME_DIR_SHARED") != "1" {
		if _, err := os.Stat(dir + string(os.PathSeparator) + "bu" + suffix); err == nil {
			return []string{Name()}
		}
		return nil
	}
	entries, _ := os.ReadDir(dir)
	var names []string
	for _, e := range entries {
		n := e.Name()
		if strings.HasPrefix(n, "bu-") && strings.HasSuffix(n, suffix) {
			raw := n[3 : len(n)-len(suffix)]
			if ipc.Check(raw) == nil {
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

func healthy(name string, timeout time.Duration) bool {
	m, err := ipc.Call(name, timeout, map[string]any{"method": "Target.getTargets", "params": map[string]any{}})
	if err != nil {
		return false
	}
	_, ok := m["result"]
	return ok
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
	cmd := exec.Command(Self(), "__daemon")
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
		defer f.Close()
	}
	detach(cmd)
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
	n := pick(name)
	if err := ipc.Check(n); err != nil {
		return err
	}
	if DaemonAlive(name) {
		// Stale daemons still answer meta requests; require a real CDP result.
		for i := 0; i < 2; i++ {
			if healthy(n, 3*time.Second) {
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
	openedInspect := false
	for attempt := 0; attempt < 3; attempt++ {
		var proc *spawned
		pending := 0
		if local {
			lk := acquireSpawnLock(n, time.Duration(startupWait*float64(time.Second)))
			if !lk.held {
				return errors.New("daemon-starting: another browser-harness daemon is still starting; retry later")
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
				publishPid(ipc.PidPath(n), p.pid)
				proc, pending = p, p.pid
			}
			lk.release()
		} else {
			// Held until the daemon answers, so concurrent callers find it instead of spawning more.
			lk, err := acquireStartLock(n, time.Duration((startupWait+5)*float64(time.Second)))
			if err != nil {
				return err
			}
			defer lk.release()
			if DaemonAlive(name) {
				return nil
			}
			p, err := spawnDaemon(name, env)
			if err != nil {
				return err
			}
			proc = p
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
			if proc.exited() {
				pendingDied = true
				break
			}
			if proc == nil && pending != 0 && pendingPid(ipc.PidPath(n)) != pending {
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
			if lk := acquireSpawnLock(n, time.Second); lk.held {
				if pidNumber(ipc.PidPath(n)) == pending {
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
			for time.Now().Before(boot) && !browser.SupportedBrowserRunning() {
				time.Sleep(300 * time.Millisecond)
			}
			continue
		}
		if local && !openedInspect && needsRemoteDebuggingPrompt(msg) {
			openedInspect = true
			if v := browser.RemoteDebuggingUserEnabled(); v != nil && *v {
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
		return fmt.Errorf("required daemon %s is not running", quoted(n))
	}
	m, err := ipc.Call(n, 3*time.Second, map[string]any{"method": "Target.getTargets", "params": map[string]any{}})
	if err != nil {
		return fmt.Errorf("required daemon %s is unhealthy: %v", quoted(n), err)
	}
	if _, ok := m["result"]; !ok {
		return fmt.Errorf("required daemon %s failed its CDP health check", quoted(n))
	}
	return nil
}

// StopRemoteDaemon cleanly stops a daemon and its billable cloud browser.
func StopRemoteDaemon(name string) error {
	if name == "" {
		name = "remote"
	}
	return RestartDaemon(name, true)
}

func quoted(s string) string { return "'" + s + "'" }

// RestartDaemon stops a daemon (callers re-spawn via EnsureDaemon). Signals are
// only sent to a process whose identity is verified by IPC or start fingerprint.
func RestartDaemon(name string, requireClean bool) error {
	n := pick(name)
	if err := ipc.Check(n); err != nil {
		return err
	}
	pidPath := ipc.PidPath(n)
	var pendingGen *generation
	pendingUnverified := false
	if strings.HasPrefix(logTail(n), "handshake-wait") {
		parked := parkedDaemonPid(n)
		pendingGen = fingerprintedGeneration(pidPath)
		pendingUnverified = parked != 0 && pendingGen == nil
	}
	daemonPid := ipc.Identify(n, 5*time.Second)
	isAlive := daemonPid != 0 || ipc.Ping(n, time.Second)
	if requireClean && !isAlive {
		return fmt.Errorf("daemon %s is unavailable for required clean shutdown", quoted(n))
	}
	if !isAlive && pendingUnverified {
		return fmt.Errorf("pending daemon %s is live but has no verifiable process fingerprint; it was not signaled and its ownership records were preserved", quoted(n))
	}
	if !isAlive && pendingGen != nil {
		lk := acquireSpawnLock(n, 5*time.Second)
		if !lk.held {
			return fmt.Errorf("pending daemon %s is changing ownership; it was not signaled", quoted(n))
		}
		defer lk.release()
		cur := fingerprintedGeneration(pidPath)
		if cur == nil || *cur != *pendingGen {
			return fmt.Errorf("pending daemon %s changed ownership; the successor was not signaled and its records were preserved", quoted(n))
		}
		if ipc.Ping(n, 200*time.Millisecond) {
			return fmt.Errorf("pending daemon %s became ready during cancellation; run --reload again", quoted(n))
		}
		terminate(pendingGen.PID)
		ipc.CleanupEndpoint(n)
		_ = os.Remove(pidPath)
		return nil
	}
	// The socket can vanish before the process exits (slow cloud stop), so keep a
	// start-time fingerprint as a second identity check before any SIGTERM.
	startFP := processStartTime(daemonPid)
	if isAlive {
		cloud := DaemonBrowserKind(n) == "cloud"
		timeout := 5 * time.Second
		if requireClean || cloud {
			timeout = 50 * time.Second
		}
		m, err := ipc.Call(n, timeout, map[string]any{"meta": "shutdown"})
		if cloud && !requireClean && err == nil && m["ok"] != true {
			// Killing it now would leave the cloud browser billing with nobody left to stop it.
			return fmt.Errorf("daemon %s could not stop its cloud browser and was left running so you can retry: %v", quoted(n), m["error"])
		}
		if requireClean {
			if err != nil {
				return fmt.Errorf("daemon %s did not confirm clean shutdown: %v", quoted(n), err)
			}
			if m["ok"] != true || truthy(m["error"]) {
				if e, ok := m["error"].(string); ok && e != "" {
					return errors.New(e)
				}
				return fmt.Errorf("daemon %s did not confirm clean shutdown", quoted(n))
			}
		}
	}
	if daemonPid != 0 {
		gone := false
		for i := 0; i < 75; i++ {
			if !alive(daemonPid) {
				gone = true
				break
			}
			time.Sleep(200 * time.Millisecond)
		}
		if !gone {
			verified := ipc.Identify(n, time.Second)
			same := verified == daemonPid || (startFP != "" && processStartTime(daemonPid) == startFP)
			if same {
				terminate(daemonPid)
			}
		}
	}
	ipc.CleanupEndpoint(n)
	_ = os.Remove(pidPath)
	return nil
}

func truthy(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case string:
		return t != ""
	case bool:
		return t
	}
	return true
}
