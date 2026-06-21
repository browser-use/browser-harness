"""Runtime directory and IPC helpers for browser manager mode."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile


IS_WINDOWS = sys.platform == "win32"


def default_root() -> Path:
    if os.environ.get("BH_MANAGER_ROOT"):
        return Path(os.environ["BH_MANAGER_ROOT"])
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        return Path(base) / "browser-harness" / "manager"
    if os.environ.get("XDG_RUNTIME_DIR"):
        return Path(os.environ["XDG_RUNTIME_DIR"]) / "browser-harness-manager"
    uid = os.getuid() if hasattr(os, "getuid") else os.environ.get("USER") or "user"
    return Path("/tmp") / f"bhm-{uid}"


def default_endpoint(root: Path | None = None) -> Path:
    if os.environ.get("BH_MANAGER_SOCKET"):
        return Path(os.environ["BH_MANAGER_SOCKET"])
    root = root or default_root()
    return root / ("manager.port.json" if IS_WINDOWS else "manager.sock")


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if IS_WINDOWS:
        return
    st = path.stat()
    uid = os.getuid()
    if st.st_uid != uid:
        raise PermissionError(f"{path} is owned by uid {st.st_uid}, expected {uid}")
    if st.st_mode & 0o077:
        os.chmod(path, 0o700)
        st = path.stat()
        if st.st_mode & 0o077:
            raise PermissionError(f"{path} must not be accessible by group/other")


def write_private_json(path: Path, data: dict) -> None:
    ensure_private_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(tmp, flags, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    os.replace(tmp, path)
    if not IS_WINDOWS:
        os.chmod(path, 0o600)


def open_private_append(path: Path):
    ensure_private_dir(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    return os.fdopen(fd, "ab")


@contextmanager
def start_lock(root: Path):
    ensure_private_dir(root)
    lock_path = root / "manager.start.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a+b") as f:
        if IS_WINDOWS:
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def spawn_kwargs() -> dict:
    if IS_WINDOWS:
        return {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
        }
    return {"start_new_session": True}


def connect(endpoint: Path, timeout: float = 1.0) -> tuple[socket.socket, str | None]:
    if not IS_WINDOWS:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(endpoint))
        return s, None
    data = json.loads(endpoint.read_text())
    port = int(data["port"])
    token = str(data["token"])
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.settimeout(timeout)
    return s, token


def send_request(sock: socket.socket, token: str | None, req: dict) -> dict:
    if token:
        req = {**req, "token": token}
    sock.sendall((json.dumps(req) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = sock.recv(1 << 16)
        if not chunk:
            break
        data += chunk
    resp = json.loads(data or b"{}")
    return resp if isinstance(resp, dict) else {"ok": False, "state": "bad-response"}


def ping(endpoint: Path, timeout: float = 0.2) -> bool:
    try:
        sock, token = connect(endpoint, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError, ValueError, KeyError, TypeError):
        return False
    try:
        resp = send_request(sock, token, {"meta": "ping"})
        return resp.get("pong") is True
    except (OSError, ValueError, AttributeError):
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def new_token() -> str:
    return secrets.token_hex(32)
