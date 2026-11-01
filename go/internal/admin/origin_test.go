package admin

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/browser-use/browser-harness/go/internal/browser"
)

// originProfile fakes a macOS home holding only a Brave Origin profile.
func originProfile(t *testing.T) string {
	t.Helper()
	home := t.TempDir()
	t.Setenv("HOME", home)
	saved := browser.GOOS
	browser.GOOS = "darwin"
	t.Cleanup(func() { browser.GOOS = saved })
	p := filepath.Join(home, "Library/Application Support/BraveSoftware/Brave-Origin")
	if err := os.MkdirAll(p, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(p, "Local State"), []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestOriginRunningWithoutGoogleChrome(t *testing.T) {
	p := originProfile(t)
	if browser.SupportedBrowserRunning() {
		t.Fatal("profile directory alone counted as running")
	}
	if err := os.Symlink(fmt.Sprintf("test-host-%d", os.Getpid()), filepath.Join(p, "SingletonLock")); err != nil {
		t.Fatal(err)
	}
	if !browser.SupportedBrowserRunning() {
		t.Fatal("running Brave Origin not detected")
	}
}

func TestOriginPortDiscoveryKeepsPermissionGate(t *testing.T) {
	for _, status := range []int{404, 403} {
		p := originProfile(t)
		t.Setenv("BU_CDP_WS", "")
		t.Setenv("BU_CDP_URL", "")
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path != "/json/version" {
				t.Errorf("unexpected path %s", r.URL.Path)
			}
			w.WriteHeader(status)
		}))
		u, _ := url.Parse(srv.URL)
		_ = os.WriteFile(filepath.Join(p, "DevToolsActivePort"), []byte(u.Port()+"\n/devtools/browser/origin\n"), 0o644)
		ws, err := browser.WSURL()
		srv.Close()
		if status == 403 {
			if err == nil || !strings.Contains(err.Error(), "permission-blocked") {
				t.Errorf("403: %q %v", ws, err)
			}
		} else if ws != "ws://127.0.0.1:"+u.Port()+"/devtools/browser/origin" {
			t.Errorf("404: %q %v", ws, err)
		}
	}
}

func TestOriginRelaunchUsesOrigin(t *testing.T) {
	p := originProfile(t)
	t.Setenv("BH_CHROME_PATH", "")
	t.Setenv("CHROME_PATH", "")
	var calls [][]string
	saved := openApp
	openApp = func(args ...string) error { calls = append(calls, args); return nil }
	t.Cleanup(func() { openApp = saved })
	r := launchBrowser()
	if r == nil || r.proc != nil || r.profile != p {
		t.Fatalf("launch %+v", r)
	}
	if !reflect.DeepEqual(calls, [][]string{{"-a", "Brave Origin"}}) {
		t.Fatalf("calls %v", calls)
	}
}

func TestLaunchMappingPreservesExistingBrowsers(t *testing.T) {
	for profile, app := range map[string]string{
		"BraveSoftware/Brave-Origin":         "Brave Origin",
		"BraveSoftware/Brave-Browser":        "Brave Browser",
		"Google/Chrome":                      "Google Chrome",
		"Google/Chrome Canary":               "Google Chrome Canary",
		"Application Support/Microsoft Edge": "Microsoft Edge",
	} {
		if got := specFor(profile).macApp; got != app {
			t.Errorf("%s: %s, want %s", profile, got, app)
		}
	}
}
