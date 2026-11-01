// Package mcpserver exposes the browser-harness helpers as MCP tools over
// stdio. Each call runs one snippet through the Python runner, so tools see
// exactly the helpers agents use.
package mcpserver

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"strings"
	"sync"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/browser-use/browser-harness/go/internal/admin"
)

type param struct {
	name, typ string
	def       any // nil: required
	nullable  bool
}

type tool struct {
	name, doc, body string
	params          []param
}

func req(name, typ string) param { return param{name: name, typ: typ} }
func opt(name, typ string, def any) param {
	return param{name: name, typ: typ, def: def}
}
func null(name, typ string) param { return param{name: name, typ: typ, nullable: true} }

const ok = "\nresult = {\"ok\": True}"

// Bodies run with the call's arguments in `a`; omitted ones keep the helper defaults.
var tools = []tool{
	{"browser_new_tab", "Open a new browser tab. Returns the new tab's targetId.",
		`result = {"targetId": new_tab(**a)}`, []param{opt("url", "string", "about:blank")}},
	{"browser_goto", "Navigate the current tab to `url`. Returns the navigation result.",
		`result = goto_url(**a)`, []param{req("url", "string")}},
	{"browser_page_info", "Return current tab metadata: url, title, viewport and scroll sizes.",
		`result = page_info()`, nil},
	{"browser_click", "Click at screen coordinates (x, y). `button` is 'left'/'right'/'middle'.",
		`click_at_xy(**a)` + ok, []param{req("x", "integer"), req("y", "integer"), opt("button", "string", "left"), opt("clicks", "integer", 1)}},
	{"browser_type", "Insert text into the focused element.",
		`type_text(**a)` + ok, []param{req("text", "string")}},
	{"browser_fill", "Fill an input matched by `selector` with `text`.",
		`fill_input(**a)` + ok, []param{req("selector", "string"), req("text", "string"), opt("clear_first", "boolean", true)}},
	{"browser_press", "Press a key. `modifiers` is a bitfield: 1=Alt, 2=Ctrl, 4=Meta, 8=Shift.",
		`press_key(**a)` + ok, []param{req("key", "string"), opt("modifiers", "integer", 0)}},
	{"browser_scroll", "Scroll the wheel at (x, y) by `dy` vertical / `dx` horizontal pixels.",
		`scroll(**a)` + ok, []param{req("x", "integer"), req("y", "integer"), opt("dy", "integer", -300), opt("dx", "integer", 0)}},
	{"browser_screenshot", "Capture a PNG screenshot. If `path` is omitted, a temp file is used.\nSet `max_dim` to downscale results larger than that dimension.",
		`p = capture_screenshot(**a)
from PIL import Image
w, h = Image.open(p).size
result = {"path": p, "width": w, "height": h, "size_bytes": os.path.getsize(p)}`,
		[]param{null("path", "string"), opt("full", "boolean", false), null("max_dim", "integer")}},
	{"browser_list_tabs", "List open page tabs.", `result = list_tabs()`, nil},
	{"browser_current_tab", "Return the active tab's targetId, url and title.", `result = current_tab()`, nil},
	{"browser_switch_tab", "Switch to tab by `targetId` or URL substring. Returns the sessionId.",
		`result = {"sessionId": switch_tab(**a)}`, []param{req("target", "string")}},
	{"browser_close_tab", "Close a tab. Without `target`, closes the active tab.",
		`close_tab(**a)` + ok, []param{null("target", "string")}},
	{"browser_ensure_real_tab", "Switch to a real (non-internal) tab if the current one is chrome:// or stale.",
		`result = ensure_real_tab()`, nil},
	{"browser_wait", "Wait for `seconds`.", `wait(**a)` + ok, []param{opt("seconds", "number", 1.0)}},
	{"browser_wait_for_load", "Wait until the current tab's readyState is 'complete'.",
		`result = {"ok": wait_for_load(**a)}`, []param{opt("timeout", "number", 15.0)}},
	{"browser_wait_for_element", "Wait for an element matching `selector` to appear. Set `visible=True` to\nalso require it to be rendered.",
		`result = {"ok": wait_for_element(**a)}`, []param{req("selector", "string"), opt("timeout", "number", 10.0), opt("visible", "boolean", false)}},
	{"browser_js", "Evaluate a JavaScript expression in the current tab (or an iframe `target_id`).",
		`result = js(**a)`, []param{req("expression", "string"), null("target_id", "string")}},
	{"browser_cdp", "Call a raw Chrome DevTools Protocol method. `params` are passed as kwargs.",
		`result = cdp(a["method"], **(a.get("params") or {}))`, []param{req("method", "string"), null("params", "object")}},
	{"browser_upload_file", "Set files on a file input matched by `selector`. `path` is the local file.",
		`upload_file(**a)` + ok, []param{req("selector", "string"), req("path", "string")}},
	{"browser_http_get", "HTTP GET `url` (browser-less). Returns the response body. Optional\n`headers` dict for authentication or custom request headers.",
		`result = {"text": http_get(**a)}`, []param{req("url", "string"), opt("timeout", "number", 20.0), null("headers", "object")}},
	{"browser_start_recording", "Start recording actions to a local directory.",
		`result = {"recording_dir": start_recording(**a)}`, []param{null("name", "string"), null("title", "string")}},
	{"browser_stop_recording", "Stop the active recording and return its directory.",
		`result = {"recording_dir": stop_recording()}`, nil},
}

func (t tool) schema() map[string]any {
	props := map[string]any{}
	required := []string{}
	for _, p := range t.params {
		s := map[string]any{"type": p.typ}
		switch {
		case p.nullable:
			s = map[string]any{"anyOf": []any{map[string]any{"type": p.typ}, map[string]any{"type": "null"}}, "default": nil}
		case p.def != nil:
			s["default"] = p.def
		default:
			required = append(required, p.name)
		}
		props[p.name] = s
	}
	return map[string]any{"type": "object", "properties": props, "required": required}
}

// wrapper turns the body's `result` into the JSON text the Python server returned:
// NaN/Infinity become null, unserializable values their str().
const wrapper = `import json as _json, math as _math
a = _json.load(open(os.environ["BH_MCP_ARGS"], encoding="utf-8"))
def _norm(v):
    if isinstance(v, float) and (_math.isnan(v) or _math.isinf(v)): return None
    if isinstance(v, dict): return {k: _norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set, frozenset)): return [_norm(x) for x in v]
    return v
def _default(v):
    if isinstance(v, bytes): return v.decode("utf-8", errors="replace")
    if hasattr(v, "isoformat"): return v.isoformat()
    return str(v)
try:
%s
    _out = {"text": _json.dumps(_norm(result), ensure_ascii=False, allow_nan=False, default=_default)}
except Exception as _e:
    _out = {"error": str(_e)}
with open(os.environ["BH_MCP_RESULT"], "w", encoding="utf-8") as _f:
    _json.dump(_out, _f)
`

func indent(s string) string {
	return "    " + strings.ReplaceAll(s, "\n", "\n    ")
}

// ensureDaemon and runSnippet are seams for tests.
var (
	ensureDaemon = func() error { return admin.EnsureDaemon(-1, "", nil) }
	runSnippet   = runPython
)

func runPython(ctx context.Context, code string, args json.RawMessage) (string, error) {
	dir, err := os.MkdirTemp("", "bh-mcp-")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(dir)
	argsPath, resPath := dir+"/args.json", dir+"/result.json"
	if len(args) == 0 || string(args) == "null" {
		args = json.RawMessage("{}")
	}
	if err := os.WriteFile(argsPath, args, 0o600); err != nil {
		return "", err
	}
	py := os.Getenv("BH_PYTHON")
	if py == "" {
		py = "python3"
	}
	cmd := exec.CommandContext(ctx, py, "-m", "browser_harness.runner")
	cmd.Stdin = strings.NewReader(code)
	// Helper prints must never reach the JSON-RPC stream.
	cmd.Stdout, cmd.Stderr = os.Stderr, os.Stderr
	cmd.Env = append(os.Environ(), "BH_MCP_ARGS="+argsPath, "BH_MCP_RESULT="+resPath)
	runErr := cmd.Run()
	raw, err := os.ReadFile(resPath)
	if err != nil {
		if runErr != nil {
			return "", runErr
		}
		return "", err
	}
	var out struct {
		Text  *string `json:"text"`
		Error *string `json:"error"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return "", err
	}
	if out.Error != nil {
		return "", errors.New(*out.Error)
	}
	return *out.Text, nil
}

// callMu runs one tool at a time: they all drive the same tab.
var callMu sync.Mutex

func handler(t tool) mcp.ToolHandler {
	code := strings.Replace(wrapper, "%s", indent(t.body), 1)
	return func(ctx context.Context, r *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		callMu.Lock()
		defer callMu.Unlock()
		text, err := "", ensureDaemon()
		if err == nil {
			text, err = runSnippet(ctx, code, r.Params.Arguments)
		}
		if err != nil {
			return &mcp.CallToolResult{IsError: true, Content: []mcp.Content{&mcp.TextContent{Text: err.Error()}}}, nil
		}
		return &mcp.CallToolResult{Content: []mcp.Content{&mcp.TextContent{Text: text}}}, nil
	}
}

func newServer(version string) *mcp.Server {
	s := mcp.NewServer(&mcp.Implementation{Name: "browser-harness", Version: version}, nil)
	for _, t := range tools {
		s.AddTool(&mcp.Tool{Name: t.name, Description: t.doc, InputSchema: t.schema()}, handler(t))
	}
	return s
}

// Run serves MCP on stdin/stdout until the client disconnects.
func Run(version string) int {
	out := os.Stdout
	// Anything else that prints (daemon setup guidance) goes to stderr.
	os.Stdout = os.Stderr
	if err := newServer(version).Run(context.Background(), &mcp.IOTransport{Reader: os.Stdin, Writer: out}); err != nil {
		os.Stderr.WriteString("browser-harness-mcp: " + err.Error() + "\n")
		return 1
	}
	return 0
}
