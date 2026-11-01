package video

import (
	"strings"
	"testing"
)

func summary() Summary {
	ts := 100.0
	return Summary{Events: []Event{
		{Frame: "0001.jpg", Helper: "click_at_xy", TS: &ts, Viewport: Size{780, 437}, Cursor: &Point{10, 20}},
		{Frame: "0002.jpg", Helper: "fill_input", SourceLine: 2, Viewport: Size{780, 437}, Box: &Box{1, 2, 3, 4}},
	}}
}

func brief() Brief {
	zero := 0
	return Brief{Task: "Do it", Plan: []string{"a", "b"}, Outcomes: []string{"done"},
		Actions: []Action{{Event: 1, Chapter: &zero, Route: "Home"}, {Event: 2, Chapter: &zero, Route: "Form", ShowTyping: true}},
		Privacy: &Privacy{ReviewedFrames: []string{"0001.jpg", "0002.jpg"}}}
}

func TestCompile(t *testing.T) {
	c, err := compile(summary(), brief(), map[int]string{2: "Ada"})
	if err != nil {
		t.Fatal(err)
	}
	click, typing := c.Beats[1], c.Beats[2]
	if !click.Click || click.T == nil || *click.T != 0 || typing.Type.Text != "Ada" || typing.EndStateHold == 0 {
		t.Fatalf("%+v %+v", click, typing)
	}
	if !strings.HasPrefix(string(renderComposition(c)), "window.COMPOSITION = {") {
		t.Fatal("composition prefix")
	}
}

func TestCompileRejects(t *testing.T) {
	cases := map[string]func(*Brief){
		"privacy review missing": func(b *Brief) { b.Privacy.ReviewedFrames = []string{"0001.jpg"} },
		"raw URL":                func(b *Brief) { b.Actions[0].Route = "https://x.test/" },
		"seven words":            func(b *Brief) { b.Actions[0].Narration = "one two three four five six seven eight" },
		"non-password":           func(*Brief) {},
		"must index plan":        func(b *Brief) { n := 5; b.Actions[0].Chapter = &n },
	}
	for want, mutate := range cases {
		b := brief()
		mutate(&b)
		revealed := map[int]string{2: "Ada"}
		if want == "non-password" {
			revealed = nil
		}
		if _, err := compile(summary(), b, revealed); err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("%s: %v", want, err)
		}
	}
}
