"""Helium (net.imput.helium) profile discovery on macOS and Windows; no real browser is launched."""
from urllib.error import HTTPError

import pytest

from browser_harness import daemon


def test_helium_profile_listed_on_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon.Path, "home", lambda: tmp_path)
    assert tmp_path / "Library/Application Support/net.imput.helium" in daemon.profile_dirs("Darwin")


def test_helium_profile_listed_on_windows(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert tmp_path / "imput/Helium/User Data" in daemon.profile_dirs("Windows")


@pytest.mark.parametrize("system,relative", [
    ("Darwin", "Library/Application Support/net.imput.helium"),
    ("Windows", "imput/Helium/User Data"),
])
def test_helium_devtools_active_port_is_discovered(monkeypatch, tmp_path, system, relative):
    """Helium answers 404 on /json/version, so the WS URL must come from DevToolsActivePort."""
    monkeypatch.setattr(daemon.Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    profile = tmp_path / relative
    profile.mkdir(parents=True)
    (profile / "DevToolsActivePort").write_text("9222\n/devtools/browser/helium\n")
    monkeypatch.setattr(daemon, "PROFILES", daemon.profile_dirs(system))
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setattr(daemon, "REMOTE_ID", None)

    def urlopen(url, **kwargs):
        assert url == "http://127.0.0.1:9222/json/version"
        raise HTTPError(url, 404, "fixture", {}, None)

    monkeypatch.setattr(daemon.urllib.request, "urlopen", urlopen)
    assert daemon.get_ws_url() == "ws://127.0.0.1:9222/devtools/browser/helium"
