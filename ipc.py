"""Cross-platform daemon IPC.

Unix: AF_UNIX socket at /tmp/bu-<NAME>.sock (unchanged from upstream).
Pinned at /tmp even though tempfile.gettempdir() would work on Linux —
macOS's gettempdir() is under /var/folders/.../T/ which can push the
full socket path past AF_UNIX's 108-char limit.

Windows: TCP loopback on an ephemeral port. The daemon writes its
address as JSON {"port": ..., "token": "..."} to %TEMP%\\bu-<NAME>.port
so the client can find it. A random 32-byte hex token gates every
request, because TCP loopback has no chmod-equivalent — any process on
the same machine could otherwise connect and issue CDP commands.
"""
import asyncio
import json
import os
import secrets
import socket
import tempfile

IS_WIN = os.name == "nt"

# Token for the currently-running daemon (populated in start_server on
# Windows, stays None on Unix where AF_UNIX + chmod 600 is the auth).
_server_token = None


def _win_base(name):
    return os.path.join(tempfile.gettempdir(), f"bu-{name}")


def _unix_sock(name):
    # Pinned at /tmp — see module docstring.
    return f"/tmp/bu-{name}.sock"


def sock_path(name):
    """Address artifact path. On Unix this is the AF_UNIX socket itself;
    on Windows it's a JSON file holding the TCP port + auth token."""
    return _win_base(name) + ".port" if IS_WIN else _unix_sock(name)


def log_path(name):
    if IS_WIN:
        return _win_base(name) + ".log"
    return f"/tmp/bu-{name}.log"


def pid_path(name):
    if IS_WIN:
        return _win_base(name) + ".pid"
    return f"/tmp/bu-{name}.pid"


def _read_addr(name):
    """Read the Windows .port file → (port, token). Returns (None, None)
    on any parse failure so callers fall through to 'no daemon running'."""
    try:
        with open(sock_path(name)) as f:
            raw = f.read().strip()
        # Accept both JSON (current format) and a bare port number
        # (previous format, kept for one release of forward-compat).
        if raw.startswith("{"):
            d = json.loads(raw)
            return int(d["port"]), d.get("token")
        return int(raw), None
    except (FileNotFoundError, ValueError, KeyError, TypeError, OSError):
        return None, None


def connect_client(name, timeout=1.0):
    """Return (connected_socket, token). `token` is None on Unix (no
    wire-level auth needed), a hex string on Windows. Callers that send
    JSON requests MUST include the token as `req["token"]` on Windows
    or the daemon will reject the request."""
    if IS_WIN:
        port, token = _read_addr(name)
        if port is None:
            raise FileNotFoundError(sock_path(name))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("127.0.0.1", port))
        return s, token
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(_unix_sock(name))
    return s, None


async def start_server(name, handler):
    """Bind the daemon server. Returns the asyncio.Server.

    Unix: start_unix_server at /tmp/bu-<NAME>.sock, chmod 600 (unchanged).
    Windows: start_server on 127.0.0.1:ephemeral, generate a 32-byte
    hex token, write {port, token} atomically to bu-<NAME>.port.
    """
    global _server_token
    if IS_WIN:
        server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]
        _server_token = secrets.token_hex(32)
        # Atomic write: write to .tmp then rename, so a concurrent reader
        # never sees a half-written file.
        addr_path = sock_path(name)
        tmp = addr_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"port": port, "token": _server_token}, f)
        os.replace(tmp, addr_path)
        return server
    path = _unix_sock(name)
    if os.path.exists(path):
        os.unlink(path)
    server = await asyncio.start_unix_server(handler, path=path)
    os.chmod(path, 0o600)
    _server_token = None
    return server


def expected_token():
    """The token this daemon will accept, or None on Unix where AF_UNIX
    + chmod 600 is the boundary. Called by daemon.handle() to gate
    every incoming request on Windows."""
    return _server_token


def listening_addr(name):
    """Human-readable address for logs."""
    if IS_WIN:
        port, _ = _read_addr(name)
        return f"127.0.0.1:{port or '?'} (via {sock_path(name)})"
    return sock_path(name)


def cleanup_addr(name):
    """Remove the sock/port artifact; used on shutdown."""
    try:
        os.unlink(sock_path(name))
    except FileNotFoundError:
        pass
