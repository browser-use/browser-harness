package main

import (
	"fmt"
	"os"

	"golang.org/x/term"

	"github.com/browser-use/browser-harness/go/internal/auth"
	"github.com/browser-use/browser-harness/go/internal/pyjson"
)

const authUsage = "usage: browser-harness auth {login,status,logout} ..."

func runAuth(args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, authUsage)
		return 2
	}
	switch args[0] {
	case "status":
		fmt.Println(pyjson.Dumps(auth.Status(), 2))
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
			fmt.Fprintf(os.Stderr, "browser-harness auth login: unrecognized argument %s\n", a)
			return 2
		}
	}
	if device && stdin {
		fmt.Fprintln(os.Stderr, "browser-harness auth login: --device-code and --api-key-stdin are mutually exclusive")
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
