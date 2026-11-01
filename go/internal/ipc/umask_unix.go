//go:build !windows

package ipc

import "syscall"

func privateUmask() func() {
	old := syscall.Umask(0o077)
	return func() { syscall.Umask(old) }
}
