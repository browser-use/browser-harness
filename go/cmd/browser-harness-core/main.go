// Command browser-harness-core is the Go core of browser-harness: daemon,
// lifecycle, auth, admin, recording and MCP. The Python package keeps only the
// snippet runner agents write against.
package main

import (
	"fmt"
	"os"

	"github.com/browser-use/browser-harness/go/internal/admin"
	"github.com/browser-use/browser-harness/go/internal/paths"
)

func main() {
	paths.LoadEnv()
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: browser-harness-core <command> [args]")
		os.Exit(2)
	}
	os.Exit(dispatch(os.Args[1], os.Args[2:]))
}

func dispatch(cmd string, args []string) int {
	switch cmd {
	case "daemon":
		return runDaemon()
	case "call":
		return runCall(args)
	case "auth":
		return runAuth(args)
	case "doctor":
		return runDoctor(args)
	case "update":
		return admin.Update(len(args) > 0 && (args[0] == "-y" || args[0] == "--yes"))
	case "mac-approve":
		return admin.MacApprove(args)
	}
	fmt.Fprintf(os.Stderr, "browser-harness-core: unknown command %q\n", cmd)
	return 2
}

func runDoctor(args []string) int {
	jsonOut, strict, fixSnap := false, false, false
	for _, a := range args {
		switch a {
		case "--json":
			jsonOut = true
		case "--require-existing-daemon":
			strict = true
		case "--fix-snap":
			fixSnap = true
		default:
			fmt.Fprintf(os.Stderr, "browser-harness doctor: unknown option %s\n", a)
			return 2
		}
	}
	switch {
	case fixSnap:
		return admin.DoctorFixSnap()
	case jsonOut:
		return admin.DoctorJSON(strict)
	case strict:
		fmt.Fprintln(os.Stderr, "--require-existing-daemon requires --json")
		return 2
	}
	return admin.Doctor()
}
