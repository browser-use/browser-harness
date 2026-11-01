//go:build !windows

package browser

import (
	"errors"
	"syscall"
)

// processExists treats EPERM as alive: the pid belongs to another user.
func processExists(pid int) bool {
	err := syscall.Kill(pid, 0)
	return err == nil || errors.Is(err, syscall.EPERM)
}
