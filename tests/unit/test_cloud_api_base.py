"""Regression tests for the optional Browser Use cloud API base override."""

from browser_harness import admin, daemon


def test_admin_cloud_api_base_default(monkeypatch):
    monkeypatch.delenv("BROWSER_USE_CLOUD_API_BASE", raising=False)
    assert admin._cloud_api_base() == "https://api.browser-use.com/api/v3"


def test_admin_cloud_api_base_override(monkeypatch):
    monkeypatch.setenv("BROWSER_USE_CLOUD_API_BASE", "https://api.eu.browser-use.com/api/v4/")
    assert admin._cloud_api_base() == "https://api.eu.browser-use.com/api/v4"


def test_daemon_cloud_api_base_default(monkeypatch):
    monkeypatch.delenv("BROWSER_USE_CLOUD_API_BASE", raising=False)
    assert daemon._cloud_api_base() == "https://api.browser-use.com/api/v3"


def test_daemon_cloud_api_base_override(monkeypatch):
    monkeypatch.setenv("BROWSER_USE_CLOUD_API_BASE", "https://api.eu.browser-use.com/api/v4/")
    assert daemon._cloud_api_base() == "https://api.eu.browser-use.com/api/v4"
