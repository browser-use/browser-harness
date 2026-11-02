package helpers

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/browser-use/browser-harness/go/internal/proc"
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
		name, ppid, start, ok := proc.Info(pid)
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
