package admin

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/auth"
	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/pyjson"
)

const (
	pypiJSON      = "https://pypi.org/pypi/browser-harness/json"
	versionTTL    = 24 * time.Hour
	doctorTextMax = 140
	snapDoc       = "https://github.com/browser-use/browser-harness/blob/main/docs/snap-linux-headless.md"
)

// Version is the installed browser-harness version, as reported by the Python package.
func Version() string { return os.Getenv("BH_VERSION") }

// RepoDir is set by the Python package when it runs from an editable git clone.
func RepoDir() string { return os.Getenv("BH_REPO_ROOT") }

func InstallMode() string {
	if RepoDir() != "" {
		return "git"
	}
	if Version() != "" {
		return "pypi"
	}
	return "unknown"
}

func cachePath() string { return filepath.Join(paths.ConfigDir(), "version-cache.json") }

func cacheRead() map[string]any {
	m := map[string]any{}
	if raw, err := os.ReadFile(cachePath()); err == nil {
		_ = json.Unmarshal(raw, &m)
	}
	if m == nil {
		m = map[string]any{}
	}
	return m
}

func cacheWrite(m map[string]any) {
	b, _ := json.Marshal(m)
	_ = os.MkdirAll(filepath.Dir(cachePath()), 0o700)
	if os.WriteFile(cachePath(), b, 0o600) == nil {
		_ = os.Chmod(cachePath(), 0o600)
	}
}

// latestReleaseTag returns the latest PyPI version, cached for 24 h.
func latestReleaseTag(force bool) string {
	c := cacheRead()
	tag, _ := c["tag"].(string)
	fetched, _ := c["fetched_at"].(float64)
	now := float64(time.Now().UnixNano()) / 1e9
	if !force && tag != "" && now-fetched < versionTTL.Seconds() {
		return tag
	}
	resp, err := (&http.Client{Timeout: 5 * time.Second}).Get(pypiJSON)
	if err != nil {
		return tag
	}
	defer resp.Body.Close()
	var v struct {
		Info struct {
			Version string `json:"version"`
		} `json:"info"`
	}
	if resp.StatusCode >= 400 || json.NewDecoder(resp.Body).Decode(&v) != nil {
		return tag
	}
	newTag := strings.TrimLeft(v.Info.Version, "v")
	c["tag"], c["fetched_at"] = newTag, now
	cacheWrite(c)
	return newTag
}

var versionRE = regexp.MustCompile(`(?i)^\s*v?(\d+(?:\.\d+)*)(?:(a|b|rc)(\d+))?`)

// versionKey is a best-effort PEP 440 order: alpha < beta < rc < final.
func versionKey(v string) [5]int {
	m := versionRE.FindStringSubmatch(v)
	if m == nil {
		return [5]int{0, 0, 0, 3, 0}
	}
	var k [5]int
	for i, p := range strings.Split(m[1], ".") {
		if i == 3 {
			break
		}
		k[i], _ = strconv.Atoi(p)
	}
	k[3] = map[string]int{"a": 0, "b": 1, "rc": 2}[strings.ToLower(m[2])]
	if m[2] == "" {
		k[3] = 3
	}
	k[4], _ = strconv.Atoi(m[3])
	return k
}

func newer(latest, cur string) bool {
	if cur == "" || latest == "" {
		return false
	}
	a, b := versionKey(latest), versionKey(cur)
	for i := range a {
		if a[i] != b[i] {
			return a[i] > b[i]
		}
	}
	return false
}

func CheckForUpdate() (string, string, bool) {
	cur, latest := Version(), latestReleaseTag(false)
	return cur, latest, newer(latest, cur)
}

// PrintUpdateBanner prints to stderr at most once per day.
func PrintUpdateBanner() {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("BH_UPDATE_CHECK"))) {
	case "0", "false", "no", "off":
		return
	}
	c := cacheRead()
	today := time.Now().Format("2006-01-02")
	if c["banner_shown_on"] == today {
		return
	}
	cur, latest, isNewer := CheckForUpdate()
	if !isNewer {
		return
	}
	fmt.Fprintf(os.Stderr, "[browser-harness] update available: %s -> %s\n", cur, latest)
	fmt.Fprintln(os.Stderr, "[browser-harness] agents: run `browser-harness --update -y` to upgrade and restart the daemon")
	c = cacheRead()
	c["banner_shown_on"] = today
	cacheWrite(c)
}

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
	var status, source string
	for _, kv := range auth.Status() {
		if s, ok := kv.V.(string); ok {
			switch kv.K {
			case "status":
				status = s
			case "source":
				source = s
			}
		}
	}
	cloud := status == "authenticated"
	latest := latestReleaseTag(false)
	isNewer := newer(latest, cur)
	disp := cur
	if disp == "" {
		disp = "(unknown)"
	}
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
	fmt.Printf("  python            %s\n", os.Getenv("BH_PYTHON_VERSION"))
	fmt.Printf("  version           %s (%s)\n", disp, InstallMode())
	if latest != "" {
		suffix := ""
		if isNewer {
			suffix = " (update available)"
		}
		fmt.Printf("  latest release    %s%s\n", latest, suffix)
	} else {
		fmt.Println("  latest release    (could not reach PyPI)")
	}
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
	var ver any
	if v := Version(); v != "" {
		ver = v
	}
	fmt.Println(pyjson.Dumps(map[string]any{
		"schema_version": 1, "healthy": ok, "require_existing_daemon": strict, "version": ver,
		"install_mode": InstallMode(), "chrome_running": chrome,
		"daemon": map[string]any{"name": Name(), "alive": up, "browser_ready": ready},
	}, 0)) // plain maps render with sorted keys, matching sort_keys=True
	if ok {
		return 0
	}
	return 1
}

func promptYes(q string, defYes, yes bool) bool {
	if yes {
		return true
	}
	suffix := "[y/N]"
	if defYes {
		suffix = "[Y/n]"
	}
	fmt.Printf("%s %s ", q, suffix)
	line, err := bufio.NewReader(os.Stdin).ReadString('\n')
	if err != nil && line == "" {
		return defYes
	}
	ans := strings.ToLower(strings.TrimSpace(line))
	if ans == "" {
		return defYes
	}
	return strings.HasPrefix(ans, "y")
}

// uvManages is true when `uv tool list` owns browser-harness; unknown counts as managed.
func uvManages() bool {
	out, err := exec.Command("uv", "tool", "list").Output()
	if err != nil {
		return true
	}
	for _, line := range strings.Split(string(out), "\n") {
		e := strings.TrimSpace(line)
		if strings.HasPrefix(e, "-") {
			continue
		}
		if strings.SplitN(e, " ", 2)[0] == "browser-harness" {
			return true
		}
	}
	return false
}

func runPassthrough(name string, args ...string) int {
	cmd := exec.Command(name, args...)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := cmd.Run(); err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			return ee.ExitCode()
		}
		return 1
	}
	return 0
}

// Update pulls the latest version and offers to recycle the daemon.
func Update(yes bool) int {
	cur, latest, isNewer := CheckForUpdate()
	switch {
	case cur != "" && latest != "" && !isNewer:
		fmt.Printf("browser-harness is up to date (%s).\n", cur)
		return 0
	case cur != "" && latest != "":
		fmt.Printf("updating browser-harness: %s -> %s\n", cur, latest)
	case latest != "":
		fmt.Printf("installed version unknown; will try to update to %s.\n", latest)
	default:
		fmt.Println("could not reach PyPI; will try to update anyway.")
	}
	switch InstallMode() {
	case "git":
		repo := RepoDir()
		out, err := exec.Command("git", "-C", repo, "status", "--porcelain").CombinedOutput()
		if err != nil {
			fmt.Fprintf(os.Stderr, "git status failed: %s\n", strings.TrimSpace(string(out)))
			return 1
		}
		if strings.TrimSpace(string(out)) != "" {
			fmt.Fprintf(os.Stderr, "refusing to update: uncommitted changes in %s\n", repo)
			fmt.Fprintf(os.Stderr, "commit or stash them first, or run `git -C %s pull` yourself.\n", repo)
			return 1
		}
		if rc := runPassthrough("git", "-C", repo, "pull", "--ff-only"); rc != 0 {
			return rc
		}
	case "pypi":
		if rc := runPassthrough("uv", "tool", "upgrade", "browser-harness"); rc != 0 {
			if !uvManages() {
				fmt.Fprintln(os.Stderr, "if you installed with pip or pipx, upgrade with: uv tool install --python 3.12 --upgrade --force browser-harness")
			}
			return rc
		}
	default:
		fmt.Fprintln(os.Stderr, "unknown install mode; can't auto-update.")
		return 1
	}
	c := cacheRead()
	delete(c, "banner_shown_on")
	cacheWrite(c)
	if DaemonAlive("") {
		if promptYes("restart the running daemon so it picks up the new code?", true, yes) {
			_ = RestartDaemon("", false)
			fmt.Println("daemon stopped; it will auto-restart on next `browser-harness` call.")
		} else {
			fmt.Println("daemon left running on old code. run `browser-harness` and it'll use the new code after the daemon recycles.")
		}
	}
	fmt.Println("update complete.")
	return 0
}
