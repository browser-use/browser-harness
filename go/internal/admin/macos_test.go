package admin

import (
	"context"
	"strings"
	"testing"
)

const chromeRoot = "/tmp/Google Chrome"

func stubMac(t *testing.T, ready []bool, toggles []string, run func(context.Context, string) (string, string, error)) *[]string {
	t.Helper()
	saved := []any{macGOOS, macDaemonReady, macToggleProfiles, macChromeRoot, runOsascript}
	t.Cleanup(func() {
		macGOOS = saved[0].(string)
		macDaemonReady = saved[1].(func() bool)
		macToggleProfiles = saved[2].(func() []string)
		macChromeRoot = saved[3].(func() string)
		runOsascript = saved[4].(func(context.Context, string) (string, string, error))
	})
	macGOOS = "darwin"
	macDaemonReady = func() bool {
		if len(ready) == 0 {
			return false
		}
		r := ready[0]
		ready = ready[1:]
		return r
	}
	macToggleProfiles = func() []string { return toggles }
	macChromeRoot = func() string { return chromeRoot }
	var scripts []string
	runOsascript = func(ctx context.Context, script string) (string, string, error) {
		scripts = append(scripts, script)
		if run == nil {
			t.Fatal("osascript should not run")
		}
		return run(ctx, script)
	}
	return &scripts
}

func osaOut(out string) func(context.Context, string) (string, string, error) {
	return func(context.Context, string) (string, string, error) { return out, "", nil }
}

func TestMacApproveRequiresPersistentChromeCheckbox(t *testing.T) {
	stubMac(t, nil, []string{"/tmp/Edge"}, nil)
	status, detail := approveRemoteDebugging()
	if status != "setup-required" || !strings.Contains(detail, "chrome://inspect/#remote-debugging") {
		t.Fatalf("%s %s", status, detail)
	}
}

func TestMacApproveRunsOsascriptAfterCheckbox(t *testing.T) {
	scripts := stubMac(t, nil, []string{chromeRoot}, osaOut("ready\n"))
	if s, d := approveRemoteDebugging(); s != "ready" || d != "" {
		t.Fatalf("%s %s", s, d)
	}
	sc := (*scripts)[0]
	if !strings.Contains(sc, "Allow remote debugging?") || !strings.Contains(sc, "AXPress") || strings.Contains(sc, "activate") {
		t.Fatal("unexpected script")
	}
}

func TestMacApproveNotFound(t *testing.T) {
	stubMac(t, nil, []string{chromeRoot}, osaOut("not-found\n"))
	if s, d := approveRemoteDebugging(); s != "not-found" || !strings.Contains(d, "retry the browser command") {
		t.Fatalf("%s %s", s, d)
	}
}

func TestMacApproveReadyWithoutOsascript(t *testing.T) {
	stubMac(t, []bool{true}, nil, nil)
	if s, _ := approveRemoteDebugging(); s != "ready" {
		t.Fatal(s)
	}
}

func TestMacApproveDetectsAcceptWhileChecking(t *testing.T) {
	stubMac(t, []bool{false, true}, []string{chromeRoot}, osaOut("not-found\n"))
	if s, _ := approveRemoteDebugging(); s != "ready" {
		t.Fatal(s)
	}
}

func TestMacApprovePendingAccessibilityConsent(t *testing.T) {
	stubMac(t, nil, []string{chromeRoot}, func(ctx context.Context, _ string) (string, string, error) {
		<-ctx.Done()
		return "", "", ctx.Err()
	})
	if s, d := approveRemoteDebugging(); s != "accessibility-required" || !strings.Contains(d, "Accessibility") {
		t.Fatalf("%s %s", s, d)
	}
}

func TestMacApproveUnsupportedOffMac(t *testing.T) {
	stubMac(t, nil, nil, nil)
	macGOOS = "linux"
	if s, d := approveRemoteDebugging(); s != "unsupported" || d != "mac-approve is only available on macOS" {
		t.Fatalf("%s %s", s, d)
	}
}
