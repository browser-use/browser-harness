"""Daemon IPC plumbing. AF_UNIX socket on POSIX, TCP loopback on Windows."""
import asyncio, json, os, re, secrets, socket, subprocess, sys, tempfile
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
# BH_TMP_DIR set → caller-isolated dir, bare filenames (avoids AF_UNIX sun_path
# overrun: 104 macOS / 108 Linux). Unset → shared tmpdir, "bu-<NAME>" prefix
# disambiguates daemons. POSIX default is /tmp (gettempdir() returns long
# /var/folders/... on macOS); Windows uses TCP so any tempdir is fine.
BH_TMP_DIR = os.environ.get("BH_TMP_DIR")
_TMP = Path(BH_TMP_DIR or (tempfile.gettempdir() if IS_WINDOWS else "/tmp"))
_TMP.mkdir(parents=True, exist_ok=True)
_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")

# Set by serve() on Windows. Daemon's handle() requires every request to carry
# this token (TCP loopback has no chmod-equivalent so any local process could
# otherwise issue CDP commands). Stays None on POSIX where AF_UNIX + chmod 600
# is the boundary.
_server_token = None


def _check(name):  # path-traversal guard for BU_NAME
    if not _NAME_RE.match(name or ""):
        raise ValueError(f"invalid BU_NAME {name!r}: must match [A-Za-z0-9_-]{{1,64}}")
    return name


def _stem(name):  # "bu" when BH_TMP_DIR isolates us, else "bu-<NAME>"
    _check(name)
    return "bu" if BH_TMP_DIR else f"bu-{name}"


def log_path(name):   return _TMP / f"{_stem(name)}.log"
def pid_path(name):   return _TMP / f"{_stem(name)}.pid"
def port_path(name):  return _TMP / f"{_stem(name)}.port"  # Windows-only: holds {"port","token"} JSON
def _sock_path(name): return _TMP / f"{_stem(name)}.sock"


def _read_port_file(name):
    """(port, token) from the Windows port file, or (None, None) on any failure."""
    try:
        d = json.loads(port_path(name).read_text())
        return int(d["port"]), d["token"]
    except (FileNotFoundError, ValueError, KeyError, TypeError, OSError):
        return None, None


def sock_addr(name):  # display-only, used in log lines
    if not IS_WINDOWS: return str(_sock_path(name))
    port, _ = _read_port_file(name)
    return f"127.0.0.1:{port}" if port else f"tcp:{_stem(name)}"


def spawn_kwargs():  # subprocess.Popen flags so the daemon detaches from this terminal
    if IS_WINDOWS:
        # CREATE_NO_WINDOW: no console window for the daemon. CREATE_NEW_PROCESS_GROUP:
        # daemon doesn't receive Ctrl-C/Ctrl-Break sent to the parent terminal, so
        # closing that terminal doesn't kill it. DETACHED_PROCESS is intentionally
        # omitted: per Win32 docs it overrides CREATE_NO_WINDOW, causing Windows to
        # allocate a fresh console for the (still console-subsystem) python.exe.
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def connect(name, timeout=1.0):
    """Blocking client. Returns (sock, token); token is None on POSIX, hex string on Windows.
    Callers sending JSON requests MUST include the token as req["token"] on Windows."""
    if not IS_WINDOWS:
        # uv-Python on Windows lacks socket.AF_UNIX, so this branch must be gated.
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout); s.connect(str(_sock_path(name))); return s, None
    port, token = _read_port_file(name)
    if port is None: raise FileNotFoundError(str(port_path(name)))
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.settimeout(timeout); return s, token


def request(c, token, req):
    """One-shot send + recv + parse on an open socket. Injects token on Windows.
    Returns the parsed JSON response. Caller closes the socket."""
    if token: req = {**req, "token": token}
    c.sendall((json.dumps(req) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = c.recv(1 << 16)
        if not chunk: break
        data += chunk
    return json.loads(data or b"{}")


def ping(name, timeout=1.0):
    """True iff a live daemon answers our ping. Defends against stale .port files
    + port reuse: a bare TCP connect can succeed against an unrelated process that
    grabbed the port after our daemon crashed; only our daemon answers {"pong":true}."""
    try:
        c, token = connect(name, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
        return False
    try:
        resp = request(c, token, {"meta": "ping"})
        # request() returns parsed JSON, which may be any valid value (a list,
        # scalar, etc. from a stale or hostile endpoint). Anything that isn't
        # a {pong: true} dict counts as "not our daemon" — never .get() blindly.
        return isinstance(resp, dict) and resp.get("pong") is True
    except (OSError, ValueError, AttributeError):
        return False
    finally:
        try: c.close()
        except OSError: pass


def identify(name, timeout=1.0):
    """Return the live daemon's PID, or None if unreachable.

    Used by restart_daemon() to signal a process whose identity has been
    verified end-to-end (live IPC + self-reported PID), instead of trusting
    a pid file whose number may have been reused by an unrelated process."""
    try:
        c, token = connect(name, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
        return None
    try:
        resp = request(c, token, {"meta": "ping"})
        # request() returns parsed JSON, which may be any valid value (a list,
        # scalar, etc. from a stale or hostile endpoint). Anything that isn't
        # a {pong: true} dict gets None — never .get() on a non-dict.
        if not isinstance(resp, dict) or resp.get("pong") is not True:
            return None
        pid = resp.get("pid")
        # `type(pid) is int` (not isinstance) intentionally rejects bool: in
        # Python, isinstance(True, int) is True, so a hostile/buggy daemon
        # could reply with {"pid": True} and we'd treat that as PID 1 (init).
        # Also reject 0/negatives — os.kill(0, sig) signals every process in
        # the calling process group, os.kill(-1, sig) signals every process
        # the caller can. Upper bound is 2**31 because C pid_t is typically
        # signed 32-bit and a value outside that range makes os.kill() raise
        # OverflowError, which would propagate out of restart_daemon() before
        # its cleanup. Linux pid_max is also bounded at 2**22 in practice.
        return pid if type(pid) is int and 0 < pid < (1 << 31) else None
    except (OSError, ValueError, AttributeError):
        return None
    finally:
        try: c.close()
        except OSError: pass


async def serve(name, handler):
    """Run the server until cancelled. handler(reader, writer) sees the same interface either way."""
    global _server_token
    if not IS_WINDOWS:
        path = str(_sock_path(name))
        if os.path.exists(path): os.unlink(path)
        server = await asyncio.start_unix_server(handler, path=path)
        os.chmod(path, 0o600)
        _server_token = None
        async with server: await asyncio.Event().wait()
        return
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    _server_token = secrets.token_hex(32)
    pf = port_path(name)
    # Atomic write so a concurrent reader never sees a half-written file.
    tmp = pf.with_name(pf.name + ".tmp")
    tmp.write_text(json.dumps({"port": port, "token": _server_token}))
    os.replace(tmp, pf)
    try:
        async with server: await asyncio.Event().wait()
    finally:
        try: pf.unlink()
        except FileNotFoundError: pass


def expected_token():
    """The token the running daemon will accept, or None on POSIX."""
    return _server_token


def cleanup_endpoint(name):  # best-effort; silent if already gone
    p = _sock_path(name) if not IS_WINDOWS else port_path(name)
    try: p.unlink()
    except FileNotFoundError: pass
