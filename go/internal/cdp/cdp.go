// Package cdp is a minimal flat-session Chrome DevTools Protocol client.
package cdp

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/coder/websocket"
)

// MaxFrame matches cdp-use's 100 MB default; screenshots and DOM dumps are large.
const MaxFrame = 100 << 20

// Error is a CDP error response.
type Error struct{ raw json.RawMessage }

func (e *Error) Error() string {
	var v struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
		Data    string `json:"data"`
	}
	if json.Unmarshal(e.raw, &v) != nil || v.Message == "" {
		return string(e.raw)
	}
	if v.Data != "" {
		return fmt.Sprintf("%s: %s (CDP %d)", v.Message, v.Data, v.Code)
	}
	return fmt.Sprintf("%s (CDP %d)", v.Message, v.Code)
}

// ErrClosed matches cdp-use's message when the socket drops mid-call.
var ErrClosed = errors.New("WebSocket connection closed")

type response struct {
	ID      int64           `json:"id"`
	Result  json.RawMessage `json:"result"`
	Error   json.RawMessage `json:"error"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params"`
	Session string          `json:"sessionId"`
}

// EventFunc receives every CDP event, in arrival order.
type EventFunc func(method string, params json.RawMessage, sessionID string)

type call struct {
	ch      chan response
	session string
}

type Client struct {
	ws       *websocket.Conn
	mu       sync.Mutex
	nextID   int64
	pending  map[int64]call
	detached [2]map[string]bool // recent detached sessions; two generations keep it bounded
	onEvent  EventFunc
	done     chan struct{}
	err      error
}

const maxDetached = 512

// detachedReply is Chrome's own error for an unknown session, so callers recover the same way.
var detachedReply = json.RawMessage(`{"code":-32001,"message":"Session with given id not found."}`)

// Dial connects to a CDP websocket. timeout 0 waits indefinitely: a local
// Chrome holds the handshake open while its "Allow remote debugging?" sheet is shown.
func Dial(ctx context.Context, url string, timeout time.Duration, onEvent EventFunc) (*Client, error) {
	dctx := ctx
	if timeout > 0 {
		var cancel context.CancelFunc
		dctx, cancel = context.WithTimeout(ctx, timeout)
		defer cancel()
	}
	ws, resp, err := websocket.Dial(dctx, url, &websocket.DialOptions{HTTPHeader: http.Header{}})
	if err != nil {
		if resp != nil {
			_ = resp.Body.Close()
			return nil, fmt.Errorf("server rejected WebSocket connection: HTTP %d", resp.StatusCode)
		}
		if errors.Is(err, context.DeadlineExceeded) {
			return nil, errors.New("timed out during opening handshake")
		}
		return nil, err
	}
	ws.SetReadLimit(MaxFrame)
	c := &Client{ws: ws, pending: map[int64]call{}, detached: [2]map[string]bool{{}, {}}, onEvent: onEvent, done: make(chan struct{})}
	// The connection outlives the opening handshake and individual callers.
	go c.readLoop(context.WithoutCancel(ctx))
	return c, nil
}

func (c *Client) readLoop(ctx context.Context) {
	defer func() {
		c.mu.Lock()
		if c.err == nil {
			c.err = ErrClosed
		}
		for id, p := range c.pending {
			close(p.ch)
			delete(c.pending, id)
		}
		c.mu.Unlock()
		close(c.done)
	}()
	for {
		_, data, err := c.ws.Read(ctx)
		if err != nil {
			return
		}
		var r response
		if json.Unmarshal(data, &r) != nil {
			continue
		}
		if r.Method != "" && r.ID == 0 {
			if r.Method == "Target.detachedFromTarget" {
				c.failSession(r.Params)
			}
			if c.onEvent != nil {
				c.onEvent(r.Method, r.Params, r.Session)
			}
			continue
		}
		c.mu.Lock()
		p, ok := c.pending[r.ID]
		delete(c.pending, r.ID)
		c.mu.Unlock()
		if ok {
			p.ch <- r
		}
	}
}

// Done closes when the websocket is gone.
func (c *Client) Done() <-chan struct{} { return c.done }

// Send issues one CDP call and waits for its reply, honouring ctx.
func (c *Client) Send(ctx context.Context, method string, params any, sessionID string) (json.RawMessage, error) {
	if params == nil {
		params = map[string]any{}
	}
	c.mu.Lock()
	if c.err != nil {
		c.mu.Unlock()
		return nil, c.err
	}
	if c.detached[0][sessionID] || c.detached[1][sessionID] {
		c.mu.Unlock()
		return nil, &Error{raw: detachedReply}
	}
	c.nextID++
	id := c.nextID
	ch := make(chan response, 1)
	c.pending[id] = call{ch, sessionID}
	c.mu.Unlock()
	msg := map[string]any{"id": id, "method": method, "params": params}
	if sessionID != "" {
		msg["sessionId"] = sessionID
	}
	b, err := json.Marshal(msg)
	if err == nil {
		err = c.ws.Write(ctx, websocket.MessageText, b)
	}
	if err != nil {
		c.forget(id)
		return nil, err
	}
	select {
	case r, ok := <-ch:
		if !ok {
			return nil, ErrClosed
		}
		if len(r.Error) > 0 && string(r.Error) != "null" {
			return nil, &Error{raw: r.Error}
		}
		if len(r.Result) == 0 {
			return json.RawMessage("{}"), nil
		}
		return r.Result, nil
	case <-ctx.Done():
		c.forget(id)
		return nil, ctx.Err()
	}
}

// failSession answers calls on a detached session: Chrome may never reply to
// commands that raced the close of their target.
func (c *Client) failSession(params json.RawMessage) {
	var v struct {
		SessionID string `json:"sessionId"`
	}
	if json.Unmarshal(params, &v) != nil || v.SessionID == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.detached[0]) >= maxDetached {
		c.detached = [2]map[string]bool{{}, c.detached[0]}
	}
	c.detached[0][v.SessionID] = true
	for id, p := range c.pending {
		if p.session == v.SessionID {
			p.ch <- response{ID: id, Error: detachedReply}
			delete(c.pending, id)
		}
	}
}

func (c *Client) forget(id int64) {
	c.mu.Lock()
	delete(c.pending, id)
	c.mu.Unlock()
}

func (c *Client) Close() error { return c.ws.Close(websocket.StatusNormalClosure, "") }
