package telemetry

import "testing"

func TestErrorClassCarriesNoMessageText(t *testing.T) {
	steps := []any{map[string]any{"helper": "js", "error": false}, map[string]any{"helper": "fill_input", "error": true}}
	cases := map[string]string{
		"GoError: no element #secret":            "helper:fill_input",
		"Error: PRIVATE_PAGE_VALUE":              "Error",
		"TypeError: x is undefined at line 3":    "TypeError",
		"PRIVATE_PAGE_VALUE: thrown as a string": "error",
	}
	for msg, want := range cases {
		s := steps
		if want != "helper:fill_input" {
			s = nil
		}
		if got := errorClass(msg, s); got != want {
			t.Errorf("%q: got %q, want %q", msg, got, want)
		}
	}
}
