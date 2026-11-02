package helpers

import (
	"bytes"
	"encoding/base64"
	"errors"
	"image"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// fake is a scripted daemon: reply(req) decides each response, and every request is kept.
type fake struct {
	reqs     []M
	timeouts []time.Duration
	reply    func(req M) (M, error)
}

func newFake(t *testing.T, reply func(req M) (M, error)) (*H, *fake) {
	t.Helper()
	f := &fake{reply: reply}
	h := &H{Name: "test"}
	h.Send = func(req M, timeout time.Duration) (M, error) {
		f.reqs = append(f.reqs, req)
		f.timeouts = append(f.timeouts, timeout)
		if f.reply == nil {
			return M{"result": M{}}, nil
		}
		return f.reply(req)
	}
	return h, f
}

func (f *fake) methods() []string {
	var out []string
	for _, r := range f.reqs {
		if m, ok := r["method"].(string); ok {
			out = append(out, m)
		} else {
			out = append(out, "meta:"+r["meta"].(string))
		}
	}
	return out
}

func (f *fake) params(method string) []M {
	var out []M
	for _, r := range f.reqs {
		if r["method"] == method {
			out = append(out, r["params"].(M))
		}
	}
	return out
}

func value(v any) (M, error) { return M{"result": M{"result": M{"value": v}}}, nil }

func pngOf(w, h int) []byte {
	var b bytes.Buffer
	_ = png.Encode(&b, image.NewRGBA(image.Rect(0, 0, w, h)))
	return b.Bytes()
}

func TestDownscale(t *testing.T) {
	out, _ := downscale(pngOf(4000, 2000), 1800)
	if c, _ := png.DecodeConfig(bytes.NewReader(out)); c.Width != 1800 || c.Height != 900 {
		t.Fatalf("%dx%d", c.Width, c.Height)
	}
	small := pngOf(100, 50)
	if out, _ := downscale(small, 1800); !bytes.Equal(out, small) {
		t.Fatal("small image was re-encoded")
	}
}

func TestScreenshotUsesLongTimeoutAndSaves(t *testing.T) {
	h, f := newFake(t, func(M) (M, error) {
		return M{"result": M{"data": base64.StdEncoding.EncodeToString(pngOf(10, 10))}}, nil
	})
	p := filepath.Join(t.TempDir(), "s.png")
	if _, err := h.CaptureScreenshot(p, false, 0); err != nil {
		t.Fatal(err)
	}
	if f.timeouts[0] != screenshotTimeout {
		t.Fatalf("timeout %v", f.timeouts[0])
	}
	if _, ok := f.reqs[0]["params"].(M)["_response_timeout"]; ok {
		t.Fatal("timeout forwarded to CDP")
	}
	if b, _ := os.ReadFile(p); len(b) == 0 {
		t.Fatal("no file")
	}
	h, _ = newFake(t, func(M) (M, error) {
		return nil, errors.New("Page.captureScreenshot timed out after 10s waiting for the daemon")
	})
	if _, err := h.CaptureScreenshot(p, false, 0); err == nil || !strings.Contains(err.Error(), "timed out after 10s") {
		t.Fatal(err)
	}
	var full time.Duration
	h, _ = newFake(t, nil)
	send := h.Send
	h.Send = func(req M, timeout time.Duration) (M, error) { full = timeout; return send(req, timeout) }
	_, _ = h.CaptureScreenshot(p, true, 0)
	if full != fullScreenshotTimeout {
		t.Fatalf("full-page timeout %v", full)
	}
}

func TestGotoURLDomainSkills(t *testing.T) {
	ws := t.TempDir()
	t.Setenv("BH_AGENT_WORKSPACE", ws)
	_ = os.MkdirAll(filepath.Join(ws, "domain-skills", "example"), 0o755)
	_ = os.WriteFile(filepath.Join(ws, "domain-skills", "example", "a.md"), nil, 0o644)
	h, _ := newFake(t, nil)
	t.Setenv("BH_DOMAIN_SKILLS", "")
	if r, _ := h.GotoURL("https://www.example.com/x"); r["domain_skills"] != nil {
		t.Fatal("skills listed by default")
	}
	t.Setenv("BH_DOMAIN_SKILLS", "1")
	if r, _ := h.GotoURL("https://www.example.com/x"); r["domain_skills"] == nil {
		t.Fatalf("skills missing: %v", r)
	}
}

func TestPageInfoJSException(t *testing.T) {
	h, _ := newFake(t, func(req M) (M, error) {
		if req["meta"] == "pending_dialog" {
			return M{}, nil
		}
		return M{"result": M{"result": M{"subtype": "error", "description": "ReferenceError: x"},
			"exceptionDetails": M{"lineNumber": 0, "columnNumber": 5}}}, nil
	})
	if _, err := h.PageInfo(); err == nil || !strings.Contains(err.Error(), "ReferenceError: x") || !strings.Contains(err.Error(), "line 0, column 5") {
		t.Fatal(err)
	}
}

func fillFake(t *testing.T, ua string, found bool) (*H, *fake) {
	return newFake(t, func(req M) (M, error) {
		switch req["method"] {
		case "Browser.getVersion":
			return M{"result": M{"userAgent": ua}}, nil
		case "Runtime.evaluate":
			return value(found)
		}
		return M{"result": M{}}, nil
	})
}

func keyEvents(f *fake) []M { return f.params("Input.dispatchKeyEvent") }

func TestFillInput(t *testing.T) {
	h, f := fillFake(t, "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)", true)
	if err := h.FillInput("#q", "Hi", true, 0); err != nil {
		t.Fatal(err)
	}
	ev := keyEvents(f)
	if ev[0]["type"] != "rawKeyDown" || ev[0]["modifiers"] != 4.0 || ev[1]["type"] != "keyUp" {
		t.Fatalf("select-all %v", ev[:2])
	}
	if ev[2]["key"] != "Backspace" {
		t.Fatalf("no backspace: %v", ev[2])
	}
	// "H" needs Shift on a US keyboard; each char is keyDown, char, keyUp.
	if ev[4]["key"] != "H" || ev[4]["code"] != "KeyH" || ev[4]["modifiers"] != 8 || ev[5]["type"] != "char" {
		t.Fatalf("H %v %v", ev[4], ev[5])
	}
	last := f.params("Runtime.evaluate")
	if !strings.Contains(last[len(last)-1]["expression"].(string), "new Event('change'") {
		t.Fatal("no change event")
	}
	_ = h.FillInput("#q", "x", true, 0)
	if n := len(f.params("Browser.getVersion")); n != 1 {
		t.Fatalf("browser OS queried %d times", n)
	}

	h, f = fillFake(t, "Mozilla/5.0 (X11; Linux x86_64)", true)
	_ = h.FillInput("#q", "x", true, 0)
	if keyEvents(f)[0]["modifiers"] != 2.0 {
		t.Fatal("linux should use Ctrl")
	}
	h, f = fillFake(t, "", true)
	_ = h.FillInput("#q", "x", false, 0)
	if keyEvents(f)[0]["type"] == "rawKeyDown" {
		t.Fatal("clear_first=false still selected all")
	}
	h, _ = fillFake(t, "", false)
	if err := h.FillInput("#missing", "x", true, 0); err == nil || !strings.Contains(err.Error(), "element not found: #missing") {
		t.Fatal(err)
	}
}

func TestPressKey(t *testing.T) {
	h, f := newFake(t, nil)
	_ = h.PressKey("!", 0)
	ev := keyEvents(f)
	if ev[0]["code"] != "Digit1" || ev[0]["windowsVirtualKeyCode"] != 49 || ev[0]["modifiers"] != 8 {
		t.Fatalf("! %v", ev[0])
	}
	f.reqs = nil
	_ = h.PressKey("é", 0)
	if ev := keyEvents(f); ev[0]["code"] != "" || ev[1]["text"] != "é" {
		t.Fatalf("é %v", ev)
	}
	f.reqs = nil
	_ = h.PressKey("ı", 0)
	if ev := keyEvents(f); ev[0]["code"] != "" || ev[0]["modifiers"] != 0 {
		t.Fatalf("ı %v", ev)
	}
	f.reqs = nil
	_ = h.PressKey("A", 2) // Ctrl+Shift intent stays the caller's: no forced Shift, no char event.
	if ev := keyEvents(f); ev[0]["modifiers"] != 2 || len(ev) != 2 {
		t.Fatalf("shortcut %v", ev)
	}
	f.reqs = nil
	_ = h.PressKey("Enter", 0)
	if ev := keyEvents(f); ev[0]["code"] != "Enter" || ev[0]["text"] != "\r" || len(ev) != 2 {
		t.Fatalf("Enter %v", ev)
	}
}

func TestWaitForElement(t *testing.T) {
	h, f := newFake(t, func(M) (M, error) { return value(true) })
	if ok, _ := h.WaitForElement("#a", 1, true); !ok || !strings.Contains(f.params("Runtime.evaluate")[0]["expression"].(string), "checkVisibility") {
		t.Fatal("visible check")
	}
	h, f = newFake(t, func(M) (M, error) { return value(false) })
	if ok, _ := h.WaitForElement("#a", 0.2, false); ok || strings.Contains(f.params("Runtime.evaluate")[0]["expression"].(string), "checkVisibility") {
		t.Fatal("timeout/simple check")
	}
}

func TestWaitForNetworkIdle(t *testing.T) {
	batches := [][]any{
		{M{"session_id": "other", "method": "Network.requestWillBeSent", "params": M{"requestId": "x"}}},
		{M{"session_id": "s1", "method": "Network.requestWillBeSent", "params": M{"requestId": "1"}}},
		{M{"session_id": "s1", "method": "Network.loadingFinished", "params": M{"requestId": "1"}}},
	}
	h, _ := newFake(t, func(req M) (M, error) {
		switch req["meta"] {
		case "session":
			return M{"session_id": "s1"}, nil
		case "drain_events":
			if len(batches) == 0 {
				return M{"events": []any{}}, nil
			}
			b := batches[0]
			batches = batches[1:]
			return M{"events": b}, nil
		}
		return M{}, nil
	})
	start := time.Now()
	if ok, _ := h.WaitForNetworkIdle(3, 200); !ok || time.Since(start) < 200*time.Millisecond {
		t.Fatal("idle")
	}
	batches = [][]any{{M{"session_id": "s1", "method": "Network.requestWillBeSent", "params": M{"requestId": "2"}}}}
	if ok, _ := h.WaitForNetworkIdle(0.4, 100); ok {
		t.Fatal("in-flight request counted as idle")
	}
}

func TestTabs(t *testing.T) {
	h, f := newFake(t, func(req M) (M, error) {
		switch {
		case req["method"] == "Target.createTarget":
			return M{"result": M{"targetId": "T2"}}, nil
		case req["method"] == "Target.attachToTarget":
			return M{"result": M{"sessionId": "S2"}}, nil
		case req["meta"] == "current_tab":
			return M{"targetId": "T1", "url": "https://x.test/", "title": "x"}, nil
		}
		return M{"result": M{}}, nil
	})
	if _, err := h.NewTab("https://a.test/"); err != nil {
		t.Fatal(err)
	}
	if bg := f.params("Target.createTarget")[0]; bg["background"] != true || bg["url"] != "about:blank" {
		t.Fatalf("create %v", bg)
	}
	if len(f.params("Target.activateTarget")) != 0 {
		t.Fatal("switch_tab activated the visible tab")
	}
	f.reqs = nil
	_, _ = h.SwitchTab("T2", true)
	if len(f.params("Target.activateTarget")) != 1 {
		t.Fatal("activate=true ignored")
	}
	t.Setenv("BH_TAB_MARKER", "off")
	f.reqs = nil
	_, _ = h.SwitchTab("T2", false)
	for _, p := range f.params("Runtime.evaluate") {
		if strings.Contains(p["expression"].(string), "'\U0001F434 '+document.title") {
			t.Fatal("marker added while disabled")
		}
	}

	// A blank attached tab is reused instead of opening another.
	h, f = newFake(t, func(req M) (M, error) {
		if req["meta"] == "current_tab" {
			return M{"targetId": "T1", "url": "data:text/html,", "title": ""}, nil
		}
		return M{"result": M{}}, nil
	})
	if id, _ := h.NewTab("https://a.test/"); id != "T1" || len(f.params("Target.createTarget")) != 0 {
		t.Fatalf("reuse: %s", id)
	}
}

func TestJSIframeSessions(t *testing.T) {
	attach := func(eval func(req M) (M, error), detachErr error) (*H, *fake) {
		return newFake(t, func(req M) (M, error) {
			switch req["method"] {
			case "Target.attachToTarget":
				return M{"result": M{"sessionId": "S"}}, nil
			case "Target.detachFromTarget":
				if detachErr != nil {
					return nil, detachErr
				}
				return M{"result": M{}}, nil
			case "Runtime.evaluate":
				return eval(req)
			}
			return M{"result": M{}}, nil
		})
	}
	h, f := attach(func(M) (M, error) { return value(1) }, nil)
	if v, err := h.JS("1", "IFRAME"); err != nil || v != 1 || len(f.params("Target.detachFromTarget")) != 1 {
		t.Fatalf("%v %v", v, err)
	}
	h, f = newFake(t, func(M) (M, error) { return value(1) })
	_, _ = h.JS("1", "")
	if len(f.params("Target.attachToTarget")) != 0 || len(f.params("Target.detachFromTarget")) != 0 {
		t.Fatal("attached without a target")
	}
	// The `return` retry reuses the one attached session.
	calls := 0
	h, f = attach(func(M) (M, error) {
		calls++
		if calls == 1 {
			return M{"result": M{"result": M{"subtype": "error", "description": "SyntaxError: Illegal return statement"}}}, nil
		}
		return value(2)
	}, nil)
	if v, _ := h.JS("return 2", "IFRAME"); v != 2 || len(f.params("Target.attachToTarget")) != 1 {
		t.Fatal("retry")
	}
	// Detach failures: dropped sessions are fine, others surface, eval errors win.
	h, _ = attach(func(M) (M, error) { return value(1) }, errors.New("No session with given id"))
	if _, err := h.JS("1", "IFRAME"); err != nil {
		t.Fatal(err)
	}
	h, _ = attach(func(M) (M, error) { return value(1) }, errors.New("boom"))
	if _, err := h.JS("1", "IFRAME"); err == nil || err.Error() != "boom" {
		t.Fatal(err)
	}
	h, _ = attach(func(M) (M, error) { return nil, errors.New("eval broke") }, errors.New("boom"))
	if _, err := h.JS("1", "IFRAME"); err == nil || !strings.Contains(err.Error(), "eval broke") {
		t.Fatal(err)
	}
}

func TestScrollRetriesWithFocusEmulationAfterTimeout(t *testing.T) {
	wheels := 0
	h, f := newFake(t, func(req M) (M, error) {
		if req["method"] == "Input.dispatchMouseEvent" {
			if wheels++; wheels == 1 {
				return nil, errors.New("Input.dispatchMouseEvent timed out after 3s waiting for the daemon")
			}
		}
		return M{"result": M{}}, nil
	})
	if err := h.Scroll(1, 2, -100, 0); err != nil {
		t.Fatal(err)
	}
	got := strings.Join(f.methods(), ",")
	want := "Input.dispatchMouseEvent,Emulation.setFocusEmulationEnabled,Input.dispatchMouseEvent,Emulation.setFocusEmulationEnabled"
	if got != want || f.reqs[3]["params"].(M)["enabled"] != false {
		t.Fatalf("calls %s", got)
	}
}
