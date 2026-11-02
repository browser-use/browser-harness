package daemon

import (
	"context"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/coder/websocket"

	"github.com/browser-use/browser-harness/go/internal/cdp"
)

// A request whose client hung up must stop waiting on Chrome.
func TestRequestEndsWhenClientDisconnects(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ws, err := websocket.Accept(w, r, nil)
		if err != nil {
			return
		}
		for { // read and never reply
			if _, _, err := ws.Read(context.Background()); err != nil {
				return
			}
		}
	}))
	defer srv.Close()
	d := New(Config{Name: "t", Kind: "cdp"}, func(string) {})
	c, err := cdp.Dial(context.Background(), "ws"+strings.TrimPrefix(srv.URL, "http"), time.Second, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	d.cdp = c
	client, server := net.Pipe()
	done := make(chan struct{})
	go func() { d.serveConn(context.Background(), server, ""); close(done) }()
	client.Write([]byte(`{"method":"Runtime.evaluate","params":{"expression":"1"}}` + "\n"))
	time.Sleep(100 * time.Millisecond)
	client.Close()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("handler still waiting after its client disconnected")
	}
}
