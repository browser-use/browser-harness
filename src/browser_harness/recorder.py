"""Session recording helpers. The daemon (browser-harness-core) does the
recording; see interaction-skills/make-video.md to turn one into a video."""
import json, os

# Helpers that change what's on screen; only these produce frames. Mirrors
# recorder.Actions in go/internal/recorder so other helpers skip the IPC hop.
ACTIONS = {
    "goto_url", "click_at_xy", "type_text", "fill_input", "press_key",
    "scroll", "dispatch_key", "upload_file", "new_tab", "switch_tab",
    "close_tab", "ensure_real_tab",
    "wait", "wait_for_load", "wait_for_element", "wait_for_network_idle",
}


def _env():
    out = {"BU_NAME": os.environ.get("BU_NAME", "default")}
    for k in ("BH_RECORD", "BH_RECORD_IDLE"):
        if k in os.environ:
            out[k] = os.environ[k]
    return out


def _send(meta, **extra):
    # late: helpers imports this module at its bottom
    from .helpers import SCREENSHOT_IPC_RESPONSE_TIMEOUT_SECONDS, _send as send
    # Frames are screenshots; cloud ones routinely exceed the default IPC budget.
    return send({"meta": meta, **extra}, response_timeout=SCREENSHOT_IPC_RESPONSE_TIMEOUT_SECONDS + 5)


def _jsonable(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def start_recording(name=None, title=None):
    """Record the session: one screenshot + trace line per action, until
    stop_recording(). Survives across CLI invocations. Returns the recording
    directory. `title` is used later as the video title."""
    d = _send("record_start", name=name or "", title=title or "", call={"env": _env()})["dir"]
    print(f"recording to {d}")
    return d


def stop_recording():
    """Stop the active recording. Returns its directory, or None if idle."""
    r = _send("record_stop", call={"env": _env()})
    d = r.get("dir")
    if d is None:
        print("no active recording")
        return None
    print(f"recording saved: {d} ({r.get('frames', 0)} frames)")
    if not r.get("frames"):
        print(f"warning: no frames captured — see frame_error in {os.path.join(d, 'events.jsonl')}")
    return d


def recording_dir():
    """Directory of the active recording, or None."""
    return _send("record_dir", call={"env": _env()}).get("dir")


def observe(name, args, kwargs, duration=None):
    """Called by the runner after each traced helper succeeds. Never raises."""
    if name not in ACTIONS:
        return
    try:
        _send("record_observe", call={
            "helper": name,
            "args": [_jsonable(a) for a in args],
            "kwargs": {k: _jsonable(v) for k, v in kwargs.items()},
            "duration": duration,
            "env": _env(),
        })
    except Exception:
        pass
