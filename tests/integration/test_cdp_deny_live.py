"""BH_CDP_DENY=tokens against a real headless Chrome and a real daemon process.

Replays the review probes for PR #1054: DevTools frontend bypass, wire-header
leak through drain_events, privileged-tab sessions, and respawn without the env
var. A Fetch-based "swapper" on its own CDP connection stands in for the
browser-token swap: it rewrites X-Card DUMMY -> REAL4111 on the way out.
Skipped when no Chrome binary is installed.
"""
import http.server
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

CHROME = next((shutil.which(b) for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(b)), None)
pytestmark = [
    pytest.mark.skipif(CHROME is None, reason="needs a Chrome/Chromium binary"),
    pytest.mark.skipif(sys.platform == "win32", reason="talks to the daemon's AF_UNIX socket"),
]
REAL = "REAL4111"
SRC = str(Path(__file__).resolve().parents[2] / "src")


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<html><body><input type=file id=f></body></html>" if self.path == "/" else b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "text/html" if self.path == "/" else "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class _RawCDP:
    """Second CDP connection: the token swapper and the 'outside' actor."""

    def __init__(self, ws_url):
        from websockets.sync.client import connect
        self.ws = connect(ws_url, max_size=None)
        self.next_id = 0
        self.pending = {}
        self.lock = threading.Lock()
        self.stop = False
        threading.Thread(target=self._loop, daemon=True).start()

    def send(self, method, params=None, session_id=None, timeout=10):
        with self.lock:
            self.next_id += 1
            mid = self.next_id
            box = self.pending[mid] = {"ev": threading.Event()}
        msg = {"id": mid, "method": method, "params": params or {}}
        if session_id:
            msg["sessionId"] = session_id
        self.ws.send(json.dumps(msg))
        assert box["ev"].wait(timeout), method
        if "error" in box["msg"]:
            raise RuntimeError(box["msg"]["error"])
        return box["msg"]["result"]

    def _loop(self):
        while not self.stop:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                return
            if "id" in msg:
                box = self.pending.pop(msg["id"], None)
                if box:
                    box["msg"] = msg
                    box["ev"].set()
            elif msg.get("method") == "Fetch.requestPaused":
                p, sid = msg["params"], msg.get("sessionId")
                headers = [{"name": k, "value": REAL if k.lower() == "x-card" else v} for k, v in p["request"]["headers"].items()]
                threading.Thread(target=self.send, args=("Fetch.continueRequest", {"requestId": p["requestId"], "headers": headers}, sid), daemon=True).start()

    def close(self):
        self.stop = True
        self.ws.close()


def _ipc(sock_path, req, timeout=20):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(str(sock_path))
    s.sendall((json.dumps(req) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(1 << 16)
        if not chunk:
            break
        data += chunk
    s.close()
    return json.loads(data)


@pytest.fixture
def live(tmp_path):
    profile = tempfile.mkdtemp(prefix="bh-deny-chrome-")
    chrome = subprocess.Popen(
        [CHROME, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    port_file = Path(profile) / "DevToolsActivePort"
    for _ in range(100):
        if port_file.exists() and port_file.read_text().strip():
            break
        time.sleep(0.1)
    port, ws_path = port_file.read_text().split()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    runtime = tmp_path / "rt"
    runtime.mkdir()
    env = {
        **os.environ, "PYTHONPATH": SRC, "BU_CDP_URL": f"http://127.0.0.1:{port}", "BU_NAME": "denyprobe",
        "BH_RUNTIME_DIR": str(runtime), "BH_TMP_DIR": str(tmp_path / "tmp"), "BH_TAB_MARKER": "0",
        "BH_CONFIG_DIR": str(tmp_path / "cfg"), "BH_AGENT_WORKSPACE": str(tmp_path / "ws"),
    }
    env.pop("BU_BROWSER_ID", None)
    env.pop("BU_CDP_WS", None)
    procs = []

    def start_daemon(**extra):
        e = {**env, **extra}
        e = {k: v for k, v in e.items() if v is not None}
        p = subprocess.Popen([sys.executable, "-m", "browser_harness.daemon"], env=e,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(p)
        for _ in range(150):
            try:
                if _ipc(runtime / "bu.sock", {"meta": "ping"}, timeout=1).get("pong"):
                    return p
            except OSError:
                pass
            time.sleep(0.1)
        raise AssertionError("daemon did not start")

    raw = _RawCDP(f"ws://127.0.0.1:{port}{ws_path}")
    ctx = {
        "start_daemon": start_daemon, "call": lambda req: _ipc(runtime / "bu.sock", req),
        "raw": raw, "origin": f"http://127.0.0.1:{server.server_address[1]}", "env": env,
        "runtime": runtime,
    }
    try:
        yield ctx
    finally:
        raw.close()
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
        server.shutdown()
        chrome.terminate()
        try:
            chrome.wait(10)
        except subprocess.TimeoutExpired:
            chrome.kill()
        shutil.rmtree(profile, ignore_errors=True)


def _cdp(ctx, method, **params):
    return ctx["call"]({"method": method, "params": params})


def _page_target(ctx):
    return next(t for t in _cdp(ctx, "Target.getTargets")["result"]["targetInfos"] if t["type"] == "page" and t["url"].startswith("http"))


def _swap_and_fetch(ctx):
    """Install the swapper on the daemon's tab, send a DUMMY header, return drained events."""
    origin = ctx["origin"]
    assert "result" in _cdp(ctx, "Page.navigate", url=origin + "/")
    time.sleep(0.5)
    tid = _page_target(ctx)["targetId"]
    sid = ctx["raw"].send("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
    ctx["raw"].send("Fetch.enable", {"patterns": [{"urlPattern": origin + "/api*"}]}, session_id=sid)
    ctx["call"]({"meta": "drain_events"})
    r = _cdp(ctx, "Runtime.evaluate", expression=f"fetch('{origin}/api',{{headers:{{'X-Card':'DUMMY'}}}}).then(r=>r.status)", awaitPromise=True)
    assert r["result"]["result"]["value"] == 200, r
    time.sleep(0.5)
    return ctx["call"]({"meta": "drain_events"})["events"]


def test_swapper_control_unset_mode_leaks_real_value(live):
    """Control: proves the swapper works, so the tokens-mode assertion below means something."""
    live["start_daemon"](BH_CDP_DENY=None)

    events = _swap_and_fetch(live)

    assert REAL in json.dumps(events)


def test_tokens_mode_keeps_swapped_header_out_of_drain_events(live):
    live["start_daemon"](BH_CDP_DENY="tokens")

    events = _swap_and_fetch(live)

    methods = {e["method"] for e in events}
    assert "Network.requestWillBeSent" in methods
    assert REAL not in json.dumps(events)
    assert not any(m.endswith("ExtraInfo") for m in methods)


def test_tokens_mode_blocks_devtools_frontend_route(live):
    live["start_daemon"](BH_CDP_DENY="tokens")
    assert "result" in _cdp(live, "Page.navigate", url=live["origin"] + "/")
    time.sleep(0.5)
    page = _page_target(live)

    opened = _cdp(live, "Target.openDevTools", targetId=page["targetId"])
    # Same frontend opened from outside the daemon: attaching to it must still fail.
    dt = live["raw"].send("Target.openDevTools", {"targetId": page["targetId"]})["targetId"]
    attached = _cdp(live, "Target.attachToTarget", targetId=dt, flatten=True)

    assert "Target.openDevTools is blocked" in opened["error"]
    assert "BH_CDP_DENY=tokens" in attached["error"]


def test_tokens_mode_refuses_tab_after_history_lands_on_chrome_page(live):
    live["start_daemon"](BH_CDP_DENY="tokens")
    origin = live["origin"]
    assert "result" in _cdp(live, "Page.navigate", url=origin + "/")
    time.sleep(0.5)
    tid = _page_target(live)["targetId"]
    sid = live["raw"].send("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
    # Outside actor leaves a chrome:// entry in the tab's history.
    live["raw"].send("Page.navigate", {"url": "chrome://version"}, session_id=sid)
    time.sleep(0.5)
    live["raw"].send("Page.navigate", {"url": origin + "/"}, session_id=sid)
    time.sleep(0.5)
    assert _cdp(live, "Runtime.evaluate", expression="1+1")["result"]["result"]["value"] == 2

    _cdp(live, "Runtime.evaluate", expression="history.back()")
    for _ in range(50):
        info = next(t for t in _cdp(live, "Target.getTargets")["result"]["targetInfos"] if t["targetId"] == tid)
        if info["url"].startswith("chrome://"):
            break
        time.sleep(0.1)
    time.sleep(0.3)
    on_chrome = _cdp(live, "Runtime.evaluate", expression="typeof chrome.send")
    left = _cdp(live, "Page.navigate", url=origin + "/")

    assert info["url"].startswith("chrome://"), info
    assert "chrome: target is blocked" in on_chrome["error"]
    assert "result" in left


def test_tokens_mode_navigate_then_evaluate_has_no_spurious_denial(live):
    live["start_daemon"](BH_CDP_DENY="tokens")

    for i in range(5):
        assert "result" in _cdp(live, "Page.navigate", url=f"{live['origin']}/?n={i}")
        r = _cdp(live, "Runtime.evaluate", expression="location.search")
        assert "result" in r, r


def test_tokens_mode_refuses_local_file_and_proxy_routes(live):
    live["start_daemon"](BH_CDP_DENY="tokens")
    assert "result" in _cdp(live, "Page.navigate", url=live["origin"] + "/")
    time.sleep(0.3)
    doc = _cdp(live, "DOM.getDocument", depth=-1)["result"]
    node = _cdp(live, "DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="#f")["result"]["nodeId"]

    upload = _cdp(live, "DOM.setFileInputFiles", files=["/etc/hostname"], nodeId=node)
    download = _cdp(live, "Browser.setDownloadBehavior", behavior="allow", downloadPath=str(live["runtime"]))
    context = _cdp(live, "Target.createBrowserContext", proxyServer="http://127.0.0.1:1")
    certs = _cdp(live, "Security.setIgnoreCertificateErrors", ignore=True)

    assert "outside BH_UPLOAD_DIR" in upload["error"]
    assert "outside BH_DOWNLOAD_DIR" in download["error"]
    assert "Target.createBrowserContext is blocked" in context["error"]
    assert "Security.setIgnoreCertificateErrors is blocked" in certs["error"]


def test_tokens_mode_survives_respawn_without_env(live):
    first = live["start_daemon"](BH_CDP_DENY="tokens")
    assert live["call"]({"meta": "ping"})["cdp_deny"] == "tokens"
    first.send_signal(signal.SIGTERM)
    first.wait(10)

    live["start_daemon"](BH_CDP_DENY=None)

    assert live["call"]({"meta": "ping"})["cdp_deny"] == "tokens"
    assert "Fetch.enable is blocked" in _cdp(live, "Fetch.enable")["error"]
