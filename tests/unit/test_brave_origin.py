"""Rudi's macOS-only discovery failure; no real browser is launched."""
import os
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from browser_harness import admin, daemon


@pytest.fixture
def origin_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon.Path, "home", lambda: tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    profile = tmp_path / "Library/Application Support/BraveSoftware/Brave-Origin"
    profile.mkdir(parents=True)
    (profile / "Local State").write_text('{}')
    monkeypatch.setattr(daemon, "PROFILES", daemon.profile_dirs())
    return profile


def test_origin_running_without_google_chrome(origin_profile):
    (origin_profile / "SingletonLock").symlink_to(f"test-host-{os.getpid()}")
    assert daemon.supported_browser_running()


def test_origin_directory_alone_is_not_a_running_browser(origin_profile):
    assert not daemon.supported_browser_running()


@pytest.mark.parametrize("status", [404, 403])
def test_origin_port_discovery_keeps_permission_gate(monkeypatch, origin_profile, status):
    (origin_profile / "DevToolsActivePort").write_text("9222\n/devtools/browser/origin\n")
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setattr(daemon, "REMOTE_ID", None)

    def urlopen(url, **kwargs):
        assert url == "http://127.0.0.1:9222/json/version"
        raise HTTPError(url, status, "fixture", {}, None)

    monkeypatch.setattr(daemon.urllib.request, "urlopen", urlopen)
    if status == 403:
        with pytest.raises(RuntimeError, match="permission-blocked"):
            daemon.get_ws_url()
    else:
        assert daemon.get_ws_url() == "ws://127.0.0.1:9222/devtools/browser/origin"


def test_origin_relaunch_uses_origin_not_regular_brave(monkeypatch, origin_profile):
    monkeypatch.delenv("BH_CHROME_PATH", raising=False)
    monkeypatch.delenv("CHROME_PATH", raising=False)
    calls = []
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(returncode=0))
    assert admin._launch_browser() == (None, origin_profile)
    assert calls == [["open", "-a", "Brave Origin"]]


@pytest.mark.parametrize("profile,app", [
    ("BraveSoftware/Brave-Origin", "Brave Origin"),
    ("BraveSoftware/Brave-Browser", "Brave Browser"),
    ("Google/Chrome", "Google Chrome"),
    ("Google/Chrome Canary", "Google Chrome Canary"),
    ("Application Support/Microsoft Edge", "Microsoft Edge"),
])
def test_launch_mapping_preserves_existing_browsers(profile, app):
    assert admin._browser_launch_spec(profile)[0] == app
