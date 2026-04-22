import asyncio
import os
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path


TMP_DIR = Path(tempfile.gettempdir())


@dataclass(frozen=True)
class RuntimePaths:
    sock: Path
    pid: Path
    log: Path
    port: Path


def supports_unix_sockets():
    return hasattr(socket, "AF_UNIX") and hasattr(asyncio, "start_unix_server")


def runtime_paths(name):
    base = TMP_DIR / f"bu-{name}"
    return RuntimePaths(
        sock=base.with_suffix(".sock"),
        pid=base.with_suffix(".pid"),
        log=base.with_suffix(".log"),
        port=base.with_suffix(".port"),
    )


def version_cache_path():
    return TMP_DIR / "bu-version-cache.json"


def screenshot_path(filename="shot.png"):
    return str(TMP_DIR / filename)


def endpoint_label(name):
    paths = runtime_paths(name)
    return str(paths.sock) if supports_unix_sockets() else f"127.0.0.1:{paths.port}"


def connect_client(name, timeout=None):
    paths = runtime_paths(name)
    if supports_unix_sockets():
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if timeout is not None:
            client.settimeout(timeout)
        client.connect(str(paths.sock))
        return client

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if timeout is not None:
        client.settimeout(timeout)
    port = int(paths.port.read_text().strip())
    client.connect(("127.0.0.1", port))
    return client


async def start_server(handler, name):
    paths = runtime_paths(name)
    cleanup_endpoint(name)

    if supports_unix_sockets():
        server = await asyncio.start_unix_server(handler, path=str(paths.sock))
        try:
            os.chmod(paths.sock, 0o600)
        except OSError:
            pass
        return server

    server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
    port = server.sockets[0].getsockname()[1]
    paths.port.write_text(str(port))
    return server


def cleanup_endpoint(name):
    paths = runtime_paths(name)
    for path in (paths.sock, paths.port):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
