import json
import socket
import stat

import pytest

from browser_harness import manager_runtime


def test_default_manager_root_is_user_private_tmp(monkeypatch):
    monkeypatch.delenv("BH_MANAGER_ROOT", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(manager_runtime, "IS_WINDOWS", False)
    monkeypatch.setattr(manager_runtime.os, "getuid", lambda: 12345, raising=False)

    assert manager_runtime.default_root() == manager_runtime.Path("/tmp/bhm-12345")


def test_ensure_private_dir_tightens_permissions(tmp_path):
    if manager_runtime.IS_WINDOWS:
        pytest.skip("POSIX permissions only")
    path = tmp_path / "manager"
    path.mkdir(mode=0o755)

    manager_runtime.ensure_private_dir(path)

    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o700


def test_write_private_json_uses_private_file_mode(tmp_path):
    if manager_runtime.IS_WINDOWS:
        pytest.skip("POSIX permissions only")
    path = tmp_path / "manager" / "registry.json"

    manager_runtime.write_private_json(path, {"ok": True})

    assert json.loads(path.read_text()) == {"ok": True}
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_windows_default_endpoint_is_token_file(monkeypatch, tmp_path):
    monkeypatch.setattr(manager_runtime, "IS_WINDOWS", True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BH_MANAGER_ROOT", raising=False)
    monkeypatch.delenv("BH_MANAGER_SOCKET", raising=False)

    root = manager_runtime.default_root()

    assert root == tmp_path / "browser-harness" / "manager"
    assert manager_runtime.default_endpoint(root) == root / "manager.port.json"


def test_send_request_injects_windows_token():
    left, right = socket.socketpair()
    try:
        left.settimeout(1)
        right.settimeout(1)
        right.sendall(b'{"ok": true}\n')

        resp = manager_runtime.send_request(left, "secret-token", {"op": "list"})
        sent = right.recv(4096).decode()
    finally:
        left.close()
        right.close()

    assert json.loads(sent) == {"op": "list", "token": "secret-token"}
    assert resp == {"ok": True}
