// Command browser-harness is the CLI, daemon and MCP server. Agent snippets are
// JavaScript, run in-process.
package main

import (
	"fmt"
	"os"

	"github.com/browser-use/browser-harness/go/internal/cli"
	"github.com/browser-use/browser-harness/go/internal/ipc"
	"github.com/browser-use/browser-harness/go/internal/mcpserver"
	"github.com/browser-use/browser-harness/go/internal/paths"
	"github.com/browser-use/browser-harness/go/internal/telemetry"
	"github.com/browser-use/browser-harness/go/internal/version"
)

func main() {
	paths.LoadEnv()
	if n := os.Getenv("BU_NAME"); n != "" {
		if err := ipc.Check(n); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	}
	cmd, args := "", os.Args[1:]
	if len(args) > 0 {
		cmd = args[0]
	}
	// Commands starting with "__" are internal: the binary re-executes itself with them.
	switch cmd {
	case "__daemon":
		os.Exit(runDaemon())
	case "__telemetry-send":
		os.Exit(telemetry.RunSender())
	case "mcp":
		os.Exit(mcpserver.Run(version.Version))
	}
	os.Exit(cli.Main(args))
}
