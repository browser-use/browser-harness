"""Connection/target invariants for independent CLI processes sharing Chrome."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from browser_harness import admin, daemon, helpers


def test_initializing_target_is_not_used_early_or_cancelled_by_one_client():
    async def run():
        d = daemon.Daemon()
        d.cdp = Mock(send_raw=AsyncMock(return_value={"sessionId": "session"}))
        enabling, finish = asyncio.Event(), asyncio.Event()

        async def enable(_session):
            enabling.set()
            await finish.wait()

        d._enable_default_domains = enable
        first = asyncio.create_task(d._ensure_target_session("tab"))
        await enabling.wait()
        second = asyncio.create_task(d._ensure_target_session("tab"))
        await asyncio.sleep(0)
        assert not second.done(), "cached attachment must wait for domain initialization"
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        finish.set()
        assert await second == "session"
        assert d.cdp.send_raw.await_count == 1
        assert d._target_attach_tasks == {}

    asyncio.run(run())


def test_shutdown_drains_pending_attachments():
    async def run():
        d = daemon.Daemon()
        attaching = asyncio.Event()

        async def send(*_args, **_kwargs):
            attaching.set()
            await asyncio.Event().wait()

        d.cdp = Mock(send_raw=send)
        request = asyncio.create_task(d._ensure_target_session("tab"))
        await attaching.wait()
        d._shutting_down = True
        assert await d._cancel_and_drain_recoveries()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(request, timeout=1)
        assert d._target_attach_tasks == {}

    asyncio.run(run())


def test_closed_default_tab_does_not_make_connection_unhealthy():
    d = daemon.Daemon()
    d.target_id = "closed-tab"
    d.session = "closed-session"
    d.cdp = Mock(send_raw=AsyncMock(return_value={"targetInfos": []}))
    assert asyncio.run(d.handle({"meta": "connection_status"})) == {
        "target_id": None, "session_id": None, "page": None,
    }
    d.cdp.send_raw.assert_awaited_once_with("Target.getTargets")


def test_explicit_raw_session_is_preserved_for_target_domain():
    d = daemon.Daemon()
    d.cdp = Mock(send_raw=AsyncMock(return_value={}))
    result = asyncio.run(d.handle({
        "method": "Target.setAutoAttach", "session_id": "iframe-session",
        "params": {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True},
    }))
    assert result == {"result": {}}
    assert d.cdp.send_raw.call_args.kwargs["session_id"] == "iframe-session"


def test_detachment_releases_target_buffers():
    d = daemon.Daemon()
    d._remember_target_session("tab", "session")
    d._record_event("Page.javascriptDialogOpening", {"message": "example"}, "session")
    d._record_event("Target.detachedFromTarget", {"sessionId": "session"})
    assert not d.target_sessions
    assert not d.session_targets
    assert not d.events_by_target
    assert not d.dialogs_by_target


def test_start_subscribes_to_target_lifecycle_before_attaching(monkeypatch):
    client = Mock()
    client.start = AsyncMock()
    client._event_registry.handle_event = AsyncMock()
    events = []

    async def send(method, params):
        events.append(method)
        assert params == {"discover": True}
        # Prove discovery is already tapped, not just that it was sent.
        await client._event_registry.handle_event("Target.targetCreated", {})

    client.send_raw = send
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    monkeypatch.setattr(daemon, "get_ws_url", lambda: "ws://127.0.0.1:9222/test")
    monkeypatch.setattr(daemon, "CDPClient", lambda _: client)
    d = daemon.Daemon()

    async def attach():
        assert len(d.events) == 1
        events.append("attach")

    d.attach_first_page = attach
    asyncio.run(d.start())
    assert events == ["Target.setDiscoverTargets", "attach"]


def test_local_websocket_has_no_approval_or_ping_deadline(monkeypatch):
    import websockets

    connect = AsyncMock(return_value=Mock())
    monkeypatch.setattr(websockets, "connect", connect)
    client = daemon._PatientCDPClient("ws://127.0.0.1:9222/test")
    client._handle_messages = AsyncMock()
    asyncio.run(client.start())
    assert connect.call_args.kwargs["open_timeout"] is None
    assert connect.call_args.kwargs["ping_interval"] is None


def test_scoped_remote_without_discovery_can_still_start(monkeypatch):
    client = Mock(start=AsyncMock(), send_raw=AsyncMock(side_effect=RuntimeError("unsupported")))
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    monkeypatch.setattr(daemon, "get_ws_url", lambda: "ws://127.0.0.1:9222/test")
    monkeypatch.setattr(daemon, "CDPClient", lambda _: client)
    d = daemon.Daemon()
    d.attach_first_page = AsyncMock()
    asyncio.run(d.start())
    d.attach_first_page.assert_awaited_once()


def test_old_daemon_has_actionable_upgrade_error_without_restart(monkeypatch):
    sock = Mock()
    monkeypatch.setattr(helpers.ipc, "connect", lambda *a, **kw: (sock, None))
    monkeypatch.setattr(helpers.ipc, "request", lambda *a: {"error": "'method'"})
    with pytest.raises(RuntimeError, match="predates per-tab routing"):
        helpers._send({"meta": "prepare_target", "target_id": "tab"})
    sock.close.assert_called_once()


@pytest.mark.parametrize("timeout", [False, True])
def test_health_probe_closes_socket_and_never_restarts_on_timeout(monkeypatch, timeout):
    sock = Mock()
    monkeypatch.setattr(admin, "daemon_alive", lambda _: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda *a, **kw: (sock, None))
    request = Mock(side_effect=TimeoutError() if timeout else None, return_value={"result": {}})
    monkeypatch.setattr(admin.ipc, "request", request)
    monkeypatch.setattr(admin, "restart_daemon", lambda *a: pytest.fail("unexpected restart"))
    monkeypatch.setattr(admin, "stop_remote_daemon", lambda *a: pytest.fail("unexpected stop"))
    if timeout:
        with pytest.raises(RuntimeError, match="left running"):
            admin.ensure_daemon()
    else:
        admin.ensure_daemon()
    assert request.call_count == 1
    sock.close.assert_called_once()


def test_default_screenshots_are_unique_and_preserved(monkeypatch, fake_png, tmp_path):
    monkeypatch.setattr(helpers.ipc, "_TMP", tmp_path)
    monkeypatch.setattr(helpers, "cdp", lambda *a, **kw: {"data": fake_png(10, 10)})
    first = Path(helpers.capture_screenshot())
    original = first.read_bytes()
    second = Path(helpers.capture_screenshot())
    assert first != second
    assert first.read_bytes() == original == second.read_bytes()


def test_implicit_target_is_pinned_once_not_daemon_global(monkeypatch):
    requests = []
    monkeypatch.setattr(helpers, "_TARGET_ID", None)

    def send(req, **kwargs):
        requests.append(req)
        if req.get("meta") == "current_tab":
            return {"targetId": "initial", "url": "about:blank", "title": ""}
        return {"result": {}}

    monkeypatch.setattr(helpers, "_send", send)
    helpers.cdp("Runtime.evaluate", expression="1")
    helpers.cdp("Page.captureScreenshot")
    assert requests[0] == {"meta": "current_tab"}
    assert len(requests) == 3
    assert [r["target_id"] for r in requests[1:]] == ["initial", "initial"]
