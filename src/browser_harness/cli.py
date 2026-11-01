"""`browser-harness-mcp`: hands over to the Go binary's MCP server."""
import os, subprocess, sys

from . import core


def mcp():
    argv = [core.binary(), "mcp"]
    if sys.platform == "win32":
        sys.exit(subprocess.run(argv, env=core.env()).returncode)
    os.execve(argv[0], argv, core.env())
