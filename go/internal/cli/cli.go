// Package cli is the `browser-harness` command line: snippets on stdin plus subcommands.
package cli

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"golang.org/x/term"

	"github.com/browser-use/browser-harness/go/internal/admin"
	"github.com/browser-use/browser-harness/go/internal/assets"
	"github.com/browser-use/browser-harness/go/internal/auth"
	"github.com/browser-use/browser-harness/go/internal/jsrun"
	"github.com/browser-use/browser-harness/go/internal/recorder"
	"github.com/browser-use/browser-harness/go/internal/telemetry"
	"github.com/browser-use/browser-harness/go/internal/video"
)

const help = `Browser Harness

Read SKILL.md for the default workflow and examples.

Typical usage:
  browser-harness <<'JS'
  ensure_real_tab()
  print(page_info())
  JS

Snippets are JavaScript with the helpers as globals. The daemon auto-starts and connects to the running browser.

Commands:
  browser-harness --version        print the installed version
  browser-harness --doctor         diagnose install, daemon, and browser state
  browser-harness doctor           same as --doctor
  browser-harness doctor --json [--require-existing-daemon]
                                    print machine-readable runtime health
  browser-harness doctor --fix-snap   print how to fix Snap Chromium blocking CDP (Linux)
  browser-harness mac-approve         approve Chrome's macOS remote debugging sheet
  browser-harness auth login          sign in to Browser Use Cloud for cloud browsers
  browser-harness auth login --device-code   sign in from SSH/headless environments
  browser-harness auth status         show Browser Use Cloud auth state
  browser-harness auth logout         remove stored Browser Use Cloud auth
  browser-harness skill               print the browser-harness skill text
  browser-harness recordings          show recording status and recent sessions
  browser-harness recordings --latest   print the newest recording directory
  browser-harness recordings enable   save browser actions locally by default
  browser-harness recordings disable  stop saving browser actions by default
  browser-harness video init <recording>      prepare a recording for editing
  browser-harness video review <recording>    compile and review the video
  browser-harness video export <recording> --reviewed   export a verified MP4
  browser-harness telemetry status    show anonymous telemetry opt-out state
  browser-harness --reload         stop the daemon so next call picks up code changes
`

const usage = `Usage:
  browser-harness <<'JS'
  print(page_info())
  JS
`

type exit struct {
	code int
	msg  *string // printed to stderr
}

func telemetryCommand(args []string) string {
	if len(args) == 0 {
		return "script"
	}
	switch a := args[0]; a {
	case "-h", "--help":
		return "help"
	case "--version":
		return "version"
	case "--doctor", "doctor":
		return "doctor"
	case "--update":
		return "update"
	case "--reload":
		return "reload"
	case "--debug-clicks":
		return "debug-clicks"
	case "auth", "skill", "mac-approve", "recordings", "telemetry", "video":
		return a
	}
	return "usage"
}

// tail keeps the last limit bytes written plus the total rune count.
type tail struct {
	mu     sync.Mutex
	limit  int
	buf    []byte
	length int
}

func (t *tail) Write(p []byte) (int, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.length += len([]rune(string(p)))
	t.buf = append(t.buf, p...)
	if len(t.buf) > t.limit*4 {
		t.buf = t.buf[len(t.buf)-t.limit*4:]
	}
	return len(p), nil
}

func (t *tail) text() string {
	t.mu.Lock()
	defer t.mu.Unlock()
	r := []rune(string(t.buf))
	if len(r) > t.limit {
		r = r[len(r)-t.limit:]
	}
	return string(r)
}

// redirect tees an os.File (stdout/stderr) through a pipe into t.
func redirect(f **os.File, t *tail) func() {
	orig := *f
	r, w, err := os.Pipe()
	if err != nil {
		return func() {}
	}
	*f = w
	done := make(chan struct{})
	go func() {
		_, _ = io.Copy(io.MultiWriter(orig, t), r)
		close(done)
	}()
	return func() {
		w.Close()
		<-done
		*f = orig
	}
}

// Main runs the CLI and returns the process exit code.
func Main(args []string) int {
	if len(args) > 0 && args[0] == "telemetry" {
		return telemetry.RunCLI(args[1:])
	}
	start := time.Now()
	command := telemetryCommand(args)
	stdoutTail := &tail{limit: 20_000}
	stderrTail := &tail{limit: 500}
	restoreOut := redirect(&os.Stdout, stdoutTail)
	restoreErr := redirect(&os.Stderr, stderrTail)
	res := run(args)
	restoreOut()
	restoreErr()
	ev := telemetry.CLIEvent{Action: "completed", Command: command, Duration: time.Since(start).Seconds(), ExitCode: res.code}
	if res.task != nil {
		ev.Task = res.task
		if telemetry.Enabled() {
			if k := admin.DaemonBrowserKind(""); k != "" {
				ev.Browser = &k
			}
		}
	}
	if out := stdoutTail.text(); out != "" {
		ev.Output = &out
	}
	if stdoutTail.length > 0 {
		ev.OutputLength = &stdoutTail.length
	}
	if len(res.steps) > 0 {
		ev.Steps = res.steps
	}
	if res.stepCount > 0 {
		ev.StepCount = &res.stepCount
	}
	if res.code != 0 {
		ev.Action = "error"
		switch {
		case res.errMsg != nil:
			ev.Error = res.errMsg
		default:
			if t := strings.TrimSpace(stderrTail.text()); t != "" {
				ev.Error = &t
			}
		}
	}
	telemetry.CaptureCLIEvent(ev)
	return res.code
}

type result struct {
	code      int
	errMsg    *string
	task      *string
	steps     []any
	stepCount int
}

func done(code int) result { return result{code: code} }

func fail(msg string) result {
	fmt.Fprintln(os.Stderr, msg)
	return result{code: 1, errMsg: &msg}
}

func run(args []string) result {
	first := ""
	if len(args) > 0 {
		first = args[0]
	}
	switch first {
	case "-h", "--help":
		fmt.Print(help + "\n")
		return done(0)
	case "--version":
		fmt.Println(admin.Version())
		return done(0)
	case "--doctor":
		return done(admin.Doctor())
	case "doctor":
		return done(doctor(args[1:]))
	case "auth":
		return done(Auth(args[1:]))
	case "mac-approve":
		return done(admin.MacApprove(args[1:]))
	case "skill":
		if len(args) != 1 {
			fmt.Fprintln(os.Stderr, "usage: browser-harness skill")
			return done(2)
		}
		fmt.Print(assets.Skill)
		return done(0)
	case "recordings":
		return done(recordings(args[1:]))
	case "video":
		return done(video.CLI(args[1:]))
	case "--reload":
		_ = admin.RestartDaemon("", false)
		fmt.Println("daemon stopped — will restart fresh on next call")
		return done(0)
	}
	if first == "--debug-clicks" {
		os.Setenv("BH_DEBUG_CLICKS", "1")
		args = args[1:]
	}
	if len(args) > 0 || term.IsTerminal(int(os.Stdin.Fd())) {
		return usageExit()
	}
	raw, _ := io.ReadAll(os.Stdin)
	code := string(raw)
	if strings.TrimSpace(code) == "" {
		r := usageExit()
		r.task = &code
		return r
	}
	return runSnippet(code)
}

// usageExit mirrors sys.exit(USAGE): the text plus a newline on stderr, exit 1.
func usageExit() result {
	fmt.Fprint(os.Stderr, usage+"\n")
	m := usage
	return result{code: 1, errMsg: &m}
}

func doctor(rest []string) int {
	if len(rest) == 1 && rest[0] == "--fix-snap" {
		return admin.DoctorFixSnap()
	}
	seen := map[string]bool{}
	ok := len(rest) > 0
	for _, a := range rest {
		if (a != "--json" && a != "--require-existing-daemon") || seen[a] {
			ok = false
		}
		seen[a] = true
	}
	if ok && seen["--json"] {
		return admin.DoctorJSON(seen["--require-existing-daemon"])
	}
	if len(rest) > 0 {
		fmt.Fprintln(os.Stderr, "usage: browser-harness doctor [--fix-snap|--json [--require-existing-daemon]]")
		return 2
	}
	return admin.Doctor()
}

func recordings(rest []string) int {
	e := recorder.FromProcess()
	switch strings.Join(rest, " ") {
	case "--latest":
		l := recorder.Latest()
		if l == "" {
			fmt.Fprintln(os.Stderr, "no recordings found")
			return 1
		}
		fmt.Println(l)
		return 0
	case "enable", "disable":
		on := rest[0] == "enable"
		if err := recorder.SetAuto(e, on); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		state := "disabled"
		if on {
			state = "enabled"
		}
		fmt.Printf("auto-recording preference %s\n", state)
		return 0
	case "":
	default:
		fmt.Fprintln(os.Stderr, "usage: browser-harness recordings [--latest|enable|disable]")
		return 2
	}
	on, source := recorder.AutoSetting(e)
	state := "off"
	if on {
		state = "on"
	}
	fmt.Printf("auto-recording: %s (%s)\n", state, source)
	active := recorder.Dir(e)
	if active == "" {
		active = "none"
	}
	fmt.Printf("active: %s\n", active)
	latest := "none"
	if all := recorder.All(); len(all) > 0 {
		latest = all[0]
	}
	fmt.Printf("latest: %s\n", latest)
	return 0
}

// localChromeListening probes /json/version so an unrelated listener on
// 9222/9223 does not masquerade as Chrome and skip the cloud bootstrap.
func localChromeListening() bool {
	c := &http.Client{Timeout: 300 * time.Millisecond}
	for _, p := range []int{9222, 9223} {
		resp, err := c.Get(fmt.Sprintf("http://127.0.0.1:%d/json/version", p))
		if err != nil {
			continue
		}
		var v map[string]any
		err = json.NewDecoder(resp.Body).Decode(&v)
		resp.Body.Close()
		if s, ok := v["webSocketDebuggerUrl"].(string); err == nil && ok && s != "" {
			return true
		}
	}
	return false
}

func cloudAuthConfigured() bool {
	_, err := auth.APIKey()
	return err == nil
}

func runSnippet(code string) result {
	trimmed := strings.TrimLeft(code, " \t\r\n\f\v")
	cloudAdmin := strings.HasPrefix(trimmed, "start_remote_daemon(") || strings.HasPrefix(trimmed, "stop_remote_daemon(")
	if !cloudAdmin {
		var err error
		if os.Getenv("BH_REQUIRE_EXISTING_DAEMON") == "1" {
			err = admin.RequireExistingDaemon("")
		} else {
			// Cloud auto-bootstrap is opt-in (BU_AUTOSPAWN); an explicit CDP endpoint blocks it.
			if !admin.DaemonAlive("") && !localChromeListening() && os.Getenv("BU_CDP_URL") == "" &&
				os.Getenv("BU_CDP_WS") == "" && cloudAuthConfigured() && os.Getenv("BU_AUTOSPAWN") != "" {
				if _, err = admin.StartRemoteDaemon(admin.Name(), "", nil); err != nil {
					r := fail("browser-harness: " + err.Error())
					r.task = &code
					return r
				}
			}
			err = admin.EnsureDaemon(-1, "", nil)
		}
		if err != nil {
			r := fail("browser-harness: " + err.Error())
			r.task = &code
			return r
		}
	}
	r := runJS(code)
	r.task = &code
	return r
}

// runJS executes the snippet in-process and collects its helper trace.
func runJS(code string) result {
	trace, err := jsrun.Run(code, os.Stdout)
	r := result{steps: trace.Steps, stepCount: trace.StepCount}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		msg := err.Error()
		r.code, r.errMsg = 1, &msg
	}
	return r
}
