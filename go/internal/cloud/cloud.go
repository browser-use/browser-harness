// Package cloud is the Browser Use Cloud API client: browsers and profiles.
package cloud

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/browser-use/browser-harness/go/internal/auth"
)

// API is the Browser Use Cloud API base; tests point it at a fake.
var API = "https://api.browser-use.com/api/v3"

// Request sends one authenticated API call and decodes its JSON reply ({} when empty).
func Request(ctx context.Context, method, path string, body any) (any, error) {
	key, err := auth.APIKey()
	if err != nil {
		return nil, err
	}
	var rd io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		rd = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, API+path, rd)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Browser-Use-API-Key", key)
	req.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: 60 * time.Second}).Do(req)
	if err != nil {
		return nil, err
	}
	defer func() { _ = resp.Body.Close() }()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("%s %s: %s", method, path, resp.Status)
	}
	if len(bytes.TrimSpace(data)) == 0 {
		return map[string]any{}, nil
	}
	var out any
	return out, json.Unmarshal(data, &out)
}

// StopBrowser stops a billable cloud browser, trying three times.
func StopBrowser(ctx context.Context, id string) error {
	if id == "" {
		return nil
	}
	var err error
	for attempt := range 3 {
		if attempt > 0 {
			time.Sleep(time.Duration(attempt) * 500 * time.Millisecond)
		}
		// Each try is short: the daemon stops its browser inside a 50 s shutdown request.
		actx, cancel := context.WithTimeout(ctx, 15*time.Second)
		_, err = Request(actx, http.MethodPatch, "/browsers/"+id, map[string]any{"action": "stop"})
		cancel()
		if err == nil {
			return nil
		}
	}
	return fmt.Errorf("stop cloud browser %s: %w", id, err)
}
