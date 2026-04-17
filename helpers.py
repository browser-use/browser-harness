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
    cdp("Input.insertText", text=text)

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
    Special keys (Enter, Tab, Arrow*, Backspace, etc.) carry their virtual key codes
    so listeners checking e.keyCode / e.key all fire."""
    vk, code, text = _KEYS.get(key, (ord(key[0]) if len(key) == 1 else 0, key, key if len(key) == 1 else ""))
    base = {"key": key, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
    cdp("Input.dispatchKeyEvent", type="keyDown", **base, **({"text": text} if text else {}))
    if text and len(text) == 1:
        cdp("Input.dispatchKeyEvent", type="char", text=text, **{k: v for k, v in base.items() if k != "text"})
    cdp("Input.dispatchKeyEvent", type="keyUp", **base)

def scroll(x, y, dy=-300, dx=0):
    cdp("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=dx, deltaY=dy)


# --- visual ---
def screenshot(path="/tmp/shot.png", full=False):
    r = cdp("Page.captureScreenshot", format="png", captureBeyondViewport=full)
    open(path, "wb").write(base64.b64decode(r["data"]))
    return path


# --- tabs ---
def list_tabs(include_chrome=False):
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
    tabs = list_tabs()
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
