package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"

	"github.com/browser-use/browser-harness/go/internal/admin"
)

// callArgs is the JSON argument object the Python wrappers send.
type callArgs struct {
	Name           string            `json:"name"`
	Wait           *float64          `json:"wait"`
	Env            map[string]string `json:"env"`
	RequireClean   bool              `json:"require_clean"`
	ProfileName    string            `json:"profileName"`
	Create         map[string]any    `json:"create"`
	Profile        string            `json:"profile_name"`
	Browser        string            `json:"browser"`
	CloudProfileID string            `json:"cloud_profile_id"`
	Include        []string          `json:"include_domains"`
	Exclude        []string          `json:"exclude_domains"`
}

// runCall is `browser-harness-core call <fn> <result-file> [json-args]`. stdout and
// stderr stay the user's; the result or error goes to the result file.
func runCall(args []string) int {
	if len(args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: browser-harness-core call <fn> <result-file> [json-args]")
		return 2
	}
	fn, resultFile := args[0], args[1]
	var a callArgs
	if len(args) > 2 {
		if err := json.Unmarshal([]byte(args[2]), &a); err != nil {
			return writeResult(resultFile, nil, err)
		}
	}
	result, err := call(fn, a)
	return writeResult(resultFile, result, err)
}

func call(fn string, a callArgs) (any, error) {
	switch fn {
	case "ensure_daemon":
		wait := -1.0
		if a.Wait != nil {
			wait = *a.Wait
		}
		return nil, admin.EnsureDaemon(wait, a.Name, a.Env)
	case "require_existing_daemon":
		return nil, admin.RequireExistingDaemon(a.Name)
	case "daemon_alive":
		return admin.DaemonAlive(a.Name), nil
	case "daemon_browser_kind":
		if k := admin.DaemonBrowserKind(a.Name); k != "" {
			return k, nil
		}
		return nil, nil
	case "daemon_browser_ready":
		return admin.DaemonBrowserReady(a.Name), nil
	case "browser_connections":
		return admin.BrowserConnections(), nil
	case "restart_daemon":
		return nil, admin.RestartDaemon(a.Name, a.RequireClean)
	case "stop_remote_daemon":
		return nil, admin.StopRemoteDaemon(a.Name)
	case "start_remote_daemon":
		return admin.StartRemoteDaemon(a.Name, a.ProfileName, a.Create)
	case "list_cloud_profiles":
		return admin.ListCloudProfiles()
	case "list_local_profiles":
		return admin.ListLocalProfiles()
	case "sync_local_profile":
		return admin.SyncLocalProfile(a.Profile, a.Browser, a.CloudProfileID, a.Include, a.Exclude)
	case "check_for_update":
		cur, latest, newer := admin.CheckForUpdate()
		var l any
		if latest != "" {
			l = latest
		}
		return []any{cur, l, newer}, nil
	case "print_update_banner":
		admin.PrintUpdateBanner()
		return nil, nil
	}
	return nil, fmt.Errorf("unknown call %q", fn)
}

func writeResult(path string, result any, err error) int {
	out := map[string]any{"result": result}
	code := 0
	if err != nil {
		out = map[string]any{"error": err.Error()}
		code = 1
	}
	b, merr := json.Marshal(out)
	if merr != nil {
		b, _ = json.Marshal(map[string]any{"error": merr.Error()})
		code = 1
	}
	if werr := os.WriteFile(path, b, 0o600); werr != nil {
		fmt.Fprintln(os.Stderr, errors.Join(werr, err))
		return 1
	}
	return code
}
