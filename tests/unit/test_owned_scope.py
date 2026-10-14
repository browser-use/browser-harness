import asyncio

import pytest

from browser_harness.owned_scope import (
    MAX_OPEN_SCOPES,
    BrowserLevelForOwnedTarget,
    OnOwnedSession,
    OwnedTarget,
    Refusal,
    ScopeTable,
    parse_scope_id,
    route_cdp,
)

OWNED = OwnedTarget(
    scope_id="a" * 32, context_id="ctx-1", target_id="owned-target", session_id="owned-session",
)


@pytest.mark.parametrize(
    ("method", "params", "session", "expected"),
    [
        ("Page.navigate", {"url": "https://x.test"}, None, OnOwnedSession("Page.navigate", {"url": "https://x.test"})),
        ("Runtime.evaluate", {"expression": "1"}, "owned-session", OnOwnedSession("Runtime.evaluate", {"expression": "1"})),
        ("Input.dispatchKeyEvent", {}, None, OnOwnedSession("Input.dispatchKeyEvent", {})),
        ("Network.getAllCookies", {}, None, OnOwnedSession("Network.getAllCookies", {})),
        ("Browser.getVersion", {}, None, BrowserLevelForOwnedTarget("Browser.getVersion", {})),
        ("Target.getTargetInfo", {"targetId": "owned-target"}, None,
         BrowserLevelForOwnedTarget("Target.getTargetInfo", {"targetId": "owned-target"})),
        ("Target.closeTarget", {"targetId": "owned-target"}, None,
         BrowserLevelForOwnedTarget("Target.closeTarget", {"targetId": "owned-target"})),
        ("Page.navigate", {}, "user-session", Refusal.FOREIGN_SESSION),
        ("Target.getTargets", {}, "user-session", Refusal.FOREIGN_SESSION),
        ("Target.getTargets", {}, None, Refusal.ENUMERATION),
        ("Target.setDiscoverTargets", {"discover": True}, None, Refusal.ENUMERATION),
        ("Target.setAutoAttach", {}, None, Refusal.ENUMERATION),
        ("Target.getBrowserContexts", {}, None, Refusal.ENUMERATION),
        ("Target.getTargetInfo", {}, None, Refusal.ENUMERATION),
        ("Target.createTarget", {"url": "about:blank"}, None, Refusal.SECOND_TARGET),
        ("Target.createBrowserContext", {}, None, Refusal.SECOND_TARGET),
        ("Target.getTargetInfo", {"targetId": "user-tab"}, None, Refusal.FOREIGN_TARGET),
        ("Target.closeTarget", {"targetId": "user-tab"}, None, Refusal.FOREIGN_TARGET),
        ("Target.attachToTarget", {"targetId": "owned-target"}, None, Refusal.FOREIGN_TARGET),
        ("Target.activateTarget", {"targetId": "user-tab"}, None, Refusal.FOREIGN_TARGET),
        ("Target.detachFromTarget", {"sessionId": "owned-session"}, None, Refusal.FOREIGN_TARGET),
        ("Storage.getCookies", {}, None, Refusal.DOMAIN_NOT_ALLOWED),
        ("Storage.clearDataForOrigin", {"origin": "*"}, None, Refusal.DOMAIN_NOT_ALLOWED),
        ("SystemInfo.getInfo", {}, None, Refusal.DOMAIN_NOT_ALLOWED),
        ("Browser.close", {}, None, Refusal.DOMAIN_NOT_ALLOWED),
        ("Browser.setDownloadBehavior", {}, None, Refusal.DOMAIN_NOT_ALLOWED),
        ("Fetch.enable", {}, None, Refusal.DOMAIN_NOT_ALLOWED),
        ("", {}, None, Refusal.DOMAIN_NOT_ALLOWED),
    ],
)
def test_route_cdp(method, params, session, expected):
    assert route_cdp(OWNED, method, params, session) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0123456789abcdef" * 2, "0123456789abcdef" * 2), ("A" * 32, None), ("a" * 31, None), (None, None), (7, None)],
)
def test_parse_scope_id(raw, expected):
    assert parse_scope_id(raw) == expected


def test_refusal_reply_is_stable_string():
    assert Refusal.SECOND_TARGET.reply() == {"error": "owned-scope: second-target"}


PING = {"pong": True, "pid": 4242, "browser_kind": "local", "capabilities": ["owned_target"]}


class RecordingBrowser:
    """send_raw fake. Records every call; replies per method; can fail by method."""

    def __init__(self, fail=None):
        self.sent = []
        self.fail = dict(fail or {})
        self._n = 0

    async def send_raw(self, method, params=None, session_id=None):
        self.sent.append((method, params, session_id))
        if method in self.fail:
            raise RuntimeError(self.fail[method])
        self._n += 1
        if method == "Target.createBrowserContext":
            return {"browserContextId": f"ctx-{self._n}"}
        if method == "Target.createTarget":
            return {"targetId": f"owned-target-{self._n}"}
        if method == "Target.attachToTarget":
            return {"sessionId": f"owned-session-{self._n}"}
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"targetId": params["targetId"], "type": "page",
                                   "url": "https://owned.test/", "title": "Owned"}}
        return {}


def _begin(table):
    return asyncio.run(table.begin())["owned_target"]


def test_begin_sends_context_target_attach_then_enables_on_owned_session_only():
    browser = RecordingBrowser()
    table = ScopeTable(browser.send_raw, PING)

    lease = asyncio.run(table.begin())

    assert lease == {"owned_target": {"protocol": 1, "scope_id": lease["owned_target"]["scope_id"],
                                      "target_id": "owned-target-2"}}
    assert parse_scope_id(lease["owned_target"]["scope_id"]) is not None
    assert browser.sent[:3] == [
        ("Target.createBrowserContext", {"disposeOnDetach": True}, None),
        ("Target.createTarget", {"url": "about:blank", "background": True, "browserContextId": "ctx-1"}, None),
        ("Target.attachToTarget", {"targetId": "owned-target-2", "flatten": True}, None),
    ]
    assert sorted(browser.sent[3:]) == [
        ("DOM.enable", None, "owned-session-3"),
        ("Network.enable", None, "owned-session-3"),
        ("Page.enable", None, "owned-session-3"),
        ("Runtime.enable", None, "owned-session-3"),
    ]


def test_begin_failure_disposes_context_and_registers_nothing():
    browser = RecordingBrowser(fail={"Page.enable": "Page.enable failed"})
    table = ScopeTable(browser.send_raw, PING)

    reply = asyncio.run(table.begin())

    assert reply == {"error": "Page.enable failed"}
    assert browser.sent[-1] == ("Target.disposeBrowserContext", {"browserContextId": "ctx-1"}, None)
    assert table.absorb_event("Page.loadEventFired", {}, "owned-session-3") is False


def test_begin_refuses_past_capacity_without_cdp():
    browser = RecordingBrowser()
    table = ScopeTable(browser.send_raw, PING)
    for _ in range(MAX_OPEN_SCOPES):
        _begin(table)
    browser.sent.clear()

    assert asyncio.run(table.begin()) == {"error": "owned-scope: capacity"}
    assert browser.sent == []


def test_scoped_enumeration_and_lifecycle_never_reach_browser():
    browser = RecordingBrowser()
    table = ScopeTable(browser.send_raw, PING)
    scope = _begin(table)["scope_id"]
    browser.sent.clear()

    replies = [asyncio.run(table.handle({"scope": scope, **req})) for req in (
        {"method": "Target.getTargets", "params": {}},
        {"method": "Target.createTarget", "params": {"url": "about:blank"}},
        {"method": "Target.closeTarget", "params": {"targetId": "user-tab"}},
        {"method": "Page.navigate", "params": {"url": "x"}, "session_id": "user-session"},
        {"method": "Storage.getCookies", "params": {}},
        {"meta": "set_session", "session_id": "user-session", "target_id": "user-tab"},
        {"meta": "shutdown"},
        {"meta": "begin_owned_target"},
        {"meta": "some_future_meta"},
    )]

    assert replies == [
        {"error": "owned-scope: enumeration"},
        {"error": "owned-scope: second-target"},
        {"error": "owned-scope: foreign-target"},
        {"error": "owned-scope: foreign-session"},
        {"error": "owned-scope: domain-not-allowed"},
        {"error": "owned-scope: lifecycle"},
        {"error": "owned-scope: lifecycle"},
        {"error": "owned-scope: lifecycle"},
        {"error": "owned-scope: unknown-meta"},
    ]
    assert browser.sent == []


def test_sessionless_cdp_lands_on_owned_session_and_target_calls_are_browser_level():
    browser = RecordingBrowser()
    table = ScopeTable(browser.send_raw, PING)
    scope = _begin(table)["scope_id"]
    browser.sent.clear()

    asyncio.run(table.handle({"scope": scope, "method": "Page.navigate", "params": {"url": "https://a.test"}}))
    asyncio.run(table.handle({"scope": scope, "method": "Target.closeTarget",
                              "params": {"targetId": "owned-target-2"}}))

    assert browser.sent == [
        ("Page.navigate", {"url": "https://a.test"}, "owned-session-3"),
        ("Target.closeTarget", {"targetId": "owned-target-2"}, None),
    ]


def test_stale_owned_session_refuses_without_recovery():
    browser = RecordingBrowser(fail={"Runtime.evaluate": "Session with given id not found."})
    table = ScopeTable(browser.send_raw, PING)
    scope = _begin(table)["scope_id"]
    browser.sent.clear()

    reply = asyncio.run(table.handle({"scope": scope, "method": "Runtime.evaluate", "params": {}}))

    assert reply == {"error": "owned-scope: stale-session"}
    assert [m for m, _, _ in browser.sent] == ["Runtime.evaluate"]


def test_projected_metas_answer_from_scope_state():
    browser = RecordingBrowser()
    table = ScopeTable(browser.send_raw, PING)
    scope = _begin(table)["scope_id"]
    browser.sent.clear()

    def meta(name):
        return asyncio.run(table.handle({"scope": scope, "meta": name}))

    assert meta("ping") == PING
    assert meta("session") == {"session_id": "owned-session-3"}
    assert meta("current_tab") == {"targetId": "owned-target-2", "url": "https://owned.test/", "title": "Owned"}
    assert meta("connection_status") == {
        "target_id": "owned-target-2", "session_id": "owned-session-3",
        "page": {"targetId": "owned-target-2", "title": "Owned", "url": "https://owned.test/"},
    }
    assert meta("pending_dialog") == {"dialog": None}
    assert browser.sent == [
        ("Target.getTargetInfo", {"targetId": "owned-target-2"}, None),
        ("Target.getTargetInfo", {"targetId": "owned-target-2"}, None),
    ]


def test_claim_owned_page_succeeds_once_then_refuses_second_target():
    table = ScopeTable(RecordingBrowser().send_raw, PING)
    scope = _begin(table)["scope_id"]

    first = asyncio.run(table.handle({"scope": scope, "meta": "claim_owned_page"}))
    second = asyncio.run(table.handle({"scope": scope, "meta": "claim_owned_page"}))

    assert first == {"targetId": "owned-target-2"}
    assert second == {"error": "owned-scope: second-target"}


def test_events_partition_at_ingest_by_owned_session():
    table = ScopeTable(RecordingBrowser().send_raw, PING)
    scope = _begin(table)["scope_id"]

    absorbed = [
        table.absorb_event("Network.requestWillBeSent", {"requestId": "r1"}, "owned-session-3"),
        table.absorb_event("Page.javascriptDialogOpening", {"message": "hi"}, "owned-session-3"),
        table.absorb_event("Network.requestWillBeSent", {"requestId": "u1"}, "user-session"),
        table.absorb_event("Target.targetCreated", {}, None),
    ]
    dialog = asyncio.run(table.handle({"scope": scope, "meta": "pending_dialog"}))
    drained = asyncio.run(table.handle({"scope": scope, "meta": "drain_events"}))
    again = asyncio.run(table.handle({"scope": scope, "meta": "drain_events"}))

    assert absorbed == [True, True, False, False]
    assert dialog == {"dialog": {"message": "hi"}}
    assert drained == {"events": [
        {"method": "Network.requestWillBeSent", "params": {"requestId": "r1"}, "session_id": "owned-session-3"},
        {"method": "Page.javascriptDialogOpening", "params": {"message": "hi"}, "session_id": "owned-session-3"},
    ]}
    assert again == {"events": []}


def test_end_disposes_only_owned_context_and_is_idempotent():
    browser = RecordingBrowser()
    table = ScopeTable(browser.send_raw, PING)
    scope = _begin(table)["scope_id"]
    browser.sent.clear()

    first = asyncio.run(table.handle({"scope": scope, "meta": "end_owned_target"}))
    second = asyncio.run(table.handle({"scope": scope, "meta": "end_owned_target"}))
    after = asyncio.run(table.handle({"scope": scope, "method": "Page.navigate", "params": {}}))

    assert first == {"ok": True, "closed": "disposed"}
    assert second == {"ok": True, "closed": "already"}
    assert after == {"error": "owned-scope: scope-closed"}
    assert browser.sent == [("Target.disposeBrowserContext", {"browserContextId": "ctx-1"}, None)]
    assert table.absorb_event("Page.loadEventFired", {}, "owned-session-3") is False


def test_failed_dispose_keeps_scope_closing_for_retry():
    browser = RecordingBrowser()
    table = ScopeTable(browser.send_raw, PING)
    scope = _begin(table)["scope_id"]
    browser.fail["Target.disposeBrowserContext"] = "boom"

    failed = asyncio.run(table.handle({"scope": scope, "meta": "end_owned_target"}))
    refused = asyncio.run(table.handle({"scope": scope, "meta": "session"}))
    del browser.fail["Target.disposeBrowserContext"]
    retried = asyncio.run(table.close_all())

    assert failed == {"error": "dispose failed: boom"}
    assert refused == {"error": "owned-scope: scope-closed"}
    assert retried == []
    assert asyncio.run(table.handle({"scope": scope, "meta": "end_owned_target"})) == {"ok": True, "closed": "already"}


def test_unknown_or_malformed_scope_is_refused():
    browser = RecordingBrowser()
    table = ScopeTable(browser.send_raw, PING)

    assert asyncio.run(table.handle({"scope": "b" * 32, "meta": "session"})) == {"error": "owned-scope: unknown-scope"}
    assert asyncio.run(table.handle({"scope": "not-a-scope", "method": "Page.navigate"})) == {
        "error": "owned-scope: unknown-scope"}
    assert asyncio.run(table.handle({"scope": "b" * 32, "meta": "end_owned_target"})) == {
        "error": "owned-scope: unknown-scope"}
    assert browser.sent == []
