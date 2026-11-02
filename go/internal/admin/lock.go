package admin

import (
	"errors"
	"os"
	"sync"
	"time"

	"github.com/browser-use/browser-harness/go/internal/ipc"
)

// spawnLock lets only one process spawn a daemon for a name at a time. Best
// effort: when it cannot be taken, held is false and the caller decides.
type spawnLock struct {
	f    *os.File
	held bool
	name string // set for start locks
}

func acquireSpawnLock(name string, timeout time.Duration) *spawnLock {
	return acquireFileLock(name, ".spawnlock", timeout)
}

// startLocks are the start locks this process holds, so nested starts don't self-deadlock.
var (
	startMu    sync.Mutex
	startLocks = map[string]bool{}
)

// acquireStartLock serialises starting a cloud or BU_CDP_URL daemon for one name
// across processes, from before the browser is created until the daemon answers.
// It returns nil when this process already holds it.
func acquireStartLock(name string, timeout time.Duration) (*spawnLock, error) {
	startMu.Lock()
	held := startLocks[name]
	startMu.Unlock()
	if held {
		return nil, nil
	}
	lk := acquireFileLock(name, ".startlock", timeout)
	if !lk.held {
		return nil, errors.New("daemon-starting: another browser-harness daemon is still starting; retry later")
	}
	startMu.Lock()
	startLocks[name] = true
	startMu.Unlock()
	lk.name = name
	return lk, nil
}

func acquireFileLock(name, suffix string, timeout time.Duration) *spawnLock {
	path := ipc.PidPath(name)
	path = path[:len(path)-len(".pid")] + suffix
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
	if l == nil || l.f == nil {
		return
	}
	if l.name != "" {
		startMu.Lock()
		delete(startLocks, l.name)
		startMu.Unlock()
	}
	unlockFile(l.f)
	l.f.Close()
	l.f = nil
}
