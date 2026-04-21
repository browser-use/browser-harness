"""Cross-platform IPC between the harness CLI and its daemon.

POSIX: AF_UNIX domain socket at ``$TMPDIR/bu-<NAME>.sock`` (the historical path).
Windows: TCP on 127.0.0.1 with the listening port persisted to
``%TEMP%/bu-<NAME>.port`` so the sync client can find the daemon.

Windows CPython lacks AF_UNIX until 3.14+, and even those builds don't ship it
on python.org / python-build-standalone releases yet. Using loopback TCP sidesteps
that without changing the wire format.
"""
import asyncio
import os
import socket
import tempfile
from pathlib import Path

IS_WINDOWS = os.name == "nt"
_DIR = Path(tempfile.gettempdir())


def paths(name):
    """Filesystem paths the daemon/clients agree on for a given BU_NAME."""
    return {
        "sock": str(_DIR / f"bu-{name}.sock"),
        "pid": str(_DIR / f"bu-{name}.pid"),
        "log": str(_DIR / f"bu-{name}.log"),
        "port": str(_DIR / f"bu-{name}.port"),
    }


def client_socket(name, timeout=None):
    """Return a connected blocking socket to the daemon."""
    p = paths(name)
    if IS_WINDOWS:
        port = int(Path(p["port"]).read_text().strip())
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout is not None:
            s.settimeout(timeout)
        s.connect(("127.0.0.1", port))
        return s
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    if timeout is not None:
        s.settimeout(timeout)
    s.connect(p["sock"])
    return s


async def start_server(handler, name):
    """Start the async IPC server. Returns (server, cleanup_callable)."""
    p = paths(name)
    if IS_WINDOWS:
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        Path(p["port"]).write_text(str(port))
        endpoint = f"127.0.0.1:{port}"

        def cleanup():
            try:
                os.unlink(p["port"])
            except FileNotFoundError:
                pass

        return server, endpoint, cleanup

    try:
        os.unlink(p["sock"])
    except FileNotFoundError:
        pass
    server = await asyncio.start_unix_server(handler, path=p["sock"])
    os.chmod(p["sock"], 0o600)

    def cleanup():
        try:
            os.unlink(p["sock"])
        except FileNotFoundError:
            pass

    return server, p["sock"], cleanup
