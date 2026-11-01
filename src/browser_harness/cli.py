"""`browser-harness` entry point: hands the command line to browser-harness-core."""
import os, subprocess, sys

from . import core


def main():
    argv = [core.binary(), "cli", *sys.argv[1:]]
    env = core.env()
    if sys.platform == "win32":
        sys.exit(subprocess.run(argv, env=env).returncode)
    os.execve(argv[0], argv, env)


if __name__ == "__main__":
    main()
