package admin

import (
	"os"
	"strings"

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
func startingDaemonPid(name string) int {
	g, _ := liveGeneration(name)
	return g.PID
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
