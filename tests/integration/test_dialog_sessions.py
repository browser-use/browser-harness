"""Opt-in Chrome regression: set BH_TEST_CHROME to a Chromium executable.

The test creates its own headless browser, profile and IPC directory; it never
attaches to a user's browser. No websites or cloud credentials are required.
"""

import asyncio
import contextlib
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from browser_harness import _ipc as ipc, daemon, helpers


@pytest.mark.skipif(not os.environ.get("BH_TEST_CHROME"), reason="set BH_TEST_CHROME to run an isolated Chrome")
@pytest.mark.parametrize("shutdown_failure", [None, "server", "cdp"])
def test_page_info_ignores_another_tabs_real_javascript_dialog(monkeypatch, shutdown_failure):
    chrome = None
    cdp_stopped = False
    original_serve, original_stop = daemon.serve, daemon.CDPClient.stop

    async def serve(connection):
        await original_serve(connection)
        if shutdown_failure == "server":
            raise RuntimeError("injected server shutdown failure")

    async def stop(client):
        nonlocal cdp_stopped
        await original_stop(client)
        cdp_stopped = True
        if shutdown_failure == "cdp":
            raise RuntimeError("injected cdp shutdown failure")

    monkeypatch.setattr(daemon, "serve", serve)
    monkeypatch.setattr(daemon.CDPClient, "stop", stop)

    async def run():
        nonlocal chrome
        with tempfile.TemporaryDirectory(prefix="bh-dialog-") as directory:
            root = Path(directory)
            profile = root / "profile"
            monkeypatch.setattr(ipc, "_RUNTIME", root)
            monkeypatch.setattr(ipc, "BH_RUNTIME_DIR", directory)
            monkeypatch.setattr(ipc, "BH_RUNTIME_DIR_SHARED", False)
            monkeypatch.setattr(daemon, "LOG", str(root / "daemon.log"))
            monkeypatch.setattr(daemon, "NAME", "default")
            monkeypatch.setattr(helpers, "NAME", "default")
            monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
            monkeypatch.setenv("BH_TAB_MARKER", "0")
            chrome = subprocess.Popen([
                os.environ["BH_TEST_CHROME"], "--headless=new",
                "--remote-debugging-port=0", f"--user-data-dir={profile}",
                "--no-first-run", "--no-default-browser-check", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            connection = server = evaluation = None
            session_a = None
            try:
                async with asyncio.timeout(15):
                    port_file = profile / "DevToolsActivePort"
                    while not port_file.exists():
                        assert chrome.poll() is None, "isolated Chrome exited before exposing CDP"
                        await asyncio.sleep(0.02)
                port, endpoint = port_file.read_text().splitlines()[:2]
                monkeypatch.setenv("BU_CDP_WS", f"ws://127.0.0.1:{port}{endpoint}")
                connection = daemon.Daemon()
                await connection.start()
                server = asyncio.create_task(daemon.serve(connection))
                async with asyncio.timeout(5):
                    while not await asyncio.to_thread(ipc.ping, "default", 0.1):
                        await asyncio.sleep(0.01)
                await asyncio.to_thread(helpers.goto_url, "data:text/html,<title>A</title>A")
                assert (await asyncio.to_thread(helpers.page_info))["title"] == "A"
                target_a = await asyncio.to_thread(helpers.current_tab)
                session_a = connection.session
                opened = asyncio.Event()
                connection.cdp.register.Page.javascriptDialogOpening(
                    lambda params, session: opened.set() if session == session_a else None
                )
                evaluation = asyncio.create_task(asyncio.to_thread(helpers.js, "alert('Dialog on A')"))
                await asyncio.wait_for(opened.wait(), 5)
                assert (await asyncio.to_thread(helpers.page_info))["dialog"]["message"] == "Dialog on A"
                target = await asyncio.to_thread(helpers.cdp, "Target.createTarget", url="data:text/html,<title>B</title>B", background=True)
                await asyncio.to_thread(helpers.switch_tab, target)
                assert (await asyncio.to_thread(helpers.current_tab))["targetId"] == target["targetId"]
                info = await asyncio.to_thread(helpers.page_info)
                assert "dialog" not in info
                assert info["title"] == "B"
                # Chrome does not replay the existing dialog on a fresh
                # session; the harness must retain the target's dialog.
                returned_session = await asyncio.to_thread(helpers.switch_tab, target_a)
                assert returned_session != session_a
                assert (await asyncio.to_thread(helpers.page_info))["dialog"]["message"] == "Dialog on A"
            finally:
                try:
                    if connection is not None and connection.cdp is not None:
                        try:
                            if session_a is not None:
                                with contextlib.suppress(Exception):
                                    await asyncio.wait_for(connection.cdp.send_raw(
                                        "Page.handleJavaScriptDialog", {"accept": True}, session_id=session_a,
                                    ), 2)
                            if evaluation is not None:
                                with contextlib.suppress(Exception):
                                    await evaluation
                            if server is not None:
                                connection.stop.set()
                                await server
                        finally:
                            await connection.cdp.stop()
                finally:
                    chrome.terminate()
                    try:
                        chrome.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        chrome.kill()
                        chrome.wait()

    try:
        if shutdown_failure:
            with pytest.raises(RuntimeError, match=f"injected {shutdown_failure} shutdown failure"):
                asyncio.run(run())
        else:
            asyncio.run(run())
        assert chrome.poll() is not None, "isolated Chrome must exit even when cleanup raises"
        assert cdp_stopped
    finally:
        # Keep the regression test safe even when the cleanup under test fails.
        if chrome is not None and chrome.poll() is None:
            chrome.kill()
            chrome.wait()
