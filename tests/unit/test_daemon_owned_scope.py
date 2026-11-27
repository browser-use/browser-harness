"""Owned-target scopes on the owners daemon: no enumeration, and no owner can reach a scope's tab."""
import asyncio
import json

from browser_harness import daemon
from browser_harness.owned_scope import OWNED_CAPABILITY
from tests.unit.test_daemon import PERSON, _Browser, _run, cmd, meta


class _ScopeBrowser(_Browser):
    async def send_raw(self, method, params=None, session_id=None):
        if method == "Target.createBrowserContext":
            self.calls.append((method, params or {}, session_id))
            return {"browserContextId": "owned-ctx"}
        if method == "Target.disposeBrowserContext":
            self.calls.append((method, params or {}, session_id))
            self.pages = {t: u for t, u in self.pages.items() if not t.startswith("tab-")}
            return {}
        return await super().send_raw(method, params, session_id)


def _daemon_with_scope():
    d = daemon.Daemon()
    d.cdp = _ScopeBrowser(PERSON)
    d.info = {t: d.cdp.info(t) for t in d.cdp.pages}
    d.stop = asyncio.Event()
    [lease] = _run(d, {"meta": "begin_owned_target"})
    owned = lease["owned_target"]
    d.info[owned["target_id"]] = d.cdp.info(owned["target_id"])
    return d, owned


def _scoped(owned, **req):
    return {"scope": owned["scope_id"], **req}


def test_ping_advertises_owned_target_capability():
    d = daemon.Daemon()
    [pong] = _run(d, {"meta": "ping", "owner": "a"})
    assert OWNED_CAPABILITY in pong["capabilities"]


def test_begin_never_enumerates_and_creates_no_owner():
    d, owned = _daemon_with_scope()
    methods = [m for m, _p, _s in d.cdp.calls]
    assert "Target.getTargets" not in methods
    assert methods[:3] == ["Target.createBrowserContext", "Target.createTarget", "Target.attachToTarget"]
    assert [p for m, p, _s in d.cdp.calls if m == "Target.createTarget"] == [
        {"url": "about:blank", "background": True, "browserContextId": "owned-ctx"}]
    assert d.owners == {} and d.tab_owner == {}


def test_begin_refused_while_stopping():
    d = daemon.Daemon()
    d.cdp = _ScopeBrowser(PERSON)
    d.stop = asyncio.Event(); d.stop.set()
    [r] = _run(d, {"meta": "begin_owned_target"})
    assert r == {"error": "daemon is shutting down"}


def test_scoped_requests_refuse_enumeration_and_reach_no_owner():
    d, owned = _daemon_with_scope()
    d.cdp.calls.clear()
    targets, tabs, pong = _run(d, _scoped(owned, method="Target.getTargets", params={}),
                               _scoped(owned, meta="tabs"), _scoped(owned, meta="ping", owner="a"))
    assert targets == {"error": "owned-scope: enumeration"}
    assert tabs == {"error": "owned-scope: enumeration"}
    assert pong["pong"] is True and "active" not in pong and "cdp" not in pong
    assert d.cdp.calls == [] and d.owners == {}


def test_scoped_page_events_skip_owner_routing():
    d, owned = _daemon_with_scope()
    sid = [s for m, p, s in d.cdp.calls if m == "Page.enable"][0]
    d._record_event("Page.javascriptDialogOpening", {"message": "hi"}, sid)
    [events] = _run(d, _scoped(owned, meta="drain_events"))
    assert [e["method"] for e in events["events"]] == ["Page.javascriptDialogOpening"]
    assert all(not o.events for o in d.owners.values())


def test_owner_cannot_see_take_close_or_drive_a_scoped_tab():
    d, owned = _daemon_with_scope()
    tid = owned["target_id"]
    sid = [s for m, p, s in d.cdp.calls if m == "Page.enable"][0]
    d.cdp.pages[tid] = "https://private.example/inbox"
    d.info[tid] = d.cdp.info(tid)
    d.cdp.calls.clear()
    targets, info, attach, close, switch, drive = _run(
        d, cmd("a", "Target.getTargets"), cmd("a", "Target.getTargetInfo", targetId=tid),
        cmd("a", "Target.attachToTarget", targetId=tid, flatten=True), cmd("a", "Target.closeTarget", targetId=tid),
        meta("a", "switch_tab", target_id=tid),
        {"owner": "a", "method": "Runtime.evaluate", "params": {"expression": "1"}, "session_id": sid})
    assert "private.example" not in json.dumps([targets, info])
    for reply in (attach, close, switch, drive):
        assert "tab-taken" in reply.get("error", ""), reply
    assert not [c for c in d.cdp.calls if c[0] in ("Target.attachToTarget", "Target.closeTarget")]
    assert not [c for c in d.cdp.calls if c[2] == sid]
    assert tid not in d.tab_owner


def test_scoped_tab_is_free_again_after_end():
    d, owned = _daemon_with_scope()
    [end] = _run(d, _scoped(owned, meta="end_owned_target"))
    assert end.get("ok") is True
    assert not d.scopes.holds_target(owned["target_id"])
    assert ("Target.disposeBrowserContext", {"browserContextId": "owned-ctx"}, None) in d.cdp.calls


def test_shutdown_closes_open_scopes():
    d, owned = _daemon_with_scope()
    errors = asyncio.run(d.scopes.close_all())
    assert errors == []
    assert not d.scopes.holds_target(owned["target_id"])
