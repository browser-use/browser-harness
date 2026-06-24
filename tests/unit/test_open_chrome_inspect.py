"""Regression for #425: the remote-debugging recovery must target the user's
running Chromium browser (Dia/Arc/Edge/Brave/…), not force-open Google Chrome.
"""

import platform as _platform
import subprocess as _subprocess

from browser_harness import admin


def _force_mac_ps(monkeypatch, comm_output):
    monkeypatch.setattr(_platform, "system", lambda: "Darwin")
    monkeypatch.setattr(_subprocess, "check_output", lambda *a, **k: comm_output)


def test_running_chromium_app_prefers_non_chrome(monkeypatch):
    _force_mac_ps(monkeypatch, "Dia\nGoogle Chrome\nFinder\n")
    assert admin._running_chromium_app() == ("Dia", "chrome")


def test_running_chromium_app_edge_uses_edge_scheme(monkeypatch):
    _force_mac_ps(monkeypatch, "Microsoft Edge\n")
    assert admin._running_chromium_app() == ("Microsoft Edge", "edge")


def test_running_chromium_app_falls_back_to_chrome(monkeypatch):
    _force_mac_ps(monkeypatch, "Finder\nSafari\n")
    assert admin._running_chromium_app() == ("Google Chrome", "chrome")


def test_running_chromium_app_none_off_macos(monkeypatch):
    monkeypatch.setattr(_platform, "system", lambda: "Linux")
    assert admin._running_chromium_app() is None


def test_open_inspect_targets_detected_browser(monkeypatch):
    monkeypatch.setattr(admin, "_running_chromium_app", lambda: ("Dia", "chrome"))
    captured = {}
    monkeypatch.setattr(_subprocess, "run", lambda args, **k: captured.setdefault("args", args))
    admin._open_chrome_inspect()
    joined = " ".join(captured.get("args", []))
    assert 'tell application "Dia"' in joined
    assert "chrome://inspect/#remote-debugging" in joined
    assert "Google Chrome" not in joined


def test_open_inspect_edge_uses_edge_scheme(monkeypatch):
    monkeypatch.setattr(admin, "_running_chromium_app", lambda: ("Microsoft Edge", "edge"))
    captured = {}
    monkeypatch.setattr(_subprocess, "run", lambda args, **k: captured.setdefault("args", args))
    admin._open_chrome_inspect()
    joined = " ".join(captured.get("args", []))
    assert 'tell application "Microsoft Edge"' in joined
    assert "edge://inspect/#remote-debugging" in joined
