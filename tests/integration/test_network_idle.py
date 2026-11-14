"""wait_for_network_idle() against a real headless Chrome and a loopback server.

Set BH_TEST_CHROME to a Chrome/Chromium binary (or have one on PATH); skipped otherwise.
The browser runs with a temporary profile and the daemon under its own BU_NAME and BH_HOME.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SLOW_S = 3.0
PAGES = {
    "/plain": "<h1>plain</h1>",
    # localhost is another site than 127.0.0.1, so Chrome loads the iframe out of process
    "/iframe": '<h1>iframe</h1><iframe src="http://localhost:{port}/child"></iframe>',
    "/child": "<p>child</p>",
    # the iframe starts out of process, then comes back in process and loads a slow image
    "/swap": '<h1>swap</h1><iframe src="http://localhost:{port}/child" onload="this.onload = null; this.src = \'/slowimg\'"></iframe>',
    "/slowimg": '<img src="/slow">',
    # a blob worker, a worker from a URL, a worker stopped before it starts, a shared worker
    "/worker": "<h1>worker</h1><script>const src = () => URL.createObjectURL(new Blob(['1'], {{type: 'text/javascript'}}));"
               "new Worker(src()); new Worker('/w.js'); new Worker(src()).terminate(); new SharedWorker(src())</script>",
    "/w.js": "1",
}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/slow":
            time.sleep(SLOW_S)
            body = b"done"
        elif self.path not in PAGES:
            return self.send_error(404)
        else:
            body = PAGES[self.path].format(port=self.server.server_address[1]).encode()
        self.send_response(200)
        self.send_header("content-type", "text/javascript" if self.path.endswith(".js") else "text/html")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _chrome():
    path = os.environ.get("BH_TEST_CHROME")
    if path:
        return path
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        if found := shutil.which(name):
            return found
    pytest.skip("no Chrome binary: set BH_TEST_CHROME")


@pytest.fixture(scope="module")
def harness():
    """Run a script through the browser-harness CLI against a fresh headless Chrome; returns its last stdout line."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    home = tempfile.mkdtemp(prefix="bh-test-")
    profile = Path(home) / "profile"
    chrome = subprocess.Popen(
        [_chrome(), "--headless=new", f"--user-data-dir={profile}", "--remote-debugging-port=0", "--no-first-run", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    active_port = profile / "DevToolsActivePort"
    deadline = time.time() + 30
    while not active_port.exists() and time.time() < deadline:
        time.sleep(0.05)
    port, path = active_port.read_text().split()[:2]
    env = {**os.environ, "BU_NAME": f"test-{uuid.uuid4().hex[:8]}", "BH_HOME": home, "BH_TAB_MARKER": "0",
           "BU_CDP_WS": f"ws://127.0.0.1:{port}{path}"}
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def run(code):
        out = subprocess.run([sys.executable, "-m", "browser_harness.run"], input=code.replace("BASE", base),
                             env=env, capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        return out.stdout.splitlines()[-1]

    yield run
    subprocess.run([sys.executable, "-c", "from browser_harness.admin import restart_daemon; restart_daemon()"], env=env, timeout=30)
    chrome.kill()
    server.shutdown()
    shutil.rmtree(home, ignore_errors=True)


IDLE_AFTER_LOAD = """
import json, time
goto_url("BASE{page}"); wait_for_load()
t = time.time(); ok = wait_for_network_idle()
print(json.dumps({{"ok": ok, "s": time.time() - t}}))
"""


@pytest.mark.parametrize("page", ["/plain", "/iframe", "/worker"])
def test_idle_after_load(harness, page):
    # The iframe document and the worker script start on the tab but finish on their own target.
    r = json.loads(harness(IDLE_AFTER_LOAD.format(page=page)))
    assert r["ok"] is True and r["s"] < 3, r


def test_slow_request_holds_idle_until_it_finishes(harness):
    r = json.loads(harness("""
import json, time
goto_url("BASE/iframe"); wait_for_load(); wait_for_network_idle()
js("void fetch('/slow')")
t = time.time(); ok = wait_for_network_idle()
print(json.dumps({"ok": ok, "s": time.time() - t}))
"""))
    assert r["ok"] is True and SLOW_S - 0.5 < r["s"] < SLOW_S + 3, r


def test_iframe_back_in_process_holds_idle_for_its_requests(harness):
    # Its target attaches, then detaches when it navigates back to the tab's site; the tab then reports its image.
    r = json.loads(harness("""
import json
goto_url("BASE/swap"); ok = wait_for_network_idle()
print(json.dumps({"ok": ok, "img": js("frames[0].document.images[0]?.complete")}))
"""))
    assert r == {"ok": True, "img": True}, r
