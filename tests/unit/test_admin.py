import pytest

from browser_harness import admin


class FakeSocket:
    def __init__(self, response=b'{"target_id":"target-1","session_id":"session-1","page":null}\n'):
        self.response = response
        self.closed = False
        self.sent = b""

    def sendall(self, data):
        self.sent += data

    def recv(self, _size):
        out, self.response = self.response, b""
        return out

    def close(self):
        self.closed = True


def test_local_chrome_mode_is_false_when_env_provides_remote_cdp():
    assert not admin._is_local_chrome_mode({"BU_CDP_WS": "ws://example.test/devtools/browser/1"})


def test_local_chrome_mode_is_false_when_process_env_provides_remote_cdp(monkeypatch):
    monkeypatch.setenv("BU_CDP_WS", "ws://example.test/devtools/browser/1")

    assert not admin._is_local_chrome_mode()


def test_handshake_timeout_needs_chrome_remote_debugging_prompt():
    msg = "CDP WS handshake failed: timed out during opening handshake"

    assert admin._needs_chrome_remote_debugging_prompt(msg)


def test_handshake_403_needs_chrome_remote_debugging_prompt():
    msg = "CDP WS handshake failed: server rejected WebSocket connection: HTTP 403"

    assert admin._needs_chrome_remote_debugging_prompt(msg)


def test_stale_websocket_does_not_open_chrome_inspect():
    msg = "no close frame received or sent"

    assert not admin._needs_chrome_remote_debugging_prompt(msg)


def test_daemon_endpoint_names_discovers_valid_socket_names(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_TMP_DIR", None)  # shared-tmpdir mode
    monkeypatch.setattr(admin.ipc, "_TMP", tmp_path)
    (tmp_path / "bu-default.sock").touch()
    (tmp_path / "bu-remote_1.sock").touch()
    (tmp_path / "bu-invalid.name.sock").touch()
    (tmp_path / "not-bu-default.sock").touch()

    assert admin._daemon_endpoint_names() == ["default", "remote_1"]


def test_daemon_endpoint_names_with_bh_tmp_dir_returns_local_name_when_sock_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_TMP_DIR", str(tmp_path))
    monkeypatch.setattr(admin.ipc, "_TMP", tmp_path)
    monkeypatch.setattr(admin, "NAME", "session-xyz")
    (tmp_path / "bu.sock").touch()

    assert admin._daemon_endpoint_names() == ["session-xyz"]


def test_daemon_endpoint_names_with_bh_tmp_dir_returns_empty_when_sock_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(admin.ipc, "IS_WINDOWS", False)
    monkeypatch.setattr(admin.ipc, "BH_TMP_DIR", str(tmp_path))
    monkeypatch.setattr(admin.ipc, "_TMP", tmp_path)
    monkeypatch.setattr(admin, "NAME", "session-xyz")

    assert admin._daemon_endpoint_names() == []


def test_active_browser_connections_counts_only_healthy_daemons(monkeypatch):
    monkeypatch.setattr(admin, "_daemon_endpoint_names", lambda: ["default", "stale", "remote"])

    def fake_connect(name, timeout=1.0):
        if name == "stale":
            raise ConnectionRefusedError()
        if name == "remote":
            return FakeSocket(b'{"error":"no close frame received or sent"}\n')
        return FakeSocket()

    monkeypatch.setattr(admin.ipc, "connect", fake_connect)

    assert admin.active_browser_connections() == 1


def test_active_browser_connections_skips_daemons_reporting_cdp_disconnected(monkeypatch):
    monkeypatch.setattr(admin, "_daemon_endpoint_names", lambda: ["default", "stale"])

    def fake_connect(name, timeout=1.0):
        if name == "stale":
            return FakeSocket(b'{"error":"cdp_disconnected"}\n')
        return FakeSocket()

    monkeypatch.setattr(admin.ipc, "connect", fake_connect)

    assert admin.active_browser_connections() == 1


def test_browser_connections_returns_attached_page(monkeypatch):
    monkeypatch.setattr(admin, "_daemon_endpoint_names", lambda: ["default"])
    response = (
        b'{"target_id":"target-1","session_id":"session-1",'
        b'"page":{"targetId":"target-1","title":"Cat - Wikipedia","url":"https://en.wikipedia.org/wiki/Cat"}}\n'
    )
    monkeypatch.setattr(admin.ipc, "connect", lambda name, timeout=1.0: FakeSocket(response))

    assert admin.browser_connections() == [
        {
            "name": "default",
            "page": {"title": "Cat - Wikipedia", "url": "https://en.wikipedia.org/wiki/Cat"},
        }
    ]


def test_run_doctor_prints_active_browser_connections_and_active_pages(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda: True)
    monkeypatch.setattr(admin, "browser_connections", lambda: [
        {
            "name": "default",
            "page": {"title": "Example", "url": "https://example.test"},
        },
        {
            "name": "cats",
            "page": {"title": "Cat - Wikipedia", "url": "https://en.wikipedia.org/wiki/Cat"},
        },
    ])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 0

    out = capsys.readouterr().out
    assert "[ok  ] active browser connections — 2" in out
    assert "        default — active page: Example — https://example.test" in out
    assert "        cats — active page: Cat - Wikipedia — https://en.wikipedia.org/wiki/Cat" in out


def test_doctor_page_output_truncates_long_text(monkeypatch, capsys):
    monkeypatch.setattr(admin, "_version", lambda: "0.1.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "git")
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda: True)
    monkeypatch.setattr(admin, "DOCTOR_TEXT_LIMIT", 20)
    monkeypatch.setattr(admin, "browser_connections", lambda: [
        {
            "name": "default",
            "page": {"title": "A very long page title", "url": "https://example.test/very/long/path"},
        }
    ])
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: "0.1.0")
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)

    assert admin.run_doctor() == 0

    out = capsys.readouterr().out
    assert "A very long page ..." in out
    assert "https://example.t..." in out


def test_start_remote_daemon_stops_created_browser_when_daemon_start_fails(monkeypatch):
    calls = []
    browser = {"id": "browser-123", "cdpUrl": "http://127.0.0.1:9333", "liveUrl": "https://live.example"}

    def fake_browser_use(path, method, body=None):
        calls.append((path, method, body))
        if (path, method) == ("/browsers", "POST"):
            return browser
        if (path, method) == ("/browsers/browser-123", "PATCH"):
            return {}
        raise AssertionError((path, method, body))

    monkeypatch.setattr(admin, "daemon_alive", lambda name: False)
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda url: "ws://example.test/devtools/browser/1")
    monkeypatch.setattr(admin, "ensure_daemon", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        admin.start_remote_daemon()

    assert calls == [
        ("/browsers", "POST", {}),
        ("/browsers/browser-123", "PATCH", {"action": "stop"}),
    ]


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
def test_start_remote_daemon_stops_created_browser_when_daemon_start_is_interrupted(monkeypatch, exc_type):
    calls = []
    browser = {"id": "browser-123", "cdpUrl": "http://127.0.0.1:9333", "liveUrl": "https://live.example"}

    def fake_browser_use(path, method, body=None):
        calls.append((path, method, body))
        if (path, method) == ("/browsers", "POST"):
            return browser
        if (path, method) == ("/browsers/browser-123", "PATCH"):
            return {}
        raise AssertionError((path, method, body))

    monkeypatch.setattr(admin, "daemon_alive", lambda name: False)
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda url: "ws://example.test/devtools/browser/1")
    monkeypatch.setattr(admin, "ensure_daemon", lambda **kwargs: (_ for _ in ()).throw(exc_type()))

    with pytest.raises(exc_type):
        admin.start_remote_daemon()

    assert calls == [
        ("/browsers", "POST", {}),
        ("/browsers/browser-123", "PATCH", {"action": "stop"}),
    ]


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
def test_stop_cloud_browser_swallows_baseexception_from_stop_request(monkeypatch, exc_type):
    monkeypatch.setattr(admin, "_browser_use", lambda *args, **kwargs: (_ for _ in ()).throw(exc_type()))

    admin._stop_cloud_browser("browser-123")

def test_start_remote_daemon_does_not_stop_created_browser_on_success(monkeypatch):
    calls = []
    browser = {"id": "browser-123", "cdpUrl": "http://127.0.0.1:9333", "liveUrl": "https://live.example"}

    def fake_browser_use(path, method, body=None):
        calls.append((path, method, body))
        if (path, method) == ("/browsers", "POST"):
            return browser
        raise AssertionError((path, method, body))

    monkeypatch.setattr(admin, "daemon_alive", lambda name: False)
    monkeypatch.setattr(admin, "_browser_use", fake_browser_use)
    monkeypatch.setattr(admin, "_cdp_ws_from_url", lambda url: "ws://example.test/devtools/browser/1")
    monkeypatch.setattr(admin, "ensure_daemon", lambda **kwargs: None)
    monkeypatch.setattr(admin, "_show_live_url", lambda url: None)

    assert admin.start_remote_daemon() == browser
    assert calls == [
        ("/browsers", "POST", {}),
    ]
