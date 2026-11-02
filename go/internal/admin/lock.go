package admin

import (
	"errors"
	"os"
	"time"

	"github.com/browser-use/browser-harness/go/internal/ipc"
	"github.com/browser-use/browser-harness/go/internal/proc"
)

var errStarting = errors.New("daemon-starting: another browser-harness daemon is still starting; retry later")

// fileLock is a cross-process lock on its own descriptor, so it also
// serialises goroutines of one process. The zero value is not held.
type fileLock struct{ f *os.File }

// lockStart takes name's lock of the given kind, waiting up to timeout. Kinds:
// "spawn" guards spawning a local daemon; "start" is held from creating a cloud
// or BU_CDP_URL browser until its daemon answers.
func lockStart(name, kind string, timeout time.Duration) (*fileLock, error) {
	f, err := os.OpenFile(ipc.LockPath(name, kind), os.O_CREATE|os.O_RDWR, 0o600) //nolint:gosec // The lock path is derived from the validated daemon name.
	if err != nil {
		return nil, errStarting
	}
	for deadline := time.Now().Add(timeout); ; time.Sleep(100 * time.Millisecond) {
		if proc.TryLock(f) {
			return &fileLock{f}, nil
		}
		if !time.Now().Before(deadline) {
			_ = f.Close()
			return nil, errStarting
		}
	}
}

func (l *fileLock) release() {
	if l == nil || l.f == nil {
		return
	}
	proc.Unlock(l.f)
	_ = l.f.Close()
	l.f = nil
}
