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


# --- cleanup_endpoint(): transient OSError / PermissionError retries ---

def test_cleanup_endpoint_retries_permission_error_and_succeeds(monkeypatch, tmp_path):
    """Regression for issue #893: on Windows, a just-SIGTERM'd daemon may still
    briefly hold the .port handle, causing p.unlink() to raise PermissionError
    ([WinError 5]). cleanup_endpoint() must retry instead of crashing."""
    port_file = tmp_path / "bu-default.port"
    port_file.write_text('{"port":12345,"token":"tok"}')
    real_unlink = type(port_file).unlink
    attempts = []
    sleeps = []

    def flaky_unlink(self, *args, **kwargs):
        attempts.append(self)
        if len(attempts) < 4:
            raise PermissionError(5, "Access is denied", str(self))
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(ipc, "IS_WINDOWS", True)
    monkeypatch.setattr(ipc, "port_path", lambda _name: port_file)
    monkeypatch.setattr(type(port_file), "unlink", flaky_unlink)
    monkeypatch.setattr(ipc.time, "sleep", lambda seconds: sleeps.append(seconds))

    ipc.cleanup_endpoint("default")

    assert len(attempts) == 4
    assert sleeps == [0.1, 0.1, 0.1]
    assert not port_file.exists()


def test_cleanup_endpoint_returns_immediately_on_file_not_found(monkeypatch, tmp_path):
    missing = tmp_path / "bu-default.sock"
    sleeps = []
    monkeypatch.setattr(ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(ipc, "_sock_path", lambda _name: missing)
    monkeypatch.setattr(ipc.time, "sleep", lambda seconds: sleeps.append(seconds))

    ipc.cleanup_endpoint("default")

    assert sleeps == []


def test_cleanup_endpoint_swallows_persistent_oserror_after_bounded_retries(monkeypatch, tmp_path):
    port_file = tmp_path / "bu-default.port"
    port_file.write_text('{"port":12345,"token":"tok"}')
    attempts = []
    sleeps = []

    def always_locked(self, *args, **kwargs):
        attempts.append(self)
        raise PermissionError(5, "Access is denied", str(self))

    monkeypatch.setattr(ipc, "IS_WINDOWS", True)
    monkeypatch.setattr(ipc, "port_path", lambda _name: port_file)
    monkeypatch.setattr(type(port_file), "unlink", always_locked)
    monkeypatch.setattr(ipc.time, "sleep", lambda seconds: sleeps.append(seconds))

    ipc.cleanup_endpoint("default")

    assert len(attempts) == 10
    assert sleeps == [0.1] * 9


def test_cleanup_endpoint_does_not_unlink_successor_endpoint_published_during_retry(monkeypatch, tmp_path):
    """If a concurrent startup publishes a new .port file after a transient
    Windows sharing error, cleanup_endpoint() must not unlink the successor's
    endpoint on subsequent retry attempts."""
    port_file = tmp_path / "bu-default.port"
    port_file.write_text('{"port":12345,"token":"old-tok"}')
    real_unlink = type(port_file).unlink
    attempts = []

    def flaky_unlink(self, *args, **kwargs):
        attempts.append(self.read_text(encoding="utf-8"))
        if len(attempts) == 1:
            raise PermissionError(5, "Access is denied", str(self))
        return real_unlink(self, *args, **kwargs)

    def publish_successor_during_sleep(_seconds):
        port_file.write_text('{"port":54321,"token":"new-tok"}')

    monkeypatch.setattr(ipc, "IS_WINDOWS", True)
    monkeypatch.setattr(ipc, "port_path", lambda _name: port_file)
    monkeypatch.setattr(type(port_file), "unlink", flaky_unlink)
    monkeypatch.setattr(ipc.time, "sleep", publish_successor_during_sleep)

    ipc.cleanup_endpoint("default")

    assert len(attempts) == 1
    assert port_file.exists()
    assert port_file.read_text(encoding="utf-8") == '{"port":54321,"token":"new-tok"}'

