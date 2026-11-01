//go:build !windows

package admin

import (
	"errors"
	"os"
	"os/exec"
	"syscall"
)

func detach(cmd *exec.Cmd) { cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true} }

func tryLock(f *os.File) bool {
	return syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB) == nil
}
func unlockFile(f *os.File) { _ = syscall.Flock(int(f.Fd()), syscall.LOCK_UN) }

func alive(pid int) bool {
	err := syscall.Kill(pid, 0)
	return err == nil || errors.Is(err, syscall.EPERM)
}

func terminate(pid int) { _ = syscall.Kill(pid, syscall.SIGTERM) }

// terminateGroup stops a browser we launched in its own session.
func terminateGroup(p *os.Process) { _ = syscall.Kill(-p.Pid, syscall.SIGTERM) }
