//go:build windows

package telemetry

import (
	"os/exec"
	"syscall"

	"golang.org/x/sys/windows"
)

func Detach(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.CREATE_NEW_PROCESS_GROUP | windows.CREATE_NO_WINDOW}
}
