import json
import os
import signal
import time
import subprocess
from pathlib import Path

import pytest

from browser_harness import admin


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


class FakeProcess:
    def __init__(self, pid=123, returncode=None):
        self.pid = pid
        self.returncode = returncode
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True


def test_cleanup_unattached_browser_launch_stops_posix_process_group(monkeypatch):
    process = FakeProcess()
    killed = []
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr("browser_harness.daemon._devtools_port_live", lambda _profile: False)
    monkeypatch.setattr(admin.os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    admin._cleanup_unattached_browser_launch((process, Path("/profile")))

    assert killed == [(123, signal.SIGTERM)]


def test_cleanup_unattached_browser_launch_keeps_cdp_browser(monkeypatch):
    process = FakeProcess()
    monkeypatch.setattr("browser_harness.daemon._devtools_port_live", lambda _profile: True)
    monkeypatch.setattr(admin.os, "killpg", lambda _pid, _sig: pytest.fail("must keep the attached browser"))

    admin._cleanup_unattached_browser_launch((process, Path("/profile")))


def test_cleanup_unattached_browser_launch_ignores_unowned_launch(monkeypatch):
    monkeypatch.setattr(
        "browser_harness.daemon._devtools_port_live",
        lambda _profile: pytest.fail("must not probe an unowned launch"),
    )

    admin._cleanup_unattached_browser_launch((None, Path("/profile")))


@pytest.mark.parametrize("env_key", ["BH_CHROME_PATH", "CHROME_PATH"])
def test_explicit_chrome_path_retains_matching_profile_on_linux(monkeypatch, tmp_path, env_key):
    binary = tmp_path / "google-chrome-stable"
    binary.touch()
    profile = tmp_path / ".config" / "google-chrome"
    (profile / "Default").mkdir(parents=True)
    (profile / "Local State").write_text('{}')
    process = FakeProcess()

    other_key = "CHROME_PATH" if env_key == "BH_CHROME_PATH" else "BH_CHROME_PATH"
    monkeypatch.setenv(env_key, str(binary))
    monkeypatch.delenv(other_key, raising=False)
    monkeypatch.setattr("browser_harness.daemon.PROFILES", [profile])
    monkeypatch.setattr("browser_harness.daemon.remote_debugging_toggle_profiles", lambda: [profile])
    monkeypatch.setattr("browser_harness.daemon._devtools_port_live", lambda _profile: False)
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: process)
    killed = []
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    launch = admin._launch_browser()
    assert launch == (process, profile)

    admin._cleanup_unattached_browser_launch(launch)
    assert killed == [(process.pid, signal.SIGTERM)]


@pytest.mark.parametrize("system", ["Darwin", "Windows"])
def test_explicit_chrome_path_remains_unowned_without_platform_cleanup(monkeypatch, tmp_path, system):
    binary = tmp_path / ("chrome.exe" if system == "Windows" else "Google Chrome")
    binary.touch()
    profile = tmp_path / ".config" / "google-chrome"
    (profile / "Default").mkdir(parents=True)
    (profile / "Local State").write_text('{}')
    process = FakeProcess()

    monkeypatch.setenv("BH_CHROME_PATH", str(binary))
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr("browser_harness.daemon.PROFILES", [profile])
    monkeypatch.setattr("browser_harness.daemon.remote_debugging_toggle_profiles", lambda: [profile])
    monkeypatch.setattr("platform.system", lambda: system)
    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(admin.os, "killpg", lambda *_args: pytest.fail("must not terminate an unowned browser"))

    launch = admin._launch_browser()
    assert launch == (process, None)

    admin._cleanup_unattached_browser_launch(launch)
    assert process.terminated is False


def test_explicit_unknown_browser_path_remains_unowned(monkeypatch, tmp_path):
    binary = tmp_path / "custom-browser"
    binary.touch()
    profile = tmp_path / ".config" / "google-chrome"
    profile.mkdir(parents=True)
    (profile / "Local State").write_text('{}')
    process = FakeProcess()

    monkeypatch.setenv("BH_CHROME_PATH", str(binary))
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr("browser_harness.daemon.PROFILES", [profile])
    monkeypatch.setattr("browser_harness.daemon.remote_debugging_toggle_profiles", lambda: [profile])
    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: process)

    assert admin._launch_browser() == (process, None)


@pytest.mark.parametrize("value", ["0", "false", "NO", " off "])
def test_update_banner_can_be_disabled_without_network_or_cache_access(monkeypatch, value):
    monkeypatch.setenv("BH_UPDATE_CHECK", value)
    monkeypatch.setattr(admin, "_cache_read", lambda: pytest.fail("cache should not be read"))
    monkeypatch.setattr(admin, "check_for_update", lambda: pytest.fail("network should not run"))

    admin.print_update_banner()


def test_update_banner_remains_enabled_by_default(monkeypatch):
    monkeypatch.delenv("BH_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(admin, "_cache_read", lambda: {"banner_shown_on": "1970-01-01"})
    called = []

    def fake_check_for_update():
        called.append(True)
        return "0.1.0", "0.1.0", False

    monkeypatch.setattr(admin, "check_for_update", fake_check_for_update)

    admin.print_update_banner()

    assert called == [True]


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


def test_strict_remote_stop_propagates_daemon_error(monkeypatch):
    sock = FakeSocket(response=b'{"error":"billing stop failed"}\n')
    monkeypatch.setattr(admin.ipc, "identify", lambda _name, timeout: 123)
    monkeypatch.setattr(admin, "_process_start_time", lambda _pid: 1)
    monkeypatch.setattr(admin.ipc, "connect", lambda _name, timeout: (sock, None))

    with pytest.raises(RuntimeError, match="billing stop failed"):
        admin.stop_remote_daemon("scoped")

    assert sock.closed is True


def test_remote_start_retries_cleanup_and_preserves_both_failures(monkeypatch):
    attempts = []
    monkeypatch.setattr(admin, "daemon_alive", lambda _name: False)
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
        "ensure_daemon",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("daemon start failed")),
    )
    monkeypatch.setattr(admin.time, "sleep", lambda _seconds: None)

    with pytest.raises(BaseExceptionGroup) as exc_info:
        admin.start_remote_daemon("scoped")

    assert [str(error) for error in exc_info.value.exceptions] == [
        "daemon start failed",
        "failed to stop remote browser browser-1: billing stop failed",
    ]
    assert len(attempts) == 3


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


def test_ensure_daemon_closes_probe_socket_when_daemon_is_healthy(monkeypatch):
    sock = FakeSocket()

    monkeypatch.setattr(admin, "daemon_alive", lambda name=None: True)
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout=3.0: (sock, None))
    monkeypatch.setattr(admin.ipc, "request", lambda conn, token, req: {"result": {"targetInfos": []}})
    monkeypatch.setattr(admin, "restart_daemon", lambda name=None: (_ for _ in ()).throw(AssertionError("unexpected restart")))

    admin.ensure_daemon()

    assert sock.closed


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


def test_start_remote_daemon_stops_created_browser_when_daemon_start_fails(monkeypatch):
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
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda url: "ws://example.test/devtools/browser/1")
    monkeypatch.setattr(admin, "ensure_daemon", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        admin.start_remote_daemon()

    assert calls == [
        ("/browsers", "POST", {}),
        ("/browsers/browser-123", "PATCH", {"action": "stop"}),
    ]


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
def test_start_remote_daemon_stops_created_browser_when_daemon_start_is_interrupted(monkeypatch, exc_type):
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
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda url: "ws://example.test/devtools/browser/1")
    monkeypatch.setattr(admin, "ensure_daemon", lambda **kwargs: (_ for _ in ()).throw(exc_type()))

    with pytest.raises(exc_type):
        admin.start_remote_daemon()

    assert calls == [
        ("/browsers", "POST", {}),
        ("/browsers/browser-123", "PATCH", {"action": "stop"}),
    ]


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
def test_stop_cloud_browser_swallows_baseexception_from_stop_request(monkeypatch, exc_type):
    monkeypatch.setattr(admin, "_browser_use", lambda *args, **kwargs: (_ for _ in ()).throw(exc_type()))

    admin._stop_cloud_browser("browser-123")

def test_start_remote_daemon_does_not_stop_created_browser_on_success(monkeypatch):
    calls = []
    browser = {"id": "browser-123", "cdpUrl": "http://127.0.0.1:9333", "liveUrl": "https://live.example"}

    def fake_browser_use(path, method, body=None):
        calls.append((path, method, body))
        if (path, method) == ("/browsers", "POST"):
            return browser
        raise AssertionError((path, method, body))

    monkeypatch.setattr(admin, "daemon_alive", lambda name: False)
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda url: "ws://example.test/devtools/browser/1")
    monkeypatch.setattr(admin, "ensure_daemon", lambda **kwargs: None)
    monkeypatch.setattr(admin, "_show_live_url", lambda url: None)

    assert admin.start_remote_daemon() == browser
    assert calls == [
        ("/browsers", "POST", {}),
    ]


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


# --- _repo_dir / _install_mode ---

def _fake_install(monkeypatch, package_dir):
    """Point admin at a package laid out under `package_dir`."""
    package_dir.mkdir(parents=True, exist_ok=True)
    module = package_dir / "admin.py"
    module.touch()
    monkeypatch.setattr(admin, "__file__", str(module))


def test_repo_dir_detects_editable_src_layout_clone(tmp_path, monkeypatch):
    """The real case this exists for: `src/browser_harness` inside a git clone."""
    clone = tmp_path / "browser-harness"
    (clone / ".git").mkdir(parents=True)
    _fake_install(monkeypatch, clone / "src" / "browser_harness")

    assert admin._repo_dir() == clone


def test_repo_dir_detects_flat_layout_clone(tmp_path, monkeypatch):
    clone = tmp_path / "browser-harness"
    (clone / ".git").mkdir(parents=True)
    _fake_install(monkeypatch, clone / "browser_harness")

    assert admin._repo_dir() == clone


def test_repo_dir_ignores_repo_enclosing_an_installed_wheel(tmp_path, monkeypatch):
    """A wheel installed into a venv inside the user's own project is NOT a
    browser-harness clone. Claiming it would make run_update() `git pull` an
    unrelated repository instead of upgrading the package."""
    project = tmp_path / "my-project"
    (project / ".git").mkdir(parents=True)
    _fake_install(
        monkeypatch,
        project / ".venv" / "lib" / "python3.12" / "site-packages" / "browser_harness",
    )

    assert admin._repo_dir() is None


def test_repo_dir_ignores_dotfiles_repo_above_a_tool_install(tmp_path, monkeypatch):
    """`uv tool install` under a $HOME that is itself a dotfiles git repo."""
    home = tmp_path / "home"
    (home / ".git").mkdir(parents=True)
    _fake_install(
        monkeypatch,
        home / ".local/share/uv/tools/browser-harness/lib/python3.12/site-packages/browser_harness",
    )

    assert admin._repo_dir() is None


def test_run_update_of_installed_wheel_never_pulls_an_enclosing_repo(tmp_path, monkeypatch):
    """End-to-end symptom: `browser-harness --update -y` must upgrade the
    package, not run git against the repository that happens to contain it."""
    import subprocess

    project = tmp_path / "my-project"
    (project / ".git").mkdir(parents=True)
    _fake_install(
        monkeypatch,
        project / ".venv" / "lib" / "python3.12" / "site-packages" / "browser_harness",
    )
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_latest_release_tag", lambda *a, **k: "0.2.0")
    monkeypatch.setattr(admin, "_cache_read", lambda: {})
    monkeypatch.setattr(admin, "_cache_write", lambda data: None)
    monkeypatch.setattr(admin, "daemon_alive", lambda *a, **k: False)
    commands = []

    def fake_run(command, *args, **kwargs):
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert admin.run_update(yes=True) == 0
    assert not any(command[:1] == ["git"] for command in commands), (
        f"run_update must not shell out to git for a wheel install; ran {commands}"
    )
    assert ["uv", "tool", "upgrade", "browser-harness"] in commands

def _wheel_update_env(tmp_path, monkeypatch):
    """Set up a wheel install so run_update() takes the pypi branch."""
    project = tmp_path / "my-project"
    (project / ".git").mkdir(parents=True)
    _fake_install(
        monkeypatch,
        project / ".venv" / "lib" / "python3.12" / "site-packages" / "browser_harness",
    )
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_latest_release_tag", lambda *a, **k: "0.2.0")
    monkeypatch.setattr(admin, "_cache_read", lambda: {})
    monkeypatch.setattr(admin, "_cache_write", lambda data: None)
    monkeypatch.setattr(admin, "daemon_alive", lambda *a, **k: False)


def test_failed_upgrade_tells_a_pip_install_how_to_upgrade(tmp_path, monkeypatch, capsys):
    """A pip or pipx install is invisible to `uv tool upgrade`, so the bare failure
    has to name the documented uv install instead of just exiting non-zero."""
    import subprocess

    _wheel_update_env(tmp_path, monkeypatch)

    def fake_run(command, *args, **kwargs):
        if list(command)[:3] == ["uv", "tool", "list"]:
            return subprocess.CompletedProcess(command, 0, "some-other-tool v1.0.0\n", "")
        return subprocess.CompletedProcess(command, 1, "", "`browser-harness` is not installed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert admin.run_update(yes=True) == 1
    assert "uv tool install --python 3.12 --upgrade --force browser-harness" in capsys.readouterr().err

def test_failed_upgrade_stays_quiet_for_a_uv_managed_install(tmp_path, monkeypatch, capsys):
    """When uv owns the tool the failure is uv's own (offline, auth), so a pip hint
    would only mislead."""
    import subprocess

    _wheel_update_env(tmp_path, monkeypatch)

    def fake_run(command, *args, **kwargs):
        if list(command)[:3] == ["uv", "tool", "list"]:
            return subprocess.CompletedProcess(command, 0, "browser-harness v0.1.0\n", "")
        return subprocess.CompletedProcess(command, 1, "", "network unreachable")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert admin.run_update(yes=True) == 1
    assert "pip or pipx" not in capsys.readouterr().err

def test_failed_upgrade_ignores_a_lookalike_uv_tool_name(tmp_path, monkeypatch, capsys):
    """A tool merely containing our name must not silence the hint for a pip install."""
    import subprocess

    _wheel_update_env(tmp_path, monkeypatch)

    def fake_run(command, *args, **kwargs):
        if list(command)[:3] == ["uv", "tool", "list"]:
            return subprocess.CompletedProcess(
                command, 0, "my-browser-harness-wrapper v2.0.0\n- bhw\n", ""
            )
        return subprocess.CompletedProcess(command, 1, "", "`browser-harness` is not installed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert admin.run_update(yes=True) == 1
    assert "uv tool install --python 3.12 --upgrade --force browser-harness" in capsys.readouterr().err
# --- Chrome's "Allow remote debugging?" popup: one pending startup per name --
# Chrome 144+ raises the popup per CDP connection, and the connection that
# raised it is what keeps it on screen. ensure_daemon used to kill that daemon
# whenever the click did not land in time, which dropped the popup and made the
# next call raise a new one. Users with several daemons saw it for ever.


def _park_daemon(tmp_path, monkeypatch, pid, *, is_daemon=True):
    """Simulate a daemon parked on the popup: pid file + fresh handshake log."""
    from browser_harness import admin as admin_mod

    monkeypatch.setattr(admin_mod, "_log_tail", lambda name=None: "handshake-wait: click Allow")
    log_file = tmp_path / "daemon.log"
    log_file.write_text("handshake-wait: click Allow")
    monkeypatch.setattr(admin_mod.ipc, "log_path", lambda name: log_file)
    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text(str(pid))
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod, "_is_daemon_process", lambda p: is_daemon)


def test_parked_daemon_is_detected_from_pid_file_and_log(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    _park_daemon(tmp_path, monkeypatch, os.getpid())
    assert admin_mod._parked_daemon_pid() == os.getpid()


def test_parked_daemon_liveness_never_uses_os_kill(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    _park_daemon(tmp_path, monkeypatch, os.getpid())
    monkeypatch.setattr(admin_mod, "_pending_pid_record", lambda path: os.getpid())
    monkeypatch.setattr(admin_mod.os, "kill", lambda *a: (_ for _ in ()).throw(AssertionError("os.kill is destructive on Windows")))
    assert admin_mod._parked_daemon_pid() == os.getpid()


def test_parked_daemon_ignored_when_the_process_is_gone(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    _park_daemon(tmp_path, monkeypatch, 2147480000, is_daemon=False)  # never a live daemon
    assert admin_mod._parked_daemon_pid() is None


def test_parked_daemon_ignored_without_the_handshake_breadcrumb(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    _park_daemon(tmp_path, monkeypatch, os.getpid())
    monkeypatch.setattr(admin_mod, "_log_tail", lambda name=None: "connecting to ws://...")
    assert admin_mod._parked_daemon_pid() is None


def test_ensure_daemon_waits_for_the_parked_daemon_instead_of_spawning(tmp_path, monkeypatch):
    """The second invocation must join the popup already on screen."""
    from browser_harness import admin as admin_mod

    _park_daemon(tmp_path, monkeypatch, os.getpid())
    monkeypatch.setattr(admin_mod, "_is_local_chrome_mode", lambda env: True)
    monkeypatch.setattr(admin_mod, "daemon_alive", lambda name=None: False)

    spawned = []

    def refuse_spawn(*args, **kwargs):
        spawned.append(args)
        raise AssertionError("spawned a sibling daemon while one was parked")

    monkeypatch.setattr(admin_mod.subprocess, "Popen", refuse_spawn)

    with pytest.raises(RuntimeError, match="popup is still open"):
        admin_mod.ensure_daemon(wait=0.3)
    assert spawned == []


def test_ensure_daemon_returns_when_the_parked_daemon_finishes(tmp_path, monkeypatch):
    """Clicking Allow completes the parked handshake; no new daemon needed."""
    from browser_harness import admin as admin_mod

    _park_daemon(tmp_path, monkeypatch, os.getpid())
    monkeypatch.setattr(admin_mod, "_is_local_chrome_mode", lambda env: True)
    calls = {"n": 0}

    def alive(name=None):
        calls["n"] += 1
        return calls["n"] > 2  # the user clicks Allow on the third poll

    monkeypatch.setattr(admin_mod, "daemon_alive", alive)
    admin_mod.ensure_daemon(wait=5.0)  # returns, does not raise


def test_ensure_daemon_does_not_replace_pending_approval_that_exited(tmp_path, monkeypatch):
    """A failed approval attempt must not create another Chrome prompt."""
    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    log_file = tmp_path / "daemon.log"
    pid_file.write_text(str(os.getpid()))
    log_file.write_text("handshake-wait: click Allow")
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod.ipc, "log_path", lambda name: log_file)
    monkeypatch.setattr(admin_mod.ipc, "spawn_kwargs", lambda: {})
    monkeypatch.setattr(admin_mod, "_is_local_chrome_mode", lambda env: True)
    monkeypatch.setattr(admin_mod, "daemon_alive", lambda name=None: False)
    pending = iter([os.getpid(), None])
    monkeypatch.setattr(admin_mod, "_parked_daemon_pid", lambda name=None: next(pending, None))
    monkeypatch.setattr(admin_mod, "_starting_daemon_pid", lambda name=None: None)
    monkeypatch.setattr(admin_mod, "_pending_pid_record", lambda path: None)
    monkeypatch.setattr(admin_mod, "_process_start_time", lambda pid: "start")

    class Dead:
        pid = 4321
        def poll(self): return 1

    spawned = []
    monkeypatch.setattr(admin_mod.subprocess, "Popen", lambda *a, **k: spawned.append(a) or Dead())

    with pytest.raises(RuntimeError, match="did not retry or create another connection"):
        admin_mod.ensure_daemon(wait=0.1)
    assert spawned == []


def test_dead_pending_cleanup_does_not_unlink_successor(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    log_file = tmp_path / "daemon.log"
    pid_file.write_text("111")
    log_file.write_text("handshake-wait: click Allow")
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod.ipc, "log_path", lambda name: log_file)
    monkeypatch.setattr(admin_mod, "_is_local_chrome_mode", lambda env: True)
    monkeypatch.setattr(admin_mod, "daemon_alive", lambda name=None: False)
    pending = iter([111, None])
    monkeypatch.setattr(admin_mod, "_parked_daemon_pid", lambda name=None: next(pending, None))
    monkeypatch.setattr(admin_mod, "_starting_daemon_pid", lambda name=None: None)

    def old_dies_as_successor_arrives(path):
        pid_file.write_text("222")
        return None

    monkeypatch.setattr(admin_mod, "_pending_pid_record", old_dies_as_successor_arrives)
    monkeypatch.setattr(admin_mod.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop after cleanup")))

    with pytest.raises(RuntimeError, match="did not retry or create another connection"):
        admin_mod.ensure_daemon(wait=0.1)
    assert pid_file.read_text() == "222"


def test_default_local_approval_has_no_deadline_without_affecting_remote():
    from browser_harness import admin as admin_mod

    assert admin_mod._daemon_wait_windows(None, local=True) == (60.0, None)
    assert admin_mod._daemon_wait_windows(None, local=False) == (60.0, 60.0)
    assert admin_mod._daemon_wait_windows(7, local=True) == (7.0, 7.0)


def test_permission_blocked_exit_is_not_retried(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    log_file = tmp_path / "daemon.log"
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod.ipc, "log_path", lambda name: log_file)
    monkeypatch.setattr(admin_mod.ipc, "spawn_kwargs", lambda: {})
    monkeypatch.setattr(admin_mod, "_is_local_chrome_mode", lambda env: True)
    monkeypatch.setattr(admin_mod, "daemon_alive", lambda name=None: False)
    monkeypatch.setattr(admin_mod, "_parked_daemon_pid", lambda name=None: None)
    monkeypatch.setattr(admin_mod, "_starting_daemon_pid", lambda name=None: None)
    monkeypatch.setattr(admin_mod, "_log_tail", lambda name=None: "permission-blocked: approval expired")
    monkeypatch.setattr(admin_mod, "_process_start_time", lambda pid: "start")
    monkeypatch.setattr(
        admin_mod,
        "restart_daemon",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("approval must not restart")),
    )

    class Dead:
        pid = 4321

        def poll(self):
            return 1

    spawned = []
    monkeypatch.setattr(admin_mod.subprocess, "Popen", lambda *a, **k: spawned.append(a) or Dead())

    with pytest.raises(RuntimeError, match="did not retry or create another connection"):
        admin_mod.ensure_daemon(wait=0.1)
    assert len(spawned) == 1


def test_cold_spawn_publishes_child_before_releasing_lock(tmp_path, monkeypatch):
    """A second cold caller sees the first child before its log exists."""
    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    log_file = tmp_path / "daemon.log"
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod.ipc, "log_path", lambda name: log_file)
    monkeypatch.setattr(admin_mod.ipc, "spawn_kwargs", lambda: {})
    monkeypatch.setattr(admin_mod, "_is_local_chrome_mode", lambda env: True)
    monkeypatch.setattr(admin_mod, "daemon_alive", lambda name=None: False)
    monkeypatch.setattr(admin_mod, "_parked_daemon_pid", lambda name=None: None)
    monkeypatch.setattr(admin_mod, "_is_daemon_process", lambda pid: pid == 4321)
    monkeypatch.setattr(admin_mod, "_process_start_time", lambda pid: "start-4321")

    class Starting:
        pid = 4321

        def poll(self): return None

    spawned = []

    def spawn(*args, **kwargs):
        spawned.append(args)
        pid_file.write_text("4321")
        return Starting()

    monkeypatch.setattr(admin_mod.subprocess, "Popen", spawn)

    with pytest.raises(RuntimeError, match="didn't come up"):
        admin_mod.ensure_daemon(wait=0)
    assert len(spawned) == 1
    assert json.loads(pid_file.read_text()) == {"pid": 4321, "started": "start-4321"}
    old = time.time() - 86400
    os.utime(pid_file, (old, old))
    with pytest.raises(RuntimeError, match="didn't come up"):
        admin_mod.ensure_daemon(wait=0)
    assert len(spawned) == 1


def test_starting_daemon_survives_wall_clock_age_before_log(tmp_path, monkeypatch):
    """Sleep can age the PID mtime before the child writes handshake-wait."""
    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text(json.dumps({"pid": os.getpid(), "started": "start"}))
    old = time.time() - 86400
    os.utime(pid_file, (old, old))
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod, "_process_start_time", lambda pid: "start")
    assert admin_mod._starting_daemon_pid() == os.getpid()


def test_parked_daemon_ignored_when_the_pid_was_reused(tmp_path, monkeypatch):
    """A recycled pid belonging to something else must not look parked."""
    from browser_harness import admin as admin_mod

    _park_daemon(tmp_path, monkeypatch, os.getpid(), is_daemon=False)
    assert admin_mod._parked_daemon_pid() is None


def test_parked_daemon_survives_wall_clock_age_while_process_is_live(tmp_path, monkeypatch):
    """A live pending approval has no age-based expiry, including across sleep."""
    from browser_harness import admin as admin_mod

    _park_daemon(tmp_path, monkeypatch, os.getpid())
    stale = time.time() - 86400
    os.utime(tmp_path / "daemon.log", (stale, stale))
    assert admin_mod._parked_daemon_pid() == os.getpid()


def test_spawn_lock_is_exclusive_then_released(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: tmp_path / "daemon.pid")
    with admin_mod._spawn_lock(timeout=0.2) as first:
        assert first.fd is not None
        with admin_mod._spawn_lock(timeout=0.2) as second:
            assert second.fd is None  # someone else holds it; proceed anyway
    with admin_mod._spawn_lock(timeout=0.2) as third:
        assert third.fd is not None  # released on exit


def test_spawn_lock_does_not_expire_while_owner_is_alive(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: tmp_path / "daemon.pid")
    with admin_mod._spawn_lock(timeout=0.1) as first:
        old = time.time() - 86400
        os.utime(first.path, (old, old))
        with admin_mod._spawn_lock(timeout=0.1) as second:
            assert second.fd is None


def test_spawn_lock_owner_cannot_unlink_successor(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: tmp_path / "daemon.pid")
    first = admin_mod._spawn_lock(timeout=0.1)
    first.__enter__()
    first.path.write_text(f"{os.getpid()} successor")
    first.__exit__()
    assert first.path.read_text() == f"{os.getpid()} successor"


def test_process_identity_check_fails_closed_when_unavailable(monkeypatch):
    from browser_harness import admin as admin_mod

    def unavailable(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(admin_mod.subprocess, "run", unavailable)
    assert admin_mod._is_daemon_process(os.getpid()) is False


def test_pending_pid_record_rejects_reused_pid(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text(json.dumps({"pid": os.getpid(), "started": "old-start"}))
    monkeypatch.setattr(admin_mod, "_process_start_time", lambda pid: "new-start")
    assert admin_mod._pending_pid_record(pid_file) is None


def test_restart_daemon_stops_exact_fingerprinted_pending_approval(tmp_path, monkeypatch):
    import signal

    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text(json.dumps({"pid": 4321, "started": "same-start"}))
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod.ipc, "identify", lambda *a, **k: None)
    monkeypatch.setattr(admin_mod.ipc, "ping", lambda *a, **k: False)
    monkeypatch.setattr(admin_mod.ipc, "cleanup_endpoint", lambda name: None)
    monkeypatch.setattr(admin_mod, "_log_tail", lambda name=None: "handshake-wait: click Allow")
    monkeypatch.setattr(admin_mod, "_process_start_time", lambda pid: "same-start")
    signals = []
    monkeypatch.setattr(admin_mod.os, "kill", lambda pid, sig: signals.append((pid, sig)))

    admin_mod.restart_daemon("pending")

    assert signals == [(4321, signal.SIGTERM)]
    assert not pid_file.exists()


def test_restart_daemon_never_signals_reused_pending_pid(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text(json.dumps({"pid": 4321, "started": "old-start"}))
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod.ipc, "identify", lambda *a, **k: None)
    monkeypatch.setattr(admin_mod.ipc, "ping", lambda *a, **k: False)
    monkeypatch.setattr(admin_mod.ipc, "cleanup_endpoint", lambda name: None)
    monkeypatch.setattr(admin_mod, "_log_tail", lambda name=None: "handshake-wait: click Allow")
    monkeypatch.setattr(admin_mod, "_process_start_time", lambda pid: "new-start")
    monkeypatch.setattr(
        admin_mod.os,
        "kill",
        lambda *a: (_ for _ in ()).throw(AssertionError("reused PID must not be signaled")),
    )

    admin_mod.restart_daemon("pending")

    assert not pid_file.exists()


def test_restart_daemon_preserves_live_pending_without_fingerprint(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text("4321")
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod.ipc, "identify", lambda *a, **k: None)
    monkeypatch.setattr(admin_mod.ipc, "ping", lambda *a, **k: False)
    monkeypatch.setattr(admin_mod, "_log_tail", lambda name=None: "handshake-wait: click Allow")
    monkeypatch.setattr(admin_mod, "_is_daemon_process", lambda pid: pid == 4321)
    monkeypatch.setattr(admin_mod, "_process_start_time", lambda pid: None)
    monkeypatch.setattr(
        admin_mod.os,
        "kill",
        lambda *a: (_ for _ in ()).throw(AssertionError("unverified PID must not be signaled")),
    )

    with pytest.raises(RuntimeError, match="ownership records were preserved"):
        admin_mod.restart_daemon("pending")

    assert pid_file.read_text() == "4321"


def test_restart_daemon_does_not_cancel_successor_generation(tmp_path, monkeypatch):
    from browser_harness import admin as admin_mod

    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text(json.dumps({"pid": 111, "started": "old-start"}))
    monkeypatch.setattr(admin_mod.ipc, "pid_path", lambda name: pid_file)
    monkeypatch.setattr(admin_mod.ipc, "identify", lambda *a, **k: None)
    monkeypatch.setattr(admin_mod.ipc, "ping", lambda *a, **k: False)
    monkeypatch.setattr(admin_mod.ipc, "cleanup_endpoint", lambda name: None)
    monkeypatch.setattr(admin_mod, "_log_tail", lambda name=None: "handshake-wait: click Allow")
    monkeypatch.setattr(admin_mod, "_parked_daemon_pid", lambda name=None: 111)
    generations = iter([(111, "old-start"), (222, "new-start")])
    monkeypatch.setattr(
        admin_mod,
        "_fingerprinted_pending_generation",
        lambda path: next(generations),
    )
    monkeypatch.setattr(
        admin_mod.os,
        "kill",
        lambda *a: (_ for _ in ()).throw(AssertionError("successor must not be signaled")),
    )

    with pytest.raises(RuntimeError, match="changed ownership; the successor was not signaled"):
        admin_mod.restart_daemon("pending")

    assert pid_file.exists()
