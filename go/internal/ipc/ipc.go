// Package ipc is the daemon transport:
// one JSON request line, one JSON response line. AF_UNIX (0600) on POSIX, TCP
// loopback plus a token in a port file on Windows.
package ipc

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"time"

	"github.com/browser-use/browser-harness/go/internal/paths"
)

const IsWindows = runtime.GOOS == "windows"

var nameRE = regexp.MustCompile(`\A[A-Za-z0-9_-]{1,64}\z`)

// Check guards BU_NAME against path traversal.
func Check(name string) error {
	if !nameRE.MatchString(name) {
		return fmt.Errorf("invalid BU_NAME %q: must match [A-Za-z0-9_-]{1,64}", name)
	}
	return nil
}

func runtimeIsolated() bool {
	return runtimeDirEnv() != "" && os.Getenv("BH_RUNTIME_DIR_SHARED") != "1"
}
func tmpIsolated() bool {
	return os.Getenv("BH_TMP_DIR") != "" && os.Getenv("BH_TMP_DIR_SHARED") != "1"
}

// BH_RUNTIME_DIR falls back to BH_TMP_DIR for legacy single-dir callers.
func runtimeDirEnv() string {
	if v := os.Getenv("BH_RUNTIME_DIR"); v != "" {
		return v
	}
	return os.Getenv("BH_TMP_DIR")
}

// RuntimeDir is where sockets, port files and PID files live.
func RuntimeDir() string {
	if v := runtimeDirEnv(); v != "" {
		a, _ := filepath.Abs(v)
		return paths.EnsurePrivateDir(a)
	}
	return paths.RuntimeDir()
}

func stem(name string, isolated bool) string {
	if isolated {
		return "bu"
	}
	return "bu-" + name
}

func LogPath(name string) string {
	return filepath.Join(paths.TmpDir(), stem(name, tmpIsolated())+".log")
}
func PidPath(name string) string {
	return filepath.Join(RuntimeDir(), stem(name, runtimeIsolated())+".pid")
}
func PortPath(name string) string {
	return filepath.Join(RuntimeDir(), stem(name, runtimeIsolated())+".port")
}
func SockPath(name string) string {
	return filepath.Join(RuntimeDir(), stem(name, runtimeIsolated())+".sock")
}

// SockAddr is display-only.
func SockAddr(name string) string {
	if !IsWindows {
		return SockPath(name)
	}
	if port, _, err := readPortFile(name); err == nil {
		return fmt.Sprintf("127.0.0.1:%d", port)
	}
	return "tcp:" + stem(name, runtimeIsolated())
}

func readPortFile(name string) (int, string, error) {
	raw, err := os.ReadFile(PortPath(name))
	if err != nil {
		return 0, "", err
	}
	var d struct {
		Port  int    `json:"port"`
		Token string `json:"token"`
	}
	if err := json.Unmarshal(raw, &d); err != nil || d.Port == 0 {
		return 0, "", errors.New("bad port file")
	}
	return d.Port, d.Token, nil
}

// Conn is one client connection plus the Windows token (empty on POSIX).
type Conn struct {
	net.Conn
	Token string
}

func Connect(name string, timeout time.Duration) (*Conn, error) {
	if !IsWindows {
		c, err := (&net.Dialer{Timeout: timeout}).DialContext(context.Background(), "unix", SockPath(name))
		if err != nil {
			return nil, err
		}
		_ = c.SetDeadline(time.Now().Add(timeout))
		return &Conn{Conn: c}, nil
	}
	port, token, err := readPortFile(name)
	if err != nil {
		return nil, err
	}
	c, err := (&net.Dialer{Timeout: timeout}).DialContext(context.Background(), "tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		return nil, err
	}
	_ = c.SetDeadline(time.Now().Add(timeout))
	return &Conn{Conn: c, Token: token}, nil
}

// Request sends one request and parses the one-line reply. The caller closes c.
func (c *Conn) Request(req map[string]any) (any, error) {
	if c.Token != "" {
		cp := make(map[string]any, len(req)+1)
		for k, v := range req {
			cp[k] = v
		}
		cp["token"] = c.Token
		req = cp
	}
	b, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	if _, err := c.Write(append(b, '\n')); err != nil {
		return nil, err
	}
	line, err := bufio.NewReaderSize(c, 1<<16).ReadBytes('\n')
	if err != nil && len(line) == 0 {
		if errors.Is(err, os.ErrDeadlineExceeded) {
			return nil, err
		}
		line = []byte("{}")
	}
	var out any
	if err := json.Unmarshal(line, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Call is Connect + Request + Close, returning the reply only when it is a JSON object.
func Call(name string, timeout time.Duration, req map[string]any) (map[string]any, error) {
	c, err := Connect(name, timeout)
	if err != nil {
		return nil, err
	}
	defer func() { _ = c.Close() }()
	resp, err := c.Request(req)
	if err != nil {
		return nil, err
	}
	m, ok := resp.(map[string]any)
	if !ok {
		return nil, errors.New("non-object reply")
	}
	return m, nil
}

// Ping is true only when our daemon answers {"pong": true}; a stale port file
// reused by an unrelated listener does not count.
func Ping(name string, timeout time.Duration) bool {
	m, err := Call(name, timeout, map[string]any{"meta": "ping"})
	return err == nil && m["pong"] == true
}

// Identify returns the live daemon's self-reported PID, or 0.
func Identify(name string, timeout time.Duration) int {
	m, err := Call(name, timeout, map[string]any{"meta": "ping"})
	if err != nil || m["pong"] != true {
		return 0
	}
	f, ok := m["pid"].(float64)
	if !ok || f != float64(int64(f)) || f <= 0 || f >= 1<<31 {
		return 0
	}
	return int(f)
}

// Listen binds the daemon endpoint and returns the listener plus the Windows token.
func Listen(name string) (net.Listener, string, error) {
	return ListenContext(context.Background(), name)
}

// ListenContext binds the daemon endpoint using ctx.
func ListenContext(ctx context.Context, name string) (net.Listener, string, error) {
	if !IsWindows {
		p := SockPath(name)
		_ = os.Remove(p)
		// umask 077 makes bind create the socket as 0600 with no chmod window.
		restore := privateUmask()
		l, err := (&net.ListenConfig{}).Listen(ctx, "unix", p)
		restore()
		return l, "", err
	}
	l, err := (&net.ListenConfig{}).Listen(ctx, "tcp", "127.0.0.1:0")
	if err != nil {
		return nil, "", err
	}
	buf := make([]byte, 32)
	_, _ = rand.Read(buf)
	token := hex.EncodeToString(buf)
	pf := PortPath(name)
	data, err := json.Marshal(map[string]any{"port": l.Addr().(*net.TCPAddr).Port, "token": token})
	if err != nil {
		_ = l.Close()
		return nil, "", err
	}
	tmp := pf + ".tmp"
	if err := os.WriteFile(tmp, data, 0o600); err != nil {
		_ = l.Close()
		return nil, "", err
	}
	if err := os.Rename(tmp, pf); err != nil {
		_ = l.Close()
		return nil, "", err
	}
	return l, token, nil
}

// CleanupEndpoint removes the socket or port file; silent when already gone.
func CleanupEndpoint(name string) {
	if IsWindows {
		_ = os.Remove(PortPath(name))
	} else {
		_ = os.Remove(SockPath(name))
	}
}
