import subprocess
import sys

from admin import (
    _version,
    ensure_daemon,
    launch_chrome,
    list_cloud_profiles,
    list_local_profiles,
    print_update_banner,
    restart_daemon,
    run_doctor,
    run_setup,
    run_update,
    start_remote_daemon,
    stop_remote_daemon,
    sync_local_profile,
)
from helpers import *
from launch import get_default_user_data_dir

HELP = """Browser Harness

Read SKILL.md for the default workflow and examples.

Typical usage:
  uv run bh <<'PY'
  ensure_real_tab()
  print(page_info())
  PY

Helpers are pre-imported. The daemon auto-starts and connects to the running browser.

Commands:
  browser-harness --version        print the installed version
  browser-harness --doctor         diagnose install, daemon, and browser state
  browser-harness --setup          interactively attach to your running browser
  browser-harness --update [-y]    pull the latest version (agents: pass -y)
"""


def _chrome_is_running():
    """Return True if any Chrome/Chromium main process is alive."""
    for name in ("chrome", "chromium", "chromium-browser"):
        try:
            subprocess.run(
                ["pgrep", "-x", name], check=True, capture_output=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return False


def _chrome_has_cdp():
    """Return True if DevToolsActivePort exists in the default profile."""
    return (get_default_user_data_dir() / "DevToolsActivePort").exists()


def main():
    args = sys.argv[1:]
    if args and args[0] in {"-h", "--help"}:
        print(HELP)
        return
    if args and args[0] == "--version":
        print(_version() or "unknown")
        return
    if args and args[0] == "--doctor":
        sys.exit(run_doctor())
    if args and args[0] == "--setup":
        sys.exit(run_setup())
    if args and args[0] == "--update":
        yes = any(a in {"-y", "--yes"} for a in args[1:])
        sys.exit(run_update(yes=yes))
    if sys.stdin.isatty():
        sys.exit(
            "browser-harness reads Python from stdin. Use:\n"
            "  browser-harness <<'PY'\n"
            "  print(page_info())\n"
            "  PY"
        )
    print_update_banner()
    try:
        ensure_daemon()
    except RuntimeError as e:
        msg = str(e).lower()
        if "devtoolsactiveport" in msg or "remote debugging" in msg:
            if _chrome_is_running() and not _chrome_has_cdp():
                sys.exit(
                    "Chrome is already running without remote debugging.\n"
                    "Close Chrome and retry so browser-harness can launch it "
                    "with the right flags automatically."
                )
            if not _chrome_is_running():
                info = launch_chrome()
                print(
                    f"Auto-launched Chrome with CDP on port {info['port']}",
                    file=sys.stderr,
                )
                ensure_daemon()
            else:
                raise
        else:
            raise
    exec(sys.stdin.read(), globals())


if __name__ == "__main__":
    main()
