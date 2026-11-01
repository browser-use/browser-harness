// Command browser-harness-core is the Go core of browser-harness: daemon,
// lifecycle, auth, admin, recording and MCP. The Python package keeps only the
// snippet runner agents write against.
package main

import (
	"fmt"
	"os"

	"github.com/browser-use/browser-harness/go/internal/cli"
	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/telemetry"
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
	case "cli":
		return cli.Main(args)
	case "telemetry-send":
		return telemetry.RunSender()
	}
	fmt.Fprintf(os.Stderr, "browser-harness-core: unknown command %q\n", cmd)
	return 2
}
