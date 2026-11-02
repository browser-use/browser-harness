package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/daemon"
	"github.com/browser-use/browser-harness/go/internal/ipc"
)

// runDaemon is `browser-harness __daemon`: the long-lived CDP holder.
func runDaemon() int {
	cfg := daemon.ConfigFromEnv()
	if err := ipc.Check(cfg.Name); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if ipc.Ping(cfg.Name, time.Second) {
		fmt.Fprintf(os.Stderr, "daemon already running on %s\n", ipc.SockAddr(cfg.Name))
		return 0
	}
	logPath := ipc.LogPath(cfg.Name)
	_ = os.WriteFile(logPath, nil, 0o600)
	logf := func(msg string) {
		f, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600) //nolint:gosec // The daemon log path comes from the local runtime configuration.
		if err != nil {
			return
		}
		_, _ = fmt.Fprintln(f, msg)
		_ = f.Close()
	}
	pidPath := ipc.PidPath(cfg.Name)
	publishOwnPID(pidPath)
	d := daemon.New(cfg, logf)
	code := 0
	ctx := context.Background()
	if err := d.Start(ctx); err != nil {
		logf("fatal: " + err.Error())
		code = 1
	} else if err := d.Serve(ctx); err != nil {
		logf("fatal: " + err.Error())
		code = 1
	}
	_ = d.StopRemote(ctx, false)
	_ = os.Remove(pidPath)
	return code
}

// publishOwnPID keeps a parent-published fingerprint record for this PID and
// never truncates it, so a cold caller cannot observe an empty PID file.
func publishOwnPID(path string) {
	pid := os.Getpid()
	published := strconv.Itoa(pid)
	if raw, err := os.ReadFile(path); err == nil { //nolint:gosec // Read the local daemon PID record.
		var rec struct {
			PID json.Number `json:"pid"`
		}
		filePID := 0
		if json.Unmarshal(raw, &rec) == nil {
			filePID, _ = strconv.Atoi(rec.PID.String())
		} else if f := strings.Fields(string(raw)); len(f) > 0 {
			filePID, _ = strconv.Atoi(f[0])
		}
		if filePID == pid {
			published = string(raw)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		_ = err
	}
	tmp := fmt.Sprintf("%s.%d.tmp", path, pid)
	if os.WriteFile(tmp, []byte(published), 0o600) == nil {
		_ = os.Rename(tmp, path)
	}
}
