"""Closed toggle-enabled Chrome masked by another running Chromium browser.

Field failure (macOS): Chrome had "Allow remote debugging" ticked and a stale
DevToolsActivePort, but Chrome itself was closed while Arc was running.
get_ws_url() blamed the inspect toggle ("DevToolsActivePort not found") and
ensure_daemon() never reached its launch-Chrome recovery, so the harness
could not start until Chrome was opened by hand.
"""
import os
from contextlib import contextmanager

import pytest

from browser_harness import admin, daemon


@pytest.fixture
def closed_chrome_masked_by_arc(monkeypatch, tmp_path):
    chrome = tmp_path / "Google/Chrome"
    chrome.mkdir(parents=True)
    (chrome / "Local State").write_text(
        '{"devtools": {"remote_debugging": {"user-enabled": true}}}'
    )
    # Stale file from a previous session: nothing listens on this port.
    (chrome / "DevToolsActivePort").write_text("9222\n/devtools/browser/stale\n")
    arc = tmp_path / "Arc/User Data"
    arc.mkdir(parents=True)
    (arc / "Local State").write_text("{}")
    (arc / "SingletonLock").symlink_to(f"test-host-{os.getpid()}")
    monkeypatch.setattr(daemon, "PROFILES", [chrome, arc])
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "TOGGLE_BOOT_GRACE", 0)
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)

    def urlopen(url, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(daemon.urllib.request, "urlopen", urlopen)
    return chrome


def test_closed_toggle_chrome_reports_chrome_not_running(closed_chrome_masked_by_arc):
    # The masking condition itself: Arc counts as a running supported browser
    # while the toggle-enabled Chrome profile has no live process behind it.
    assert daemon.supported_browser_running()
    assert not daemon.browser_running_for_profile(closed_chrome_masked_by_arc)
    with pytest.raises(RuntimeError, match="chrome-not-running"):
        daemon.get_ws_url()


def test_ensure_daemon_launches_browser_for_dead_chrome_not_running_daemon(monkeypatch, tmp_path):
    launches = []
    restarts = []
    alive = {"value": False}

    @contextmanager
    def fake_lock(name=None, timeout=None):
        yield type("Lock", (), {"fd": 1})()

    class DeadProcess:
        pid = 4242

        def poll(self):
            return 1

    monkeypatch.setattr(admin, "_spawn_lock", fake_lock)
    monkeypatch.setattr(admin, "_daemon_wait_windows", lambda wait, local: (5.0, 5.0))
    monkeypatch.setattr(admin, "daemon_alive", lambda name=None: alive["value"])
    monkeypatch.setattr(admin, "_parked_daemon_pid", lambda name=None: None)
    monkeypatch.setattr(admin, "_starting_daemon_pid", lambda name=None: None)
    monkeypatch.setattr(admin, "_log_tail", lambda name=None: "fatal: chrome-not-running: Google Chrome is not running")
    monkeypatch.setattr(admin, "_pid_number", lambda path: 4242)
    monkeypatch.setattr(admin, "_publish_pid", lambda path, pid: None)
    monkeypatch.setattr(admin.ipc, "log_path", lambda name: tmp_path / "daemon.log")
    monkeypatch.setattr(admin.ipc, "pid_path", lambda name: tmp_path / "daemon.pid")
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: DeadProcess())
    monkeypatch.setattr(admin, "restart_daemon", lambda name=None: restarts.append(name))
    port_checks = []
    monkeypatch.setattr(
        daemon,
        "supported_browser_running",
        lambda: (_ for _ in ()).throw(AssertionError("global readiness path must not be used")),
    )
    monkeypatch.setattr(daemon, "_devtools_port_live", lambda profile: port_checks.append(profile) or True)

    def fake_launch():
        launches.append(True)
        alive["value"] = True
        return (None, tmp_path)

    monkeypatch.setattr(admin, "_launch_browser", fake_launch)
    admin.ensure_daemon()
    assert launches == [True]
    # Recovery waits on the launched profile's own DevTools port.
    assert port_checks == [tmp_path]
    # The daemon that reported chrome-not-running is already dead; restarting
    # here could stop a healthy successor from a concurrent ensure_daemon().
    assert restarts == []
