"""Browser control via CDP.

Core helpers live here. Agent-editable helpers live in
BH_AGENT_WORKSPACE/agent_helpers.py.
"""
import base64, importlib.util, json, math, os, random, time, urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import _ipc as ipc
from . import paths
from . import pointer as _pointer


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
    _mouse(x, y, press=(button, clicks))

def move_mouse(x, y):
    """Move the pointer to (x, y) as a hand does, from where it last was: a straight spring hop for a
    short move, a glide along a curve for a long one (pointer.py), as 25-45 real mouseMoved events.

    click_at_xy() travels the same way first: Akamai only validates a session (_abck ~0~) that saw
    enough pointer travel, and a click that teleports onto its target does not count."""
    _mouse(x, y)

def _mouse(x, y, press=None):
    """Travel to (x, y), then press and release when press=(button, clicks). The daemon sends the
    events at their times without waiting for each answer, so a click costs its travel time plus one
    round trip, not a round trip per event."""
    try:
        state = _send({"meta": "pointer"})  # the daemon remembers the pointer across CLI calls
    except Exception:
        state = {}  # daemon predates pointer tracking
    view = state.get("viewport")
    if not view:
        try: view = js("[innerWidth, innerHeight, devicePixelRatio]")
        except Exception: view = None
    w, h, dpr = (view + [1])[:3] if isinstance(view, list) and len(view) >= 2 else (max(x, 800), max(y, 600), 1)
    bounds = (0.0, 0.0, max(float(w), x + 1.0), max(float(h), y + 1.0))
    start = state.get("pointer") or (
        _pointer.clamp(x + random.uniform(-150, 150), 0, bounds[2]), _pointer.clamp(y + random.uniform(-100, 100), 0, bounds[3]))
    # Draw the macOS Harness arrow on the page's DevTools overlay (live view, not the DOM): default on cloud.
    draw = "browser_kind" in state and os.environ.get(
        "BH_POINTER", "1" if state["browser_kind"] == "cloud" else "0").strip().lower() not in ("0", "false", "no", "off")
    events = [{"at": t, "type": "mouseMoved", "x": px, "y": py, **({"quad": _pointer.arrow(px, py, shape, dpr=dpr)} if draw else {})}
              for t, px, py, shape in _pointer.samples(tuple(start), (x, y), bounds)]
    if press:
        button, clicks = press
        # Press on arrival, as macOS Harness does: the spring's soft landing is the pause before it.
        t = (events[-1]["at"] if events else 0.0) + random.uniform(0.01, 0.03)
        pulse = [{"at": t + dt, "quad": _pointer.arrow(x, y, press=k, dpr=dpr)} for dt, k in _pointer.PRESS[1:]] if draw else []
        for kind, hold in (("mousePressed", random.uniform(0.03, 0.08)), ("mouseReleased", 0.0)):
            events.append({"at": t, "type": kind, "x": x, "y": y, "button": button, "clickCount": clicks})
            t += hold
        events = sorted(events + pulse, key=lambda e: e["at"])
    if not events:
        return
    if "viewport" in state:  # daemon with meta=mouse
        req = {"meta": "mouse", "events": events}
        try:
            _send(req, response_timeout=events[-1]["at"] + 10)
        except RuntimeError as e:
            if "Session with given id not found" not in str(e): raise
            cdp("Runtime.evaluate", expression="1")  # the daemon re-attaches the tab; no event reached the old one
            _send(req, response_timeout=events[-1]["at"] + 10)
        return
    t0 = time.time()  # older daemon: one call per event, on the same schedule
    for e in (e for e in events if "type" in e):
        e = {k: v for k, v in e.items() if k != "quad"}
        delay = t0 + e.pop("at") - time.time()
        if delay > 0: time.sleep(delay)
        cdp("Input.dispatchMouseEvent", **e)

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
    submit buttons disabled. This helper focuses the element with a real click (click_at_xy),
    clears it, types via real key events, then fires synthetic input+change events so the
    framework sees the update. JS focus() is only the fallback when the click did not focus it.

    Raises RuntimeError if the element is not found. Pass timeout>0 to wait for
    late-rendered elements (e.g. after a route change) before typing.
    """
    if timeout > 0:
        if not wait_for_element(selector, timeout=timeout):
            raise RuntimeError(f"fill_input: element not found: {selector!r}")
    q = f"document.querySelector({json.dumps(selector)})"
    # The field's centre, and whether a click there lands on the field (or its own label or wrapper),
    # not on a cookie banner or modal covering it: clicking that could press a button on it.
    box = js(
        f"(()=>{{const e={q};if(!e)return null;e.scrollIntoView({{block:'center',behavior:'instant'}});"
        f"const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,h=document.elementFromPoint(x,y);"
        f"const own=!!h&&(h===e||e.contains(h)||h.contains(e)||(h.closest('label')||{{}}).control===e"
        f"||!!(e.parentElement&&e.parentElement.contains(h)));"
        f"return [x,y,r.width*r.height,own];}})()"
    )
    if not box:
        raise RuntimeError(f"fill_input: element not found: {selector!r}")
    if box[2] and (len(box) < 4 or box[3]):
        click_at_xy(box[0], box[1])  # trusted press: Akamai 403s a submit whose page never saw one
    # JS focus only if the click did not focus it. Appending (clear_first=False): put the caret at the
    # end, where focus() leaves it, not where the click landed (inputs like type=email have no caret API).
    end = "" if clear_first else "try{const n=(e.value||'').length;e.setSelectionRange(n,n)}catch(_){}"
    js(f"(()=>{{const e={q},a=document.activeElement;if(!e)return;if(a!==e&&!e.contains(a))e.focus();{end}}})()")
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
    r = _send({"meta": "current_tab"})
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

def new_tab(url="about:blank"):
    # Always create blank, then goto: passing url to createTarget races with
    # attach, so the brief about:blank is "complete" by the time the caller
    # polls and wait_for_load() returns before navigation actually starts.
    if url != "about:blank":
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

def _page_ready(timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if js("document.readyState") == "complete": return True
        time.sleep(0.3)
    return False

def wait_for_load(timeout=15.0):
    """Poll document.readyState == 'complete' or timeout. On a cloud browser whose captcha solver
    is mid-solve on this tab, also wait for the solve (wait_for_captcha_solver, up to 60 s on top of
    timeout: a solve outlasts a page load) and poll the reloaded page again within timeout."""
    if not _page_ready(timeout): return False
    done, solved = _captcha_wait(60.0)
    return done and (not solved or _page_ready(timeout))

# Captcha widgets and challenge scripts the cloud solver handles (reCAPTCHA, hCaptcha, DataDome,
# AWS WAF, Cloudflare, Arkose, PerimeterX). Only pages with one wait for a solve that has not started yet.
_CAPTCHA_MARKERS = "!!document.querySelector('[src*=captcha],[src*=\"challenges.cloudflare.com\"],[src*=arkoselabs],#px-captcha')"
# Right after a load, how long a page must show no captcha widget before the solver start grace is
# skipped: a widget a framework renders late still makes the wait. Every cloud wait_for_load pays it.
CAPTCHA_ABSENT_S = 0.5

def wait_for_captcha_solver(timeout=60.0):
    """Wait while Browser Use Cloud's captcha solver is mid-solve on this tab (its
    BrowserUse.captchaSolverStarted event has no Finished yet), or may still start one: on a page
    with a captcha it starts up to ~2 s after the load. Don't click, type or navigate meanwhile.
    True once no solve runs (at once on local Chrome), False if one still runs after timeout."""
    return _captcha_wait(timeout)[0]

def _captcha_wait(timeout):
    """(no solve runs now, a solve ran or a widget showed while waiting)."""
    deadline, waited = time.time() + timeout, False
    while True:
        try:
            state = _send({"meta": "captcha_solving"})
        except RuntimeError:
            return True, waited  # daemon predates solver tracking: browser-harness --reload
        if state.get("seconds") is None:
            grace = state.get("grace") or 0.0
            if not grace: return True, waited
            # Watch the page for a widget, polling only the page: go on once none showed for
            # CAPTCHA_ABSENT_S (or the rest of the grace). A widget keeps the wait for its solve.
            watch_end = time.time() + min(grace, CAPTCHA_ABSENT_S)
            while True:
                try: marked = bool(js(_CAPTCHA_MARKERS))
                except RuntimeError: marked = True  # page mid-navigation: assume it may have one
                if marked or time.time() >= watch_end: break
                time.sleep(0.05)
            if not marked: return True, waited
        waited = True
        if time.time() >= deadline: return False, waited
        time.sleep(0.25)

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
