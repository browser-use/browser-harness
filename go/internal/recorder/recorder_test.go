package recorder

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type fakePage struct {
	ctx  map[string]any
	shot string
	err  error
}

func (f fakePage) JS(string) (map[string]any, error) { return f.ctx, nil }
func (f fakePage) Screenshot() (string, error)       { return f.shot, f.err }

func events(t *testing.T, d string) []map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(d, "events.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	var out []map[string]any
	for _, line := range strings.Split(strings.TrimSpace(string(raw)), "\n") {
		var m map[string]any
		if err := json.Unmarshal([]byte(line), &m); err != nil {
			t.Fatal(err)
		}
		out = append(out, m)
	}
	return out
}

func click() Call { return Call{Helper: "click_at_xy", Args: []any{10, 20}} }

func TestCaptureWritesFrame(t *testing.T) {
	d := t.TempDir()
	capture(d, click(), fakePage{shot: base64.StdEncoding.EncodeToString([]byte("jpeg-bytes"))})
	ev := events(t, d)[0]
	if ev["frame"] != "0001.jpg" || ev["x"] != 10.0 || ev["y"] != 20.0 {
		t.Fatalf("event %v", ev)
	}
	if b, _ := os.ReadFile(filepath.Join(d, "0001.jpg")); string(b) != "jpeg-bytes" {
		t.Fatalf("frame %q", b)
	}
}

func TestDroppedFrameIsRecorded(t *testing.T) {
	d := t.TempDir()
	capture(d, click(), fakePage{err: errors.New("Page.captureScreenshot timed out after 60s")})
	ev := events(t, d)[0]
	if _, ok := ev["frame"]; ok {
		t.Fatalf("frame on failure: %v", ev)
	}
	if m, _ := filepath.Glob(filepath.Join(d, "*.jpg")); len(m) != 0 {
		t.Fatalf("jpg written: %v", m)
	}
	if fe, _ := ev["frame_error"].(string); !strings.Contains(fe, "Page.captureScreenshot") || !strings.Contains(fe, "60s") {
		t.Fatalf("frame_error %q", fe)
	}
}

func TestMessageLessFrameError(t *testing.T) {
	d := t.TempDir()
	capture(d, click(), fakePage{err: errors.New("")})
	if fe := events(t, d)[0]["frame_error"]; fe != "RuntimeError: no detail" {
		t.Fatalf("frame_error %q", fe)
	}
}

func TestPasswordTextIsMasked(t *testing.T) {
	d := t.TempDir()
	c := Call{Helper: "type_text", Args: []any{"hunter2"}}
	capture(d, c, fakePage{ctx: map[string]any{"input": "password"}, err: errors.New("x")})
	if txt := events(t, d)[0]["text"]; txt != "•••••••" {
		t.Fatalf("text %q", txt)
	}
}

func TestURLSecretsAreScrubbed(t *testing.T) {
	d := t.TempDir()
	c := Call{Helper: "goto_url", Args: []any{"https://x.test/cb?code=abc&ok=1"}}
	capture(d, c, fakePage{err: errors.New("x")})
	to, _ := events(t, d)[0]["to"].(string)
	if strings.Contains(to, "abc") {
		t.Fatalf("to %q", to)
	}
}
