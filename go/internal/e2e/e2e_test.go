// Package e2e drives the real binary against a real Chrome. It runs only when
// BH_TEST_CDP_URL points at one (go/tools/test.sh starts a headless Chrome).
package e2e

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

const page = `<!doctype html><title>Form</title><body><input id=name></body>`

type env struct {
	t   *testing.T
	bin string
	dir string
	url string // the test page
}

func setup(t *testing.T) *env {
	cdp := os.Getenv("BH_TEST_CDP_URL")
	if cdp == "" {
		t.Skip("BH_TEST_CDP_URL not set")
	}
	dir := t.TempDir()
	bin := filepath.Join(dir, "browser-harness")
	if out, err := exec.Command("go", "build", "-o", bin, "../../cmd/browser-harness").CombinedOutput(); err != nil {
		t.Fatalf("build: %v\n%s", err, out)
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(page)) }))
	t.Cleanup(srv.Close)
	e := &env{t: t, bin: bin, dir: dir, url: srv.URL}
	t.Cleanup(func() { _, _ = e.run("none", "", "--reload") })
	return e
}

// run executes one snippet (or CLI args) as its own process, like an agent does.
func (e *env) run(agent, code string, args ...string) (string, error) {
	cmd := exec.Command(e.bin, args...)
	cmd.Env = append(os.Environ(), "BU_CDP_URL="+os.Getenv("BH_TEST_CDP_URL"), "BU_NAME=e2e", "BH_HOME="+e.dir,
		"BH_TELEMETRY=0", "BH_AGENT_ID="+agent)
	cmd.Stdin = strings.NewReader(code)
	out, err := cmd.CombinedOutput()
	return strings.TrimSpace(string(out)), err
}

// parallel runs fn for n agents at once and fails on any error it returns.
func parallel(t *testing.T, n int, fn func(i int) error) {
	var wg sync.WaitGroup
	errs := make([]error, n)
	for i := range n {
		wg.Add(1)
		go func() { defer wg.Done(); errs[i] = fn(i) }()
	}
	wg.Wait()
	for i, err := range errs {
		if err != nil {
			t.Errorf("agent %d: %v", i, err)
		}
	}
}

// Many agents starting at once share one daemon instead of each spawning one.
func TestColdStartsShareOneDaemon(t *testing.T) {
	e := setup(t)
	tabs := make([]string, 10)
	parallel(t, 10, func(i int) error {
		out, err := e.run("none", "print(current_tab().targetId)")
		tabs[i] = out
		return err
	})
	for _, tab := range tabs {
		if tab != tabs[0] {
			t.Fatalf("agents saw different daemons' tabs: %v", tabs)
		}
	}
}

// Agents running separate snippets in parallel each stay on their own current tab.
func TestAgentsKeepTheirOwnCurrentTab(t *testing.T) {
	e := setup(t)
	parallel(t, 8, func(i int) error {
		agent := fmt.Sprintf("agent%d", i)
		if out, err := e.run(agent, fmt.Sprintf(`new_tab(%q); wait_for_load()`, e.url+"/?a="+agent)); err != nil {
			return fmt.Errorf("new_tab: %v %s", err, out)
		}
		defer func() { _, _ = e.run(agent, "close_tab()") }()
		for k := range 5 {
			text := fmt.Sprintf("%s-%d", agent, k)
			out, err := e.run(agent, fmt.Sprintf(`fill_input("#name", %q); print(js("location.search + '|' + document.querySelector('#name').value"))`, text))
			if want := "?a=" + agent + "|" + text; err != nil || out != want {
				return fmt.Errorf("snippet %d: got %q want %q (%v)", k, out, want, err)
			}
		}
		return nil
	})
}

// Agents sharing one snippet-free daemon use named tabs and {tab} without switching.
func TestNamedTabsInParallel(t *testing.T) {
	e := setup(t)
	parallel(t, 8, func(i int) error {
		name := fmt.Sprintf("t%d", i)
		out, err := e.run("none", fmt.Sprintf(`
new_tab(%q, {name: %q}); wait_for_load({tab: %q});
let wrong = 0;
for (let k = 0; k < 10; k++) {
  const text = %q + "-" + k;
  fill_input("#name", text, {tab: %q});
  if (js("document.querySelector('#name').value", {tab: %q}) !== text) wrong++;
}
capture_screenshot(%q, {tab: %q});
close_tab(%q);
print(wrong);`, e.url+"/?t="+name, name, name, name, name, name, filepath.Join(e.dir, name+".png"), name, name))
		if err != nil || out != "0" {
			return fmt.Errorf("got %q (%v)", out, err)
		}
		return nil
	})
}

// An agent's tab never leaks into the shared tab or into on(name), and survives being closed.
func TestAgentTabsStayPrivate(t *testing.T) {
	e := setup(t)
	shared, err := e.run("none", "print(current_tab().targetId)")
	if err != nil {
		t.Fatal(err)
	}
	if out, err := e.run("alice", fmt.Sprintf(`new_tab(%q); wait_for_load()`, e.url+"/?alice")); err != nil {
		t.Fatalf("new_tab: %v %s", err, out)
	}
	if out, _ := e.run("none", "print(current_tab().targetId)"); out != shared {
		t.Fatalf("alice's new_tab moved the shared tab: %s -> %s", shared, out)
	}
	if out, _ := e.run("alice", `print(on("e2e").current_tab().url)`); out != e.url+"/?alice" {
		t.Fatalf("on() ignored alice's tab: %s", out)
	}
	// Closing alice's tab from outside falls back instead of failing her next call.
	if out, err := e.run("alice", `cdp("Target.closeTarget", {targetId: current_tab().targetId}); wait(0.5); print(typeof page_info().url)`); err != nil || out != "string" {
		t.Fatalf("after close: %q %v", out, err)
	}
}
