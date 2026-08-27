"""CLI/SDK parity: identical CDP wire traffic for identical operations.

Every CLI helper funnels through `helpers._send`; every SDK call funnels through
`HarnessClient.send`. Drive the same operation down both paths against the same
canned daemon responses, then diff the emitted request sequences and the return
values. A divergence here is a real behavioral difference between
`browser-use <<PY ... PY` and `browser_harness.sdk`, independent of any page,
model, or network.
"""
import asyncio
import json
from unittest.mock import patch

import pytest

from browser_harness import helpers
from browser_harness.sdk import Browser

# canned CDP responses -- enough shape for every helper under test
RESPONSES = {
    "Page.navigate": {"result": {"frameId": "F1"}},
    "Target.getTargets": {
        "result": {
            "targetInfos": [
                {"type": "page", "targetId": "T-AAAA", "title": "Doc", "url": "https://x.test/"},
                {"type": "page", "targetId": "T-BBBB", "title": "Settings", "url": "chrome://settings"},
                {"type": "iframe", "targetId": "T-IFRA", "title": "", "url": "https://ad.test/frame"},
            ]
        }
    },
    "Target.activateTarget": {"result": {}},
    "Target.attachToTarget": {"result": {"sessionId": "S9"}},
    "Target.createTarget": {"result": {"targetId": "T-NEW"}},
    "Target.closeTarget": {"result": {}},
    "Input.dispatchMouseEvent": {"result": {}},
    "Input.dispatchKeyEvent": {"result": {}},
    "Input.insertText": {"result": {}},
    "Page.captureScreenshot": {"result": {"data": ""}},
    "DOM.getDocument": {"result": {"root": {"nodeId": 1}}},
    "DOM.querySelector": {"result": {"nodeId": 7}},
    "DOM.setFileInputFiles": {"result": {}},
    "Accessibility.getFullAXTree": {"result": {"nodes": []}},
}

META = {
    "pending_dialog": {},
    "current_tab": {"targetId": "T-AAAA", "title": "Doc", "url": "https://x.test/"},
    "set_session": {"ok": True},
    "session": {"session_id": "S1"},
    "drain_events": {"events": []},
}

ELEMENT_FOUND = [True]  # flipped by the error-path tests

PAGE_INFO_JSON = json.dumps(
    {"url": "https://x.test/", "title": "Doc", "w": 1200, "h": 800, "sx": 0, "sy": 0, "pw": 1200, "ph": 4000}
)


def _respond(req: dict) -> dict:
    """One canned daemon, shared by both implementations."""
    if "meta" in req:
        return dict(META.get(req["meta"], {}))
    method = req["method"]
    if method == "Runtime.evaluate":
        expr = req["params"]["expression"]
        if "document.readyState" in expr:
            return {"result": {"result": {"value": "complete"}}}
        if "navigator.platform" in expr:
            return {"result": {"result": {"value": "Linux x86_64"}}}
        if "location.href" in expr and "JSON.stringify" in expr:
            return {"result": {"result": {"value": PAGE_INFO_JSON}}}
        if "querySelector" in expr:
            return {"result": {"result": {"value": ELEMENT_FOUND[0]}}}
        return {"result": {"result": {"value": None}}}
    return dict(RESPONSES.get(method, {"result": {}}))


def _normalize(requests: list[dict]) -> list[dict]:
    """Strip only what cannot be identical across transports (nothing today);
    kept as the single place to declare an allowed difference."""
    return requests


def run_cli(call) -> tuple[list[dict], object]:
    seen: list[dict] = []

    def fake_send(req):
        seen.append(json.loads(json.dumps(req)))
        r = _respond(req)
        if "error" in r:
            raise RuntimeError(r["error"])
        return r

    helpers._select_all_mods = None
    with patch("browser_harness.helpers._send", side_effect=fake_send):
        value = call(helpers)
    return _normalize(seen), value


def run_sdk(call) -> tuple[list[dict], object]:
    seen: list[dict] = []
    browser = Browser(auto_start=False)
    browser._started = True

    async def fake_send(req, request_timeout=None):
        seen.append(json.loads(json.dumps(req)))
        r = _respond(req)
        if "error" in r:
            from browser_harness.sdk import HarnessError

            raise HarnessError(r["error"])
        return r

    browser.client.send = fake_send
    value = asyncio.run(call(browser))
    return _normalize(seen), value


# (name, cli callable, sdk callable, compares_return)
OPERATIONS = [
    ('goto_url', lambda h: h.goto_url('https://x.test/'), lambda b: b.goto_url('https://x.test/'), False),
    ('page_info', lambda h: h.page_info(), lambda b: b.page_info(), False),
    ('click_at_xy', lambda h: h.click_at_xy(10, 20), lambda b: b.click_at_xy(10, 20), True),
    ('type_text', lambda h: h.type_text('hello'), lambda b: b.type_text('hello'), True),
    ('press_key_enter', lambda h: h.press_key('Enter'), lambda b: b.press_key('Enter'), True),
    ('press_key_char', lambda h: h.press_key('a'), lambda b: b.press_key('a'), True),
    ('press_key_mod', lambda h: h.press_key('a', modifiers=2), lambda b: b.press_key('a', modifiers=2), True),
    ('scroll', lambda h: h.scroll(5, 6, dy=-300), lambda b: b.scroll(5, 6, dy=-300), True),
    ('fill_input', lambda h: h.fill_input('#q', 'ab'), lambda b: b.fill_input('#q', 'ab'), True),
    ('dispatch_key', lambda h: h.dispatch_key('#q', 'Enter'), lambda b: b.dispatch_key('#q', 'Enter'), True),
    ('upload_file', lambda h: h.upload_file('#f', '/tmp/a.txt'), lambda b: b.upload_file('#f', '/tmp/a.txt'), True),
    ('list_tabs', lambda h: h.list_tabs(), lambda b: b.list_tabs(), False),
    ('list_tabs_no_chrome', lambda h: h.list_tabs(include_chrome=False), lambda b: b.list_tabs(include_chrome=False), False),
    ('current_tab', lambda h: h.current_tab(), lambda b: b.current_tab(), False),
    ('switch_tab', lambda h: h.switch_tab('T-AAAA'), lambda b: b.switch_tab('T-AAAA'), True),
    ('new_tab_blank', lambda h: h.new_tab(), lambda b: b.new_tab(), True),
    ('new_tab_url', lambda h: h.new_tab('https://x.test/p'), lambda b: b.new_tab('https://x.test/p'), True),
    ('close_tab', lambda h: h.close_tab('T-AAAA'), lambda b: b.close_tab('T-AAAA'), True),
    ('ensure_real_tab', lambda h: h.ensure_real_tab(), lambda b: b.ensure_real_tab(), False),
    ('iframe_target', lambda h: h.iframe_target('ad.test'), lambda b: b.iframe_target('ad.test'), True),
    ('js', lambda h: h.js('1+1'), lambda b: b.js('1+1'), True),
    ('js_in_iframe', lambda h: h.js('1+1', target_id='T-IFRA'), lambda b: b.js('1+1', target_id='T-IFRA'), True),
    ('wait_for_load', lambda h: h.wait_for_load(), lambda b: b.wait_for_load(), True),
    ('wait_for_element', lambda h: h.wait_for_element('#q'), lambda b: b.wait_for_element('#q'), True),
    (
        'wait_for_element_visible',
        lambda h: h.wait_for_element('#q', visible=True),
        lambda b: b.wait_for_element('#q', visible=True),
        True,
    ),
    ('drain_events', lambda h: h.drain_events(), lambda b: b.drain_events(), True),
    ('cdp_raw', lambda h: h.cdp('Page.navigate', url='https://x.test/'), lambda b: b.cdp('Page.navigate', url='https://x.test/'), True),
]


@pytest.mark.parametrize('name,cli_call,sdk_call,compare_return', OPERATIONS, ids=[o[0] for o in OPERATIONS])
def test_cli_and_sdk_emit_identical_cdp_traffic(name, cli_call, sdk_call, compare_return):
    cli_requests, cli_value = run_cli(cli_call)
    sdk_requests, sdk_value = run_sdk(sdk_call)

    assert cli_requests, f'{name}: CLI path emitted no requests -- test is not exercising it'
    assert sdk_requests == cli_requests, (
        f'{name}: SDK emits different CDP traffic than the CLI\n'
        f'CLI ({len(cli_requests)}): {json.dumps(cli_requests, indent=1)}\n'
        f'SDK ({len(sdk_requests)}): {json.dumps(sdk_requests, indent=1)}'
    )
    if compare_return:
        assert sdk_value == cli_value, f'{name}: same traffic but different return: CLI={cli_value!r} SDK={sdk_value!r}'


def test_capture_screenshot_parity(tmp_path, fake_png):
    """Same CDP call, same bytes on disk, same returned path."""
    png = fake_png(40, 30)
    responses = dict(RESPONSES)
    responses["Page.captureScreenshot"] = {"result": {"data": png}}
    cli_path = str(tmp_path / "cli.png")
    sdk_path = str(tmp_path / "sdk.png")

    with patch.dict(RESPONSES, responses):
        cli_requests, cli_value = run_cli(lambda h: h.capture_screenshot(cli_path))
        sdk_requests, sdk_value = run_sdk(lambda b: b.capture_screenshot(sdk_path))

    assert sdk_requests == cli_requests
    assert str(sdk_value) == sdk_path and str(cli_value) == cli_path
    assert (tmp_path / "sdk.png").read_bytes() == (tmp_path / "cli.png").read_bytes()


def test_wait_for_network_idle_parity():
    """Identical meta+drain sequence; both return True on a quiet buffer."""
    cli_requests, cli_value = run_cli(lambda h: h.wait_for_network_idle(timeout=1.0, idle_ms=1))
    sdk_requests, sdk_value = run_sdk(lambda b: b.wait_for_network_idle(timeout=1.0, idle_ms=1))
    assert cli_value is True and sdk_value is True
    assert [r for r in sdk_requests if "meta" in r] == [r for r in cli_requests if "meta" in r]


@pytest.mark.parametrize(
    "cli_call,sdk_call",
    [
        (lambda h: h.fill_input("#missing", "x"), lambda b: b.fill_input("#missing", "x")),
        (lambda h: h.upload_file("#missing", "/tmp/a"), lambda b: b.upload_file("#missing", "/tmp/a")),
    ],
    ids=["fill_input_missing", "upload_file_missing"],
)
def test_error_paths_raise_the_same_type_and_message(cli_call, sdk_call):
    """SDK errors must stay catchable as the CLI's RuntimeError, with the same text."""
    responses = dict(RESPONSES)
    responses["DOM.querySelector"] = {"result": {"nodeId": 0}}

    ELEMENT_FOUND[0] = False
    try:
        with patch.dict(RESPONSES, responses):
            with pytest.raises(RuntimeError) as cli_error:
                run_cli(cli_call)
            with pytest.raises(RuntimeError) as sdk_error:
                run_sdk(sdk_call)
    finally:
        ELEMENT_FOUND[0] = True

    assert isinstance(sdk_error.value, RuntimeError)
    assert str(sdk_error.value) == str(cli_error.value)


def test_parity_suite_covers_every_cli_helper():
    """Fail when a CLI helper gains no parity check -- the suite must not silently
    stop covering the surface it claims to."""
    covered = {name.split('_')[0] for name, *_ in OPERATIONS} | {
        'goto', 'page', 'click', 'type', 'press', 'fill', 'dispatch', 'upload', 'list', 'current',
        'switch', 'new', 'close', 'ensure', 'iframe', 'wait', 'js', 'drain', 'cdp', 'scroll',
    }
    exercised = {
        'goto_url', 'page_info', 'click_at_xy', 'type_text', 'press_key', 'scroll', 'fill_input',
        'dispatch_key', 'upload_file', 'list_tabs', 'current_tab', 'switch_tab', 'new_tab', 'close_tab',
        'ensure_real_tab', 'iframe_target', 'js', 'wait_for_load', 'wait_for_element', 'drain_events', 'cdp',
    }
    public = {
        n
        for n in dir(helpers)
        if not n.startswith('_') and callable(getattr(helpers, n)) and getattr(helpers, n).__module__ == helpers.__name__
    }
    # deliberately out of scope: pure-python or CLI-only concerns
    exempt = {'wait', 'wait_for_network_idle', 'capture_screenshot', 'http_get', 'start_recording', 'stop_recording', 'recording_dir'}
    missing = public - exercised - exempt - covered
    assert not missing, f'CLI helpers with no parity check: {sorted(missing)}'
