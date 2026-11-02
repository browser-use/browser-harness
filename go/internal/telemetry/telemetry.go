// Package telemetry is the best-effort, opt-out PostHog telemetry.
package telemetry

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/proc"
	"github.com/browser-use/browser-harness/go/internal/version"

	"github.com/browser-use/browser-harness/go/internal/paths"
)

const (
	posthogKey  = "phc_rCPCLPtaXB3EuBdiH7JLKtU2Wj5iPnuwdsbw58CnjYXc"
	posthogHost = "https://eu.i.posthog.com"
)

var (
	disableEnvs = []string{"BH_TELEMETRY", "ANONYMIZED_TELEMETRY"}
	installIDRE = regexp.MustCompile(`^[0-9a-f-]{32,36}$`)
)

func configPath() string { return filepath.Join(paths.ConfigDir(), "telemetry.json") }

func load() map[string]any {
	m := map[string]any{}
	if raw, err := os.ReadFile(configPath()); err == nil {
		_ = json.Unmarshal(raw, &m)
	}
	if m == nil {
		m = map[string]any{}
	}
	return m
}

func save(m map[string]any) {
	if raw := indent(m); raw != nil {
		_ = paths.WriteFileAtomic(configPath(), raw, 0o600)
	}
}

func envDisabled() bool {
	for _, k := range disableEnvs {
		if paths.Disabled(os.Getenv(k)) {
			return true
		}
	}
	return false
}

func uuid4() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	b[6] = b[6]&0x0f | 0x40
	b[8] = b[8]&0x3f | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

func installID(m map[string]any, create bool) any {
	if s, ok := m["install_id"].(string); ok && installIDRE.MatchString(s) {
		return s
	}
	if !create {
		return nil
	}
	id := uuid4()
	m["install_id"] = id
	save(m)
	return id
}

// disabledByConfig honours hand-edited opt-outs such as 1 or "yes", not only true.
func disabledByConfig(m map[string]any) bool {
	switch v := m["disabled"].(type) {
	case nil:
		return false
	case bool:
		return v
	case float64:
		return v != 0
	case string:
		return v != ""
	}
	return true
}

func Enabled() bool { return !envDisabled() && !disabledByConfig(load()) }

func Status() map[string]any {
	m := load()
	env := envDisabled()
	enabled := !env && !disabledByConfig(m)
	return map[string]any{
		"enabled": enabled, "disabled_by_env": env, "disabled_by_config": disabledByConfig(m),
		"install_id": installID(m, enabled), "config_path": configPath(),
	}
}

func setEnabled(on bool) map[string]any {
	m := load()
	m["disabled"] = !on
	save(m)
	return Status()
}

// RunCLI is `browser-harness telemetry [status|enable|disable]`.
func RunCLI(args []string) int {
	switch strings.Join(args, " ") {
	case "", "status":
		printJSON(Status())
	case "disable":
		printJSON(setEnabled(false))
	case "enable":
		printJSON(setEnabled(true))
	default:
		fmt.Println("usage: browser-harness telemetry [status|enable|disable]")
		return 2
	}
	return 0
}

var agentMarkers = []struct{ env, want, client string }{
	{"AGENT", "amp", "amp"}, {"CLAUDECODE", "", "claude-code"}, {"CODEX_SANDBOX", "", "codex"},
	{"CODEX_THREAD_ID", "", "codex"}, {"GEMINI_CLI", "", "gemini-cli"}, {"COPILOT_CLI", "", "copilot-cli"},
	{"COPILOT_AGENT_SESSION_ID", "", "copilot-cli"}, {"OPENCLAW_CLI", "", "openclaw"}, {"HERMES_SESSION_ID", "", "hermes"},
	{"CURSOR_AGENT", "", "cursor"}, {"CURSOR_TRACE_ID", "", "cursor"}, {"OPENCODE", "", "opencode"},
}

func agentClient() any {
	for _, m := range agentMarkers {
		if v := os.Getenv(m.env); v != "" && (m.want == "" || v == m.want) {
			return m.client
		}
	}
	return nil
}

func orNil(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func base() map[string]any {
	return map[string]any{"browser_harness_version": version.Version,
		"os": runtime.GOOS, "machine": runtime.GOARCH}
}

func cdpHostname() any {
	v := os.Getenv("BU_CDP_WS")
	if v == "" {
		v = os.Getenv("BU_CDP_URL")
	}
	if v == "" {
		return nil
	}
	if !strings.Contains(v, "://") {
		v = "//" + v
	}
	u, err := url.Parse(v)
	if err != nil || u.Hostname() == "" {
		return nil
	}
	return strings.ToLower(u.Hostname())
}

// CLIEvent is one cli_event; nil pointers encode as null.
type CLIEvent struct {
	Action, Command         string
	Task, Browser           *string
	OutputLength, StepCount *int
	Steps                   any
	Duration                float64
	ExitCode                int
	Error                   *string
}

func strp(p *string) any {
	if p == nil {
		return nil
	}
	return *p
}
func intp(p *int) any {
	if p == nil {
		return nil
	}
	return *p
}

// CaptureCLIEvent sends the event from a detached process; failures are silent.
// Snippet text, output, helper arguments and error details can hold page data
// from the user's browser, so only their sizes, helper names and error class leave the machine.
func CaptureCLIEvent(e CLIEvent) {
	if !Enabled() {
		return
	}
	var taskLen any
	if e.Task != nil {
		taskLen = len([]rune(*e.Task))
	}
	var steps []any
	if s, ok := e.Steps.([]any); ok {
		for _, st := range s {
			m, _ := st.(map[string]any)
			steps = append(steps, map[string]any{"helper": m["helper"], "duration_seconds": m["duration_seconds"], "error": m["error"] != nil})
		}
	}
	var errClass any
	if e.Error != nil {
		errClass = errorClass(*e.Error, steps)
	}
	props := base()
	for k, v := range map[string]any{
		"$process_person_profile": true, "action": e.Action, "command": e.Command,
		"browser": strp(e.Browser), "cdp_url": cdpHostname(),
		"client": orNil(os.Getenv("BH_CLIENT")), "client_version": orNil(os.Getenv("BH_CLIENT_VERSION")),
		"agent_client": agentClient(), "model": orNil(os.Getenv("BROWSER_USE_AGENT_MODEL")),
		"model_provider": orNil(os.Getenv("BROWSER_USE_MODEL_PROVIDER")),
		"task_length":    taskLen, "output_length": intp(e.OutputLength), "steps": steps, "step_count": intp(e.StepCount),
		"duration_seconds": e.Duration, "exit_code": e.ExitCode, "error_class": errClass,
	} {
		props[k] = v
	}
	send(map[string]any{"api_key": posthogKey, "distinct_id": installID(load(), true),
		"event": "cli_event", "properties": props})
}

// errorClass names what failed without any message text, which can echo page data:
// the failing helper, else the JavaScript error type, else "error".
func errorClass(msg string, steps []any) string {
	for i := len(steps) - 1; i >= 0; i-- {
		if m, _ := steps[i].(map[string]any); m["error"] == true {
			return fmt.Sprintf("helper:%v", m["helper"])
		}
	}
	if m := jsErrorRE.FindStringSubmatch(msg); m != nil {
		return m[1]
	}
	return "error"
}

var jsErrorRE = regexp.MustCompile(`^(Error|EvalError|RangeError|ReferenceError|SyntaxError|TypeError|URIError|AggregateError|GoError)\b`)

// send hands the payload to a detached copy of this binary so the CLI never blocks.
func send(payload map[string]any) {
	host := strings.TrimRight(os.Getenv("BH_POSTHOG_HOST"), "/")
	if host == "" {
		host = posthogHost
	}
	timeout := 5.0
	if t, err := strconv.ParseFloat(os.Getenv("BH_TELEMETRY_TIMEOUT"), 64); err == nil {
		timeout = t
	}
	job := map[string]any{"url": host + "/i/v0/e/", "timeout": timeout, "payload": payload}
	raw := compact(job)
	if raw == nil {
		return
	}
	self, err := os.Executable()
	if err != nil {
		return
	}
	// A file, not a stdin pipe: Go feeds pipes from a goroutine that dies when the CLI exits.
	f, err := os.CreateTemp("", "bh-telemetry-*.json")
	if err != nil {
		return
	}
	_, werr := f.Write(raw)
	cerr := f.Close()
	if werr != nil || cerr != nil {
		_ = os.Remove(f.Name())
		return
	}
	cmd := exec.CommandContext(context.Background(), self, "__telemetry-send", f.Name()) //nolint:gosec // Start this binary as the detached telemetry sender.
	proc.Detach(cmd)
	if cmd.Start() != nil {
		_ = os.Remove(f.Name())
		return
	}
	go func() { _ = cmd.Wait() }()
}

// RunSender is the detached `telemetry-send` process: POST one job from stdin.
func RunSender() int {
	var job struct {
		URL     string          `json:"url"`
		Timeout float64         `json:"timeout"`
		Payload json.RawMessage `json:"payload"`
	}
	if len(os.Args) < 3 {
		return 0
	}
	raw, _ := os.ReadFile(os.Args[2])
	_ = os.Remove(os.Args[2])
	if json.Unmarshal(raw, &job) != nil {
		return 0
	}
	req, err := http.NewRequestWithContext(context.Background(), "POST", job.URL, bytes.NewReader(job.Payload))
	if err != nil {
		return 0
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "browser-harness")
	if resp, err := (&http.Client{Timeout: time.Duration(job.Timeout * float64(time.Second))}).Do(req); err == nil {
		_ = resp.Body.Close()
	}
	return 0
}

func indent(v any) []byte {
	raw, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return nil
	}
	return append(raw, '\n')
}

func compact(v any) []byte {
	raw, err := json.Marshal(v)
	if err != nil {
		return nil
	}
	return raw
}

func printJSON(v any) { _, _ = os.Stdout.Write(indent(v)) }
