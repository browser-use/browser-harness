"""macOS TCC blocks reading the browser profile dir (EPERM), where
DevToolsActivePort lives. get_ws_url() must not crash on that: it falls back to a
dedicated automation Chrome, and fails with actionable guidance when it can't.
No real browser is launched."""
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from browser_harness import daemon


class _BlockedProfile:
    """A profile dir the OS refuses to read (macOS TCC / EPERM)."""

    def __truediv__(self, _name):
        return self

    def read_text(self, *args, **kwargs):
        raise PermissionError(1, "Operation not permitted")

    def exists(self):
        return True

    def __str__(self):
        return "/Library/Application Support/Google/Chrome"


@pytest.fixture
def blocked_profile(monkeypatch):
    monkeypatch.setattr(daemon, "PROFILES", [_BlockedProfile()])
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setattr(daemon, "REMOTE_ID", None)

    def refused(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(daemon.urllib.request, "urlopen", refused)
    monkeypatch.setattr(daemon.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(daemon, "_json_version_ws", lambda _port: None)


def test_blocked_profile_falls_back_to_automation_chrome(blocked_profile, monkeypatch):
    endpoint = "ws://127.0.0.1:49231/devtools/browser/auto"
    called = False

    def launch_and_record():
        nonlocal called
        called = True
        return endpoint

    monkeypatch.setattr(daemon, "launch_automation_chrome", launch_and_record)
    assert daemon.get_ws_url() == endpoint
    assert called


def test_blocked_profile_without_browser_raises_actionable_error(blocked_profile, monkeypatch):
    monkeypatch.setattr(daemon, "launch_automation_chrome", lambda: None)
    monkeypatch.setattr(daemon, "remote_debugging_user_enabled", lambda: False)
    with pytest.raises(RuntimeError, match="Full Disk Access"):
        daemon.get_ws_url()


def test_blocked_profile_with_missing_profile_falls_back(blocked_profile, monkeypatch, tmp_path):
    monkeypatch.setattr(daemon, "PROFILES", [_BlockedProfile(), tmp_path / "missing-profile"])
    endpoint = "ws://127.0.0.1:49231/devtools/browser/auto"
    monkeypatch.setattr(daemon, "supported_browser_running", lambda: True)
    monkeypatch.setattr(daemon, "NO_TOGGLE_GRACE", -1)
    launch = []
    monkeypatch.setattr(daemon, "launch_automation_chrome", lambda: launch.append(True) or endpoint)

    assert daemon.get_ws_url() == endpoint
    assert launch == [True]


def test_one_readable_profile_prevents_tcc_fallback(blocked_profile, monkeypatch, tmp_path):
    readable = tmp_path / "readable-profile"
    readable.mkdir()
    monkeypatch.setattr(daemon, "PROFILES", [_BlockedProfile(), readable])
    monkeypatch.setattr(daemon, "NO_TOGGLE_GRACE", -1)
    monkeypatch.setattr(daemon, "supported_browser_running", lambda: False)
    launch = []
    monkeypatch.setattr(daemon, "launch_automation_chrome", lambda: launch.append(True))

    with pytest.raises(RuntimeError, match="chrome-not-running"):
        daemon.get_ws_url()
    assert launch == []


@pytest.mark.parametrize("system", ["Windows", "Linux"])
def test_permission_error_on_non_macos_uses_normal_profile_error(
    blocked_profile, monkeypatch, system
):
    monkeypatch.setattr(daemon.platform, "system", lambda: system)
    monkeypatch.setattr(daemon, "supported_browser_running", lambda: True)
    monkeypatch.setattr(daemon, "NO_TOGGLE_GRACE", -1)
    monkeypatch.setattr(daemon, "remote_debugging_user_enabled", lambda: None)
    monkeypatch.setattr(daemon, "_endpoint_owned_by_profile", lambda *_a, **_k: True)
    launch = []
    monkeypatch.setattr(daemon, "launch_automation_chrome", lambda: launch.append(True))

    with pytest.raises(RuntimeError, match="DevToolsActivePort not found") as exc:
        daemon.get_ws_url()

    assert "Full Disk Access" not in str(exc.value)
    assert launch == []


def test_automation_profile_rediscovers_selected_port_after_restart(monkeypatch, tmp_path):
    profile = tmp_path / "automation-profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("49231\n/devtools/browser/persisted\n")
    monkeypatch.setattr(daemon, "AUTOMATION_PROFILE", profile)
    monkeypatch.setattr(daemon, "browser_running_for_profile", lambda path: path == profile)
    monkeypatch.setattr(
        daemon,
        "_json_version_ws",
        lambda port: f"ws://127.0.0.1:{port}/devtools/browser/persisted" if port == 49231 else None,
    )

    def unexpected_launch():
        pytest.fail("a live automation profile should be reused")

    monkeypatch.setattr(daemon, "_automation_chrome_binary", unexpected_launch)
    monkeypatch.setattr(daemon, "_profile_process_owns", lambda _profile: True)
    monkeypatch.setattr(daemon, "_endpoint_owned_by_profile", lambda *_args, **_kwargs: True)
    assert daemon.launch_automation_chrome() == "ws://127.0.0.1:49231/devtools/browser/persisted"


@pytest.mark.parametrize(
    ("response_path", "accepted"),
    [
        ("/devtools/browser/profile-owner", True),
        ("/devtools/browser/unrelated-owner", False),
    ],
)
def test_json_version_reuse_requires_profile_endpoint_identity(
    monkeypatch, tmp_path, response_path, accepted
):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text(
        "49231\n/devtools/browser/profile-owner\n"
    )
    monkeypatch.setattr(daemon, "PROFILES", [profile])
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "supported_browser_running", lambda: True)
    monkeypatch.setattr(daemon, "NO_TOGGLE_GRACE", -1)
    monkeypatch.setattr(daemon, "remote_debugging_user_enabled", lambda: None)
    monkeypatch.setattr(
        daemon, "_endpoint_owned_by_profile",
        lambda _base, _port, ws, _snapshot: accepted and daemon._ws_matches_devtools_active_port(
            profile, "49231", ws
        ),
    )
    response = MagicMock()
    response.read.return_value = (
        '{"webSocketDebuggerUrl": '
        f'"ws://127.0.0.1:49231{response_path}"}}'
    ).encode()
    response.__enter__.return_value = response
    monkeypatch.setattr(daemon.urllib.request, "urlopen", lambda *_a, **_k: response)

    if accepted:
        assert daemon.get_ws_url() == f"ws://127.0.0.1:49231{response_path}"
    else:
        with pytest.raises(RuntimeError, match="DevToolsActivePort not found"):
            daemon.get_ws_url()


@pytest.mark.parametrize("process_owns_profile", [True, False])
def test_json_version_404_fallback_requires_profile_process_identity(
    monkeypatch, tmp_path, process_owns_profile
):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text(
        "49231\n/devtools/browser/profile-owner\n"
    )
    monkeypatch.setattr(daemon, "PROFILES", [profile])
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "supported_browser_running", lambda: True)
    monkeypatch.setattr(daemon, "NO_TOGGLE_GRACE", -1)
    monkeypatch.setattr(daemon, "remote_debugging_user_enabled", lambda: None)
    monkeypatch.setattr(
        daemon, "_profile_process_owns", lambda base: base == profile and process_owns_profile
    )
    monkeypatch.setattr(
        daemon, "_endpoint_owned_by_profile", lambda *_args, **_kwargs: process_owns_profile
    )

    def not_found(*_args, **_kwargs):
        raise daemon.urllib.error.HTTPError(
            "http://127.0.0.1:49231/json/version", 404, "Not Found", {}, None
        )

    monkeypatch.setattr(daemon.urllib.request, "urlopen", not_found)

    if process_owns_profile:
        assert daemon.get_ws_url() == (
            "ws://127.0.0.1:49231/devtools/browser/profile-owner"
        )
    else:
        with pytest.raises(RuntimeError, match="DevToolsActivePort not found"):
            daemon.get_ws_url()


def test_stale_automation_port_does_not_attach_to_unrelated_listener(monkeypatch, tmp_path):
    profile = tmp_path / "automation-profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("49231\n/devtools/browser/stale\n")
    monkeypatch.setattr(daemon, "AUTOMATION_PROFILE", profile)
    monkeypatch.setattr(daemon, "_profile_process_owns", lambda _path: False)
    monkeypatch.setattr(daemon, "_port_in_use", lambda _port: True)
    monkeypatch.setattr(daemon, "_automation_chrome_binary", lambda: None)

    assert daemon.launch_automation_chrome() is None


def test_live_automation_profile_with_unverifiable_endpoint_is_not_reused(
    monkeypatch, tmp_path
):
    profile = tmp_path / "automation-profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("49231\n/devtools/browser/stale\n")
    monkeypatch.setattr(daemon, "AUTOMATION_PROFILE", profile)
    monkeypatch.setattr(daemon, "_profile_process_owns", lambda _path: True)
    monkeypatch.setattr(daemon, "_json_version_ws", lambda _port: None)
    monkeypatch.setattr(daemon, "_port_in_use", lambda _port: True)
    monkeypatch.setattr(daemon, "_automation_chrome_binary", lambda: None)

    assert daemon.launch_automation_chrome() is None


@pytest.mark.parametrize(
    "endpoint",
    [
        "ws://example.com:49231/devtools/browser/profile-owner",
        "ws://192.168.1.2:49231/devtools/browser/profile-owner",
        "ws://127.0.0.1:49232/devtools/browser/profile-owner",
        "ws://127.0.0.1:49231/devtools/browser/foreign-profile",
        "wss://127.0.0.1:49231/devtools/browser/profile-owner",
    ],
)
def test_automation_reuse_rejects_foreign_endpoint_identity(
    monkeypatch, tmp_path, endpoint
):
    profile = tmp_path / "automation-profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text(
        "49231\n/devtools/browser/profile-owner\n"
    )
    monkeypatch.setattr(daemon, "AUTOMATION_PROFILE", profile)
    monkeypatch.setattr(daemon, "_profile_process_owns", lambda *_args: True)
    monkeypatch.setattr(daemon, "_endpoint_owned_by_profile", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(daemon, "_json_version_ws", lambda _port: endpoint)
    monkeypatch.setattr(daemon, "_automation_chrome_binary", lambda: None)

    assert daemon.launch_automation_chrome() is None


def test_automation_launch_rejects_unrelated_listener(monkeypatch, tmp_path):
    profile = tmp_path / "automation-profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text(
        "49231\n/devtools/browser/stale-snapshot\n"
    )
    monkeypatch.setattr(daemon, "AUTOMATION_PROFILE", profile)
    monkeypatch.setattr(daemon, "_port_in_use", lambda _port: True)
    monkeypatch.setattr(daemon, "_free_port", lambda: 49231)
    monkeypatch.setattr(daemon, "_automation_chrome_binary", lambda: "/mock/chrome")
    monkeypatch.setattr(daemon, "_profile_process_owns", lambda *_args: True)
    monkeypatch.setattr(daemon, "_devtools_active_port_snapshot",
                        lambda _profile: (1, 2, 3, 45,
                                          b"49231\n/devtools/browser/stale-snapshot\n",
                                          "49231", "/devtools/browser/stale-snapshot"))
    monkeypatch.setattr(daemon, "_endpoint_owned_by_profile", lambda *_a, **_k: False)
    monkeypatch.setattr(
        daemon, "_json_version_ws", lambda _port: "ws://127.0.0.1:49231/devtools/browser/other"
    )
    clock_values = iter([0, 0, 21])
    monkeypatch.setattr(
        daemon, "time", SimpleNamespace(time=lambda: next(clock_values), sleep=lambda _seconds: None)
    )

    class RunningChild:
        pid = 1234

        @staticmethod
        def poll():
            return None

    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *_args, **_kwargs: RunningChild())

    assert daemon.launch_automation_chrome() is None


@pytest.mark.parametrize("payload", [[], "not-json-object", {"webSocketDebuggerUrl": 1}, {}])
def test_json_version_rejects_non_object_or_invalid_websocket_field(
    monkeypatch, payload
):
    response = MagicMock()
    response.read.return_value = daemon.json.dumps(payload).encode()
    response.__enter__.return_value = response
    monkeypatch.setattr(daemon.urllib.request, "urlopen", lambda *_a, **_k: response)
    assert daemon._json_version_ws(49231) is None


@pytest.mark.parametrize(
    ("profile_name", "executable_name"),
    [("Chrome", "Google Chrome"), ("Chrome Beta", "Google Chrome Beta"),
     ("Chrome Dev", "Google Chrome Dev"), ("Chrome Canary", "Google Chrome Canary")],
)
def test_default_chrome_profiles_allow_omitted_profile_switch(
    monkeypatch, tmp_path, profile_name, executable_name
):
    root = tmp_path / "Library/Application Support/Google" / profile_name
    root.mkdir(parents=True)
    monkeypatch.setattr(daemon.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(daemon.platform, "system", lambda: "Darwin")
    executable = f"/Applications/{executable_name}.app/Contents/MacOS/{executable_name}"
    monkeypatch.setattr(daemon, "_trusted_browser_executable", lambda _exe: True)
    monkeypatch.setattr(daemon, "_process_args", lambda _pid: [executable])
    (root / "SingletonLock").symlink_to("host-77")
    assert daemon._profile_browser_pid(root) == 77


def test_default_profile_does_not_accept_another_browser_or_profile_switch(
    monkeypatch, tmp_path
):
    profile = tmp_path / "Library/Application Support/Google/Chrome"
    profile.mkdir(parents=True)
    (profile / "SingletonLock").symlink_to("host-77")
    monkeypatch.setattr(daemon.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(daemon.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(daemon, "_trusted_browser_executable", lambda _exe: True)
    monkeypatch.setattr(daemon, "_process_args", lambda _pid: [
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    ])
    assert daemon._profile_browser_pid(profile) is None
    monkeypatch.setattr(daemon, "_process_args", lambda _pid: [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        f"--user-data-dir={tmp_path / 'other'}",
    ])
    assert daemon._profile_browser_pid(profile) is None


def test_automation_launch_stops_polling_when_child_exits(monkeypatch, tmp_path):
    profile = tmp_path / "automation-profile"
    profile.mkdir()
    monkeypatch.setattr(daemon, "AUTOMATION_PROFILE", profile)
    monkeypatch.setattr(daemon, "_port_in_use", lambda _port: True)
    monkeypatch.setattr(daemon, "_free_port", lambda: 49231)
    monkeypatch.setattr(daemon, "_automation_chrome_binary", lambda: "/mock/chrome")
    discovery = []
    monkeypatch.setattr(daemon, "_json_version_ws", lambda _port: discovery.append(True))

    class FailedChild:
        pid = 1234

        @staticmethod
        def poll():
            return 1

    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *_args, **_kwargs: FailedChild())

    assert daemon.launch_automation_chrome() is None
    assert discovery == []


def test_automation_launch_requires_launched_pid_and_profile_endpoint(
    monkeypatch, tmp_path
):
    profile = tmp_path / "automation-profile"
    profile.mkdir()
    monkeypatch.setattr(daemon, "AUTOMATION_PROFILE", profile)
    monkeypatch.setattr(daemon, "_port_in_use", lambda _port: True)
    monkeypatch.setattr(daemon, "_free_port", lambda: 49231)
    monkeypatch.setattr(daemon, "_automation_chrome_binary", lambda: "/mock/chrome")
    clock_values = iter([0, 0])
    monkeypatch.setattr(
        daemon, "time", SimpleNamespace(time=lambda: next(clock_values), sleep=lambda _seconds: None)
    )

    class RunningChild:
        pid = 1234

        @staticmethod
        def poll():
            return None

    def spawn(*_args, **_kwargs):
        (profile / "DevToolsActivePort").write_text(
            "49231\n/devtools/browser/launched-profile\n"
        )
        return RunningChild()

    monkeypatch.setattr(daemon.subprocess, "Popen", spawn)
    monkeypatch.setattr(
        daemon, "_endpoint_owned_by_profile",
        lambda _profile, _port, _ws, _snapshot=None, expected_pid=None: expected_pid == 1234,
    )
    monkeypatch.setattr(
        daemon,
        "_json_version_ws",
        lambda _port: "ws://127.0.0.1:49231/devtools/browser/launched-profile",
    )

    assert daemon.launch_automation_chrome() == (
        "ws://127.0.0.1:49231/devtools/browser/launched-profile"
    )


def test_endpoint_ownership_binds_browser_pid_and_listener(monkeypatch, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    portfile = profile / "DevToolsActivePort"
    portfile.write_text("49231\n/devtools/browser/owned\n")
    snapshot = daemon._devtools_active_port_snapshot(profile)
    monkeypatch.setattr(daemon, "_profile_browser_pid", lambda *_args: 4321)
    monkeypatch.setattr(daemon, "_listener_pids", lambda _port: {4321})

    assert daemon._endpoint_owned_by_profile(
        profile, "49231", "ws://127.0.0.1:49231/devtools/browser/owned", snapshot
    )
    assert not daemon._endpoint_owned_by_profile(
        profile, "49231", "ws://127.0.0.2:49231/devtools/browser/owned", snapshot
    )
    monkeypatch.setattr(daemon, "_listener_pids", lambda _port: {9876})
    assert not daemon._endpoint_owned_by_profile(
        profile, "49231", "ws://127.0.0.1:49231/devtools/browser/owned", snapshot
    )


def test_endpoint_ownership_rejects_replaced_active_port_file(monkeypatch, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    portfile = profile / "DevToolsActivePort"
    portfile.write_text("49231\n/devtools/browser/owned\n")
    snapshot = daemon._devtools_active_port_snapshot(profile)
    monkeypatch.setattr(daemon, "_profile_browser_pid", lambda *_args: 4321)
    monkeypatch.setattr(daemon, "_listener_pids", lambda _port: {4321})
    monkeypatch.setattr(daemon, "_ws_matches_devtools_active_port", lambda *_args: True)
    replacement = (snapshot[0], snapshot[1] + 1, *snapshot[2:])
    monkeypatch.setattr(daemon, "_devtools_active_port_snapshot", lambda _base: replacement)

    assert not daemon._endpoint_owned_by_profile(
        profile, "49231", "ws://127.0.0.1:49231/devtools/browser/owned", snapshot
    )


def test_endpoint_ownership_fails_closed_without_listener_identity(monkeypatch, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("49231\n/devtools/browser/owned\n")
    snapshot = daemon._devtools_active_port_snapshot(profile)
    monkeypatch.setattr(daemon, "_listener_pids", lambda _port: set())

    assert not daemon._endpoint_owned_by_profile(
        profile, "49231", "ws://127.0.0.1:49231/devtools/browser/owned", snapshot
    )


def test_windows_endpoint_ownership_uses_listener_pid_and_process_command(monkeypatch, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("49231\n/devtools/browser/owned\n")
    snapshot = daemon._devtools_active_port_snapshot(profile)
    monkeypatch.setattr(daemon.platform, "system", lambda: "Windows")
    monkeypatch.setattr(daemon, "_listener_pids", lambda _port: {55})
    monkeypatch.setattr(
        daemon, "_process_args",
        lambda _pid: [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                      f"--user-data-dir={profile}"],
    )
    monkeypatch.setattr(daemon, "_trusted_browser_executable", lambda _exe: True)

    assert daemon._endpoint_owned_by_profile(
        profile, "49231", "ws://127.0.0.1:49231/devtools/browser/owned", snapshot
    )


@pytest.mark.parametrize(
    "switch",
    [
        "--single-argument",
        "-single-argument",
        "/single-argument",
        "--single-argument=value",
        "-single-argument=value",
        "/single-argument=value",
    ],
)
def test_profile_argument_matches_rejects_preceding_windows_single_argument(
    monkeypatch, tmp_path, switch
):
    monkeypatch.setattr(daemon.platform, "system", lambda: "Windows")
    profile = tmp_path / "profile"

    assert not daemon._profile_argument_matches(
        [switch, f"--user-data-dir={profile}"], profile
    )


@pytest.mark.parametrize("system", ["Darwin", "Linux", "Windows"])
def test_profile_argument_matches_preserves_canonical_argv(monkeypatch, tmp_path, system):
    monkeypatch.setattr(daemon.platform, "system", lambda: system)
    profile = tmp_path / "profile"

    assert daemon._profile_argument_matches(
        ["--remote-debugging-port=49231", f"--user-data-dir={profile}", "--headless"],
        profile,
    )


@pytest.mark.parametrize(
    "switch",
    [
        "--single-argument",
        "-single-argument",
        "/single-argument",
        "--single-argument=value",
        "-single-argument=value",
        "/single-argument=value",
    ],
)
def test_windows_endpoint_ownership_rejects_single_argument_before_profile(
    monkeypatch, tmp_path, switch
):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("49231\n/devtools/browser/owned\n")
    snapshot = daemon._devtools_active_port_snapshot(profile)
    monkeypatch.setattr(daemon.platform, "system", lambda: "Windows")
    monkeypatch.setattr(daemon, "_listener_pids", lambda _port: {55})
    monkeypatch.setattr(
        daemon,
        "_process_args",
        lambda _pid: [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            switch,
            f"--user-data-dir={profile}",
        ],
    )
    monkeypatch.setattr(daemon, "_trusted_browser_executable", lambda _exe: True)

    assert not daemon._endpoint_owned_by_profile(
        profile, "49231", "ws://127.0.0.1:49231/devtools/browser/owned", snapshot
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "ws://127.0.0.1:49231/devtools/browser/owned/extra",
        "ws://127.0.0.1.evil:49231/devtools/browser/owned",
        "ws://127.0.0.1@evil:49231/devtools/browser/owned",
        "ws://127.0.0.1:49231/devtools/browser/owned?next=/devtools/browser/owned",
        "ws://127.0.0.1:49231/devtools/browser/owned#fragment",
    ],
)
def test_endpoint_identity_rejects_ambiguous_host_and_path(monkeypatch, tmp_path, endpoint):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("49231\n/devtools/browser/owned\n")

    assert not daemon._ws_matches_devtools_active_port(profile, "49231", endpoint)

@pytest.mark.parametrize(
    ("executable", "profile_arg", "expected"),
    [("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "match", 77),
     ("/tmp/Google Chrome", "match", None),
     ("/Applications/Google Chrome.app/Contents/MacOS/renamed", "match", None),
     ("/tmp/Google Chrome.app/Contents/MacOS/Google Chrome", "match", None),
     ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "other", None)],
)
def test_profile_browser_pid_rejects_nonbrowser_and_profile_mismatch(
    monkeypatch, tmp_path, executable, profile_arg, expected
):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "SingletonLock").symlink_to("host-77")
    argument = f"--user-data-dir={profile}" if profile_arg == "match" else f"--user-data-dir={tmp_path / 'other'}"
    monkeypatch.setattr(daemon, "_process_args", lambda _pid: [executable, argument])
    monkeypatch.setattr(
        daemon, "_trusted_browser_executable",
        lambda exe: exe == "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )

    assert daemon._profile_browser_pid(profile) == expected


@pytest.mark.parametrize(
    "arguments",
    [
        lambda profile: [f"--title=--user-data-dir={profile}"],
        lambda profile: [f"--user-data-dir={profile}-suffix"],
        lambda profile: [f"--user-data-dir={profile}", f"--user-data-dir={profile}"],
        lambda profile: ["--user-data-dir", str(profile)],
        lambda profile: [f"-user-data-dir={profile}"],
        lambda profile: ["--", f"--user-data-dir={profile}"],
        lambda profile: [f"--USER-DATA-DIR={profile}"],
        lambda profile: [f"--user-data-dir={profile}", f"--USER-DATA-DIR={profile}"],
        lambda profile: [f" --user-data-dir={profile}"],
        lambda profile: [f"--user-data-dir={profile} "],
        lambda profile: ["--user-data-dir", str(profile)],
        lambda profile: [f"/user-data-dir={profile}"],
        lambda profile: [f"/USER-DATA-DIR={profile}"],
        lambda profile: [f"--User-Data-Dir={profile}"],
        lambda profile: [f"--user-data-dir={profile}", f"/user-data-dir={profile}"],
        lambda profile: ["--", f"--user-data-dir={profile}"],
        lambda profile: [f"--app=--user-data-dir={profile}"],
        lambda profile: [f"--app=https://example.test/?profile=--user-data-dir={profile}"],
    ],
)
def test_profile_browser_pid_rejects_ambiguous_or_embedded_profile_switches(
    monkeypatch, tmp_path, arguments
):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "SingletonLock").symlink_to("host-77")
    monkeypatch.setattr(daemon.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        daemon, "_process_args",
        lambda _pid: [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            *arguments(profile),
        ],
    )
    monkeypatch.setattr(daemon, "_trusted_browser_executable", lambda _exe: True)

    assert daemon._profile_browser_pid(profile) is None


def test_profile_browser_pid_rejects_expected_pid_mismatch(monkeypatch, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "SingletonLock").symlink_to("host-77")
    monkeypatch.setattr(
        daemon, "_process_args", lambda _pid: [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"--user-data-dir={profile}",
        ]
    )
    monkeypatch.setattr(daemon, "_trusted_browser_executable", lambda _exe: True)

    assert daemon._profile_browser_pid(profile, expected_pid=78) is None


def test_profile_browser_pid_accepts_canonical_switch_before_terminator(monkeypatch, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "SingletonLock").symlink_to("host-77")
    monkeypatch.setattr(
        daemon, "_process_args", lambda _pid: [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"--user-data-dir={profile}", "--", "--user-data-dir=/tmp/ignored",
        ]
    )
    monkeypatch.setattr(daemon, "_trusted_browser_executable", lambda _exe: True)

    assert daemon._profile_browser_pid(profile) == 77


def test_linux_executable_trust_requires_package_ownership(monkeypatch):
    monkeypatch.setattr(daemon.platform, "system", lambda: "Linux")

    def package_owner(command, **_kwargs):
        if command[0] == "dpkg-query" and command[-1] == "/usr/bin/google-chrome":
            return "google-chrome-stable: /usr/bin/google-chrome"
        raise daemon.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(daemon.subprocess, "check_output", package_owner)
    assert daemon._trusted_browser_executable("/usr/bin/google-chrome")
    assert not daemon._trusted_browser_executable("/tmp/google-chrome")


def test_linux_resolved_chrome_image_requires_google_chrome_package(monkeypatch):
    monkeypatch.setattr(daemon.platform, "system", lambda: "Linux")

    def package_owner(command, **_kwargs):
        if command[0] == "dpkg-query" and command[-1] == "/opt/google/chrome/chrome":
            return "google-chrome-stable: /opt/google/chrome/chrome"
        raise daemon.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(daemon.subprocess, "check_output", package_owner)
    assert daemon._trusted_browser_executable("/opt/google/chrome/chrome")
    assert not daemon._trusted_browser_executable("/opt/google/chrome/powershell")


def test_linux_packaged_brave_alias_is_recognized(monkeypatch):
    monkeypatch.setattr(daemon.platform, "system", lambda: "Linux")

    def package_owner(command, **_kwargs):
        if command[0] == "dpkg-query" and command[-1] == "/usr/bin/brave":
            return "brave-browser: /usr/bin/brave"
        raise daemon.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(daemon.subprocess, "check_output", package_owner)
    assert daemon._trusted_browser_executable("/usr/bin/brave")


@pytest.mark.parametrize(
    ("identifier", "team", "image"),
    [
        ("ai.perplexity.comet", "7S8W4W365S", "Comet"),
        ("ai.perplexity.comet-beta", "7S8W4W365S", "Comet Beta"),
        ("ai.perplexity.comet-canary", "7S8W4W365S", "Comet Canary"),
        ("company.thebrowser.Browser", "S6N382Y83G", "Arc"),
        ("company.thebrowser.dia", "S6N382Y83G", "Dia"),
        ("com.google.Chrome.beta", "EQHXZ8M8AV", "Google Chrome Beta"),
        ("com.google.Chrome.dev", "EQHXZ8M8AV", "Google Chrome Dev"),
        ("com.microsoft.edgemac.canary", "UBF8T346G9", "Microsoft Edge Canary"),
        ("com.brave.Browser.beta", "K8S9R7G5K2", "Brave Browser"),
        ("com.brave.Browser.nightly", "K8S9R7G5K2", "Brave Browser"),
    ],
)
def test_macos_trust_accepts_discovered_browser_identities(
    monkeypatch, identifier, team, image
):
    monkeypatch.setattr(daemon.platform, "system", lambda: "Darwin")

    def codesign(command, **_kwargs):
        if "--verify" in command:
            return SimpleNamespace(returncode=0)
        return f"Identifier={identifier}\nTeamIdentifier={team}\n"

    monkeypatch.setattr(daemon.subprocess, "run", codesign)
    monkeypatch.setattr(daemon.subprocess, "check_output", codesign)
    executable = f"/Applications/{image}.app/Contents/MacOS/{image}"
    assert daemon._trusted_browser_executable(executable)


def test_executable_trust_cache_invalidates_on_in_place_rewrite(tmp_path, monkeypatch):
    executable = tmp_path / "chrome"
    executable.write_bytes(b"AAAA")
    trust_check = MagicMock(side_effect=[True, False])
    monkeypatch.setattr(daemon, "_trusted_browser_executable", trust_check)
    cache = {}

    assert daemon._trusted_browser_executable_cached(str(executable), cache)
    original = executable.stat()
    executable.write_bytes(b"BBBB")
    os.utime(executable, ns=(original.st_atime_ns, original.st_mtime_ns))

    assert not daemon._trusted_browser_executable_cached(str(executable), cache)
    assert trust_check.call_count == 2


def test_explicit_cdp_url_discovers_and_validates_isolated_profile(
    monkeypatch, tmp_path
):
    profile = tmp_path / "isolated" / "chrome-data"
    profile.mkdir(parents=True)
    (profile / "DevToolsActivePort").write_text(
        "49231\n/devtools/browser/isolated-owner\n"
    )
    (profile / "SingletonLock").symlink_to("host-777")
    executable = tmp_path / "chrome"
    executable.write_text("test executable")
    monkeypatch.setattr(daemon, "PROFILES", [])
    monkeypatch.setattr(daemon, "AUTOMATION_PROFILE", tmp_path / "other-profile")
    monkeypatch.setattr(daemon, "_listener_pids", lambda _port: {777})
    monkeypatch.setattr(daemon, "_process_args", lambda _pid: [
        str(executable),
        f"--user-data-dir={profile}", "--remote-debugging-port=49231",
    ])
    trust_check = MagicMock(return_value=True)
    monkeypatch.setattr(daemon, "_trusted_browser_executable", trust_check)
    trust_cache = {}
    snapshots = daemon._http_endpoint_snapshots(
        "http://127.0.0.1:49231", trust_cache
    )
    repeated_snapshots = daemon._http_endpoint_snapshots(
        "http://127.0.0.1:49231", trust_cache
    )
    assert [base for base, _snapshot in snapshots] == [profile.resolve()]
    assert repeated_snapshots == snapshots
    trust_check.assert_called_once_with(str(executable.resolve()))
    assert daemon._http_endpoint_owned(
        "http://127.0.0.1:49231",
        "ws://127.0.0.1:49231/devtools/browser/isolated-owner",
        snapshots,
    )
    assert not daemon._http_endpoint_owned(
        "http://127.0.0.1:49231",
        "ws://127.0.0.1:49231/devtools/browser/foreign-owner",
        snapshots,
    )


def test_explicit_cdp_profile_argument_rejects_relative_path():
    assert daemon._profile_argument_value(["--user-data-dir=relative/profile"]) is None


def test_macos_executable_trust_requires_valid_expected_signer(monkeypatch):
    monkeypatch.setattr(daemon.platform, "system", lambda: "Darwin")

    def codesign(command, **_kwargs):
        if "--verify" in command:
            return SimpleNamespace(returncode=0)
        return "Identifier=com.google.Chrome\nTeamIdentifier=EQHXZ8M8AV\n"

    monkeypatch.setattr(daemon.subprocess, "run", codesign)
    monkeypatch.setattr(daemon.subprocess, "check_output", codesign)
    assert daemon._trusted_browser_executable(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    monkeypatch.setattr(
        daemon.subprocess, "check_output",
        lambda *_args, **_kwargs: "Identifier=com.google.Chrome\nTeamIdentifier=ATTACKER\n",
    )
    assert not daemon._trusted_browser_executable("/tmp/Google Chrome")


@pytest.mark.parametrize(
    ("image", "product", "publisher", "expected"),
    [
        ("chrome.exe", "Google Chrome", "Google LLC", True),
        ("chromium.exe", "Chromium", "Google LLC", True),
        ("brave.exe", "Brave", "Brave Software, Inc.", True),
        ("msedge.exe", "Microsoft Edge", "Microsoft Corporation", True),
        ("powershell.exe", "Windows PowerShell", "Microsoft Corporation", False),
        ("chrome.exe", "Windows PowerShell", "Google LLC", False),
        ("chrome.exe", "Google Chrome", "Attacker LLC", False),
        ("chrome.exe", "Google Chrome", "Google LLC", False),
    ],
)
def test_windows_executable_trust_requires_browser_product_and_valid_publisher(
    monkeypatch, tmp_path, image, product, publisher, expected
):
    monkeypatch.setattr(daemon.platform, "system", lambda: "Windows")
    browser_path = tmp_path / "quotes ' backtick ` semicolon ; pipe |" / image
    observed = {}

    def inspect(command, **kwargs):
        observed["command"] = command
        observed["env_path"] = kwargs["env"]["BH_BROWSER_EXE"]
        return daemon.json.dumps({
            "status": "Valid" if expected else "Invalid",
            "signer": publisher,
            "product": product,
            "description": product,
        })

    monkeypatch.setattr(daemon.subprocess, "check_output", inspect)
    assert daemon._trusted_browser_executable(str(browser_path)) is expected
    assert observed["env_path"] == str(browser_path)
    assert len(observed["command"]) == 5
    assert str(browser_path) not in observed["command"][-1]


@pytest.mark.parametrize("status, expected", [("Valid", True), ("NotSigned", False), ("HashMismatch", False)])
def test_windows_authenticode_status_is_stringified_and_validated(
    monkeypatch, tmp_path, status, expected
):
    monkeypatch.setattr(daemon.platform, "system", lambda: "Windows")
    browser_path = tmp_path / "chrome.exe"
    observed = {}

    def inspect(command, **_kwargs):
        observed["script"] = command[-1]
        return daemon.json.dumps({
            "status": status,
            "signer": "Google LLC",
            "product": "Google Chrome",
            "description": "Google Chrome",
        })

    monkeypatch.setattr(daemon.subprocess, "check_output", inspect)
    assert daemon._trusted_browser_executable(str(browser_path)) is expected
    assert "$s.Status.ToString()" in observed["script"]


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Program Files\Google\Chrome\chrome 'quoted'.exe",
        r"C:\Program Files\Google\Chrome\chrome`&|;().exe",
        r"C:\Browser (Stable)\chrome.exe",
    ],
)
def test_windows_process_lookup_keeps_pid_out_of_powershell_source(monkeypatch, path):
    monkeypatch.setattr(daemon.platform, "system", lambda: "Windows")
    seen = {}

    def query(command, **kwargs):
        seen["command"] = command
        seen["env"] = kwargs["env"]
        return daemon.json.dumps({"exe": path, "command": f'"{path}" --user-data-dir=C:\\profile'})

    # Win32 argument parsing is unavailable here; the lookup must fail closed.
    monkeypatch.setattr(daemon.subprocess, "check_output", query)
    def unavailable_win32(*_args, **_kwargs):
        raise OSError("Win32 APIs unavailable on this host")

    monkeypatch.setattr(daemon.ctypes, "WinDLL", unavailable_win32, raising=False)
    assert daemon._process_args(4242) is None
    assert seen["env"]["BH_PROCESS_PID"] == "4242"
    assert "4242" not in seen["command"]
    assert path not in seen["command"]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ('/Applications/Chrome --user-data-dir=/tmp/automation-profile', True),
        ('/Applications/Chrome --user-data-dir=/tmp/unrelated-profile', False),
    ],
)
def test_profile_process_identity_matches_user_data_dir(monkeypatch, tmp_path, command, expected):
    profile = tmp_path / "automation-profile"
    profile.mkdir()
    monkeypatch.setattr(daemon.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(daemon.os, "readlink", lambda _path: "host-1234")
    monkeypatch.setattr(daemon, "_trusted_browser_executable", lambda _exe: True)
    observed = command.replace("/tmp/automation-profile", str(profile))
    monkeypatch.setattr(
        daemon, "_process_args",
        lambda _pid: [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            observed.split(" ", 1)[1],
        ],
    )
    assert daemon._profile_process_owns(profile) is expected


@pytest.mark.parametrize(
    ("variable", "value", "expected"),
    [
        ("BH_HOME", "/custom/bh", "/custom/bh/chrome-profile"),
        (
            "BROWSER_HARNESS_HOME",
            "/custom/browser-harness",
            "/custom/browser-harness/chrome-profile",
        ),
        ("XDG_CONFIG_HOME", "/custom/config", "/custom/config/browser-harness/chrome-profile"),
    ],
)
def test_default_automation_profile_uses_harness_home(
    monkeypatch, variable, value, expected
):
    from browser_harness import paths

    for key in ("BH_HOME", "BROWSER_HARNESS_HOME", "XDG_CONFIG_HOME", "BH_AUTOMATION_PROFILE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(variable, value)

    assert daemon.automation_profile() == paths.home_dir() / "chrome-profile"
    assert str(daemon.automation_profile()) == expected
