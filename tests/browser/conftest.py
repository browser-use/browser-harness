"""Opt-in real-browser tests. Always create an isolated disposable profile/daemon."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import pytest


@pytest.fixture(scope="module")
def browser_cli():
    chrome = os.environ.get("BH_TEST_CHROME")
    if not chrome:
        pytest.skip("set BH_TEST_CHROME to run against a disposable headless Chrome")
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="bh-test-", dir="/tmp") as directory:
        root = Path(directory)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BU_", "BH_", "BROWSER_HARNESS_"))}
        env.update(BU_NAME="fixture", BH_HOME=str(root / "home"), BH_RUNTIME_DIR=str(root / "runtime"),
                   BH_TMP_DIR=str(root / "tmp"), BH_AGENT_WORKSPACE=str(root / "workspace"),
                   BH_TAB_MARKER="0", BH_RECORD="0", PYTHONPATH=str(repo / "src"))
        browser = subprocess.Popen([chrome, "--headless=new", "--remote-debugging-port=0",
                                    f"--user-data-dir={root / 'profile'}", "--no-first-run", "--no-default-browser-check", "about:blank"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        daemon_process = None
        try:
            port_file = root / "profile" / "DevToolsActivePort"
            deadline = time.monotonic() + 15
            while not port_file.exists():
                if browser.poll() is not None or time.monotonic() > deadline:
                    pytest.fail("disposable Chrome failed to start")
                time.sleep(0.05)
            port, path = port_file.read_text().splitlines()[:2]
            env["BU_CDP_WS"] = f"ws://127.0.0.1:{port}{path}"
            daemon_process = subprocess.Popen([sys.executable, "-m", "browser_harness.daemon"], env=env,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sock_path = root / "runtime" / "bu.sock"
            while True:
                try:
                    with socket.socket(socket.AF_UNIX) as sock:
                        sock.settimeout(1)
                        sock.connect(str(sock_path))
                        sock.sendall(b'{"meta":"ping"}\n')
                        if json.loads(sock.recv(4096)).get("pong"):
                            break
                except (OSError, ValueError):
                    pass
                if daemon_process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail("disposable harness daemon failed to start")
                time.sleep(0.05)
            def run(code, timeout=20):
                result = subprocess.run([sys.executable, "-m", "browser_harness.run"], input=code, text=True,
                                        capture_output=True, env=env, cwd=repo, timeout=timeout)
                if result.returncode:
                    log = root / "tmp" / "bu.log"
                    evidence = log.read_text()[-4000:] if log.exists() else "no daemon log"
                    raise AssertionError(result.stdout + result.stderr + "\nDaemon log:\n" + evidence)
                return result.stdout
            yield run
        finally:
            for process in (daemon_process, browser):
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
