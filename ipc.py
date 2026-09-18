"""Cross-platform daemon IPC endpoint. Read, edit, extend -- this file is yours.

Every other file in this project (helpers.py, admin.py, daemon.py) independently
computed `/tmp/bu-{NAME}.sock` and called `socket.socket(socket.AF_UNIX, ...)`
directly. `AF_UNIX` does not exist on all Windows Python builds (confirmed:
absent here), so every one of those call sites raised AttributeError before a
connection was ever attempted -- `browser-harness --doctor` couldn't even
report status, let alone drive a browser.

This module is the one place that decides POSIX-Unix-socket vs Windows-TCP-
loopback, so the three call sites can share one connect()/listen_kwargs() pair
instead of three copies of the same platform branch.
"""

from __future__ import annotations

import socket
import sys
import zlib

IS_WINDOWS = sys.platform == "win32"
HAS_AF_UNIX = hasattr(socket, "AF_UNIX")
USE_UNIX_SOCKET = HAS_AF_UNIX and not IS_WINDOWS

# Windows fallback: a fixed high port per daemon `name`, derived deterministically
# (NOT via Python's hash() -- that's salted per-process via PYTHONHASHSEED, so a
# daemon process and a client process would compute different ports for the same
# name). crc32 is stable across processes and interpreters.
_PORT_BASE = 51000
_PORT_SPAN = 4000


def tcp_port(name: str) -> int:
    return _PORT_BASE + (zlib.crc32(name.encode("utf-8")) % _PORT_SPAN)


def unix_path(name: str) -> str:
    return f"/tmp/bu-{name}.sock"


def connect(name: str, timeout: float = 1.0) -> socket.socket:
    """Open a client connection to the daemon's control socket."""
    if USE_UNIX_SOCKET:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(unix_path(name))
        return s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(("127.0.0.1", tcp_port(name)))
    return s


def listen_kwargs(name: str) -> dict:
    """Kwargs for asyncio.start_unix_server(...) on POSIX or asyncio.start_server(...) on Windows.

    Caller picks the function based on `USE_UNIX_SOCKET`:

        if ipc.USE_UNIX_SOCKET:
            server = await asyncio.start_unix_server(handler, **ipc.listen_kwargs(name))
        else:
            server = await asyncio.start_server(handler, **ipc.listen_kwargs(name))
    """
    if USE_UNIX_SOCKET:
        return {"path": unix_path(name)}
    return {"host": "127.0.0.1", "port": tcp_port(name)}
