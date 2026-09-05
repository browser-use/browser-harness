"""Opt-in live CDP stress test using only a disposable Chrome profile.

BH_TEST_CHROME=/path/to/chrome BH_TEST_AGENTS=100 uv run --with pytest \
    python -m pytest tests/integration/test_shared_browser.py -q -s
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

import pytest
from PIL import Image


@pytest.mark.skipif(not os.environ.get("BH_TEST_CHROME"), reason="set BH_TEST_CHROME to opt in")
def test_independent_processes_share_one_browser_connection():
    count = int(os.environ.get("BH_TEST_AGENTS", "10"))
    with tempfile.TemporaryDirectory(prefix="bh-multi-", dir=None if os.name == "nt" else "/tmp") as folder:
        root = Path(folder)
        profile = root / "chrome"
        with (root / "chrome.log").open("wb") as log:
            chrome = subprocess.Popen([
                os.environ["BH_TEST_CHROME"], "--headless=new", "--remote-debugging-port=0",
                f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--disable-background-networking", "--window-size=800,600",
                "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=log)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BU_", "BH_"))}
        env.update(BH_HOME=str(root / "home"), BH_RUNTIME_DIR=str(root / "run"),
                   BH_TMP_DIR=str(root / "shots"), BH_RECORD="0", BH_TAB_MARKER="0",
                   BH_TELEMETRY="0", BH_DOMAIN_SKILLS="0")
        try:
            deadline = time.monotonic() + 20
            port_file = profile / "DevToolsActivePort"
            while not port_file.exists():
                assert chrome.poll() is None, (root / "chrome.log").read_text()
                assert time.monotonic() < deadline, "Chrome startup timed out"
                time.sleep(0.05)
            port, endpoint = port_file.read_text().splitlines()[:2]
            env["BU_CDP_WS"] = f"ws://127.0.0.1:{port}{endpoint}"

            async def cli(script):
                p = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "browser_harness.run", env=env,
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    out, err = await asyncio.wait_for(p.communicate(script.encode()), timeout=180)
                except BaseException:
                    if p.returncode is None:
                        p.kill()
                    await p.wait()
                    raise
                assert p.returncode == 0, err.decode() + out.decode()
                return json.loads(out.decode().strip().splitlines()[-1])

            async def run():
                started = time.monotonic()

                async def create(i):
                    html = (f'<body style="margin:0;background:rgb({i % 256},100,150)">'
                            '<button style="position:absolute;left:0;top:0;width:100px;height:40px" '
                            f'onclick="window.clicks++">agent-{i}</button>'
                            '<input style="position:absolute;left:0;top:50px;width:200px;height:40px">'
                            f'<script>window.owner={i};window.clicks=0</script>')
                    return await cli(f'''
import json
from browser_harness.helpers import _send
tid = new_tab({("data:text/html," + quote(html))!r})
assert wait_for_load()
assert js("window.owner") == {i}
print(json.dumps({{"target":tid,"pid":_send({{"meta":"ping"}})["pid"]}}))
''')

                # Cold-start burst; every creator exits before the next phase.
                tabs = await asyncio.gather(*(create(i) for i in range(count)))
                assert len({t["target"] for t in tabs}) == count
                pids = {t["pid"] for t in tabs}
                assert len(pids) == 1, f"multiple daemons: {pids}"

                async def act(i, tab):
                    return await cli(f'''
import json
from browser_harness.helpers import _send
switch_tab({tab["target"]!r})
click_at_xy(40, 20)
click_at_xy(50, 70)
type_text("agent-{i}")
state = js("({{owner:window.owner, clicks:window.clicks, text:document.querySelector('input').value}})")
assert state == {{"owner":{i},"clicks":1,"text":"agent-{i}"}}, state
shot = capture_screenshot()
assert current_tab()["targetId"] == {tab["target"]!r}
print(json.dumps({{"shot":shot,"pid":_send({{"meta":"ping"}})["pid"]}}))
''')
                results = await asyncio.gather(*(act(i, t) for i, t in enumerate(tabs)))
                assert {r["pid"] for r in results} == pids
                assert len({r["shot"] for r in results}) == count
                for i, r in enumerate(results):
                    with Image.open(r["shot"]) as image:
                        assert image.convert("RGB").getpixel((300, 200)) == (i % 256, 100, 150)
                if count > 1:
                    await cli(f'''
import json, time
switch_tab({tabs[0]["target"]!r})
# Chrome suppresses background alerts. This is the disposable HEADLESS browser,
# not the user's visible Chrome; activate only to exercise a real modal dialog.
activate_tab({tabs[0]["target"]!r})
cdp("Runtime.evaluate", expression="setTimeout(() => alert('only-tab-zero'), 10)", userGesture=True)
time.sleep(0.2)
print(json.dumps(page_info()))
''')
                    status = await cli(f'''
import json
switch_tab({tabs[1]["target"]!r})
print(json.dumps(page_info()))
''')
                    assert "dialog" not in status
                    await cli(f'''
import json
switch_tab({tabs[0]["target"]!r})
assert page_info()["dialog"]["message"] == "only-tab-zero"
cdp("Page.handleJavaScriptDialog", accept=True)
print(json.dumps(True))
''')
                # Closing even the startup default must not replace the daemon.
                cleanup = await cli('''
import json
from browser_harness.helpers import _send
for t in list_tabs(): close_tab(t)
assert "error" not in _send({"meta":"connection_status"})
print(json.dumps(_send({"meta":"ping"})["pid"]))
''')
                fresh = await create(count)
                assert {cleanup, fresh["pid"]} == pids
                print(json.dumps({"agents": count, "daemons": len(pids), "distinct_tabs": count,
                                  "distinct_screenshots": count, "seconds": round(time.monotonic()-started, 2)}))

            asyncio.run(run())
        finally:
            # Only the owned test daemon in this isolated runtime directory.
            subprocess.run([sys.executable, "-c",
                            "from browser_harness.admin import restart_daemon; restart_daemon()"],
                           env=env, capture_output=True, timeout=20)
            chrome.terminate()
            try:
                chrome.wait(timeout=10)
            except subprocess.TimeoutExpired:
                chrome.kill()
                chrome.wait(timeout=5)
