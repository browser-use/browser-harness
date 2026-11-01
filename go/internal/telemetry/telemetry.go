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
	if os.WriteFile(p, indent(m), 0o600) == nil && runtime.GOOS != "windows" {
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

func base() map[string]any {
	v := os.Getenv("BH_VERSION")
	if v == "" {
		v = "unknown"
	}
	return map[string]any{"browser_harness_version": v, "python_version": os.Getenv("BH_PYTHON_VERSION"),
		"os": osName(), "machine": machine()}
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
	props := base()
	for k, v := range map[string]any{
		"$process_person_profile": true, "action": e.Action, "command": e.Command,
		"browser": strp(e.Browser), "cdp_url": cdpHostname(),
		"client": orNil(os.Getenv("BH_CLIENT")), "client_version": orNil(os.Getenv("BH_CLIENT_VERSION")),
		"agent_client": agentClient(), "model": orNil(os.Getenv("BROWSER_USE_AGENT_MODEL")),
		"model_provider": orNil(os.Getenv("BROWSER_USE_MODEL_PROVIDER")),
		"task":           task, "task_length": taskLen, "output": strp(e.Output),
		"output_length": intp(e.OutputLength), "steps": e.Steps, "step_count": intp(e.StepCount),
		"duration_seconds": e.Duration, "exit_code": e.ExitCode, "error_message": strp(e.Error),
	} {
		props[k] = v
	}
	send(map[string]any{"api_key": posthogKey, "distinct_id": installID(load(), true),
		"event": "cli_event", "properties": props})
}

// Capture sends an event with scrubbed properties.
func Capture(event string, props map[string]any) {
	if !Enabled() {
		return
	}
	all := base()
	all["$process_person_profile"] = false
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
			all[safe] = t
		default:
			s := fmt.Sprint(t)
			if strings.Contains(s, "://") {
				s = "[redacted]"
			}
			if r := []rune(s); len(r) > 120 {
				s = string(r[:120])
			}
			all[safe] = s
		}
	}
	send(map[string]any{"api_key": posthogKey, "distinct_id": installID(load(), true),
		"event": event, "properties": all})
}

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
	self, err := os.Executable()
	if err != nil {
		return
	}
	cmd := exec.Command(self, "telemetry-send")
	cmd.Stdin = bytes.NewReader(compact(job))
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

func indent(v any) []byte {
	raw, _ := json.MarshalIndent(v, "", "  ")
	return append(raw, '\n')
}

func compact(v any) []byte {
	raw, _ := json.Marshal(v)
	return raw
}

func printJSON(v any) { os.Stdout.Write(indent(v)) }
