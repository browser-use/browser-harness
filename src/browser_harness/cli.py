"""Console entry points: hand the command line to browser-harness-core."""
import os, subprocess, sys

from . import core


def _exec(*args):
    argv = [core.binary(), *args]
    env = core.env()
    if sys.platform == "win32":
        sys.exit(subprocess.run(argv, env=env).returncode)
    os.execve(argv[0], argv, env)


def main():
    _exec("cli", *sys.argv[1:])


def mcp():
    """`browser-harness-mcp`: the MCP server over stdio."""
    _exec("mcp")


if __name__ == "__main__":
    main()
