package pyjson

import "testing"

func TestDumps(t *testing.T) {
	cases := []struct {
		v      any
		indent int
		want   string
	}{
		{Obj{{"status", "stored"}, {"path", "/x/auth.json"}}, 0, `{"status": "stored", "path": "/x/auth.json"}`},
		{map[string]any{"b": 1, "a": []any{true, nil, 2.5, 3.0}}, 0, `{"a": [true, null, 2.5, 3.0], "b": 1}`},
		{Obj{{"status", "missing"}, {"source", nil}}, 2, "{\n  \"status\": \"missing\",\n  \"source\": null\n}"},
		{"caf\u00e9 \U0001F434 \x7f \"q\"", 0, `"caf\u00e9 \ud83d\udc34 \u007f \"q\""`},
	}
	for _, c := range cases {
		if got := Dumps(c.v, c.indent); got != c.want {
			t.Errorf("Dumps(%v)=%s want %s", c.v, got, c.want)
		}
	}
}

func TestDumpsUnicode(t *testing.T) {
	got := DumpsUnicode(Obj{{K: "title", V: "café \U0001F434 \x7f\n"}, {K: "w", V: 393}})
	want := "{\"title\": \"café \U0001F434 \x7f\\n\", \"w\": 393}"
	if got != want {
		t.Errorf("got %q want %q", got, want)
	}
}
