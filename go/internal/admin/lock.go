package admin

import (
	"os"
	"time"

	"github.com/browser-use/browser-harness/go/internal/ipc"
)

// spawnLock lets only one process spawn a daemon for a name at a time. Best
// effort: when it cannot be taken, held is false and the caller decides.
type spawnLock struct {
	f    *os.File
	held bool
}

func acquireSpawnLock(name string, timeout time.Duration) *spawnLock {
	path := ipc.PidPath(name)
	path = path[:len(path)-len(".pid")] + ".spawnlock"
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		return &spawnLock{}
	}
	if st, err := f.Stat(); err == nil && st.Size() == 0 {
		_, _ = f.Write([]byte("1"))
	}
	deadline := time.Now().Add(timeout)
	for {
		if tryLock(f) {
			return &spawnLock{f: f, held: true}
		}
		if !time.Now().Before(deadline) {
			f.Close()
			return &spawnLock{}
		}
		time.Sleep(100 * time.Millisecond)
	}
}

func (l *spawnLock) release() {
	if l.f == nil {
		return
	}
	unlockFile(l.f)
	l.f.Close()
	l.f = nil
}
