import os, sys, urllib.request

# Windows default stdout encoding is cp1252, which can't encode the 🐴 marker
# helpers prepend to tab titles (or anything else outside Latin-1). Force UTF-8
# so `print(page_info())` doesn't UnicodeEncodeError on Windows. Issue #124(4).
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from .admin import (
    _version,
    NAME,
    daemon_alive,
    ensure_daemon,
    list_cloud_profiles,
    list_local_profiles,
    print_update_banner,
    restart_daemon,
    run_doctor,
    run_doctor_fix_snap,
    run_update,
    start_remote_daemon,
    stop_remote_daemon,
    sync_local_profile,
)
from .helpers import *
from .browser import (
    default_profile as native_default_profile,
    find_existing_endpoint,
    list_local_browsers as native_local_browsers,
    list_local_profiles as native_local_profiles,
    open_local_profile_marker,
    set_default_profile as native_set_default_profile,
)

HELP = """Browser Harness

Read SKILL.md for the default workflow and examples.

Typical usage:
  browser-harness <<'PY'
  ensure_real_tab()
  print(page_info())
  PY

Helpers are pre-imported. The daemon auto-starts and connects to the running browser.

Commands:
  browser-harness --version        print the installed version
  browser-harness --doctor         diagnose install, daemon, and browser state
  browser-harness doctor           same as --doctor
  browser-harness doctor --fix-snap   print how to fix Snap Chromium blocking CDP (Linux)
  browser-harness --update [-y]    pull the latest version (agents: pass -y)
  browser-harness --reload         stop the daemon so next call picks up code changes
  browser-harness profile-target --profile NAME [--browser NAME]
                                   open a local profile marker and pin daemon to it
  browser-harness local-profiles [--json]
                                   list detected local browser profiles
  browser-harness local-browsers [--json]
                                   list detected local browsers
  browser-harness default-profile [--profile NAME_OR_ID] [--browser NAME] [--json]
                                   show or set deterministic default local profile
"""

USAGE = """Usage:
  browser-harness <<'PY'
  print(page_info())
  PY
"""


# Probe /json/version (not a bare TCP connect) so a non-Chrome process bound to
# 9222/9223 doesn't masquerade as Chrome and skip the cloud bootstrap. Mirrors
# daemon.py's fallback probe.
def _local_chrome_listening():
    for port in (9222, 9223):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.3).close()
            return True
        except OSError: pass
    try:
        return find_existing_endpoint() is not None
    except Exception:
        return False
    return False


# BU_CDP_URL / BU_CDP_WS are documented to override local Chrome discovery
# (install.md:58-59), so they must also block cloud auto-bootstrap. Without this
# guard, start_remote_daemon() in admin.py overwrites BU_CDP_WS in the daemon
# env with a cloud WebSocket URL, silently replacing the user's explicit endpoint
# *and* billing them for a cloud browser they never asked for.
def _explicit_cdp_configured():
    return bool(os.environ.get("BU_CDP_URL") or os.environ.get("BU_CDP_WS"))


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
    if args and args[0] == "doctor":
        rest = args[1:]
        if rest == ["--fix-snap"]:
            sys.exit(run_doctor_fix_snap())
        if rest:
            print("usage: browser-harness doctor [--fix-snap]", file=sys.stderr)
            sys.exit(2)
        sys.exit(run_doctor())
    if args and args[0] == "--update":
        yes = any(a in {"-y", "--yes"} for a in args[1:])
        sys.exit(run_update(yes=yes))
    if args and args[0] == "--reload":
        restart_daemon()
        print("daemon stopped — will restart fresh on next call")
        return
    if args and args[0] == "profile-target":
        rest = args[1:]
        profile = None
        browser = None
        marker = None
        i = 0
        while i < len(rest):
            if rest[i] == "--profile" and i + 1 < len(rest):
                profile = rest[i + 1]; i += 2; continue
            if rest[i] == "--browser" and i + 1 < len(rest):
                browser = rest[i + 1]; i += 2; continue
            if rest[i] == "--marker" and i + 1 < len(rest):
                marker = rest[i + 1]; i += 2; continue
            print("usage: browser-harness profile-target --profile NAME [--browser NAME] [--marker MARKER]", file=sys.stderr)
            sys.exit(2)
        if not profile:
            print("usage: browser-harness profile-target --profile NAME [--browser NAME] [--marker MARKER]", file=sys.stderr)
            sys.exit(2)
        opened = open_local_profile_marker(profile, browser_name=browser, marker=marker)
        restart_daemon()
        ensure_daemon(env={"BH_TARGET_MARKER": opened["marker"]})
        print(opened["url"])
        return
    if args and args[0] == "local-profiles":
        data = native_local_profiles()
        if "--json" in args[1:]:
            import json
            print(json.dumps(data, indent=2))
        else:
            for profile in data:
                print(f"{profile['id']}\t{profile['displayName']}\t{profile['profilePath']}")
        return
    if args and args[0] == "local-browsers":
        data = native_local_browsers()
        if "--json" in args[1:]:
            import json
            print(json.dumps(data, indent=2))
        else:
            for browser in data:
                print(f"{browser['name']}\tprofiles={browser['profileCount']}\t{browser.get('browserPath') or ''}")
        return
    if args and args[0] == "default-profile":
        rest = args[1:]
        profile = None
        browser = None
        as_json = "--json" in rest
        i = 0
        while i < len(rest):
            if rest[i] == "--json":
                i += 1; continue
            if rest[i] == "--profile" and i + 1 < len(rest):
                profile = rest[i + 1]; i += 2; continue
            if rest[i] == "--browser" and i + 1 < len(rest):
                browser = rest[i + 1]; i += 2; continue
            print("usage: browser-harness default-profile [--profile NAME_OR_ID] [--browser NAME] [--json]", file=sys.stderr)
            sys.exit(2)
        selected = native_set_default_profile(profile, browser_name=browser) if profile else native_default_profile()
        if as_json:
            import json
            print(json.dumps(selected, indent=2))
        elif selected:
            print(f"{selected['id']}\t{selected['displayName']}\t{selected['profilePath']}")
        else:
            print("no default profile configured", file=sys.stderr)
            sys.exit(1)
        return
    if args and args[0] == "--debug-clicks":
        os.environ["BH_DEBUG_CLICKS"] = "1"
        args = args[1:]
    if not args and not sys.stdin.isatty():
        code = sys.stdin.read()
        if not code.strip():
            sys.exit(USAGE)
    else:
        sys.exit(USAGE)
    print_update_banner()
    # Auto-bootstrap a cloud browser is opt-in via BU_AUTOSPAWN — BROWSER_USE_API_KEY alone
    # is not enough, since the key is commonly set for unrelated reasons (profile sync,
    # cloud API calls, parent agents managing their own session). An explicit BU_CDP_URL
    # or BU_CDP_WS also blocks the spawn so we honour the precedence install.md promises.
    if (
        not daemon_alive()
        and not _local_chrome_listening()
        and not _explicit_cdp_configured()
        and os.environ.get("BROWSER_USE_API_KEY")
        and os.environ.get("BU_AUTOSPAWN")
    ):
        start_remote_daemon(NAME)
    ensure_daemon()
    exec(code, globals())


if __name__ == "__main__":
    main()
