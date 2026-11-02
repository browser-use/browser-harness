// Package proc is the process plumbing shared by the CLI and the daemon:
// detaching, signalling, file locks and per-process identity.
package proc

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"time"
)

// Output runs name with args and returns its stdout, killing it after timeout.
func Output(timeout time.Duration, name string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...) //nolint:gosec // Callers pass fixed tools and integer PIDs.
	cmd.WaitDelay = time.Second                    // a grandchild holding stdout must not outlast the timeout
	out, err := cmd.Output()
	return string(out), err
}

// Info is a process's name, parent and start time; ok is false where it cannot be read (Windows).
func Info(pid int) (name string, ppid int, start string, ok bool) {
	switch runtime.GOOS {
	case "linux":
		raw, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
		if err != nil {
			return "", 0, "", false
		}
		s := string(raw)
		open, end := strings.IndexByte(s, '('), strings.LastIndexByte(s, ')')
		if open < 0 || end < open {
			return "", 0, "", false
		}
		f := strings.Fields(s[end+1:])
		if len(f) < 20 {
			return "", 0, "", false
		}
		ppid, _ = strconv.Atoi(f[1])
		return s[open+1 : end], ppid, f[19], true
	case "darwin":
		out, err := Output(2*time.Second, "ps", "-o", "ppid=,lstart=,comm=", "-p", strconv.Itoa(pid))
		f := strings.Fields(out)
		if err != nil || len(f) < 7 { // ppid, 5 lstart fields, command
			return "", 0, "", false
		}
		ppid, _ = strconv.Atoi(f[0])
		return strings.Join(f[6:], " "), ppid, strings.Join(f[1:6], " "), true
	}
	return "", 0, "", false
}

// StartTime is an opaque fingerprint of pid's start, used to detect PID reuse; "" when unknown.
func StartTime(pid int) string {
	if pid <= 0 {
		return ""
	}
	if runtime.GOOS == "windows" {
		return windowsStartTime(pid)
	}
	_, _, start, _ := Info(pid)
	return start
}
