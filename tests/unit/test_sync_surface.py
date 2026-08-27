"""The sync facade must expose exactly the async surface, and cover every CLI helper."""
import asyncio
import inspect
import json

from browser_harness import helpers
from browser_harness.sdk import Browser, Element, SyncBrowser, SyncElement

from .test_cli_sdk_parity import OPERATIONS, _respond


def _public(obj) -> set[str]:
    return {n for n in dir(obj) if not n.startswith("_") and callable(getattr(obj, n))}


# lifecycle/plumbing that is meaningless or renamed on the blocking facade
SYNC_ONLY_EXEMPT: set[str] = set()
ASYNC_ONLY_EXEMPT: set[str] = set()


def test_sync_surface_matches_async():
    """Drift guard: a method added to Browser must appear on SyncBrowser."""
    async_surface = _public(Browser) - ASYNC_ONLY_EXEMPT
    sync_surface = _public(SyncBrowser) - {"client"} - SYNC_ONLY_EXEMPT
    missing = async_surface - sync_surface
    extra = sync_surface - async_surface
    assert not missing, f'SyncBrowser is missing async methods: {sorted(missing)}'
    assert not extra, f'SyncBrowser has methods the async Browser lacks: {sorted(extra)}'


def test_sync_element_surface_matches_async():
    missing = _public(Element) - _public(SyncElement)
    assert not missing, f'SyncElement is missing Element methods: {sorted(missing)}'


def test_sync_signatures_match_async_minus_await():
    """Same parameter names and defaults, so CLI snippets port verbatim."""
    mismatches = []
    for name in sorted(_public(Browser) & _public(SyncBrowser)):
        async_sig = inspect.signature(getattr(Browser, name))
        sync_sig = inspect.signature(getattr(SyncBrowser, name))
        if [(p.name, p.default) for p in async_sig.parameters.values()] != [
            (p.name, p.default) for p in sync_sig.parameters.values()
        ]:
            mismatches.append(f'{name}: async{async_sig} != sync{sync_sig}')
    assert not mismatches, 'signature drift:\n' + '\n'.join(mismatches)


def test_every_cli_helper_has_a_sync_method():
    """The question this package exists to answer: can a CLI snippet be ported
    one-for-one by prefixing `browser.`?"""
    cli_helpers = {
        n
        for n in dir(helpers)
        if not n.startswith("_")
        and callable(getattr(helpers, n))
        and getattr(getattr(helpers, n), "__module__", "") == helpers.__name__
    }
    # recorder helpers are CLI-session concerns, not browser operations
    exempt = {"start_recording", "stop_recording", "recording_dir"}
    missing = cli_helpers - _public(SyncBrowser) - exempt
    assert not missing, f'CLI helpers with no SyncBrowser equivalent: {sorted(missing)}'


def test_sync_emits_the_same_cdp_traffic_as_the_cli():
    """Every parity operation, re-run through the blocking facade."""
    failures = []
    for name, cli_call, _sdk_call, _cmp in OPERATIONS:
        cli_seen: list[dict] = []
        sync_seen: list[dict] = []

        def fake_cli_send(req, _seen=cli_seen):
            _seen.append(json.loads(json.dumps(req)))
            return _respond(req)

        async def fake_sync_send(req, request_timeout=None, _seen=sync_seen):
            _seen.append(json.loads(json.dumps(req)))
            return _respond(req)

        from unittest.mock import patch

        helpers._select_all_mods = None
        with patch("browser_harness.helpers._send", side_effect=fake_cli_send):
            cli_call(helpers)

        browser = SyncBrowser(auto_start=False)
        browser._browser._started = True
        browser._browser.client.send = fake_sync_send
        # the operation table is written against the async Browser; the facade
        # takes the same args, so re-dispatch by name
        method, args, kwargs = _DISPATCH[name]
        getattr(browser, method)(*args, **kwargs)

        if sync_seen != cli_seen:
            failures.append(name)
    assert not failures, f'sync facade diverges from the CLI on: {failures}'


# operation name -> (method, args, kwargs) for the sync re-dispatch above
_DISPATCH = {
    'goto_url': ('goto_url', ('https://x.test/',), {}),
    'page_info': ('page_info', (), {}),
    'click_at_xy': ('click_at_xy', (10, 20), {}),
    'type_text': ('type_text', ('hello',), {}),
    'press_key_enter': ('press_key', ('Enter',), {}),
    'press_key_char': ('press_key', ('a',), {}),
    'press_key_mod': ('press_key', ('a', 2), {}),
    'scroll': ('scroll', (5, 6, -300), {}),
    'fill_input': ('fill_input', ('#q', 'ab'), {}),
    'dispatch_key': ('dispatch_key', ('#q', 'Enter'), {}),
    'upload_file': ('upload_file', ('#f', '/tmp/a.txt'), {}),
    'list_tabs': ('list_tabs', (), {}),
    'list_tabs_no_chrome': ('list_tabs', (False,), {}),
    'current_tab': ('current_tab', (), {}),
    'switch_tab': ('switch_tab', ('T-AAAA',), {}),
    'new_tab_blank': ('new_tab', (), {}),
    'new_tab_url': ('new_tab', ('https://x.test/p',), {}),
    'close_tab': ('close_tab', ('T-AAAA',), {}),
    'ensure_real_tab': ('ensure_real_tab', (), {}),
    'iframe_target': ('iframe_target', ('ad.test',), {}),
    'js': ('js', ('1+1',), {}),
    'js_in_iframe': ('js', ('1+1', 'T-IFRA'), {}),
    'wait_for_load': ('wait_for_load', (), {}),
    'wait_for_element': ('wait_for_element', ('#q',), {}),
    'wait_for_element_visible': ('wait_for_element', ('#q', 10.0, True), {}),
    'drain_events': ('drain_events', (), {}),
    'cdp_raw': ('cdp', ('Page.navigate',), {'url': 'https://x.test/'}),
}


def test_sync_runs_from_inside_a_running_event_loop():
    """Notebooks and async apps: the facade must not need the caller's loop."""

    async def inside():
        browser = SyncBrowser(auto_start=False)
        browser._browser._started = True

        async def fake_send(req, request_timeout=None):
            return _respond(req)

        browser._browser.client.send = fake_send
        return await asyncio.to_thread(browser.page_info)

    info = asyncio.run(inside())
    assert info.url == 'https://x.test/'
