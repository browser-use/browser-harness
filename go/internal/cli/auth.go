package cli

import (
	"fmt"
	"os"

	"golang.org/x/term"

	"github.com/browser-use/browser-harness/go/internal/auth"
	"github.com/browser-use/browser-harness/go/internal/pyjson"
)

const authUsage = "usage: browser-harness auth [-h] {login,status,logout} ..."

// Auth is `browser-harness auth`.
func Auth(args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, authUsage)
		return 2
	}
	switch args[0] {
	case "status":
		st, err := auth.Status()
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		fmt.Println(pyjson.Dumps(st, 2))
		return 0
	case "logout":
		removed, err := auth.Clear()
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		status := "missing"
		if removed {
			status = "logged-out"
		}
		fmt.Println(pyjson.Dumps(pyjson.Obj{{K: "status", V: status}, {K: "path", V: auth.Path()}}, 2))
		return 0
	case "login":
	default:
		fmt.Fprintln(os.Stderr, authUsage)
		return 2
	}
	device, stdin, jsonOut, noOpen := false, false, false, false
	for _, a := range args[1:] {
		switch a {
		case "--device-code":
			device = true
		case "--api-key-stdin":
			stdin = true
		case "--json":
			jsonOut = true
		case "--no-open":
			noOpen = true
		default:
			fmt.Fprintf(os.Stderr, "%s\nbrowser-harness auth: error: unrecognized arguments: %s\n", authUsage, a)
			return 2
		}
	}
	if device && stdin {
		fmt.Fprintf(os.Stderr, "%s\nbrowser-harness auth login: error: argument --api-key-stdin: not allowed with argument --device-code\n", authUsage)
		return 2
	}
	var err error
	switch {
	case stdin:
		err = auth.StdinLogin(os.Stdin, term.IsTerminal(int(os.Stdin.Fd())), jsonOut, os.Stdout)
	case device:
		err = auth.DeviceLogin(!noOpen, jsonOut, os.Stdout)
	default:
		err = auth.BrowserLogin(!noOpen, jsonOut, os.Stdout)
	}
	if err != nil {
		if jsonOut {
			fmt.Fprintln(os.Stderr, pyjson.Dumps(pyjson.Obj{{K: "status", V: "error"}, {K: "reason", V: err.Error()}}, 0))
		} else {
			fmt.Fprintln(os.Stderr, err)
		}
		return 1
	}
	return 0
}
