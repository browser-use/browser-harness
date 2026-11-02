package admin

import (
	"errors"
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
	return acquireFileLock(name, ".spawnlock", timeout)
}

// acquireStartLock serialises starting a cloud or BU_CDP_URL daemon for one name,
// from before the browser is created until the daemon answers. It is a file
// lock on its own descriptor, so it also serialises goroutines of one process.
func acquireStartLock(name string, timeout time.Duration) (*spawnLock, error) {
	lk := acquireFileLock(name, ".startlock", timeout)
	if !lk.held {
		return nil, errors.New("daemon-starting: another browser-harness daemon is still starting; retry later")
	}
	return lk, nil
}

func acquireFileLock(name, suffix string, timeout time.Duration) *spawnLock {
	path := ipc.PidPath(name)
	path = path[:len(path)-len(".pid")] + suffix
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o600) //nolint:gosec // The lock path is derived from the validated daemon name.
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
			_ = f.Close()
			return &spawnLock{}
		}
		time.Sleep(100 * time.Millisecond)
	}
}

func (l *spawnLock) release() {
	if l == nil || l.f == nil {
		return
	}
	unlockFile(l.f)
	_ = l.f.Close()
	l.f = nil
}
