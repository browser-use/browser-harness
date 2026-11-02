// Package jsrun runs agent snippets: JavaScript executed in-process by goja,
// with the browser helpers as globals. Helpers are synchronous; there is no
// event loop, so snippets never need await.
package jsrun

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/dop251/goja"

	"github.com/browser-use/browser-harness/go/internal/admin"
	"github.com/browser-use/browser-harness/go/internal/helpers"
	"github.com/browser-use/browser-harness/go/internal/ipc"
	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/recorder"
)

const (
	maxSteps   = 500
	maxArgsLen = 300
)

// Trace is the per-helper record the CLI sends with telemetry.
type Trace struct {
	Steps     []any
	StepCount int
}

// Seams for tests that fake the daemon.
var (
	newHelpers     = helpers.New
	connectDefault = admin.ConnectDefault
)

type runner struct {
	rt        *goja.Runtime
	h         *helpers.H
	out       io.Writer
	trace     Trace
	lazy      bool                     // the default daemon starts on the first browser helper
	inBrowser bool                     // set while installBrowser binds the browser helpers
	ready     map[*helpers.H]bool      // helpers whose daemon and agent tab are set up
	tabs      map[[2]string]*helpers.H // (daemon, tab) -> pinned helpers
	daemons   map[string]*goja.Object  // on(name) results
}

func newRunner(out io.Writer) *runner {
	r := &runner{rt: goja.New(), h: newHelpers(ipc.Name()), out: out, tabs: map[[2]string]*helpers.H{}, daemons: map[string]*goja.Object{}, ready: map[*helpers.H]bool{}}
	r.rt.SetFieldNameMapper(goja.TagFieldNameMapper("json", true))
	r.install()
	return r
}

// Run executes a snippet, printing to out. Uncaught errors come back with the JS stack.
// The default daemon starts on the first browser helper, so cloud-only snippets need no local browser.
func Run(code string, out io.Writer) (Trace, error) {
	r := newRunner(out)
	r.lazy = true
	if err := r.loadAgentHelpers(); err != nil {
		return r.trace, err
	}
	_, err := r.rt.RunScript("snippet.js", code)
	return r.trace, cleanError(err)
}

// Eval runs code with globals set and returns its last expression as plain Go values.
func Eval(code string, globals map[string]any, out io.Writer) (any, error) {
	r := newRunner(out)
	for k, v := range globals {
		_ = r.rt.Set(k, v)
	}
	v, err := r.rt.RunScript("eval.js", code)
	if err != nil {
		return nil, cleanError(err)
	}
	return v.Export(), nil
}

func cleanError(err error) error {
	var ex *goja.Exception
	if errors.As(err, &ex) {
		return errors.New(strings.TrimSpace(ex.String()))
	}
	return err
}

// agent_helpers.js in the workspace may define extra globals for every snippet.
func (r *runner) loadAgentHelpers() error {
	p := filepath.Join(paths.WorkspaceDir(), "agent_helpers.js")
	src, err := os.ReadFile(p) //nolint:gosec // Load agent-authored helpers from the configured workspace.
	if err == nil {
		_, err = r.rt.RunScript(p, string(src))
		return cleanError(err)
	}
	return nil
}

// --- argument helpers: f(a, b, {option: value}) ---

type args struct {
	call goja.FunctionCall
	opts map[string]any
	pos  int        // arguments before the options object
	h    *helpers.H // the daemon and tab this call acts on
}

// parse treats a trailing plain object as options. A tab
// object (it has targetId or target_id) in a positional slot stays positional.
func parse(call goja.FunctionCall, positional int) args {
	n := len(call.Arguments)
	a := args{call: call, opts: map[string]any{}, pos: min(n, positional)}
	if n > 0 {
		if m, ok := call.Arguments[n-1].Export().(map[string]any); ok && (n > positional || m["targetId"] == nil && m["target_id"] == nil) {
			a.opts, a.pos = m, min(n-1, positional)
		}
	}
	return a
}

func (a args) has(i int) bool {
	v := a.call.Argument(i)
	return i < a.pos && !goja.IsUndefined(v) && !goja.IsNull(v)
}

// get is positional argument i, else option name, else nil.
func (a args) get(i int, name string) any {
	if a.has(i) {
		return a.call.Argument(i).Export()
	}
	return a.opts[name]
}

func (a args) str(i int, name, def string) string {
	switch v := a.get(i, name).(type) {
	case string:
		return v
	case map[string]any: // a tab object
		if id, ok := v["targetId"].(string); ok {
			return id
		}
		if id, ok := v["target_id"].(string); ok {
			return id
		}
	}
	return def
}

func (a args) num(i int, name string, def float64) float64 {
	switch v := a.get(i, name).(type) {
	case int64:
		return float64(v)
	case float64:
		return v
	}
	return def
}

func (a args) flag(i int, name string, def bool) bool {
	if v, ok := a.get(i, name).(bool); ok {
		return v
	}
	return def
}

func (a args) strs(i int, name string) []string {
	switch v := a.get(i, name).(type) {
	case string:
		return []string{v}
	case []any:
		out := make([]string, len(v))
		for j, s := range v {
			out[j] = fmt.Sprint(s)
		}
		return out
	}
	return nil
}

func (a args) strMap(i int, name string) map[string]string {
	m, _ := a.get(i, name).(map[string]any)
	if m == nil {
		return nil
	}
	out := map[string]string{}
	for k, v := range m {
		out[k] = fmt.Sprint(v)
	}
	return out
}

// --- binding, tracing and recording ---

func (r *runner) bind(name string, positional int, fn func(a args) (any, error)) {
	r.bindOn(r.rt.GlobalObject(), r.h, name, positional, fn)
}

// bindOn installs a helper on obj; a {tab: id} option runs it on that tab of base's daemon.
func (r *runner) bindOn(obj *goja.Object, base *helpers.H, name string, positional int, fn func(a args) (any, error)) {
	browser := r.inBrowser
	_ = obj.Set(name, func(call goja.FunctionCall) goja.Value {
		a := parse(call, positional)
		a.h = base
		var v any
		var err error
		start := time.Now()
		if browser {
			err = r.prepare(base)
		}
		if t, ok := a.opts["tab"]; ok && browser && err == nil {
			delete(a.opts, "tab")
			a.h, err = r.onTab(base, t)
		}
		// Checked whether or not a recording is running: one may start automatically.
		password := false
		if err == nil && browser && typing[name] {
			password = r.typingIntoPassword(a, name)
		}
		if err == nil {
			v, err = fn(a)
		}
		if err == nil && !password && name == "fill_input" {
			password = r.typingIntoPassword(a, name) // the field may only exist once fill_input waited for it
		}
		r.record(name, call, a, time.Since(start), err, password)
		if err != nil {
			panic(r.rt.NewGoError(err))
		}
		return r.rt.ToValue(v)
	})
}

// typing helpers can put secrets into a recording; focus is checked before they run,
// since a page may move focus away from a password field as it is typed into.
var typing = map[string]bool{"type_text": true, "press_key": true, "fill_input": true, "dispatch_key": true}

// prepare starts a lazily skipped default daemon and selects the agent's own tab, once per daemon.
func (r *runner) prepare(base *helpers.H) error {
	if r.ready[base] {
		return nil
	}
	r.ready[base] = true
	if base == r.h && r.lazy {
		r.lazy = false
		if err := connectDefault(); err != nil {
			return err
		}
	}
	return base.UseAgentTab(helpers.AgentID())
}

func (r *runner) typingIntoPassword(a args, name string) bool {
	// Follow focus into shadow roots: activeElement stops at the shadow host.
	expr := `(() => { let e = document.activeElement; while (e?.shadowRoot?.activeElement) e = e.shadowRoot.activeElement; return e?.type === "password"; })()`
	if name == "fill_input" || name == "dispatch_key" {
		b, _ := json.Marshal(a.str(0, "selector", "")) //nolint:errchkjson // Strings always encode to JSON.
		expr = `document.querySelector(` + string(b) + `)?.type === "password"`
	}
	v, err := a.h.JS(expr, "")
	return err == nil && v == true
}

func (r *runner) record(name string, call goja.FunctionCall, a args, d time.Duration, err error, password bool) {
	r.trace.StepCount++
	var raw []any
	for i := 0; i < len(call.Arguments) && i < a.pos; i++ {
		raw = append(raw, call.Arguments[i].Export())
	}
	if r.trace.StepCount <= maxSteps {
		b, marshalErr := json.Marshal(append(raw, a.opts))
		if marshalErr != nil {
			b = nil // Unencodable helper arguments leave an empty trace summary.
		}
		s := strings.TrimSuffix(strings.TrimPrefix(string(b), "["), "]")
		if len(s) > maxArgsLen {
			s = s[:maxArgsLen]
		}
		step := map[string]any{"helper": name, "args": s, "duration_seconds": float64(d.Milliseconds()) / 1000}
		if err != nil {
			step["error"] = cut(err.Error(), 300)
		}
		r.trace.Steps = append(r.trace.Steps, step)
	}
	if err == nil && recorder.Actions[name] {
		dur := float64(d.Milliseconds()) / 1000
		_, _ = a.h.Send(map[string]any{"meta": "record_observe", "call": recorder.Call{
			Helper: name, Args: raw, Kwargs: a.opts, Duration: &dur, Env: recorder.FromProcess(),
			Session: a.h.PinnedSession(), Password: password}}, 65*time.Second)
	}
}

func cut(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

func (r *runner) recordMeta(meta string, extra map[string]any) (map[string]any, error) {
	// Record the agent's own tab, not whichever tab the daemon has attached.
	if err := r.prepare(r.h); err != nil {
		return nil, err
	}
	req := map[string]any{"meta": meta, "call": recorder.Call{Env: recorder.FromProcess(), Session: r.h.PinnedSession()}}
	for k, v := range extra {
		req[k] = v
	}
	m, err := r.h.Send(req, 65*time.Second)
	if err == nil && m["error"] != nil {
		err = fmt.Errorf("%v", m["error"])
	}
	return m, err
}

func (r *runner) print(call goja.FunctionCall) goja.Value {
	parts := make([]string, len(call.Arguments))
	for i, a := range call.Arguments {
		if s, ok := a.Export().(string); ok {
			parts[i] = s
		} else if b, err := json.Marshal(a.Export()); err == nil && !goja.IsUndefined(a) {
			parts[i] = string(b)
		} else {
			parts[i] = a.String()
		}
	}
	_, _ = fmt.Fprintln(r.out, strings.Join(parts, " ")) // a closed stdout (e.g. | head) must not fail the snippet
	return goja.Undefined()
}

func none(err error) (any, error) { return nil, err }

func (r *runner) install() {
	h := r.h
	_ = r.rt.Set("print", r.print)
	_ = r.rt.Set("on", func(name string) *goja.Object {
		obj, err := r.on(name)
		if err != nil {
			panic(r.rt.NewGoError(err))
		}
		return obj
	})
	console := r.rt.NewObject()
	_ = console.Set("log", r.print)
	_ = console.Set("error", r.print)
	_ = r.rt.Set("console", console)

	r.installBrowser(r.rt.GlobalObject(), h)

	r.bind("http_get", 3, func(a args) (any, error) {
		return helpers.HTTPGet(a.str(0, "url", ""), a.strMap(1, "headers"), a.num(2, "timeout", 20))
	})

	// Recording (the daemon records; these only start, stop and locate it).
	r.bind("start_recording", 2, func(a args) (any, error) {
		m, err := r.recordMeta("record_start", map[string]any{"name": a.str(0, "name", ""), "title": a.str(1, "title", "")})
		if err != nil {
			return nil, err
		}
		_, _ = fmt.Fprintf(r.out, "recording to %v\n", m["dir"])
		return m["dir"], nil
	})
	r.bind("stop_recording", 0, func(a args) (any, error) {
		m, err := r.recordMeta("record_stop", nil)
		if err != nil || m["dir"] == nil {
			if err == nil {
				_, _ = fmt.Fprintln(r.out, "no active recording")
			}
			return nil, err
		}
		_, _ = fmt.Fprintf(r.out, "recording saved: %v (%v frames)\n", m["dir"], m["frames"])
		if f, _ := m["frames"].(float64); f == 0 {
			_, _ = fmt.Fprintf(r.out, "warning: no frames captured — see frame_error in %v\n", filepath.Join(fmt.Sprint(m["dir"]), "events.jsonl"))
		}
		return m["dir"], nil
	})
	r.bind("recording_dir", 0, func(a args) (any, error) {
		m, err := r.recordMeta("record_dir", nil)
		if err != nil {
			return nil, err
		}
		return m["dir"], nil
	})

	// Daemon and cloud browser management.
	r.bind("ensure_daemon", 3, func(a args) (any, error) {
		return none(admin.EnsureDaemon(a.num(0, "wait", -1), a.str(1, "name", ""), a.strMap(2, "env")))
	})
	r.bind("require_existing_daemon", 1, func(a args) (any, error) { return none(admin.RequireExistingDaemon(a.str(0, "name", ""))) })
	r.bind("daemon_alive", 1, func(a args) (any, error) { return admin.DaemonAlive(a.str(0, "name", "")), nil })
	r.bind("daemon_browser_ready", 1, func(a args) (any, error) { return admin.DaemonBrowserReady(a.str(0, "name", "")), nil })
	r.bind("browser_connections", 0, func(a args) (any, error) { return admin.BrowserConnections(), nil })
	r.bind("restart_daemon", 2, func(a args) (any, error) {
		return none(admin.RestartDaemon(a.str(0, "name", ""), a.flag(1, "require_clean", false)))
	})
	r.bind("start_remote_daemon", 2, func(a args) (any, error) {
		create := map[string]any{}
		for k, v := range a.opts {
			if k != "profileName" {
				create[k] = v
			}
		}
		return admin.StartRemoteDaemon(a.str(0, "name", "remote"), a.str(1, "profileName", ""), create)
	})
	r.bind("stop_remote_daemon", 1, func(a args) (any, error) { return none(admin.StopRemoteDaemon(a.str(0, "name", "remote"))) })
	r.bind("cleanup_cloud_browsers", 2, func(a args) (any, error) {
		return admin.CleanupCloudBrowsers(time.Duration(a.num(0, "older_than", 30)*float64(time.Minute)), a.flag(1, "dry_run", false))
	})
	r.bind("list_cloud_profiles", 0, func(a args) (any, error) { return admin.ListCloudProfiles() })
	r.bind("list_local_profiles", 0, func(a args) (any, error) { return admin.ListLocalProfiles() })
	r.bind("sync_local_profile", 5, func(a args) (any, error) {
		return admin.SyncLocalProfile(a.str(0, "profile_name", ""), a.str(1, "browser", ""), a.str(2, "cloud_profile_id", ""),
			a.strs(3, "include_domains"), a.strs(4, "exclude_domains"))
	})

	// Files: snippets have no fs module.
	r.bind("read_file", 1, func(a args) (any, error) {
		b, err := os.ReadFile(a.str(0, "path", ""))
		return string(b), err
	})
	r.bind("write_file", 2, func(a args) (any, error) {
		return none(os.WriteFile(a.str(0, "path", ""), []byte(a.str(1, "data", "")), 0o644))
	})
	_ = r.rt.Set("env", func(name string) any {
		if v, ok := os.LookupEnv(name); ok {
			return v
		}
		return nil
	})
}

// installBrowser binds the page, input, tab and wait helpers for one daemon onto obj.
func (r *runner) installBrowser(obj *goja.Object, base *helpers.H) {
	r.inBrowser = true
	defer func() { r.inBrowser = false }()
	// Page and CDP.
	r.bindOn(obj, base, "cdp", 1, func(a args) (any, error) {
		params := map[string]any{}
		for k, v := range a.opts {
			if k != "session_id" {
				params[k] = v
			}
		}
		s, _ := a.opts["session_id"].(string)
		return a.h.CDP(a.str(0, "method", ""), params, s)
	})
	r.bindOn(obj, base, "drain_events", 0, func(a args) (any, error) { return a.h.DrainEvents() })
	r.bindOn(obj, base, "js", 2, func(a args) (any, error) { return a.h.JS(a.str(0, "expression", ""), a.str(1, "target_id", "")) })
	r.bindOn(obj, base, "goto_url", 1, func(a args) (any, error) { return a.h.GotoURL(a.str(0, "url", "")) })
	r.bindOn(obj, base, "page_info", 0, func(a args) (any, error) { return a.h.PageInfo() })

	// Input.
	r.bindOn(obj, base, "click_at_xy", 4, func(a args) (any, error) {
		return none(a.h.ClickAtXY(a.num(0, "x", 0), a.num(1, "y", 0), a.str(2, "button", "left"), int(a.num(3, "clicks", 1))))
	})
	r.bindOn(obj, base, "type_text", 1, func(a args) (any, error) { return none(a.h.TypeText(a.str(0, "text", ""))) })
	r.bindOn(obj, base, "fill_input", 4, func(a args) (any, error) {
		return none(a.h.FillInput(a.str(0, "selector", ""), a.str(1, "text", ""), a.flag(2, "clear_first", true), a.num(3, "timeout", 0)))
	})
	r.bindOn(obj, base, "press_key", 2, func(a args) (any, error) {
		return none(a.h.PressKey(a.str(0, "key", ""), int(a.num(1, "modifiers", 0))))
	})
	r.bindOn(obj, base, "scroll", 4, func(a args) (any, error) {
		return none(a.h.Scroll(a.num(0, "x", 0), a.num(1, "y", 0), a.num(2, "dy", -300), a.num(3, "dx", 0)))
	})
	r.bindOn(obj, base, "dispatch_key", 3, func(a args) (any, error) {
		return none(a.h.DispatchKey(a.str(0, "selector", ""), a.str(1, "key", "Enter"), a.str(2, "event", "keypress")))
	})
	r.bindOn(obj, base, "upload_file", 2, func(a args) (any, error) { return none(a.h.UploadFile(a.str(0, "selector", ""), a.strs(1, "path"))) })
	r.bindOn(obj, base, "capture_screenshot", 3, func(a args) (any, error) {
		return a.h.CaptureScreenshot(a.str(0, "path", ""), a.flag(1, "full", false), int(a.num(2, "max_dim", 0)))
	})

	// Tabs.
	r.bindOn(obj, base, "list_tabs", 1, func(a args) (any, error) { return a.h.ListTabs(a.flag(0, "include_chrome", true)) })
	r.bindOn(obj, base, "current_tab", 0, func(a args) (any, error) { return a.h.CurrentTab() })
	r.bindOn(obj, base, "activate_tab", 1, func(a args) (any, error) { return a.h.ActivateTab(a.str(0, "target", "")) })
	r.bindOn(obj, base, "switch_tab", 2, func(a args) (any, error) { return a.h.SwitchTab(a.str(0, "target", ""), a.flag(1, "activate", false)) })
	r.bindOn(obj, base, "new_tab", 1, func(a args) (any, error) {
		id, err := a.h.NewTab(a.str(0, "url", "about:blank"))
		if name, _ := a.opts["name"].(string); err == nil && name != "" {
			err = a.h.NameTab(name, id)
		}
		return id, err
	})
	r.bindOn(obj, base, "name_tab", 1, func(a args) (any, error) { return none(a.h.NameTab(a.str(0, "name", ""), a.h.Target)) })
	r.bindOn(obj, base, "close_tab", 1, func(a args) (any, error) { return none(a.h.CloseTab(a.str(0, "target", ""))) })
	r.bindOn(obj, base, "ensure_real_tab", 0, func(a args) (any, error) { return a.h.EnsureRealTab() })
	r.bindOn(obj, base, "iframe_target", 1, func(a args) (any, error) {
		id, err := a.h.IframeTarget(a.str(0, "url_substr", ""))
		if id == "" {
			return nil, err
		}
		return id, err
	})

	// Waiting and HTTP.
	r.bindOn(obj, base, "wait", 1, func(a args) (any, error) { helpers.Wait(a.num(0, "seconds", 1)); return nil, nil })
	r.bindOn(obj, base, "wait_for_load", 1, func(a args) (any, error) { return a.h.WaitForLoad(a.num(0, "timeout", 15)) })
	r.bindOn(obj, base, "wait_for_element", 3, func(a args) (any, error) {
		return a.h.WaitForElement(a.str(0, "selector", ""), a.num(1, "timeout", 10), a.flag(2, "visible", false))
	})
	r.bindOn(obj, base, "wait_for_network_idle", 2, func(a args) (any, error) {
		return a.h.WaitForNetworkIdle(a.num(0, "timeout", 10), int(a.num(1, "idle_ms", 500)))
	})
}

func (r *runner) onTab(base *helpers.H, t any) (*helpers.H, error) {
	id, _ := t.(string)
	if m, ok := t.(map[string]any); ok {
		id, _ = m["targetId"].(string)
		if id == "" {
			id, _ = m["target_id"].(string)
		}
	}
	if id == "" {
		return nil, errors.New("tab: expected a target id or a tab object")
	}
	// Key by target id: a tab name may move to another tab during the snippet.
	id = base.Resolve(id)
	key := [2]string{base.Name, id}
	if h := r.tabs[key]; h != nil {
		return h, nil
	}
	h, err := base.OnTab(id)
	if err == nil {
		r.tabs[key] = h
	}
	return h, err
}

// on returns the browser helpers of another daemon, e.g. a cloud browser next to local Chrome.
func (r *runner) on(name string) (*goja.Object, error) {
	if err := ipc.Check(name); err != nil {
		return nil, err
	}
	if obj := r.daemons[name]; obj != nil {
		return obj, nil
	}
	if err := admin.Connect(name); err != nil {
		return nil, err
	}
	obj := r.rt.NewObject()
	r.installBrowser(obj, newHelpers(name))
	r.daemons[name] = obj
	return obj, nil
}
