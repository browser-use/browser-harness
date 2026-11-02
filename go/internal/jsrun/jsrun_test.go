package jsrun

import (
	"bytes"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/browser-use/browser-harness/go/internal/helpers"
)

func fakeDaemon(t *testing.T) *[]helpers.M {
	t.Helper()
	t.Setenv("BH_AGENT_ID", "none") // these tests count requests; agent tabs add a lookup
	var reqs []helpers.M
	saved := newHelpers
	t.Cleanup(func() { newHelpers = saved })
	newHelpers = func(name string) *helpers.H {
		h := &helpers.H{Name: name}
		h.Send = func(req helpers.M, _ time.Duration) (helpers.M, error) {
			reqs = append(reqs, req)
			switch req["method"] {
			case "Runtime.evaluate":
				return helpers.M{"result": helpers.M{"result": helpers.M{"value": "Example"}}}, nil
			case "Target.closeTarget":
				return nil, errors.New("No target with given id found (CDP -32602)")
			}
			return helpers.M{"result": helpers.M{}}, nil
		}
		return h
	}
	return &reqs
}

func TestRunSnippet(t *testing.T) {
	reqs := fakeDaemon(t)
	t.Setenv("BH_AGENT_WORKSPACE", t.TempDir())
	var out bytes.Buffer
	trace, err := Run(`
click_at_xy(10, 20, {button: "right"});
print(js("document.title"), {a: [1, 2]});
try { close_tab("nope"); } catch (e) { print("caught:", e.message); }
`, &out, false)
	if err != nil {
		t.Fatal(err)
	}
	if got := out.String(); got != "Example {\"a\":[1,2]}\ncaught: No target with given id found (CDP -32602)\n" {
		t.Fatalf("output %q", got)
	}
	click := (*reqs)[0]["params"].(helpers.M)
	if click["x"] != 10.0 || click["button"] != "right" {
		t.Fatalf("click %v", click)
	}
	if trace.StepCount != 3 || trace.Steps[2].(map[string]any)["error"] == nil {
		t.Fatalf("trace %+v", trace)
	}
}

func TestUncaughtErrorHasLocation(t *testing.T) {
	fakeDaemon(t)
	t.Setenv("BH_AGENT_WORKSPACE", t.TempDir())
	_, err := Run("\n\nnot_a_helper()", &bytes.Buffer{}, false)
	if err == nil || !strings.Contains(err.Error(), "not_a_helper is not defined") || !strings.Contains(err.Error(), "snippet.js:3") {
		t.Fatal(err)
	}
}

func TestEvalReturnsLastExpression(t *testing.T) {
	fakeDaemon(t)
	v, err := Eval("({n: cfg.n + 1})", map[string]any{"cfg": map[string]any{"n": 1}}, &bytes.Buffer{})
	if err != nil || v.(map[string]any)["n"] != int64(2) {
		t.Fatal(v, err)
	}
}

func TestOptionsVersusPositional(t *testing.T) {
	cases := []struct {
		js         string
		positional int
		want       string
	}{
		{`f("n", {title: "t"})`, 2, "n|t"},
		{`f({name: "n", title: "t"})`, 2, "n|t"},
		{`f("n", "t")`, 2, "n|t"},
		{`f({targetId: "T"})`, 2, "T|"},
		{`f("x", {targetId: "T"})`, 1, "x|"},
		{`f({target_id: "T"})`, 2, "T|"},
	}
	for _, c := range cases {
		r := newRunner(&bytes.Buffer{})
		var got string
		r.bind("f", c.positional, func(a args) (any, error) {
			got = a.str(0, "name", "") + "|" + a.str(1, "title", "")
			return nil, nil
		})
		if _, err := r.rt.RunString(c.js); err != nil || got != c.want {
			t.Errorf("%s: %q %v", c.js, got, err)
		}
	}
}
