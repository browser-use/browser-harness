from browser_harness import _ipc as ipc


import asyncio
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from browser_harness import daemon


def test_daemons_sharing_a_runtime_dir_never_share_files(monkeypatch):
    """BH_RUNTIME_DIR used to give every daemon the same bu.sock/bu.pid/bu.log
    unless BH_RUNTIME_DIR_SHARED=1 was also set, so parallel daemons cross-wired."""
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR", "/tmp/bh")
    monkeypatch.setattr(ipc, "BH_TMP_DIR", "/tmp/bh")

    for path in (ipc._sock_path, ipc.pid_path, ipc.log_path, ipc.port_path):
        assert path("a") != path("b")
        assert path("a").name.startswith("bu-a.")


@pytest.fixture
def short_runtime(monkeypatch):
    # AF_UNIX paths are capped at 104 bytes on macOS; pytest's tmp_path can be longer.
    runtime = Path(tempfile.mkdtemp(prefix="bh"))
    monkeypatch.setattr(ipc, "_RUNTIME", runtime)
    yield runtime
    shutil.rmtree(runtime, ignore_errors=True)


@pytest.mark.skipif(ipc.IS_WINDOWS, reason="AF_UNIX")
def test_two_daemons_in_one_runtime_dir_answer_separately(short_runtime):

    def handler_for(name):
        async def handler(reader, writer):
            await reader.readline()
            writer.write((json.dumps({"pong": True, "who": name}) + "\n").encode())
            await writer.drain()
            writer.close()
        return handler

    async def main():
        servers = [asyncio.create_task(ipc.serve(n, handler_for(n))) for n in ("a", "b")]
        await asyncio.sleep(0.1)
        try:
            def ask(name):
                c, token = ipc.connect(name)
                try:
                    return ipc.request(c, token, {"meta": "ping"})["who"]
                finally:
                    c.close()
            return await asyncio.to_thread(ask, "a"), await asyncio.to_thread(ask, "b")
        finally:
            for t in servers:
                t.cancel()

    assert asyncio.run(main()) == ("a", "b")


class _EchoDaemon:
    async def handle(self, req):
        return {"result": {"length": len(req["params"]["expression"])}}


def _roundtrip(monkeypatch, payload_bytes):
    """Send one request of payload_bytes through the daemon's real IPC handler."""
    monkeypatch.setattr(daemon, "log", lambda msg: None)

    async def main():
        server = asyncio.create_task(ipc.serve("big", daemon._ipc_handler(_EchoDaemon())))
        await asyncio.sleep(0.1)
        try:
            def send():
                c, token = ipc.connect("big", timeout=30)
                try:
                    return ipc.request(c, token, {"method": "Runtime.evaluate", "params": {"expression": "x" * payload_bytes}})
                finally:
                    c.close()
            return await asyncio.to_thread(send)
        finally:
            server.cancel()

    return asyncio.run(main())


@pytest.mark.skipif(ipc.IS_WINDOWS, reason="AF_UNIX")
def test_ipc_accepts_a_10mb_upload_sized_request(short_runtime, monkeypatch):
    """A 10 MB file as base64 is ~14 MB. asyncio's default 64 KiB line limit
    broke every cloud upload over ~48 KB."""
    size = 10 * 1024 * 1024 * 4 // 3 + 1024
    assert _roundtrip(monkeypatch, size) == {"result": {"length": size}}


@pytest.mark.skipif(ipc.IS_WINDOWS, reason="AF_UNIX")
def test_oversized_ipc_request_gets_a_clear_error_not_a_broken_pipe(short_runtime, monkeypatch):
    monkeypatch.setattr(ipc, "MAX_REQUEST_BYTES", 1 << 20)

    resp = _roundtrip(monkeypatch, 3 << 20)

    assert "over the 1 MiB limit" in resp["error"]


@pytest.mark.skipif(ipc.IS_WINDOWS, reason="AF_UNIX")
def test_too_long_socket_path_names_the_fix(short_runtime, monkeypatch):
    runtime = short_runtime / ("d" * 120)
    runtime.mkdir()
    monkeypatch.setattr(ipc, "_RUNTIME", runtime)

    async def handler(reader, writer):
        writer.close()

    with pytest.raises(RuntimeError, match="BH_RUNTIME_DIR"):
        asyncio.run(ipc.serve("x", handler))


def test_remote_marker_roundtrip(short_runtime):

    assert ipc.read_remote_marker("w") is None
    ipc.write_remote_marker("w", "cloud", "b-1")
    assert ipc.read_remote_marker("w") == {"kind": "cloud", "browser_id": "b-1"}
    ipc.clear_remote_marker("w")
    assert ipc.read_remote_marker("w") is None


# --- identify(): ping payload sanitation ---

class _FakeConn:
    def close(self): pass


def _patch_identify_response(monkeypatch, response):
    """Stub connect() and request() so identify() sees `response` as the JSON
    parsed from the daemon's reply, exactly as it would arrive over the wire."""
    monkeypatch.setattr(ipc, "connect", lambda name, timeout=1.0: (_FakeConn(), "tok"))
    monkeypatch.setattr(ipc, "request", lambda conn, tok, msg: response)


def test_identify_returns_pid_for_well_formed_ping_reply(monkeypatch):
    _patch_identify_response(monkeypatch, {"pong": True, "pid": 4242})

    assert ipc.identify("default", timeout=0.0) == 4242


def test_identify_rejects_boolean_pid(monkeypatch):
    """isinstance(True, int) is True in Python; a hostile or buggy daemon
    that replies {"pid": True} would otherwise yield PID 1 (init on POSIX),
    which os.kill(1, SIGTERM) would target. Reject it explicitly."""
    _patch_identify_response(monkeypatch, {"pong": True, "pid": True})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_rejects_boolean_false_pid(monkeypatch):
    """False is also an int subclass and would yield PID 0."""
    _patch_identify_response(monkeypatch, {"pong": True, "pid": False})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_returns_none_when_pid_field_missing(monkeypatch):
    """Pre-upgrade daemons reply {pong: True} only — no pid. identify must
    return None so callers know they have no verified PID to signal, while
    still letting alive-checks via ipc.ping() succeed."""
    _patch_identify_response(monkeypatch, {"pong": True})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_handles_non_dict_ping_payload(monkeypatch):
    """request() can deserialize any valid JSON value. A stale or hostile
    endpoint replying with a list / scalar / null would crash a naive
    resp.get() with AttributeError; identify must absorb that and return None."""
    for payload in ([1, 2, 3], "hello", 42, None):
        _patch_identify_response(monkeypatch, payload)
        assert ipc.identify("default", timeout=0.0) is None, (
            f"identify() should reject non-dict ping payload: {payload!r}"
        )


def test_identify_returns_none_when_pong_is_not_true(monkeypatch):
    _patch_identify_response(monkeypatch, {"pong": False, "pid": 4242})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_rejects_zero_and_negative_pids(monkeypatch):
    """os.kill semantics on POSIX: pid=0 signals every process in the calling
    process group; pid=-1 signals every process the caller can; pid<-1 signals
    the corresponding process group. None of these are valid daemon PIDs and
    forwarding any of them to os.kill would be catastrophic."""
    for bad_pid in (0, -1, -42, -99999):
        _patch_identify_response(monkeypatch, {"pong": True, "pid": bad_pid})
        assert ipc.identify("default", timeout=0.0) is None, (
            f"identify() must reject non-positive pid {bad_pid!r}"
        )


# --- ping(): same payload sanitation ---

def _patch_ping_response(monkeypatch, response):
    monkeypatch.setattr(ipc, "connect", lambda name, timeout=1.0: (_FakeConn(), "tok"))
    monkeypatch.setattr(ipc, "request", lambda conn, tok, msg: response)


def test_ping_returns_true_for_well_formed_pong(monkeypatch):
    _patch_ping_response(monkeypatch, {"pong": True})

    assert ipc.ping("default", timeout=0.0) is True


def test_ping_handles_non_dict_payload(monkeypatch):
    """Same regression class as identify(): if a stale or hostile endpoint
    replies with a list / scalar / null, ping() must return False rather than
    raising AttributeError on resp.get(). restart_daemon() now calls ping() on
    the fallback path, so an unhandled raise here would abort cleanup."""
    for payload in ([1, 2, 3], "hello", 42, None):
        _patch_ping_response(monkeypatch, payload)
        assert ipc.ping("default", timeout=0.0) is False, (
            f"ping() should reject non-dict payload: {payload!r}"
        )


def test_ping_returns_false_when_pong_field_is_missing_or_not_true(monkeypatch):
    for resp in ({}, {"pong": False}, {"pong": "yes"}, {"pong": 1}):
        _patch_ping_response(monkeypatch, resp)
        assert ipc.ping("default", timeout=0.0) is False, (
            f"ping() should require pong is exactly True; got: {resp!r}"
        )
