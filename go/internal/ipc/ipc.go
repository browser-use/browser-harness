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
	"github.com/browser-use/browser-harness/go/internal/proc"
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

// Name is the default daemon name: BU_NAME, else "default".
func Name() string {
	if n := os.Getenv("BU_NAME"); n != "" {
		return n
	}
	return "default"
}

// Isolated is true when BH_RUNTIME_DIR holds a single daemon, named plain "bu".
func Isolated() bool {
	return os.Getenv("BH_RUNTIME_DIR") != "" && os.Getenv("BH_RUNTIME_DIR_SHARED") != "1"
}

func tmpIsolated() bool {
	return os.Getenv("BH_TMP_DIR") != "" && os.Getenv("BH_TMP_DIR_SHARED") != "1"
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
func PidPath(name string) string  { return runtimePath(name, ".pid") }
func PortPath(name string) string { return runtimePath(name, ".port") }
func SockPath(name string) string { return runtimePath(name, ".sock") }

// LockPath is the file lock serialising daemon starts for name; kind tells locks apart.
func LockPath(name, kind string) string { return runtimePath(name, "."+kind+"lock") }

func runtimePath(name, ext string) string {
	return filepath.Join(paths.RuntimeDir(), stem(name, Isolated())+ext)
}

// SockAddr is display-only.
func SockAddr(name string) string {
	if !IsWindows {
		return SockPath(name)
	}
	if port, _, err := readPortFile(name); err == nil {
		return fmt.Sprintf("127.0.0.1:%d", port)
	}
	return "tcp:" + stem(name, Isolated())
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
	network, addr, token := "unix", SockPath(name), ""
	if IsWindows {
		port, t, err := readPortFile(name)
		if err != nil {
			return nil, err
		}
		network, addr, token = "tcp", fmt.Sprintf("127.0.0.1:%d", port), t
	}
	c, err := (&net.Dialer{Timeout: timeout}).DialContext(context.Background(), network, addr)
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
func Listen(ctx context.Context, name string) (net.Listener, string, error) {
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
	data, err := json.Marshal(map[string]any{"port": l.Addr().(*net.TCPAddr).Port, "token": token})
	if err != nil {
		_ = l.Close()
		return nil, "", err
	}
	if err := paths.WriteFileAtomic(PortPath(name), data, 0o600); err != nil {
		_ = l.Close()
		return nil, "", err
	}
	return l, token, nil
}

// EndpointPath is the file a client connects through: the socket, or the port file on Windows.
func EndpointPath(name string) string {
	if IsWindows {
		return PortPath(name)
	}
	return SockPath(name)
}

// CleanupEndpoint removes the endpoint file; silent when already gone.
func CleanupEndpoint(name string) { _ = os.Remove(EndpointPath(name)) }

// WritePid records pid as name's daemon, with its start time so a reused PID is never mistaken for it.
func WritePid(name string, pid int) {
	var started any
	if fp := proc.StartTime(pid); fp != "" {
		started = fp
	}
	if b, err := json.Marshal(map[string]any{"pid": pid, "started": started}); err == nil {
		_ = paths.WriteFileAtomic(PidPath(name), b, 0o600)
	}
}

// ReadPid is the recorded daemon PID and start time; pid is 0 when there is no record.
func ReadPid(name string) (pid int, started string) {
	raw, err := os.ReadFile(PidPath(name)) //nolint:gosec // The path is derived from the validated daemon name.
	if err != nil {
		return 0, ""
	}
	var rec struct {
		PID     int    `json:"pid"`
		Started string `json:"started"`
	}
	if json.Unmarshal(raw, &rec) != nil {
		return 0, ""
	}
	return rec.PID, rec.Started
}
