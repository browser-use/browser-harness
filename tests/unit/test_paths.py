from types import SimpleNamespace

import pytest

from browser_harness import paths


def _set_windows_identity(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("USERNAME", "alice")
    monkeypatch.setenv("USERDOMAIN", "WORKSTATION")


def _successful_icacls(calls):
    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return fake_run


def test_ensure_private_dir_replaces_windows_acl_recursively(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    calls = []
    monkeypatch.setattr(paths.subprocess, "run", _successful_icacls(calls))
    target = tmp_path / "private"

    assert paths.ensure_private_dir(target) == target

    argv = [call[0] for call in calls]
    assert argv[0][:3] == ["icacls", str(target), "/save"]
    assert argv[0][-1] == "/T"
    assert argv[1:] == [
        ["icacls", str(target), "/reset", "/T"],
        ["icacls", str(target), "/grant:r", "WORKSTATION\\alice:(OI)(CI)F", "/T"],
        ["icacls", str(target), "/inheritance:r", "/T"],
    ]
    assert all(call[1] == {"capture_output": True, "text": True, "check": False} for call in calls)


def test_ensure_private_dir_rehardens_existing_windows_tree(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    (target / "existing.txt").write_text("secret", encoding="utf-8")
    calls = []
    monkeypatch.setattr(paths.subprocess, "run", _successful_icacls(calls))

    paths.ensure_private_dir(target)

    argv = [call[0] for call in calls]
    assert argv[0][:3] == ["icacls", str(target), "/save"]
    assert argv[1] == ["icacls", str(target), "/reset", "/T"]
    assert argv[-1] == ["icacls", str(target), "/inheritance:r", "/T"]


def test_harden_private_path_replaces_file_acl_on_windows(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    calls = []
    monkeypatch.setattr(paths.subprocess, "run", _successful_icacls(calls))
    target = tmp_path / "auth.json"

    paths.harden_private_path(target)

    argv = [call[0] for call in calls]
    assert argv[0][:3] == ["icacls", str(target), "/save"]
    assert len(argv[0]) == 4
    assert argv[1:] == [
        ["icacls", str(target), "/reset"],
        ["icacls", str(target), "/grant:r", "WORKSTATION\\alice:F"],
        ["icacls", str(target), "/inheritance:r"],
    ]


def test_harden_private_path_restores_acl_after_partial_failure(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if "/grant:r" in args:
            return SimpleNamespace(returncode=5, stdout="", stderr="Access is denied.")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.warns(RuntimeWarning, match="icacls exited with 5"):
        paths.harden_private_path(target, directory=True)

    backup = calls[0][3]
    assert calls[0][:3] == ["icacls", str(target), "/save"]
    assert calls[1] == ["icacls", str(target), "/reset", "/T"]
    assert calls[2] == ["icacls", str(target), "/grant:r", "WORKSTATION\\alice:(OI)(CI)F", "/T"]
    assert calls[3] == ["icacls", str(target.parent), "/restore", backup]
    assert not any("/inheritance:r" in call for call in calls)


def test_harden_private_path_warns_when_icacls_fails(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)

    def fake_run(args, **kwargs):
        return SimpleNamespace(returncode=5, stdout="", stderr="Access is denied.")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.warns(RuntimeWarning, match="icacls exited with 5"):
        paths.harden_private_path(tmp_path / "private", directory=True)


def test_harden_private_path_warns_without_windows_username(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.delenv("USERDOMAIN", raising=False)

    with pytest.warns(RuntimeWarning, match="USERNAME is not set"):
        paths.harden_private_path(tmp_path / "private", directory=True)


def test_harden_private_path_warns_when_icacls_is_unavailable(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)

    def fake_run(args, **kwargs):
        raise FileNotFoundError("icacls")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.warns(RuntimeWarning, match="icacls"):
        paths.harden_private_path(tmp_path / "private", directory=True)


def test_posix_private_modes(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    calls = []
    monkeypatch.setattr(paths.os, "chmod", lambda path, mode: calls.append((path, mode)))

    new_dir = tmp_path / "new"
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()
    private_file = tmp_path / "auth.json"
    private_file.touch()

    paths.ensure_private_dir(new_dir)
    paths.ensure_private_dir(existing_dir)
    paths.harden_private_path(private_file)

    assert calls == [
        (new_dir, 0o700),
        (private_file, 0o600),
    ]
