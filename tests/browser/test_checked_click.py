from pathlib import Path
import re
from urllib.parse import quote

import pytest


RECIPE = re.findall(r"```python\n(.*?)```", (Path(__file__).resolve().parents[2] / "interaction-skills/checked-clicks.md").read_text(), re.S)[0]
PAGE = """<html><body><div style="height:1800px"></div>
<button id="save" onclick="window.clicks++;document.querySelector('#status').textContent='Saved'">Save</button>
<p id="status">Unsaved</p><script>window.clicks=0;</script></body></html>"""


@pytest.mark.parametrize("change,error", [
    ("", None),
    ("document.body.insertAdjacentHTML('beforeend', '<div style=\"position:fixed;inset:0;z-index:99\"></div>')", "covered"),
    ("document.querySelector('#save').remove()", "detached"),
    ("document.querySelector('#save').outerHTML = '<button id=save onclick=window.clicks++>Save</button>'", "replaced"),
    ("document.querySelector('#save').textContent = 'Delete'", "changed"),
    ("document.querySelector('#save').disabled = true", "disabled"),
])
def test_checked_click_against_real_dom(browser_cli, change, error):
    script = RECIPE + f'''
goto_url({('data:text/html,' + quote(PAGE))!r})
wait_for_load()
sid = cdp("Target.attachToTarget", targetId=current_tab()["targetId"], flatten=True)["sessionId"]
try:
    nodes = cdp("Accessibility.getFullAXTree", session_id=sid)["nodes"]
    node = next(n for n in nodes if n.get("role", {{}}).get("value") == "button" and n.get("name", {{}}).get("value") == "Save")
    assert js("document.querySelector('#save').getBoundingClientRect().top > innerHeight")
    if {bool(change)!r}:
        js({change!r})
    failed = False
    try:
        checked_click(sid, node["backendDOMNodeId"], "button", "Save")
    except RuntimeError as exc:
        failed = True
        print(str(exc))
    assert failed is {bool(error)!r}
    assert js("window.clicks") == {0 if error else 1}
    if not failed:
        assert js("document.querySelector('#status').textContent") == "Saved"
    print("verified")
finally:
    cdp("Target.detachFromTarget", sessionId=sid)
'''
    assert "verified" in browser_cli(script)
