from pathlib import Path
from types import SimpleNamespace

import pytest

from browser_harness import paths

APPROVED_SID = "S-1-5-21-111"
FOREIGN_SID = "S-1-5-21-999"


def _set_windows_identity(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setattr(paths, "_windows_user_sid", lambda: APPROVED_SID)
    monkeypatch.setattr(
        paths, "_read_sddl",
        lambda path: f"O:{APPROVED_SID}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})",
    )


def _successful_icacls(calls):
    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})".encode()
            )
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
    assert argv[1:-1] == [
        ["icacls", str(target), "/inheritance:r", "/T"],
        ["icacls", str(target), "/grant:r", f"*{APPROVED_SID}:(OI)(CI)F", "/T"],
    ]
    assert argv[-1][:3] == ["icacls", str(target), "/save"]
    assert argv[-1][-1] == "/T"
    assert all(call[1] == {"capture_output": True, "text": True, "check": False} for call in calls)


def test_ensure_private_dir_does_not_reharden_valid_windows_tree(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    (target / "existing.txt").write_text("secret", encoding="utf-8")
    calls = []
    monkeypatch.setattr(paths.subprocess, "run", _successful_icacls(calls))

    paths.ensure_private_dir(target)

    assert calls == []


def test_ensure_private_dir_rehardens_existing_unprotected_windows_tree(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    calls = []
    state = {"hardened": False}

    def read_sddl(_path):
        dacl = f"D:P(A;;FA;;;{APPROVED_SID})" if state["hardened"] else "D:(A;;FA;;;S-1-1-0)"
        return f"O:{APPROVED_SID}G:{APPROVED_SID}{dacl}"

    def fake_run(args, **kwargs):
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                b"D:(A;;FA;;;S-1-1-0)"
            )
        if "/grant:r" in args:
            state["hardened"] = True
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths, "_read_sddl", read_sddl)
    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    paths.ensure_private_dir(target)

    assert any("/inheritance:r" in call for call in calls)
    assert any("/grant:r" in call for call in calls)


def test_harden_private_path_replaces_file_acl_on_windows(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    calls = []
    monkeypatch.setattr(paths.subprocess, "run", _successful_icacls(calls))
    target = tmp_path / "auth.json"
    target.touch()

    paths.harden_private_path(target)

    argv = [call[0] for call in calls]
    assert len(argv[0]) == 4
    backup = argv[0][3]
    assert argv[1:3] == [
        ["icacls", str(target), "/inheritance:r"],
        ["icacls", str(target), "/grant:r", f"*{APPROVED_SID}:F"],
    ]
    assert argv[3][:3] == ["icacls", str(target), "/save"]
    assert argv[0] == ["icacls", str(target), "/save", backup]


def test_harden_private_path_restores_acl_after_partial_failure(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})".encode()
            )
        if "/grant:r" in args:
            return SimpleNamespace(returncode=5, stdout="", stderr="Access is denied.")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.raises(PermissionError, match="icacls exited with 5"):
        paths.harden_private_path(target, directory=True)

    backup = calls[0][3]
    assert calls[:4] == [
        ["icacls", str(target), "/save", backup, "/T"],
        ["icacls", str(target), "/inheritance:r", "/T"],
        ["icacls", str(target), "/grant:r", f"*{APPROVED_SID}:(OI)(CI)F", "/T"],
        ["icacls", str(target.parent), "/restore", backup],
    ]
    assert calls[4][:3] == ["icacls", str(target), "/save"]
    assert calls[4][-1] == "/T"
    assert len(calls) == 5
    assert all("/reset" not in call for call in calls)


def test_harden_private_path_raises_when_icacls_fails(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()

    def fake_run(args, **kwargs):
        return SimpleNamespace(returncode=5, stdout="", stderr="Access is denied.")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.raises(PermissionError, match="icacls exited with 5"):
        paths.harden_private_path(target, directory=True)


def test_harden_private_path_uses_token_sid_instead_of_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("USERNAME", "untrusted-name")
    monkeypatch.setenv("USERDOMAIN", "untrusted-domain")
    monkeypatch.setattr(paths, "_windows_user_sid", lambda: APPROVED_SID)

    assert paths._windows_principal() == f"*{APPROVED_SID}"


def test_harden_private_path_raises_when_icacls_is_unavailable(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "auth.json"
    target.touch()

    def fake_run(args, **kwargs):
        raise FileNotFoundError("icacls")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.raises(PermissionError, match="icacls"):
        paths.harden_private_path(target)


def test_harden_private_path_propagates_acl_restore_failure(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "auth.json"
    target.touch()
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})".encode()
            )
        if "/grant:r" in args:
            return SimpleNamespace(returncode=5, stdout="", stderr="Access denied")
        if "/restore" in args:
            return SimpleNamespace(returncode=5, stdout="", stderr="Restore denied")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.raises(PermissionError, match="Restore denied"):
        paths.harden_private_path(target)

    assert calls[-1][0:3] == ["icacls", str(target.parent), "/restore"]


def test_harden_private_path_removes_foreign_explicit_grants(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "auth.json"
    target.touch()
    calls = []
    saves = iter(
        [
            f"D:(A;;FA;;;{APPROVED_SID})(A;;FA;;;{FOREIGN_SID})(A;;FA;;;S-1-1-0)".encode(),
            f"D:(A;;FA;;;{APPROVED_SID})".encode(),
        ]
    )

    def fake_run(args, **kwargs):
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(next(saves))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    paths.harden_private_path(target)

    assert [call[2] for call in calls] == [
        "/save",
        "/inheritance:r",
        "/remove:g",
        "/remove:d",
        "/remove:g",
        "/remove:d",
        "/grant:r",
        "/save",
    ]
    removed = {call[3] for call in calls if call[2] in {"/remove:g", "/remove:d"}}
    assert removed == {f"*{FOREIGN_SID}", "*S-1-1-0"}


def test_harden_private_path_rolls_back_when_acl_readback_has_foreign_principal(
    monkeypatch, tmp_path
):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "auth.json"
    target.touch()
    calls = []
    reads = 0

    def read_sddl(_path):
        nonlocal reads
        reads += 1
        suffix = (
            f"(A;;FA;;;{APPROVED_SID})(A;;FA;;;{FOREIGN_SID})"
            if reads == 2
            else f"(A;;FA;;;{APPROVED_SID})"
        )
        return f"O:{APPROVED_SID}G:{APPROVED_SID}D:P{suffix}"

    monkeypatch.setattr(paths, "_read_sddl", read_sddl)

    def fake_run(args, **kwargs):
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})".encode()
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.raises(PermissionError, match="unapproved principal"):
        paths.harden_private_path(target)

    assert any("/restore" in call for call in calls)


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


@pytest.mark.parametrize("ace", [
    f"(XA;;FA;;;{APPROVED_SID};(@User.x==1))",
        f"(A;;FA;;;{APPROVED_SID};(@User.x==1))",
        f"(A;;FR;;;{APPROVED_SID})",
        f"(A;;FA;;;{FOREIGN_SID})",
])
def test_acl_parser_rejects_conditional_and_insufficient_aces(ace):
    with pytest.raises(PermissionError):
        paths._parse_acl_snapshot(
            f"O:{APPROVED_SID}G:{APPROVED_SID}D:P{ace}".encode(),
            approved_sid=APPROVED_SID,
        )


@pytest.mark.parametrize("flags", ["IO", "OIIO", "ID", "ZZ", "NP", "OIOI"])
def test_acl_parser_rejects_non_applicable_or_invalid_approved_ace_flags(flags):
    with pytest.raises(PermissionError):
        paths._parse_acl_snapshot(
            f"O:{APPROVED_SID}G:{APPROVED_SID}D:P"
            f"(A;{flags};FA;;;{APPROVED_SID})".encode(),
            approved_sid=APPROVED_SID,
        )


def test_acl_parser_accepts_applicable_directory_inheritance_flags():
    assert paths._parse_acl_snapshot(
        f"O:{APPROVED_SID}G:{APPROVED_SID}D:P"
        f"(A;OICI;FA;;;{APPROVED_SID})".encode(),
        approved_sid=APPROVED_SID,
    ) == {APPROVED_SID}


@pytest.mark.parametrize("control_flags", ["P", "PAI", "PAR", "PAIAR"])
def test_acl_parser_keeps_dacl_control_flags_out_of_ace_parsing(control_flags):
    assert paths._parse_acl_snapshot(
        f"O:{APPROVED_SID}G:{APPROVED_SID}D:{control_flags}"
        f"(A;;FA;;;{APPROVED_SID})".encode(),
        approved_sid=APPROVED_SID,
    ) == {APPROVED_SID}


@pytest.mark.parametrize("control_flags", ["", "AI", "AR", "AIAR"])
def test_acl_parser_still_requires_protected_dacl_with_auto_inherit_flags(control_flags):
    with pytest.raises(PermissionError, match="protected DACL"):
        paths._parse_acl_snapshot(
            f"O:{APPROVED_SID}G:{APPROVED_SID}D:{control_flags}"
            f"(A;;FA;;;{APPROVED_SID})".encode(),
            approved_sid=APPROVED_SID,
        )


@pytest.mark.parametrize("filename", [
    "owner's credentials.json",
    'owner"s credentials.json',
    "owner’s credentials.json",
    "owner’s ` credentials; & | < > $(Write-Output INJECTED).json",
])
def test_read_sddl_passes_path_as_data_without_interpolating_powershell_source(
    monkeypatch, tmp_path, filename
):
    target = tmp_path / "folder with spaces" / filename
    calls = []
    descriptor = "O:S-1-5-21-123456789-123456789-123456789-1001G:BAD:P(A;;FA;;;SY)"

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=descriptor, stderr="")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    assert paths._read_sddl(target) == descriptor
    args, kwargs = calls[0]
    command = args[args.index("-Command") + 1]
    assert command == (
        "$a = Get-Acl -LiteralPath $env:BH_SDDL_PATH; "
        "$s = [System.Security.AccessControl.AccessControlSections]::All; "
        "[Console]::Write($a.GetSecurityDescriptorSddlForm($s))"
    )
    assert str(target) not in command
    assert "INJECTED" not in command
    assert kwargs["env"]["BH_SDDL_PATH"] == str(target)
    assert {key: kwargs[key] for key in ("capture_output", "text", "check")} == {
        "capture_output": True,
        "text": True,
        "check": False,
    }
    assert "shell" not in kwargs


def test_acl_parser_requires_protected_dacl_trusted_owner_and_no_deny():
    valid_prefix = f"O:{APPROVED_SID}G:{APPROVED_SID}D:"
    for sddl in (
        valid_prefix + f"(A;;FA;;;{APPROVED_SID})",
        f"O:{FOREIGN_SID}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})",
        f"O:{APPROVED_SID}G:{APPROVED_SID}D:P(D;;FA;;;{FOREIGN_SID})(A;;FA;;;{APPROVED_SID})",
        f"O:{APPROVED_SID}G:{APPROVED_SID}D:P",
    ):
        with pytest.raises(PermissionError):
            paths._parse_acl_snapshot(sddl.encode(), approved_sid=APPROVED_SID)


def test_hardening_rejects_reparse_points_before_acl_commands(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "link"
    original_lstat = Path.lstat
    monkeypatch.setattr(
        Path,
        "lstat",
        lambda self: SimpleNamespace(st_mode=0o100600, st_file_attributes=0x400)
        if self == target
        else original_lstat(self),
    )
    calls = []
    monkeypatch.setattr(paths.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(PermissionError, match="reparse point"):
        paths.harden_private_path(target)
    assert calls == []


def test_ensure_private_dir_rejects_reparse_ancestor_before_mkdir(monkeypatch, tmp_path):
    ancestor = tmp_path / "junction"
    target = ancestor / "private"
    original_lstat = Path.lstat

    def mock_lstat(item):
        if item == ancestor:
            actual = original_lstat(tmp_path)
            return SimpleNamespace(st_mode=actual.st_mode, st_file_attributes=0x400)
        return original_lstat(item)

    monkeypatch.setattr(Path, "lstat", mock_lstat)
    with pytest.raises(PermissionError, match="reparse point"):
        paths.ensure_private_dir(target)
    assert not target.exists()


def test_restore_acl_rejects_foreign_owner_after_dacl_restore(monkeypatch, tmp_path):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "auth.json"
    target.touch()
    calls = []
    restored = False

    def read_sddl(_path):
        owner = FOREIGN_SID if restored else APPROVED_SID
        return f"O:{owner}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})"

    def fake_run(args, **kwargs):
        nonlocal restored
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})".encode()
            )
        if "/grant:r" in args:
            return SimpleNamespace(returncode=5, stdout="", stderr="mutation failed")
        if "/restore" in args:
            restored = True
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths, "_read_sddl", read_sddl)
    monkeypatch.setattr(paths.subprocess, "run", fake_run)
    with pytest.raises(PermissionError, match="owner is not the effective user SID"):
        paths.harden_private_path(target)


@pytest.mark.parametrize("child_sddl, message", [
    (f"O:{FOREIGN_SID}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})", "owner"),
])
def test_recursive_hardening_rejects_invalid_child_acl_before_mutation(
    monkeypatch, tmp_path, child_sddl, message
):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    child = target / "credential.json"
    child.write_text("secret", encoding="utf-8")
    valid = f"O:{APPROVED_SID}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})"
    acl_reads = []
    calls = []
    monkeypatch.setattr(
        paths, "_read_sddl", lambda item: acl_reads.append(item) or (child_sddl if item == child else valid)
    )
    monkeypatch.setattr(paths.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(PermissionError, match=message):
        paths.harden_private_path(target, directory=True)

    assert child in acl_reads
    assert calls == []
    assert child.read_text(encoding="utf-8") == "secret"


def test_recursive_hardening_rejects_child_junction_before_acl_reads_or_mutation(
    monkeypatch, tmp_path
):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    junction = target / "linked"
    junction.mkdir()
    original_lstat = Path.lstat

    def mock_lstat(item):
        if item == junction:
            actual = original_lstat(item)
            return SimpleNamespace(st_mode=actual.st_mode, st_file_attributes=0x400)
        return original_lstat(item)

    acl_reads = []
    calls = []
    monkeypatch.setattr(Path, "lstat", mock_lstat)
    monkeypatch.setattr(paths, "_read_sddl", lambda item: acl_reads.append(item))
    monkeypatch.setattr(paths.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(PermissionError, match="reparse point"):
        paths.harden_private_path(target, directory=True)

    assert acl_reads == []
    assert calls == []


@pytest.mark.parametrize(
    "post_sddl, message",
    [
        (f"O:{FOREIGN_SID}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})", "owner"),
        (
            f"O:{APPROVED_SID}G:{APPROVED_SID}D:P(A;;FA;;;{FOREIGN_SID})",
            "unapproved principal",
        ),
        (
            f"O:{APPROVED_SID}G:{APPROVED_SID}D:P(A;;120089;;;{APPROVED_SID})",
            "Full Control",
        ),
        (
            (f"O:{APPROVED_SID}G:{APPROVED_SID}D:P"
             f"(A;IO;FA;;;{APPROVED_SID})"),
            "non-applicable",
        ),
        (
            (f"O:{APPROVED_SID}G:{APPROVED_SID}D:P"
             f"(D;;FA;;;{APPROVED_SID})(A;;FA;;;{APPROVED_SID})"),
            "deny ACE",
        ),
        (
            (f"O:{APPROVED_SID}G:{APPROVED_SID}D:P"
             f"(XA;;FA;;;{APPROVED_SID};(@User.x==1))"),
            "conditional or unsupported",
        ),
        (
            f"O:{APPROVED_SID}G:{APPROVED_SID}D:(A;;FA;;;{APPROVED_SID})",
            "protected DACL",
        ),
    ],
)
def test_recursive_hardening_revalidates_every_child_after_mutation(
    monkeypatch, tmp_path, post_sddl, message
):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    child = target / "credential.json"
    child.write_text("secret", encoding="utf-8")
    valid = f"O:{APPROVED_SID}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})"
    reads = []
    calls = []
    mutated = False

    def read_sddl(item):
        reads.append(item)
        if item == child and mutated:
            return post_sddl
        return valid

    def fake_run(args, **kwargs):
        nonlocal mutated
        calls.append(args)
        if "/grant:r" in args:
            mutated = True
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})".encode()
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths, "_read_sddl", read_sddl)
    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.raises(PermissionError, match=message):
        paths.harden_private_path(target, directory=True)

    assert reads.count(child) == 3
    assert any("/restore" in call for call in calls)


def test_recursive_hardening_rejects_replacement_during_descriptor_read(
    monkeypatch, tmp_path
):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    child = target / "credential.json"
    child.write_text("original", encoding="utf-8")
    replacement = target / "replacement"
    replacement.write_text("replacement", encoding="utf-8")
    valid = f"O:{APPROVED_SID}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})"
    calls = []

    def read_sddl(item):
        if item == child:
            replacement.replace(child)
        return valid

    monkeypatch.setattr(paths, "_read_sddl", read_sddl)
    monkeypatch.setattr(paths.subprocess, "run", lambda args, **kwargs: calls.append(args))

    with pytest.raises(PermissionError, match="filesystem objects changed"):
        paths.harden_private_path(target, directory=True)

    assert calls == []
    assert child.read_text(encoding="utf-8") == "replacement"


def test_recursive_hardening_rechecks_siblings_and_refuses_unsafe_rollback(
    monkeypatch, tmp_path
):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    child = target / "credential.json"
    child.write_text("credential", encoding="utf-8")
    sibling = target / "sibling.json"
    sibling.write_text("original sibling", encoding="utf-8")
    replacement = tmp_path / "replacement.json"
    replacement.write_text("replacement sibling", encoding="utf-8")
    valid = f"O:{APPROVED_SID}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})"
    calls = []
    mutated = False

    def read_sddl(item):
        if mutated and item == child and sibling.exists():
            replacement.replace(sibling)
        return valid

    def fake_run(args, **kwargs):
        nonlocal mutated
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})".encode()
            )
        if "/grant:r" in args:
            mutated = True
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths, "_read_sddl", read_sddl)
    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.raises(PermissionError, match="filesystem objects changed"):
        paths.harden_private_path(target, directory=True)

    assert sibling.read_text(encoding="utf-8") == "replacement sibling"
    assert not any("/restore" in call for call in calls)


def test_recursive_hardening_accepts_inherited_acl_before_hardening(
    monkeypatch, tmp_path
):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    child = target / "credential.json"
    child.write_text("secret", encoding="utf-8")
    inherited = (
        f"O:{APPROVED_SID}G:{APPROVED_SID}D:"
        f"(A;ID;FA;;;{APPROVED_SID})(A;;FA;;;S-1-1-0)"
    )
    protected = f"O:{APPROVED_SID}G:{APPROVED_SID}D:P(A;;FA;;;{APPROVED_SID})"
    mutated = False
    calls = []

    def read_sddl(item):
        return protected if mutated else inherited

    def fake_run(args, **kwargs):
        nonlocal mutated
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})(A;;FA;;;S-1-1-0)".encode()
            )
        if "/grant:r" in args:
            mutated = True
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths, "_read_sddl", read_sddl)
    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    paths.harden_private_path(target, directory=True)

    assert any("/inheritance:r" in call for call in calls)
    assert any("/grant:r" in call for call in calls)


def test_recursive_hardening_rolls_back_when_child_is_replaced_during_mutation(
    monkeypatch, tmp_path
):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    child = target / "credential.json"
    child.write_text("original", encoding="utf-8")
    replacement = target / "replacement"
    replacement.write_text("replacement", encoding="utf-8")
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})".encode()
            )
        if "/grant:r" in args:
            replacement.replace(child)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.raises(PermissionError, match="filesystem objects changed"):
        paths.harden_private_path(target, directory=True)

    assert child.read_text(encoding="utf-8") == "replacement"
    assert not any("/restore" in call for call in calls)


def test_recursive_hardening_rejects_child_reparse_point_created_during_mutation(
    monkeypatch, tmp_path
):
    _set_windows_identity(monkeypatch)
    target = tmp_path / "private"
    target.mkdir()
    child = target / "credential.json"
    child.write_text("original", encoding="utf-8")
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if "/save" in args:
            Path(args[args.index("/save") + 1]).write_bytes(
                f"D:(A;;FA;;;{APPROVED_SID})".encode()
            )
        if "/grant:r" in args:
            child.unlink()
            child.symlink_to(tmp_path / "outside")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paths.subprocess, "run", fake_run)

    with pytest.raises(PermissionError, match="reparse point"):
        paths.harden_private_path(target, directory=True)

    assert not any("/restore" in call for call in calls)
