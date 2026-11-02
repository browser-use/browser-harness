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

// newHelpers is a seam for tests.
var newHelpers = helpers.New

type runner struct {
	rt    *goja.Runtime
	h     *helpers.H
	out   io.Writer
	trace Trace
}

func newRunner(out io.Writer) *runner {
	r := &runner{rt: goja.New(), h: newHelpers(admin.Name()), out: out}
	r.rt.SetFieldNameMapper(goja.TagFieldNameMapper("json", true))
	r.install()
	return r
}

// Run executes a snippet, printing to out. Uncaught errors come back with the JS stack.
func Run(code string, out io.Writer) (Trace, error) {
	r := newRunner(out)
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
	src, err := os.ReadFile(p)
	if err != nil {
		return nil
	}
	_, err = r.rt.RunScript(p, string(src))
	return cleanError(err)
}

// --- argument helpers: f(a, b, {option: value}) ---

type args struct {
	call goja.FunctionCall
	opts map[string]any
	pos  int // arguments before the options object
}

// parse treats a trailing plain object as options, like Python keywords. A tab
// object (it has targetId) in a positional slot stays positional.
func parse(call goja.FunctionCall, positional int) args {
	n := len(call.Arguments)
	a := args{call: call, opts: map[string]any{}, pos: min(n, positional)}
	if n > 0 {
		if m, ok := call.Arguments[n-1].Export().(map[string]any); ok && (n > positional || m["targetId"] == nil) {
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
	_ = r.rt.Set(name, func(call goja.FunctionCall) goja.Value {
		a := parse(call, positional)
		start := time.Now()
		v, err := fn(a)
		r.record(name, call, a, time.Since(start), err)
		if err != nil {
			panic(r.rt.NewGoError(err))
		}
		return r.rt.ToValue(v)
	})
}

func (r *runner) record(name string, call goja.FunctionCall, a args, d time.Duration, err error) {
	r.trace.StepCount++
	var raw []any
	for i := 0; i < len(call.Arguments) && i < a.pos; i++ {
		raw = append(raw, call.Arguments[i].Export())
	}
	if r.trace.StepCount <= maxSteps {
		b, _ := json.Marshal(append(raw, a.opts))
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
		_, _ = r.h.Send(map[string]any{"meta": "record_observe", "call": recorder.Call{
			Helper: name, Args: raw, Kwargs: a.opts, Duration: &dur, Env: recorder.FromProcess()}}, 65*time.Second)
	}
}

func cut(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

func (r *runner) recordMeta(meta string, extra map[string]any) (map[string]any, error) {
	req := map[string]any{"meta": meta, "call": recorder.Call{Env: recorder.FromProcess()}}
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
	fmt.Fprintln(r.out, strings.Join(parts, " "))
	return goja.Undefined()
}

func none(err error) (any, error) { return nil, err }

func (r *runner) install() {
	h := r.h
	_ = r.rt.Set("print", r.print)
	console := r.rt.NewObject()
	_ = console.Set("log", r.print)
	_ = console.Set("error", r.print)
	_ = r.rt.Set("console", console)

	// Page and CDP.
	r.bind("cdp", 1, func(a args) (any, error) {
		params := map[string]any{}
		for k, v := range a.opts {
			if k != "session_id" {
				params[k] = v
			}
		}
		s, _ := a.opts["session_id"].(string)
		return h.CDP(a.str(0, "method", ""), params, s)
	})
	r.bind("drain_events", 0, func(a args) (any, error) { return h.DrainEvents() })
	r.bind("js", 2, func(a args) (any, error) { return h.JS(a.str(0, "expression", ""), a.str(1, "target_id", "")) })
	r.bind("goto_url", 1, func(a args) (any, error) { return h.GotoURL(a.str(0, "url", "")) })
	r.bind("page_info", 0, func(a args) (any, error) { return h.PageInfo() })

	// Input.
	r.bind("click_at_xy", 4, func(a args) (any, error) {
		return none(h.ClickAtXY(a.num(0, "x", 0), a.num(1, "y", 0), a.str(2, "button", "left"), int(a.num(3, "clicks", 1))))
	})
	r.bind("type_text", 1, func(a args) (any, error) { return none(h.TypeText(a.str(0, "text", ""))) })
	r.bind("fill_input", 4, func(a args) (any, error) {
		return none(h.FillInput(a.str(0, "selector", ""), a.str(1, "text", ""), a.flag(2, "clear_first", true), a.num(3, "timeout", 0)))
	})
	r.bind("press_key", 2, func(a args) (any, error) { return none(h.PressKey(a.str(0, "key", ""), int(a.num(1, "modifiers", 0)))) })
	r.bind("scroll", 4, func(a args) (any, error) {
		return none(h.Scroll(a.num(0, "x", 0), a.num(1, "y", 0), a.num(2, "dy", -300), a.num(3, "dx", 0)))
	})
	r.bind("dispatch_key", 3, func(a args) (any, error) {
		return none(h.DispatchKey(a.str(0, "selector", ""), a.str(1, "key", "Enter"), a.str(2, "event", "keypress")))
	})
	r.bind("upload_file", 2, func(a args) (any, error) { return none(h.UploadFile(a.str(0, "selector", ""), a.strs(1, "path"))) })
	r.bind("capture_screenshot", 3, func(a args) (any, error) {
		return h.CaptureScreenshot(a.str(0, "path", ""), a.flag(1, "full", false), int(a.num(2, "max_dim", 0)))
	})

	// Tabs.
	r.bind("list_tabs", 1, func(a args) (any, error) { return h.ListTabs(a.flag(0, "include_chrome", true)) })
	r.bind("current_tab", 0, func(a args) (any, error) { return h.CurrentTab() })
	r.bind("activate_tab", 1, func(a args) (any, error) { return h.ActivateTab(a.str(0, "target", "")) })
	r.bind("switch_tab", 2, func(a args) (any, error) { return h.SwitchTab(a.str(0, "target", ""), a.flag(1, "activate", false)) })
	r.bind("new_tab", 1, func(a args) (any, error) { return h.NewTab(a.str(0, "url", "about:blank")) })
	r.bind("close_tab", 1, func(a args) (any, error) { return none(h.CloseTab(a.str(0, "target", ""))) })
	r.bind("ensure_real_tab", 0, func(a args) (any, error) { return h.EnsureRealTab() })
	r.bind("iframe_target", 1, func(a args) (any, error) {
		id, err := h.IframeTarget(a.str(0, "url_substr", ""))
		if id == "" {
			return nil, err
		}
		return id, err
	})

	// Waiting and HTTP.
	r.bind("wait", 1, func(a args) (any, error) { helpers.Wait(a.num(0, "seconds", 1)); return nil, nil })
	r.bind("wait_for_load", 1, func(a args) (any, error) { return h.WaitForLoad(a.num(0, "timeout", 15)) })
	r.bind("wait_for_element", 3, func(a args) (any, error) {
		return h.WaitForElement(a.str(0, "selector", ""), a.num(1, "timeout", 10), a.flag(2, "visible", false))
	})
	r.bind("wait_for_network_idle", 2, func(a args) (any, error) {
		return h.WaitForNetworkIdle(a.num(0, "timeout", 10), int(a.num(1, "idle_ms", 500)))
	})
	r.bind("http_get", 3, func(a args) (any, error) {
		return helpers.HTTPGet(a.str(0, "url", ""), a.strMap(1, "headers"), a.num(2, "timeout", 20))
	})

	// Recording (the daemon records; these only start, stop and locate it).
	r.bind("start_recording", 2, func(a args) (any, error) {
		m, err := r.recordMeta("record_start", map[string]any{"name": a.str(0, "name", ""), "title": a.str(1, "title", "")})
		if err != nil {
			return nil, err
		}
		fmt.Fprintf(r.out, "recording to %v\n", m["dir"])
		return m["dir"], nil
	})
	r.bind("stop_recording", 0, func(a args) (any, error) {
		m, err := r.recordMeta("record_stop", nil)
		if err != nil || m["dir"] == nil {
			if err == nil {
				fmt.Fprintln(r.out, "no active recording")
			}
			return nil, err
		}
		fmt.Fprintf(r.out, "recording saved: %v (%v frames)\n", m["dir"], m["frames"])
		if f, _ := m["frames"].(float64); f == 0 {
			fmt.Fprintf(r.out, "warning: no frames captured — see frame_error in %v\n", filepath.Join(fmt.Sprint(m["dir"]), "events.jsonl"))
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
