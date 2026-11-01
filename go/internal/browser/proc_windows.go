//go:build windows

package browser

func processExists(pid int) bool { return false }
