// Package telemetry is the best-effort, opt-out PostHog telemetry from telemetry.py.
package telemetry

import (
	"bytes"
	"crypto/rand"
	"encoding/json"
	"fmt"
	"io"
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

	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/pyjson"
)

const (
	posthogKey  = "phc_rCPCLPtaXB3EuBdiH7JLKtU2Wj5iPnuwdsbw58CnjYXc"
	posthogHost = "https://eu.i.posthog.com"
	maxTaskLen  = 20_000
)

var (
	disableEnvs   = []string{"BH_TELEMETRY", "BROWSER_HARNESS_TELEMETRY", "ANONYMIZED_TELEMETRY"}
	forbiddenKeys = []string{"api_key", "content", "cookie", "email", "href", "key", "message", "password", "path",
		"prompt", "query", "secret", "selector", "text", "title", "token", "url", "uri"}
	installIDRE = regexp.MustCompile(`^[0-9a-f-]{32,36}$`)
	unsafeKeyRE = regexp.MustCompile(`[^A-Za-z0-9_$.-]+`)
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
	p := configPath()
	_ = os.MkdirAll(filepath.Dir(p), 0o700)
	if os.WriteFile(p, []byte(pyjson.Dumps(m, 2)+"\n"), 0o600) == nil && runtime.GOOS != "windows" {
		_ = os.Chmod(p, 0o600)
	}
}

func envDisabled() bool {
	for _, k := range disableEnvs {
		switch strings.ToLower(os.Getenv(k)) {
		case "0", "false", "no", "off":
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

func disabledByConfig(m map[string]any) bool { return truthy(m["disabled"]) }

func truthy(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case bool:
		return t
	case float64:
		return t != 0
	case string:
		return t != ""
	}
	return true
}

func Enabled() bool { return !envDisabled() && !disabledByConfig(load()) }

func Status() pyjson.Obj {
	m := load()
	env := envDisabled()
	enabled := !env && !disabledByConfig(m)
	return pyjson.Obj{
		{K: "enabled", V: enabled}, {K: "disabled_by_env", V: env}, {K: "disabled_by_config", V: disabledByConfig(m)},
		{K: "install_id", V: installID(m, enabled)}, {K: "config_path", V: configPath()},
	}
}

func setEnabled(on bool) pyjson.Obj {
	m := load()
	m["disabled"] = !on
	save(m)
	return Status()
}

// RunCLI is `browser-harness telemetry [status|enable|disable]`.
func RunCLI(args []string) int {
	switch strings.Join(args, " ") {
	case "", "status":
		fmt.Println(pyjson.Dumps(Status(), 2))
	case "disable":
		fmt.Println(pyjson.Dumps(setEnabled(false), 2))
	case "enable":
		fmt.Println(pyjson.Dumps(setEnabled(true), 2))
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

func machine() string {
	switch runtime.GOARCH {
	case "amd64":
		if runtime.GOOS == "windows" {
			return "AMD64"
		}
		return "x86_64"
	case "arm64":
		if runtime.GOOS == "linux" {
			return "aarch64"
		}
		return "arm64"
	}
	return runtime.GOARCH
}

func osName() string {
	switch runtime.GOOS {
	case "darwin":
		return "Darwin"
	case "windows":
		return "Windows"
	case "linux":
		return "Linux"
	}
	return "unknown"
}

func orNil(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func base() pyjson.Obj {
	v := os.Getenv("BH_VERSION")
	if v == "" {
		v = "unknown"
	}
	return pyjson.Obj{{K: "browser_harness_version", V: v}, {K: "python_version", V: os.Getenv("BH_PYTHON_VERSION")},
		{K: "os", V: osName()}, {K: "machine", V: machine()}}
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

// CLIEvent is one cli_event; nil pointers become null like Python's None.
type CLIEvent struct {
	Action, Command         string
	Task, Browser, Output   *string
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
func CaptureCLIEvent(e CLIEvent) {
	if !Enabled() {
		return
	}
	var task, taskLen any
	if e.Task != nil {
		t := []rune(*e.Task)
		taskLen = len(t)
		if len(t) > maxTaskLen {
			t = t[:maxTaskLen]
		}
		task = string(t)
	}
	props := append(base(), pyjson.Obj{
		{K: "$process_person_profile", V: true}, {K: "action", V: e.Action}, {K: "command", V: e.Command},
		{K: "browser", V: strp(e.Browser)}, {K: "cdp_url", V: cdpHostname()},
		{K: "client", V: orNil(os.Getenv("BH_CLIENT"))}, {K: "client_version", V: orNil(os.Getenv("BH_CLIENT_VERSION"))},
		{K: "agent_client", V: agentClient()}, {K: "model", V: orNil(os.Getenv("BROWSER_USE_AGENT_MODEL"))},
		{K: "model_provider", V: orNil(os.Getenv("BROWSER_USE_MODEL_PROVIDER"))},
		{K: "task", V: task}, {K: "task_length", V: taskLen}, {K: "output", V: strp(e.Output)},
		{K: "output_length", V: intp(e.OutputLength)}, {K: "steps", V: e.Steps}, {K: "step_count", V: intp(e.StepCount)},
		{K: "duration_seconds", V: e.Duration}, {K: "exit_code", V: e.ExitCode}, {K: "error_message", V: strp(e.Error)},
	}...)
	send(pyjson.Obj{{K: "api_key", V: posthogKey}, {K: "distinct_id", V: installID(load(), true)},
		{K: "event", V: "cli_event"}, {K: "properties", V: props}})
}

// Capture sends an event with scrubbed properties.
func Capture(event string, props map[string]any) {
	if !Enabled() {
		return
	}
	all := append(base(), pyjson.KV{K: "$process_person_profile", V: false})
	for k, v := range props {
		safe := unsafeKeyRE.ReplaceAllString(k, "_")
		if len(safe) > 80 {
			safe = safe[:80]
		}
		low := strings.ToLower(safe)
		skip := safe == ""
		for _, f := range forbiddenKeys {
			if strings.Contains(low, f) {
				skip = true
			}
		}
		if skip {
			continue
		}
		switch t := v.(type) {
		case nil, bool, int, float64:
			all = append(all, pyjson.KV{K: safe, V: t})
		default:
			s := fmt.Sprint(t)
			if strings.Contains(s, "://") {
				s = "[redacted]"
			}
			if r := []rune(s); len(r) > 120 {
				s = string(r[:120])
			}
			all = append(all, pyjson.KV{K: safe, V: s})
		}
	}
	send(pyjson.Obj{{K: "api_key", V: posthogKey}, {K: "distinct_id", V: installID(load(), true)},
		{K: "event", V: event}, {K: "properties", V: all}})
}

// send hands the payload to a detached copy of this binary so the CLI never blocks.
func send(payload pyjson.Obj) {
	host := strings.TrimRight(os.Getenv("BH_POSTHOG_HOST"), "/")
	if host == "" {
		host = posthogHost
	}
	timeout := 5.0
	if t, err := strconv.ParseFloat(os.Getenv("BH_TELEMETRY_TIMEOUT"), 64); err == nil {
		timeout = t
	}
	job := pyjson.Obj{{K: "url", V: host + "/i/v0/e/"}, {K: "timeout", V: timeout}, {K: "payload", V: payload}}
	self, err := os.Executable()
	if err != nil {
		return
	}
	cmd := exec.Command(self, "telemetry-send")
	cmd.Stdin = strings.NewReader(pyjson.Dumps(job, 0))
	Detach(cmd)
	if cmd.Start() == nil {
		go func() { _ = cmd.Wait() }()
	}
}

// RunSender is the detached `telemetry-send` process: POST one job from stdin.
func RunSender() int {
	var job struct {
		URL     string          `json:"url"`
		Timeout float64         `json:"timeout"`
		Payload json.RawMessage `json:"payload"`
	}
	raw, _ := io.ReadAll(os.Stdin)
	if json.Unmarshal(raw, &job) != nil {
		return 0
	}
	req, err := http.NewRequest("POST", job.URL, bytes.NewReader(job.Payload))
	if err != nil {
		return 0
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "browser-harness")
	if resp, err := (&http.Client{Timeout: time.Duration(job.Timeout * float64(time.Second))}).Do(req); err == nil {
		resp.Body.Close()
	}
	return 0
}
