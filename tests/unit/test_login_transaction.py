import asyncio
import json
import struct

import pytest

from browser_harness import _ipc as ipc
from browser_harness import daemon


ADAPTER = "credential-form-v1"


@pytest.fixture(autouse=True)
def named_daemon(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "login-test")


def _daemon():
    d = daemon.Daemon()
    d.cdp = object()
    d.session = "session-1"
    d.target_id = "target-1"
    d._session_generation = 7
    return d


def test_begin_is_bounded_and_exclusive():
    async def run():
        d = _daemon()
        first = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="client-a")
        duplicate = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="client-b")
        collision = await d.handle({"method": "Runtime.evaluate", "params": {}}, owner="client-b")
        return first, duplicate, collision

    first, duplicate, collision = asyncio.run(run())
    assert set(first) == {"status", "transaction_id"}
    assert first["status"] == "awaiting_secret"
    assert duplicate == {"error": "login_transaction_active"}
    assert collision == {"error": "login_transaction_active"}


def test_begin_waits_for_in_flight_execution_and_blocks_new_execution():
    class BlockingCDP:
        def __init__(self):
            self.entered = asyncio.Event()
            self.release = asyncio.Event()
            self.calls = []

        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append(method)
            self.entered.set()
            await self.release.wait()
            return {"done": method}

    async def run():
        d = _daemon()
        cdp = BlockingCDP()
        d.cdp = cdp
        ordinary = asyncio.create_task(d.handle(
            {"method": "Runtime.evaluate", "params": {"expression": "1"}},
            owner="ordinary-before",
        ))
        await cdp.entered.wait()

        begin = asyncio.create_task(d.handle(
            {"meta": "login_begin", "adapter": ADAPTER}, owner="login"
        ))
        await asyncio.sleep(0)
        assert not begin.done()
        assert d._login_transaction is None

        # Liveness is unrelated to browser execution and must not queue behind it.
        ping = await asyncio.wait_for(d.handle({"meta": "ping"}), 0.1)

        cdp.release.set()
        ordinary_result = await ordinary
        begin_result = await begin
        blocked = await d.handle(
            {"method": "Runtime.evaluate", "params": {"expression": "2"}},
            owner="ordinary-after",
        )
        return ordinary_result, begin_result, blocked, ping, cdp.calls

    ordinary_result, begin_result, blocked, ping, calls = asyncio.run(run())
    assert ordinary_result == {"result": {"done": "Runtime.evaluate"}}
    assert begin_result["status"] == "awaiting_secret"
    assert blocked == {"error": "login_transaction_active"}
    assert ping["pong"] is True
    assert calls == ["Runtime.evaluate"]


@pytest.mark.parametrize("login_request", [
    {"meta": "login_begin", "adapter": "other"},
    {"meta": "login_begin", "adapter": ADAPTER, "url": "https://example.com"},
    {"meta": "login_begin", "adapter": ADAPTER, "selector": "#password"},
    {"meta": "login_begin", "adapter": ADAPTER, "javascript": "alert(1)"},
    {"meta": "login_begin", "adapter": ADAPTER, "credential_path": "/secret"},
    {"meta": "login_begin", "adapter": ADAPTER, "command": "printenv"},
])
def test_begin_rejects_unknown_adapter_and_extra_fields(login_request):
    assert asyncio.run(_daemon().handle(login_request, owner="client")) == {"error": "invalid_login_request"}


def test_wrong_stale_and_oversized_secret_do_not_escape():
    async def run():
        d = _daemon()
        begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="client")
        tx = begun["transaction_id"]
        wrong = await d.accept_login_secret("0" * 32, b"sentinel", owner="client")
        large = await d.accept_login_secret(tx, b"x" * (daemon.LOGIN_SECRET_MAX_BYTES + 1), owner="client")
        accepted = await d.accept_login_secret(tx, b"sentinel", owner="client")
        await d.release_login_owner("client")
        stale = await d.accept_login_secret(tx, b"sentinel", owner="client")
        return wrong, large, accepted, stale

    wrong, large, accepted, stale = asyncio.run(run())
    assert wrong == {"error": "wrong_login_transaction"}
    assert large == {"error": "secret_too_large"}
    assert accepted == {"status": "secret_received"}
    assert stale == {"error": "no_login_transaction"}
    assert "sentinel" not in json.dumps([wrong, large, accepted, stale])


def test_secret_fails_closed_when_binding_changed():
    async def run():
        d = _daemon()
        begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="client")
        d.session = "session-2"
        result = await d.accept_login_secret(begun["transaction_id"], b"sentinel", owner="client")
        return result, d._login_transaction

    result, transaction = asyncio.run(run())
    assert result == {"error": "stale_login_transaction"}
    assert transaction is None


def test_abort_requires_transaction_owner():
    async def run():
        d = _daemon()
        begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="client-a")
        cross_owner = await d.handle(
            {"meta": "login_abort", "transaction_id": begun["transaction_id"]}, owner="client-b"
        )
        still_active = d._login_transaction is not None
        binary_cross_owner = await d.accept_login_secret(
            begun["transaction_id"], b"sentinel", owner="client-b"
        )
        return cross_owner, binary_cross_owner, still_active

    cross_owner, binary_cross_owner, still_active = asyncio.run(run())
    assert cross_owner == {"error": "wrong_login_transaction"}
    assert binary_cross_owner == {"error": "wrong_login_transaction"}
    assert still_active is True


def test_abort_disconnect_timeout_and_shutdown_cleanup(monkeypatch):
    async def run():
        d = _daemon()
        one = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="a")
        assert await d.handle({"meta": "login_abort", "transaction_id": "0" * 32}, owner="a") == {
            "error": "wrong_login_transaction"
        }
        assert await d.handle({"meta": "login_abort", "transaction_id": one["transaction_id"]}, owner="a") == {
            "status": "aborted"
        }
        two = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="b")
        await d.release_login_owner("b")
        three = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="c")
        d._login_transaction.deadline = 0
        assert d.expire_login_transaction() is True
        four = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="d")
        d.stop = asyncio.Event()
        monkeypatch.setattr(daemon, "stop_remote", lambda strict=False: True)
        assert await d.handle({"meta": "shutdown"}, owner="admin") == {"ok": True}
        return two, three, four, d

    two, three, four, d = asyncio.run(run())
    assert all(item["status"] == "awaiting_secret" for item in (two, three, four))
    assert d._login_transaction is None


def test_binary_frame_is_bounded_and_not_json(monkeypatch):
    secret = b"binary-sentinel-password"
    tx = "0123456789abcdef0123456789abcdef"
    left, right = ipc.socket.socketpair()
    try:
        ipc.send_login_secret(left, tx, secret)
        frame = right.recv(4096)
    finally:
        left.close()
        right.close()
    assert frame == struct.pack("!B16sI", ipc.LOGIN_SECRET_OPCODE, bytes.fromhex(tx), len(secret)) + secret
    with pytest.raises(UnicodeDecodeError):
        frame.decode("utf-8")


def test_windows_secret_transport_fails_closed(monkeypatch):
    monkeypatch.setattr(ipc, "IS_WINDOWS", True)
    assert asyncio.run(_daemon().handle(
        {"meta": "login_begin", "adapter": ADAPTER}, owner="client"
    )) == {"error": "login_secret_transport_unsupported"}
    with pytest.raises(NotImplementedError, match="unsupported"):
        ipc.send_login_secret(object(), "0" * 32, b"secret")


def test_cloud_secret_transport_fails_closed(monkeypatch):
    monkeypatch.setattr(daemon, "REMOTE_ID", "cloud-browser")
    assert asyncio.run(_daemon().handle(
        {"meta": "login_begin", "adapter": ADAPTER}, owner="client"
    )) == {"error": "login_secret_transport_unsupported"}


async def _open_login_server(d):
    server = await asyncio.start_server(
        lambda reader, writer: daemon._connection_handler(d, reader, writer), "127.0.0.1", 0
    )
    reader, writer = await asyncio.open_connection("127.0.0.1", server.sockets[0].getsockname()[1])
    writer.write((json.dumps({"meta": "login_begin", "adapter": ADAPTER}) + "\n").encode())
    await writer.drain()
    begun = json.loads(await reader.readline())
    return server, reader, writer, begun


def test_serve_incomplete_payload_hits_absolute_deadline_and_cleans_up(monkeypatch):
    async def run():
        monkeypatch.setattr(daemon, "LOGIN_TIMEOUT_SECONDS", 0.05)
        d = _daemon()
        server, reader, writer, begun = await _open_login_server(d)
        raw_id = bytes.fromhex(begun["transaction_id"])
        writer.write(ipc.LOGIN_FRAME_HEADER.pack(ipc.LOGIN_SECRET_OPCODE, raw_id, 4) + b"x")
        await writer.drain()
        response = json.loads(await asyncio.wait_for(reader.readline(), 0.5))
        await asyncio.sleep(0)
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()
        return response, d._login_transaction

    response, transaction = asyncio.run(run())
    assert response == {"error": "login_frame_incomplete"}
    assert transaction is None


@pytest.mark.parametrize("opcode,length", [
    (ipc.LOGIN_ABORT_OPCODE, 1),
    (ipc.LOGIN_SECRET_OPCODE, 0),
    (ipc.LOGIN_SECRET_OPCODE, ipc.LOGIN_SECRET_MAX_BYTES + 1),
    (99, 0),
])
def test_serve_rejects_malformed_frames_without_trusting_payload(opcode, length):
    async def run():
        d = _daemon()
        server, reader, writer, begun = await _open_login_server(d)
        writer.write(ipc.LOGIN_FRAME_HEADER.pack(opcode, bytes.fromhex(begun["transaction_id"]), length))
        await writer.drain()
        response = json.loads(await asyncio.wait_for(reader.readline(), 0.5))
        await asyncio.sleep(0)
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()
        return response, d._login_transaction

    response, transaction = asyncio.run(run())
    assert response == {"error": "invalid_login_frame"}
    assert transaction is None


def test_serve_truncated_header_fails_closed():
    async def run():
        d = _daemon()
        server, reader, writer, _begun = await _open_login_server(d)
        writer.write(b"\x01truncated")
        await writer.drain()
        writer.write_eof()
        response = json.loads(await asyncio.wait_for(reader.readline(), 0.5))
        await asyncio.sleep(0)
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()
        return response, d._login_transaction

    response, transaction = asyncio.run(run())
    assert response == {"error": "login_frame_incomplete"}
    assert transaction is None
