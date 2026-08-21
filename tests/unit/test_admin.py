import threading
import urllib.error
from contextlib import contextmanager

import pytest

from browser_harness import admin


def write_remote_id(path, browser_id):
    path.write_text(admin._encode_remote_browser_id(browser_id))


class FakeSocket:
    def __init__(self, response=b'{"target_id":"target-1","session_id":"session-1","page":null}\n'):
        self.response = response
        self.closed = False
        self.sent = b""

    def sendall(self, data):
        self.sent += data

    def recv(self, _size):
        out, self.response = self.response, b""
        return out

    def close(self):
        self.closed = True


def test_local_chrome_mode_is_false_when_env_provides_remote_cdp():
    assert not admin._is_local_chrome_mode({"BU_CDP_WS": "ws://example.test/devtools/browser/1"})


def test_require_existing_daemon_fails_without_spawning(monkeypatch):
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)

    with pytest.raises(RuntimeError, match="required daemon 'scoped' is not running"):
        admin.require_existing_daemon("scoped")


def test_require_existing_daemon_probes_cdp(monkeypatch):
    sock = FakeSocket(response=b'{"result":{"targetInfos":[]}}\n')
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda _name, timeout: (sock, None))

    admin.require_existing_daemon("scoped")

    assert b'"method": "Target.getTargets"' in sock.sent
    assert sock.closed is True


def test_strict_remote_stop_propagates_daemon_error(monkeypatch, tmp_path):
    sock = FakeSocket(response=b'{"error":"billing stop failed"}\n')
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: True)
    monkeypatch.setattr(admin.ipc, "identify", lambda _name, timeout: 123)
    monkeypatch.setattr(admin, "_process_start_time", lambda _pid: 1)
    monkeypatch.setattr(admin.ipc, "connect", lambda _name, timeout: (sock, None))
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: tmp_path / "remote-id")
    monkeypatch.setattr(admin, "_daemon_browser_identity", lambda _name: (None, None))

    with pytest.raises(RuntimeError, match="billing stop failed"):
        admin.stop_remote_daemon("scoped")

    assert sock.closed is True


def test_restart_daemon_require_clean_rejects_missing_daemon(monkeypatch):
    monkeypatch.setattr(admin.ipc, "identify", lambda _name, timeout: None)
    monkeypatch.setattr(admin.ipc, "ping", lambda _name, timeout: False)

    with pytest.raises(RuntimeError, match="unavailable for required clean shutdown"):
        admin.restart_daemon("scoped", require_clean=True)


def test_restart_daemon_require_clean_rejects_eof_response(monkeypatch):
    sock = FakeSocket(response=b"")
    monkeypatch.setattr(admin.ipc, "identify", lambda _name, timeout: None)
    monkeypatch.setattr(admin.ipc, "ping", lambda _name, timeout: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda _name, timeout: (sock, None))

    with pytest.raises(RuntimeError, match="did not confirm clean shutdown"):
        admin.restart_daemon("scoped", require_clean=True)

    assert sock.closed is True


def test_remote_stop_falls_back_when_daemon_dies_after_outer_probe(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    write_remote_id(state_path, "browser-1")
    restarts = []
    stopped = []
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: True)

    def fake_restart(name, require_clean=False):
        restarts.append((name, require_clean))
        if require_clean:
            raise RuntimeError("daemon vanished")

    monkeypatch.setattr(admin, "_restart_daemon_locked", fake_restart)
    monkeypatch.setattr(
        admin,
        "_stop_cloud_browser",
        lambda browser_id, strict=False: stopped.append((browser_id, strict)) or True,
    )

    admin.stop_remote_daemon("scoped")

    assert restarts == [("scoped", True), ("scoped", False)]
    assert stopped == [("browser-1", True)]
    assert not state_path.exists()


def test_remote_stop_fallback_error_describes_the_whole_recovery_step(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    write_remote_id(state_path, "browser-1")
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: True)
    monkeypatch.setattr(admin, "_daemon_browser_identity", lambda _name: ("cloud", "browser-1"))

    def restart(_name, require_clean=False):
        raise RuntimeError("clean shutdown failed" if require_clean else "forced cleanup failed")

    monkeypatch.setattr(admin, "_restart_daemon_locked", restart)
    monkeypatch.setattr(admin, "_stop_cloud_browser", lambda _browser_id, strict=False: True)

    with pytest.raises(ExceptionGroup, match="fallback cloud-browser recovery") as exc_info:
        admin.stop_remote_daemon("scoped")

    assert [str(error) for error in exc_info.value.exceptions] == [
        "clean shutdown failed",
        "forced cleanup failed",
    ]


@pytest.mark.parametrize(
    ("daemon_identity", "direct_stops"),
    [
        (("local", None), ["browser-1"]),
        (("cdp", None), ["browser-1"]),
        (("cloud", "browser-1"), []),
        (("cloud", "browser-2"), ["browser-1"]),
    ],
)
def test_live_daemon_stops_persisted_browser_only_when_it_is_not_the_exact_owner(
    monkeypatch, tmp_path, daemon_identity, direct_stops
):
    state_path = tmp_path / "remote-id"
    write_remote_id(state_path, "browser-1")
    restarts = []
    stopped = []
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: True)
    monkeypatch.setattr(admin, "_daemon_browser_identity", lambda _name: daemon_identity)
    monkeypatch.setattr(
        admin,
        "_restart_daemon_locked",
        lambda name, require_clean=False: restarts.append((name, require_clean)),
    )
    monkeypatch.setattr(
        admin,
        "_stop_cloud_browser",
        lambda browser_id, strict=False: stopped.append(browser_id) or True,
    )

    admin.stop_remote_daemon("scoped")

    assert restarts == [("scoped", True)]
    assert stopped == direct_stops
    assert not state_path.exists()


def test_remote_stop_ignores_corrupt_recovery_state_after_live_clean_shutdown(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    state_path.write_text("not a valid cloud id!\n")
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: True)
    monkeypatch.setattr(admin, "_restart_daemon_locked", lambda _name, require_clean=False: None)

    admin.stop_remote_daemon("scoped")

    assert not state_path.exists()


def test_remote_start_retries_cleanup_and_preserves_both_failures(monkeypatch, tmp_path):
    attempts = []
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
    monkeypatch.setattr(admin.uuid, "uuid4", lambda: "browser-1")
    monkeypatch.setattr(
        admin,
        "_browser_use",
        lambda path, method, body=None: (
            {"id": "browser-1", "cdpUrl": "https://cdp.example.test"}
            if method == "POST"
            else attempts.append((path, method, body))
            or (_ for _ in ()).throw(OSError("billing stop failed"))
        ),
    )
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda _url: "wss://cdp.example.test/ws")
    monkeypatch.setattr(
        admin,
        "_ensure_daemon_locked",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("daemon start failed")),
    )
    monkeypatch.setattr(admin.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: tmp_path / "remote-id")

    with pytest.raises(BaseExceptionGroup) as exc_info:
        admin.start_remote_daemon("scoped")

    assert [str(error) for error in exc_info.value.exceptions] == [
        "daemon start failed",
        "failed to stop remote browser browser-1: billing stop failed",
    ]
    assert len(attempts) == 3
    assert admin._read_remote_browser_id("scoped") == "browser-1"


def test_remote_start_does_not_post_when_recovery_state_cannot_promote(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    pending_path = tmp_path / "remote-id.pending"
    attempts = []
    real_replace = admin.os.replace
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
    monkeypatch.setattr(admin.uuid, "uuid4", lambda: "browser-1")
    monkeypatch.setattr(
        admin,
        "_browser_use",
        lambda path, method, body=None: (
            {"id": "browser-1", "cdpUrl": "https://cdp.example.test"}
            if method == "POST"
            else attempts.append((path, method, body))
            or (_ for _ in ()).throw(OSError("billing stop failed"))
        ),
    )
    monkeypatch.setattr(admin.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(
        admin.os,
        "replace",
        lambda _source, _destination: (_ for _ in ()).throw(OSError("rename failed")),
    )

    with pytest.raises(OSError, match="rename failed"):
        admin.start_remote_daemon("scoped")

    assert attempts == []
    expected = admin._encode_remote_browser_recovery(client_session_id="browser-1")
    assert pending_path.read_text() == expected
    assert not state_path.exists()

    monkeypatch.setattr(admin.os, "replace", real_replace)
    assert admin._read_remote_browser_recovery("scoped") == {
        "browser_id": None,
        "client_session_id": "browser-1",
    }
    assert state_path.read_text() == expected
    assert not pending_path.exists()


def test_remote_id_persistence_retains_complete_pending_record_when_directory_fsync_fails(
    monkeypatch, tmp_path
):
    state_path = tmp_path / "remote-id"
    pending_path = tmp_path / "remote-id.pending"
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(
        admin,
        "_fsync_directory",
        lambda _directory: (_ for _ in ()).throw(OSError("directory fsync failed")),
    )

    with pytest.raises(OSError, match="directory fsync failed"):
        admin._persist_remote_browser_id("scoped", "browser-1")

    assert pending_path.read_text() == admin._encode_remote_browser_id("browser-1")
    assert not state_path.exists()


def test_remote_id_persistence_cleanup_cannot_mask_original_write_failure(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    fsync_calls = 0
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)

    def fail_fsync(_fd):
        nonlocal fsync_calls
        fsync_calls += 1
        raise OSError("write fsync failed" if fsync_calls == 1 else "cleanup fsync failed")

    monkeypatch.setattr(admin.os, "fsync", fail_fsync)

    with pytest.raises(OSError, match="write fsync failed"):
        admin._persist_remote_browser_id("scoped", "browser-1")

    assert not (tmp_path / "remote-id.pending").exists()


def test_ensure_daemon_self_heal_uses_durable_cleanup_for_cloud(monkeypatch, tmp_path):
    alive = iter([True, True])
    stopped = []
    lock_entries = []
    lock_active = False

    @contextmanager
    def non_reentrant_lock(name):
        nonlocal lock_active
        assert not lock_active, "ensure_daemon must not reacquire its lifecycle lock"
        lock_active = True
        lock_entries.append(name)
        try:
            yield
        finally:
            lock_active = False

    class Process:
        def poll(self):
            return None

    monkeypatch.setattr(admin, "daemon_alive", lambda _name=None: next(alive))
    monkeypatch.setattr(admin, "_remote_daemon_lifecycle_lock", non_reentrant_lock)
    monkeypatch.setattr(
        admin.ipc,
        "connect",
        lambda _name, timeout: (FakeSocket(response=b'{"error":"cdp disconnected"}\n'), None),
    )
    monkeypatch.setattr(admin, "daemon_browser_kind", lambda _name=None: "cloud")
    monkeypatch.setattr(admin, "_read_remote_browser_id", lambda _name: "browser-1")
    monkeypatch.setattr(
        admin,
        "_stop_remote_daemon_locked",
        lambda name: stopped.append(name),
    )
    monkeypatch.setattr(admin, "_restart_daemon_locked", lambda _name: pytest.fail("must clean cloud"))
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: tmp_path / "remote-id")
    monkeypatch.setattr(admin.ipc, "log_path", lambda _name: tmp_path / "daemon.log")
    monkeypatch.setattr(admin.subprocess, "Popen", lambda *args, **kwargs: Process())
    monkeypatch.setattr(admin.time, "sleep", lambda _seconds: None)

    admin.ensure_daemon(name="scoped", env={"BU_CDP_WS": "wss://cdp.example.test/ws"})

    assert stopped == ["scoped"]
    assert lock_entries == ["scoped"]


def test_dead_remote_daemon_stops_persisted_cloud_browser(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    write_remote_id(state_path, "browser-1")
    stopped = []
    restarted = []
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
    monkeypatch.setattr(
        admin,
        "_stop_cloud_browser",
        lambda browser_id, strict=False: stopped.append((browser_id, strict)) or True,
    )
    monkeypatch.setattr(
        admin,
        "_restart_daemon_locked",
        lambda name, require_clean=False: restarted.append((name, require_clean)),
    )

    admin.stop_remote_daemon("scoped")

    assert stopped == [("browser-1", True)]
    assert restarted == [("scoped", False)]
    assert not state_path.exists()


def test_remote_browser_recovery_promotes_valid_pending_state(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    pending_path = tmp_path / "remote-id.pending"
    write_remote_id(pending_path, "browser-1")
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)

    assert admin._read_remote_browser_id("scoped") == "browser-1"
    assert state_path.read_text() == admin._encode_remote_browser_id("browser-1")
    assert not pending_path.exists()


def test_remote_browser_recovery_rejects_truncated_pending_id(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    pending_path = tmp_path / "remote-id.pending"
    pending_path.write_text("browser-1")
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)

    with pytest.raises(RuntimeError, match="invalid pending remote browser recovery state"):
        admin._read_remote_browser_id("scoped")

    assert pending_path.read_text() == "browser-1"
    assert not state_path.exists()


def test_dead_remote_daemon_retains_recovery_state_when_stop_fails(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    write_remote_id(state_path, "browser-1")
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
    monkeypatch.setattr(
        admin,
        "_stop_cloud_browser",
        lambda _browser_id, strict=False: (_ for _ in ()).throw(RuntimeError("stop failed")),
    )

    with pytest.raises(RuntimeError, match="stop failed"):
        admin.stop_remote_daemon("scoped")

    assert admin._read_remote_browser_id("scoped") == "browser-1"


def test_local_chrome_mode_is_false_when_process_env_provides_remote_cdp(monkeypatch):
    monkeypatch.setenv("BU_CDP_WS", "ws://example.test/devtools/browser/1")

    assert not admin._is_local_chrome_mode()


def test_handshake_timeout_needs_chrome_remote_debugging_prompt():
    msg = "CDP WS handshake failed: timed out during opening handshake"

    assert admin._needs_chrome_remote_debugging_prompt(msg)


def test_handshake_403_needs_chrome_remote_debugging_prompt():
    msg = "CDP WS handshake failed: server rejected WebSocket connection: HTTP 403"

    assert admin._needs_chrome_remote_debugging_prompt(msg)


def test_stale_websocket_does_not_open_chrome_inspect():
    msg = "no close frame received or sent"

    assert not admin._needs_chrome_remote_debugging_prompt(msg)


def test_daemon_endpoint_names_discovers_valid_socket_names(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR", None)  # shared-tmpdir mode
    monkeypatch.setattr(admin.ipc, "_RUNTIME", tmp_path)
    (tmp_path / "bu-default.sock").touch()
    (tmp_path / "bu-remote_1.sock").touch()
    (tmp_path / "bu-invalid.name.sock").touch()
    (tmp_path / "not-bu-default.sock").touch()

    assert admin._daemon_endpoint_names() == ["default", "remote_1"]


def test_daemon_endpoint_names_with_bh_runtime_dir_returns_local_name_when_sock_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR_SHARED", False)
    monkeypatch.setattr(admin.ipc, "_RUNTIME", tmp_path)
    monkeypatch.setattr(admin, "NAME", "session-xyz")
    (tmp_path / "bu.sock").touch()

    assert admin._daemon_endpoint_names() == ["session-xyz"]


def test_daemon_endpoint_names_with_bh_runtime_dir_returns_empty_when_sock_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR_SHARED", False)
    monkeypatch.setattr(admin.ipc, "_RUNTIME", tmp_path)
    monkeypatch.setattr(admin, "NAME", "session-xyz")

    assert admin._daemon_endpoint_names() == []


def test_daemon_endpoint_names_with_shared_bh_runtime_dir_discovers_named_sockets(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(admin.ipc, "BH_RUNTIME_DIR_SHARED", True)
    monkeypatch.setattr(admin.ipc, "_RUNTIME", tmp_path)
    (tmp_path / "bu-default.sock").touch()
    (tmp_path / "bu-work.sock").touch()
    (tmp_path / "bu-invalid.name.sock").touch()
    (tmp_path / "bu.sock").touch()  # stale isolated-runtime endpoint

    assert admin._daemon_endpoint_names() == ["default", "work"]


def test_active_browser_connections_counts_only_healthy_daemons(monkeypatch):
    monkeypatch.setattr(admin, "_daemon_endpoint_names", lambda: ["default", "stale", "remote"])

    def fake_connect(name, timeout=1.0):
        if name == "stale":
            raise ConnectionRefusedError()
        if name == "remote":
            return FakeSocket(b'{"error":"no close frame received or sent"}\n'), None
        return FakeSocket(), None

    monkeypatch.setattr(admin.ipc, "connect", fake_connect)

    assert admin.active_browser_connections() == 1


def test_daemon_browser_ready_checks_the_selected_daemon(monkeypatch):
    calls = []
    monkeypatch.setattr(
        admin,
        "_daemon_browser_connection",
        lambda name: calls.append(name) or {"name": name, "page": None},
    )

    assert admin.daemon_browser_ready("work")
    assert calls == ["work"]


def test_active_browser_connections_skips_daemons_reporting_cdp_disconnected(monkeypatch):
    monkeypatch.setattr(admin, "_daemon_endpoint_names", lambda: ["default", "stale"])

    def fake_connect(name, timeout=1.0):
        if name == "stale":
            return FakeSocket(b'{"error":"cdp_disconnected"}\n'), None
        return FakeSocket(), None

    monkeypatch.setattr(admin.ipc, "connect", fake_connect)

    assert admin.active_browser_connections() == 1


def test_browser_connections_returns_attached_page(monkeypatch):
    monkeypatch.setattr(admin, "_daemon_endpoint_names", lambda: ["default"])
    response = (
        b'{"target_id":"target-1","session_id":"session-1",'
        b'"page":{"targetId":"target-1","title":"Cat - Wikipedia","url":"https://en.wikipedia.org/wiki/Cat"}}\n'
    )
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout=1.0: (FakeSocket(response), None))

    assert admin.browser_connections() == [
        {
            "name": "default",
            "page": {"title": "Cat - Wikipedia", "url": "https://en.wikipedia.org/wiki/Cat"},
        }
    ]


def test_chrome_running_detects_helium_on_linux(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "subprocess.check_output",
        lambda *args, **kwargs: "systemd\nhelium\nxdg-desktop-portal\n",
    )

    assert admin._chrome_running()


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/snap/chromium/1234/usr/lib/chromium-browser/chromium-browser", True),
        ("/SNAP/foo", True),
        ("/usr/bin/google-chrome-stable", False),
        ("", False),
    ],
)
def test_is_snap_browser(path, expected):
    assert admin._is_snap_browser(path) == expected


def test_doctor_probe_preserves_snap_bin_env_symlink(monkeypatch, tmp_path):
    target = tmp_path / "usr" / "bin" / "snap"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/sh\n")
    snap_bin = tmp_path / "snap" / "bin"
    snap_bin.mkdir(parents=True)
    chromium = snap_bin / "chromium"
    chromium.symlink_to(target)

    monkeypatch.setenv("BH_CHROME_PATH", str(chromium))
    monkeypatch.delenv("CHROME_PATH", raising=False)

    name, path = admin._doctor_probe_chrome_binary_for_snap()

    assert name == "chromium"
    assert path == str(chromium)
    assert admin._is_snap_browser(path)


def test_doctor_probe_preserves_snap_bin_path_symlink(monkeypatch, tmp_path):
    target = tmp_path / "usr" / "bin" / "snap"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/sh\n")
    snap_bin = tmp_path / "snap" / "bin"
    snap_bin.mkdir(parents=True)
    chromium = snap_bin / "chromium"
    chromium.symlink_to(target)

    monkeypatch.delenv("BH_CHROME_PATH", raising=False)
    monkeypatch.delenv("CHROME_PATH", raising=False)

    def fake_which(cmd):
        return str(chromium) if cmd == "chromium" else None

    monkeypatch.setattr("shutil.which", fake_which)

    name, path = admin._doctor_probe_chrome_binary_for_snap()

    assert name == "chromium"
    assert path == str(chromium)
    assert admin._is_snap_browser(path)


def test_run_doctor_prints_snap_detect_on_linux_when_probe_is_snap(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: False)
    monkeypatch.setattr(admin, "daemon_alive", lambda: False)
    monkeypatch.setattr(admin, "browser_connections", lambda: [])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_doctor_probe_chrome_binary_for_snap", lambda: ("chromium", "/snap/chromium/1/usr/bin/chromium"))
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 1

    out = capsys.readouterr().out
    assert "[snap-detect]" in out
    assert "Browser: chromium (snap)" in out
    assert "Snap confinement prevents CDP binding" in out
    assert "docs/snap-linux-headless.md" in out


def test_run_doctor_skips_snap_detect_on_non_linux(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda: True)
    monkeypatch.setattr(admin, "browser_connections", lambda: [])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_doctor_probe_chrome_binary_for_snap", lambda: ("chromium", "/snap/chromium/1/usr/bin/chromium"))
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 0

    out = capsys.readouterr().out
    assert "[snap-detect]" not in out


def test_run_doctor_reports_bad_stored_cloud_auth_without_crashing(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda: True)
    monkeypatch.setattr(admin, "browser_connections", lambda: [])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_doctor_probe_chrome_binary_for_snap", lambda: (None, None))
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(admin.auth, "auth_status", lambda: (_ for _ in ()).throw(admin.auth.AuthError("auth file is not valid JSON")))

    assert admin.run_doctor() == 0

    out = capsys.readouterr().out
    assert "Browser Use cloud auth" in out
    assert "auth file is not valid JSON" in out


def test_run_doctor_fix_snap_prints_steps(capsys):
    assert admin.run_doctor_fix_snap() == 0
    out = capsys.readouterr().out
    assert "browser-harness doctor --fix-snap" in out
    assert "BH_CHROME_PATH" in out
    assert "google-chrome-stable_current_amd64.deb" in out
    assert "browser-harness --doctor" in out


def test_run_doctor_prints_active_browser_connections_and_active_pages(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda: True)
    monkeypatch.setattr(admin, "browser_connections", lambda: [
        {
            "name": "default",
            "page": {"title": "Example", "url": "https://example.test"},
        },
        {
            "name": "cats",
            "page": {"title": "Cat - Wikipedia", "url": "https://en.wikipedia.org/wiki/Cat"},
        },
    ])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 0

    out = capsys.readouterr().out
    assert "[ok  ] active browser connections — 2" in out
    assert "        default — active page: Example — https://example.test" in out
    assert "        cats — active page: Cat - Wikipedia — https://en.wikipedia.org/wiki/Cat" in out


def test_doctor_page_output_truncates_long_text(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda: True)
    monkeypatch.setattr(admin, "DOCTOR_TEXT_LIMIT", 20)
    monkeypatch.setattr(admin, "browser_connections", lambda: [
        {
            "name": "default",
            "page": {"title": "A very long page title", "url": "https://example.test/very/long/path"},
        }
    ])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 0

    out = capsys.readouterr().out
    assert "A very long page ..." in out
    assert "https://example.t..." in out


def test_start_remote_daemon_stops_created_browser_when_daemon_start_fails(monkeypatch, tmp_path):
    calls = []
    browser = {"id": "browser-123", "cdpUrl": "http://127.0.0.1:9333", "liveUrl": "https://live.example"}

    def fake_browser_use(path, method, body=None):
        calls.append((path, method, body))
        if (path, method) == ("/browsers", "POST"):
            return browser
        if (path, method) == ("/browsers/browser-123", "PATCH"):
            return {}
        raise AssertionError((path, method, body))

    monkeypatch.setattr(admin, "daemon_alive", lambda name: False)
    monkeypatch.setattr(admin.uuid, "uuid4", lambda: "browser-123")
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda url: "ws://example.test/devtools/browser/1")
    monkeypatch.setattr(admin, "_ensure_daemon_locked", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: tmp_path / "remote-id")

    with pytest.raises(RuntimeError, match="boom"):
        admin.start_remote_daemon()

    assert calls == [
        ("/browsers", "POST", {"clientSessionId": "browser-123"}),
        ("/browsers/browser-123", "PATCH", {"action": "stop"}),
    ]
    assert not (tmp_path / "remote-id").exists()


def test_start_remote_daemon_stops_created_browser_when_recovery_state_cannot_persist(
    monkeypatch, tmp_path
):
    calls = []
    browser = {"id": "browser-123", "cdpUrl": "http://127.0.0.1:9333"}

    def fake_browser_use(path, method, body=None):
        calls.append((path, method, body))
        if (path, method) == ("/browsers", "POST"):
            return browser
        if (path, method) == ("/browsers/browser-123", "PATCH"):
            return {}
        raise AssertionError((path, method, body))

    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
    monkeypatch.setattr(admin.uuid, "uuid4", lambda: "browser-123")
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: tmp_path / "remote-id")
    monkeypatch.setattr(
        admin,
        "_persist_remote_browser_recovery",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr(
        admin,
        "_ensure_daemon_locked",
        lambda **_kwargs: pytest.fail("daemon must not start without recovery state"),
    )
    monkeypatch.setattr(admin, "_clear_remote_browser_id", lambda _name: None)

    with pytest.raises(OSError, match="disk full"):
        admin.start_remote_daemon("scoped")

    assert calls == []


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
def test_start_remote_daemon_stops_created_browser_when_daemon_start_is_interrupted(monkeypatch, exc_type, tmp_path):
    calls = []
    browser = {"id": "browser-123", "cdpUrl": "http://127.0.0.1:9333", "liveUrl": "https://live.example"}

    def fake_browser_use(path, method, body=None):
        calls.append((path, method, body))
        if (path, method) == ("/browsers", "POST"):
            return browser
        if (path, method) == ("/browsers/browser-123", "PATCH"):
            return {}
        raise AssertionError((path, method, body))

    monkeypatch.setattr(admin, "daemon_alive", lambda name: False)
    monkeypatch.setattr(admin.uuid, "uuid4", lambda: "browser-123")
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda url: "ws://example.test/devtools/browser/1")
    monkeypatch.setattr(admin, "_ensure_daemon_locked", lambda **kwargs: (_ for _ in ()).throw(exc_type()))
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: tmp_path / "remote-id")

    with pytest.raises(exc_type):
        admin.start_remote_daemon()

    assert calls == [
        ("/browsers", "POST", {"clientSessionId": "browser-123"}),
        ("/browsers/browser-123", "PATCH", {"action": "stop"}),
    ]
    assert not (tmp_path / "remote-id").exists()


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
def test_stop_cloud_browser_swallows_baseexception_from_stop_request(monkeypatch, exc_type):
    monkeypatch.setattr(admin, "_browser_use", lambda *args, **kwargs: (_ for _ in ()).throw(exc_type()))

    admin._stop_cloud_browser("browser-123")

def test_start_remote_daemon_does_not_stop_created_browser_on_success(monkeypatch, tmp_path):
    calls = []
    browser = {"id": "server-browser-456", "cdpUrl": "http://127.0.0.1:9333", "liveUrl": "https://live.example"}

    def fake_browser_use(path, method, body=None):
        calls.append((path, method, body))
        if (path, method) == ("/browsers", "POST"):
            assert admin._read_remote_browser_recovery("remote") == {
                "browser_id": None,
                "client_session_id": "browser-123",
            }
            return browser
        raise AssertionError((path, method, body))

    monkeypatch.setattr(admin, "daemon_alive", lambda name: False)
    monkeypatch.setattr(admin.uuid, "uuid4", lambda: "browser-123")
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda url: "ws://example.test/devtools/browser/1")
    monkeypatch.setattr(admin, "_ensure_daemon_locked", lambda **kwargs: None)
    monkeypatch.setattr(admin, "_show_live_url", lambda url: None)
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: tmp_path / "remote-id")

    assert admin.start_remote_daemon() == browser
    assert calls == [
        ("/browsers", "POST", {"clientSessionId": "browser-123"}),
    ]
    assert admin._read_remote_browser_recovery("remote") == {
        "browser_id": "server-browser-456",
        "client_session_id": "browser-123",
    }


def test_start_remote_daemon_rejects_client_session_id_override(monkeypatch):
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
    monkeypatch.setattr(
        admin,
        "_browser_use",
        lambda *_args, **_kwargs: pytest.fail("invalid caller input must not reach Cloud"),
    )

    with pytest.raises(ValueError, match="managed internally"):
        admin.start_remote_daemon(clientSessionId="caller-selected")


def test_crash_recovery_resolves_client_key_before_stopping_server_browser(monkeypatch, tmp_path):
    calls = []
    state_path = tmp_path / "remote-id"
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    admin._persist_remote_browser_recovery("remote", client_session_id="client-key-123")

    def browser_use(path, method, body=None):
        calls.append((path, method, body))
        if (path, method) == ("/browsers/client-session/client-key-123", "GET"):
            return {"id": "server-browser-456"}
        if (path, method) == ("/browsers/server-browser-456", "PATCH"):
            return {}
        raise AssertionError((path, method, body))

    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
    monkeypatch.setattr(admin, "_browser_use", browser_use)
    monkeypatch.setattr(admin, "_restart_daemon_locked", lambda _name: None)

    admin.stop_remote_daemon("remote")

    assert calls == [
        ("/browsers/client-session/client-key-123", "GET", None),
        ("/browsers/server-browser-456", "PATCH", {"action": "stop"}),
    ]
    assert not state_path.exists()


def test_crash_recovery_clears_key_when_cloud_never_created_a_session(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    admin._persist_remote_browser_recovery("remote", client_session_id="client-key-123")

    def browser_use(path, method, body=None):
        assert (path, method, body) == (
            "/browsers/client-session/client-key-123", "GET", None
        )
        raise urllib.error.HTTPError(path, 404, "not found", None, None)

    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
    monkeypatch.setattr(admin, "_browser_use", browser_use)
    monkeypatch.setattr(admin, "_restart_daemon_locked", lambda _name: None)

    admin.stop_remote_daemon("remote")

    assert not state_path.exists()


def test_start_remote_daemon_opens_live_view_by_default(monkeypatch):
    browser = {"id": "browser-123", "liveUrl": "https://live.example"}
    shown = []
    monkeypatch.delenv("BH_OPEN_LIVE_URL", raising=False)
    monkeypatch.setattr(admin, "_start_remote_daemon_locked", lambda *_args, **_kwargs: browser)
    monkeypatch.setattr(admin, "_show_live_url", shown.append)

    assert admin.start_remote_daemon("scoped") == browser
    assert shown == ["https://live.example"]


@pytest.mark.parametrize("value", ["0", "false", "NO", " off "])
def test_start_remote_daemon_can_suppress_live_view_for_orchestrators(monkeypatch, value):
    browser = {"id": "browser-123", "liveUrl": "https://live.example"}
    monkeypatch.setenv("BH_OPEN_LIVE_URL", value)
    monkeypatch.setattr(admin, "_start_remote_daemon_locked", lambda *_args, **_kwargs: browser)
    monkeypatch.setattr(
        admin,
        "_show_live_url",
        lambda _url: pytest.fail("suppressed live view must not be printed or opened"),
    )

    assert admin.start_remote_daemon("scoped") == browser


def test_concurrent_same_name_remote_starts_provision_once(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    daemon_started = threading.Event()
    first_provisioned = threading.Event()
    release_first = threading.Event()
    provisioned = []
    results = []
    errors = []
    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(admin.uuid, "uuid4", lambda: "browser-1")
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: daemon_started.is_set())

    def browser_use(path, method, body=None):
        assert (path, method) == ("/browsers", "POST")
        provisioned.append(body)
        first_provisioned.set()
        assert release_first.wait(timeout=2)
        return {"id": "browser-1", "cdpUrl": "https://cdp.example.test"}

    monkeypatch.setattr(admin, "_browser_use", browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda _url: "wss://cdp.example.test/ws")
    monkeypatch.setattr(admin, "_ensure_daemon_locked", lambda **_kwargs: daemon_started.set())
    monkeypatch.setattr(admin, "_show_live_url", lambda _url: None)

    def start():
        try:
            results.append(admin.start_remote_daemon("scoped"))
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=start)
    second = threading.Thread(target=start)
    first.start()
    assert first_provisioned.wait(timeout=2)
    second.start()
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive() and not second.is_alive()
    assert len(provisioned) == 1
    assert [result["id"] for result in results] == ["browser-1"]
    assert len(errors) == 1
    assert "already alive" in str(errors[0])


def test_remote_start_serializes_against_ordinary_ensure(monkeypatch, tmp_path):
    state_path = tmp_path / "remote-id"
    daemon_started = threading.Event()
    cloud_post_entered = threading.Event()
    ordinary_lock_attempted = threading.Event()
    release_cloud_post = threading.Event()
    spawn_envs = []
    results = []
    errors = []
    ordinary_thread = None
    real_lifecycle_lock = admin._remote_daemon_lifecycle_lock

    class Process:
        def poll(self):
            return None

    @contextmanager
    def observed_lifecycle_lock(name):
        if threading.current_thread() is ordinary_thread:
            ordinary_lock_attempted.set()
        with real_lifecycle_lock(name):
            yield

    def browser_use(path, method, body=None):
        assert (path, method) == ("/browsers", "POST")
        cloud_post_entered.set()
        assert release_cloud_post.wait(timeout=2)
        return {"id": "browser-1", "cdpUrl": "https://cdp.example.test"}

    def popen(*_args, **kwargs):
        spawn_envs.append(kwargs["env"])
        daemon_started.set()
        return Process()

    def connect(*_args, **_kwargs):
        return FakeSocket(response=b'{"result":{"targetInfos":[]}}\n'), None

    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(admin.uuid, "uuid4", lambda: "browser-1")
    monkeypatch.setattr(admin.ipc, "log_path", lambda _name: tmp_path / "daemon.log")
    monkeypatch.setattr(admin, "_remote_daemon_lifecycle_lock", observed_lifecycle_lock)
    monkeypatch.setattr(admin, "daemon_alive", lambda _name=None: daemon_started.is_set())
    monkeypatch.setattr(admin, "_browser_use", browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda _url: "wss://cdp.example.test/ws")
    monkeypatch.setattr(admin, "_show_live_url", lambda _url: None)
    monkeypatch.setattr(admin.subprocess, "Popen", popen)
    monkeypatch.setattr(admin.ipc, "connect", connect)

    def start_remote():
        try:
            results.append(admin.start_remote_daemon("scoped"))
        except BaseException as exc:
            errors.append(exc)

    def ensure_ordinary():
        try:
            admin.ensure_daemon(name="scoped")
        except BaseException as exc:
            errors.append(exc)

    remote_thread = threading.Thread(target=start_remote, daemon=True)
    ordinary_thread = threading.Thread(target=ensure_ordinary, daemon=True)
    remote_thread.start()
    assert cloud_post_entered.wait(timeout=2)
    ordinary_thread.start()
    assert ordinary_lock_attempted.wait(timeout=2)
    assert not daemon_started.is_set()
    release_cloud_post.set()
    remote_thread.join(timeout=2)
    ordinary_thread.join(timeout=2)

    assert not remote_thread.is_alive() and not ordinary_thread.is_alive()
    assert errors == []
    assert [result["id"] for result in results] == ["browser-1"]
    assert len(spawn_envs) == 1
    assert spawn_envs[0]["BU_CDP_WS"] == "wss://cdp.example.test/ws"
    assert spawn_envs[0]["BU_BROWSER_ID"] == "browser-1"
    assert admin._read_remote_browser_id("scoped") == "browser-1"


def test_reload_serializes_against_remote_provision(monkeypatch, tmp_path):
    from browser_harness import run

    state_path = tmp_path / "remote-id"
    cloud_post_entered = threading.Event()
    release_cloud_post = threading.Event()
    reload_lock_attempted = threading.Event()
    daemon_started = threading.Event()
    restart_observations = []
    errors = []
    reload_thread = None
    real_lifecycle_lock = admin._remote_daemon_lifecycle_lock

    @contextmanager
    def observed_lifecycle_lock(name):
        if threading.current_thread() is reload_thread:
            reload_lock_attempted.set()
        with real_lifecycle_lock(name):
            yield

    def browser_use(path, method, body=None):
        assert (path, method) == ("/browsers", "POST")
        cloud_post_entered.set()
        assert release_cloud_post.wait(timeout=2)
        return {"id": "browser-1", "cdpUrl": "https://cdp.example.test"}

    monkeypatch.setattr(admin.ipc, "remote_id_path", lambda _name: state_path)
    monkeypatch.setattr(admin.uuid, "uuid4", lambda: "browser-1")
    monkeypatch.setattr(admin, "_remote_daemon_lifecycle_lock", observed_lifecycle_lock)
    monkeypatch.setattr(admin, "daemon_alive", lambda _name=None: daemon_started.is_set())
    monkeypatch.setattr(admin, "_browser_use", browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda _url: "wss://cdp.example.test/ws")
    monkeypatch.setattr(admin, "_ensure_daemon_locked", lambda **_kwargs: daemon_started.set())
    monkeypatch.setattr(admin, "_show_live_url", lambda _url: None)
    monkeypatch.setattr(
        admin,
        "_restart_daemon_locked",
        lambda name, require_clean=False: restart_observations.append(
            (name, daemon_started.is_set(), require_clean)
        ),
    )

    def start_remote():
        try:
            admin.start_remote_daemon(admin.NAME)
        except BaseException as exc:
            errors.append(exc)

    def reload():
        try:
            # This is the exact imported function used by `browser-harness --reload`.
            run.restart_daemon()
        except BaseException as exc:
            errors.append(exc)

    provision_thread = threading.Thread(target=start_remote, daemon=True)
    reload_thread = threading.Thread(target=reload, daemon=True)
    provision_thread.start()
    assert cloud_post_entered.wait(timeout=2)
    reload_thread.start()
    assert reload_lock_attempted.wait(timeout=2)
    assert restart_observations == []
    release_cloud_post.set()
    provision_thread.join(timeout=2)
    reload_thread.join(timeout=2)

    assert not provision_thread.is_alive() and not reload_thread.is_alive()
    assert errors == []
    assert restart_observations == [(admin.NAME, True, False)]


def test_remote_stop_uses_locked_restart_without_reacquiring_lifecycle_lock(monkeypatch):
    active = False
    lock_entries = []
    restart_calls = []

    @contextmanager
    def non_reentrant_lifecycle_lock(name):
        nonlocal active
        assert not active, "already-locked callers must use _restart_daemon_locked"
        active = True
        lock_entries.append(name)
        try:
            yield
        finally:
            active = False

    monkeypatch.setattr(admin, "_remote_daemon_lifecycle_lock", non_reentrant_lifecycle_lock)
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
    monkeypatch.setattr(admin, "_read_remote_browser_id", lambda _name: None)
    monkeypatch.setattr(admin, "_clear_remote_browser_id", lambda _name: None)
    monkeypatch.setattr(
        admin,
        "_restart_daemon_locked",
        lambda name, require_clean=False: restart_calls.append((name, require_clean)),
    )

    admin.stop_remote_daemon("scoped")

    assert lock_entries == ["scoped"]
    assert restart_calls == [("scoped", False)]


# --- restart_daemon: PID-reuse safety ---

def test_restart_daemon_does_not_signal_when_daemon_unreachable(monkeypatch, tmp_path):
    """If ipc.identify() returns None (daemon gone), restart_daemon must NOT
    fall back to reading the pid file and SIGTERMing whatever owns that PID —
    that's the PID-reuse hazard. It should only clean up files."""
    pid_path = tmp_path / "default.pid"
    # A pid file with a PID that, if signaled, would hit an unrelated process.
    # The whole point is that we don't read or trust this number.
    pid_path.write_text("99999")

    kill_calls = []
    monkeypatch.setattr(admin.os, "kill", lambda pid, sig: kill_calls.append((pid, sig)))
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: None)
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: False)
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)

    # Should not raise, should not signal, should still clean up the pid file.
    admin.restart_daemon("default")

    assert kill_calls == [], (
        f"restart_daemon SIGTERM'd a PID despite identify() returning None — "
        f"this is the PID-reuse hazard the function is meant to avoid. Calls: {kill_calls}"
    )
    assert not pid_path.exists(), "stale pid file should be cleaned up"


def test_restart_daemon_signals_pid_returned_by_identify_not_pid_file(monkeypatch, tmp_path):
    """The PID we signal must come from the live daemon's self-report, never
    from the pid file. If a stale pid file disagrees, the live daemon's PID wins."""
    import signal

    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")  # bogus stale value — must be ignored

    live_pid = 4242

    kill_calls = []
    def fake_kill(pid, sig):
        kill_calls.append((pid, sig))
        # First os.kill(pid, 0) probe: report process is gone so we exit the loop
        # without escalating. We just want to see WHICH pid was probed.
        if sig == 0:
            raise ProcessLookupError

    class FakeIPC:
        def __init__(self):
            self.shutdown_sent = False
        def identify(self, name, timeout=5.0):
            return live_pid
        def connect(self, name, timeout):
            return ("conn", "tok")
        def request(self, conn, tok, msg):
            if msg.get("meta") == "shutdown":
                self.shutdown_sent = True
            return {"ok": True}
        def pid_path(self, name):
            return pid_path
        def cleanup_endpoint(self, name):
            pass

    fake = FakeIPC()
    monkeypatch.setattr(admin.os, "kill", fake_kill)
    monkeypatch.setattr(admin.ipc, "identify", fake.identify)
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)
    monkeypatch.setattr(admin.ipc, "connect", fake.connect)
    monkeypatch.setattr(admin.ipc, "request", fake.request)
    monkeypatch.setattr(admin.ipc, "pid_path", fake.pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", fake.cleanup_endpoint)

    admin.restart_daemon("default")

    assert fake.shutdown_sent, "expected shutdown IPC to be sent"
    assert kill_calls, "expected at least one os.kill probe"
    pids_signaled = {pid for pid, _ in kill_calls}
    assert pids_signaled == {live_pid}, (
        f"restart_daemon must only signal the PID returned by identify(); "
        f"signaled pids: {pids_signaled}, expected {{{live_pid}}} (and NOT 99999)"
    )
    assert not pid_path.exists()


def test_restart_daemon_sends_shutdown_to_pre_upgrade_daemon_without_pid_in_ping(monkeypatch, tmp_path):
    """Backward compat: a pre-upgrade daemon's ping reply has {pong:True} but
    no `pid` field, so identify() returns None. The shutdown IPC must STILL be
    sent (so the daemon exits cleanly), but no os.kill happens (we have no
    verified PID to safely signal)."""
    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")  # bogus stale value

    kill_calls = []
    shutdown_calls = []

    def fake_request(conn, tok, msg):
        if msg.get("meta") == "shutdown":
            shutdown_calls.append(msg)
        return {"ok": True}

    monkeypatch.setattr(admin.os, "kill", lambda pid, sig: kill_calls.append((pid, sig)))
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: None)
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)  # old daemon: alive but no pid
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout: ("conn", "tok"))
    monkeypatch.setattr(admin.ipc, "request", fake_request)
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)

    admin.restart_daemon("default")

    assert shutdown_calls, (
        "restart_daemon must send shutdown IPC to a pre-upgrade daemon even "
        "when identify() can't return a PID — otherwise upgrades orphan the "
        "old daemon while deleting its socket and pid file."
    )
    assert kill_calls == [], (
        f"no os.kill should fire when we don't have a verified PID, "
        f"but got: {kill_calls}"
    )
    assert not pid_path.exists()


def test_restart_daemon_skips_sigterm_if_pid_was_reused_during_wait(monkeypatch, tmp_path):
    """A second identify() runs immediately before the SIGTERM. If the daemon
    exited and the PID was reused mid-wait, identify() will return None (or a
    different PID) and we must NOT signal — that's the PID-reuse race during
    the 15s wait window."""
    import signal

    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")
    live_pid = 4242

    kill_calls = []

    def fake_kill(pid, sig):
        kill_calls.append((pid, sig))
        # All os.kill(pid, 0) probes succeed → loop exhausts → reaches the
        # SIGTERM branch. (We're simulating a "wedged" daemon that the wait
        # loop can't tell apart from a daemon whose PID got reused.)

    # First identify() call (top of restart_daemon) returns the live PID.
    # Second identify() call (right before SIGTERM) returns None — simulating
    # the daemon having exited and its PID having been reused by an unrelated
    # process. The function must NOT escalate to SIGTERM in that state.
    identify_responses = iter([live_pid, None])
    monkeypatch.setattr(admin.os, "kill", fake_kill)
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: next(identify_responses))
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout: ("conn", "tok"))
    monkeypatch.setattr(admin.ipc, "request", lambda conn, tok, msg: {"ok": True})
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)
    # Speed up the wait loop so the test finishes quickly. The loop polls 75
    # times at 0.2s = 15s; with sleep neutralized it runs in microseconds.
    monkeypatch.setattr(admin.time, "sleep", lambda _s: None)

    admin.restart_daemon("default")

    sigterms = [(pid, sig) for pid, sig in kill_calls if sig == signal.SIGTERM]
    assert sigterms == [], (
        f"restart_daemon issued SIGTERM despite the re-verify identify() "
        f"returning None (PID was reused during the 15s wait). Calls: {kill_calls}"
    )
    assert not pid_path.exists()


def test_restart_daemon_sigterms_via_start_time_fingerprint_when_socket_gone(monkeypatch, tmp_path):
    """Slow-shutdown recovery: the daemon's serve() tears down the IPC socket
    BEFORE the process exits (the daemon then runs slow cleanup like remote
    `stop` PATCH calls that can hang). In that window, identify() returns None
    even though the process is still our daemon. SIGTERM must still fire when
    the PID's start-time fingerprint hasn't changed since we first identified
    it — that's strong evidence of "same process, just slow to exit."
    """
    import signal

    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")
    live_pid = 4242

    kill_calls = []

    def fake_kill(pid, sig):
        kill_calls.append((pid, sig))
        # All os.kill(pid, 0) probes succeed; loop exhausts → SIGTERM gate runs.

    # First identify() returns live_pid. Second identify() returns None — the
    # daemon has torn down its IPC during shutdown but the process is still
    # finishing up cleanup work, so the start-time fingerprint is unchanged.
    identify_responses = iter([live_pid, None])
    # Both _process_start_time() calls return the same fingerprint, signaling
    # "still the same process." This is the legitimate-slow-shutdown case.
    monkeypatch.setattr(admin, "_process_start_time", lambda pid: "STARTED_AT_X")
    monkeypatch.setattr(admin.os, "kill", fake_kill)
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: next(identify_responses))
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout: ("conn", "tok"))
    monkeypatch.setattr(admin.ipc, "request", lambda conn, tok, msg: {"ok": True})
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)
    monkeypatch.setattr(admin.time, "sleep", lambda _s: None)

    admin.restart_daemon("default")

    sigterms = [(pid, sig) for pid, sig in kill_calls if sig == signal.SIGTERM]
    assert sigterms == [(live_pid, signal.SIGTERM)], (
        f"slow-shutdown daemon (identify=None but unchanged start-time) must "
        f"still receive SIGTERM. signal calls: {kill_calls}"
    )


def test_restart_daemon_skips_sigterm_when_start_time_changed_during_wait(monkeypatch, tmp_path):
    """If the start-time fingerprint of the original PID has CHANGED, the PID
    was reused by another process. Even though identify() also returns None,
    we must skip SIGTERM — start-time mismatch is the signal that protects
    against killing an unrelated reused-PID process."""
    import signal

    pid_path = tmp_path / "default.pid"
    pid_path.write_text("99999")
    live_pid = 4242

    kill_calls = []
    monkeypatch.setattr(admin.os, "kill", lambda pid, sig: kill_calls.append((pid, sig)))

    identify_responses = iter([live_pid, None])
    # First start-time read at top of restart_daemon: "ORIGINAL".
    # Second start-time read in the safety gate: "DIFFERENT" — proof of reuse.
    start_time_responses = iter(["ORIGINAL", "DIFFERENT"])
    monkeypatch.setattr(admin, "_process_start_time", lambda pid: next(start_time_responses))
    monkeypatch.setattr(admin.ipc, "identify", lambda name, timeout=5.0: next(identify_responses))
    monkeypatch.setattr(admin.ipc, "ping", lambda name, timeout=1.0: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout: ("conn", "tok"))
    monkeypatch.setattr(admin.ipc, "request", lambda conn, tok, msg: {"ok": True})
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: pid_path)
    monkeypatch.setattr(admin.ipc, "cleanup_endpoint", lambda name: None)
    monkeypatch.setattr(admin.time, "sleep", lambda _s: None)

    admin.restart_daemon("default")

    sigterms = [(pid, sig) for pid, sig in kill_calls if sig == signal.SIGTERM]
    assert sigterms == [], (
        f"start-time mismatch indicates PID reuse — restart_daemon must NOT "
        f"SIGTERM. signal calls: {kill_calls}"
    )


# --- _process_start_time helper ---

def test_process_start_time_returns_stable_fingerprint_for_self():
    """The start-time of the current process should be readable on Linux,
    macOS, and Windows, and stable across two reads."""
    import os as _os, sys
    if sys.platform.startswith("linux") or sys.platform == "darwin" or sys.platform == "win32":
        pid = _os.getpid()
        first = admin._process_start_time(pid)
        second = admin._process_start_time(pid)
        assert first is not None, "expected a fingerprint for the current PID"
        assert first == second, (
            f"two reads of the same PID should return the same fingerprint; "
            f"got {first!r} vs {second!r}"
        )


def test_process_start_time_returns_none_for_invalid_pid():
    """Bad inputs (None, 0, negatives, non-int) and PIDs with no live process
    must return None rather than raising."""
    for bad in (None, 0, -1, -42, "not-an-int", 1.5, True, False):
        assert admin._process_start_time(bad) is None, (
            f"expected None for invalid pid {bad!r}"
        )
    # 2**31 - 1 is the largest pid_t; in practice no live process at that PID.
    assert admin._process_start_time((1 << 31) - 1) is None
