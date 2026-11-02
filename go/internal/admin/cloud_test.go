package admin

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os/exec"
	"strings"
	"syscall"
	"testing"
	"time"

	"github.com/browser-use/browser-harness/go/internal/cloud"
	"github.com/browser-use/browser-harness/go/internal/ipc"
)

func TestCleanupCloudBrowsers(t *testing.T) {
	old := time.Now().Add(-2 * time.Hour).UTC().Format(time.RFC3339)
	fresh := time.Now().Add(-time.Minute).UTC().Format(time.RFC3339)
	var stopped []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == "GET" && r.URL.Query().Get("pageNumber") == "1":
			json.NewEncoder(w).Encode(map[string]any{"totalItems": 3, "items": []any{
				map[string]any{"id": "old", "startedAt": old},
				map[string]any{"id": "fresh", "startedAt": fresh},
				map[string]any{"id": "done", "startedAt": old, "finishedAt": old},
			}})
		case r.Method == "PATCH":
			stopped = append(stopped, r.URL.Path)
			w.Write([]byte("{}"))
		default:
			t.Errorf("unexpected %s %s", r.Method, r.URL)
		}
	}))
	defer srv.Close()
	prev := cloud.API
	cloud.API = srv.URL
	defer func() { cloud.API = prev }()
	t.Setenv("BROWSER_USE_API_KEY", "test")

	got, err := CleanupCloudBrowsers(30*time.Minute, true)
	if err != nil || len(got) != 2 || got[0]["action"] != "would_stop" || got[1]["action"] != "skipped" || len(stopped) != 0 {
		t.Fatalf("dry run: %v %v %v", got, err, stopped)
	}
	got, err = CleanupCloudBrowsers(30*time.Minute, false)
	if err != nil || got[0]["action"] != "stopped" || len(stopped) != 1 || stopped[0] != "/browsers/old" {
		t.Fatalf("stop: %v %v %v", got, err, stopped)
	}
}

func TestInvalidDaemonNamesAreRejected(t *testing.T) {
	for _, err := range []error{EnsureDaemon(0, "../x", nil), RestartDaemon("../x", false), func() error { _, e := StartRemoteDaemon("a/b", "", nil); return e }()} {
		if err == nil || !strings.Contains(err.Error(), "invalid BU_NAME") {
			t.Errorf("got %v", err)
		}
	}
}

// A cloud daemon that cannot stop its browser must stay up and --reload must fail.
func TestReloadKeepsCloudDaemonWhoseStopFailed(t *testing.T) {
	t.Setenv("BH_RUNTIME_DIR", t.TempDir())
	sleeper := exec.Command("sleep", "30")
	if err := sleeper.Start(); err != nil {
		t.Skip(err)
	}
	defer sleeper.Process.Kill()
	l, _, err := ipc.Listen(t.Context(), "cloudt")
	if err != nil {
		t.Fatal(err)
	}
	defer l.Close()
	go func() {
		for {
			c, err := l.Accept()
			if err != nil {
				return
			}
			go func() {
				defer c.Close()
				var req map[string]any
				if json.NewDecoder(c).Decode(&req) != nil {
					return
				}
				resp := map[string]any{"pong": true, "pid": sleeper.Process.Pid, "browser_kind": "cloud"}
				if req["meta"] == "shutdown" {
					resp = map[string]any{"error": "PATCH /browsers/x failed"}
				}
				b, _ := json.Marshal(resp)
				c.Write(append(b, '\n'))
			}()
		}
	}()
	err = RestartDaemon("cloudt", false)
	if err == nil || !strings.Contains(err.Error(), "could not stop its cloud browser") {
		t.Fatalf("got %v", err)
	}
	if sleeper.ProcessState != nil || sleeper.Process.Signal(syscall.Signal(0)) != nil {
		t.Fatal("daemon process was killed")
	}
}

// Goroutines of one process must not both hold the start lock.
func TestStartLockSerialisesGoroutines(t *testing.T) {
	t.Setenv("BH_RUNTIME_DIR", t.TempDir())
	first, err := lockStart("same", "start", time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := lockStart("same", "start", 300*time.Millisecond); err == nil {
		t.Fatal("second holder in the same process")
	}
	first.release()
	again, err := lockStart("same", "start", time.Second)
	if err != nil {
		t.Fatal(err)
	}
	again.release()
}

// Doctor reads kind, tab count, names and per-agent tabs from the daemon status.
func TestConnectionCarriesTabsAndAgents(t *testing.T) {
	t.Setenv("BH_RUNTIME_DIR", t.TempDir())
	l, _, err := ipc.Listen(t.Context(), "doc")
	if err != nil {
		t.Fatal(err)
	}
	defer l.Close()
	go func() {
		for {
			c, err := l.Accept()
			if err != nil {
				return
			}
			go func() {
				defer c.Close()
				var req map[string]any
				_ = json.NewDecoder(c).Decode(&req)
				b, _ := json.Marshal(map[string]any{"page": map[string]any{"title": "T", "url": "https://a.test/"}, "kind": "cloud", "tabs": 3,
					"names": map[string]any{"cart": "X"}, "agents": []any{map[string]any{"agent": "id:bob", "title": "B", "url": "https://b.test/"}}})
				_, _ = c.Write(append(b, '\n'))
			}()
		}
	}()
	c := daemonConnection("doc")
	if c == nil || c.Kind != "cloud" || c.Tabs != 3 || len(c.Names) != 1 || c.Names[0] != "cart" || len(c.Agents) != 1 || c.Agents[0].URL != "https://b.test/" {
		t.Fatalf("got %+v", c)
	}
}
