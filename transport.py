import hashlib
import os
import socket
import sys
from pathlib import Path


NAME = os.environ.get("BU_NAME", "default")
BASE = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".") if sys.platform == "win32" else Path("/tmp")
HAS_UNIX_SOCKET = sys.platform != "win32" and hasattr(socket, "AF_UNIX")


def _tcp_port(name=None):
    n = name or os.environ.get("BU_NAME", NAME)
    digest = hashlib.sha256(n.encode()).digest()
    return 49152 + int.from_bytes(digest[:2], "big") % 10000


def paths(name=None):
    n = name or os.environ.get("BU_NAME", NAME)
    return BASE / f"bu-{n}.sock", BASE / f"bu-{n}.pid", BASE / f"bu-{n}.log"


def connect_socket(name=None, timeout=None):
    if HAS_UNIX_SOCKET:
        sock_path, _, _ = paths(name)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if timeout is not None:
            s.settimeout(timeout)
        s.connect(str(sock_path))
        return s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if timeout is not None:
        s.settimeout(timeout)
    s.connect(("127.0.0.1", _tcp_port(name)))
    return s


async def start_server(handler, name=None):
    if HAS_UNIX_SOCKET:
        import asyncio
        sock_path, _, _ = paths(name)
        if sock_path.exists():
            sock_path.unlink()
        server = await asyncio.start_unix_server(handler, path=str(sock_path))
        os.chmod(sock_path, 0o600)
        return server, str(sock_path)
    import asyncio
    port = _tcp_port(name)
    server = await asyncio.start_server(handler, host="127.0.0.1", port=port)
    return server, f"127.0.0.1:{port}"


def cleanup_endpoint(name=None):
    if not HAS_UNIX_SOCKET:
        return
    sock_path, _, _ = paths(name)
    try:
        sock_path.unlink()
    except FileNotFoundError:
        pass
