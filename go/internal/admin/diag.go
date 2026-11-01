package admin

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"

	"github.com/browser-use/browser-harness/go/internal/auth"
	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/version"
)

const (
	doctorTextMax = 140
	snapDoc       = "https://github.com/browser-use/browser-harness/blob/main/docs/snap-linux-headless.md"
)

// Version is the build version ("dev" for local builds).
func Version() string { return version.Version }

// InstallMode is "git" when running from a source checkout, else "release".
func InstallMode() string {
	if paths.RepoRoot() != "" {
		return "git"
	}
	return "release"
}

var versionRE = regexp.MustCompile(`(?i)^\s*v?(\d+(?:\.\d+)*)(?:(a|b|rc)(\d+))?`)

func shortText(s string) string {
	r := []rune(s)
	if len(r) <= doctorTextMax {
		return s
	}
	return string(r[:doctorTextMax-3]) + "..."
}

func isSnap(p string) bool { return p != "" && strings.Contains(strings.ToLower(p), "/snap/") }

func snapProbePath(p string) string {
	if isSnap(p) {
		return p
	}
	if r, err := filepath.EvalSymlinks(p); err == nil {
		return r
	}
	return p
}

func probeChromeForSnap() (string, string) {
	for _, key := range []string{"BH_CHROME_PATH", "CHROME_PATH"} {
		raw := strings.TrimSpace(os.Getenv(key))
		if raw == "" {
			continue
		}
		if fi, err := os.Stat(raw); err == nil && !fi.IsDir() {
			return filepath.Base(raw), snapProbePath(raw)
		}
	}
	for _, c := range []string{"google-chrome-stable", "google-chrome", "chromium-browser", "chromium"} {
		if p, err := exec.LookPath(c); err == nil {
			return c, snapProbePath(p)
		}
	}
	return "", ""
}

func DoctorFixSnap() int {
	fmt.Print(`browser-harness doctor --fix-snap

Snap-packaged Chromium cannot expose DevTools the way browser-harness needs.
Full background: ` + snapDoc + `

1. Install Google Chrome from Google's .deb (not the Snap store):
   wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
   sudo apt install ./google-chrome-stable_current_amd64.deb

2. Point the harness (and your shell) at the native binary so PATH does not
   pick the Snap wrapper first. Example for bash (~/.bashrc or session env):
   export BH_CHROME_PATH=/usr/bin/google-chrome-stable
   # CHROME_PATH is also honored by doctor's snap probe if you prefer that name.

3. Launch Chrome from that path (Way 2) or open Chrome normally (Way 1),
   enable remote debugging per install.md, then verify:
   browser-harness --doctor

`)
	return 0
}

func osRelease() string {
	if runtime.GOOS == "windows" {
		return ""
	}
	out, err := exec.Command("uname", "-r").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

func platformName() string {
	switch runtime.GOOS {
	case "darwin":
		return "Darwin"
	case "windows":
		return "Windows"
	case "linux":
		return "Linux"
	}
	return runtime.GOOS
}

// Doctor prints read-only diagnostics; 0 iff Chrome and the daemon are healthy.
func Doctor() int {
	cur := Version()
	chrome := chromeRunning()
	daemonUp := DaemonAlive("")
	conns := BrowserConnections()
	st, err := auth.Status()
	status, source := st.Status, st.Source
	if err != nil {
		status, source = "error", err.Error()
	}
	cloud := status == "authenticated"
	row := func(label string, ok bool, detail string) {
		mark := "ok  "
		if !ok {
			mark = "FAIL"
		}
		if detail != "" {
			detail = " — " + detail
		}
		fmt.Printf("  [%s] %s%s\n", mark, label, detail)
	}
	fmt.Println("browser-harness doctor")
	fmt.Printf("  platform          %s %s\n", platformName(), osRelease())
	fmt.Printf("  version           %s (%s)\n", cur, InstallMode())
	if runtime.GOOS == "linux" {
		if name, p := probeChromeForSnap(); name != "" && isSnap(p) {
			fmt.Println("[snap-detect]")
			fmt.Printf("Browser: %s (snap) — WARNING: Snap confinement prevents CDP binding.\n", name)
			fmt.Println("  Fix: Install Chrome natively (see docs/snap-linux-headless.md)")
			fmt.Printf("  Docs: %s\n", snapDoc)
		}
	}
	row("chrome running", chrome, map[bool]string{true: "", false: "start chrome/edge"}[chrome])
	row("daemon alive", daemonUp, map[bool]string{true: "", false: "see install.md"}[daemonUp])
	row("active browser connections", len(conns) > 0, strconv.Itoa(len(conns)))
	for _, c := range conns {
		if c.Page != nil {
			fmt.Printf("        %s — active page: %s — %s\n", c.Name, shortText(c.Page["title"]), shortText(c.Page["url"]))
		} else {
			fmt.Printf("        %s — active page: (no real page)\n", c.Name)
		}
	}
	detail := "optional: browser-harness auth login"
	if source != "" {
		detail = source
	}
	row("Browser Use cloud auth", cloud, detail)
	if chrome && daemonUp {
		return 0
	}
	return 1
}

// DoctorJSON is the stable, non-networked health report for orchestrators.
func DoctorJSON(strict bool) int {
	var chrome any
	if !strict {
		chrome = chromeRunning()
	}
	ready := DaemonBrowserReady("")
	up := ready || DaemonAlive("")
	ok := ready || (chrome == true && up)
	if strict {
		ok = up && ready
	}
	raw, _ := json.Marshal(map[string]any{
		"schema_version": 1, "healthy": ok, "require_existing_daemon": strict, "version": Version(),
		"install_mode": InstallMode(), "chrome_running": chrome,
		"daemon": map[string]any{"name": Name(), "alive": up, "browser_ready": ready},
	})
	fmt.Println(string(raw))
	if ok {
		return 0
	}
	return 1
}
