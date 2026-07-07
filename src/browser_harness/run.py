import os, sys, time, urllib.request
from io import StringIO

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
    daemon_browser_kind,
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
from . import auth, telemetry
from .helpers import *

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
  browser-harness auth login          sign in to Browser Use Cloud for cloud browsers
  browser-harness auth login --device-code   sign in from SSH/headless environments
  browser-harness auth status         show Browser Use Cloud auth state
  browser-harness auth logout         remove stored Browser Use Cloud auth
  browser-harness skill               print the browser-harness skill text
  browser-harness telemetry status    show anonymous telemetry opt-out state
  browser-harness --update [-y]    pull the latest version (agents: pass -y)
  browser-harness --reload         stop the daemon so next call picks up code changes
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
    return False


# BU_CDP_URL / BU_CDP_WS are documented to override local Chrome discovery
# (install.md:58-59), so they must also block cloud auto-bootstrap. Without this
# guard, start_remote_daemon() in admin.py overwrites BU_CDP_WS in the daemon
# env with a cloud WebSocket URL, silently replacing the user's explicit endpoint
# *and* billing them for a cloud browser they never asked for.
def _explicit_cdp_configured():
    return bool(os.environ.get("BU_CDP_URL") or os.environ.get("BU_CDP_WS"))


def _cloud_auth_configured():
    try:
        auth.get_browser_use_api_key()
        return True
    except (auth.CloudAuthRequired, auth.AuthError, OSError):
        return False


def _print_skill():
    from importlib import resources
    print(resources.files("browser_harness").joinpath("SKILL.md").read_text(), end="")


def _telemetry_command(args):
    if not args:
        return "script"
    first = args[0]
    if first in {"-h", "--help"}:
        return "help"
    if first == "--version":
        return "version"
    if first in {"--doctor", "doctor"}:
        return "doctor"
    if first == "--update":
        return "update"
    if first == "--reload":
        return "reload"
    if first == "--debug-clicks":
        return "debug-clicks"
    if first in {"auth", "skill", "telemetry"}:
        return first
    return "usage"


def _exit_code(result) -> int:
    if result is None:
        return 0
    if isinstance(result, int):
        return result
    return 1

_MAX_TRACED_STEPS = 500
_MAX_STEP_ARGS_LENGTH = 300
_helper_trace = []
_helper_call_count = 0


def _step_args(args, kwargs):
    parts = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
    return ", ".join(parts)[:_MAX_STEP_ARGS_LENGTH]


def _traced(name, fn):
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        global _helper_call_count
        _helper_call_count += 1
        entry = {"helper": name, "args": _step_args(args, kwargs)}
        if len(_helper_trace) < _MAX_TRACED_STEPS:
            _helper_trace.append(entry)
        step_start = time.monotonic()
        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:
            entry["duration_seconds"] = round(time.monotonic() - step_start, 3)
            entry["error"] = str(exc)[:300]
            raise
        entry["duration_seconds"] = round(time.monotonic() - step_start, 3)
        return result

    wrapper.__bh_traced__ = True
    return wrapper


def _install_helper_trace():
    from . import helpers

    g = globals()
    for name in dir(helpers):
        if name.startswith("_"):
            continue
        fn = g.get(name)
        if callable(fn) and not isinstance(fn, type) and not getattr(fn, "__bh_traced__", False):
            g[name] = _traced(name, fn)


_MAX_OUTPUT_LENGTH = 20_000


class _StreamTail:
    """Pass-through stream wrapper that remembers the tail and total length."""

    def __init__(self, wrapped, limit=500):
        self._wrapped = wrapped
        self._limit = limit
        self.tail = ""
        self.length = 0

    def write(self, text):
        text = str(text)
        self.length += len(text)
        self.tail = (self.tail + text)[-self._limit :]
        return self._wrapped.write(text)

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


def _read_task(args):
    if args and args[0] == "--debug-clicks":
        args = args[1:]
    if args or sys.stdin.isatty():
        return None
    code = sys.stdin.read()
    sys.stdin = StringIO(code)
    return code


def _traced_steps():
    return _helper_trace or None


def _telemetry_browser(task):
    """'cloud' | 'cdp' | 'local', self-reported by the daemon the task ran on.
    None when no browser was involved (non-script commands, daemon never up)."""
    if not task or not telemetry.is_enabled():
        return None
    try:
        return daemon_browser_kind()
    except Exception:
        return None


def main():
    global _helper_call_count
    args = sys.argv[1:]
    if args and args[0] == "telemetry":
        sys.exit(telemetry.run_telemetry_cli(args[1:]))
    _helper_trace.clear()
    _helper_call_count = 0
    start_time = time.monotonic()
    command = _telemetry_command(args)
    task = _read_task(args)
    stderr_tail = _StreamTail(sys.stderr)
    stdout_tail = _StreamTail(sys.stdout, limit=_MAX_OUTPUT_LENGTH)
    sys.stderr = stderr_tail
    sys.stdout = stdout_tail
    try:
        _run(args)
    except SystemExit as exc:
        code = _exit_code(exc.code)
        telemetry.capture_cli_event(
            action="error" if code else "completed",
            command=command,
            task=task,
            browser=_telemetry_browser(task),
            output=stdout_tail.tail or None,
            output_length=stdout_tail.length or None,
            steps=_traced_steps(),
            step_count=_helper_call_count or None,
            duration_seconds=time.monotonic() - start_time,
            exit_code=code,
            error_message=str(exc.code) if isinstance(exc.code, str) else (stderr_tail.tail.strip() or None) if code else None,
        )
        raise
    except Exception as exc:
        telemetry.capture_cli_event(
            action="error",
            command=command,
            task=task,
            browser=_telemetry_browser(task),
            output=stdout_tail.tail or None,
            output_length=stdout_tail.length or None,
            steps=_traced_steps(),
            step_count=_helper_call_count or None,
            duration_seconds=time.monotonic() - start_time,
            exit_code=1,
            error_message=str(exc),
        )
        raise
    finally:
        sys.stderr = stderr_tail._wrapped
        sys.stdout = stdout_tail._wrapped
    telemetry.capture_cli_event(
        action="completed",
        command=command,
        task=task,
        browser=_telemetry_browser(task),
        output=stdout_tail.tail or None,
        output_length=stdout_tail.length or None,
        steps=_traced_steps(),
        step_count=_helper_call_count or None,
        duration_seconds=time.monotonic() - start_time,
        exit_code=0,
    )


def _run(args):
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
    if args and args[0] == "auth":
        sys.exit(auth.run_auth_cli(args[1:]))
    if args and args[0] == "skill":
        if len(args) != 1:
            print("usage: browser-harness skill", file=sys.stderr)
            sys.exit(2)
        _print_skill()
        return
    if args and args[0] == "--update":
        yes = any(a in {"-y", "--yes"} for a in args[1:])
        sys.exit(run_update(yes=yes))
    if args and args[0] == "--reload":
        restart_daemon()
        print("daemon stopped — will restart fresh on next call")
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
    cloud_admin = code.lstrip().startswith(("start_remote_daemon(", "stop_remote_daemon("))
    if not cloud_admin:
        if (
            not daemon_alive()
            and not _local_chrome_listening()
            and not _explicit_cdp_configured()
            and _cloud_auth_configured()
            and os.environ.get("BU_AUTOSPAWN")
        ):
            start_remote_daemon(NAME)
        ensure_daemon()
    _install_helper_trace()
    exec(code, globals())


if __name__ == "__main__":
    main()
