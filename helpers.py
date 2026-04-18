"""Browser control via CDP. Read, edit, extend — this file is yours."""
import base64, json, os, socket, time, urllib.request
from pathlib import Path


def _load_env():
    p = Path(__file__).parent / ".env"
    if not p.exists(): return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
_load_env()

NAME = os.environ.get("BU_NAME", "default")
SOCK = f"/tmp/bu-{NAME}.sock"
PID = f"/tmp/bu-{NAME}.pid"
INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")
BU_API = "https://api.browser-use.com/api/v3"


def _send(req):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK)
    s.sendall((json.dumps(req) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(1 << 20)
        if not chunk: break
        data += chunk
    s.close()
    r = json.loads(data)
    if "error" in r: raise RuntimeError(r["error"])
    return r


def cdp(method, session_id=None, **params):
    """Raw CDP. cdp('Page.navigate', url='...'), cdp('DOM.getDocument', depth=-1)."""
    return _send({"method": method, "params": params, "session_id": session_id}).get("result", {})


def drain_events():  return _send({"meta": "drain_events"})["events"]
def get_session():   return _send({"meta": "session"})["session_id"]
def set_session(s):  return _send({"meta": "set_session", "session_id": s})
def shutdown():      return _send({"meta": "shutdown"})


# --- daemon lifecycle (socket IS the lock; one per BU_NAME) ---
def _paths(name): n = name or NAME; return f"/tmp/bu-{n}.sock", f"/tmp/bu-{n}.pid"

def daemon_alive(name=None):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(1)
        s.connect(_paths(name)[0]); s.close(); return True
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout):
        return False

def ensure_daemon(wait=60.0, name=None, env=None):
    """Idempotent. `env` is merged into the child process env."""
    if daemon_alive(name): return
    import subprocess
    e = {**os.environ, **({"BU_NAME": name} if name else {}), **(env or {})}
    subprocess.Popen(["uv", "run", "daemon.py"], cwd=os.path.dirname(os.path.abspath(__file__)),
                     env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.time() + wait
    while time.time() < deadline:
        if daemon_alive(name): return
        time.sleep(0.2)
    raise RuntimeError(f"daemon {name or NAME} didn't come up — check /tmp/bu-{name or NAME}.log")

def kill_daemon(name=None):
    """Graceful shutdown, wait up to 15s for finally-block cleanup (remote stop), then SIGTERM."""
    import signal
    sock, pid_path = _paths(name)
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(5)
        s.connect(sock); s.sendall(b'{"meta":"shutdown"}\n'); s.recv(1024); s.close()
    except Exception: pass
    try: pid = int(open(pid_path).read())
    except (FileNotFoundError, ValueError): pid = None
    if pid:
        for _ in range(75):
            try: os.kill(pid, 0); time.sleep(0.2)
            except ProcessLookupError: break
        else:
            try: os.kill(pid, signal.SIGTERM)
            except ProcessLookupError: pass
    for f in (sock, pid_path):
        try: os.unlink(f)
        except FileNotFoundError: pass


# --- Browser Use cloud (remote browsers) ---
# https://docs.browser-use.com/cloud/api-v3/browsers/create-browser-session
def _bu(path, method, body=None):
    k = os.environ.get("BROWSER_USE_API_KEY")
    if not k: raise RuntimeError("BROWSER_USE_API_KEY missing — see .env.example")
    req = urllib.request.Request(f"{BU_API}{path}", method=method,
        data=(json.dumps(body).encode() if body is not None else None),
        headers={"X-Browser-Use-API-Key": k, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")

def browser_use_create(**params):
    return _bu("/browsers", "POST", params)

def browser_use_stop(browser_id):
    return _bu(f"/browsers/{browser_id}", "PATCH", {"action": "stop"})

def cdp_ws_from_url(cdp_url):
    return json.loads(urllib.request.urlopen(f"{cdp_url}/json/version", timeout=15).read())["webSocketDebuggerUrl"]

def start_remote_daemon(name="remote", **create_kwargs):
    if daemon_alive(name): raise RuntimeError(f"daemon {name!r} already alive — kill_daemon({name!r}) first")
    b = browser_use_create(**create_kwargs)
    ensure_daemon(name=name, env={"BU_CDP_WS": cdp_ws_from_url(b["cdpUrl"]),
                                  "BU_BROWSER_ID": b["id"]})
    return b


# --- navigation / page ---
def goto(url):  return cdp("Page.navigate", url=url)

def page_info():
    """{url, title, w, h, sx, sy, pw, ph} — viewport + scroll + page size."""
    r = cdp("Runtime.evaluate",
            expression="JSON.stringify({url:location.href,title:document.title,w:innerWidth,h:innerHeight,sx:scrollX,sy:scrollY,pw:document.documentElement.scrollWidth,ph:document.documentElement.scrollHeight})",
            returnByValue=True)
    return json.loads(r["result"]["value"])


# --- input ---
def click(x, y, button="left", clicks=1):
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button=button, clickCount=clicks)
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button=button, clickCount=clicks)

def type_text(text):
    """Raw Input.insertText — inserts at the caret of the focused element. Fires `input`
    events (so most framework onChange/v-model handlers see it) but NOT keydown/keyup.
    For form fields prefer `fill(selector, value)` which focuses + types + blurs."""
    cdp("Input.insertText", text=text)

def fill(selector, value):
    """Focus the element, bulk-insert `value` (fires native beforeinput/input events so
    React/Vue/Angular/Formik onChange all see it), then Tab to blur (fires change). Fast:
    ~4 CDP calls regardless of value length. Does NOT reliably work on `<input type="date">`
    — those parse keystrokes segment-by-segment and reject bulk text."""
    ok = js(f"(() => {{const el = document.querySelector({json.dumps(selector)}); if (!el) return false; el.focus(); return document.activeElement === el;}})()")
    if not ok: raise RuntimeError(f"couldn't focus {selector}")
    cdp("Input.insertText", text=value)
    press_key("Tab")


# --- page inspection: composable pieces of what other tools bundle into "state" ---

# Default selector for "things a user can interact with". Override via the `selector` arg
# on clickables() when a site uses custom [data-*] patterns.
CLICKABLE_SELECTOR = "button,input,select,textarea,a[href],[role=button],[role=link],[role=menuitem],[role=checkbox],[role=combobox],[role=tab],[onclick],[contenteditable=true]"

# Input types → canonical format string. "What does this browser-native widget expect to
# be typed". Extend for site-specific widgets (e.g. jQuery datepicker mm/dd/yyyy).
FORMAT_HINTS = {"date":"YYYY-MM-DD", "time":"HH:MM", "datetime-local":"YYYY-MM-DDTHH:MM",
                "month":"YYYY-MM", "week":"YYYY-Www"}

def clickables(selector=None, scope="document", visible_only=True):
    """Interactive elements as [{i, tag, type, id, name, role, text}]. Cheaper than
    screenshot+Read for seeing what to click. `selector` overrides CLICKABLE_SELECTOR;
    `scope` is any JS root expression; `visible_only=False` includes `display:none` els."""
    sel = selector or CLICKABLE_SELECTOR
    vis = "(el.offsetParent !== null || el.tagName === 'INPUT')" if visible_only else "true"
    return json.loads(js(f"""JSON.stringify(Array.from({scope}.querySelectorAll({json.dumps(sel)})).filter(el => {vis}).map((el, i) => ({{
      i, tag: el.tagName.toLowerCase(), type: el.type || el.getAttribute('type') || '',
      id: el.id, name: el.name || '', role: el.getAttribute('role') || '',
      text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim()
    }})))""") or "[]")

def field_info(selector, format_hints=None):
    """Everything to fill one input correctly: value, validation attrs, format hint for
    date/time, live validity. `format_hints` overrides FORMAT_HINTS (pass custom map for
    site-specific widgets like jQuery datepicker)."""
    fmt = json.dumps(format_hints or FORMAT_HINTS)
    return json.loads(js(f"""(() => {{const el=document.querySelector({json.dumps(selector)}); if(!el) return 'null';
      const fmt = ({fmt})[el.type] || el.getAttribute('data-date-format') || el.getAttribute('pattern') || '';
      return JSON.stringify({{tag:el.tagName.toLowerCase(), type:el.type||'', value:el.value||'', checked:el.checked||false, required:el.required||false,
        pattern:el.pattern||'', min:el.min||'', max:el.max||'', step:el.step||'', minlength:el.minLength>0?el.minLength:null, maxlength:el.maxLength>0?el.maxLength:null,
        accept:el.accept||'', multiple:el.multiple||false, inputmode:el.inputMode||el.getAttribute('inputmode')||'', autocomplete:el.autocomplete||'',
        placeholder:el.placeholder||'', aria_label:el.getAttribute('aria-label')||'', format_hint:fmt,
        valid:el.validity?el.validity.valid:true, error:el.validationMessage||''}});}})()""") or "null")

_KEYS = {  # key → (windowsVirtualKeyCode, code, text)
    "Enter": (13, "Enter", "\r"), "Tab": (9, "Tab", "\t"), "Backspace": (8, "Backspace", ""),
    "Escape": (27, "Escape", ""), "Delete": (46, "Delete", ""), " ": (32, "Space", " "),
    "ArrowLeft": (37, "ArrowLeft", ""), "ArrowUp": (38, "ArrowUp", ""),
    "ArrowRight": (39, "ArrowRight", ""), "ArrowDown": (40, "ArrowDown", ""),
    "Home": (36, "Home", ""), "End": (35, "End", ""),
    "PageUp": (33, "PageUp", ""), "PageDown": (34, "PageDown", ""),
}
def press_key(key, modifiers=0):
    """Modifiers bitfield: 1=Alt, 2=Ctrl, 4=Meta(Cmd), 8=Shift.
    Printable chars send rawKeyDown + char (single insertion); control keys (Enter, Tab,
    Arrow*, Backspace, etc.) send keyDown + keyUp carrying their virtual key codes so
    listeners checking e.keyCode / e.key all fire."""
    vk, code, text = _KEYS.get(key, (ord(key[0]) if len(key) == 1 else 0, key, key if len(key) == 1 else ""))
    base = {"key": key, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
    if text and len(text) == 1 and key not in _KEYS:
        # Printable character: rawKeyDown (no text) + char (with text) → one insertion.
        # Previously sent keyDown with text AND char with text, which double-inserted.
        cdp("Input.dispatchKeyEvent", type="rawKeyDown", **base)
        cdp("Input.dispatchKeyEvent", type="char", text=text, **base)
    else:
        # Control key (Enter, Tab, arrows, etc.): keyDown carries text if it has one.
        cdp("Input.dispatchKeyEvent", type="keyDown", **base, **({"text": text} if text else {}))
    cdp("Input.dispatchKeyEvent", type="keyUp", **base)

def scroll(x, y, dy=-300, dx=0):
    cdp("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=dx, deltaY=dy)


# --- visual ---
def screenshot(path="/tmp/shot.png", full=False):
    r = cdp("Page.captureScreenshot", format="png", captureBeyondViewport=full)
    open(path, "wb").write(base64.b64decode(r["data"]))
    return path


# --- tabs ---
def list_tabs(include_chrome=True):
    out = []
    for t in cdp("Target.getTargets")["targetInfos"]:
        if t["type"] != "page": continue
        url = t.get("url", "")
        if not include_chrome and url.startswith(INTERNAL): continue
        out.append({"targetId": t["targetId"], "title": t.get("title", ""), "url": url})
    return out

def current_tab():
    t = cdp("Target.getTargetInfo").get("targetInfo", {})
    return {"targetId": t.get("targetId"), "url": t.get("url", ""), "title": t.get("title", "")}

def switch_tab(target_id):
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"]
    set_session(sid)
    return sid

def new_tab(url="about:blank"):
    tid = cdp("Target.createTarget", url=url)["targetId"]
    switch_tab(tid)
    return tid

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

def js(expression, target_id=None):
    """Run JS in the attached tab (default) or inside an iframe target (via iframe_target())."""
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"] if target_id else None
    r = cdp("Runtime.evaluate", session_id=sid, expression=expression, returnByValue=True, awaitPromise=True)
    return r.get("result", {}).get("value")

_KC = {"Enter":13,"Tab":9,"Escape":27,"Backspace":8," ":32,"ArrowLeft":37,"ArrowUp":38,"ArrowRight":39,"ArrowDown":40}
def dispatch_key(selector, key="Enter", event="keypress"):
    """Dispatch a DOM KeyboardEvent on the matched element. Use when CDP's press_key doesn't trigger DOM listeners — e.g. `keypress` for Enter on <input type=search> (CDP's `char` event quirk for special keys)."""
    kc = _KC.get(key, ord(key) if len(key) == 1 else 0)
    js(f"(()=>{{const e=document.querySelector({json.dumps(selector)});if(e){{e.focus();e.dispatchEvent(new KeyboardEvent({json.dumps(event)},{{key:{json.dumps(key)},code:{json.dumps(key)},keyCode:{kc},which:{kc},bubbles:true}}));}}}})()")


def upload_file(selector, path):
    """Set files on a file input via CDP DOM.setFileInputFiles. `path` is an absolute filepath (use tempfile.mkstemp if needed)."""
    doc = cdp("DOM.getDocument", depth=-1)
    nid = cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)["nodeId"]
    if not nid: raise RuntimeError(f"no element for {selector}")
    cdp("DOM.setFileInputFiles", files=[path] if isinstance(path, str) else list(path), nodeId=nid)


def capture_dialogs():
    """Stub window.alert/confirm/prompt so messages stash in window.__dialogs__. Call BEFORE the action that triggers the dialog; read with dialogs()."""
    js("window.__dialogs__=[];window.alert=m=>window.__dialogs__.push(String(m));window.confirm=m=>{window.__dialogs__.push(String(m));return true;};window.prompt=(m,d)=>{window.__dialogs__.push(String(m));return d||'';}")

def dialogs():
    """Return list of captured dialog messages since last capture_dialogs()."""
    return json.loads(js("JSON.stringify(window.__dialogs__||[])") or "[]")


def http_get(url, headers=None, timeout=20.0):
    """Pure HTTP — no browser. Use for static pages / APIs. Wrap in ThreadPoolExecutor for bulk."""
    import urllib.request, gzip
    h = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
    if headers: h.update(headers)
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip": data = gzip.decompress(data)
        return data.decode()
