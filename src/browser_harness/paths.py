"""browser-harness filesystem layout."""
from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def home_dir() -> Path:
    raw = os.environ.get("BH_HOME") or os.environ.get("BROWSER_HARNESS_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return (Path(base).expanduser() / "browser-harness").resolve()
    return (Path.home() / ".config" / "browser-harness").resolve()


def _windows_user_sid() -> str:
    if sys.platform != "win32":
        raise PermissionError("Windows user SID is only available on Windows")

    import ctypes
    from ctypes import wintypes

    class _SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]

    class _TokenUser(ctypes.Structure):
        _fields_ = [("User", _SidAndAttributes)]

    token = wintypes.HANDLE()
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.IsValidSid.argtypes = [wintypes.LPVOID]
    advapi32.IsValidSid.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.LPVOID]
    kernel32.LocalFree.restype = wintypes.LPVOID
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)
    ):
        raise PermissionError(f"could not open process token: {ctypes.get_last_error()}")

    try:
        token_user = 1
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, token_user, None, 0, ctypes.byref(size))
        if not size.value:
            raise PermissionError(f"could not query process token: {ctypes.get_last_error()}")
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(
            token, token_user, buffer, size, ctypes.byref(size)
        ):
            raise PermissionError(f"could not read process token: {ctypes.get_last_error()}")

        sid = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents.User.Sid
        if not advapi32.IsValidSid(sid):
            raise PermissionError("process token contains an invalid user SID")
        string_sid = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(string_sid)):
            raise PermissionError(f"could not convert user SID: {ctypes.get_last_error()}")
        try:
            return string_sid.value
        finally:
            kernel32.LocalFree(string_sid)
    finally:
        kernel32.CloseHandle(token)


def _windows_principal(resolve_sid=None) -> str:
    sid = (resolve_sid or _windows_user_sid)()
    if not sid:
        raise PermissionError("could not resolve the effective Windows user SID")
    return f"*{sid.lstrip('*')}"


def _run_icacls(path: Path, *args: str) -> bool:
    try:
        result = subprocess.run(
            ["icacls", str(path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise PermissionError(f"could not restrict permissions for {path}: {exc}") from exc

    if result.returncode == 0:
        return True

    detail = (result.stderr or result.stdout or "").strip()
    suffix = f": {detail}" if detail else ""
    raise PermissionError(
        f"could not restrict permissions for {path}: icacls exited with {result.returncode}{suffix}"
    )


def _read_acl_snapshot(path: Path, *, directory: bool) -> bytes:
    recursive = ("/T",) if directory else ()
    fd, snapshot_name = tempfile.mkstemp(prefix="browser-harness-acl-read-", suffix=".txt")
    os.close(fd)
    snapshot_path = Path(snapshot_name)
    snapshot_path.unlink(missing_ok=True)
    try:
        _run_icacls(path, "/save", str(snapshot_path), *recursive)
        return snapshot_path.read_bytes()
    finally:
        snapshot_path.unlink(missing_ok=True)


def _acl_principals(snapshot: bytes) -> set[str]:
    if snapshot.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = snapshot.decode("utf-16")
    else:
        text = snapshot.decode("utf-8")
    aliases = {
        "AU": "S-1-5-11",
        "BA": "S-1-5-32-544",
        "BU": "S-1-5-32-545",
        "SY": "S-1-5-18",
        "WD": "S-1-1-0",
    }
    return {
        aliases.get(match.upper().lstrip("*"), match.upper().lstrip("*"))
        for match in re.findall(r"\([^)]*;;;([^;)]+)\)", text)
    }


def _parse_acl_snapshot(snapshot: bytes, *, approved_sid: str) -> set[str]:
    """Parse only simple, explicit allow/deny ACEs; reject ambiguous SDDL."""
    text = snapshot.decode("utf-8")
    if not text.startswith("O:") or "G:" not in text or "D:" not in text:
        raise PermissionError("ACL must have a trusted owner and protected DACL")
    owner = text[2:text.index("G:")]
    if owner.upper() != approved_sid.upper():
        raise PermissionError(f"ACL owner is not the effective user SID: {owner}")
    dacl_start = text.index("D:") + 2
    ace_start = text.find("(", dacl_start)
    if ace_start < 0:
        ace_start = len(text)
    control_flags = text[dacl_start:ace_start]
    flags = re.findall(r"AI|AR|P", control_flags)
    if "".join(flags) != control_flags or len(flags) != len(set(flags)) or "P" not in flags:
        raise PermissionError("ACL must have a protected DACL")
    dacl_end = text.find("S:", ace_start)
    dacl = text[ace_start:] if dacl_end < 0 else text[ace_start:dacl_end]
    if not dacl:
        raise PermissionError("ACL has a null or empty DACL")
    ace_pattern = re.compile(
        r"\((A|D);([^;]*);(FA|[0-9A-Fa-f]+);[^;]*;[^;]*;([^;)]+)\)"
    )
    principals: set[str] = set()
    offset = 0
    full_control = 0x1F01FF
    while offset < len(dacl):
        match = ace_pattern.match(dacl, offset)
        if not match:
            raise PermissionError("ACL contains a conditional or unsupported ACE")
        ace_type, flags_text, mask_text, sid = match.groups()
        flags = re.findall(r"OI|CI|NP|IO|ID|SA|FA", flags_text)
        if "".join(flags) != flags_text or len(flags) != len(set(flags)):
            raise PermissionError("ACL contains unsupported or malformed ACE flags")
        if {"IO", "ID", "SA", "FA"}.intersection(flags):
            raise PermissionError("ACL contains a non-applicable or non-explicit allow ACE")
        if "NP" in flags and not {"OI", "CI"}.intersection(flags):
            raise PermissionError("ACL contains non-applicable ACE inheritance flags")
        if ace_type == "D":
            raise PermissionError(f"ACL contains an applicable deny ACE for {sid}")
        if sid.upper() != approved_sid.upper():
            raise PermissionError(f"ACL contains an unapproved principal: {sid}")
        mask = full_control if mask_text == "FA" else int(mask_text, 16)
        if sid.upper() == approved_sid.upper() and mask != full_control:
            raise PermissionError("ACL does not grant explicit Full Control to the effective user")
        principals.add(sid.upper())
        offset = match.end()
    if approved_sid.upper() not in principals:
        raise PermissionError("ACL does not grant explicit Full Control to the effective user")
    return principals


def _validate_acl_owner(snapshot: bytes, *, approved_sid: str) -> None:
    """Validate the stable owner independently of DACL hardening state."""
    text = snapshot.decode("utf-8")
    if not text.startswith("O:") or "G:" not in text:
        raise PermissionError("ACL must have a trusted owner")
    owner = text[2:text.index("G:")]
    if owner.upper() != approved_sid.upper():
        raise PermissionError(f"ACL owner is not the effective user SID: {owner}")


def _reject_reparse_path(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise PermissionError(f"refusing to harden reparse point: {path}")


def reject_reparse_path(path: Path) -> None:
    """Public guard for callers that read or replace credential paths."""
    absolute = path.absolute()
    for item in reversed((absolute, *absolute.parents)):
        _reject_reparse_path(item)


def _read_sddl(path: Path) -> str:
    command = (
        "$a = Get-Acl -LiteralPath $env:BH_SDDL_PATH; "
        "$s = [System.Security.AccessControl.AccessControlSections]::All; "
        "[Console]::Write($a.GetSecurityDescriptorSddlForm($s))"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "BH_SDDL_PATH": str(path)},
        )
    except OSError as exc:
        raise PermissionError(f"could not read security descriptor for {path}: {exc}") from exc
    if result.returncode:
        raise PermissionError(f"could not read security descriptor for {path}: {result.stderr.strip()}")
    return result.stdout


def _read_acl_principals(path: Path, *, directory: bool, approved_sid: str) -> set[str]:
    # Keep the canonical icacls readback used for rollback verification, and
    # independently inspect the full descriptor because ACL-only output omits owner.
    _read_acl_snapshot(path, directory=directory)
    return _parse_acl_snapshot(_read_sddl(path).encode("utf-8"), approved_sid=approved_sid)


def _object_identity(path: Path) -> tuple[int, int, int, int]:
    """Return the filesystem identity fields available without following links."""
    info = path.lstat()
    return (
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        getattr(info, "st_file_attributes", 0),
    )


def _validate_acl_tree(
    path: Path,
    *,
    directory: bool,
    approved_sid: str,
    expected_identities: dict[Path, tuple[int, int, int, int] | None] | None = None,
    validate_dacl: bool = True,
    read_descriptors: bool = True,
    dacl_validity: dict[Path, bool] | None = None,
) -> dict[Path, tuple[int, int, int, int] | None]:
    """Validate all objects and, on readback, ensure the tree still names them."""
    objects = [path]
    if directory:
        pending = [path]
        try:
            path.lstat()
        except FileNotFoundError:
            pending.clear()
        while pending:
            parent = pending.pop()
            for child in parent.iterdir():
                _reject_reparse_path(child)
                objects.append(child)
                info = child.lstat()
                if stat.S_ISDIR(info.st_mode):
                    pending.append(child)

    # Finish the path/reparse-point pass before invoking ACL readers for any object.
    identities: dict[Path, tuple[int, int, int, int] | None] = {}
    for item in objects:
        _reject_reparse_path(item)
        try:
            identities[item] = _object_identity(item)
        except FileNotFoundError:
            identities[item] = None
    if expected_identities is not None and identities != expected_identities:
        raise PermissionError(
            f"filesystem objects changed while hardening {path}: "
            f"expected {expected_identities!r}, found {identities!r}"
        )
    for item in objects if read_descriptors else ():
        # Descriptor APIs take a path, so bind each read to the object found in
        # the enumeration. A replacement during the read must never validate.
        before = _object_identity(item)
        if before != identities[item]:
            raise PermissionError(f"filesystem object changed while hardening {item}")
        snapshot = _read_sddl(item).encode("utf-8")
        after = _object_identity(item)
        if before != after:
            raise PermissionError(f"filesystem objects changed while hardening {path}")
        _validate_acl_owner(snapshot, approved_sid=approved_sid)
        if validate_dacl:
            try:
                _parse_acl_snapshot(snapshot, approved_sid=approved_sid)
            except PermissionError:
                if dacl_validity is None:
                    raise
                dacl_validity[item] = False
            else:
                if dacl_validity is not None:
                    dacl_validity[item] = True
    if read_descriptors:
        # Re-enumerate after every descriptor read so a sibling replaced while
        # another object's descriptor was being queried cannot pass validation.
        _validate_acl_tree(
            path,
            directory=directory,
            approved_sid=approved_sid,
            expected_identities=identities,
            read_descriptors=False,
        )
    return identities


def _restore_acl(
    path: Path,
    backup_path: Path,
    *,
    directory: bool,
    expected_identities: dict[Path, tuple[int, int, int, int] | None],
    approved_sid: str,
) -> None:
    _assert_acl_tree_identity(path, directory=directory, expected_identities=expected_identities)
    restore_root = path.parent if path.parent != Path("") else Path(".")
    _run_icacls(restore_root, "/restore", str(backup_path))
    _assert_acl_tree_identity(path, directory=directory, expected_identities=expected_identities)
    if _read_acl_snapshot(path, directory=directory) != backup_path.read_bytes():
        raise PermissionError(f"could not verify restored permissions for {path}")
    _validate_acl_tree(
        path,
        directory=directory,
        approved_sid=approved_sid,
        expected_identities=expected_identities,
        validate_dacl=False,
    )
    _assert_acl_tree_identity(path, directory=directory, expected_identities=expected_identities)


def _assert_acl_tree_identity(
    path: Path,
    *,
    directory: bool,
    expected_identities: dict[Path, tuple[int, int, int, int] | None],
) -> None:
    current_identities = _validate_acl_tree(
        path,
        directory=directory,
        approved_sid="",
        expected_identities=expected_identities,
        read_descriptors=False,
    )
    if current_identities != expected_identities:
        raise PermissionError(f"filesystem objects changed; refusing ACL rollback for {path}")


def _mutate_acl_tree(
    path: Path,
    *args: str,
    directory: bool,
    expected_identities: dict[Path, tuple[int, int, int, int] | None],
) -> None:
    _assert_acl_tree_identity(path, directory=directory, expected_identities=expected_identities)
    _run_icacls(path, *args, *(("/T",) if directory else ()))
    _assert_acl_tree_identity(path, directory=directory, expected_identities=expected_identities)


def _windows_acl_tree_is_hardened(path: Path, *, directory: bool, resolve_sid=None) -> bool:
    approved_sid = _windows_principal(resolve_sid).lstrip("*").upper()
    identities = _validate_acl_tree(
        path, directory=directory, approved_sid=approved_sid, validate_dacl=False
    )
    dacl_validity: dict[Path, bool] = {}
    _validate_acl_tree(
        path,
        directory=directory,
        approved_sid=approved_sid,
        expected_identities=identities,
        dacl_validity=dacl_validity,
    )
    return bool(dacl_validity) and all(dacl_validity.values())


def _harden_windows_acl(path: Path, *, directory: bool, resolve_sid=None) -> None:
    _reject_reparse_path(path)
    principal = _windows_principal(resolve_sid)
    approved = {principal.lstrip("*").upper()}
    original_identities = _validate_acl_tree(
        path,
        directory=directory,
        approved_sid=next(iter(approved)),
        validate_dacl=False,
    )
    recursive = ("/T",) if directory else ()
    inheritance = "(OI)(CI)" if directory else ""
    grant = f"{principal}:{inheritance}F"

    fd, backup_name = tempfile.mkstemp(prefix="browser-harness-acl-", suffix=".txt")
    os.close(fd)
    backup_path = Path(backup_name)
    backup_path.unlink(missing_ok=True)

    try:
        _run_icacls(path, "/save", str(backup_path), *recursive)
        _assert_acl_tree_identity(path, directory=directory, expected_identities=original_identities)
        backup = backup_path.read_bytes()
        original_principals = _acl_principals(backup)

        try:
            _mutate_acl_tree(
                path,
                "/inheritance:r",
                directory=directory,
                expected_identities=original_identities,
            )
            for unapproved in sorted(original_principals - approved):
                _mutate_acl_tree(
                    path,
                    "/remove:g",
                    f"*{unapproved}",
                    directory=directory,
                    expected_identities=original_identities,
                )
                _mutate_acl_tree(
                    path,
                    "/remove:d",
                    f"*{unapproved}",
                    directory=directory,
                    expected_identities=original_identities,
                )
            _mutate_acl_tree(
                path,
                "/grant:r",
                grant,
                directory=directory,
                expected_identities=original_identities,
            )
            remaining = _read_acl_principals(
                path, directory=directory, approved_sid=next(iter(approved))
            )
            if remaining != approved:
                names = ", ".join(sorted(remaining - approved)) or "the approved SID is missing"
                raise PermissionError(f"ACL readback failed for {path}: {names}")
            _validate_acl_tree(
                path,
                directory=directory,
                approved_sid=next(iter(approved)),
                expected_identities=original_identities,
            )
        except Exception:
            _restore_acl(
                path,
                backup_path,
                directory=directory,
                expected_identities=original_identities,
                approved_sid=next(iter(approved)),
            )
            raise
    finally:
        backup_path.unlink(missing_ok=True)


def harden_private_path(path: Path, *, directory: bool = False, resolve_sid=None) -> None:
    reject_reparse_path(path)
    if sys.platform == "win32":
        _reject_reparse_path(path)
        _harden_windows_acl(path, directory=directory, resolve_sid=resolve_sid)
        return
    os.chmod(path, 0o700 if directory else 0o600)


def ensure_private_dir(path: Path) -> Path:
    reject_reparse_path(path)
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        if not existed or not _windows_acl_tree_is_hardened(path, directory=True):
            harden_private_path(path, directory=True)
    elif not existed:
        harden_private_path(path, directory=True)
    return path


def config_dir() -> Path:
    raw = os.environ.get("BH_CONFIG_DIR")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir())


def inspect_marker() -> Path:
    """Marker recording that the harness opened a chrome://inspect tab"""
    return config_dir() / "inspect-opened"


def runtime_dir() -> Path:
    raw = os.environ.get("BH_RUNTIME_DIR")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir() / "runtime")


def tmp_dir() -> Path:
    raw = os.environ.get("BH_TMP_DIR")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir() / "tmp")


def workspace_dir() -> Path:
    raw = os.environ.get("BH_AGENT_WORKSPACE")
    return ensure_private_dir(Path(raw).expanduser().resolve() if raw else home_dir() / "agent-workspace")
