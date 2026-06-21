import stat

import pytest

from browser_harness import local_profiles


def _install(tmp_path, name="Google Chrome"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    browser = tmp_path / "chrome"
    browser.write_text("#!/bin/sh\n")
    browser.chmod(browser.stat().st_mode | stat.S_IXUSR)
    user_data = tmp_path / "User Data"
    user_data.mkdir()
    (user_data / "Local State").write_text(
        '{"profile":{"info_cache":{"Default":{"name":"Greg"},"Profile 1":{"name":"Work"}}}}'
    )
    for profile_dir in ("Default", "Profile 1"):
        profile = user_data / profile_dir
        profile.mkdir()
        (profile / "Preferences").write_text("{}")
    return local_profiles.LocalBrowserInstall(name, browser, user_data)


def test_local_profile_detection_reads_local_state_names_and_stable_ids(tmp_path, monkeypatch):
    install = _install(tmp_path)
    monkeypatch.setattr(local_profiles, "known_local_browser_installs", lambda: [install])

    profiles = local_profiles.detect_local_profiles()

    assert [p.id for p in profiles] == ["google-chrome:Default", "google-chrome:Profile 1"]
    assert profiles[0].profile_name == "Greg"
    assert profiles[1].display_name == "Google Chrome - Work"


def test_local_profile_resolution_requires_exact_id_when_names_collide(tmp_path, monkeypatch):
    chrome = _install(tmp_path / "chrome", "Google Chrome")
    brave = _install(tmp_path / "brave", "Brave")
    monkeypatch.setattr(local_profiles, "known_local_browser_installs", lambda: [chrome, brave])

    with pytest.raises(RuntimeError, match="multiple local profiles matched"):
        local_profiles.resolve_local_profile("Work")

    assert local_profiles.resolve_local_profile("brave:Profile 1").browser_name == "Brave"


def test_default_profile_file_roundtrip(tmp_path, monkeypatch):
    install = _install(tmp_path)
    monkeypatch.setenv("BH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("BH_LOCAL_PROFILE", raising=False)
    monkeypatch.delenv("BH_SELECTED_LOCAL_PROFILE", raising=False)
    monkeypatch.setattr(local_profiles, "known_local_browser_installs", lambda: [install])

    result = local_profiles.set_default_profile_id("google-chrome:Default")

    assert result["default_local_profile_id"] == "google-chrome:Default"
    assert local_profiles.get_default_profile_id() == "google-chrome:Default"


def test_browser_profiles_payload_is_concise_by_default(tmp_path, monkeypatch):
    install = _install(tmp_path)
    monkeypatch.setenv("BH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr(local_profiles, "known_local_browser_installs", lambda: [install])
    local_profiles.set_default_profile_id("google-chrome:Default")

    assert local_profiles.list_browser_profiles_payload() == {
        "selected": "google-chrome:Default",
        "profiles": [
            {
                "id": "google-chrome:Default",
                "label": "Google Chrome - Greg",
                "selected": True,
            },
            {
                "id": "google-chrome:Profile 1",
                "label": "Google Chrome - Work",
                "selected": False,
            },
        ],
    }


def test_default_profile_rejects_missing_browser_binary(tmp_path, monkeypatch):
    install = _install(tmp_path)
    install.browser_path.unlink()
    monkeypatch.setenv("BH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr(local_profiles, "known_local_browser_installs", lambda: [install])

    with pytest.raises(RuntimeError, match="browser binary not found or not executable"):
        local_profiles.set_default_profile_id("google-chrome:Default")


def test_env_selected_profile_overrides_default_file(tmp_path, monkeypatch):
    install = _install(tmp_path)
    monkeypatch.setenv("BH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr(local_profiles, "known_local_browser_installs", lambda: [install])
    local_profiles.set_default_profile_id("google-chrome:Default")

    monkeypatch.setenv("BH_SELECTED_LOCAL_PROFILE", "google-chrome:Profile 1")

    assert local_profiles.get_default_profile_id() == "google-chrome:Profile 1"
