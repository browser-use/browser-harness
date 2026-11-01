"""Run one agent snippet from stdin with the helpers pre-imported.

This is the only part of the CLI that is Python: agents write Python against
these globals. browser-harness-core prepares the daemon before starting this
process and reads the helper trace back from BH_TRACE_FILE for telemetry.
"""
import functools, json, os, sys, time

# Windows' default cp1252 can't encode the 🐴 tab-title marker or arbitrary
# page text; force UTF-8 so print(page_info()) never raises (#124).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try: _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass

from .admin import (
    NAME,
    browser_connections,
    daemon_alive,
    daemon_browser_kind,
    ensure_daemon,
    list_cloud_profiles,
    list_local_profiles,
    require_existing_daemon,
    restart_daemon,
    start_remote_daemon,
    stop_remote_daemon,
    sync_local_profile,
)
from . import recorder
from .helpers import *

_MAX_TRACED_STEPS = 500
_MAX_STEP_ARGS_LENGTH = 300
_helper_trace = []
_helper_call_count = 0


def _step_args(args, kwargs):
    parts = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
    return ", ".join(parts)[:_MAX_STEP_ARGS_LENGTH]


def _traced(name, fn):
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
        recorder.observe(name, args, kwargs, entry["duration_seconds"])
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


def _write_trace(error):
    path = os.environ.get("BH_TRACE_FILE")
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"steps": _helper_trace, "step_count": _helper_call_count, "error": error}, f, default=str)
    except OSError:
        pass


def main():
    code = sys.stdin.read()
    error = None
    _install_helper_trace()
    try:
        exec(code, globals())
    except SystemExit as exc:
        if isinstance(exc.code, str):
            error = exc.code
        raise
    except BaseException as exc:
        error = str(exc)
        raise
    finally:
        _write_trace(error)


if __name__ == "__main__":
    main()
