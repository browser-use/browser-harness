"""Cross-platform IPC transport tests.

Logic tests use monkeypatch for sys.platform, so both OS branches
are covered on any host. Tests that actually bind a socket use the
host's real OS — we just ensure UDS/TCP behavior is equivalent.
"""
import asyncio
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

import pytest

import transport


# --- state_dir --------------------------------------------------------------

def test_state_dir_posix_returns_tmp(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert transport.state_dir() == Path("/tmp")


def test_state_dir_windows_uses_temp_env(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("TEMP", str(tmp_path))
    assert transport.state_dir() == tmp_path


def test_state_dir_windows_falls_back_to_gettempdir(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.delenv("TMP", raising=False)
    # gettempdir always returns something even without TEMP/TMP
    assert transport.state_dir() == Path(tempfile.gettempdir())


# --- path helpers -----------------------------------------------------------

def test_endpoint_path_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert transport.endpoint_path("default") == Path("/tmp/bu-default.endpoint")
    assert transport.endpoint_path("work") == Path("/tmp/bu-work.endpoint")


def test_endpoint_path_windows_under_temp(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("TEMP", str(tmp_path))
    assert transport.endpoint_path("default") == tmp_path / "bu-default.endpoint"


def test_pid_path_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert transport.pid_path("default") == Path("/tmp/bu-default.pid")


def test_log_path_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert transport.log_path("default") == Path("/tmp/bu-default.log")


def test_version_cache_path_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert transport.version_cache_path() == Path("/tmp/bu-version-cache.json")


def test_version_cache_path_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("TEMP", str(tmp_path))
    assert transport.version_cache_path() == tmp_path / "bu-version-cache.json"


# --- kind / is_tcp ----------------------------------------------------------

def test_is_tcp_false_on_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert transport.is_tcp() is False


def test_is_tcp_true_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert transport.is_tcp() is True


# --- endpoint descriptor I/O ------------------------------------------------

def test_write_endpoint_atomic_uses_replace(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)
    desc = {"v": 1, "kind": "tcp", "host": "127.0.0.1", "port": 12345}
    transport.write_endpoint("default", desc)
    on_disk = json.loads((tmp_path / "bu-default.endpoint").read_text())
    assert on_disk == desc
    # no orphan .tmp file left behind
    assert list(tmp_path.glob("*.tmp")) == []


def test_read_endpoint_returns_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)
    assert transport.read_endpoint("default") is None


def test_read_endpoint_round_trips(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)
    desc = {"v": 1, "kind": "uds", "path": "/tmp/bu-foo.sock"}
    transport.write_endpoint("foo", desc)
    assert transport.read_endpoint("foo") == desc


def test_read_endpoint_returns_none_for_malformed_json(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)
    (tmp_path / "bu-broken.endpoint").write_text("not json")
    assert transport.read_endpoint("broken") is None


def test_cleanup_endpoint_removes_file(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)
    transport.write_endpoint("x", {"v": 1, "kind": "tcp", "host": "127.0.0.1", "port": 1})
    assert (tmp_path / "bu-x.endpoint").exists()
    transport.cleanup_endpoint("x")
    assert not (tmp_path / "bu-x.endpoint").exists()


def test_cleanup_endpoint_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)
    transport.cleanup_endpoint("never-existed")  # must not raise


# --- popen detach kwargs ----------------------------------------------------

def test_popen_detach_kwargs_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    kw = transport.popen_detach_kwargs()
    assert kw == {"start_new_session": True}


def test_popen_detach_kwargs_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    kw = transport.popen_detach_kwargs()
    assert "creationflags" in kw
    # Numeric flags per MSDN so this test works on POSIX runners too
    # (subprocess module there has no DETACHED_PROCESS attribute).
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    assert kw["creationflags"] & DETACHED_PROCESS
    assert kw["creationflags"] & CREATE_NEW_PROCESS_GROUP
    assert "start_new_session" not in kw


# --- real-socket integration (uses host OS) --------------------------------
# These don't monkeypatch — they exercise the REAL transport against the
# REAL operating system. On Linux/macOS this drives the UDS branch; on
# Windows it drives the TCP branch. Both must work end-to-end.


def test_is_alive_false_when_no_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)
    assert transport.is_alive("ghost") is False


def test_is_alive_false_when_port_not_listening(tmp_path, monkeypatch):
    """Endpoint file points at 127.0.0.1:port but nothing is listening."""
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)
    # grab + release a port to get a guaranteed-free number
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    free_port = s.getsockname()[1]
    s.close()
    transport.write_endpoint("dead", {"v": 1, "kind": "tcp",
                                      "host": "127.0.0.1", "port": free_port})
    assert transport.is_alive("dead") is False


def _run_server_and_connect(tmp_path, name):
    """Helper: spin up transport.start_ipc_server, connect via
    open_client_sync on an executor thread (sync calls would otherwise
    deadlock the event loop that's running the handler), assert echo."""
    async def handler(reader, writer):
        line = await reader.readline()
        writer.write(line)  # echo
        await writer.drain()
        writer.close()

    def sync_client():
        s = transport.open_client_sync(name, timeout=5)
        try:
            s.sendall(b'{"hello":1}\n')
            data = b""
            while not data.endswith(b"\n"):
                chunk = s.recv(1024)
                if not chunk:
                    break
                data += chunk
            return data
        finally:
            s.close()

    async def driver():
        server = await transport.start_ipc_server(name, handler)
        async with server:
            assert transport.is_alive(name) is True
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, sync_client)
            assert data == b'{"hello":1}\n'
            server.close()
            await server.wait_closed()
        transport.cleanup_endpoint(name)
        transport.cleanup_server_files(name)

    asyncio.run(driver())


def test_roundtrip_client_server_local_os(tmp_path, monkeypatch):
    """Full integration on the current OS — UDS on POSIX, TCP on Windows."""
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)
    _run_server_and_connect(tmp_path, "default")


def test_descriptor_has_version_field(tmp_path, monkeypatch):
    """Forward-compat: descriptor always carries `v: 1`."""
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)

    async def handler(reader, writer):
        writer.close()

    async def driver():
        server = await transport.start_ipc_server("vtest", handler)
        try:
            desc = transport.read_endpoint("vtest")
            assert desc is not None
            assert desc["v"] == 1
            assert desc["kind"] in ("uds", "tcp")
        finally:
            server.close()
            await server.wait_closed()
            transport.cleanup_endpoint("vtest")
            transport.cleanup_server_files("vtest")

    asyncio.run(driver())


@pytest.mark.skipif(sys.platform == "win32",
                    reason="UDS chmod only meaningful on POSIX")
def test_uds_socket_file_is_0600_on_posix(tmp_path, monkeypatch):
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)

    async def handler(reader, writer):
        writer.close()

    async def driver():
        server = await transport.start_ipc_server("perms", handler)
        try:
            desc = transport.read_endpoint("perms")
            assert desc["kind"] == "uds"
            mode = os.stat(desc["path"]).st_mode & 0o777
            assert mode == 0o600, f"expected 0o600 got {oct(mode)}"
        finally:
            server.close()
            await server.wait_closed()
            transport.cleanup_endpoint("perms")
            transport.cleanup_server_files("perms")

    asyncio.run(driver())


@pytest.mark.skipif(sys.platform != "win32",
                    reason="TCP loopback bind only exercised on Windows branch")
def test_tcp_binds_loopback_only_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(transport, "state_dir", lambda: tmp_path)

    async def handler(reader, writer):
        writer.close()

    async def driver():
        server = await transport.start_ipc_server("wintcp", handler)
        try:
            desc = transport.read_endpoint("wintcp")
            assert desc["kind"] == "tcp"
            assert desc["host"] == "127.0.0.1"  # NEVER 0.0.0.0
            assert isinstance(desc["port"], int) and desc["port"] > 0
        finally:
            server.close()
            await server.wait_closed()
            transport.cleanup_endpoint("wintcp")
            transport.cleanup_server_files("wintcp")

    asyncio.run(driver())
