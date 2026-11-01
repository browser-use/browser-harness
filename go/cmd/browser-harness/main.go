// Command browser-harness is the CLI, daemon and MCP server. Only the snippets
// agents write run in Python, through browser_harness.runner.
package main

import (
	"fmt"
	"io"
	"os"

	"github.com/browser-use/browser-harness/go/internal/cli"
	"github.com/browser-use/browser-harness/go/internal/jsrun"
	"github.com/browser-use/browser-harness/go/internal/mcpserver"
	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/telemetry"
)

func main() {
	paths.Discover()
	paths.LoadEnv()
	cmd, args := "", os.Args[1:]
	if len(args) > 0 {
		cmd = args[0]
	}
	// Commands starting with "__" are internal: the binary re-executes itself with them.
	switch cmd {
	case "__daemon":
		os.Exit(runDaemon())
	case "__call":
		os.Exit(runCall(args[1:]))
	case "__telemetry-send":
		os.Exit(telemetry.RunSender())
	case "js":
		// Prototype: run a JavaScript snippet from stdin, no Python involved.
		code, _ := io.ReadAll(os.Stdin)
		if err := jsrun.Run(string(code), os.Stdout); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		os.Exit(0)
	case "mcp":
		os.Exit(mcpserver.Run(os.Getenv("BH_VERSION")))
	}
	os.Exit(cli.Main(args))
}
