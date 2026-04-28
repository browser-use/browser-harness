"""Daemon IPC plumbing. AF_UNIX socket on POSIX, TCP loopback on Windows."""
import asyncio, os, re, socket, subprocess, sys, tempfile
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
# Override via BH_TMP_DIR for sock/port/pid/log + screenshot output (e.g. per-session
# scratch dir). Default keeps AF_UNIX paths under sun_path limits (104 macOS, 108 Linux):
# /tmp on POSIX (gettempdir() returns long /var/folders/... on macOS); tempdir on Windows.
# Caller picking BH_TMP_DIR is responsible for keeping <dir>/bu-<NAME>.sock under 104 chars.
_TMP = Path(os.environ.get("BH_TMP_DIR") or (tempfile.gettempdir() if IS_WINDOWS else "/tmp"))
_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")


def _check(name):  # path-traversal guard for BU_NAME
    if not _NAME_RE.match(name or ""):
        raise ValueError(f"invalid BU_NAME {name!r}: must match [A-Za-z0-9_-]{{1,64}}")
    return name


def log_path(name):   return _TMP / f"bu-{_check(name)}.log"
def pid_path(name):   return _TMP / f"bu-{_check(name)}.pid"
def port_path(name):  return _TMP / f"bu-{_check(name)}.port"  # Windows-only: holds the daemon's TCP port
def _sock_path(name): return _TMP / f"bu-{_check(name)}.sock"


def sock_addr(name):  # display-only, used in log lines
    if not IS_WINDOWS: return str(_sock_path(name))
    try: return f"127.0.0.1:{port_path(name).read_text().strip()}"
    except FileNotFoundError: return f"tcp:bu-{_check(name)}"


def spawn_kwargs():  # subprocess.Popen flags so the daemon detaches from this terminal
    if IS_WINDOWS:
        return {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def connect(name, timeout=1.0):
    """Blocking client. Raises FileNotFoundError if no daemon, TimeoutError on connect timeout."""
    if not IS_WINDOWS:
        # uv-Python on Windows lacks socket.AF_UNIX, so this branch must be gated.
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout); s.connect(str(_sock_path(name))); return s
    try: port = int(port_path(name).read_text().strip())
    except (FileNotFoundError, ValueError): raise FileNotFoundError(str(port_path(name)))
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.settimeout(timeout); return s


async def serve(name, handler):
    """Run the server until cancelled. handler(reader, writer) sees the same interface either way."""
    if not IS_WINDOWS:
        path = str(_sock_path(name))
        if os.path.exists(path): os.unlink(path)
        server = await asyncio.start_unix_server(handler, path=path)
        os.chmod(path, 0o600)
        async with server: await asyncio.Event().wait()
        return
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    pf = port_path(name)
    pf.write_text(str(server.sockets[0].getsockname()[1]))  # so clients can find us
    try:
        async with server: await asyncio.Event().wait()
    finally:
        try: pf.unlink()
        except FileNotFoundError: pass


def cleanup_endpoint(name):  # best-effort; silent if already gone
    p = _sock_path(name) if not IS_WINDOWS else port_path(name)
    try: p.unlink()
    except FileNotFoundError: pass
