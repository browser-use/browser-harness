package helpers

import (
	"testing"
	"time"
)

func TestAgentTabFollowsTheAgentAcrossSnippets(t *testing.T) {
	tabs := map[string]string{} // the daemon's agent -> tab map
	daemon := func(req M, _ time.Duration) (M, error) {
		switch req["meta"] {
		case "agent_tab":
			a, _ := req["agent"].(string)
			if set, ok := req["set"].(string); ok {
				tabs[a] = set
				return M{"ok": true}, nil
			}
			return M{"target_id": tabs[a]}, nil
		case "attach":
			return M{"session_id": "S-" + req["target_id"].(string)}, nil
		case "current_tab":
			return M{"targetId": "SHARED", "url": "https://shared.test/"}, nil
		}
		if req["method"] == "Target.createTarget" {
			return M{"result": M{"targetId": "MINE"}}, nil
		}
		return M{"result": M{}}, nil
	}
	first := &H{Name: "t", Send: daemon}
	if err := first.UseAgentTab("agent-a"); err != nil || first.Target != "" {
		t.Fatalf("no tab yet: %v %q", err, first.Target)
	}
	if _, err := first.NewTab("https://mine.test/"); err != nil || first.Target != "MINE" {
		t.Fatalf("new_tab did not adopt: %v %q", err, first.Target)
	}
	// A later snippet of the same agent resumes on its own tab, not the daemon's shared one.
	next := &H{Name: "t", Send: daemon}
	if err := next.UseAgentTab("agent-a"); err != nil || next.Target != "MINE" || next.session != "S-MINE" {
		t.Fatalf("resume: %v %q %q", err, next.Target, next.session)
	}
	other := &H{Name: "t", Send: daemon}
	if _, _ = other.UseAgentTab("agent-b"), other.Target; other.Target != "" {
		t.Fatalf("another agent got %q", other.Target)
	}
	if err := next.CloseTab(""); err != nil || next.Target != "" || tabs["agent-a"] != "" {
		t.Fatalf("close: %v %q %q", err, next.Target, tabs["agent-a"])
	}
}
