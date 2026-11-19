"""A daemon killed under the process that spawned it is started again at once (browser-use's reattach).

Needs a Chrome/Chromium binary (BH_TEST_CHROME or on PATH); skipped otherwise.
"""
import os
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from browser_harness import _ipc as ipc, admin

from .test_network_idle import _chrome


@pytest.fixture
def chrome_ws():
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
    yield f"ws://127.0.0.1:{port}{path}"
    chrome.kill()
    shutil.rmtree(home, ignore_errors=True)


def test_a_killed_daemon_is_started_again_without_waiting_for_its_zombie(chrome_ws):
    """It stayed a zombie of this process, with its pid and start time, and ensure_daemon() waited 60 s for it to
    come up, then failed with the dead daemon's last log line."""
    name = f"test-{uuid.uuid4().hex[:8]}"
    env = {"BU_CDP_WS": chrome_ws, "BH_TAB_MARKER": "0"}
    try:
        admin.ensure_daemon(name=name, env=env)
        old = ipc.identify(name)
        os.kill(old, signal.SIGKILL)
        time.sleep(0.3)

        t = time.monotonic()
        admin.ensure_daemon(name=name, env=env)

        assert time.monotonic() - t < 15
        assert ipc.identify(name) not in (None, old)
    finally:
        admin.restart_daemon(name)
