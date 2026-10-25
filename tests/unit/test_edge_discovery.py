import urllib.error

from browser_harness import admin, daemon


def test_edge_devtools_active_port_falls_back_to_recorded_websocket_on_json_404(tmp_path, monkeypatch):
    (tmp_path / "DevToolsActivePort").write_text(
        "9222\n/devtools/browser/edge-live-session\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(daemon, "PROFILES", [tmp_path])
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    times = iter([0.0, 0.0, 31.0])
    monkeypatch.setattr(daemon.time, "time", lambda: next(times))
    monkeypatch.setattr(daemon.time, "sleep", lambda _seconds: None)

    def json_version_is_hidden(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "http://127.0.0.1:9222/json/version",
            404,
            "Not Found",
            {},
            None,
        )

    monkeypatch.setattr(daemon.urllib.request, "urlopen", json_version_is_hidden)

    assert daemon.get_ws_url() == "ws://127.0.0.1:9222/devtools/browser/edge-live-session"


def test_windows_edge_inspect_opens_with_edge_executable_not_system_chrome_protocol(monkeypatch):
    launches = []
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "subprocess.check_output",
        lambda *_args, **_kwargs: "D:\\Microsoft Edge\\msedge.exe\n",
    )
    monkeypatch.setattr("subprocess.Popen", lambda args, **kwargs: launches.append((args, kwargs)))
    monkeypatch.setattr(
        "webbrowser.open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("system protocol must not be used")),
    )

    admin._open_chrome_inspect()

    assert launches == [
        (["D:\\Microsoft Edge\\msedge.exe", "edge://inspect/#remote-debugging"], {}),
    ]
