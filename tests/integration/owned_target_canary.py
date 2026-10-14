"""Disposable-Chrome canary for BH_OWNED_TARGET=1.

Launches a throwaway headless Chrome with a temp profile, pre-opens an
unrelated tab, puts a recording CDP proxy between the daemon and Chrome, and
runs the real CLI in owned-target mode. Not collected by pytest; run directly:

    python tests/integration/owned_target_canary.py [path-to-chrome]
"""
import asyncio, json, os, shutil, signal, subprocess, sys, tempfile, threading, time, urllib.request
from pathlib import Path
from queue import Queue

from websockets.asyncio.client import connect as ws_connect
from websockets.asyncio.server import serve as ws_serve
from websockets.exceptions import ConnectionClosed

CHROME = sys.argv[1] if len(sys.argv) > 1 else "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CLI = str(Path(sys.executable).with_name("browser-harness"))
UNRELATED_TITLE = "unrelated-target-7f3a"
OWNED_URL = "data:text/html,<title>owned-target-page</title>owned"

BODY = f"""
try:
    list_tabs()
    raise SystemExit("enumeration was allowed")
except RuntimeError as e:
    assert str(e) == "owned-scope: enumeration", e
assert current_tab()["url"] == "about:blank", current_tab()
tid = new_tab({OWNED_URL!r})
wait_for_load()
try:
    new_tab()
    raise SystemExit("second target was allowed")
except RuntimeError as e:
    assert str(e) == "owned-scope: second-target", e
print(json.dumps({{"tid": tid, "title": page_info()["title"], "events": [e["method"] for e in drain_events()][:3]}}))
"""


def http_json(port, path, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def start_proxy(upstream, log):
    ready = Queue()

    async def handler(client):
        async with ws_connect(upstream, max_size=None) as up:
            async def client_to_chrome():
                async for msg in client:
                    log.append(json.loads(msg))
                    await up.send(msg)

            async def chrome_to_client():
                async for msg in up:
                    await client.send(msg)

            try:
                await asyncio.gather(client_to_chrome(), chrome_to_client())
            except ConnectionClosed:
                pass

    async def main():
        async with ws_serve(handler, "127.0.0.1", 0, max_size=None) as server:
            ready.put(server.sockets[0].getsockname()[1])
            await asyncio.Future()

    threading.Thread(target=lambda: asyncio.run(main()), daemon=True).start()
    return ready.get(timeout=10)


def wait_for(pred, timeout, what):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return
        time.sleep(0.2)
    raise SystemExit(f"timed out waiting for {what}")


def main():
    root = Path(tempfile.mkdtemp(prefix="bho-", dir="/tmp"))
    procs = []
    try:
        profile = root / "profile"
        chrome = subprocess.Popen(
            [CHROME, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={profile}",
             "--no-first-run", "--no-default-browser-check", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        procs.append(chrome)
        active = profile / "DevToolsActivePort"
        wait_for(lambda: active.exists() and len(active.read_text().splitlines()) == 2, 20, "DevToolsActivePort")
        port = int(active.read_text().splitlines()[0])
        unrelated = http_json(port, f"/json/new?data:text/html,<title>{UNRELATED_TITLE}</title>private", "PUT")
        browser_ws = http_json(port, "/json/version")["webSocketDebuggerUrl"]

        log = []
        proxy_port = start_proxy(browser_ws, log)
        env = {
            **os.environ,
            "BU_NAME": "owned-canary",
            "BU_CDP_WS": f"ws://127.0.0.1:{proxy_port}/devtools/browser/proxy",
            "BH_RUNTIME_DIR": str(root / "rt"),
            "BH_TMP_DIR": str(root / "tmp"),
            "BH_RECORD": "0",
            "BH_TELEMETRY": "0",
            "BH_UPDATE_CHECK": "0",
        }
        env.pop("BH_REQUIRE_EXISTING_DAEMON", None)
        daemon = subprocess.Popen([sys.executable, "-m", "browser_harness.daemon"], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(daemon)
        sock = root / "rt" / "bu.sock"
        wait_for(lambda: sock.exists(), 20, "daemon socket")

        before = len(log)
        owned = subprocess.run([CLI], input=BODY, env={**env, "BH_OWNED_TARGET": "1"},
                               capture_output=True, text=True, timeout=60)
        during = log[before:]
        print("owned run rc:", owned.returncode)
        print("owned run stdout:", owned.stdout.strip())
        print("owned run stderr:", owned.stderr.strip() or "<empty>")
        print("CDP methods during owned run:", [m.get("method") for m in during])

        assert owned.returncode == 0, owned.stderr
        result = json.loads(owned.stdout.strip().splitlines()[-1])
        assert result["title"] == "owned-target-page", result
        methods = [m.get("method") for m in during]
        assert "Target.getTargets" not in methods, methods
        assert methods[:3] == ["Target.createBrowserContext", "Target.createTarget", "Target.attachToTarget"], methods
        assert methods[-1] == "Target.disposeBrowserContext", methods
        assert unrelated["id"] not in json.dumps(during), "a CDP request named the unrelated target"
        assert UNRELATED_TITLE not in owned.stdout + owned.stderr, "unrelated title leaked to CLI output"

        tabs = {t["id"]: t for t in http_json(port, "/json/list")}
        assert unrelated["id"] in tabs, "unrelated tab was closed"
        assert tabs[unrelated["id"]]["title"] == UNRELATED_TITLE, tabs[unrelated["id"]]["title"]
        assert result["tid"] not in tabs, "owned target survived the run"

        missing = subprocess.run([CLI], input="print('body ran')",
                                 env={**env, "BU_NAME": "owned-missing", "BH_OWNED_TARGET": "1",
                                      "BH_RUNTIME_DIR": str(root / "rt-missing")},
                                 capture_output=True, text=True, timeout=30)
        print("missing-daemon rc:", missing.returncode, "stderr:", missing.stderr.strip())
        assert missing.returncode == 1 and "body ran" not in missing.stdout, missing
        assert missing.stderr.strip() == "browser-harness: required daemon 'owned-missing' is not running"
        print("owned-target canary: ok")
    finally:
        for p in reversed(procs):
            p.send_signal(signal.SIGTERM)
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
