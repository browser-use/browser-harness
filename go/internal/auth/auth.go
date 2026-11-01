// Package auth ports browser_harness/auth.py: Browser Use Cloud API key storage
// and the browser, device-code and stdin login flows.
package auth

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/pyjson"
)

const (
	defaultBase     = "https://api.browser-use.com"
	defaultClientID = "browser-use-terminal"
	callbackPath    = "/browser-use-cloud/callback"
	timeoutSeconds  = 600
)

// ErrRequired keeps the model-facing message from auth.py.
var ErrRequired = errors.New("cloud-auth-required: run `browser-harness auth login`")

func base() string {
	if v := os.Getenv("BROWSER_USE_CLOUD_API_URL"); v != "" {
		return strings.TrimRight(v, "/")
	}
	return defaultBase
}

func clientID() string {
	if v := os.Getenv("BROWSER_HARNESS_OAUTH_CLIENT_ID"); v != "" {
		return v
	}
	return defaultClientID
}

func deviceName() string {
	if v := os.Getenv("BH_DEVICE_NAME"); v != "" {
		return v
	}
	return "browser-harness"
}

// Path is BH_AUTH_PATH or <config>/auth.json.
func Path() string {
	if v := os.Getenv("BH_AUTH_PATH"); v != "" {
		if strings.HasPrefix(v, "~/") {
			h, _ := os.UserHomeDir()
			v = filepath.Join(h, v[2:])
		}
		return v
	}
	return filepath.Join(paths.ConfigDir(), "auth.json")
}

func loadFile(p string) (map[string]any, error) {
	raw, err := os.ReadFile(p)
	if errors.Is(err, os.ErrNotExist) {
		return map[string]any{}, nil
	}
	if err != nil {
		return nil, err
	}
	var v any
	if json.Unmarshal(raw, &v) != nil {
		return nil, fmt.Errorf("auth file is not valid JSON: %s", p)
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("auth file must contain a JSON object: %s", p)
	}
	return m, nil
}

func stored() (map[string]any, error) {
	m, err := loadFile(Path())
	if err != nil {
		return nil, err
	}
	rec, _ := m["browser_use"].(map[string]any)
	return rec, nil
}

// APIKey prefers BROWSER_USE_API_KEY, then the stored record.
func APIKey() (string, error) {
	if k := os.Getenv("BROWSER_USE_API_KEY"); k != "" {
		return k, nil
	}
	rec, err := stored()
	if err != nil {
		return "", err
	}
	if rec != nil {
		if k, ok := rec["api_key"].(string); ok && k != "" {
			return k, nil
		}
	}
	return "", ErrRequired
}

// Status keeps auth_status()'s key order: status, source, path.
func Status() (pyjson.Obj, error) {
	var status string
	var source any
	if os.Getenv("BROWSER_USE_API_KEY") != "" {
		return pyjson.Obj{{K: "status", V: "authenticated"}, {K: "source", V: "env"}, {K: "path", V: Path()}}, nil
	}
	rec, err := stored()
	if err != nil {
		return nil, err
	}
	switch {
	case rec != nil && rec["api_key"] != nil && rec["api_key"] != "":
		status, source = "authenticated", "stored"
	default:
		status, source = "missing", nil
	}
	return pyjson.Obj{{K: "status", V: status}, {K: "source", V: source}, {K: "path", V: Path()}}, nil
}

// Record is the stored browser_use entry.
type Record struct {
	APIKey    string   `json:"api_key"`
	APIKeyID  *string  `json:"api_key_id"`
	ProjectID *string  `json:"project_id"`
	ExpiresAt *string  `json:"expires_at"`
	Scopes    []string `json:"scopes"`
	Source    string   `json:"source"`
}

func recordFromToken(data map[string]any, source string) (Record, error) {
	key, _ := data["api_key"].(string)
	if key == "" {
		return Record{}, errors.New("auth token response did not include an api_key")
	}
	str := func(k string) *string {
		if s, ok := data[k].(string); ok {
			return &s
		}
		return nil
	}
	scopes := []string{}
	if list, ok := data["scopes"].([]any); ok {
		for _, s := range list {
			scopes = append(scopes, fmt.Sprint(s))
		}
	}
	return Record{APIKey: key, APIKeyID: str("api_key_id"), ProjectID: str("project_id"), ExpiresAt: str("expires_at"), Scopes: scopes, Source: source}, nil
}

func writePrivate(p string, data map[string]any) error {
	b, _ := json.MarshalIndent(data, "", "  ")
	tmp := p + ".tmp"
	f, err := os.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600)
	if err != nil {
		return err
	}
	if _, err := f.Write(append(b, '\n')); err != nil {
		f.Close()
		return err
	}
	f.Close()
	if err := os.Rename(tmp, p); err != nil {
		return err
	}
	_ = os.Chmod(p, 0o600)
	return nil
}

func Save(r Record) error {
	p := Path()
	_ = os.MkdirAll(filepath.Dir(p), 0o700)
	_ = os.Chmod(filepath.Dir(p), 0o700)
	m, err := loadFile(p)
	if err != nil {
		return err
	}
	var asMap map[string]any
	b, _ := json.Marshal(r)
	_ = json.Unmarshal(b, &asMap)
	m["browser_use"] = asMap
	return writePrivate(p, m)
}

// Clear removes the stored key and reports whether one existed.
func Clear() (bool, error) {
	p := Path()
	m, err := loadFile(p)
	if err != nil {
		return false, err
	}
	_, existed := m["browser_use"]
	delete(m, "browser_use")
	if len(m) > 0 {
		return existed, writePrivate(p, m)
	}
	if err := os.Remove(p); err != nil && !errors.Is(err, os.ErrNotExist) {
		return existed, err
	}
	return existed, nil
}

func postJSON(u string, payload any) (map[string]any, error) {
	b, _ := json.Marshal(payload)
	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Post(u, "application/json", bytes.NewReader(b))
	if err != nil {
		return nil, fmt.Errorf("network error: %v", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var data map[string]any
	_ = json.Unmarshal(body, &data)
	if resp.StatusCode >= 400 {
		code := firstString(data, "error", "state")
		if code == "" {
			code = "http_" + strconv.Itoa(resp.StatusCode)
		}
		if desc := firstString(data, "error_description", "reason", "message"); desc != "" {
			return nil, fmt.Errorf("%s: %s", code, desc)
		}
		return nil, errors.New(code)
	}
	if data == nil {
		data = map[string]any{}
	}
	return data, nil
}

func firstString(m map[string]any, keys ...string) string {
	for _, k := range keys {
		if s, ok := m[k].(string); ok && s != "" {
			return s
		}
	}
	return ""
}

func intOr(v any, def int) int {
	switch t := v.(type) {
	case float64:
		return int(t)
	case string:
		if i, err := strconv.Atoi(t); err == nil {
			return i
		}
	}
	return def
}

func token(n int) string {
	b := make([]byte, n)
	_, _ = rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}

// Opener opens URLs in the user's browser; overridable in tests.
var Opener = openURL

// BrowserLogin runs the PKCE loopback flow.
func BrowserLogin(open, jsonOut bool, out io.Writer) error {
	verifier := token(48)
	sum := sha256.Sum256([]byte(verifier))
	challenge := base64.RawURLEncoding.EncodeToString(sum[:])
	state := token(32)
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return err
	}
	redirect := fmt.Sprintf("http://%s%s", ln.Addr().String(), callbackPath)
	data, err := postJSON(base()+"/cloud/cli-auth/browser", map[string]any{
		"client_id": clientID(), "response_type": "code", "redirect_uri": redirect,
		"code_challenge": challenge, "code_challenge_method": "S256", "state": state, "device_name": deviceName(),
	})
	if err != nil {
		ln.Close()
		return err
	}
	authURL := firstString(data, "authorization_uri", "auth_url")
	if authURL == "" {
		ln.Close()
		return errors.New("auth start response did not include authorization_uri")
	}
	opened := open && Opener(authURL) == nil
	if jsonOut {
		writeJSON(out, pyjson.Obj{{K: "status", V: "needs_user_auth"}, {K: "auth_url", V: authURL}, {K: "callback", V: redirect}, {K: "expires_in", V: nullableInt(data["expires_in"])}, {K: "opened", V: opened}})
	} else {
		fmt.Fprintln(out, "Open this URL to sign in to Browser Use Cloud:")
		fmt.Fprintln(out, authURL)
		if opened {
			fmt.Fprintln(out, "Waiting for login to complete...")
		} else {
			fmt.Fprintln(out, "Waiting for login to complete after you open the URL...")
		}
	}
	type cb struct{ code, errCode, desc string }
	got := make(chan cb, 1)
	srv := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != callbackPath {
			http.NotFound(w, r)
			return
		}
		q := r.URL.Query()
		c := cb{code: q.Get("code"), errCode: q.Get("error"), desc: q.Get("error_description")}
		if q.Get("state") != state {
			c = cb{errCode: "invalid_state", desc: "OAuth callback state did not match"}
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write([]byte("<html><body><h1>Browser Use Cloud login complete</h1><p>You can close this tab.</p></body></html>"))
		select {
		case got <- c:
		default:
		}
	})}
	go srv.Serve(ln)
	defer srv.Shutdown(context.Background())
	var c cb
	select {
	case c = <-got:
	case <-time.After(timeoutSeconds * time.Second):
		return errors.New("timed out waiting for browser auth callback")
	}
	if c.errCode != "" {
		if c.desc != "" {
			return fmt.Errorf("auth failed: %s: %s", c.errCode, c.desc)
		}
		return fmt.Errorf("auth failed: %s", c.errCode)
	}
	if c.code == "" {
		return errors.New("auth callback did not include a code")
	}
	tok, err := postJSON(base()+"/cloud/cli-auth/token", map[string]any{
		"grant_type": "authorization_code", "code": c.code, "redirect_uri": redirect, "code_verifier": verifier, "client_id": clientID(),
	})
	if err != nil {
		return err
	}
	return storeAndReport(tok, "oauth", jsonOut, out, "Browser Use Cloud auth stored.")
}

// DeviceLogin runs the device-code flow for SSH/headless hosts.
func DeviceLogin(open, jsonOut bool, out io.Writer) error {
	data, err := postJSON(base()+"/cloud/cli-auth/device", map[string]any{"client_id": clientID(), "device_name": deviceName()})
	if err != nil {
		return err
	}
	deviceCode, userCode := firstString(data, "device_code"), firstString(data, "user_code")
	verify := firstString(data, "verification_uri", "verification_url")
	if deviceCode == "" || userCode == "" || verify == "" {
		return errors.New("device auth response missing device_code, user_code, or verification_uri")
	}
	complete := firstString(data, "verification_uri_complete")
	openURI := verify
	if complete != "" {
		openURI = complete
	}
	opened := open && Opener(openURI) == nil
	if jsonOut {
		var vc any
		if complete != "" {
			vc = complete
		}
		writeJSON(out, pyjson.Obj{{K: "status", V: "needs_user_auth"}, {K: "verification_uri", V: verify}, {K: "verification_uri_complete", V: vc}, {K: "user_code", V: userCode}, {K: "expires_in", V: nullableInt(data["expires_in"])}, {K: "opened", V: opened}})
	} else {
		fmt.Fprintln(out, "Open this URL to sign in to Browser Use Cloud:")
		fmt.Fprintln(out, openURI)
		fmt.Fprintf(out, "Code: %s\n", userCode)
		fmt.Fprintln(out, "Waiting for login to complete...")
	}
	interval := intOr(data["interval"], 5)
	if interval < 1 {
		interval = 1
	}
	deadline := time.Now().Add(time.Duration(intOr(data["expires_in"], timeoutSeconds)) * time.Second)
	for time.Now().Before(deadline) {
		tok, err := postJSON(base()+"/cloud/cli-auth/token", map[string]any{
			"grant_type": "urn:ietf:params:oauth:grant-type:device_code", "device_code": deviceCode, "client_id": clientID(),
		})
		if err == nil {
			return storeAndReport(tok, "oauth", jsonOut, out, "Browser Use Cloud auth stored.")
		}
		switch strings.SplitN(err.Error(), ":", 2)[0] {
		case "authorization_pending":
		case "slow_down":
			interval += 5
		default:
			return err
		}
		time.Sleep(time.Duration(interval) * time.Second)
	}
	return errors.New("timed out waiting for device auth")
}

// StdinLogin stores a key read from in (prompting without echo on a TTY).
func StdinLogin(in io.Reader, isTTY bool, jsonOut bool, out io.Writer) error {
	var key string
	if isTTY {
		k, err := readPassword("Browser Use API key: ")
		if err != nil {
			return errors.New("no API key provided")
		}
		key = k
	} else {
		b, _ := io.ReadAll(in)
		key = string(b)
	}
	key = strings.TrimSpace(key)
	if key == "" {
		return errors.New("no API key provided")
	}
	if len(key) < 20 {
		return errors.New("API key looks too short")
	}
	if err := Save(Record{APIKey: key, Scopes: []string{}, Source: "manual"}); err != nil {
		return err
	}
	if jsonOut {
		writeJSON(out, StoredOutput())
	} else {
		fmt.Fprintln(out, "Browser Use Cloud API key stored.")
	}
	return nil
}

func storeAndReport(tok map[string]any, source string, jsonOut bool, out io.Writer, msg string) error {
	rec, err := recordFromToken(tok, source)
	if err != nil {
		return err
	}
	if err := Save(rec); err != nil {
		return err
	}
	if jsonOut {
		writeJSON(out, StoredOutput())
	} else {
		fmt.Fprintln(out, msg)
	}
	return nil
}

func nullableInt(v any) any {
	switch v.(type) {
	case float64, string:
		if i := intOr(v, -1<<31); i != -1<<31 {
			return i
		}
	}
	return nil
}

func writeJSON(w io.Writer, v any) { fmt.Fprintln(w, pyjson.Dumps(v, 0)) }

// StoredOutput is the success line after a login.
func StoredOutput() pyjson.Obj { return pyjson.Obj{{K: "status", V: "stored"}, {K: "path", V: Path()}} }
