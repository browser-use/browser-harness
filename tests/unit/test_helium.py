"""Helium is a supported browser, but its profile was absent from the scans."""
import os
from types import SimpleNamespace

import pytest

from browser_harness import admin, daemon


@pytest.fixture
def helium_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon.Path, "home", lambda: tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    profile = tmp_path / "Library/Application Support/net.imput.helium"
    profile.mkdir(parents=True)
    (profile / "Local State").write_text('{}')
    monkeypatch.setattr(daemon, "PROFILES", daemon.profile_dirs())
    return profile


def test_helium_running_without_google_chrome(helium_profile):
    (helium_profile / "SingletonLock").symlink_to(f"test-host-{os.getpid()}")
    assert daemon.supported_browser_running()


def test_helium_directory_alone_is_not_a_running_browser(helium_profile):
    assert not daemon.supported_browser_running()


def test_helium_relaunch_uses_helium_not_chrome(monkeypatch, helium_profile):
    monkeypatch.delenv("BH_CHROME_PATH", raising=False)
    monkeypatch.delenv("CHROME_PATH", raising=False)
    calls = []
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(returncode=0))
    assert admin._launch_browser() == (None, helium_profile)
    assert calls == [["open", "-a", "Helium"]]


@pytest.mark.parametrize("system,profile", [
    ("Darwin", "Library/Application Support/net.imput.helium"),
    ("Linux", ".config/net.imput.helium"),
    ("Linux", ".var/app/net.imput.helium/config/net.imput.helium"),
    ("Windows", "imput/Helium/User Data"),
])
def test_helium_profile_is_scanned_on_every_platform(system, profile):
    assert any(str(p).endswith(profile) for p in daemon.profile_dirs(system))


def test_helium_profile_maps_to_helium_launch_spec():
    assert admin._browser_launch_spec("~/Library/Application Support/net.imput.helium")[0] == "Helium"
