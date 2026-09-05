import asyncio
from types import SimpleNamespace

import pytest

from browser_harness import daemon, helpers
from browser_harness._events import EventHistory, RequestState


def event(method="Network.requestWillBeSent", request="r", session="active"):
    return {"method": method, "params": {"requestId": request}, "session_id": session}


def test_independent_readers_and_legacy_drain_keep_same_history():
    history = EventHistory()
    cursor = history.read()["cursor"]
    history.append(event())
    first = history.read(cursor)
    assert history.drain() == [event()]
    assert history.drain() == []
    assert history.read(cursor) == first
    assert history.read(first["cursor"])["events"] == []
    history.append(event("Network.loadingFinished"))
    assert [e["sequence"] for e in history.read(first["cursor"])["events"]] == [2]


def test_overflow_reports_exact_gap_and_payload_truncation():
    history = EventHistory(capacity=2, max_event_bytes=200)
    cursor = history.read()["cursor"]
    for i in range(4):
        history.append(event(request=str(i)))
    result = history.read(cursor)
    assert result["dropped"] == 2
    assert [e["sequence"] for e in result["events"]] == [3, 4]
    history.append({"method": "Runtime.consoleAPICalled", "params": {"args": ["x" * 1000]}, "session_id": "active"})
    last = history.read(result["cursor"])["events"][0]
    assert last["truncated"] is True
    assert last["params"] == {}
    assert len(history.events) == 2


def test_cursor_restart_validation_and_session_filter():
    first, second = EventHistory(), EventHistory()
    with pytest.raises(RuntimeError, match="EventCursorExpired"):
        second.read(first.read()["cursor"])
    for sequence in [-1, 9, True, "0"]:
        with pytest.raises(ValueError):
            first.read({"generation": first.generation, "sequence": sequence})
    first.append(event(session="background"))
    first.append(event(session="active"))
    result = first.read(session_id="active")
    assert len(result["events"]) == 1
    assert result["events"][0]["session_id"] == "active"
    assert result["cursor"]["sequence"] == 2


def ready_daemon():
    d = daemon.Daemon()
    d.cdp = SimpleNamespace(ws=SimpleNamespace(state=1))
    d.session = "active"
    d.network = RequestState("active")
    d.network.enabled = True
    d._record_event("Page.frameNavigated", {"frame": {"id": "root"}}, "active")
    return d


@pytest.mark.parametrize("completion", ["Network.loadingFinished", "Network.loadingFailed"])
def test_inflight_survives_readers_ring_overflow_and_redirects(completion):
    async def run():
        d = ready_daemon()
        d.events = EventHistory(capacity=2)
        d._record_event(**event())
        d._record_event("Network.requestWillBeSent", {"requestId": "r", "redirectResponse": {"status": 302}}, "active")
        await d.handle({"meta": "drain_events"})
        for _ in range(4):
            d._record_event("Runtime.consoleAPICalled", {}, "background")
        assert (await d.handle({"meta": "network_status", "session_id": "active"}))["inflight"] == 1
        d._record_event(completion, {"requestId": "r"}, "background")
        assert d.network.snapshot()["inflight"] == 1
        d._record_event(completion, {"requestId": "r"}, "active")
        assert d.network.snapshot()["inflight"] == 0
    asyncio.run(run())


def test_unknown_coverage_and_tracking_overflow_fail_closed():
    tracker = RequestState("s", max_requests=1)
    tracker.record("Page.frameNavigated", {"frame": {"id": "root"}}, "s")
    tracker.enabled = True
    assert tracker.snapshot()["known"] is False
    tracker.record("Page.frameNavigated", {"frame": {"id": "iframe", "parentId": "root"}}, "s")
    assert tracker.snapshot()["known"] is False
    tracker.record("Page.frameNavigated", {"frame": {"id": "root"}}, "s")
    assert tracker.snapshot()["known"] is True
    tracker.record("Network.requestWillBeSent", {"requestId": "one"}, "s")
    tracker.record("Network.requestWillBeSent", {"requestId": "two"}, "s")
    tracker.record("Network.loadingFinished", {"requestId": "one"}, "s")
    assert tracker.snapshot()["inflight"] == 0
    assert tracker.snapshot()["known"] is False
    assert tracker.snapshot()["reason"] == "request tracking overflow"


def test_detach_and_tab_switch_invalidate_waiter():
    async def run():
        d = ready_daemon()
        d._record_event("Target.detachedFromTarget", {"sessionId": "active"})
        assert d.network.snapshot()["known"] is False
        d.session = "new-session"
        response = await d.handle({"meta": "network_status", "session_id": "active"})
        assert "session changed" in response["error"]
    asyncio.run(run())


def test_network_enable_failure_is_not_idle(monkeypatch):
    class Broken:
        async def send_raw(self, method, **kwargs):
            if method == "Network.enable":
                raise RuntimeError("disconnected")
            return {}
    monkeypatch.setattr(daemon, "log", lambda msg: None)
    d = ready_daemon()
    d.cdp = Broken()
    asyncio.run(d._enable_default_domains("active"))
    assert d.network.snapshot()["known"] is False


def test_closed_websocket_cannot_report_idle():
    d = ready_daemon()
    d.cdp.ws.state = 3
    state = asyncio.run(d.handle({"meta": "network_status", "session_id": "active"}))
    assert state["known"] is False
    assert state["reason"] == "browser connection lost"


def test_wait_unknown_status_and_stale_daemon_raise(monkeypatch):
    monkeypatch.setattr(helpers, "_send", lambda req: {"session_id": "s"} if req.get("meta") == "session" else {})
    with pytest.raises(RuntimeError, match="Network idle unknown"):
        helpers.wait_for_network_idle()
