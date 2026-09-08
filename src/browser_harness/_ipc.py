"""Daemon IPC plumbing. AF_UNIX socket on POSIX, TCP loopback on Windows."""
import asyncio, json, os, re, secrets, socket, subprocess, sys
from pathlib import Path

from . import paths

IS_WINDOWS = sys.platform == "win32"
# Two caller-supplied dirs:
#   BH_RUNTIME_DIR — sock/port/pid. AF_UNIX sun_path is 104 bytes on macOS, so
#       the runtime dir must be short. Caller is responsible for keeping it
#       within budget. Falls back to BH_TMP_DIR (legacy single-dir callers),
#       then to the browser-harness runtime dir.
#   BH_TMP_DIR — screenshots, debug overlays, daemon log. No path-length
#       sensitivity; caller can use a deep persistent path.
# By default, a caller-supplied dir is treated as per-instance and files use
# bare "bu" stems. Set BH_RUNTIME_DIR_SHARED=1 or BH_TMP_DIR_SHARED=1 when the
# dir is shared by multiple BU_NAME values and the filename must carry the name.
BH_TMP_DIR = os.environ.get("BH_TMP_DIR")
BH_RUNTIME_DIR = os.environ.get("BH_RUNTIME_DIR") or BH_TMP_DIR
BH_RUNTIME_DIR_SHARED = os.environ.get("BH_RUNTIME_DIR_SHARED") == "1"
BH_TMP_DIR_SHARED = os.environ.get("BH_TMP_DIR_SHARED") == "1"
_TMP = paths.tmp_dir()
_RUNTIME = paths.ensure_private_dir(Path(BH_RUNTIME_DIR).expanduser().resolve()) if BH_RUNTIME_DIR else paths.runtime_dir()
_TMP.mkdir(parents=True, exist_ok=True)
_RUNTIME.mkdir(parents=True, exist_ok=True)
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


def _runtime_stem(name):  # "bu" when BH_RUNTIME_DIR isolates us, else "bu-<NAME>"
    _check(name)
    return "bu" if BH_RUNTIME_DIR and not BH_RUNTIME_DIR_SHARED else f"bu-{name}"


def _tmp_stem(name):  # "bu" when BH_TMP_DIR isolates us, else "bu-<NAME>"
    _check(name)
    return "bu" if BH_TMP_DIR and not BH_TMP_DIR_SHARED else f"bu-{name}"


def log_path(name):   return _TMP / f"{_tmp_stem(name)}.log"
def pid_path(name):   return _RUNTIME / f"{_runtime_stem(name)}.pid"
def port_path(name):  return _RUNTIME / f"{_runtime_stem(name)}.port"  # Windows-only: holds {"port","token"} JSON
def _sock_path(name): return _RUNTIME / f"{_runtime_stem(name)}.sock"


def _read_port_file(name):
    """(port, token) from the Windows port file, or (None, None) on any failure."""
    try:
        d = json.loads(port_path(name).read_text(encoding="utf-8"))
        return int(d["port"]), d["token"]
    except (FileNotFoundError, ValueError, KeyError, TypeError, OSError):
        return None, None


def sock_addr(name):  # display-only, used in log lines
    if not IS_WINDOWS: return str(_sock_path(name))
    port, _ = _read_port_file(name)
    return f"127.0.0.1:{port}" if port else f"tcp:{_runtime_stem(name)}"


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


def _lock_path(name):  return _RUNTIME / f"{_runtime_stem(name)}.lock"


def _lock_holder_alive(path):
    """True iff the PID recorded in `path` is still a live process. Unreadable,
    corrupt, or out-of-range contents count as not-alive (safe to reclaim)."""
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    # Same bounds as identify() above: os.kill(0, sig) hits the calling process
    # group rather than a specific process, and a value outside pid_t's range
    # makes os.kill() raise OverflowError instead of telling us "not alive".
    if not 0 < pid < (1 << 31):
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError, SystemError, OverflowError):
        return False


def acquire_startup_lock(name):
    """Claim exclusive ownership of `name`'s endpoint for the life of this server.

    Without this, two invocations racing for the same name could both pass a
    prior ping-based "not already running" check -- that check-then-act gap
    can be tens of seconds wide (CDP handshake, an unclicked Allow popup) --
    and the second would silently unlink + rebind over a still-live first
    daemon's socket, orphaning it with no error raised anywhere.
    The claim itself is a write-then-link: the PID is written to a private
    temp file first, then published via os.link(), which atomically creates
    the lock's directory entry only if it doesn't already exist. That keeps
    another invocation from ever observing a lock that exists but is still
    empty -- which a plain O_CREAT|O_EXCL-then-write would allow, and which
    would read as "corrupt, not-alive" and get reclaimed out from under the
    process that just created it.

    Staleness is decided by whether the PID recorded in the lock is still a
    live process, not by pinging the endpoint: the lock is meant to be held
    from before the endpoint exists (through the CDP handshake) to after it
    is torn down, so "nothing answers yet/anymore" is not evidence the lock
    holder is gone -- a ping-based check would let a second invocation steal
    the lock out from under a holder that simply hasn't bound yet.

    Raises RuntimeError if a live process already holds the lock. Reclaims a
    stale lock (previous holder crashed/was killed without cleanup).

    Call once per daemon lifetime and pass the returned path to serve();
    release it with release_startup_lock() only after the endpoint itself
    has been torn down, so a replacement can never bind while this process's
    old endpoint files might still be cleaned up out from under it."""
    path = _lock_path(name)
    for _attempt in range(2):
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(str(os.getpid()), encoding="utf-8")
        os.chmod(tmp, 0o600)
        try:
            os.link(str(tmp), str(path))
            return path
        except FileExistsError:
            if _lock_holder_alive(path):
                raise RuntimeError(
                    f"a browser-harness daemon is already running for BU_NAME={name!r}"
                ) from None
            try: path.unlink()  # stale lock, no live owner -- reclaim it
            except FileNotFoundError: pass
        finally:
            try: tmp.unlink()
            except FileNotFoundError: pass
    raise RuntimeError(f"failed to acquire startup lock for BU_NAME={name!r}")


def release_startup_lock(lock_path):
    try: lock_path.unlink()
    except FileNotFoundError: pass


async def serve(name, handler, lock_path=None):
    """Run the server until cancelled. handler(reader, writer) sees the same interface either way.

    `lock_path`: a lock already claimed via acquire_startup_lock(). Pass one
    when the caller needs to hold it across more than this call (e.g. a CDP
    handshake beforehand and endpoint cleanup after) -- the caller then owns
    releasing it via release_startup_lock(), not this function. Omit it to
    have serve() claim and release its own lock for the duration of the call."""
    global _server_token
    owns_lock = lock_path is None
    if owns_lock:
        # Off-thread: acquire_startup_lock() does blocking file I/O to check a
        # stale lock's liveness; running it inline would block this same event
        # loop that a *different* daemon's handler (in-process, e.g. tests)
        # needs to run on.
        lock_path = await asyncio.to_thread(acquire_startup_lock, name)
    try:
        if not IS_WINDOWS:
            path = str(_sock_path(name))
            if os.path.exists(path): os.unlink(path)
            # umask 0o077 makes bind() create the socket as 0600 — no TOCTOU window before chmod.
            old_umask = os.umask(0o077)
            try: server = await asyncio.start_unix_server(handler, path=path)
            finally: os.umask(old_umask)
            _server_token = None
            async with server: await asyncio.Event().wait()
            return
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        _server_token = secrets.token_hex(32)
        pf = port_path(name)
        # Atomic write so a concurrent reader never sees a half-written file.
        tmp = pf.with_name(pf.name + ".tmp")
        tmp.write_text(json.dumps({"port": port, "token": _server_token}), encoding="utf-8")
        os.replace(tmp, pf)
        try:
            async with server: await asyncio.Event().wait()
        finally:
            try: pf.unlink()
            except FileNotFoundError: pass
    finally:
        if owns_lock:
            await asyncio.to_thread(release_startup_lock, lock_path)


def expected_token():
    """The token the running daemon will accept, or None on POSIX."""
    return _server_token


def cleanup_endpoint(name):  # best-effort; silent if already gone
    p = _sock_path(name) if not IS_WINDOWS else port_path(name)
    try: p.unlink()
    except FileNotFoundError: pass
