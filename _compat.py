"""Cross-platform IPC compat shim.

POSIX (macOS/Linux) keeps AF_UNIX domain sockets — original behavior, unchanged.
Windows uses AF_INET on 127.0.0.1 with a port published in a sidecar file
because Python's socket module on Windows doesn't expose AF_UNIX (even though
WSL-style Win10 1803+ supports it natively, the Python stdlib doesn't surface it).

Daemon writes its bound port to <bu_dir>/bu-<name>.port at startup; clients
read the file to find the port. PID/log files use the same per-name base.
"""
import os
import socket
import sys
import tempfile
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


def _bu_dir():
    """Per-OS temp dir for daemon sockets/ports/pid/log files."""
    if IS_WINDOWS:
        return Path(tempfile.gettempdir())
    return Path("/tmp")


def paths(name):
    """Return a dict of file paths for daemon `name`. Always has 'log' and 'pid'.
    On POSIX also has 'sock'. On Windows also has 'port_file'."""
    n = name or os.environ.get("BU_NAME", "default")
    base = _bu_dir() / f"bu-{n}"
    out = {"log": f"{base}.log", "pid": f"{base}.pid"}
    if IS_WINDOWS:
        out["port_file"] = f"{base}.port"
    else:
        out["sock"] = f"{base}.sock"
    return out


def client_connect(name=None, timeout=1.0):
    """Connect a client socket to the daemon. Returns the connected socket.
    Raises FileNotFoundError if the daemon isn't running, ConnectionRefusedError
    or socket.timeout on transient failures (caller decides whether to retry)."""
    p = paths(name)
    if IS_WINDOWS:
        try:
            port = int(open(p["port_file"]).read().strip())
        except (FileNotFoundError, ValueError):
            raise FileNotFoundError(p["port_file"])
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("127.0.0.1", port))
        return s
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(p["sock"])
    return s


def remove_transport_artifacts(name=None):
    """Remove the daemon's socket/port file. Idempotent."""
    p = paths(name)
    for key in ("sock", "port_file"):
        if key in p:
            try:
                os.unlink(p[key])
            except FileNotFoundError:
                pass


async def start_server(handler, name=None):
    """Start the daemon's listening server. Returns (asyncio_server, address_info).

    POSIX: AF_UNIX server bound to <bu_dir>/bu-<name>.sock with 0600 perms.
    Windows: AF_INET TCP server on 127.0.0.1 ephemeral port; port written to
             <bu_dir>/bu-<name>.port for clients to discover."""
    import asyncio
    p = paths(name)
    if IS_WINDOWS:
        server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]
        with open(p["port_file"], "w") as f:
            f.write(str(port))
        return server, f"127.0.0.1:{port}"
    if os.path.exists(p["sock"]):
        os.unlink(p["sock"])
    server = await asyncio.start_unix_server(handler, path=p["sock"])
    os.chmod(p["sock"], 0o600)
    return server, p["sock"]
