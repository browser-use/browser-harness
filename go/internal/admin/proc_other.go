//go:build !windows

package admin

func windowsStartTime(pid int) string { return "" }
