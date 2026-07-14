import pytest

from browser_harness import daemon


def test_cloud_only_rejects_local_cdp_ws(monkeypatch):
    monkeypatch.setenv("BH_CLOUD_ONLY", "1")
    monkeypatch.setenv("BU_CDP_WS", "ws://127.0.0.1:9222/devtools/browser/local")
    monkeypatch.delenv("BU_CDP_URL", raising=False)

    with pytest.raises(RuntimeError, match="refuses local BU_CDP_WS"):
        daemon.get_ws_url()


def test_cloud_only_rejects_local_cdp_url(monkeypatch):
    monkeypatch.setenv("BH_CLOUD_ONLY", "1")
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.setenv("BU_CDP_URL", "http://localhost:9222")

    with pytest.raises(RuntimeError, match="refuses local BU_CDP_URL"):
        daemon.get_ws_url()


def test_cloud_only_requires_remote_ws_instead_of_profile_discovery(monkeypatch):
    monkeypatch.setenv("BH_CLOUD_ONLY", "1")
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)

    with pytest.raises(RuntimeError, match="requires Browser Use Cloud"):
        daemon.get_ws_url()


def test_cloud_only_allows_remote_cdp_ws(monkeypatch):
    monkeypatch.setenv("BH_CLOUD_ONLY", "1")
    monkeypatch.setenv("BU_CDP_WS", "wss://cloud.example.test/devtools/browser/abc")
    monkeypatch.delenv("BU_CDP_URL", raising=False)

    assert daemon.get_ws_url() == "wss://cloud.example.test/devtools/browser/abc"
