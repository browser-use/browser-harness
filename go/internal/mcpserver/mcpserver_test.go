package mcpserver

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func connect(t *testing.T) *mcp.ClientSession {
	t.Helper()
	ct, st := mcp.NewInMemoryTransports()
	ctx := context.Background()
	if _, err := newServer("test").Connect(ctx, st, nil); err != nil {
		t.Fatal(err)
	}
	cs, err := mcp.NewClient(&mcp.Implementation{Name: "t"}, nil).Connect(ctx, ct, nil)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { cs.Close() })
	return cs
}

func stub(t *testing.T, daemonErr error, run func(string, json.RawMessage) (string, error)) {
	t.Helper()
	d, r := ensureDaemon, runSnippet
	t.Cleanup(func() { ensureDaemon, runSnippet = d, r })
	ensureDaemon = func() error { return daemonErr }
	runSnippet = func(code string, args json.RawMessage) (any, error) {
		s, err := run(code, args)
		if err != nil {
			return nil, err
		}
		var v any
		_ = json.Unmarshal([]byte(s), &v)
		return v, nil
	}
}

func call(t *testing.T, cs *mcp.ClientSession, name string, args any) *mcp.CallToolResult {
	t.Helper()
	res, err := cs.CallTool(context.Background(), &mcp.CallToolParams{Name: name, Arguments: args})
	if err != nil {
		t.Fatal(err)
	}
	return res
}

func text(r *mcp.CallToolResult) string { return r.Content[0].(*mcp.TextContent).Text }

func TestHelperFailureUsesToolError(t *testing.T) {
	stub(t, nil, func(string, json.RawMessage) (string, error) { return "", errors.New("browser closed") })
	r := call(t, connect(t), "browser_page_info", map[string]any{})
	if !r.IsError || text(r) != "browser closed" {
		t.Fatalf("%+v", r)
	}
}

func TestDaemonFailureUsesToolError(t *testing.T) {
	stub(t, errors.New("no browser"), func(string, json.RawMessage) (string, error) {
		t.Fatal("snippet ran without a daemon")
		return "", nil
	})
	if r := call(t, connect(t), "browser_list_tabs", nil); !r.IsError || text(r) != "no browser" {
		t.Fatalf("%+v", r)
	}
}

func TestSuccessIsANormalResult(t *testing.T) {
	var gotCode string
	var gotArgs map[string]any
	stub(t, nil, func(code string, args json.RawMessage) (string, error) {
		gotCode = code
		_ = json.Unmarshal(args, &gotArgs)
		return `{"ok": true}`, nil
	})
	r := call(t, connect(t), "browser_click", map[string]any{"x": 10, "y": 20})
	if r.IsError || text(r) != `{"ok":true}` {
		t.Fatalf("%+v", r)
	}
	if !strings.Contains(gotCode, "click_at_xy(a.x, a.y, a)") || gotArgs["x"] != 10.0 || len(gotArgs) != 2 {
		t.Fatalf("code %q args %v", gotCode, gotArgs)
	}
}

func TestToolSchemas(t *testing.T) {
	res, err := connect(t).ListTools(context.Background(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(res.Tools) != len(tools) {
		t.Fatalf("%d tools", len(res.Tools))
	}
	for _, tl := range res.Tools {
		if tl.Name != "browser_click" {
			continue
		}
		raw, _ := json.Marshal(tl.InputSchema)
		var s struct {
			Required   []string                  `json:"required"`
			Properties map[string]map[string]any `json:"properties"`
		}
		_ = json.Unmarshal(raw, &s)
		if strings.Join(s.Required, ",") != "x,y" || s.Properties["button"]["default"] != "left" {
			t.Fatalf("schema %s", raw)
		}
	}
}
