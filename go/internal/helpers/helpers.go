// Package helpers is the browser API agents call from snippets and MCP tools.
// Each helper talks to the daemon over IPC; none of them hold browser state.
package helpers

import (
	"bytes"
	"compress/gzip"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"image"
	"image/png"
	"io"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
	"unicode"

	"golang.org/x/image/draw"

	"github.com/browser-use/browser-harness/go/internal/ipc"
	"github.com/browser-use/browser-harness/go/internal/paths"
)

const (
	callTimeout       = 5 * time.Second
	screenshotTimeout = 60 * time.Second
)

var internalPrefixes = []string{"chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:"}

// M is a JSON object.
type M = map[string]any

// H drives one named daemon.
type H struct {
	Name      string
	selectAll float64 // cached select-all modifier: 4 on macOS browsers, else 2
	// Send is the IPC round trip; tests replace it.
	Send func(req M, timeout time.Duration) (M, error)
}

func New(name string) *H {
	h := &H{Name: name}
	h.Send = func(req M, timeout time.Duration) (M, error) {
		m, err := ipc.Call(name, timeout, req)
		if errors.Is(err, os.ErrDeadlineExceeded) {
			label := req["method"]
			if label == nil {
				label = req["meta"]
			}
			return nil, fmt.Errorf("%v timed out after %gs waiting for the daemon", label, timeout.Seconds())
		}
		return m, err
	}
	return h
}

func (h *H) send(req M, timeout time.Duration) (M, error) {
	m, err := h.Send(req, timeout)
	if err != nil {
		return nil, err
	}
	if e, ok := m["error"]; ok {
		return nil, fmt.Errorf("%v", e)
	}
	return m, nil
}

// CDP sends a raw CDP command on the attached session (or session, when given).
func (h *H) CDP(method string, params M, session string) (M, error) {
	return h.cdpTimeout(method, params, session, callTimeout)
}

func (h *H) cdpTimeout(method string, params M, session string, timeout time.Duration) (M, error) {
	if params == nil {
		params = M{}
	}
	req := M{"method": method, "params": params, "session_id": nil}
	if session != "" {
		req["session_id"] = session
	}
	m, err := h.send(req, timeout)
	if err != nil {
		return nil, err
	}
	res, _ := m["result"].(M)
	if res == nil {
		res = M{}
	}
	return res, nil
}

func (h *H) DrainEvents() ([]any, error) {
	m, err := h.send(M{"meta": "drain_events"}, callTimeout)
	if err != nil {
		return nil, err
	}
	ev, _ := m["events"].([]any)
	return ev, nil
}

// --- JavaScript in the page ---

func snippet(expr string) string {
	s := strings.ReplaceAll(strings.TrimSpace(expr), "\n", `\n`)
	if len(s) > 160 {
		s = s[:157] + "..."
	}
	return s
}

func (h *H) evaluate(expr, session string) (any, error) {
	r, err := h.CDP("Runtime.evaluate", M{"expression": expr, "returnByValue": true, "awaitPromise": true}, session)
	if err != nil {
		return nil, fmt.Errorf("%v; expression: %s", err, snippet(expr))
	}
	result, _ := r["result"].(M)
	details, _ := r["exceptionDetails"].(M)
	if details != nil || result["subtype"] == "error" {
		desc, _ := result["description"].(string)
		if exc, ok := details["exception"].(M); desc == "" && ok {
			desc, _ = exc["description"].(string)
			if v, ok := exc["value"]; desc == "" && ok {
				desc = fmt.Sprint(v)
			}
		}
		if desc == "" && details != nil {
			desc, _ = details["text"].(string)
		}
		if desc == "" {
			desc = "JavaScript evaluation failed"
		}
		loc := ""
		if l, ok := details["lineNumber"]; ok {
			loc = fmt.Sprintf(" at line %v, column %v", l, details["columnNumber"])
		}
		return nil, fmt.Errorf("JavaScript evaluation failed%s: %s; expression: %s", loc, desc, snippet(expr))
	}
	if v, ok := result["value"]; ok {
		return v, nil
	}
	if u, ok := result["unserializableValue"].(string); ok {
		switch u {
		case "NaN":
			return math.NaN(), nil
		case "Infinity":
			return math.Inf(1), nil
		case "-Infinity":
			return math.Inf(-1), nil
		case "-0":
			return math.Copysign(0, -1), nil
		}
		return strings.TrimSuffix(u, "n"), nil
	}
	return nil, nil
}

// JS evaluates expr in the attached tab, or in an iframe target. A top-level
// `return` is retried inside a function wrapper.
func (h *H) JS(expr, targetID string) (any, error) {
	session := ""
	if targetID != "" {
		r, err := h.CDP("Target.attachToTarget", M{"targetId": targetID, "flatten": true}, "")
		if err != nil {
			return nil, err
		}
		session, _ = r["sessionId"].(string)
		defer h.detach(session)
	}
	v, err := h.evaluate(expr, session)
	if err != nil && strings.Contains(err.Error(), "Illegal return statement") {
		return h.evaluate("(function(){"+expr+"})()", session)
	}
	return v, err
}

// detach releases an iframe session so polling loops don't pile up sessions.
func (h *H) detach(session string) {
	_, _ = h.CDP("Target.detachFromTarget", M{"sessionId": session}, "")
}

func quote(s string) string {
	b, _ := json.Marshal(s)
	return string(b)
}

// --- navigation ---

func (h *H) GotoURL(url string) (M, error) {
	r, err := h.CDP("Page.navigate", M{"url": url}, "")
	if err != nil || os.Getenv("BH_DOMAIN_SKILLS") != "1" {
		return r, err
	}
	host := url
	if i := strings.Index(host, "://"); i >= 0 {
		host = host[i+3:]
	}
	host = strings.TrimPrefix(strings.SplitN(strings.SplitN(host, "/", 2)[0], ":", 2)[0], "www.")
	dir := filepath.Join(paths.WorkspaceDir(), "domain-skills", strings.Split(host, ".")[0])
	var skills []string
	_ = filepath.WalkDir(dir, func(p string, d os.DirEntry, err error) error {
		if err == nil && !d.IsDir() && strings.HasSuffix(p, ".md") {
			skills = append(skills, filepath.Base(p))
		}
		return nil
	})
	if len(skills) > 0 {
		sort.Strings(skills)
		r["domain_skills"] = skills[:min(10, len(skills))]
	}
	return r, nil
}

// PageInfo is viewport, scroll and page size; or the open native dialog, which freezes the page.
func (h *H) PageInfo() (M, error) {
	m, err := h.send(M{"meta": "pending_dialog"}, callTimeout)
	if err != nil {
		return nil, err
	}
	if d := m["dialog"]; d != nil {
		return M{"dialog": d}, nil
	}
	v, err := h.evaluate("JSON.stringify({url:location.href,title:document.title,w:innerWidth,h:innerHeight,sx:scrollX,sy:scrollY,pw:document.documentElement.scrollWidth,ph:document.documentElement.scrollHeight})", "")
	if err != nil {
		return nil, err
	}
	var info M
	err = json.Unmarshal([]byte(fmt.Sprint(v)), &info)
	return info, err
}

// --- input ---

func (h *H) ClickAtXY(x, y float64, button string, clicks int) error {
	for _, t := range []string{"mousePressed", "mouseReleased"} {
		if _, err := h.CDP("Input.dispatchMouseEvent", M{"type": t, "x": x, "y": y, "button": button, "clickCount": clicks}, ""); err != nil {
			return err
		}
	}
	return nil
}

func (h *H) TypeText(text string) error {
	_, err := h.CDP("Input.insertText", M{"text": text}, "")
	return err
}

func (h *H) selectAllModifier() float64 {
	if h.selectAll == 0 {
		h.selectAll = 2
		if r, err := h.CDP("Browser.getVersion", nil, ""); err == nil {
			if ua, _ := r["userAgent"].(string); strings.Contains(ua, "Mac OS X") || strings.Contains(ua, "Macintosh") {
				h.selectAll = 4
			}
		}
	}
	return h.selectAll
}

// FillInput types into framework-managed inputs (React, Vue) with real key
// events, then fires input and change so the framework sees the value.
func (h *H) FillInput(selector, text string, clearFirst bool, timeout float64) error {
	if timeout > 0 {
		if ok, err := h.WaitForElement(selector, timeout, false); err != nil || !ok {
			return fmt.Errorf("fill_input: element not found: %s", selector)
		}
	}
	q := quote(selector)
	focused, err := h.JS("(()=>{const e=document.querySelector("+q+");if(!e)return false;e.focus();return true;})()", "")
	if err != nil {
		return err
	}
	if focused != true {
		return fmt.Errorf("fill_input: element not found: %s", selector)
	}
	if clearFirst {
		// Raw select-all with the editing command; press_key would also emit a char event.
		sel := M{"key": "a", "code": "KeyA", "modifiers": h.selectAllModifier(), "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65}
		down := M{"type": "rawKeyDown", "commands": []string{"SelectAll"}}
		up := M{"type": "keyUp"}
		for k, v := range sel {
			down[k], up[k] = v, v
		}
		for _, ev := range []M{down, up} {
			if _, err := h.CDP("Input.dispatchKeyEvent", ev, ""); err != nil {
				return err
			}
		}
		if err := h.PressKey("Backspace", 0); err != nil {
			return err
		}
	}
	for _, ch := range text {
		if err := h.PressKey(string(ch), 0); err != nil {
			return err
		}
	}
	_, err = h.JS("(()=>{const e=document.querySelector("+q+");if(!e)return;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})();", "")
	return err
}

type namedKey struct {
	vk         int
	code, text string
}

var namedKeys = map[string]namedKey{
	"Enter": {13, "Enter", "\r"}, "Tab": {9, "Tab", "\t"}, "Backspace": {8, "Backspace", ""},
	"Escape": {27, "Escape", ""}, "Delete": {46, "Delete", ""}, " ": {32, "Space", " "},
	"ArrowLeft": {37, "ArrowLeft", ""}, "ArrowUp": {38, "ArrowUp", ""},
	"ArrowRight": {39, "ArrowRight", ""}, "ArrowDown": {40, "ArrowDown", ""},
	"Home": {36, "Home", ""}, "End": {35, "End", ""}, "PageUp": {33, "PageUp", ""}, "PageDown": {34, "PageDown", ""},
}

// US-layout physical keys for ASCII punctuation, and the shifted characters that share them.
var punctuation = map[rune]namedKey{
	'`': {192, "Backquote", ""}, '-': {189, "Minus", ""}, '=': {187, "Equal", ""}, '[': {219, "BracketLeft", ""},
	']': {221, "BracketRight", ""}, '\\': {220, "Backslash", ""}, ';': {186, "Semicolon", ""}, '\'': {222, "Quote", ""},
	',': {188, "Comma", ""}, '.': {190, "Period", ""}, '/': {191, "Slash", ""},
}
var shifted = map[rune]rune{
	'~': '`', '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
	'_': '-', '+': '=', '{': '[', '}': ']', '|': '\\', ':': ';', '"': '\'', '<': ',', '>': '.', '?': '/',
}

// printableKey is the US-layout code and virtual key for one ASCII character.
func printableKey(c rune) (code string, vk int, shift, ok bool) {
	base, isShifted := shifted[c]
	if !isShifted {
		base = c
	}
	shift = isShifted || unicode.IsUpper(c)
	switch u := unicode.ToUpper(base); {
	case u >= 'A' && u <= 'Z':
		return "Key" + string(u), int(u), shift, true
	case base >= '0' && base <= '9':
		return "Digit" + string(base), int(base), shift, true
	}
	if k, ok := punctuation[base]; ok {
		return k.code, k.vk, shift, true
	}
	return "", 0, false, false
}

// PressKey sends keyDown/char/keyUp with the code and keyCode a US keyboard
// would. Modifiers: 1 Alt, 2 Ctrl, 4 Meta, 8 Shift.
func (h *H) PressKey(key string, modifiers int) error {
	var code, text string
	var vk int
	runes := []rune(key)
	switch k, named := namedKeys[key]; {
	case named:
		vk, code, text = k.vk, k.code, k.text
	case len(runes) == 1:
		text = key
		if c, v, shift, ok := printableKey(runes[0]); ok {
			code, vk = c, v
			if shift && modifiers&7 == 0 {
				modifiers |= 8
			}
		}
	default:
		code = key
	}
	base := M{"key": key, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
	with := func(extra M) M {
		out := M{}
		for k, v := range base {
			out[k] = v
		}
		for k, v := range extra {
			out[k] = v
		}
		return out
	}
	printable := len(runes) == 1 && text != "" && modifiers&7 == 0
	down := with(M{"type": "keyDown"})
	if !printable && text != "" {
		down["text"] = text
	}
	events := []M{down}
	if printable {
		events = append(events, with(M{"type": "char", "text": text}))
	}
	events = append(events, with(M{"type": "keyUp"}))
	for _, ev := range events {
		if _, err := h.CDP("Input.dispatchKeyEvent", ev, ""); err != nil {
			return err
		}
	}
	return nil
}

func (h *H) Scroll(x, y, dy, dx float64) error {
	_, err := h.CDP("Input.dispatchMouseEvent", M{"type": "mouseWheel", "x": x, "y": y, "deltaX": dx, "deltaY": dy}, "")
	return err
}

func (h *H) DispatchKey(selector, key, event string) error {
	kc := map[string]int{"Enter": 13, "Tab": 9, "Escape": 27, "Backspace": 8, " ": 32, "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40}[key]
	if r := []rune(key); kc == 0 && len(r) == 1 {
		kc = int(r[0])
	}
	_, err := h.JS(fmt.Sprintf("(()=>{const e=document.querySelector(%s);if(e){e.focus();e.dispatchEvent(new KeyboardEvent(%s,{key:%s,code:%s,keyCode:%d,which:%d,bubbles:true}));}})()",
		quote(selector), quote(event), quote(key), quote(key), kc, kc), "")
	return err
}

func (h *H) UploadFile(selector string, files []string) error {
	doc, err := h.CDP("DOM.getDocument", M{"depth": -1}, "")
	if err != nil {
		return err
	}
	root, _ := doc["root"].(M)
	r, err := h.CDP("DOM.querySelector", M{"nodeId": root["nodeId"], "selector": selector}, "")
	if err != nil {
		return err
	}
	if n, _ := r["nodeId"].(float64); n == 0 {
		return fmt.Errorf("no element for %s", selector)
	}
	_, err = h.CDP("DOM.setFileInputFiles", M{"files": files, "nodeId": r["nodeId"]}, "")
	return err
}

// --- screenshots ---

// CaptureScreenshot saves a PNG; maxDim > 0 downscales so neither side exceeds it.
func (h *H) CaptureScreenshot(path string, full bool, maxDim int) (string, error) {
	if path == "" {
		path = filepath.Join(paths.TmpDir(), "shot.png")
	}
	r, err := h.cdpTimeout("Page.captureScreenshot", M{"format": "png", "captureBeyondViewport": full}, "", screenshotTimeout)
	if err != nil {
		if strings.Contains(err.Error(), "timed out") {
			return "", fmt.Errorf("Page.captureScreenshot timed out after %gs", screenshotTimeout.Seconds())
		}
		return "", err
	}
	raw, err := base64.StdEncoding.DecodeString(fmt.Sprint(r["data"]))
	if err != nil {
		return "", err
	}
	if maxDim > 0 {
		if raw, err = downscale(raw, maxDim); err != nil {
			return "", err
		}
	}
	return path, os.WriteFile(path, raw, 0o644)
}

func downscale(raw []byte, maxDim int) ([]byte, error) {
	img, err := png.Decode(bytes.NewReader(raw))
	if err != nil {
		return nil, err
	}
	b := img.Bounds()
	long := max(b.Dx(), b.Dy())
	if long <= maxDim {
		return raw, nil
	}
	s := float64(maxDim) / float64(long)
	dst := image.NewRGBA(image.Rect(0, 0, max(1, int(math.Round(float64(b.Dx())*s))), max(1, int(math.Round(float64(b.Dy())*s)))))
	draw.CatmullRom.Scale(dst, dst.Bounds(), img, b, draw.Src, nil)
	var buf bytes.Buffer
	err = png.Encode(&buf, dst)
	return buf.Bytes(), err
}

// --- tabs ---

// Tab is what tab helpers return.
type Tab = M

func tab(id, title, url any) Tab {
	return Tab{"targetId": id, "target_id": id, "title": title, "url": url}
}

func isInternal(url string) bool {
	for _, p := range internalPrefixes {
		if strings.HasPrefix(url, p) {
			return true
		}
	}
	return false
}

func (h *H) ListTabs(includeChrome bool) ([]Tab, error) {
	r, err := h.CDP("Target.getTargets", nil, "")
	if err != nil {
		return nil, err
	}
	infos, _ := r["targetInfos"].([]any)
	out := []Tab{}
	for _, i := range infos {
		t, _ := i.(M)
		url, _ := t["url"].(string)
		title, _ := t["title"].(string)
		placeholder := strings.HasPrefix(title, "Starting agent ") && (url == "" || url == "about:blank" || strings.HasPrefix(url, "about:blank#"))
		if t["type"] != "page" || placeholder || (!includeChrome && isInternal(url)) {
			continue
		}
		out = append(out, tab(t["targetId"], title, url))
	}
	return out, nil
}

func (h *H) CurrentTab() (Tab, error) {
	m, err := h.send(M{"meta": "current_tab"}, callTimeout)
	if err != nil {
		return nil, err
	}
	return tab(m["targetId"], m["title"], m["url"]), nil
}

func (h *H) ActivateTab(target string) (string, error) {
	_, err := h.CDP("Target.activateTarget", M{"targetId": target}, "")
	return target, err
}

func markerOff() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("BH_TAB_MARKER"))) {
	case "0", "false", "no", "off":
		return true
	}
	return false
}

// SwitchTab attaches the agent to target, moving the 🐴 title marker with it.
func (h *H) SwitchTab(target string, activate bool) (string, error) {
	_, _ = h.CDP("Runtime.evaluate", M{"expression": "if(document.title.startsWith('\U0001F434 '))document.title=document.title.slice(3)"}, "")
	if activate {
		if _, err := h.ActivateTab(target); err != nil {
			return "", err
		}
	}
	r, err := h.CDP("Target.attachToTarget", M{"targetId": target, "flatten": true}, "")
	if err != nil {
		return "", err
	}
	sid, _ := r["sessionId"].(string)
	if _, err := h.send(M{"meta": "set_session", "session_id": sid, "target_id": target}, callTimeout); err != nil {
		return "", err
	}
	if !markerOff() {
		_, _ = h.CDP("Runtime.evaluate", M{"expression": "if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title"}, "")
	}
	return sid, nil
}

// NewTab opens url in a background tab, reusing the attached tab when it is blank.
func (h *H) NewTab(url string) (string, error) {
	if url != "about:blank" {
		if cur, err := h.CurrentTab(); err == nil {
			u, _ := cur["url"].(string)
			if u == "" || u == "about:blank" || u == "data:text/html," || strings.HasPrefix(u, "about:blank#") ||
				strings.HasPrefix(u, "chrome://newtab") || strings.HasPrefix(u, "chrome://new-tab-page") ||
				strings.HasPrefix(u, "edge://newtab") || strings.HasPrefix(u, "about:newtab") {
				if _, err := h.GotoURL(url); err != nil {
					return "", err
				}
				id, _ := cur["targetId"].(string)
				return id, nil
			}
		}
	}
	// Create blank then navigate: a url in createTarget races the attach.
	r, err := h.CDP("Target.createTarget", M{"url": "about:blank", "background": true}, "")
	if err != nil {
		return "", err
	}
	tid, _ := r["targetId"].(string)
	if _, err := h.SwitchTab(tid, false); err != nil {
		return "", err
	}
	if url != "about:blank" {
		_, err = h.GotoURL(url)
	}
	return tid, err
}

func (h *H) CloseTab(target string) error {
	if target == "" {
		cur, err := h.CurrentTab()
		if err != nil {
			return err
		}
		target, _ = cur["targetId"].(string)
	}
	_, err := h.CDP("Target.closeTarget", M{"targetId": target}, "")
	return err
}

func (h *H) EnsureRealTab() (Tab, error) {
	tabs, err := h.ListTabs(false)
	if err != nil || len(tabs) == 0 {
		return nil, err
	}
	if cur, err := h.CurrentTab(); err == nil {
		if u, _ := cur["url"].(string); u != "" && !isInternal(u) {
			return cur, nil
		}
	}
	id, _ := tabs[0]["targetId"].(string)
	_, err = h.SwitchTab(id, false)
	return tabs[0], err
}

func (h *H) IframeTarget(urlSubstr string) (string, error) {
	r, err := h.CDP("Target.getTargets", nil, "")
	if err != nil {
		return "", err
	}
	infos, _ := r["targetInfos"].([]any)
	for _, i := range infos {
		t, _ := i.(M)
		if u, _ := t["url"].(string); t["type"] == "iframe" && strings.Contains(u, urlSubstr) {
			id, _ := t["targetId"].(string)
			return id, nil
		}
	}
	return "", nil
}

// --- waiting ---

func Wait(seconds float64) { time.Sleep(time.Duration(seconds * float64(time.Second))) }

func (h *H) poll(timeout float64, interval time.Duration, check func() (bool, error)) (bool, error) {
	deadline := time.Now().Add(time.Duration(timeout * float64(time.Second)))
	for time.Now().Before(deadline) {
		ok, err := check()
		if err != nil || ok {
			return ok, err
		}
		time.Sleep(interval)
	}
	return false, nil
}

func (h *H) WaitForLoad(timeout float64) (bool, error) {
	return h.poll(timeout, 300*time.Millisecond, func() (bool, error) {
		v, err := h.JS("document.readyState", "")
		return v == "complete", err
	})
}

// WaitForElement polls for selector; visible also requires it to be rendered.
func (h *H) WaitForElement(selector string, timeout float64, visible bool) (bool, error) {
	q := quote(selector)
	check := "!!document.querySelector(" + q + ")"
	if visible {
		check = "(()=>{const e=document.querySelector(" + q + ");if(!e)return false;" +
			"if(typeof e.checkVisibility==='function')return e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true});" +
			"const s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'})()"
	}
	return h.poll(timeout, 300*time.Millisecond, func() (bool, error) {
		v, err := h.JS(check, "")
		return v == true, err
	})
}

// WaitForNetworkIdle waits until no requests are in flight on the attached
// session and no Network events arrived for idleMs.
func (h *H) WaitForNetworkIdle(timeout float64, idleMs int) (bool, error) {
	s, err := h.send(M{"meta": "session"}, callTimeout)
	if err != nil {
		return false, err
	}
	active := s["session_id"]
	inflight := map[any]bool{}
	last := time.Now()
	return h.poll(timeout, 100*time.Millisecond, func() (bool, error) {
		events, err := h.DrainEvents()
		if err != nil {
			return false, err
		}
		for _, ev := range events {
			e, _ := ev.(M)
			if e["session_id"] != active {
				continue
			}
			method, _ := e["method"].(string)
			params, _ := e["params"].(M)
			switch {
			case method == "Network.requestWillBeSent":
				inflight[params["requestId"]] = true
				last = time.Now()
			case method == "Network.loadingFinished" || method == "Network.loadingFailed":
				delete(inflight, params["requestId"])
				last = time.Now()
			case strings.HasPrefix(method, "Network."):
				last = time.Now()
			}
		}
		return len(inflight) == 0 && time.Since(last) >= time.Duration(idleMs)*time.Millisecond, nil
	})
}

// --- HTTP without the browser ---

// HTTPGet fetches url; with BROWSER_USE_API_KEY it goes through the fetch-use
// proxy (bot detection, residential IPs), otherwise directly.
func HTTPGet(url string, headers map[string]string, timeout float64) (string, error) {
	if key := os.Getenv("BROWSER_USE_API_KEY"); key != "" {
		return fetchUse(url, headers, timeout, key)
	}
	ctx := &http.Client{Timeout: time.Duration(timeout * float64(time.Second))}
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0")
	req.Header.Set("Accept-Encoding", "gzip")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := ctx.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("HTTP Error %d: %s", resp.StatusCode, http.StatusText(resp.StatusCode))
	}
	var body io.Reader = resp.Body
	if resp.Header.Get("Content-Encoding") == "gzip" {
		gz, err := gzip.NewReader(resp.Body)
		if err != nil {
			return "", err
		}
		body = gz
	}
	raw, err := io.ReadAll(body)
	return string(raw), err
}

func fetchUse(url string, headers map[string]string, timeout float64, key string) (string, error) {
	session := os.Getenv("SESSION_ID")
	if session == "" {
		b := make([]byte, 16)
		_, _ = rand.Read(b)
		h := hex.EncodeToString(b)
		session = h[:8] + "-" + h[8:12] + "-" + h[12:16] + "-" + h[16:20] + "-" + h[20:]
	}
	ms := min(int(timeout*1000), 120_000)
	payload := M{"url": url, "method": "GET", "timeout_ms": ms, "follow_redirects": true, "max_redirects": 10,
		"proxy_country": "US", "session_id": session}
	if len(headers) > 0 {
		payload["headers"] = headers
	}
	body, _ := json.Marshal(payload)
	base := os.Getenv("FETCH_USE_URL")
	if base == "" {
		base = "https://fetch.browser-use.com"
	}
	req, err := http.NewRequest("POST", base+"/fetch", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Browser-Use-API-Key", key)
	if t := os.Getenv("FETCH_USE_AUTH_TOKEN"); t != "" {
		req.Header.Set("X-Fetch-Token", t)
	}
	resp, err := (&http.Client{Timeout: time.Duration(ms)*time.Millisecond + 10*time.Second}).Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	var out struct {
		Body  string `json:"body"`
		Error string `json:"error"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", fmt.Errorf("fetch-use: HTTP %d", resp.StatusCode)
	}
	if out.Error != "" {
		return "", errors.New(out.Error)
	}
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("fetch-use: HTTP %d", resp.StatusCode)
	}
	return out.Body, nil
}
