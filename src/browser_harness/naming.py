"""The command name printed in help, usage and hint text."""
import os

DEFAULT = "browser-harness"


def cli_name():
    """`browser-harness`, or the CLI that wraps it: BH_CLI_NAME, which run.main(prog=...) sets. Paths such as
    ~/.config/browser-harness and the package name on PyPI keep the real name."""
    return os.environ.get("BH_CLI_NAME") or DEFAULT


def named(text):
    """Text written for `browser-harness` (HELP, USAGE) with the command renamed."""
    name = cli_name()
    return text if name == DEFAULT else text.replace(DEFAULT, name)
