from pathlib import Path
from unittest.mock import Mock

import transport


def test_paths_default_to_tmp_for_posix_compatibility(monkeypatch):
    monkeypatch.setattr(transport, "BASE", Path("/tmp"))

    sock, pid, log = transport.paths("demo")

    assert sock == Path("/tmp/bu-demo.sock")
    assert pid == Path("/tmp/bu-demo.pid")
    assert log == Path("/tmp/bu-demo.log")


def test_connect_socket_uses_unix_socket_when_available(monkeypatch):
    fake_socket = Mock()
    socket_factory = Mock(return_value=fake_socket)
    monkeypatch.setattr(transport, "BASE", Path("/tmp"))
    monkeypatch.setattr(transport, "HAS_UNIX_SOCKET", True)
    monkeypatch.setattr(transport.socket, "socket", socket_factory)
    monkeypatch.setattr(transport.socket, "AF_UNIX", 1, raising=False)
    monkeypatch.setattr(transport.socket, "SOCK_STREAM", 2)

    result = transport.connect_socket("demo", timeout=3)

    assert result is fake_socket
    socket_factory.assert_called_once_with(1, 2)
    fake_socket.settimeout.assert_called_once_with(3)
    fake_socket.connect.assert_called_once_with(str(Path("/tmp/bu-demo.sock")))


def test_connect_socket_uses_tcp_when_unix_socket_unavailable(monkeypatch):
    fake_socket = Mock()
    socket_factory = Mock(return_value=fake_socket)
    monkeypatch.setattr(transport, "HAS_UNIX_SOCKET", False)
    monkeypatch.setattr(transport.socket, "socket", socket_factory)
    monkeypatch.setattr(transport.socket, "AF_INET", 1)
    monkeypatch.setattr(transport.socket, "SOCK_STREAM", 2)

    result = transport.connect_socket("demo", timeout=3)

    assert result is fake_socket
    socket_factory.assert_called_once_with(1, 2)
    fake_socket.settimeout.assert_called_once_with(3)
    fake_socket.connect.assert_called_once_with(("127.0.0.1", transport._tcp_port("demo")))
