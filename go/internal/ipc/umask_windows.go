//go:build windows

package ipc

func privateUmask() func() { return func() {} }
