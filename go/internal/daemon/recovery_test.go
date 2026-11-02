package daemon

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/coder/websocket"

	"github.com/browser-use/browser-harness/go/internal/cdp"
)

// fakeChrome answers the few browser-level calls attachFirstPage makes.
func fakeChrome(t *testing.T) *cdp.Client {
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
			var m struct {
				ID     int64  `json:"id"`
				Method string `json:"method"`
			}
			_ = json.Unmarshal(data, &m)
			res := `{}`
			switch m.Method {
			case "Target.getTargets":
				res = `{"targetInfos":[{"targetId":"USER","type":"page","url":"https://mail.example.com/","title":"Inbox"}]}`
			case "Target.createTarget":
				res = `{"targetId":"BLANK"}`
			case "Target.attachToTarget":
				res = `{"sessionId":"S1"}`
			}
			_ = ws.Write(ctx, websocket.MessageText, []byte(fmt.Sprintf(`{"id":%d,"result":%s}`, m.ID, res)))
		}
	}))
	t.Cleanup(srv.Close)
	c, err := cdp.Dial(context.Background(), "ws"+strings.TrimPrefix(srv.URL, "http"), time.Second, nil)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { c.Close() })
	return c
}

func TestLocalRecoveryNeverTakesAUserTab(t *testing.T) {
	d := New(Config{Name: "default", Kind: "local"}, func(string) {})
	d.cdp = fakeChrome(t)
	page, err := d.attachFirstPage(context.Background(), "OLD", false)
	if err != nil || page.TargetID != "BLANK" {
		t.Fatalf("recovered onto %+v (%v)", page, err)
	}
	// A fresh start still attaches to the first real tab, as before.
	page, err = d.attachFirstPage(context.Background(), "", false)
	if err != nil || page.TargetID != "USER" {
		t.Fatalf("start attached %+v (%v)", page, err)
	}
}
