//go:build !windows

package proc

import (
	"errors"
	"os"
	"os/exec"
	"syscall"
)

// Detach starts cmd in its own session so it outlives this process and its terminal.
func Detach(cmd *exec.Cmd) { cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true} }

// Alive treats EPERM as alive: the pid belongs to another user.
func Alive(pid int) bool {
	err := syscall.Kill(pid, 0)
	return err == nil || errors.Is(err, syscall.EPERM)
}

func Terminate(pid int) { _ = syscall.Kill(pid, syscall.SIGTERM) }

// TerminateGroup stops a process started with Detach, with everything it spawned.
func TerminateGroup(p *os.Process) { _ = syscall.Kill(-p.Pid, syscall.SIGTERM) }

func TryLock(f *os.File) bool {
	return syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB) == nil
}
func Unlock(f *os.File) { _ = syscall.Flock(int(f.Fd()), syscall.LOCK_UN) }

func windowsStartTime(int) string { return "" }
