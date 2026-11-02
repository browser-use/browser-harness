package main

import (
	"context"
	"fmt"
	"os"
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
	ipc.WritePid(cfg.Name, os.Getpid()) // the same record the spawning CLI wrote, or the first one
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
	_ = os.Remove(ipc.PidPath(cfg.Name))
	return code
}
