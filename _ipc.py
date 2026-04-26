"""Cross-platform IPC abstraction.

On Unix: AF_UNIX socket at /tmp/bu-<NAME>.sock (original behaviour).
On Windows: TCP loopback (127.0.0.1:<port>); port persisted to %TEMP%/bu-<NAME>.sock
            so the file path stays a single source of truth across platforms.

Public API:
    runtime_dir()          -> str: per-OS tmp dir
    runtime_path(name, ext)-> str: /tmp/bu-<NAME>.<ext> on Unix, %TEMP%\bu-<NAME>.<ext> on Win
    SOCK_EXT               -> "sock"  (file used as either Unix socket or port marker)
    PID_EXT, LOG_EXT
    is_windows()           -> bool
    connect_daemon(name, timeout=1) -> socket: connected to daemon (raises on failure)
    start_daemon_server(handler, name) -> (server, endpoint_str) for asyncio
    cleanup_endpoint(name)  -> None: unlink sock/port file
"""

import asyncio
import os
import platform
import socket
from pathlib import Path


def is_windows() -> bool:
    return platform.system() == "Windows"


def runtime_dir() -> str:
    if is_windows():
        return (
            os.environ.get("TEMP")
            or os.environ.get("TMP")
            or str(Path.home() / "AppData" / "Local" / "Temp")
        )
    return "/tmp"


SOCK_EXT = "sock"
PID_EXT = "pid"
LOG_EXT = "log"


def runtime_path(name: str, ext: str = SOCK_EXT) -> str:
    return os.path.join(runtime_dir(), f"bu-{name}.{ext}")


def _read_port(name: str) -> int | None:
    try:
        return int(open(runtime_path(name, SOCK_EXT)).read().strip())
    except (FileNotFoundError, ValueError, NotADirectoryError):
        return None


def _alloc_port() -> int:
    """Pick a free TCP port on 127.0.0.1."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def connect_daemon(name: str, timeout: float = 1.0) -> socket.socket:
    """Connect to a running daemon. Raises FileNotFoundError, ConnectionRefusedError, or socket.timeout."""
    if is_windows():
        port = _read_port(name)
        if port is None:
            raise FileNotFoundError(runtime_path(name, SOCK_EXT))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("127.0.0.1", port))
        return s
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(runtime_path(name, SOCK_EXT))
    return s


async def start_daemon_server(handler, name: str):
    """Start the daemon listening server (asyncio).

    Returns (server, endpoint_str) tuple. endpoint_str describes where it listens
    for log purposes ("/tmp/bu-default.sock" or "127.0.0.1:54321").
    """
    sock_path = runtime_path(name, SOCK_EXT)
    if is_windows():
        port = _alloc_port()
        # Persist port to .sock file (acts as port marker on Win)
        with open(sock_path, "w") as f:
            f.write(str(port))
        server = await asyncio.start_server(handler, "127.0.0.1", port)
        return server, f"127.0.0.1:{port}"
    # Unix
    if os.path.exists(sock_path):
        os.unlink(sock_path)
    server = await asyncio.start_unix_server(handler, path=sock_path)
    try:
        os.chmod(sock_path, 0o600)
    except OSError:
        pass
    return server, sock_path


def cleanup_endpoint(name: str) -> None:
    """Remove sock/port + pid files."""
    for ext in (SOCK_EXT, PID_EXT):
        try:
            os.unlink(runtime_path(name, ext))
        except FileNotFoundError:
            pass
