"""Cross-platform daemon IPC.

Unix: AF_UNIX socket at /tmp/bu-<NAME>.sock (unchanged).
Windows: TCP loopback on an ephemeral port; the port number lives in
/tmp/bu-<NAME>.port so the client can find it. %TEMP% stands in for /tmp
on Windows via tempfile.gettempdir().
"""
import asyncio
import os
import socket
import tempfile

IS_WIN = os.name == "nt"


def _base(name):
    return os.path.join(tempfile.gettempdir(), f"bu-{name}")


def sock_path(name):
    """Address artifact path: .sock on Unix (the socket itself), .port on Windows (a text file with the TCP port)."""
    return _base(name) + (".port" if IS_WIN else ".sock")


def log_path(name):
    return _base(name) + ".log"


def pid_path(name):
    return _base(name) + ".pid"


def _read_port(name):
    try:
        return int(open(sock_path(name)).read().strip())
    except (FileNotFoundError, ValueError):
        return None


def connect_client(name, timeout=1.0):
    """Return a connected blocking socket to the daemon. Raises on failure."""
    if IS_WIN:
        port = _read_port(name)
        if port is None:
            raise FileNotFoundError(sock_path(name))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("127.0.0.1", port))
        return s
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(sock_path(name))
    return s


async def start_server(name, handler):
    """Bind the daemon server. Returns the asyncio.Server.

    Unix: start_unix_server at /tmp/bu-<NAME>.sock, chmod 600.
    Windows: start_server on 127.0.0.1:ephemeral; writes port to bu-<NAME>.port.
    """
    path = sock_path(name)
    if IS_WIN:
        server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]
        open(path, "w").write(str(port))
        return server
    if os.path.exists(path):
        os.unlink(path)
    server = await asyncio.start_unix_server(handler, path=path)
    os.chmod(path, 0o600)
    return server


def listening_addr(name):
    """Human-readable address for logs."""
    if IS_WIN:
        return f"127.0.0.1:{_read_port(name) or '?'} (via {sock_path(name)})"
    return sock_path(name)


def cleanup_addr(name):
    """Remove the sock/port artifact; used on shutdown."""
    try:
        os.unlink(sock_path(name))
    except FileNotFoundError:
        pass
