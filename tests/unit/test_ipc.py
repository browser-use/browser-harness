import asyncio
import os
import shutil
import tempfile
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


# --- acquire_startup_lock(): staleness must track process liveness, not ping ---


def test_acquire_startup_lock_rejects_a_lock_held_by_a_live_pid_that_isnt_answering_yet(
    monkeypatch, tmp_path
):
    """Regression test for cubic review comment on #692 (finding 1).

    A daemon that has claimed the lock but hasn't bound its endpoint yet (mid
    CDP handshake, or an unclicked "Allow remote debugging?" popup) has no
    endpoint to ping. Deciding staleness by pinging would treat "nothing
    answers yet" as "the holder is gone" and let a second invocation steal
    the lock and race to bind -- exactly the bug this lock exists to prevent.
    Staleness must be decided by whether the recorded PID is still alive.
    """
    monkeypatch.setattr(ipc, "_RUNTIME", tmp_path)
    lock_path = ipc._lock_path("worker")
    lock_path.write_text(str(os.getpid()), encoding="utf-8")  # our own pid: always alive

    with pytest.raises(RuntimeError, match="already running"):
        ipc.acquire_startup_lock("worker")

    assert lock_path.read_text(encoding="utf-8") == str(os.getpid())


def test_acquire_startup_lock_reclaims_a_lock_left_by_a_dead_pid(monkeypatch, tmp_path):
    monkeypatch.setattr(ipc, "_RUNTIME", tmp_path)
    lock_path = ipc._lock_path("worker")
    lock_path.write_text("999999", encoding="utf-8")

    def fake_kill(pid, _sig):
        if pid == 999999:
            raise ProcessLookupError()

    monkeypatch.setattr(ipc.os, "kill", fake_kill)

    reclaimed = ipc.acquire_startup_lock("worker")

    assert reclaimed == lock_path
    assert lock_path.read_text(encoding="utf-8") == str(os.getpid())


def test_acquire_startup_lock_reclaims_a_lock_containing_pid_zero(monkeypatch, tmp_path):
    """Regression test for cubic review comment on #692 (finding 4).

    os.kill(0, 0) signals the caller's own process group and succeeds, so a
    lock file containing "0" would read as a live holder forever without the
    same pid-range guard identify() already applies elsewhere.
    """
    monkeypatch.setattr(ipc, "_RUNTIME", tmp_path)
    lock_path = ipc._lock_path("worker")
    lock_path.write_text("0", encoding="utf-8")

    reclaimed = ipc.acquire_startup_lock("worker")

    assert reclaimed == lock_path
    assert lock_path.read_text(encoding="utf-8") == str(os.getpid())


def test_acquire_startup_lock_never_publishes_the_lock_before_its_pid_is_written(
    monkeypatch, tmp_path
):
    """Regression test for cubic review comment on #692 (finding 1).

    The old O_CREAT|O_EXCL-then-write left a window where the lock's
    directory entry existed before its PID was written. A racing acquire
    that hit that window would read the file as empty, treat it as corrupt
    (not-alive), and reclaim a lock another process was still creating.
    Publishing must happen via os.link() from an already-fully-written temp
    file, so the lock is never observable with partial content.
    """
    monkeypatch.setattr(ipc, "_RUNTIME", tmp_path)
    real_link = os.link
    seen_content_at_publish = {}

    def spy_link(src, dst):
        seen_content_at_publish["content"] = Path(src).read_text(encoding="utf-8")
        return real_link(src, dst)

    monkeypatch.setattr(ipc.os, "link", spy_link)

    lock_path = ipc.acquire_startup_lock("worker")

    assert seen_content_at_publish["content"] == str(os.getpid())
    assert lock_path.read_text(encoding="utf-8") == str(os.getpid())
    # The private temp file used to stage the write must not linger.
    assert list(tmp_path.iterdir()) == [lock_path]


# --- serve(): startup mutual exclusion ---


def test_serve_does_not_silently_evict_a_still_running_daemon(monkeypatch):
    """Regression test for #692.

    already_running() is a ping check performed *before* serve() binds, with
    no lock held across that gap. serve() itself does a check-then-act:
    `if os.path.exists(path): os.unlink(path)` then binds a new listener at
    the same path -- unconditionally, with no ownership check. Two
    invocations racing for the same name can both pass the "not already
    running" check; the second then silently unlinks and rebinds over the
    first daemon's live socket, orphaning it with no error raised anywhere.

    This asserts the observable contract from the issue: once a daemon is
    up and reachable, a second serve() attempt for the same name must not
    silently take over -- either the first stays reachable, or the second
    attempt fails loudly. POSIX-only (exercises the AF_UNIX socket file).
    """
    if ipc.IS_WINDOWS:
        pytest.skip("POSIX-only: exercises the AF_UNIX socket-file race")

    # AF_UNIX sun_path is 104 bytes on macOS -- pytest's own tmp_path nests
    # too deep for that, so use a short-named dir directly under /tmp
    # instead (same constraint _ipc.py itself documents for BH_RUNTIME_DIR).
    runtime_dir = Path(tempfile.mkdtemp(prefix="bhipc-", dir="/tmp"))
    monkeypatch.setattr(ipc, "_RUNTIME", runtime_dir)
    name = "race"

    async def handler_one(reader, writer):
        await reader.readline()
        writer.write(b'{"pong": true, "pid": 111}\n')
        await writer.drain()
        writer.close()

    async def handler_two(reader, writer):
        await reader.readline()
        writer.write(b'{"pong": true, "pid": 222}\n')
        await writer.drain()
        writer.close()

    async def scenario():
        task_one = asyncio.create_task(ipc.serve(name, handler_one))
        try:
            for _ in range(200):
                if ipc._sock_path(name).exists():
                    break
                await asyncio.sleep(0.01)
            else:
                raise AssertionError("first daemon never bound its socket")

            # identify() is blocking socket I/O; run it off-thread so it
            # doesn't stall the event loop the server tasks need to run on.
            first_pid = await asyncio.to_thread(ipc.identify, name, 1.0)
            assert first_pid == 111, "sanity check: first daemon should answer first"

            task_two = asyncio.create_task(ipc.serve(name, handler_two))
            try:
                await asyncio.sleep(0.2)  # let a racing serve() unlink + rebind

                assert not task_one.done(), (
                    "the first daemon's serve() task must not be silently "
                    "torn down by a second invocation for the same name"
                )
                second_pid = await asyncio.to_thread(ipc.identify, name, 1.0)
                assert second_pid == first_pid, (
                    "a second serve() call silently took over the socket for "
                    "a still-running daemon (reached pid "
                    f"{second_pid} instead of the original {first_pid}) -- "
                    "it must either fail to start or leave the first daemon "
                    "reachable, never evict it silently"
                )
            finally:
                task_two.cancel()
                try:
                    await task_two
                except (asyncio.CancelledError, Exception):
                    pass
        finally:
            task_one.cancel()
            try:
                await task_one
            except (asyncio.CancelledError, Exception):
                pass

    try:
        asyncio.run(scenario())
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
