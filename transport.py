"""Cross-platform IPC transport for the browser-harness daemon.

POSIX : Unix Domain Socket at <state_dir>/bu-<NAME>.sock
Windows: TCP on 127.0.0.1 with a kernel-assigned port (bind is loopback-only).

Callers never check ``sys.platform`` themselves — everything OS-specific is
behind this module. Both the daemon and the clients read the endpoint
descriptor (``<state_dir>/bu-<NAME>.endpoint``, JSON with a ``v`` version
field) to discover where to connect.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


# --- state directory + path helpers ----------------------------------------

def state_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir())
    return Path("/tmp")


def endpoint_path(name: str) -> Path:
    return state_dir() / f"bu-{name}.endpoint"


def pid_path(name: str) -> Path:
    return state_dir() / f"bu-{name}.pid"


def log_path(name: str) -> Path:
    return state_dir() / f"bu-{name}.log"


def version_cache_path() -> Path:
    return state_dir() / "bu-version-cache.json"


def _sock_path(name: str) -> Path:
    # Internal: the UDS socket file lives next to the endpoint file.
    return state_dir() / f"bu-{name}.sock"


# --- kind ------------------------------------------------------------------

def is_tcp() -> bool:
    return sys.platform == "win32"


# --- endpoint descriptor I/O -----------------------------------------------

def write_endpoint(name: str, descriptor: dict) -> None:
    """Atomic: write to a sibling .tmp file, then os.replace()."""
    target = endpoint_path(name)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(descriptor))
    os.replace(tmp, target)


def read_endpoint(name: str) -> dict | None:
    try:
        raw = endpoint_path(name).read_text()
    except FileNotFoundError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def cleanup_endpoint(name: str) -> None:
    try:
        endpoint_path(name).unlink()
    except FileNotFoundError:
        pass


def cleanup_server_files(name: str) -> None:
    """Also remove the UDS socket file (no-op on TCP)."""
    if is_tcp():
        return
    try:
        _sock_path(name).unlink()
    except FileNotFoundError:
        pass


# --- Popen detach ----------------------------------------------------------

def popen_detach_kwargs() -> dict:
    """Kwargs so subprocess.Popen spawns a detached daemon on this OS."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


# --- async server ----------------------------------------------------------

async def start_ipc_server(name: str, handler) -> asyncio.Server:
    """Start the IPC listener and publish its endpoint descriptor.

    On POSIX this creates an AF_UNIX server chmod'd to 0o600; on Windows a
    loopback-only TCP server. The endpoint file is written *after* the
    listener is up and the real port (TCP) or socket path (UDS) is known.
    Callers should ``async with server: ...`` and call
    ``cleanup_endpoint(name)`` + ``cleanup_server_files(name)`` on shutdown.
    """
    if is_tcp():
        server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
        host, port = server.sockets[0].getsockname()[:2]
        descriptor = {"v": 1, "kind": "tcp", "host": host, "port": int(port)}
    else:
        sock = _sock_path(name)
        if sock.exists():
            sock.unlink()
        server = await asyncio.start_unix_server(handler, path=str(sock))
        os.chmod(sock, 0o600)
        descriptor = {"v": 1, "kind": "uds", "path": str(sock)}

    write_endpoint(name, descriptor)
    return server


# --- sync client (mirrors helpers.py / admin.py usage) ---------------------

def open_client_sync(name: str, timeout: float | None = None) -> socket.socket:
    """Open + connect a blocking socket to the daemon. Raises if no endpoint
    file exists or the daemon isn't accepting connections."""
    desc = read_endpoint(name)
    if desc is None:
        raise FileNotFoundError(f"no endpoint for {name!r} at {endpoint_path(name)}")
    kind = desc.get("kind")
    if kind == "tcp":
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout is not None:
            s.settimeout(timeout)
        s.connect((desc["host"], int(desc["port"])))
        return s
    if kind == "uds":
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if timeout is not None:
            s.settimeout(timeout)
        s.connect(desc["path"])
        return s
    raise ValueError(f"unknown endpoint kind {kind!r} for {name!r}")


def is_alive(name: str, timeout: float = 1.0) -> bool:
    """True if a client can connect to the endpoint right now.

    False for: no endpoint file, malformed descriptor, refused/timeout/missing
    target. Stale endpoint files (descriptor present, nothing listening) are
    also False — callers handle the unlink.
    """
    try:
        s = open_client_sync(name, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout, OSError, ValueError):
        return False
    s.close()
    return True
