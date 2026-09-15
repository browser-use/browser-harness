import asyncio
import json
import os
import sys
import threading
import time

import pytest

from browser_harness import daemon, sedu_login


HERMES_CHECKOUT = os.environ.get("HERMES_CHECKOUT")
pytestmark = pytest.mark.skipif(not HERMES_CHECKOUT, reason="set HERMES_CHECKOUT for cross-repo test")
if HERMES_CHECKOUT:
    sys.path.insert(0, HERMES_CHECKOUT)
    from hermes_cli import browser_login as hermes_login


class EventingCDP:
    def __init__(self):
        self.calls = []
        self.daemon = None
        self.snapshot_count = 0

    async def send_raw(self, method, params=None, session_id=None):
        params = params or {}
        self.calls.append((method, params, session_id))
        if method == "Page.navigate":
            return {"loaderId": "loader-1"}
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"loaderId": "loader-1"}}}
        if method == "Runtime.evaluate":
            if params.get("expression") == sedu_login._VALIDATE_FORM:
                return {"result": {"value": {
                    "href": sedu_login.FORM_ACTION, "title": "login", "body": "",
                    "ready": "complete", "user": True, "password": True,
                    "submit": True, "action": sedu_login.FORM_ACTION, "method": "post",
                }}}
            if params.get("expression") == sedu_login._DOCUMENT:
                return {"result": {"objectId": "document-1"}}
            self.snapshot_count += 1
            if self.snapshot_count == 1:
                value = {"href": sedu_login.FORM_ACTION, "title": "login", "body": "",
                         "ready": "complete", "protected": [False, False, False], "identity": 1}
            else:
                value = {"href": "https://s-edu.cloud/npms/", "title": "S-EDU", "body": "",
                         "ready": "complete", "protected": [True, True, True], "identity": 2}
            return {"result": {"value": value}}
        if method == "Runtime.callFunctionOn":
            if params.get("functionDeclaration") == sedu_login._SUBMIT_FUNCTION:
                self.daemon._record_event("Network.requestWillBeSent", {
                    "request": {"postData": "username=sentinel-user&password=sentinel-password"},
                }, session_id)
            return {"result": {"value": True}}
        raise AssertionError(method)


class BlockedCDP(EventingCDP):
    def __init__(self, entered):
        super().__init__()
        self.entered = entered

    async def send_raw(self, method, params=None, session_id=None):
        if method == "Page.navigate":
            self.calls.append((method, params or {}, session_id))
            self.entered.set()
            await asyncio.Event().wait()
        raise AssertionError("browser mutation continued after cancellation")


def _harness_daemon(cdp):
    value = daemon.Daemon()
    value.cdp = cdp
    cdp.daemon = value
    value.target_id = "target-1"
    value.session = "session-1"
    value._session_generation = 1
    return value


def _start_server(socket_path, cdp):
    ready = threading.Event()
    stop = threading.Event()
    state = {}

    def serve():
        async def main():
            d = _harness_daemon(cdp)
            state["daemon"] = d
            server = await asyncio.start_unix_server(
                lambda reader, writer: daemon._connection_handler(d, reader, writer),
                path=str(socket_path),
            )
            ready.set()
            while not stop.is_set():
                await asyncio.sleep(0.01)
            server.close()
            await server.wait_closed()
        asyncio.run(main())

    thread = threading.Thread(target=serve)
    thread.start()
    assert ready.wait(2)
    return stop, thread, state


def _client(monkeypatch, tmp_path):
    socket_path = tmp_path / "sedu.sock"
    pid_path = tmp_path / "sedu.pid"
    pid_path.write_text(str(os.getpid()))
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    monkeypatch.setattr(hermes_login, "_socket_path", lambda _session: socket_path)
    monkeypatch.setattr(hermes_login, "_pid_path", lambda _session: pid_path)
    monkeypatch.setattr(hermes_login, "_verify_harness_process", lambda _pid: None)
    target = hermes_login.BrowserLoginTarget("s-edu.cloud", "primary", "sedu-primary", "sedu-v1")
    return socket_path, hermes_login.HarnessLoginClient(target, timeout=40)


def test_actual_hermes_client_to_actual_harness_connection_handler(monkeypatch, tmp_path):
    socket_path, client = _client(monkeypatch, tmp_path)
    cdp = EventingCDP()
    stop, thread, state = _start_server(socket_path, cdp)
    try:
        client.begin()
        result = client.submit(hermes_login._secret_payload("sentinel-user", "sentinel-password"))
        client.acknowledge_handoff()
    finally:
        stop.set()
        thread.join(2)
    assert result == {"status": "success", "state": "active"}
    assert [call[0] for call in cdp.calls].count("Page.navigate") == 1
    assert state["daemon"]._sensitive_event_session is None
    assert "sentinel" not in json.dumps(list(state["daemon"].events))


def test_actual_client_abort_cancels_actual_handler_adapter(monkeypatch, tmp_path):
    socket_path, client = _client(monkeypatch, tmp_path)
    entered = threading.Event()
    cdp = BlockedCDP(entered)
    stop, server_thread, state = _start_server(socket_path, cdp)
    outcome = {}
    client.begin()
    submitter = threading.Thread(target=lambda: outcome.setdefault(
        "error", pytest.raises(OSError, client.submit,
                                hermes_login._secret_payload("sentinel-user", "sentinel-password"))
    ))
    submitter.start()
    assert entered.wait(2)
    client.abort()
    submitter.join(2)
    stop.set()
    server_thread.join(2)
    assert not submitter.is_alive()
    assert [call[0] for call in cdp.calls] == ["Page.navigate"]
    assert state["daemon"]._login_transaction is None


@pytest.mark.parametrize("frame", [
    lambda tx: daemon.ipc.LOGIN_FRAME_HEADER.pack(99, bytes.fromhex(tx), 0),
    lambda tx: daemon.ipc.LOGIN_FRAME_HEADER.pack(
        daemon.ipc.LOGIN_HANDOFF_ACK_OPCODE, b"x" * 16, 0
    ),
])
def test_actual_handler_quarantines_invalid_or_wrong_ack(monkeypatch, tmp_path, frame):
    socket_path, client = _client(monkeypatch, tmp_path)
    stop, thread, state = _start_server(socket_path, EventingCDP())
    try:
        client.begin()
        result = client.submit(hermes_login._secret_payload(
            "sentinel-user", "sentinel-password"
        ))
        assert result == {"status": "success", "state": "active"}
        client.connection.sendall(frame(client.transaction_id))
        response = hermes_login._recv_json_line(client.connection, time.monotonic() + 1)
        assert response == {"error": "invalid_login_frame"}
        deadline = time.monotonic() + 1
        while not state["daemon"]._execution_quarantined and time.monotonic() < deadline:
            time.sleep(0.01)
        assert state["daemon"]._execution_quarantined is True
        assert asyncio.run(state["daemon"].handle({"meta": "session"})) == {
            "error": "cdp_transport_quarantined"
        }
    finally:
        client.abort()
        stop.set()
        thread.join(2)
