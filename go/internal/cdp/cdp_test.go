package cdp

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/coder/websocket"
)

// Chrome can drop commands that race the close of their target; the client
// must fail them when the session detaches instead of waiting forever.
func TestDetachedSessionFailsPendingAndLaterCalls(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ws, err := websocket.Accept(w, r, nil)
		if err != nil {
			return
		}
		ctx := context.Background()
		for {
			_, data, err := ws.Read(ctx)
			if err != nil {
				return
			}
			var m struct{ SessionID string }
			_ = json.Unmarshal(data, &m)
			if m.SessionID == "S" {
				ev, _ := json.Marshal(map[string]any{"method": "Target.detachedFromTarget", "params": map[string]any{"sessionId": "S"}})
				_ = ws.Write(ctx, websocket.MessageText, ev)
			}
		}
	}))
	defer srv.Close()
	c, err := Dial(context.Background(), "ws"+strings.TrimPrefix(srv.URL, "http"), time.Second, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	for i := 0; i < 2; i++ {
		if _, err := c.Send(ctx, "Runtime.evaluate", nil, "S"); err == nil || !strings.Contains(err.Error(), "Session with given id not found") {
			t.Fatalf("call %d: got %v", i, err)
		}
	}
}
