"""Browser control via CDP.

Core helpers live here. Agent-editable helpers live in
BH_AGENT_WORKSPACE/agent_helpers.py.
"""
import base64, importlib.util, json, math, os, time, urllib.request
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
    if "error" in r: raise RuntimeError(r["error"])
    return r


def cdp(method, session_id=None, _response_timeout=DEFAULT_IPC_RESPONSE_TIMEOUT_SECONDS, **params):
    """Raw CDP. cdp('Page.navigate', url='...'), cdp('DOM.getDocument', depth=-1)."""
    return _send(
        {"method": method, "params": params, "session_id": session_id},
        response_timeout=_response_timeout,
    ).get("result", {})


def drain_events():  return _send({"meta": "drain_events"})["events"]


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
    dialog = _send({"meta": "pending_dialog"}).get("dialog")
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
_OPENED_TABS = set()
_REUSED_BLANK_TABS = {}
_KEEP_OPENED_TABS = False
_RETURN_TAB_ID = None


def _reset_tab_ownership():
    """Reset process-local ownership before and after one CLI invocation."""
    global _KEEP_OPENED_TABS, _RETURN_TAB_ID
    _OPENED_TABS.clear()
    _REUSED_BLANK_TABS.clear()
    _KEEP_OPENED_TABS = False
    _RETURN_TAB_ID = None


def _blank_restore_url(url):
    url = str(url or "")
    if url.startswith(("chrome://newtab", "chrome://new-tab-page", "edge://newtab", "about:newtab")):
        return "about:blank"
    return url or "about:blank"


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
    r = _send({"meta": "current_tab"})
    return {
        "targetId": r["targetId"],
        "target_id": r["targetId"],
        "url": r["url"],
        "title": r["title"],
    }

def _mark_tab():
    """Prepend horse emoji to tab title so the user can see which tab the agent controls."""
    try: cdp("Runtime.evaluate", expression="if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title")
    except Exception: pass

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
    # Unmark old tab. Horse emoji is a surrogate pair in JS UTF-16 strings (2 code units),
    # plus the trailing space = 3 code units, so slice(3) cleanly removes the prefix.
    try: cdp("Runtime.evaluate", expression="if(document.title.startsWith('\U0001F434 '))document.title=document.title.slice(3)")
    except Exception: pass
    if activate:
        activate_tab(target_id)
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"]
    _send({"meta": "set_session", "session_id": sid, "target_id": target_id})
    _mark_tab()
    return sid


DEFAULT_MAX_TABS = 15
_TAB_CAP_SKIP = (
    "chrome://",
    "chrome-untrusted://",
    "edge://",
    "devtools://",
    "chrome-extension://",
)


def _reap_tabs(keep_id):
    """Keep automation browsers bounded by closing their oldest work tabs."""
    global _RETURN_TAB_ID
    try:
        max_tabs = int(os.environ.get("BH_MAX_TABS", str(DEFAULT_MAX_TABS)))
    except ValueError:
        max_tabs = DEFAULT_MAX_TABS
    if max_tabs <= 0:
        return

    try:
        endpoint = _send({"meta": "http_endpoint"}).get("endpoint")
        if not endpoint:
            return
        with urllib.request.urlopen(f"{endpoint.rstrip('/')}/json/list", timeout=2) as response:
            pages = [
                target
                for target in json.loads(response.read())
                if target.get("type") == "page"
                and not target.get("url", "").startswith(_TAB_CAP_SKIP)
            ]
    except Exception:
        return

    excess = len(pages) - max_tabs
    if excess <= 0:
        return
    for target in reversed(pages):
        target_id = target.get("id")
        if excess <= 0:
            break
        if not target_id or target_id == keep_id:
            continue
        if _close_target_with_retry(target_id) is not None:
            continue
        _OPENED_TABS.discard(target_id)
        _REUSED_BLANK_TABS.pop(target_id, None)
        if _RETURN_TAB_ID == target_id:
            _RETURN_TAB_ID = None
        excess -= 1


def new_tab(url="about:blank"):
    global _RETURN_TAB_ID
    # Always create blank, then goto: passing url to createTarget races with
    # attach, so the brief about:blank is "complete" by the time the caller
    # polls and wait_for_load() returns before navigation actually starts.
    cur = None
    try:
        cur = current_tab()
        cur_url = cur.get("url") or ""
        if url != "about:blank":
            # Reuse attached tab when it's blank
            if (
                cur_url in ("", "about:blank", "data:text/html,")
                or cur_url.startswith("about:blank#")
                or cur_url.startswith(("chrome://newtab", "chrome://new-tab-page", "edge://newtab", "about:newtab"))
            ):
                target_id = cur.get("targetId") or cur.get("target_id")
                _REUSED_BLANK_TABS.setdefault(target_id, _blank_restore_url(cur_url))
                _reap_tabs(target_id)
                goto_url(url)
                return target_id
    except Exception:
        pass
    if cur:
        current_id = cur.get("targetId") or cur.get("target_id")
        if current_id and current_id not in _OPENED_TABS and _RETURN_TAB_ID is None:
            _RETURN_TAB_ID = current_id
    tid = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
    _OPENED_TABS.add(tid)
    switch_tab(tid)
    _reap_tabs(tid)
    if url != "about:blank":
        goto_url(url)
    return tid


def opened_tabs():
    """Return target IDs created by new_tab() in this CLI process."""
    return list(_OPENED_TABS)


def keep_opened_tabs(keep=True):
    """Opt out of automatic cleanup for tabs owned by this CLI process."""
    global _KEEP_OPENED_TABS
    _KEEP_OPENED_TABS = keep


def _restore_reused_blank_tabs():
    restored = []
    failures = []
    for target_id, original_url in list(_REUSED_BLANK_TABS.items()):
        try:
            switch_tab(target_id)
            goto_url(original_url or "about:blank")
            restored.append(target_id)
            _REUSED_BLANK_TABS.pop(target_id, None)
        except Exception as exc:
            failures.append((target_id, exc))
    return restored, failures


def _move_to_keeper(target_ids):
    """Move off an owned target before it closes; return protected IDs and failures."""
    try:
        current_id = current_tab()["targetId"]
    except Exception as exc:
        # Without the active target ID, any owned target could be the daemon's
        # current session. Fail closed instead of risking a stale attachment.
        return set(target_ids), [("current target", exc)]
    if current_id not in target_ids:
        return set(), []

    if _RETURN_TAB_ID and _RETURN_TAB_ID not in target_ids:
        try:
            switch_tab(_RETURN_TAB_ID)
            return set(), []
        except Exception:
            # The original tab may have been closed while the task was running.
            # Fall back to a fresh neutral target before closing the owned one.
            pass

    keeper_id = None
    try:
        keeper_id = cdp("Target.createTarget", url="about:blank")["targetId"]
        switch_tab(keeper_id)
        # The keeper becomes the daemon's neutral anchor. It is intentionally
        # not owned by this invocation and can be reused by the next new_tab().
    except Exception as exc:
        failures = [("keeper handoff", exc)]
        # switch_tab() can fail after the daemon accepted set_session. Read the
        # daemon's acknowledged target before deciding whether the keeper is
        # safe to close; ambiguity fails closed and leaves the neutral page.
        keeper_attached = None
        if keeper_id:
            try:
                keeper_attached = current_tab()["targetId"] == keeper_id
            except Exception:
                pass
        if keeper_id and keeper_attached is False:
            close_error = _close_target_with_retry(keeper_id)
            if close_error is not None:
                failures.append((keeper_id, close_error))
        return {current_id}, failures
    return set(), []


def _cleanup_error_message(failures):
    details = ", ".join(f"{target}: {error}" for target, error in failures)
    return f"tab cleanup incomplete ({details})"


def _close_target_with_retry(target_id):
    last_error = None
    for _ in range(2):
        try:
            result = cdp("Target.closeTarget", targetId=target_id)
            if result.get("success", True):
                return None
            last_error = RuntimeError("Target.closeTarget returned false")
        except Exception as exc:
            last_error = exc
    return last_error


def close_opened_tabs(force=False):
    """Close created tabs and restore blank tabs reused by this CLI process."""
    global _RETURN_TAB_ID
    if _KEEP_OPENED_TABS and not force:
        # Keeping means hands off every tab this invocation touched, not just
        # ones it created via Target.createTarget. new_tab() usually reuses
        # the current blank tab instead of creating a new one (the daemon is
        # commonly parked on a blank keeper between invocations), so most
        # "kept" tabs in practice are reused-blank ones. Restoring them to
        # blank here would silently defeat keep_opened_tabs() for exactly the
        # common case a caller relies on it for.
        _OPENED_TABS.clear()
        _REUSED_BLANK_TABS.clear()
        _RETURN_TAB_ID = None
        return []

    _, failures = _restore_reused_blank_tabs()

    target_ids = set(_OPENED_TABS)
    if not target_ids:
        if failures:
            raise RuntimeError(_cleanup_error_message(failures))
        _RETURN_TAB_ID = None
        return []

    protected_ids, handoff_failures = _move_to_keeper(target_ids)
    failures.extend(handoff_failures)
    target_ids.difference_update(protected_ids)

    closed = []
    for target_id in list(target_ids):
        last_error = _close_target_with_retry(target_id)
        if last_error is None:
            closed.append(target_id)
            _OPENED_TABS.discard(target_id)
        else:
            failures.append((target_id, last_error))

    if closed:
        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                remaining = {tab["targetId"] for tab in list_tabs(include_chrome=True)}
            except Exception:
                break
            if not remaining.intersection(closed):
                break
            time.sleep(0.05)
    if failures:
        raise RuntimeError(_cleanup_error_message(failures))
    _RETURN_TAB_ID = None
    return closed

def close_tab(target=None):
    """Close a tab. If `target` is omitted, closes the currently attached tab.
    Accepts a raw targetId string or a dict from list_tabs()/current_tab()."""
    global _RETURN_TAB_ID
    target_id = _target_id(target)
    if target_id is None:
        target_id = current_tab()["targetId"]
    result = cdp("Target.closeTarget", targetId=target_id)
    if not result.get("success", True):
        raise RuntimeError("Target.closeTarget returned false")
    _OPENED_TABS.discard(target_id)
    _REUSED_BLANK_TABS.pop(target_id, None)
    if _RETURN_TAB_ID == target_id:
        _RETURN_TAB_ID = None


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
    active_session = _send({"meta": "session"}).get("session_id")
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
        return _runtime_evaluate(expression, session_id=sid, await_promise=True)
    except RuntimeError as e:
        if _is_illegal_return_error(e):
            return _runtime_evaluate(_wrap_js_function(expression), session_id=sid, await_promise=True)
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
