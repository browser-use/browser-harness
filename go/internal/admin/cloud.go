package admin

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"runtime"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/auth"
	"github.com/browser-use/browser-harness/go/internal/daemon"
)

// HTTPError mirrors urllib's HTTPError text, which callers and agents see.
type HTTPError struct {
	Code   int
	Reason string
}

func (e *HTTPError) Error() string { return fmt.Sprintf("HTTP Error %d: %s", e.Code, e.Reason) }

func browserUse(path, method string, body any) (any, error) {
	key, err := auth.APIKey()
	if err != nil {
		return nil, err
	}
	var rd io.Reader
	if body != nil {
		b, _ := json.Marshal(body)
		rd = bytes.NewReader(b)
	}
	req, _ := http.NewRequest(method, daemon.BUAPI+path, rd)
	req.Header.Set("X-Browser-Use-API-Key", key)
	req.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: 60 * time.Second}).Do(req)
	if err != nil {
		return nil, fmt.Errorf("<urlopen error %v>", err)
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, &HTTPError{Code: resp.StatusCode, Reason: http.StatusText(resp.StatusCode)}
	}
	if len(bytes.TrimSpace(data)) == 0 {
		return map[string]any{}, nil
	}
	var out any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func stopCloudBrowser(id string, strict bool) error {
	if id == "" {
		return nil
	}
	var last error
	for attempt := 0; attempt < 3; attempt++ {
		if _, last = browserUse("/browsers/"+id, "PATCH", map[string]any{"action": "stop"}); last == nil {
			return nil
		}
		if attempt < 2 {
			time.Sleep(time.Duration(attempt+1) * 500 * time.Millisecond)
		}
	}
	if strict {
		return fmt.Errorf("failed to stop remote browser %s: %v", id, last)
	}
	return nil
}

func cdpWSFromURL(cdpURL string) (string, error) {
	resp, err := (&http.Client{Timeout: 15 * time.Second}).Get(cdpURL + "/json/version")
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return "", &HTTPError{Code: resp.StatusCode, Reason: http.StatusText(resp.StatusCode)}
	}
	var v struct {
		WS string `json:"webSocketDebuggerUrl"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&v); err != nil {
		return "", err
	}
	if v.WS == "" {
		return "", errors.New("'webSocketDebuggerUrl'")
	}
	return v.WS, nil
}

func hasLocalGUI() bool {
	switch runtime.GOOS {
	case "darwin", "windows":
		return true
	case "linux":
		return os.Getenv("DISPLAY") != "" || os.Getenv("WAYLAND_DISPLAY") != ""
	}
	return false
}

// showLiveURL prints the liveUrl to stdout and opens it when a GUI exists.
func showLiveURL(u string) {
	if u == "" {
		return
	}
	fmt.Println(u)
	if !hasLocalGUI() {
		fmt.Fprintln(os.Stderr, "(no local GUI — share the liveUrl with the user)")
		return
	}
	if err := auth.Opener(u); err != nil {
		fmt.Fprintf(os.Stderr, "(couldn't auto-open: %v — share the liveUrl with the user)\n", err)
		return
	}
	fmt.Fprintln(os.Stderr, "(opened liveUrl in your default browser)")
}

func shouldShowLiveView() (bool, error) {
	raw, set := os.LookupEnv("BH_OPEN_LIVE_URL")
	if !set {
		return true, nil
	}
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "0", "false", "no", "off":
		return false, nil
	case "1", "true", "yes", "on":
		return true, nil
	}
	return false, errors.New("BH_OPEN_LIVE_URL must be one of: 1, true, yes, on, 0, false, no, off")
}

// ListCloudProfiles pages through every profile (API pageSize cap is 100).
func ListCloudProfiles() ([]map[string]any, error) {
	out := []map[string]any{}
	for page := 1; ; page++ {
		listing, err := browserUse(fmt.Sprintf("/profiles?pageSize=100&pageNumber=%d", page), "GET", nil)
		if err != nil {
			return nil, err
		}
		var items []any
		total := -1
		switch l := listing.(type) {
		case map[string]any:
			items, _ = l["items"].([]any)
			if t, ok := l["totalItems"].(float64); ok {
				total = int(t)
			}
		case []any:
			items = l
		}
		if len(items) == 0 {
			break
		}
		for _, it := range items {
			p, _ := it.(map[string]any)
			id, _ := p["id"].(string)
			detail, err := browserUse("/profiles/"+id, "GET", nil)
			if err != nil {
				return nil, err
			}
			dm, _ := detail.(map[string]any)
			domains := dm["cookieDomains"]
			if domains == nil {
				domains = []any{}
			}
			out = append(out, map[string]any{
				"id": dm["id"], "name": dm["name"], "userId": dm["userId"],
				"cookieDomains": domains, "lastUsedAt": dm["lastUsedAt"],
			})
		}
		if _, isMap := listing.(map[string]any); isMap && (total < 0 || len(out) >= total) {
			break
		}
	}
	return out, nil
}

func resolveProfileName(name string) (string, error) {
	all, err := ListCloudProfiles()
	if err != nil {
		return "", err
	}
	var ids []string
	for _, p := range all {
		if p["name"] == name {
			id, _ := p["id"].(string)
			ids = append(ids, id)
		}
	}
	switch len(ids) {
	case 0:
		return "", fmt.Errorf("no cloud profile named %s -- call list_cloud_profiles() or sync_local_profile() first", pyQuote(name))
	case 1:
		return ids[0], nil
	}
	return "", fmt.Errorf("%d cloud profiles named %s -- pass profileId=<uuid> instead", len(ids), pyQuote(name))
}

// StartRemoteDaemon provisions a cloud browser and starts a daemon attached to it;
// when the daemon fails to start, the billable browser is stopped again.
func StartRemoteDaemon(name, profileName string, create map[string]any) (map[string]any, error) {
	if name == "" {
		name = "remote"
	}
	show, err := shouldShowLiveView()
	if err != nil {
		return nil, err
	}
	if DaemonAlive(name) {
		return nil, fmt.Errorf("daemon %s already alive -- restart_daemon(%s) first", pyQuote(name), pyQuote(name))
	}
	if create == nil {
		create = map[string]any{}
	}
	if profileName != "" {
		if _, both := create["profileId"]; both {
			return nil, errors.New("pass profileName OR profileId, not both")
		}
		id, err := resolveProfileName(profileName)
		if err != nil {
			return nil, err
		}
		create["profileId"] = id
	}
	raw, err := browserUse("/browsers", "POST", create)
	if err != nil {
		return nil, err
	}
	b, _ := raw.(map[string]any)
	id, _ := b["id"].(string)
	cdpURL, _ := b["cdpUrl"].(string)
	startErr := func() error {
		ws, err := cdpWSFromURL(cdpURL)
		if err != nil {
			return err
		}
		return EnsureDaemon(-1, name, map[string]string{"BU_CDP_WS": ws, "BU_BROWSER_ID": id})
	}()
	if startErr != nil {
		if cerr := stopCloudBrowser(id, true); cerr != nil {
			return nil, fmt.Errorf("remote daemon startup and cloud browser cleanup both failed (2 sub-exceptions): %v; %v", startErr, cerr)
		}
		return nil, startErr
	}
	if show {
		live, _ := b["liveUrl"].(string)
		showLiveURL(live)
	}
	return b, nil
}

const profileUseMissing = "profile-use not installed -- curl -fsSL https://browser-use.com/profile.sh | sh"

func ListLocalProfiles() (any, error) {
	p, err := exec.LookPath("profile-use")
	if err != nil {
		return nil, errors.New(profileUseMissing)
	}
	out, err := exec.Command(p, "list", "--json").Output()
	if err != nil {
		return nil, fmt.Errorf("Command '['profile-use', 'list', '--json']' returned non-zero exit status: %v", err)
	}
	var v any
	return v, json.Unmarshal(out, &v)
}

var createdRE = regexp.MustCompile(`Profile created:\s+([0-9a-f-]{36})`)

// SyncLocalProfile shells out to `profile-use sync` and returns the cloud UUID.
func SyncLocalProfile(profile, browserName, cloudID string, include, exclude []string) (string, error) {
	p, err := exec.LookPath("profile-use")
	if err != nil {
		return "", errors.New(profileUseMissing)
	}
	key, err := auth.APIKey()
	if err != nil {
		return "", err
	}
	args := []string{"sync", "--profile", profile}
	if browserName != "" {
		args = append(args, "--browser", browserName)
	}
	if cloudID != "" {
		args = append(args, "--cloud-profile-id", cloudID)
	}
	for _, d := range include {
		args = append(args, "--domain", d)
	}
	for _, d := range exclude {
		args = append(args, "--exclude-domain", d)
	}
	cmd := exec.Command(p, args...)
	cmd.Env = append(os.Environ(), "BROWSER_USE_API_KEY="+key)
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	runErr := cmd.Run()
	os.Stdout.Write(stdout.Bytes())
	os.Stderr.Write(stderr.Bytes())
	code := 0
	if runErr != nil {
		var ee *exec.ExitError
		if errors.As(runErr, &ee) {
			code = ee.ExitCode()
		} else {
			return "", runErr
		}
		return "", fmt.Errorf("profile-use sync failed (exit %d)", code)
	}
	// With --cloud-profile-id the tool reuses that profile instead of printing a new UUID.
	if cloudID != "" {
		return cloudID, nil
	}
	m := createdRE.FindStringSubmatch(stdout.String())
	if m == nil {
		return "", fmt.Errorf("profile-use did not report a profile UUID (exit %d)", code)
	}
	return m[1], nil
}

// CleanupCloudBrowsers stops active cloud browsers started more than olderThan ago.
func CleanupCloudBrowsers(olderThan time.Duration, dryRun bool) ([]map[string]any, error) {
	var active []map[string]any
	for page, seen := 1, 0; ; page++ {
		listing, err := browserUse(fmt.Sprintf("/browsers?pageSize=100&pageNumber=%d", page), "GET", nil)
		if err != nil {
			return nil, err
		}
		l, _ := listing.(map[string]any)
		items, _ := l["items"].([]any)
		for _, it := range items {
			if b, _ := it.(map[string]any); b != nil && b["finishedAt"] == nil {
				active = append(active, b)
			}
		}
		seen += len(items)
		if total, _ := l["totalItems"].(float64); len(items) == 0 || seen >= int(total) {
			break
		}
	}
	out := []map[string]any{}
	for _, b := range active {
		id, _ := b["id"].(string)
		startedAt, _ := b["startedAt"].(string)
		started, err := time.Parse(time.RFC3339, startedAt)
		if err != nil {
			return nil, fmt.Errorf("browser %s: bad startedAt %q", id, startedAt)
		}
		age := time.Since(started)
		action := "skipped"
		if age > olderThan {
			action = "would_stop"
			if !dryRun {
				action = "stopped"
				if err := stopCloudBrowser(id, true); err != nil {
					action = "stop_failed: " + err.Error()
				}
			}
		}
		out = append(out, map[string]any{
			"id": id, "started_at": startedAt, "age_minutes": float64(age.Round(6*time.Second)) / float64(time.Minute),
			"action": action,
		})
	}
	return out, nil
}
