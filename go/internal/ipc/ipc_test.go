package ipc

import (
	"bufio"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestStems(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("BH_TMP_DIR", "")
	t.Setenv("BH_RUNTIME_DIR", dir)
	t.Setenv("BH_RUNTIME_DIR_SHARED", "1")
	if got := filepath.Base(PidPath("work")); got != "bu-work.pid" {
		t.Errorf("shared runtime dir: %s", got)
	}
	t.Setenv("BH_RUNTIME_DIR_SHARED", "")
	if got := filepath.Base(PidPath("work")); got != "bu.pid" {
		t.Errorf("isolated runtime dir: %s", got)
	}
	t.Setenv("BH_TMP_DIR", dir)
	t.Setenv("BH_TMP_DIR_SHARED", "1")
	if got := filepath.Base(LogPath("work")); got != "bu-work.log" {
		t.Errorf("shared tmp dir: %s", got)
	}
}

// serve answers every request on the "default" endpoint with reply.
func serve(t *testing.T, reply string) {
	t.Helper()
	dir, err := os.MkdirTemp("", "bhipc")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	t.Setenv("BH_TMP_DIR", "")
	t.Setenv("BH_RUNTIME_DIR", dir)
	l, _, err := Listen(t.Context(), "default")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { l.Close() })
	go func() {
		for {
			c, err := l.Accept()
			if err != nil {
				return
			}
			_, _ = bufio.NewReader(c).ReadBytes('\n')
			_, _ = c.Write([]byte(reply + "\n"))
			c.Close()
		}
	}()
}

func TestIdentifySanitizesPid(t *testing.T) {
	cases := map[string]int{
		`{"pong": true, "pid": 4242}`:  4242,
		`{"pong": true, "pid": true}`:  0,
		`{"pong": true, "pid": false}`: 0,
		`{"pong": true}`:               0,
		`{"pong": false, "pid": 4242}`: 0,
		`{"pong": true, "pid": 0}`:     0,
		`{"pong": true, "pid": -1}`:    0,
		`{"pong": true, "pid": -42}`:   0,
		`{"pong": true, "pid": 1.5}`:   0,
		`[1, 2, 3]`:                    0,
		`"hello"`:                      0,
		`42`:                           0,
		`null`:                         0,
	}
	for reply, want := range cases {
		serve(t, reply)
		if got := Identify("default", time.Second); got != want {
			t.Errorf("Identify(%s) = %d, want %d", reply, got, want)
		}
	}
}

func TestPingRequiresPongTrue(t *testing.T) {
	cases := map[string]bool{
		`{"pong": true}`:  true,
		`{}`:              false,
		`{"pong": false}`: false,
		`{"pong": "yes"}`: false,
		`{"pong": 1}`:     false,
		`[1, 2, 3]`:       false,
		`"hello"`:         false,
		`null`:            false,
	}
	for reply, want := range cases {
		serve(t, reply)
		if got := Ping("default", time.Second); got != want {
			t.Errorf("Ping(%s) = %v, want %v", reply, got, want)
		}
	}
}

func TestSocketIsPrivate(t *testing.T) {
	if IsWindows {
		t.Skip("TCP on Windows")
	}
	serve(t, `{"pong": true}`)
	fi, err := os.Stat(SockPath("default"))
	if err != nil {
		t.Fatal(err)
	}
	if fi.Mode().Perm()&0o077 != 0 {
		t.Errorf("socket mode %v", fi.Mode().Perm())
	}
}
