"""Browser control via CDP.

Core helpers live here. Agent-editable helpers live in
BH_AGENT_WORKSPACE/agent_helpers.py.
"""
import base64, hashlib, importlib.util, json, math, os, sys, tempfile, time, urllib.request, uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from . import _ipc as ipc
from . import paths


CORE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CORE_DIR.parent.parent
AGENT_WORKSPACE = paths.workspace_dir()


def _load_env():
    paths = [REPO_ROOT / ".env", AGENT_WORKSPACE / ".env"]
    for p in paths:
        if not p.exists():
            continue
        _load_env_file(p)


def _load_env_file(p):
    for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

NAME = os.environ.get("BU_NAME", "default")
SOCK = ipc.sock_addr(NAME)
INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")
IPC_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_IPC_RESPONSE_TIMEOUT_SECONDS = 5.0
# Cloud screenshots routinely take longer than ordinary CDP round trips. Keep
# their IPC socket alive within the caller's existing 90-second process budget.
SCREENSHOT_IPC_RESPONSE_TIMEOUT_SECONDS = 60.0


class _IPCResponseTimeout(TimeoutError):
    pass


def _send(req, response_timeout=DEFAULT_IPC_RESPONSE_TIMEOUT_SECONDS):
    c, token = ipc.connect(NAME, timeout=IPC_CONNECT_TIMEOUT_SECONDS)
    try:
        c.settimeout(response_timeout)
        try:
            r = ipc.request(c, token, req)
        except TimeoutError as e:
            # Carry the detail on the exception itself. Raising the bare class
            # left str(exc) empty, so every caller that reported the error had
            # to rebuild the context by hand or print nothing useful.
            label = req.get("method") or req.get("meta") or "request"
            raise _IPCResponseTimeout(
                f"{label} timed out after {response_timeout:g}s waiting for the daemon"
            ) from e
    finally:
        c.close()
    if r.get("tab_guard") == "refused":
        detail = r.get("error") or "daemon refused stale or invalid guard authorization"
        line = f"[tab-guard] REFUSED (daemon) {req.get('method') or req.get('meta') or 'request'}"
        log_path = os.environ.get("BH_TAB_GUARD_LOG")
        if log_path:
            try:
                with open(log_path, "a") as f:
                    f.write(f"{line}: {detail}\n")
            except Exception:
                pass
        raise TabGuardRefused(f"{line}: {detail}", source="daemon")
    if "error" in r: raise RuntimeError(r["error"])
    return r


# --- tab guard (opt-in via BH_TAB_GUARD=1) ---------------------------------
# The daemon attaches to whatever tab is FOCUSED, and that focus follows the
# human. For an UNATTENDED run — a scheduled job, a cron tick, anything nobody
# is watching — that means a navigate, a click, a screenshot or a close can land
# on a tab the run never opened: the person's own mail, banking, work.
#
# Documentation alone does not hold this. A run that is told "open your own tab
# first" still drifts, because the drift happens between calls and nothing
# refuses the next one. With BH_TAB_GUARD=1 the run may act only on tabs it
# created itself; anything else raises TabGuardRefused.
#
# Opt-in deliberately: interactive use legitimately drives a tab the human
# already opened ("summarise the page I'm looking at"), so the guard would be
# wrong there. Unattended runs never need it.
#
# ALLOWLIST, not blocklist. Naming the dangerous methods cannot work: CDP has
# hundreds and gains more. Leaving Runtime.evaluate off such a list is enough to
# undo the whole guard, since js("location.href=...") and js("el.click()") are
# ordinary fallbacks when a synthetic click is blocked. So the rule is inverted:
# on a tab the run does not own, only target ENUMERATION and CREATION are
# allowed, and every session-scoped method is refused.
#
# Reading an unowned tab is refused too. list_tabs() answers "what else is
# open?" from Target.getTargets without attaching, which is all a run needs;
# Runtime.evaluate and Page.captureScreenshot against someone's private tab are
# the thing being prevented.

class TabGuardRefused(RuntimeError):
    """A guarded operation was refused locally or by daemon authorization."""

    def __init__(self, message, *, source="helper"):
        super().__init__(message)
        self.source = source


# Global, and safe under the guard: enumeration and creation.
_TARGET_SAFE_METHODS = {"Target.getTargets", "Target.createTarget"}
# Global, but act on a specific target named in the params — check THAT target.
_TARGET_SCOPED_METHODS = {
    "Target.closeTarget", "Target.activateTarget", "Target.attachToTarget",
    "Target.getTargetInfo",
}
# Other Target methods are refused; session calls must use an owned session.
_GUARD_TAB_SCOPED_METHODS = {
    "DOM.getDocument", "DOM.querySelector", "DOM.querySelectorAll", "DOM.setFileInputFiles",
    "Emulation.setEmulatedMedia", "Emulation.setFocusEmulationEnabled",
    "Input.dispatchKeyEvent", "Input.dispatchMouseEvent", "Input.insertText",
    "Network.disable", "Network.enable", "Network.setBlockedURLs",
    "Network.setBypassServiceWorker", "Network.setCacheDisabled",
    "Network.setExtraHTTPHeaders", "Network.setUserAgentOverride",
    "Page.bringToFront", "Page.reload",
    "Page.captureScreenshot", "Page.getFrameTree",
    "Page.handleJavaScriptDialog", "Page.navigate", "Page.setDocumentContent",
    "Runtime.evaluate",
}
_GUARD_CONTEXT_WIDE_METHODS = {
    "Network.canClearBrowserCache", "Network.canClearBrowserCookies",
    "Network.clearBrowserCache", "Network.clearBrowserCookies",
    "Network.deleteCookies", "Network.getAllCookies", "Network.getCookies",
    "Network.setCookie", "Network.setCookies",
    "Storage.clearCookies", "Storage.clearDataForOrigin",
    "Storage.clearDataForStorageKey", "Storage.getCookies", "Storage.setCookies",
}


def _guard_scope_reason(method):
    if method == "Target.exposeDevToolsProtocol":
        return "Target.exposeDevToolsProtocol exposes unrestricted target commands"
    if method.startswith("ServiceWorker."):
        return "ServiceWorker methods are not tab-scoped"
    if method.startswith("Storage."):
        return "Storage methods are origin/context-wide and unavailable under the tab guard"
    if method.startswith(("Browser.", "SystemInfo.")):
        return "browser-wide method is unavailable under the tab guard"
    if method in _GUARD_CONTEXT_WIDE_METHODS:
        return "browser/context-wide method is unavailable under the tab guard"
    if not method.startswith("Target.") and method not in _GUARD_TAB_SCOPED_METHODS:
        return "method is not in the tab-scoped allowlist"
    return None


def _url_scope_reason(url, required=False):
    if url is None or url == "":
        return "URL is required" if required else None
    if not isinstance(url, str):
        return "URL must be a string"
    lowered = url.lower()
    if lowered == "about:blank" or lowered.startswith("about:blank#"):
        return None
    parsed = urlparse(url)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        return None
    return "URL scheme is unavailable under the tab guard"


def _url_scope_check(method, params):
    if method == "Target.createTarget":
        return _url_scope_reason(params.get("url"))
    if method == "Page.navigate":
        return _url_scope_reason(params.get("url"), required=True)
    return None


def _validate_context_url(method, params, session_id, context):
    if not isinstance(context, dict):
        _refuse(method, f"session:{session_id}", params.get("url", ""),
                "attached target/session could not be resolved (failing closed)")
    if context.get("session_id") != session_id:
        _refuse(method, f"session:{session_id}", params.get("url", ""),
                "session does not match the daemon current session and has no target ownership mapping")
    if not isinstance(context.get("target_id"), str) or not context["target_id"]:
        _refuse(method, f"session:{session_id}", params.get("url", ""),
                "session-to-target ownership mapping could not be resolved (failing closed)")
    if "url" not in context:
        _refuse(method, f"session:{session_id}", params.get("url", ""),
                "daemon did not provide the attached target URL (failing closed)")
    url_reason = _url_scope_reason(context.get("url"), required=True)
    if url_reason:
        _refuse(method, f"session:{session_id}", context.get("url", ""), url_reason)


def _guard_context_request(**params):
    epoch_context = _send({"meta": "guard_epoch"})
    epoch = epoch_context.get("tab_guard_epoch") if isinstance(epoch_context, dict) else None
    if not isinstance(epoch, int) or epoch < 0:
        return {}
    return _send({"meta": "guard_context", "tab_guard_run": _run_id(),
                  "tab_guard_epoch": epoch, **params})


def _check_session_target_url(method, params, session_id):
    try:
        context = _guard_context_request(session_id=session_id)
    except Exception:
        _refuse(method, f"session:{session_id}", params.get("url", ""),
                "attached target URL could not be read (failing closed)")
    _validate_context_url(method, params, session_id, context)
    if context["target_id"] not in _owned_ids():
        _refuse(method, f"session:{session_id}", context.get("url", ""),
                "session target was not opened by this run")
    return context


def _tab_guard_on():
    return os.environ.get("BH_TAB_GUARD") == "1"


def _run_id():
    """Identifies one run. Set BH_TAB_GUARD_RUN to something unique per run (a
    job id): ownership is scoped to it, so a run starts owning nothing and two
    concurrent runs cannot consume each other's list."""
    run_id = os.environ.get("BH_TAB_GUARD_RUN", "")
    try:
        parsed = uuid.UUID(run_id)
    except (ValueError, AttributeError):
        parsed = None
    if (parsed is None or parsed.version != 4 or parsed.variant != uuid.RFC_4122
            or str(parsed) != run_id):
        _refuse("run", None, "", "BH_TAB_GUARD_RUN must be a fresh canonical UUID4")
    return run_id


def _owned_path():
    # The run id is part of the FILENAME, not just the contents. Two harness
    # users sharing a daemon name (the default is literally "default") would
    # otherwise read-modify-write one file and drop each other's entries —
    # which refuses a run on its OWN tab, mid-task.
    key = json.dumps([NAME, str(ipc._RUNTIME), _run_id()], ensure_ascii=True)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return ipc._TMP / f"{ipc._tmp_stem(NAME)}-owned-tabs-{digest}.json"


def _owned_state():
    owned_path = _owned_path()  # Invalid run IDs must not be swallowed below.
    return _read_owned_state(owned_path)


def _read_owned_state(owned_path):
    try:
        state = json.loads(owned_path.read_text(encoding="utf-8"))
    except Exception:
        return {"tabs": [], "sessions": [], "contexts": []}
    if not isinstance(state, dict):
        return {"tabs": [], "sessions": [], "contexts": []}
    return {
        kind: [v for v in state[kind] if isinstance(v, str) and v]
        if isinstance(state.get(kind), list) else []
        for kind in ("tabs", "sessions", "contexts")
    }


@contextmanager
def _ownership_lock(path):
    """Hold the per-record lock across ownership read, update, and replace."""
    lock_path = path.with_name(path.name + ".lock")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        if os.name == "nt":
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"1")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


def _owned_ids():
    """Target ids of tabs this run opened."""
    return set(_owned_state()["tabs"])


def _owned_sessions():
    """Session ids this run attached, so an explicitly-addressed session can be
    told apart from someone else's."""
    return set(_owned_state()["sessions"])


def _owned_contexts():
    """Browser contexts created by this guarded run."""
    return set(_owned_state()["contexts"])


def _create_guard_context():
    """Create and record the private browser context used by this run."""
    try:
        request = {"method": "Target.createBrowserContext", "params": {}, "session_id": None}
        request.update(_guard_dispatch_fields("Target.createBrowserContext", {}, None))
        response = _send(request)
        context_id = response.get("result", {}).get("browserContextId")
    except Exception:
        context_id = None
    if not isinstance(context_id, str) or not context_id:
        _refuse("Target.createTarget", None, "", "could not create a run-owned browser context")
    _remember("contexts", context_id)
    if context_id not in _owned_contexts():
        _refuse("Target.createTarget", None, "", "run-owned browser context could not be recorded")
    return context_id


def _guard_target_context(params):
    """Pin guarded target creation to a context owned by this run."""
    requested = params.get("browserContextId")
    contexts = _owned_contexts()
    if "browserContextId" in params:
        if requested not in contexts:
            _refuse("Target.createTarget", None, params.get("url", ""),
                    "browser context is not owned by this run")
        return requested
    if len(contexts) > 1:
        _refuse("Target.createTarget", None, params.get("url", ""),
                "multiple run-owned browser contexts require an explicit browserContextId")
    context_id = next(iter(contexts), None) or _create_guard_context()
    params["browserContextId"] = context_id
    return context_id


def _remember(kind, value, remove=False):
    if not _tab_guard_on() or not value:
        return
    path = _owned_path()
    temporary = None
    try:
        with _ownership_lock(path):
            state = _read_owned_state(path)
            present = value in state[kind]
            if (not remove and present) or (remove and not present):
                return
            state[kind] = sorted(set(state[kind]) - {value} if remove else set(state[kind]) | {value})
            fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.replace(temporary, path)
    except Exception as e:
        # NOT silent. With the guard on, a lost ownership record refuses every
        # later action on a tab the run genuinely opened, and swallowing this
        # would make a disk problem look like a guard bug.
        print(f"[tab-guard] WARNING could not record ownership of {value}: {e}", file=sys.stderr, flush=True)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _own_tab(target_id):
    """Record a tab created while this run's guard is enabled."""
    _remember("tabs", target_id)


def tab_guard_reset():
    """Forget every owned tab and session. Rarely needed: a run with its own
    BH_TAB_GUARD_RUN already starts owning nothing. Calling it mid-run makes the
    run disown its own tabs and be refused on them."""
    if not _tab_guard_on():
        return
    run_id = _run_id()
    epoch = _send({"meta": "guard_epoch"}).get("tab_guard_epoch")
    if not isinstance(epoch, int) or epoch < 0:
        _refuse("tab_guard_reset", None, "", "daemon guard epoch is unavailable")
    response = _send({"meta": "tab_guard_reset", "tab_guard_run": run_id,
                      "tab_guard_epoch": epoch})
    if (response.get("tab_guard") != "ok"
            or response.get("tab_guard_run") != run_id):
        _refuse("tab_guard_reset", None, "", "daemon did not acknowledge run revocation")
    path = _owned_path()
    with _ownership_lock(path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _checked_session(method, params):
    """Snapshot target/session together, validate both, and pin later dispatch."""
    try:
        context = _guard_context_request()
    except Exception:
        context = {}
    context = context if isinstance(context, dict) else {}
    target_id, sid = context.get("target_id"), context.get("session_id")
    _validate_context_url(method, params, sid, context)
    if (isinstance(target_id, str) and target_id in _owned_ids()
            and isinstance(sid, str) and sid and sid in _owned_sessions()):
        return sid
    _refuse(method, target_id, params.get("url", ""),
            "attached tab/session is not owned or could not be resolved (failing closed)")


def _is_owned_iframe(target_id):
    """Only a frame in an owned page's frame tree may inherit tab ownership.

    OOPIF target IDs are frame IDs. Enumeration, target type, opener IDs and
    URLs alone do not establish ancestry. Workers without proof fail closed.
    """
    if _tab_guard_on():
        try:
            context = _guard_context_request()
            epoch = context.get("tab_guard_epoch") if isinstance(context, dict) else None
            if (context.get("tab_guard") != "ok" or not isinstance(epoch, int)
                    or context.get("session_id") not in _owned_sessions()
                    or context.get("target_id") not in _owned_ids()):
                return False
            result = _send({
                "meta": "guard_iframe", "tab_guard": _owned_state(),
                "tab_guard_run": _run_id(), "tab_guard_epoch": epoch,
                "target_id": target_id,
            })
            if result.get("tab_guard") == "ok" and result.get("target_id") == target_id:
                _remember("tabs", target_id)
                return True
        except Exception:
            pass
        return False
    try:
        info = _send({"method": "Target.getTargetInfo", "params": {"targetId": target_id}, "session_id": None})
        target_info = info.get("result", {}).get("targetInfo", {})
        if target_info.get("type") != "iframe":
            return False
        if _url_scope_reason(target_info.get("url")):
            return False
        sid = _checked_session("Target.attachToTarget", {})
        tree = _send({"method": "Page.getFrameTree", "params": {}, "session_id": sid})["result"]["frameTree"]
        pending = list(tree.get("childFrames", []))
        while pending:
            child = pending.pop()
            if child.get("frame", {}).get("id") == target_id:
                return True
            pending.extend(child.get("childFrames", []))
    except Exception:
        pass
    return False


def _refuse(method, target_id, url, reason):
    line = f"[tab-guard] REFUSED {method} {target_id or '?'} {url or ''}".rstrip()
    print(line, file=sys.stderr, flush=True)
    # A supervisor that wants to count refusals usually cannot see this
    # process's stderr — it is a child of a child, and its output is captured by
    # whatever spawned it. BH_TAB_GUARD_LOG appends the line to a file the
    # supervisor does read.
    log_path = os.environ.get("BH_TAB_GUARD_LOG")
    if log_path:
        try:
            with open(log_path, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass  # the stderr line and the raise still stand
    raise TabGuardRefused(f"{line} ({reason})")


def _tab_guard_check(method, params, session_id=None):
    if not _tab_guard_on():
        return session_id
    _run_id()
    url_reason = _url_scope_check(method, params)
    if url_reason:
        _refuse(method, params.get("targetId"), params.get("url", ""), url_reason)
    scope_reason = _guard_scope_reason(method)
    if scope_reason:
        _refuse(method, params.get("targetId"), params.get("url", ""), scope_reason)
    if method == "Target.createTarget":
        _guard_target_context(params)
    if method in _TARGET_SAFE_METHODS:
        return

    if method in {"Target.detachFromTarget", "Target.sendMessageToTarget"}:
        sid = params.get("sessionId")
        if not sid or sid not in _owned_sessions():
            _refuse(method, f"session:{sid}", "", "session was not attached by this run")
        if params.get("targetId") is not None:
            _refuse(method, params["targetId"], "", "use only the owned sessionId")
        if method == "Target.sendMessageToTarget":
            try:
                message = json.loads(params.get("message", ""))
                nested_method = message["method"]
                nested_scope_reason = _guard_scope_reason(nested_method) if isinstance(nested_method, str) else None
                raw_nested_params = message.get("params", {})
                nested_params = {} if raw_nested_params is None else raw_nested_params
                nested_url_reason = (_url_scope_check(nested_method, nested_params)
                                     if isinstance(nested_method, str) and isinstance(nested_params, dict)
                                     else "invalid nested params")
                if (not isinstance(message, dict) or not isinstance(nested_method, str)
                        or nested_method.startswith("Target.") or nested_scope_reason
                        or nested_url_reason or "sessionId" in message):
                    raise ValueError("nested routing")
            except (ValueError, KeyError, TypeError):
                _refuse(method, f"session:{sid}", "", "invalid or nested target-routing message")
        _check_session_target_url(method, params, sid)
        return

    if method in _TARGET_SCOPED_METHODS:
        target_id = params.get("targetId")
        if target_id in _owned_ids():
            return
        if method == "Target.attachToTarget" and target_id and _is_owned_iframe(target_id):
            return
        _refuse(method, target_id, params.get("url", ""), "not a tab this run opened")

    # Unknown Target methods are browser-scoped in the daemon. Never authorize
    # them merely because the daemon happens to be attached to an owned page.
    if method.startswith("Target."):
        _refuse(method, None, "", "unsupported browser-level target operation")

    if session_id is not None:
        # An explicitly-addressed session: allowed only if this run attached it.
        # Validating the daemon's CURRENT target instead would check one target
        # and then dispatch into another.
        if session_id and session_id in _owned_sessions():
            _check_session_target_url(method, params, session_id)
            return session_id
        _refuse(method, f"session:{session_id}", params.get("url", ""), "session was not attached by this run")

    return _checked_session(method, params)


def _guard_dispatch_fields(method, params, session_id):
    """Pin guarded IPC to the daemon's current run, target, and document."""
    if not _tab_guard_on():
        return {}
    requested_session = session_id
    if method in {"Target.detachFromTarget", "Target.sendMessageToTarget"}:
        requested_session = params.get("sessionId")
    requested_target = params.get("targetId") if method in _TARGET_SCOPED_METHODS else None
    try:
        epoch_context = _send({"meta": "guard_epoch"})
        epoch = epoch_context.get("tab_guard_epoch") if isinstance(epoch_context, dict) else None
        if not isinstance(epoch, int) or epoch < 0:
            _refuse(method, requested_target or f"session:{requested_session}",
                    params.get("url", ""), "daemon guard epoch is unavailable")
        if method in {"Target.createBrowserContext", "Target.createTarget", "Target.getTargets"}:
            return {
                "tab_guard": _owned_state(),
                "tab_guard_run": _run_id(),
                "tab_guard_epoch": epoch,
                "tab_guard_target_id": None,
                "tab_guard_session_id": None,
                "tab_guard_document_generation": None,
                "tab_guard_url": None,
            }
        context_request = {"meta": "guard_context", "tab_guard_run": _run_id(),
                           "tab_guard_epoch": epoch}
        if requested_session:
            context_request["session_id"] = requested_session
        elif requested_target:
            context_request["target_id"] = requested_target
        context = _send(context_request)
    except TabGuardRefused:
        raise
    except (OSError, RuntimeError, TimeoutError):
        _refuse(method, requested_target or f"session:{requested_session}",
                params.get("url", ""), "guard authorization could not be read")
    if not isinstance(context, dict) or context.get("tab_guard") != "ok":
        _refuse(method, requested_target or f"session:{requested_session}",
                params.get("url", ""), "daemon guard authorization is unavailable")
    epoch = context.get("tab_guard_epoch")
    if not isinstance(epoch, int) or epoch < 0:
        _refuse(method, requested_target or f"session:{requested_session}",
                params.get("url", ""), "daemon guard epoch is unavailable")
    target_id = context.get("target_id") if (requested_session or requested_target) else None
    if requested_target and target_id != requested_target:
        _refuse(method, requested_target, params.get("url", ""),
                "target mapping changed before dispatch")
    if requested_target and not requested_session:
        requested_session = context.get("session_id")
    generation = context.get("document_generation")
    if requested_session and (not isinstance(generation, int) or generation < 0):
        _refuse(method, f"session:{requested_session}", params.get("url", ""),
                "document generation is unavailable")
    fields = {
        "tab_guard": _owned_state(),
        "tab_guard_run": _run_id(),
        "tab_guard_epoch": epoch,
        "tab_guard_target_id": target_id,
        "tab_guard_session_id": requested_session,
        "tab_guard_document_generation": generation,
        "tab_guard_url": context.get("url"),
    }
    return fields


def cdp(method, session_id=None, _response_timeout=DEFAULT_IPC_RESPONSE_TIMEOUT_SECONDS, **params):
    """Raw CDP. cdp('Page.navigate', url='...'), cdp('DOM.getDocument', depth=-1).

    Under BH_TAB_GUARD=1, a call against a tab this run did not open raises
    TabGuardRefused — see the tab guard block above."""
    session_id = _tab_guard_check(method, params, session_id)
    guard_fields = _guard_dispatch_fields(method, params, session_id)
    request = {"method": method, "params": params, "session_id": session_id}
    request.update(guard_fields)
    result = _send(
        request,
        response_timeout=_response_timeout,
    ).get("result", {})
    # Ownership is recorded at the protocol chokepoint, not in new_tab(), so a
    # caller reaching for raw CDP is covered too.
    if method == "Target.createTarget":
        _own_tab(result.get("targetId"))
    elif method == "Target.attachToTarget":
        _remember("sessions", result.get("sessionId"))
    elif method == "Target.detachFromTarget":
        _remember("sessions", params.get("sessionId"), remove=True)
    elif method == "Target.closeTarget" and result.get("success"):
        _remember("tabs", params.get("targetId"), remove=True)
    return result


def _read_meta(meta, **params):
    req = {"meta": meta, **params}
    guarded = _tab_guard_on()
    if guarded:
        run_id = _run_id()
        req["tab_guard"] = _owned_state()
        req["tab_guard_run"] = run_id
        try:
            context = _send({"meta": "guard_epoch"})
        except Exception:
            _refuse(meta, None, "", "metadata could not be read (failing closed)")
        if not isinstance(context, dict) or context.get("tab_guard") != "ok":
            reason = ("daemon must be reloaded for tab guard support" if meta == "set_session"
                      else "metadata could not be read (failing closed)")
            _refuse(meta, None, "", reason)
        epoch = context.get("tab_guard_epoch")
        if not isinstance(epoch, int) or epoch < 0:
            reason = ("daemon must be reloaded for tab guard support" if meta == "set_session"
                      else "metadata could not be read (failing closed)")
            _refuse(meta, None, "", reason)
        req["tab_guard_epoch"] = epoch
    try:
        # An old daemon ignores unknown request fields. Detect it before a
        # set_session could enable domains or disable a foreign session.
        if guarded and meta == "set_session":
            if context.get("tab_guard") != "ok":
                _refuse(meta, None, "", "daemon must be reloaded for tab guard support")
        response = _send(req)
    except TabGuardRefused:
        raise
    except Exception:
        if guarded:
            _refuse(meta, None, "", "metadata could not be read (failing closed)")
        raise
    if guarded and response.get("tab_guard") != "ok":
        _refuse(meta, response.get("target_id"), "", "metadata ownership could not be verified")
    if guarded and meta in {"current_tab", "pending_dialog", "connection_status", "session"}:
        page = response.get("page") if isinstance(response.get("page"), dict) else response
        if not isinstance(page, dict) or "url" not in page:
            _refuse(meta, response.get("target_id"), "", "metadata URL could not be verified")
        url_reason = _url_scope_reason(page.get("url"), required=True)
        if url_reason:
            _refuse(meta, response.get("target_id"), page.get("url", ""), url_reason)
    return response


def drain_events():  return _read_meta("drain_events")["events"]


def _js_snippet(expression, limit=160):
    snippet = expression.strip().replace("\n", "\\n")
    return snippet[:limit - 3] + "..." if len(snippet) > limit else snippet


def _js_exception_description(result, details):
    desc = result.get("description")
    exc = details.get("exception") if details else None
    if not desc and isinstance(exc, dict):
        desc = exc.get("description")
        if desc is None and "value" in exc:
            desc = str(exc["value"])
        if desc is None:
            desc = exc.get("className")
    if not desc and details:
        desc = details.get("text")
    return desc or "JavaScript evaluation failed"


def _decode_unserializable_js_value(value):
    if value == "NaN":
        return math.nan
    if value == "Infinity":
        return math.inf
    if value == "-Infinity":
        return -math.inf
    if value == "-0":
        return -0.0
    if value.endswith("n"):
        return int(value[:-1])
    return value


def _runtime_value(response, expression):
    result = response.get("result", {})
    details = response.get("exceptionDetails")
    if details or result.get("subtype") == "error":
        desc = _js_exception_description(result, details)
        if details:
            line = details.get("lineNumber")
            col = details.get("columnNumber")
            loc = f" at line {line}, column {col}" if line is not None and col is not None else ""
        else:
            loc = ""
        raise RuntimeError(f"JavaScript evaluation failed{loc}: {desc}; expression: {_js_snippet(expression)}")
    if "value" in result:
        return result["value"]
    if "unserializableValue" in result:
        return _decode_unserializable_js_value(result["unserializableValue"])
    return None


def _runtime_evaluate(expression, session_id=None, await_promise=False):
    try:
        r = cdp("Runtime.evaluate", session_id=session_id, expression=expression, returnByValue=True, awaitPromise=await_promise)
    except TimeoutError as e:
        raise RuntimeError(f"Runtime.evaluate timed out; expression: {_js_snippet(expression)}") from e
    return _runtime_value(r, expression)


def _wrap_js_function(expression):
    return f"(function(){{{expression}}})()"


def _is_illegal_return_error(exc):
    return "Illegal return statement" in str(exc)


# --- navigation / page ---
def goto_url(url):
    r = cdp("Page.navigate", url=url)
    if os.environ.get("BH_DOMAIN_SKILLS") != "1":
        return r
    d = (AGENT_WORKSPACE / "domain-skills" / (urlparse(url).hostname or "").removeprefix("www.").split(".")[0])
    return {**r, "domain_skills": sorted(p.name for p in d.rglob("*.md"))[:10]} if d.is_dir() else r

def page_info():
    """{url, title, w, h, sx, sy, pw, ph} — viewport + scroll + page size.

    If a native dialog (alert/confirm/prompt/beforeunload) is open, returns
    {dialog: {type, message, ...}} instead — the page's JS thread is frozen
    until the dialog is handled (see interaction-skills/dialogs.md)."""
    dialog = _read_meta("pending_dialog").get("dialog")
    if dialog:
        return {"dialog": dialog}
    expression = "JSON.stringify({url:location.href,title:document.title,w:innerWidth,h:innerHeight,sx:scrollX,sy:scrollY,pw:document.documentElement.scrollWidth,ph:document.documentElement.scrollHeight})"
    return json.loads(_runtime_evaluate(expression))

# --- input ---
_debug_click_counter = 0

def click_at_xy(x, y, button="left", clicks=1):
    if os.environ.get("BH_DEBUG_CLICKS"):
        global _debug_click_counter
        try:
            from PIL import Image, ImageDraw
            dpr = js("window.devicePixelRatio") or 1
            path = capture_screenshot(str(ipc._TMP / f"debug_click_{_debug_click_counter}.png"))
            img = Image.open(path)
            draw = ImageDraw.Draw(img)
            px, py = int(x * dpr), int(y * dpr)
            r = int(15 * dpr)
            draw.ellipse([px - r, py - r, px + r, py + r], outline="red", width=int(3 * dpr))
            draw.line([px - r - int(5 * dpr), py, px + r + int(5 * dpr), py], fill="red", width=int(2 * dpr))
            draw.line([px, py - r - int(5 * dpr), px, py + r + int(5 * dpr)], fill="red", width=int(2 * dpr))
            img.save(path)
            print(f"[debug_click] saved {path} (x={x}, y={y}, dpr={dpr})")
        except Exception as e:
            print(f"[debug_click] overlay failed: {e}")
        _debug_click_counter += 1
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button=button, clickCount=clicks)
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button=button, clickCount=clicks)

def type_text(text):
    cdp("Input.insertText", text=text)

_SELECT_ALL_MODIFIER = None
def _select_all_modifier():
    """Select-all modifier by the browser's OS (not this process's): 4=Meta on macOS, else 2=Ctrl."""
    global _SELECT_ALL_MODIFIER
    if _SELECT_ALL_MODIFIER is None:
        if _tab_guard_on():
            _SELECT_ALL_MODIFIER = 4 if sys.platform == "darwin" else 2
        else:
            ua = cdp("Browser.getVersion").get("userAgent", "")
            _SELECT_ALL_MODIFIER = 4 if "Mac OS X" in ua or "Macintosh" in ua else 2
    return _SELECT_ALL_MODIFIER

def fill_input(selector, text, clear_first=True, timeout=0.0):
    """Fill a framework-managed input (React controlled, Vue v-model, Ember tracked).

    type_text() uses Input.insertText which bypasses framework event listeners and leaves
    submit buttons disabled. This helper focuses the element, clears it, types via real
    key events, then fires synthetic input+change events so the framework sees the update.

    Raises RuntimeError if the element is not found. Pass timeout>0 to wait for
    late-rendered elements (e.g. after a route change) before typing.
    """
    if timeout > 0:
        if not wait_for_element(selector, timeout=timeout):
            raise RuntimeError(f"fill_input: element not found: {selector!r}")
    focused = js(
        f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
        f"if(!e)return false;e.focus();return true;}})()"
    )
    if not focused:
        raise RuntimeError(f"fill_input: element not found: {selector!r}")
    if clear_first:
        # Dispatch select-all directly — NOT via press_key, which always emits a
        # `char` event for single-char keys. With Ctrl/Cmd held, that `char`
        # makes Chrome treat the input as a printable "a" instead of firing the
        # select-all shortcut, leaving the field uncleared.
        mods = _select_all_modifier()
        select_all = {"key": "a", "code": "KeyA", "modifiers": mods,
                      "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65,
                      "commands": ["SelectAll"]}
        cdp("Input.dispatchKeyEvent", type="rawKeyDown", **select_all)
        cdp("Input.dispatchKeyEvent", type="keyUp",
            **{k: v for k, v in select_all.items() if k != "commands"})
        press_key("Backspace")
    for ch in text:
        press_key(ch)
    js(
        f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
        f"if(!e)return;"
        f"e.dispatchEvent(new Event('input',{{bubbles:true}}));"
        f"e.dispatchEvent(new Event('change',{{bubbles:true}}));}})();"
    )

_KEYS = {  # key → (windowsVirtualKeyCode, code, text)
    "Enter": (13, "Enter", "\r"), "Tab": (9, "Tab", "\t"), "Backspace": (8, "Backspace", ""),
    "Escape": (27, "Escape", ""), "Delete": (46, "Delete", ""), " ": (32, "Space", " "),
    "ArrowLeft": (37, "ArrowLeft", ""), "ArrowUp": (38, "ArrowUp", ""),
    "ArrowRight": (39, "ArrowRight", ""), "ArrowDown": (40, "ArrowDown", ""),
    "Home": (36, "Home", ""), "End": (35, "End", ""),
    "PageUp": (33, "PageUp", ""), "PageDown": (34, "PageDown", ""),
}
# US-layout physical keys for printable ASCII punctuation: char → (code, virtual key).
# `code` names the physical key, so it is layout-independent and never the
# character itself; the virtual key code is the Win32 VK_OEM_* value, which is
# unrelated to ord(char) for everything except A-Z and 0-9.
_PUNCTUATION_KEYS = {
    "`": ("Backquote", 192), "-": ("Minus", 189), "=": ("Equal", 187),
    "[": ("BracketLeft", 219), "]": ("BracketRight", 221), "\\": ("Backslash", 220),
    ";": ("Semicolon", 186), "'": ("Quote", 222), ",": ("Comma", 188),
    ".": ("Period", 190), "/": ("Slash", 191),
}
# Characters a US layout only produces with Shift held, mapped to the unshifted
# character that shares their physical key.
_SHIFTED_CHARS = {
    "~": "`", "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6",
    "&": "7", "*": "8", "(": "9", ")": "0", "_": "-", "+": "=",
    "{": "[", "}": "]", "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".", "?": "/",
}


def _printable_key(char):
    """(code, virtual key, needs_shift) for one printable ASCII char on a US layout.

    None when the character has no US physical key — accented letters, CJK,
    emoji. Those still insert from the char event's text, and inventing a
    keyboard key for them would just be a different wrong answer.
    """
    unshifted = _SHIFTED_CHARS.get(char, char)
    needs_shift = char in _SHIFTED_CHARS or char.isupper()
    if unshifted.isascii() and "a" <= unshifted.lower() <= "z":
        return f"Key{unshifted.upper()}", ord(unshifted.upper()), needs_shift
    if unshifted.isdigit() and unshifted.isascii():
        return f"Digit{unshifted}", ord(unshifted), needs_shift
    if unshifted in _PUNCTUATION_KEYS:
        code, vk = _PUNCTUATION_KEYS[unshifted]
        return code, vk, needs_shift
    return None


def press_key(key, modifiers=0):
    """Modifiers bitfield: 1=Alt, 2=Ctrl, 4=Meta(Cmd), 8=Shift.

    Named keys (Enter, Tab, Arrow*, Backspace, ...) and printable characters alike
    carry the physical `code` and virtual key code a real US keyboard sends, so
    listeners reading e.key, e.code and e.keyCode all agree. A character that
    needs Shift on that layout (uppercase, !@#$...) sets the Shift modifier too,
    unless the caller is already composing a shortcut with Alt/Ctrl/Meta — there,
    the caller's intent wins over the physical truth.
    """
    if key in _KEYS:
        vk, code, text = _KEYS[key]
    elif len(key) == 1:
        text = key
        resolved = _printable_key(key)
        if resolved:
            code, vk, needs_shift = resolved
            if needs_shift and not modifiers & (1 | 2 | 4):
                modifiers |= 8
        else:
            code, vk = "", 0
    else:
        vk, code, text = 0, key, ""
    base = {"key": key, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
    shortcut_modifiers = modifiers & (1 | 2 | 4)  # Alt/Ctrl/Meta turn single keys into shortcuts.
    printable_char = len(key) == 1 and bool(text) and not shortcut_modifiers
    cdp("Input.dispatchKeyEvent", type="keyDown", **base, **({} if printable_char or not text else {"text": text}))
    if printable_char:
        cdp("Input.dispatchKeyEvent", type="char", text=text, **{k: v for k, v in base.items() if k != "text"})
    cdp("Input.dispatchKeyEvent", type="keyUp", **base)

def scroll(x, y, dy=-300, dx=0):
    cdp("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=dx, deltaY=dy)


# --- visual ---
def capture_screenshot(path=None, full=False, max_dim=None):
    """Save a PNG of the current viewport. Set max_dim=1800 on a 2× display to
    keep the file under the 2000px-per-side limit some image-aware LLMs enforce."""
    path = path or str(ipc._TMP / "shot.png")
    try:
        r = cdp(
            "Page.captureScreenshot",
            _response_timeout=SCREENSHOT_IPC_RESPONSE_TIMEOUT_SECONDS,
            format="png",
            captureBeyondViewport=full,
        )
    except _IPCResponseTimeout as e:
        raise RuntimeError(
            f"Page.captureScreenshot timed out after {SCREENSHOT_IPC_RESPONSE_TIMEOUT_SECONDS:g}s"
        ) from e
    open(path, "wb").write(base64.b64decode(r["data"]))
    if max_dim:
        from PIL import Image
        img = Image.open(path)
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim))
            img.save(path)
    return path


# --- tabs ---
def _is_agent_startup_placeholder(title, url):
    url = str(url or "")
    return str(title or "").startswith("Starting agent ") and (
        url in ("", "about:blank") or url.startswith("about:blank#")
    )


def list_tabs(include_chrome=True):
    out = []
    for t in cdp("Target.getTargets")["targetInfos"]:
        if t["type"] != "page": continue
        url = t.get("url", "")
        if _is_agent_startup_placeholder(t.get("title", ""), url): continue
        if not include_chrome and url.startswith(INTERNAL): continue
        out.append({
            "targetId": t["targetId"],
            "target_id": t["targetId"],
            "title": t.get("title", ""),
            "url": url,
        })
    return out

def current_tab():
    r = _read_meta("current_tab")
    return {
        "targetId": r["targetId"],
        "target_id": r["targetId"],
        "url": r["url"],
        "title": r["title"],
    }

def _mark_tab():
    """Prepend horse emoji to tab title so the user can see which tab the agent controls."""
    if os.environ.get("BH_TAB_MARKER", "").strip().lower() in {"0", "false", "no", "off"}:
        return
    try:
        cdp("Runtime.evaluate", expression="if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title")
    except TabGuardRefused:
        if _tab_guard_on():
            raise
    except Exception:
        pass


def _guard_can_unmark_current_tab():
    """Only remove a marker after proving the current tab is ours and safe."""
    if not _tab_guard_on():
        return True
    try:
        context = _guard_context_request()
        if not isinstance(context, dict):
            return False
        target_id, session_id = context.get("target_id"), context.get("session_id")
        if target_id not in _owned_ids() or session_id not in _owned_sessions():
            return False
        return _url_scope_reason(context.get("url"), required=True) is None
    except Exception:
        return False

def _target_id(target):
    """Accept a raw target id or a tab dict returned by the helpers."""
    return (target.get("targetId") or target.get("target_id")) if isinstance(target, dict) else target

def activate_tab(target):
    """Make a target the visible Chrome tab.

    This is intentionally separate from switch_tab(): attaching the agent to a
    target does not require taking over the user's visible Chrome tab.
    """
    target_id = _target_id(target)
    cdp("Target.activateTarget", targetId=target_id)
    return target_id

def switch_tab(target, activate=False):
    """Attach the agent without changing Chrome's visible tab by default.

    Pass activate=True only when Chrome must visibly show the target. The horse
    marker still moves to the attached target so the user can find it.
    """
    # Accept either a raw targetId string or the dict returned by current_tab() / list_tabs(),
    # so `switch_tab(current_tab())` works without a manual ["targetId"] dance.
    target_id = _target_id(target)
    if _tab_guard_on() and isinstance(target, dict):
        url_reason = _url_scope_reason(target.get("url"), required=True)
        if url_reason:
            _refuse("switch_tab", target_id, target.get("url", ""), url_reason)
    # Unmark old tab. Horse emoji is a surrogate pair in JS UTF-16 strings (2 code units),
    # plus the trailing space = 3 code units, so slice(3) cleanly removes the prefix.
    if _guard_can_unmark_current_tab():
        try:
            cdp("Runtime.evaluate", expression="if(document.title.startsWith('\U0001F434 '))document.title=document.title.slice(3)")
        except TabGuardRefused:
            if _tab_guard_on():
                raise
        except Exception:
            pass
    if activate:
        activate_tab(target_id)
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"]
    _read_meta("set_session", session_id=sid, target_id=target_id)
    _mark_tab()
    return sid

def _may_reuse_attached_tab():
    """Whether new_tab() may navigate the already-attached tab instead of
    creating one.

    Under the tab guard, only when this run opened that tab: a blank tab is
    still SOMEONE'S tab, and reusing it is the drift the guard exists to stop.
    Unreadable attached tab -> do not reuse, which just means creating a fresh
    tab, so failing closed here costs nothing.
    """
    if not _tab_guard_on():
        return True
    try:
        return current_tab().get("targetId") in _owned_ids()
    except Exception:
        return False


def new_tab(url="about:blank"):
    # Always create blank, then goto: passing url to createTarget races with
    # attach, so the brief about:blank is "complete" by the time the caller
    # polls and wait_for_load() returns before navigation actually starts.
    if url != "about:blank" and _may_reuse_attached_tab():
        try:
            cur = current_tab()
            cur_url = cur.get("url") or ""
            # Reuse attached tab when it's blank
            if (
                cur_url in ("", "about:blank", "data:text/html,")
                or cur_url.startswith("about:blank#")
                or cur_url.startswith(("chrome://newtab", "chrome://new-tab-page", "edge://newtab", "about:newtab"))
            ):
                goto_url(url)
                return cur.get("targetId") or cur.get("target_id")
        except Exception:
            pass
    tid = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
    switch_tab(tid)
    if url != "about:blank":
        goto_url(url)
    return tid

def close_tab(target=None):
    """Close a tab. If `target` is omitted, closes the currently attached tab.
    Accepts a raw targetId string or a dict from list_tabs()/current_tab()."""
    target_id = _target_id(target)
    if target_id is None:
        target_id = current_tab()["targetId"]
    cdp("Target.closeTarget", targetId=target_id)


def ensure_real_tab():
    """Switch to a real user tab if current is chrome:// / internal / stale."""
    tabs = list_tabs(include_chrome=False)
    if not tabs:
        return None
    try:
        cur = current_tab()
        if cur["url"] and not cur["url"].startswith(INTERNAL):
            return cur
    except Exception:
        pass
    switch_tab(tabs[0]["targetId"])
    return tabs[0]

def iframe_target(url_substr):
    """First iframe target whose URL contains `url_substr`. Use with js(..., target_id=...)."""
    for t in cdp("Target.getTargets")["targetInfos"]:
        if t["type"] == "iframe" and url_substr in t.get("url", ""):
            return t["targetId"]
    return None


# --- utility ---
def wait(seconds=1.0):
    time.sleep(seconds)

def wait_for_load(timeout=15.0):
    """Poll document.readyState == 'complete' or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if js("document.readyState") == "complete": return True
        time.sleep(0.3)
    return False

def wait_for_element(selector, timeout=10.0, visible=False):
    """Poll until querySelector(selector) exists in the DOM, or timeout.

    wait_for_load() misses SPAs — the document is 'complete' before the framework renders.
    Use this after actions that trigger async rendering (route changes, data fetches).
    Set visible=True to also require the element to be non-hidden and in-layout.
    Returns True if found, False on timeout.
    """
    if visible:
        # checkVisibility walks the ancestor chain and respects display:none /
        # visibility:hidden / opacity:0 on parents, which a getComputedStyle
        # check on the element alone misses (it returns the descendant's own
        # style, not the inherited "is this rendered" state). Falls back to
        # the per-element CSS check on older Chrome that lacks checkVisibility.
        check = (
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            f"if(!e)return false;"
            f"if(typeof e.checkVisibility==='function')"
            f"return e.checkVisibility({{checkOpacity:true,checkVisibilityCSS:true}});"
            f"const s=getComputedStyle(e);"
            f"return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'}})()"
        )
    else:
        check = f"!!document.querySelector({json.dumps(selector)})"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if js(check): return True
        time.sleep(0.3)
    return False

def wait_for_network_idle(timeout=10.0, idle_ms=500):
    """Wait until all in-flight requests finish and no Network.* events arrive for idle_ms ms.

    Useful after form submits, SPA route transitions, and any action that triggers
    XHR/fetch without a visible DOM change. Builds on drain_events() — no daemon changes.
    Returns True if idle window reached, False on timeout.

    Events are filtered to the active session — a previously-attached background
    tab (e.g. a polling/SSE page the agent switched away from) keeps emitting
    Network events into the daemon's global event buffer; without this filter
    they would poison the idle check on the current tab.
    """
    deadline = time.time() + timeout
    last_activity = time.time()
    inflight = set()
    active_session = _read_meta("session").get("session_id")
    while time.time() < deadline:
        for e in drain_events():
            if e.get("session_id") != active_session:
                continue
            method = e.get("method", "")
            params = e.get("params", {})
            if method == "Network.requestWillBeSent":
                inflight.add(params.get("requestId"))
                last_activity = time.time()
            elif method in ("Network.loadingFinished", "Network.loadingFailed"):
                inflight.discard(params.get("requestId"))
                last_activity = time.time()
            elif method.startswith("Network."):
                last_activity = time.time()
        if not inflight and (time.time() - last_activity) * 1000 >= idle_ms:
            return True
        time.sleep(0.1)
    return False

def js(expression, target_id=None):
    """Run JS in the attached tab (default) or inside an iframe target (via iframe_target()).

    Expressions are evaluated as-is first. If Chrome reports an illegal top-level
    `return`, the snippet is retried inside a function wrapper, so both
    `document.title` and `const x = 1; return x` work without mis-wrapping nested
    functions that contain their own returns.
    """
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"] if target_id else None
    try:
        result = _js_evaluate(expression, sid)
    except BaseException:
        # Keep the evaluation error; a detach failure here must not replace it.
        if sid:
            try:
                _detach_iframe_session(sid)
            except BaseException:
                pass
        raise
    if sid:
        _detach_iframe_session(sid)
    return result


def _js_evaluate(expression, sid):
    try:
        return _runtime_evaluate(expression, session_id=sid, await_promise=True)
    except RuntimeError as e:
        if _is_illegal_return_error(e):
            return _runtime_evaluate(_wrap_js_function(expression), session_id=sid, await_promise=True)
        raise


def _detach_iframe_session(sid):
    """Release the session js(target_id=...) attached so polling loops do not
    accumulate one live session (and one event stream) per call. A session that
    Chrome already dropped (iframe navigated or closed) is not a leak."""
    try:
        cdp("Target.detachFromTarget", sessionId=sid)
    except Exception as e:
        message = str(e).lower()
        if "no session with given id" in message or "session with given id not found" in message:
            return
        raise


_KC = {"Enter": 13, "Tab": 9, "Escape": 27, "Backspace": 8, " ": 32, "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40}


def dispatch_key(selector, key="Enter", event="keypress"):
    """Dispatch a DOM KeyboardEvent on the matched element.

    Use this when a site reacts to synthetic DOM key events on an element more reliably
    than to raw CDP input events.
    """
    kc = _KC.get(key, ord(key) if len(key) == 1 else 0)
    js(
        f"(()=>{{const e=document.querySelector({json.dumps(selector)});if(e){{e.focus();e.dispatchEvent(new KeyboardEvent({json.dumps(event)},{{key:{json.dumps(key)},code:{json.dumps(key)},keyCode:{kc},which:{kc},bubbles:true}}));}}}})()"
    )

def upload_file(selector, path):
    """Set files on a file input via CDP DOM.setFileInputFiles. `path` is an absolute filepath (use tempfile.mkstemp if needed)."""
    doc = cdp("DOM.getDocument", depth=-1)
    nid = cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)["nodeId"]
    if not nid: raise RuntimeError(f"no element for {selector}")
    cdp("DOM.setFileInputFiles", files=[path] if isinstance(path, str) else list(path), nodeId=nid)

def http_get(url, headers=None, timeout=20.0):
    """Pure HTTP — no browser. Use for static pages / APIs. Wrap in ThreadPoolExecutor for bulk.

    When BROWSER_USE_API_KEY is set, routes through the fetch-use proxy (handles bot
    detection, residential proxies, retries). Falls back to local urllib otherwise."""
    if os.environ.get("BROWSER_USE_API_KEY"):
        try:
            from fetch_use import fetch_sync
            return fetch_sync(url, headers=headers, timeout_ms=int(timeout * 1000)).text
        except ImportError:
            pass
    import gzip
    h = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
    if headers: h.update(headers)
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip": data = gzip.decompress(data)
        return data.decode()


# Imported at the bottom so recorder's own `from . import helpers` sees a
# fully-defined module. Exposes the recording helpers via `from .helpers import *`.
from .recorder import start_recording, stop_recording, recording_dir


def _load_agent_helpers():
    p = AGENT_WORKSPACE / "agent_helpers.py"
    if not p.exists():
        return
    spec = importlib.util.spec_from_file_location("browser_harness_agent_helpers", p)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if name.startswith("_"):
            continue
        globals()[name] = value


_load_agent_helpers()
