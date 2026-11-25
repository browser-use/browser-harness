import builtins
import json, os, sys, time, urllib.request
from io import StringIO

# Windows default stdout/stderr encoding is cp1252
# which can't encode the 🐴 marker helpers prepend to tab titles (or anything
# else outside the locale charset). Force UTF-8 so `print(page_info())` and
# tracebacks carrying page titles don't UnicodeEncodeError on Windows. #124(4).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try: _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass

from . import _ipc


def _alias_named_local_daemon_to_owner():
    """`BU_NAME=<x>` on the local Chrome, with no daemon of that name, means owner x
    on the shared daemon instead of a second browser connection.

    Agents invent per-job names (`gmail1375`) to isolate work. On the local Chrome
    a second daemon isolates nothing more than an owner does, and each one costs
    another "Allow remote debugging?" dialog that brings Chrome to the front (3
    named daemons = 3 dialogs, measured). Remote and CDP daemons keep their names:
    a live daemon of that name, a name whose remote browser ended (it fails closed
    with remote-browser-ended instead of falling back to local Chrome),
    BU_CDP_URL/BU_CDP_WS, BH_REQUIRE_EXISTING_DAEMON=1 or BH_NAMED_LOCAL_DAEMON=1
    leaves BU_NAME alone. Runs before the modules that read BU_NAME at import, so
    it is silent: _print_owner_alias() says it when a script runs, under the CLI's
    name (help, doctor and a host that imports this module print nothing)."""
    global _owner_alias
    name = os.environ.get("BU_NAME")
    if not name or name == "default":
        return False
    if (os.environ.get("BU_CDP_URL") or os.environ.get("BU_CDP_WS")
            or os.environ.get("BH_REQUIRE_EXISTING_DAEMON") == "1"
            or os.environ.get("BH_NAMED_LOCAL_DAEMON") == "1"):
        return False
    try:
        if _ipc.ping(name, timeout=0.5) or _ipc.read_remote_marker(name) is not None:
            return False
    except Exception:
        return False
    os.environ.setdefault("BH_OWNER", name)
    os.environ["BU_NAME"] = "default"
    _owner_alias = name
    return True


_owner_alias = None  # the BU_NAME that became an owner, for the notice when a script runs
_alias_named_local_daemon_to_owner()

from .admin import (
    _version,
    NAME,
    daemon_alive,
    daemon_browser_kind,
    ensure_daemon,
    list_cloud_profiles,
    list_local_profiles,
    print_update_banner,
    require_existing_daemon,
    restart_daemon,
    run_doctor,
    run_doctor_fix_snap,
    run_doctor_json,
    run_update,
    start_remote_daemon,
    stop_remote_daemon,
    sync_local_profile,
)
from . import auth, recorder, telemetry
from .helpers import *
from .helpers import captcha_note as _captcha_note  # private name: not traced as a step of the agent's script
from .naming import cli_name as _cli_name, named as _named
from .helpers import _warn_shared_owner

HELP = """Browser Harness

Read SKILL.md for the default workflow and examples.

Typical usage:
  browser-harness <<'PY'
  new_tab("https://example.com")
  print(page_info())
  PY

Helpers are pre-imported. The daemon auto-starts and connects to the running browser.

Commands:
  browser-harness --version        print the installed version
  browser-harness --doctor         diagnose install, daemon, and browser state
  browser-harness doctor           same as --doctor
  browser-harness doctor --json [--require-existing-daemon]
                                    print machine-readable runtime health
  browser-harness doctor --fix-snap   print how to fix Snap Chromium blocking CDP (Linux)
  browser-harness mac-approve         approve Chrome's macOS remote debugging sheet
  browser-harness auth login          sign in to Browser Use Cloud for cloud browsers
  browser-harness auth login --device-code   sign in from SSH/headless environments
  browser-harness auth status         show Browser Use Cloud auth state
  browser-harness auth logout         remove stored Browser Use Cloud auth
  browser-harness skill               print the browser-harness skill text
  browser-harness recordings          show recording status and recent sessions
  browser-harness recordings --latest   print the newest recording directory
  browser-harness recordings enable   save browser actions locally by default
  browser-harness recordings disable  stop saving browser actions by default
  browser-harness video init <recording>      prepare a recording for editing
  browser-harness video review <recording>    compile and review the video
  browser-harness video export <recording> --reviewed   export a verified MP4
  browser-harness telemetry status    show anonymous telemetry opt-out state
  browser-harness feedback "what happened" [--category bug|docs|missing|other]
                                    tell the Browser Use team what broke or could be better
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
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.3) as response:
                version = json.loads(response.read())
            if isinstance(version, dict) and isinstance(version.get("webSocketDebuggerUrl"), str) and version["webSocketDebuggerUrl"]:
                return True
        except (OSError, TypeError, ValueError):
            pass
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


def _print_captcha_note():
    """Captcha solves running, and finishes not yet shown, so the agent waits instead of reloading."""
    note = _captcha_note()
    if note:
        print(note)


def _print_owner_alias():
    if _owner_alias:
        print(f"{_cli_name()}: BU_NAME={_owner_alias} has no browser of its own; using the shared local Chrome as owner {os.environ.get('BH_OWNER') or _owner_alias!r} (no extra Allow prompt). Set BH_NAMED_LOCAL_DAEMON=1 for a separate connection.", file=sys.stderr)


def _print_skill():
    from importlib import resources
    # SKILL.md is UTF-8 (contains emoji); locale-codec read crashes on gbk Windows
    print(resources.files("browser_harness").joinpath("SKILL.md").read_text(encoding="utf-8"), end="")


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
    if first in {"auth", "feedback", "skill", "mac-approve", "recordings", "telemetry", "video"}:
        return first
    return "usage"


def _exit_code(result) -> int:
    if result is None:
        return 0
    if isinstance(result, int):
        return result
    return 1

_MAX_TRACED_STEPS = 500
_helper_trace = []
_helper_call_count = 0


_BUILTIN_CLASSES = {id(c): c.__name__ for c in vars(builtins).values() if isinstance(c, type)}


def _error_class(exc):
    """The nearest built-in class: a script's own exception names and every message stay on this machine."""
    return next(_BUILTIN_CLASSES[id(c)] for c in type(exc).__mro__ if id(c) in _BUILTIN_CLASSES)


def _traced(name, fn):
    import functools

    from . import helpers

    step_name = name if name in helpers._OWN_NAMES else "custom"  # agent_helpers.py names are the user's own

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        global _helper_call_count
        _helper_call_count += 1
        entry = {"helper": step_name}
        if len(_helper_trace) < _MAX_TRACED_STEPS:
            _helper_trace.append(entry)
        step_start = time.monotonic()
        try:
            result = fn(*args, **kwargs)
        except BaseException:
            entry["duration_seconds"] = round(time.monotonic() - step_start, 3)
            entry["error"] = True
            raise
        entry["duration_seconds"] = round(time.monotonic() - step_start, 3)
        recorder.observe(name, args, kwargs, entry["duration_seconds"])
        return result

    wrapper.__bh_traced__ = True
    return wrapper


# Their arguments are free text sent, scrubbed, to the library project (report.py), never in cli_event's steps.
_UNTRACED = {"report_issue", "report_run"}


def _install_helper_trace():
    from . import helpers

    g = globals()
    for name in dir(helpers):
        if name.startswith("_") or name in _UNTRACED:
            continue
        fn = g.get(name)
        if callable(fn) and not isinstance(fn, type) and not getattr(fn, "__bh_traced__", False):
            g[name] = _traced(name, fn)


class _CountingStream:
    """Pass-through stream wrapper that counts the characters written."""

    def __init__(self, wrapped):
        self._wrapped = wrapped
        self.length = 0

    def write(self, text):
        text = str(text)
        self.length += len(text)
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


def main(prog=None):
    """The CLI. prog: the command name a wrapping CLI prints in help, usage and hints (sets BH_CLI_NAME)."""
    global _helper_call_count
    if prog:
        os.environ["BH_CLI_NAME"] = prog  # env, so subcommands and the daemon it spawns say the same name
    args = sys.argv[1:]
    if args and args[0] == "telemetry":
        sys.exit(telemetry.run_telemetry_cli(args[1:]))
    _helper_trace.clear()
    _helper_call_count = 0
    start_time = time.monotonic()
    command = _telemetry_command(args)
    task = _read_task(args)
    stdout = _CountingStream(sys.stdout)
    sys.stdout = stdout
    try:
        _run(args)
    except SystemExit as exc:
        code = _exit_code(exc.code)
        telemetry.capture_cli_event(
            action="error" if code else "completed",
            command=command,
            task_length=len(task) if task is not None else None,
            browser=_telemetry_browser(task),
            output_length=stdout.length or None,
            steps=_traced_steps(),
            step_count=_helper_call_count or None,
            duration_seconds=time.monotonic() - start_time,
            exit_code=code,
            error_message="SystemExit" if code else None,
        )
        raise
    except Exception as exc:
        telemetry.capture_cli_event(
            action="error",
            command=command,
            task_length=len(task) if task is not None else None,
            browser=_telemetry_browser(task),
            output_length=stdout.length or None,
            steps=_traced_steps(),
            step_count=_helper_call_count or None,
            duration_seconds=time.monotonic() - start_time,
            exit_code=1,
            error_message=_error_class(exc),
        )
        raise
    finally:
        sys.stdout = stdout._wrapped
    telemetry.capture_cli_event(
        action="completed",
        command=command,
        task_length=len(task) if task is not None else None,
        browser=_telemetry_browser(task),
        output_length=stdout.length or None,
        steps=_traced_steps(),
        step_count=_helper_call_count or None,
        duration_seconds=time.monotonic() - start_time,
        exit_code=0,
    )


def _run(args):
    if args and args[0] in {"-h", "--help"}:
        print(_named(HELP))
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
        if rest and set(rest).issubset({"--json", "--require-existing-daemon"}) \
                and "--json" in rest and len(rest) == len(set(rest)):
            sys.exit(run_doctor_json(require_existing_daemon="--require-existing-daemon" in rest))
        if rest:
            print(f"usage: {_cli_name()} doctor [--fix-snap|--json [--require-existing-daemon]]", file=sys.stderr)
            sys.exit(2)
        sys.exit(run_doctor())
    if args and args[0] == "auth":
        sys.exit(auth.run_auth_cli(args[1:]))
    if args and args[0] == "feedback":
        from . import report

        sys.exit(report.run_feedback_cli(args[1:]))
    if args and args[0] == "mac-approve":
        from . import macos

        sys.exit(macos.run_cli(args[1:]))
    if args and args[0] == "skill":
        if len(args) != 1:
            print(f"usage: {_cli_name()} skill", file=sys.stderr)
            sys.exit(2)
        _print_skill()
        return
    if args and args[0] == "recordings":
        rest = args[1:]
        if rest == ["--latest"]:
            latest = recorder.latest_recording()
            if latest is None:
                print("no recordings found", file=sys.stderr)
                sys.exit(1)
            print(latest)
            return
        if rest in (["enable"], ["disable"]):
            enabled = rest == ["enable"]
            recorder.set_auto_recording(enabled)
            print(f"auto-recording preference {'enabled' if enabled else 'disabled'}")
            return
        if rest:
            print(f"usage: {_cli_name()} recordings [--latest|enable|disable]", file=sys.stderr)
            sys.exit(2)
        enabled, source = recorder.auto_recording_setting()
        print(f"auto-recording: {'on' if enabled else 'off'} ({source})")
        active = recorder.recording_dir()
        print(f"active: {active or 'none'}")
        recent = recorder.recordings()
        print(f"latest: {recent[0] if recent else 'none'}")
        return
    if args and args[0] == "video":
        from . import video

        sys.exit(video.run_cli(args[1:]))
    if args and args[0] == "--update":
        rest = args[1:]
        if not set(rest).issubset({"-y", "--yes"}):
            print(f"usage: {_cli_name()} --update [-y|--yes]", file=sys.stderr)
            sys.exit(2)
        sys.exit(run_update(yes=bool(rest)))
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
            sys.exit(_named(USAGE))
    else:
        sys.exit(_named(USAGE))
    print_update_banner()
    # Auto-bootstrap a cloud browser is opt-in via BU_AUTOSPAWN — BROWSER_USE_API_KEY alone
    # is not enough, since the key is commonly set for unrelated reasons (profile sync,
    # cloud API calls, parent agents managing their own session). An explicit BU_CDP_URL
    # or BU_CDP_WS also blocks the spawn so we honour the precedence install.md promises.
    cloud_admin = code.lstrip().startswith(("start_remote_daemon(", "stop_remote_daemon("))
    if not cloud_admin:  # a cloud start or stop uses no local Chrome: no owner notice either
        _print_owner_alias()
        require_existing = os.environ.get("BH_REQUIRE_EXISTING_DAEMON") == "1"
        try:
            if require_existing:
                require_existing_daemon()
            else:
                if (
                    not daemon_alive()
                    and not _local_chrome_listening()
                    and not _explicit_cdp_configured()
                    and _cloud_auth_configured()
                    and os.environ.get("BU_AUTOSPAWN")
                ):
                    start_remote_daemon(NAME)
                ensure_daemon()
        except RuntimeError as e:
            # Setup/permission errors are instructions for calling agent
            print(f"{_cli_name()}: {e}", file=sys.stderr)
            sys.exit(1)
    _warn_shared_owner()
    _install_helper_trace()
    try:
        exec(code, globals())
    finally:
        if not cloud_admin:
            _print_captcha_note()


if __name__ == "__main__":
    main()
