"""Fix #2: daemon rebuilds the CDP websocket and retries once when it drops.

These exercise Daemon.handle()'s recovery branch and _conn_dead() without a real
browser: the CDP client is a stub, and _connect_cdp is monkeypatched to swap in a
fresh stub the way the real reconnect swaps in a live client.
"""
import asyncio

from browser_harness import daemon as d


class FakeCDP:
    def __init__(self, results=None, fail_times=0, exc=None):
        self.results = results or {}
        self.fail_times = fail_times
        self.exc = exc or ConnectionError("WebSocket connection closed")
        self.calls = []
        self.stopped = False

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.exc
        return self.results.get(method, {"ok": method})

    async def stop(self):
        self.stopped = True


def _daemon_with(dead):
    dm = d.Daemon()
    dm.cdp = dead
    dm.session = "sess-old"
    dm.target_id = "tgt-old"
    return dm


def test_conn_dead_matches_all_drop_signatures():
    assert d._conn_dead(ConnectionError("WebSocket connection closed"))
    assert d._conn_dead(ConnectionError("Client is stopping"))
    assert d._conn_dead(RuntimeError("Client is not started. Call start() first"))
    assert d._conn_dead(RuntimeError("no close frame received or sent"))

    class ConnectionClosedError(Exception):  # matched by type name, no websockets import
        pass

    assert d._conn_dead(ConnectionClosedError("1006"))
    # A normal CDP protocol error must NOT look like a dead socket.
    assert not d._conn_dead(RuntimeError("Cannot find context with specified id"))


def test_handle_reconnects_and_retries_on_dead_ws():
    dead = FakeCDP(fail_times=1)  # first call drops, would keep dropping if reused
    dm = _daemon_with(dead)
    good = FakeCDP(results={"Runtime.evaluate": {"value": 42}})

    async def fake_connect():
        dm.cdp = good
        dm.session = "sess-new"
        dm.target_id = "tgt-new"

    dm._connect_cdp = fake_connect

    resp = asyncio.run(dm.handle({"method": "Runtime.evaluate", "params": {"expression": "1"}}))

    assert resp == {"result": {"value": 42}}, resp
    assert dead.stopped is True                       # old client torn down
    assert good.calls[-1][2] == "sess-new"            # retry ran on the fresh session


def test_handle_reports_error_when_rebuild_fails():
    dead = FakeCDP(fail_times=1)
    dm = _daemon_with(dead)

    async def fake_connect():
        raise RuntimeError("Chrome gone")

    dm._connect_cdp = fake_connect

    resp = asyncio.run(dm.handle({"method": "Runtime.evaluate", "params": {}}))

    assert "error" in resp
    assert "CDP reconnect failed" in resp["error"]


def test_handle_passes_through_non_socket_errors_without_reconnect():
    boom = FakeCDP(fail_times=1, exc=RuntimeError("Cannot find context with specified id"))
    dm = _daemon_with(boom)

    called = {"connect": False}

    async def fake_connect():
        called["connect"] = True

    dm._connect_cdp = fake_connect

    resp = asyncio.run(dm.handle({"method": "Runtime.evaluate", "params": {}}))

    assert resp == {"error": "Cannot find context with specified id"}
    assert called["connect"] is False                 # a plain CDP error never reconnects
    assert boom.stopped is False


def test_reconnect_is_noop_when_client_already_swapped():
    """Second handler to see the same drop must reuse the rebuilt client, not
    tear down the live one."""
    dead = FakeCDP()
    dm = _daemon_with(dead)
    live = FakeCDP()
    dm.cdp = live  # simulate: another coroutine already reconnected

    async def fake_connect():
        raise AssertionError("_connect_cdp must not run when client already swapped")

    dm._connect_cdp = fake_connect

    asyncio.run(dm._reconnect(dead))                  # `dead` is the stale one

    assert dm.cdp is live
    assert dead.stopped is False
