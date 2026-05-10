import asyncio
import os
import stat
import sys
from pathlib import Path

import pytest

from browser_harness import _ipc as ipc


def test_runtime_stem_uses_name_in_shared_runtime_dir(monkeypatch):
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR", "/tmp/browser-harness")
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR_SHARED", True)

    assert ipc._runtime_stem("work") == "bu-work"


def test_runtime_stem_uses_bare_name_in_isolated_runtime_dir(monkeypatch):
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR", "/tmp/browser-harness-work")
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR_SHARED", False)

    assert ipc._runtime_stem("work") == "bu"


def test_tmp_stem_uses_name_in_shared_tmp_dir(monkeypatch):
    monkeypatch.setattr(ipc, "BH_TMP_DIR", "/tmp/browser-harness")
    monkeypatch.setattr(ipc, "BH_TMP_DIR_SHARED", True)

    assert ipc._tmp_stem("work") == "bu-work"


# --- serve(): AF_UNIX socket created with owner-only permissions ---

@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only: AF_UNIX socket perms")
def test_serve_posix_socket_is_created_with_owner_only_perms(tmp_path, monkeypatch):
    """The AF_UNIX socket file must be mode 0o600 from the moment bind()
    creates it, not just after the explicit chmod. asyncio.start_unix_server
    begins accepting connections immediately, so a co-located unprivileged
    user racing connect() against the chmod could otherwise issue CDP
    commands during that window. Tightening the umask around bind() makes
    the permissions correct atomically; this test asserts (a) umask is set
    to 0o077 by the time start_unix_server's bind() runs, and (b) chmod
    0o600 fires on the resulting path as a defence-in-depth follow-up."""
    # serve() resolves the socket via _RUNTIME + _runtime_stem(name).
    # BH_RUNTIME_DIR set + not shared makes _runtime_stem return "bu". Bind via
    # a *relative* path from inside tmp_path: macOS caps AF_UNIX sun_path at
    # ~104 bytes and pytest's tmp_path under /var/folders can exceed that, so
    # _RUNTIME="." keeps the bound path short ("bu.sock") on every platform.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(ipc, "BH_RUNTIME_DIR_SHARED", False)
    monkeypatch.setattr(ipc, "_RUNTIME", Path("."))

    captured = {"umask_during_bind": None}
    chmod_calls = []
    real_start = asyncio.start_unix_server
    real_chmod = os.chmod

    async def spy_start(handler, path):
        # Snapshot the umask the kernel will see when bind() creates the
        # socket file. os.umask(0) flips to 0 and returns the prior value;
        # restore immediately so we don't disturb the run.
        current = os.umask(0)
        os.umask(current)
        captured["umask_during_bind"] = current
        return await real_start(handler, path)

    def spy_chmod(path, mode):
        chmod_calls.append((str(path), mode))
        return real_chmod(path, mode)

    monkeypatch.setattr(asyncio, "start_unix_server", spy_start)
    monkeypatch.setattr(os, "chmod", spy_chmod)

    async def run():
        async def handler(reader, writer):
            writer.close()

        task = asyncio.create_task(ipc.serve("default", handler))
        # Yield until serve() has reached its blocking point — chmod is the
        # last sync step before `await asyncio.Event().wait()`, so seeing
        # the chmod call is the cleanest "serve is past setup" signal.
        for _ in range(200):
            await asyncio.sleep(0)
            if chmod_calls and captured["umask_during_bind"] is not None:
                break
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, BaseException):
            pass

    asyncio.run(run())
    assert captured["umask_during_bind"] == 0o077, (
        f"serve() must tighten umask to 0o077 before start_unix_server's "
        f"bind() creates the socket file. Saw umask="
        f"{oct(captured['umask_during_bind']) if captured['umask_during_bind'] is not None else 'unset'}."
    )
    sock_path = str(Path(".") / "bu.sock")
    assert (sock_path, 0o600) in chmod_calls, (
        f"serve() must chmod the socket file to 0o600 as a belt-and-braces "
        f"defence after umask. Got chmod calls: {chmod_calls}"
    )


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
