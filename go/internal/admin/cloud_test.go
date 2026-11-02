package admin

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/browser-use/browser-harness/go/internal/daemon"
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
	prev := daemon.BUAPI
	daemon.BUAPI = srv.URL
	defer func() { daemon.BUAPI = prev }()
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
