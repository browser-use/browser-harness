package daemon

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/browser-use/browser-harness/go/internal/recorder"
)

// page adapts the daemon's attached session for the recorder.
type page struct {
	d   *Daemon
	ctx context.Context
}

func (p page) sid() string {
	p.d.mu.Lock()
	defer p.d.mu.Unlock()
	return p.d.session
}

func (p page) JS(expr string) (map[string]any, error) {
	ctx, cancel := context.WithTimeout(p.ctx, 5*time.Second)
	defer cancel()
	raw, err := p.d.send(ctx, "Runtime.evaluate", map[string]any{"expression": expr, "returnByValue": true}, p.sid())
	if err != nil {
		return nil, err
	}
	var r struct {
		Result struct {
			Value map[string]any `json:"value"`
		} `json:"result"`
		Exception json.RawMessage `json:"exceptionDetails"`
	}
	if err := json.Unmarshal(raw, &r); err != nil {
		return nil, err
	}
	if len(r.Exception) > 0 {
		return nil, errors.New("page context script failed")
	}
	return r.Result.Value, nil
}

// Screenshot uses the same 60 s budget as capture_screenshot(): cloud frames
// routinely exceed the 5 s default.
func (p page) Screenshot() (string, error) {
	ctx, cancel := context.WithTimeout(p.ctx, 60*time.Second)
	defer cancel()
	raw, err := p.d.send(ctx, "Page.captureScreenshot", map[string]any{"format": "jpeg", "quality": 80}, p.sid())
	if err != nil {
		return "", err
	}
	var r struct {
		Data string `json:"data"`
	}
	if err := json.Unmarshal(raw, &r); err != nil {
		return "", err
	}
	return r.Data, nil
}

func decodeCall(req map[string]any) (recorder.Call, error) {
	var c recorder.Call
	raw, err := json.Marshal(req["call"])
	if err != nil {
		return c, err
	}
	return c, json.Unmarshal(raw, &c)
}

// handleRecord serves record_observe, record_start and record_stop.
func (d *Daemon) handleRecord(ctx context.Context, meta string, req map[string]any) map[string]any {
	c, err := decodeCall(req)
	if err != nil {
		return map[string]any{"error": err.Error()}
	}
	p := page{d: d, ctx: ctx}
	switch meta {
	case "record_observe":
		recorder.Observe(c, p)
		return map[string]any{"ok": true}
	case "record_start":
		name, _ := req["name"].(string)
		title, _ := req["title"].(string)
		dir, err := recorder.Start(c.Env, name, title, p)
		if err != nil {
			return map[string]any{"error": err.Error()}
		}
		return map[string]any{"dir": dir}
	case "record_stop":
		dir, frames := recorder.Stop(c.Env, p)
		if dir == "" {
			return map[string]any{"dir": nil, "frames": 0}
		}
		return map[string]any{"dir": dir, "frames": frames}
	}
	return map[string]any{"error": fmt.Sprintf("unknown recording request %q", meta)}
}
