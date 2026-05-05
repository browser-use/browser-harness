import asyncio, os, stat, sys
import pytest
from browser_harness import _ipc as ipc


# --- identify(): ping payload sanitation ---

class _FakeConn:
    def close(self): pass


def _patch_identify_response(monkeypatch, response):
    """Stub connect() and request() so identify() sees `response` as the JSON
    parsed from the daemon's reply, exactly as it would arrive over the wire."""
    monkeypatch.setattr(ipc, "connect", lambda name, timeout=1.0: (_FakeConn(), "tok"))
    monkeypatch.setattr(ipc, "request", lambda conn, tok, msg: response)


def test_identify_returns_pid_for_well_formed_ping_reply(monkeypatch):
    _patch_identify_response(monkeypatch, {"pong": True, "pid": 4242})

    assert ipc.identify("default", timeout=0.0) == 4242


def test_identify_rejects_boolean_pid(monkeypatch):
    """isinstance(True, int) is True in Python; a hostile or buggy daemon
    that replies {"pid": True} would otherwise yield PID 1 (init on POSIX),
    which os.kill(1, SIGTERM) would target. Reject it explicitly."""
    _patch_identify_response(monkeypatch, {"pong": True, "pid": True})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_rejects_boolean_false_pid(monkeypatch):
    """False is also an int subclass and would yield PID 0."""
    _patch_identify_response(monkeypatch, {"pong": True, "pid": False})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_returns_none_when_pid_field_missing(monkeypatch):
    """Pre-upgrade daemons reply {pong: True} only — no pid. identify must
    return None so callers know they have no verified PID to signal, while
    still letting alive-checks via ipc.ping() succeed."""
    _patch_identify_response(monkeypatch, {"pong": True})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_handles_non_dict_ping_payload(monkeypatch):
    """request() can deserialize any valid JSON value. A stale or hostile
    endpoint replying with a list / scalar / null would crash a naive
    resp.get() with AttributeError; identify must absorb that and return None."""
    for payload in ([1, 2, 3], "hello", 42, None):
        _patch_identify_response(monkeypatch, payload)
        assert ipc.identify("default", timeout=0.0) is None, (
            f"identify() should reject non-dict ping payload: {payload!r}"
        )


def test_identify_returns_none_when_pong_is_not_true(monkeypatch):
    _patch_identify_response(monkeypatch, {"pong": False, "pid": 4242})

    assert ipc.identify("default", timeout=0.0) is None


def test_identify_rejects_zero_and_negative_pids(monkeypatch):
    """os.kill semantics on POSIX: pid=0 signals every process in the calling
    process group; pid=-1 signals every process the caller can; pid<-1 signals
    the corresponding process group. None of these are valid daemon PIDs and
    forwarding any of them to os.kill would be catastrophic."""
    for bad_pid in (0, -1, -42, -99999):
        _patch_identify_response(monkeypatch, {"pong": True, "pid": bad_pid})
        assert ipc.identify("default", timeout=0.0) is None, (
            f"identify() must reject non-positive pid {bad_pid!r}"
        )


# --- ping(): same payload sanitation ---

def _patch_ping_response(monkeypatch, response):
    monkeypatch.setattr(ipc, "connect", lambda name, timeout=1.0: (_FakeConn(), "tok"))
    monkeypatch.setattr(ipc, "request", lambda conn, tok, msg: response)


def test_ping_returns_true_for_well_formed_pong(monkeypatch):
    _patch_ping_response(monkeypatch, {"pong": True})

    assert ipc.ping("default", timeout=0.0) is True


def test_ping_handles_non_dict_payload(monkeypatch):
    """Same regression class as identify(): if a stale or hostile endpoint
    replies with a list / scalar / null, ping() must return False rather than
    raising AttributeError on resp.get(). restart_daemon() now calls ping() on
    the fallback path, so an unhandled raise here would abort cleanup."""
    for payload in ([1, 2, 3], "hello", 42, None):
        _patch_ping_response(monkeypatch, payload)
        assert ipc.ping("default", timeout=0.0) is False, (
            f"ping() should reject non-dict payload: {payload!r}"
        )


def test_ping_returns_false_when_pong_field_is_missing_or_not_true(monkeypatch):
    for resp in ({}, {"pong": False}, {"pong": "yes"}, {"pong": 1}):
        _patch_ping_response(monkeypatch, resp)
        assert ipc.ping("default", timeout=0.0) is False, (
            f"ping() should require pong is exactly True; got: {resp!r}"
        )


# --- serve(): AF_UNIX bind permissions / symlink defense ---
# Regression coverage for #298. POSIX-only — Windows uses TCP loopback.

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only AF_UNIX path")


@skip_on_windows
def test_ensure_private_dir_creates_with_0o700(tmp_path):
    """Fresh mkdir path: dir must end up mode 0o700, owned by us."""
    target = tmp_path / "priv.d"
    ipc._ensure_private_dir(target)
    st = os.lstat(target)
    assert stat.S_ISDIR(st.st_mode)
    assert (st.st_mode & 0o777) == 0o700
    assert st.st_uid == os.geteuid()


@skip_on_windows
def test_ensure_private_dir_tightens_loose_perms(tmp_path):
    """Pre-existing dir owned by us with loose perms gets chmod'd back to 0o700."""
    target = tmp_path / "loose.d"
    target.mkdir(mode=0o755)
    os.chmod(target, 0o755)  # in case umask suppressed group/other bits at mkdir
    ipc._ensure_private_dir(target)
    assert (os.lstat(target).st_mode & 0o777) == 0o700


@skip_on_windows
def test_ensure_private_dir_refuses_symlink(tmp_path):
    """A symlink at the path — even pointing to a real dir we'd accept — must
    be refused. lstat (not stat) is what makes this detection possible."""
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    link = tmp_path / "link.d"
    os.symlink(real, link)
    with pytest.raises(RuntimeError, match="not a directory"):
        ipc._ensure_private_dir(link)


@skip_on_windows
def test_ensure_private_dir_refuses_non_directory(tmp_path):
    """A regular file at the path is also refused (not a dir)."""
    target = tmp_path / "file.d"
    target.write_text("")
    with pytest.raises(RuntimeError, match="not a directory"):
        ipc._ensure_private_dir(target)


@skip_on_windows
def test_serve_socket_is_mode_0o600_with_umask_zero(tmp_path, monkeypatch):
    """The whole point of #298: with umask 0, the socket file used to exist on
    disk briefly at 0o777 between bind() and chmod(). After the fix, set umask
    to 0 in the test, run serve() through bind(), and verify the on-disk mode
    is never wider than 0o700. We also verify the final chmod tightens to 0o600.

    We can't observe the *intermediate* state from Python without instrumenting
    syscalls, but the umask wrapper guarantees the kernel never wrote a wider
    mode in the first place."""
    monkeypatch.setattr(ipc, "_TMP", tmp_path)
    old_umask = os.umask(0)
    try:
        async def runner():
            async def handler(r, w): w.close()
            # Manually replicate the POSIX branch up through chmod, then stop.
            # Calling serve() directly would block forever on the trailing
            # asyncio.Event().wait().
            ipc._ensure_private_dir(ipc._sock_dir("default"))
            path = str(ipc._sock_path("default"))
            try: os.unlink(path)
            except FileNotFoundError: pass
            saved = os.umask(0o077)
            try:
                server = await asyncio.start_unix_server(handler, path=path)
            finally:
                os.umask(saved)
            mode_before_chmod = os.lstat(path).st_mode & 0o777
            os.chmod(path, 0o600)
            mode_after = os.lstat(path).st_mode & 0o777
            server.close()
            await server.wait_closed()
            return mode_before_chmod, mode_after
        before, after = asyncio.run(runner())
    finally:
        os.umask(old_umask)
    # umask 0o077 means socket created mode 0o700 (or stricter); never wider.
    assert before & 0o077 == 0, f"socket exposed group/other bits: {oct(before)}"
    assert after == 0o600


@skip_on_windows
def test_serve_unlinks_stale_symlink_inside_private_dir(tmp_path, monkeypatch):
    """If a stale symlink (e.g. left over from external tampering) sits at the
    socket path, the unconditional unlink must remove it — os.path.exists()
    used to follow it and skip the unlink, leading bind() to follow the
    symlink kernel-side."""
    monkeypatch.setattr(ipc, "_TMP", tmp_path)
    ipc._ensure_private_dir(ipc._sock_dir("default"))
    path = ipc._sock_path("default")
    # Dangling symlink at the socket path.
    target = tmp_path / "elsewhere"
    os.symlink(target, path)
    assert not os.path.exists(path)  # dangling: exists() returns False — the old bug

    async def runner():
        async def handler(r, w): w.close()
        try: os.unlink(str(path))
        except FileNotFoundError: pass
        saved = os.umask(0o077)
        try:
            server = await asyncio.start_unix_server(handler, path=str(path))
        finally:
            os.umask(saved)
        os.chmod(str(path), 0o600)
        # Bound path must be a real socket, not a symlink, and not at the
        # symlink's target.
        st = os.lstat(str(path))
        is_sock = stat.S_ISSOCK(st.st_mode)
        target_exists = os.path.exists(target)
        server.close()
        await server.wait_closed()
        return is_sock, target_exists

    is_sock, target_exists = asyncio.run(runner())
    assert is_sock, "bound path must be a real socket, not a symlink"
    assert not target_exists, "bind() must not have followed the symlink"
