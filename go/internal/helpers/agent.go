package helpers

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

// wrappers are processes between an agent and the CLI that do not identify the agent.
var wrappers = map[string]bool{
	"sh": true, "bash": true, "zsh": true, "dash": true, "fish": true, "ksh": true, "csh": true, "tcsh": true,
	"timeout": true, "env": true, "nice": true, "nohup": true, "xargs": true, "sudo": true, "time": true,
	"stdbuf": true, "browser-harness": true,
}

// AgentID names the agent running this snippet, so each agent keeps its own current tab
// across its snippets. BH_AGENT_ID wins ("none" turns this off); otherwise it is the
// nearest ancestor process that is not a shell or wrapper, e.g. the coding agent itself.
func AgentID() string {
	id, _ := AgentIdentity()
	return id
}

// AgentIdentity is AgentID plus the agent process's name, when it was detected.
func AgentIdentity() (id, name string) {
	if v := strings.TrimSpace(os.Getenv("BH_AGENT_ID")); v != "" {
		if v == "none" {
			return "", ""
		}
		return "id:" + v, ""
	}
	pid := os.Getppid()
	for i := 0; i < 32 && pid > 1; i++ { // deep enough for nested shells and wrappers
		name, ppid, start, ok := procInfo(pid)
		if !ok {
			return "", ""
		}
		if base := strings.TrimPrefix(filepath.Base(name), "-"); !wrappers[base] {
			return fmt.Sprintf("pid:%d:%s", pid, start), base // start time guards against PID reuse
		}
		pid = ppid
	}
	return "", ""
}

// procInfo is a process's name, parent and start time.
func procInfo(pid int) (name string, ppid int, start string, ok bool) {
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
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		out, err := exec.CommandContext(ctx, "ps", "-o", "ppid=,lstart=,comm=", "-p", strconv.Itoa(pid)).Output() //nolint:gosec // Query process metadata using an integer PID.
		f := strings.Fields(string(out))
		if err != nil || len(f) < 7 { // ppid, 5 lstart fields, command
			return "", 0, "", false
		}
		ppid, _ = strconv.Atoi(f[0])
		return strings.Join(f[6:], " "), ppid, strings.Join(f[1:6], " "), true
	}
	return "", 0, "", false // Windows: agents set BH_AGENT_ID
}
