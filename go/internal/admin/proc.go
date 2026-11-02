package admin

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/ipc"
)

// processStartTime is an opaque per-process fingerprint used to detect PID reuse.
func processStartTime(pid int) string {
	if pid <= 0 {
		return ""
	}
	switch runtime.GOOS {
	case "linux":
		raw, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
		if err != nil {
			return ""
		}
		s := string(raw)
		i := strings.LastIndex(s, ")")
		if i < 0 || i+2 > len(s) {
			return ""
		}
		f := strings.Fields(s[i+2:])
		if len(f) < 20 {
			return ""
		}
		return f[19]
	case "darwin":
		out, err := exec.CommandContext(context.Background(), "ps", "-o", "lstart=", "-p", strconv.Itoa(pid)).Output() //nolint:gosec // Query process metadata using an integer PID.
		if err != nil {
			return ""
		}
		return strings.TrimSpace(string(out))
	case "windows":
		return windowsStartTime(pid)
	}
	return ""
}

// isDaemonProcess guards against PID reuse where no fingerprint exists.
func isDaemonProcess(pid int) bool {
	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.CommandContext(context.Background(), "powershell", "-NoProfile", "-NonInteractive", "-Command", //nolint:gosec // The PowerShell expression interpolates only an integer PID.
			fmt.Sprintf("(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine", pid))
	} else {
		cmd = exec.CommandContext(context.Background(), "ps", "-o", "command=", "-p", strconv.Itoa(pid)) //nolint:gosec // Query process metadata using an integer PID.
	}
	out, err := runWithTimeout(cmd, 2*time.Second)
	if err != nil || strings.TrimSpace(out) == "" {
		return false
	}
	return strings.Contains(out, "__daemon") || strings.Contains(out, "browser_harness")
}

func runWithTimeout(cmd *exec.Cmd, d time.Duration) (string, error) {
	done := make(chan struct{})
	var out []byte
	var err error
	go func() { out, err = cmd.Output(); close(done) }()
	select {
	case <-done:
		return string(out), err
	case <-time.After(d):
		if cmd.Process != nil {
			_ = cmd.Process.Kill()
		}
		return "", errors.New("timeout")
	}
}

type pidRecord struct {
	PID         int
	Fingerprint string
	HasJSON     bool
}

func readPidRecord(path string) (pidRecord, bool) {
	raw, err := os.ReadFile(path) //nolint:gosec // Read a local daemon PID record.
	if err != nil {
		return pidRecord{}, false
	}
	var rec struct {
		PID     json.RawMessage `json:"pid"`
		Started *string         `json:"started"`
	}
	if json.Unmarshal(raw, &rec) == nil && len(rec.PID) > 0 {
		pid, err := strconv.Atoi(strings.Trim(string(rec.PID), `"`))
		if err != nil {
			return pidRecord{}, false
		}
		r := pidRecord{PID: pid, HasJSON: true}
		if rec.Started != nil {
			r.Fingerprint = *rec.Started
		}
		return r, true
	}
	f := strings.Fields(string(raw))
	if len(f) == 0 {
		return pidRecord{}, false
	}
	pid, err := strconv.Atoi(f[0])
	if err != nil {
		return pidRecord{}, false
	}
	return pidRecord{PID: pid}, true
}

// pendingPid trusts a PID only with a matching fingerprint, or, for legacy
// records, when the process still looks like one of our daemons.
func pendingPid(path string) int {
	r, ok := readPidRecord(path)
	if !ok || r.PID <= 0 {
		return 0
	}
	if r.Fingerprint != "" {
		if cur := processStartTime(r.PID); cur != "" && cur == r.Fingerprint {
			return r.PID
		}
		return 0
	}
	if isDaemonProcess(r.PID) {
		return r.PID
	}
	return 0
}

type generation struct {
	PID         int
	Fingerprint string
}

// fingerprintedGeneration returns the record only while that exact process lives.
func fingerprintedGeneration(path string) *generation {
	r, ok := readPidRecord(path)
	if !ok || !r.HasJSON || r.Fingerprint == "" || r.PID <= 0 || r.PID >= 1<<31 {
		return nil
	}
	if cur := processStartTime(r.PID); cur != "" && cur == r.Fingerprint {
		return &generation{PID: r.PID, Fingerprint: r.Fingerprint}
	}
	return nil
}

func pidNumber(path string) int {
	r, ok := readPidRecord(path)
	if !ok {
		return 0
	}
	return r.PID
}

func publishPid(path string, pid int) {
	var started any
	if fp := processStartTime(pid); fp != "" {
		started = fp
	}
	b, err := json.Marshal(map[string]any{"pid": pid, "started": started})
	if err != nil {
		return
	}
	tmp := fmt.Sprintf("%s.%d.%d.tmp", path, os.Getpid(), time.Now().UnixNano())
	if os.WriteFile(tmp, b, 0o600) == nil {
		_ = os.Rename(tmp, path)
	}
}

func logTail(name string) string {
	raw, err := os.ReadFile(ipc.LogPath(name))
	if err != nil {
		return ""
	}
	lines := strings.Split(strings.TrimSpace(string(raw)), "\n")
	if len(lines) == 0 {
		return ""
	}
	return lines[len(lines)-1]
}

// parkedDaemonPid finds a daemon still parked on Chrome's Allow popup, which
// has no IPC socket yet; spawning a sibling would raise a second popup.
func parkedDaemonPid(name string) int {
	if !strings.HasPrefix(logTail(name), "handshake-wait") {
		return 0
	}
	return pendingPid(ipc.PidPath(name))
}

func startingDaemonPid(name string) int { return pendingPid(ipc.PidPath(name)) }
