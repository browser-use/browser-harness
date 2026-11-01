// Package jsrun is a prototype: agent snippets in JavaScript, run in-process by
// goja, with the helpers implemented in Go against the daemon. No Python.
package jsrun

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"image"
	"image/png"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/dop251/goja"
	"golang.org/x/image/draw"

	"github.com/browser-use/browser-harness/go/internal/admin"
	"github.com/browser-use/browser-harness/go/internal/ipc"
	"github.com/browser-use/browser-harness/go/internal/paths"
)

type runner struct {
	rt   *goja.Runtime
	name string
	out  io.Writer
}

// Run executes one JavaScript snippet; errors carry the JS stack.
func Run(code string, out io.Writer) error {
	if err := admin.EnsureDaemon(-1, "", nil); err != nil {
		return err
	}
	r := &runner{rt: goja.New(), name: admin.Name(), out: out}
	r.rt.SetFieldNameMapper(goja.TagFieldNameMapper("json", true))
	r.install()
	_, err := r.rt.RunScript("snippet.js", code)
	return err
}

// throw turns a Go error into a JS exception so snippets can try/catch it.
func (r *runner) throw(err error) { panic(r.rt.NewGoError(err)) }

func (r *runner) send(req map[string]any, timeout time.Duration) map[string]any {
	m, err := ipc.Call(r.name, timeout, req)
	if err != nil {
		r.throw(err)
	}
	if e, ok := m["error"]; ok {
		r.throw(fmt.Errorf("%v", e))
	}
	return m
}

func (r *runner) cdp(method string, params map[string]any, session any, timeout time.Duration) map[string]any {
	if params == nil {
		params = map[string]any{}
	}
	res, _ := r.send(map[string]any{"method": method, "params": params, "session_id": session}, timeout)["result"].(map[string]any)
	if res == nil {
		res = map[string]any{}
	}
	return res
}

// opts reads an optional trailing options object: f(a, b, {key: value}).
func opts(call goja.FunctionCall, i int) map[string]any {
	if v := call.Argument(i); !goja.IsUndefined(v) && !goja.IsNull(v) {
		if m, ok := v.Export().(map[string]any); ok {
			return m
		}
	}
	return map[string]any{}
}

func num(m map[string]any, k string, def float64) float64 {
	switch v := m[k].(type) {
	case int64:
		return float64(v)
	case float64:
		return v
	}
	return def
}

func (r *runner) evaluate(expr string, session any) any {
	res := r.cdp("Runtime.evaluate", map[string]any{"expression": expr, "returnByValue": true, "awaitPromise": true}, session, 5*time.Second)
	result, _ := res["result"].(map[string]any)
	if d, ok := res["exceptionDetails"].(map[string]any); ok || result["subtype"] == "error" {
		desc, _ := result["description"].(string)
		if desc == "" && d != nil {
			desc, _ = d["text"].(string)
		}
		r.throw(fmt.Errorf("JavaScript evaluation failed: %s", desc))
	}
	return result["value"]
}

func (r *runner) js(expr string, session any) (v any) {
	defer func() {
		if p := recover(); p != nil {
			if e, ok := p.(*goja.Object); ok && strings.Contains(e.String(), "Illegal return statement") {
				v = r.evaluate("(function(){"+expr+"})()", session)
				return
			}
			panic(p)
		}
	}()
	return r.evaluate(expr, session)
}

func (r *runner) currentTab() map[string]any {
	m := r.send(map[string]any{"meta": "current_tab"}, 5*time.Second)
	return map[string]any{"targetId": m["targetId"], "url": m["url"], "title": m["title"]}
}

func targetID(v goja.Value) string {
	if m, ok := v.Export().(map[string]any); ok {
		s, _ := m["targetId"].(string)
		return s
	}
	return v.String()
}

func (r *runner) switchTab(tid string) string {
	sid, _ := r.cdp("Target.attachToTarget", map[string]any{"targetId": tid, "flatten": true}, nil, 5*time.Second)["sessionId"].(string)
	r.send(map[string]any{"meta": "set_session", "session_id": sid, "target_id": tid}, 5*time.Second)
	return sid
}

var namedKeys = map[string]struct {
	vk         int
	code, text string
}{
	"Enter": {13, "Enter", "\r"}, "Tab": {9, "Tab", "\t"}, "Backspace": {8, "Backspace", ""},
	"Escape": {27, "Escape", ""}, "ArrowDown": {40, "ArrowDown", ""}, "ArrowUp": {38, "ArrowUp", ""},
}

func (r *runner) pressKey(key string, mods float64) {
	base := map[string]any{"key": key, "modifiers": mods}
	if k, ok := namedKeys[key]; ok {
		base["code"], base["windowsVirtualKeyCode"] = k.code, k.vk
		if k.text != "" {
			base["text"] = k.text
		}
	} else {
		base["text"] = key
	}
	down := map[string]any{"type": "keyDown"}
	for k, v := range base {
		down[k] = v
	}
	r.cdp("Input.dispatchKeyEvent", down, nil, 5*time.Second)
	up := map[string]any{"type": "keyUp", "key": key, "modifiers": mods}
	r.cdp("Input.dispatchKeyEvent", up, nil, 5*time.Second)
}

func (r *runner) screenshot(path string, o map[string]any) string {
	if path == "" {
		path = filepath.Join(paths.TmpDir(), "shot.png")
	}
	res := r.cdp("Page.captureScreenshot", map[string]any{"format": "png", "captureBeyondViewport": o["full"] == true}, nil, 60*time.Second)
	raw, err := base64.StdEncoding.DecodeString(fmt.Sprint(res["data"]))
	if err != nil {
		r.throw(err)
	}
	if maxDim := int(num(o, "max_dim", 0)); maxDim > 0 {
		img, err := png.Decode(bytes.NewReader(raw))
		if err != nil {
			r.throw(err)
		}
		if b := img.Bounds(); max(b.Dx(), b.Dy()) > maxDim {
			s := float64(maxDim) / float64(max(b.Dx(), b.Dy()))
			dst := image.NewRGBA(image.Rect(0, 0, int(float64(b.Dx())*s), int(float64(b.Dy())*s)))
			draw.CatmullRom.Scale(dst, dst.Bounds(), img, b, draw.Src, nil)
			var buf bytes.Buffer
			_ = png.Encode(&buf, dst)
			raw = buf.Bytes()
		}
	}
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		r.throw(err)
	}
	return path
}

func (r *runner) print(call goja.FunctionCall) goja.Value {
	parts := make([]string, len(call.Arguments))
	for i, a := range call.Arguments {
		if s, ok := a.Export().(string); ok {
			parts[i] = s
			continue
		}
		raw, err := json.Marshal(a.Export())
		if err != nil {
			parts[i] = a.String()
		} else {
			parts[i] = string(raw)
		}
	}
	fmt.Fprintln(r.out, strings.Join(parts, " "))
	return goja.Undefined()
}

func (r *runner) install() {
	rt := r.rt
	set := func(name string, f any) { _ = rt.Set(name, f) }
	set("print", r.print)
	console := rt.NewObject()
	_ = console.Set("log", r.print)
	set("console", console)

	set("cdp", func(method string, params map[string]any) map[string]any {
		return r.cdp(method, params, nil, 5*time.Second)
	})
	set("drain_events", func() any { return r.send(map[string]any{"meta": "drain_events"}, 5*time.Second)["events"] })
	set("js", func(call goja.FunctionCall) goja.Value {
		expr, o := call.Argument(0).String(), opts(call, 1)
		var sid any
		if tid, ok := o["target_id"].(string); ok {
			sid = r.cdp("Target.attachToTarget", map[string]any{"targetId": tid, "flatten": true}, nil, 5*time.Second)["sessionId"]
			defer r.cdp("Target.detachFromTarget", map[string]any{"sessionId": sid}, nil, 5*time.Second)
		}
		return rt.ToValue(r.js(expr, sid))
	})
	set("goto_url", func(url string) map[string]any {
		return r.cdp("Page.navigate", map[string]any{"url": url}, nil, 5*time.Second)
	})
	set("page_info", func() any {
		if d := r.send(map[string]any{"meta": "pending_dialog"}, 5*time.Second)["dialog"]; d != nil {
			return map[string]any{"dialog": d}
		}
		var info map[string]any
		s := r.js("JSON.stringify({url:location.href,title:document.title,w:innerWidth,h:innerHeight,sx:scrollX,sy:scrollY,pw:document.documentElement.scrollWidth,ph:document.documentElement.scrollHeight})", nil)
		_ = json.Unmarshal([]byte(fmt.Sprint(s)), &info)
		return info
	})
	set("click_at_xy", func(call goja.FunctionCall) goja.Value {
		x, y, o := call.Argument(0).ToFloat(), call.Argument(1).ToFloat(), opts(call, 2)
		button, _ := o["button"].(string)
		if button == "" {
			button = "left"
		}
		for _, t := range []string{"mousePressed", "mouseReleased"} {
			r.cdp("Input.dispatchMouseEvent", map[string]any{"type": t, "x": x, "y": y, "button": button, "clickCount": num(o, "clicks", 1)}, nil, 5*time.Second)
		}
		return goja.Undefined()
	})
	set("type_text", func(text string) { r.cdp("Input.insertText", map[string]any{"text": text}, nil, 5*time.Second) })
	set("press_key", func(key string, mods float64) { r.pressKey(key, mods) })
	set("fill_input", func(call goja.FunctionCall) goja.Value {
		sel, text, o := call.Argument(0).String(), call.Argument(1).String(), opts(call, 2)
		q, _ := json.Marshal(sel)
		if r.js("(()=>{const e=document.querySelector("+string(q)+");if(!e)return false;e.focus();return true})()", nil) != true {
			r.throw(fmt.Errorf("fill_input: element not found: %s", sel))
		}
		if o["clear_first"] != false {
			r.js("(()=>{const e=document.activeElement;if(e&&\"value\" in e)e.value=\"\"})()", nil)
		}
		for _, ch := range text {
			r.pressKey(string(ch), 0)
		}
		r.js("(()=>{const e=document.querySelector("+string(q)+");e.dispatchEvent(new Event(\"input\",{bubbles:true}));e.dispatchEvent(new Event(\"change\",{bubbles:true}))})()", nil)
		return goja.Undefined()
	})
	set("capture_screenshot", func(call goja.FunctionCall) goja.Value {
		path := ""
		if v := call.Argument(0); !goja.IsUndefined(v) && !goja.IsNull(v) {
			path = v.String()
		}
		return rt.ToValue(r.screenshot(path, opts(call, 1)))
	})
	set("list_tabs", func(call goja.FunctionCall) goja.Value {
		includeChrome := opts(call, 0)["include_chrome"] != false
		var out []any
		infos, _ := r.cdp("Target.getTargets", nil, nil, 5*time.Second)["targetInfos"].([]any)
		for _, i := range infos {
			t, _ := i.(map[string]any)
			url, _ := t["url"].(string)
			if t["type"] != "page" || (!includeChrome && (strings.HasPrefix(url, "chrome") || strings.HasPrefix(url, "about:") || strings.HasPrefix(url, "devtools:"))) {
				continue
			}
			out = append(out, map[string]any{"targetId": t["targetId"], "title": t["title"], "url": url})
		}
		return rt.ToValue(out)
	})
	set("current_tab", r.currentTab)
	set("switch_tab", func(t goja.Value) string { return r.switchTab(targetID(t)) })
	set("activate_tab", func(t goja.Value) string {
		tid := targetID(t)
		r.cdp("Target.activateTarget", map[string]any{"targetId": tid}, nil, 5*time.Second)
		return tid
	})
	set("new_tab", func(call goja.FunctionCall) goja.Value {
		url := "about:blank"
		if v := call.Argument(0); !goja.IsUndefined(v) {
			url = v.String()
		}
		tid, _ := r.cdp("Target.createTarget", map[string]any{"url": "about:blank", "background": true}, nil, 5*time.Second)["targetId"].(string)
		r.switchTab(tid)
		if url != "about:blank" {
			r.cdp("Page.navigate", map[string]any{"url": url}, nil, 5*time.Second)
		}
		return rt.ToValue(tid)
	})
	set("close_tab", func(call goja.FunctionCall) goja.Value {
		tid := ""
		if v := call.Argument(0); !goja.IsUndefined(v) && !goja.IsNull(v) {
			tid = targetID(v)
		} else {
			tid, _ = r.currentTab()["targetId"].(string)
		}
		r.cdp("Target.closeTarget", map[string]any{"targetId": tid}, nil, 5*time.Second)
		return goja.Undefined()
	})
	set("wait", func(seconds float64) { time.Sleep(time.Duration(seconds * float64(time.Second))) })
	set("wait_for_load", func(call goja.FunctionCall) goja.Value {
		timeout := 15.0
		if v := call.Argument(0); !goja.IsUndefined(v) {
			timeout = v.ToFloat()
		}
		deadline := time.Now().Add(time.Duration(timeout * float64(time.Second)))
		for time.Now().Before(deadline) {
			if r.js("document.readyState", nil) == "complete" {
				return rt.ToValue(true)
			}
			time.Sleep(300 * time.Millisecond)
		}
		return rt.ToValue(false)
	})
	set("write_file", func(path string, data string) {
		if err := os.WriteFile(path, []byte(data), 0o644); err != nil {
			r.throw(err)
		}
	})
	set("base64_decode", func(s string) string {
		raw, err := base64.StdEncoding.DecodeString(s)
		if err != nil {
			r.throw(errors.New("base64_decode: " + err.Error()))
		}
		return string(raw)
	})
}
