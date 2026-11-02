package admin

import (
	"fmt"
	"os"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/ipc"
	"github.com/browser-use/browser-harness/go/internal/proc"
)

// generation is one daemon process: its PID and start time.
type generation struct {
	PID     int
	Started string
}

// liveGeneration is name's recorded daemon while that exact process still runs.
func liveGeneration(name string) (generation, bool) {
	pid, started := ipc.ReadPid(name)
	if pid <= 0 || started == "" || proc.StartTime(pid) != started {
		return generation{}, false
	}
	return generation{pid, started}, true
}

// startingDaemonPid is the PID of name's recorded daemon while it still runs, else 0.
// Without a recorded start time (its lookup failed) the process must at least be a daemon.
func startingDaemonPid(name string) int {
	if g, ok := liveGeneration(name); ok {
		return g.PID
	}
	if pid, started := ipc.ReadPid(name); pid > 0 && started == "" && isDaemonProcess(pid) {
		return pid
	}
	return 0
}

func isDaemonProcess(pid int) bool {
	var out string
	var err error
	if runtime.GOOS == "windows" {
		out, err = proc.Output(2*time.Second, "powershell", "-NoProfile", "-NonInteractive", "-Command",
			fmt.Sprintf("(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine", pid))
	} else {
		out, err = proc.Output(2*time.Second, "ps", "-o", "command=", "-p", strconv.Itoa(pid))
	}
	return err == nil && strings.Contains(out, "__daemon")
}

// parkedDaemonPid finds a daemon still parked on Chrome's Allow popup, which
// has no IPC socket yet; spawning a sibling would raise a second popup.
func parkedDaemonPid(name string) int {
	if !strings.HasPrefix(logTail(name), "handshake-wait") {
		return 0
	}
	return startingDaemonPid(name)
}

func logTail(name string) string {
	raw, err := os.ReadFile(ipc.LogPath(name))
	if err != nil {
		return ""
	}
	lines := strings.Split(strings.TrimSpace(string(raw)), "\n")
	return lines[len(lines)-1]
}
