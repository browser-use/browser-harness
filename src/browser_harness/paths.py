"""browser-harness filesystem layout."""
from __future__ import annotations

import os
import subprocess
import tempfile
import sys
import warnings
from pathlib import Path


def home_dir() -> Path:
    raw = os.environ.get("BH_HOME") or os.environ.get("BROWSER_HARNESS_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return (Path(base).expanduser() / "browser-harness").resolve()
    return (Path.home() / ".config" / "browser-harness").resolve()


def _windows_principal() -> str | None:
    username = os.environ.get("USERNAME")
    if not username:
        return None
    domain = os.environ.get("USERDOMAIN")
    return f"{domain}\\{username}" if domain else username


def _run_icacls(path: Path, *args: str) -> bool:
    try:
        result = subprocess.run(
            ["icacls", str(path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        warnings.warn(
            f"could not restrict permissions for {path}: {exc}",
            RuntimeWarning,
            stacklevel=3,
        )
        return False

    if result.returncode == 0:
        return True

    detail = (result.stderr or result.stdout or "").strip()
    suffix = f": {detail}" if detail else ""
    warnings.warn(
        f"could not restrict permissions for {path}: icacls exited with {result.returncode}{suffix}",
        RuntimeWarning,
        stacklevel=3,
    )
    return False


def _harden_windows_acl(path: Path, *, directory: bool) -> None:
    principal = _windows_principal()
    if not principal:
        warnings.warn(
            f"could not restrict permissions for {path}: USERNAME is not set",
            RuntimeWarning,
            stacklevel=2,
        )
        return

    recursive = ("/T",) if directory else ()
    inheritance = "(OI)(CI)" if directory else ""
    grant = f"{principal}:{inheritance}F"

    fd, backup_name = tempfile.mkstemp(prefix="browser-harness-acl-", suffix=".txt")
    os.close(fd)
    backup_path = Path(backup_name)
    backup_path.unlink(missing_ok=True)

    try:
        # Keep the ACL transition failure-safe. If any restrictive update fails
        # after /reset, restore the exact pre-change DACL before returning.
        if not _run_icacls(path, "/save", str(backup_path), *recursive):
            return

        for args in (
            ("/reset", *recursive),
            ("/grant:r", grant, *recursive),
            ("/inheritance:r", *recursive),
        ):
            if _run_icacls(path, *args):
                continue

            restore_root = path.parent if path.parent != Path("") else Path(".")
            _run_icacls(restore_root, "/restore", str(backup_path))
            return
    finally:
        backup_path.unlink(missing_ok=True)


def harden_private_path(path: Path, *, directory: bool = False) -> None:
    if sys.platform == "win32":
        _harden_windows_acl(path, directory=directory)
        return
    os.chmod(path, 0o700 if directory else 0o600)


def ensure_private_dir(path: Path) -> Path:
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32" or not existed:
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
