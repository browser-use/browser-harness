import asyncio
import os
import secrets
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path


TCP_HOST = "127.0.0.1"
TMP_DIR = Path(tempfile.gettempdir())


@dataclass(frozen=True)
class RuntimePaths:
    sock: Path
    pid: Path
    log: Path
    port: Path
    token: Path


def supports_unix_sockets():
    if not hasattr(socket, "AF_UNIX") or not hasattr(asyncio, "start_unix_server"):
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.close()
        return True
    except OSError:
        return False


def runtime_paths(name):
    base = TMP_DIR / f"bu-{name}"
    return RuntimePaths(
        sock=base.with_suffix(".sock"),
        pid=base.with_suffix(".pid"),
        log=base.with_suffix(".log"),
        port=base.with_suffix(".port"),
        token=base.with_suffix(".token"),
    )


def version_cache_path():
    return TMP_DIR / "bu-version-cache.json"


def screenshot_path(filename="shot.png"):
    return str(TMP_DIR / filename)


def endpoint_label(name):
    paths = runtime_paths(name)
    if paths.port.exists():
        try:
            port = int(paths.port.read_text().strip())
            return f"{TCP_HOST}:{port}"
        except (OSError, ValueError):
            return f"{TCP_HOST}:<unknown port> (port file: {paths.port})"
    if supports_unix_sockets():
        return str(paths.sock)
    try:
        port = int(paths.port.read_text().strip())
        return f"{TCP_HOST}:{port}"
    except (OSError, ValueError):
        return f"{TCP_HOST}:<unknown port> (port file: {paths.port})"


def _chmod_private(path):
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _write_private(path, value):
    path.write_text(value)
    _chmod_private(path)


def _connect_tcp(paths, timeout):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if timeout is not None:
        client.settimeout(timeout)
    try:
        port = int(paths.port.read_text().strip())
        token = paths.token.read_text().strip()
        client.connect((TCP_HOST, port))
        client.sendall((token + "\n").encode())
        return client
    except Exception:
        client.close()
        raise


def connect_client(name, timeout=None):
    paths = runtime_paths(name)
    if paths.port.exists():
        try:
            return _connect_tcp(paths, timeout)
        except (FileNotFoundError, OSError, ValueError):
            if not supports_unix_sockets():
                raise

    if supports_unix_sockets():
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if timeout is not None:
            client.settimeout(timeout)
        client.connect(str(paths.sock))
        return client

    return _connect_tcp(paths, timeout)


async def _start_tcp_server(handler, paths):
    token = secrets.token_urlsafe(32)

    async def authenticated_handler(reader, writer):
        try:
            line = await reader.readline()
            if line.decode(errors="replace").strip() != token:
                writer.close()
                await writer.wait_closed()
                return
            await handler(reader, writer)
        except Exception:
            writer.close()
            raise

    server = await asyncio.start_server(authenticated_handler, host=TCP_HOST, port=0)
    port = server.sockets[0].getsockname()[1]
    _write_private(paths.token, token)
    _write_private(paths.port, str(port))
    return server


async def start_server(handler, name):
    paths = runtime_paths(name)
    cleanup_endpoint(name)

    if supports_unix_sockets():
        try:
            server = await asyncio.start_unix_server(handler, path=str(paths.sock))
            _chmod_private(paths.sock)
            return server
        except (AttributeError, NotImplementedError, OSError):
            cleanup_endpoint(name)

    return await _start_tcp_server(handler, paths)


def cleanup_endpoint(name):
    paths = runtime_paths(name)
    for path in (paths.sock, paths.port, paths.token):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
