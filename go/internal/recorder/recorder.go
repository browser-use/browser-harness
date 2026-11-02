// Package recorder records one screenshot plus one trace line per
// action, stored as <workspace>/recordings/<name>/{meta.json,events.jsonl,NNNN.jpg}.
// Recording failures are swallowed; they must never break a run.
package recorder

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/paths"
)

// Actions are helpers that change what is on screen; read-only helpers get no frame.
var Actions = map[string]bool{
	"goto_url": true, "click_at_xy": true, "type_text": true, "fill_input": true, "press_key": true,
	"scroll": true, "dispatch_key": true, "upload_file": true, "new_tab": true, "switch_tab": true,
	"close_tab": true, "ensure_real_tab": true,
	"wait": true, "wait_for_load": true, "wait_for_element": true, "wait_for_network_idle": true,
}

const (
	textLimit = 500
	settle    = 150 * time.Millisecond
	// CtxJS captures page context; the focused-element box lets a video zoom on
	// the input being typed into, and `input` flags password fields for masking.
	CtxJS = "(()=>{const o={url:location.href,title:document.title," +
		"w:innerWidth,h:innerHeight,sx:scrollX,sy:scrollY,dpr:devicePixelRatio};" +
		"const e=document.activeElement;" +
		"if(e&&e!==document.body&&e!==document.documentElement){" +
		"const r=e.getBoundingClientRect();" +
		"if(r.width||r.height)o.box={x:r.x,y:r.y,w:r.width,h:r.height};" +
		"o.input=String(e.type||e.tagName||'').toLowerCase();}" +
		"return o})()"
)

// Credential-bearing query/fragment params are scrubbed from every stored URL.
var urlSecrets = regexp.MustCompile(`(?i)([?&#](?:code|access_token|id_token|refresh_token|token|assertion` +
	`|client_secret|client_info|session_state|api_?key|sig|signature|auth|authorization|password|secret)=)[^&#]+`)

func scrubURL(u string) string { return urlSecrets.ReplaceAllString(u, "${1}REDACTED") }

func Root() string { return filepath.Join(paths.WorkspaceDir(), "recordings") }

func configPath() string { return filepath.Join(paths.ConfigDir(), "recording.json") }

// Env is the caller's per-process overrides; the daemon may run with a different env.
type Env struct {
	Record *string `json:"BH_RECORD"`
	Idle   *string `json:"BH_RECORD_IDLE"`
	Name   string  `json:"BU_NAME"`
}

func FromProcess() Env {
	e := Env{Name: os.Getenv("BU_NAME")}
	if v, ok := os.LookupEnv("BH_RECORD"); ok {
		e.Record = &v
	}
	if v, ok := os.LookupEnv("BH_RECORD_IDLE"); ok {
		e.Idle = &v
	}
	return e
}

func (e Env) override() *bool {
	if e.Record == nil {
		return nil
	}
	switch strings.ToLower(strings.TrimSpace(*e.Record)) {
	case "0", "false", "no", "off":
		f := false
		return &f
	}
	t := true
	return &t
}

func (e Env) name() string {
	if e.Name == "" {
		return "default"
	}
	return e.Name
}

func (e Env) marker() string { return filepath.Join(Root(), ".active-"+e.name()) }

func (e Env) idleGap() time.Duration {
	if e.Idle != nil {
		if f, err := strconv.ParseFloat(*e.Idle, 64); err == nil {
			return time.Duration(f * float64(time.Second))
		}
	}
	return 180 * time.Second
}

// AutoSetting returns (enabled, source) for the automatic-recording preference.
func AutoSetting(e Env) (bool, string) {
	if o := e.override(); o != nil {
		return *o, "BH_RECORD"
	}
	raw, err := os.ReadFile(configPath())
	if err == nil {
		var m map[string]any
		if json.Unmarshal(raw, &m) == nil {
			if b, ok := m["enabled"].(bool); ok {
				return b, "config"
			}
		}
	}
	return false, "default"
}

func SetAuto(e Env, enabled bool) error {
	p := configPath()
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, jsonLine(map[string]bool{"enabled": enabled}), 0o600); err != nil {
		return err
	}
	if err := os.Rename(tmp, p); err != nil {
		return err
	}
	if !enabled {
		if d := Dir(e); d != "" && isAuto(d) {
			_ = os.Remove(e.marker())
		}
	}
	return nil
}

// Dir is the active recording directory, or "".
func Dir(e Env) string {
	raw, err := os.ReadFile(e.marker())
	if err != nil {
		return ""
	}
	d := strings.TrimSpace(string(raw))
	if fi, err := os.Stat(d); err == nil && fi.IsDir() {
		return d
	}
	return ""
}

// All lists recording directories, newest first.
func All() []string {
	entries, err := os.ReadDir(Root())
	if err != nil {
		return []string{}
	}
	type rec struct {
		path string
		mod  time.Time
	}
	var found []rec
	for _, en := range entries {
		if !en.IsDir() {
			continue
		}
		p := filepath.Join(Root(), en.Name())
		ev, evErr := os.Stat(filepath.Join(p, "events.jsonl"))
		_, metaErr := os.Stat(filepath.Join(p, "meta.json"))
		if evErr != nil && metaErr != nil {
			continue
		}
		mod := time.Time{}
		if evErr == nil {
			mod = ev.ModTime()
		} else if fi, err := os.Stat(p); err == nil {
			mod = fi.ModTime()
		}
		found = append(found, rec{p, mod})
	}
	sort.SliceStable(found, func(i, j int) bool { return found[i].mod.After(found[j].mod) })
	out := make([]string, len(found))
	for i, r := range found {
		out[i] = r.path
	}
	return out
}

func Latest() string {
	if all := All(); len(all) > 0 {
		return all[0]
	}
	return ""
}

func isAuto(d string) bool {
	raw, err := os.ReadFile(filepath.Join(d, "meta.json"))
	if err != nil {
		return false
	}
	var m map[string]any
	return json.Unmarshal(raw, &m) == nil && m["auto"] == true
}

func nowSec() float64 { return float64(time.Now().UnixMilli()) / 1000 }

func writeMeta(d, name string, title any, auto bool) error {
	meta := map[string]any{"name": name, "title": title, "started": nowSec()}
	if auto {
		meta["auto"] = true
	}
	return os.WriteFile(filepath.Join(d, "meta.json"), jsonLine(meta), 0o644)
}

func autoStart(e Env) (string, error) {
	stamp := time.Now().Format("session-20060102-150405")
	name := stamp
	for n := 2; ; n++ {
		if _, err := os.Stat(filepath.Join(Root(), name)); errors.Is(err, os.ErrNotExist) {
			break
		}
		name = fmt.Sprintf("%s-%d", stamp, n)
	}
	d := filepath.Join(Root(), name)
	if err := os.MkdirAll(d, 0o755); err != nil {
		return "", err
	}
	if err := writeMeta(d, name, nil, true); err != nil {
		return "", err
	}
	return d, os.WriteFile(e.marker(), []byte(d), 0o644)
}

func frames(d string) []string {
	m, _ := filepath.Glob(filepath.Join(d, "*.jpg"))
	return m
}

func autoStale(e Env, d string) bool {
	if !isAuto(d) {
		return false // explicit recordings never auto-roll
	}
	var newest time.Time
	for _, f := range frames(d) {
		if fi, err := os.Stat(f); err == nil && fi.ModTime().After(newest) {
			newest = fi.ModTime()
		}
	}
	return !newest.IsZero() && time.Since(newest) > e.idleGap()
}

// Page is what capture needs from the browser.
type Page interface {
	JS(expression string) (map[string]any, error)
	Screenshot() (string, error) // base64 JPEG
}

// Call describes one helper invocation from the snippet runner.
type Call struct {
	Helper   string         `json:"helper"`
	Args     []any          `json:"args"`
	Kwargs   map[string]any `json:"kwargs"`
	Duration *float64       `json:"duration"`
	Env      Env            `json:"env"`
}

// Observe runs after each traced helper succeeds. It never fails.
func Observe(c Call, p Page) {
	if !Actions[c.Helper] {
		return
	}
	defer func() { _ = recover() }()
	e := c.Env
	if o := e.override(); o != nil && !*o {
		return
	}
	enabled, _ := AutoSetting(e)
	d := Dir(e)
	if d != "" && isAuto(d) && !enabled {
		_ = os.Remove(e.marker())
		d = ""
	}
	if d != "" && autoStale(e, d) {
		_ = os.Remove(e.marker())
		d = ""
	}
	if d == "" {
		if !enabled {
			return
		}
		var err error
		if d, err = autoStart(e); err != nil {
			return
		}
	}
	time.Sleep(settle)
	capture(d, c, p)
}

// Start begins an explicit recording and returns its directory.
func Start(e Env, name, title string, p Page) (string, error) {
	if o := e.override(); o != nil && !*o {
		return "", errors.New("recording disabled by BH_RECORD=0")
	}
	if name == "" {
		name = time.Now().Format("rec-20060102-150405")
	}
	d := filepath.Join(Root(), name)
	if err := os.MkdirAll(d, 0o755); err != nil {
		return "", err
	}
	var t any
	if title != "" {
		t = title
	}
	if err := writeMeta(d, name, t, false); err != nil {
		return "", err
	}
	if err := os.WriteFile(e.marker(), []byte(d), 0o644); err != nil {
		return "", err
	}
	capture(d, Call{Helper: "start_recording", Env: e}, p)
	return d, nil
}

// Stop ends the active recording; it returns the directory ("" when idle) and the frame count.
func Stop(e Env, p Page) (string, int) {
	d := Dir(e)
	if d == "" {
		return "", 0
	}
	capture(d, Call{Helper: "stop_recording", Env: e}, p)
	_ = os.Remove(e.marker())
	return d, len(frames(d))
}

func capture(d string, c Call, p Page) {
	ev := map[string]any{"ts": nowSec(), "helper": c.Helper}
	if c.Duration != nil {
		ev["duration"] = *c.Duration
	}
	ctx := map[string]any{}
	if m, err := p.JS(CtxJS); err == nil && m != nil {
		ctx = m
		for _, k := range []string{"url", "title", "w", "h", "sx", "sy", "dpr", "box", "input"} {
			if v, ok := m[k]; ok {
				ev[k] = v
			}
		}
	}
	for k, v := range details(c, ctx) {
		ev[k] = v
	}
	for _, k := range []string{"url", "to"} {
		if v, ok := ev[k]; ok && v != nil {
			ev[k] = scrubURL(fmt.Sprint(v))
		}
	}
	if data, err := p.Screenshot(); err != nil {
		msg := err.Error()
		if msg == "" {
			msg = "no detail"
		}
		ev["frame_error"] = truncate(msg, 200)
	} else if raw, derr := base64.StdEncoding.DecodeString(data); derr != nil {
		ev["frame_error"] = truncate(derr.Error(), 200)
	} else {
		n := len(frames(d)) + 1
		for {
			frame := fmt.Sprintf("%04d.jpg", n)
			f, err := os.OpenFile(filepath.Join(d, frame), os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o644)
			if errors.Is(err, os.ErrExist) {
				n++
				continue
			}
			if err == nil {
				_, _ = f.Write(raw)
				f.Close()
				ev["frame"] = frame
			} else {
				ev["frame_error"] = truncate(err.Error(), 200)
			}
			break
		}
	}
	f, err := os.OpenFile(filepath.Join(d, "events.jsonl"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	defer f.Close()
	_, _ = f.Write(jsonLine(ev))
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		return string(r[:n])
	}
	return s
}

func details(c Call, ctx map[string]any) map[string]any {
	arg := func(i int, name string, def any) any {
		if len(c.Args) > i {
			return c.Args[i]
		}
		if v, ok := c.Kwargs[name]; ok {
			return v
		}
		return def
	}
	d := map[string]any{}
	add := func(k string, v any) {
		if v != nil {
			d[k] = v
		}
	}
	switch c.Helper {
	case "click_at_xy":
		add("x", arg(0, "x", nil))
		add("y", arg(1, "y", nil))
	case "scroll":
		add("x", arg(0, "x", nil))
		add("y", arg(1, "y", nil))
		add("dy", arg(2, "dy", -300))
		add("dx", arg(3, "dx", 0))
	case "goto_url", "new_tab":
		add("to", arg(0, "url", nil))
	case "type_text":
		add("text", mask(arg(0, "text", ""), ctx))
	case "fill_input":
		add("selector", arg(0, "selector", nil))
		add("text", mask(arg(1, "text", ""), ctx))
	case "press_key":
		add("key", arg(0, "key", nil))
	case "dispatch_key":
		add("selector", arg(0, "selector", nil))
		add("key", arg(1, "key", "Enter"))
	case "wait_for_element":
		add("selector", arg(0, "selector", nil))
	}
	return d
}

func mask(v any, ctx map[string]any) string {
	s := fmt.Sprint(v)
	if ctx["input"] == "password" {
		return strings.Repeat("•", len([]rune(s)))
	}
	return truncate(s, textLimit)
}

// jsonLine is one JSON value plus a newline, with page text left unescaped.
func jsonLine(v any) []byte {
	var b bytes.Buffer
	e := json.NewEncoder(&b)
	e.SetEscapeHTML(false)
	_ = e.Encode(v)
	return b.Bytes()
}
