import json
import stat
import threading
import urllib.error
import urllib.request
from io import StringIO

import pytest

from browser_harness import auth


def test_get_api_key_prefers_env_over_stored(monkeypatch, tmp_path):
    monkeypatch.setenv("BH_AUTH_PATH", str(tmp_path / "auth.json"))
    auth.save_auth_record(auth.AuthRecord(api_key="stored-key", source="oauth"))
    monkeypatch.setenv("BROWSER_USE_API_KEY", "env-key")

    assert auth.get_browser_use_api_key() == "env-key"


def test_status_and_logout_for_stored_key(monkeypatch, tmp_path):
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)
    monkeypatch.setenv("BH_AUTH_PATH", str(tmp_path / "auth.json"))
    auth.save_auth_record(auth.AuthRecord(
        api_key="secret-key",
        api_key_id="key-123",
        project_id="project-123",
        scopes=["browser"],
    ))

    status = auth.auth_status()
    mode = stat.S_IMODE((tmp_path / "auth.json").stat().st_mode)
    removed = auth.clear_auth()

    assert status["status"] == "authenticated"
    assert status["source"] == "stored"
    assert "api_key" not in status
    assert "api_key_id" not in status
    assert mode == 0o600
    assert removed is True
    assert auth.auth_status()["status"] == "missing"


def test_missing_key_raises_cloud_auth_required(monkeypatch, tmp_path):
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)
    monkeypatch.setenv("BH_AUTH_PATH", str(tmp_path / "missing.json"))

    try:
        auth.get_browser_use_api_key()
    except auth.CloudAuthRequired as e:
        assert "browser-harness auth login" in str(e)
    else:
        raise AssertionError("expected CloudAuthRequired")


def test_api_key_stdin_login_stores_manual_key_without_printing(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)
    monkeypatch.setenv("BH_AUTH_PATH", str(tmp_path / "auth.json"))
    manual_key = "manual-key-1234567890abcdef"

    record = auth.api_key_stdin_login(input_stream=StringIO(manual_key + "\n"))
    out = capsys.readouterr().out

    assert record.source == "manual"
    assert auth.get_browser_use_api_key() == manual_key
    assert manual_key not in out
    assert "stored" in out.lower()
    assert json.loads((tmp_path / "auth.json").read_text())["browser_use"]["source"] == "manual"


def test_api_key_stdin_json_login_outputs_no_secret(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)
    monkeypatch.setenv("BH_AUTH_PATH", str(tmp_path / "auth.json"))
    manual_key = "manual-key-1234567890abcdef"

    auth.api_key_stdin_login(json_output=True, input_stream=StringIO(manual_key + "\n"))
    out = capsys.readouterr().out

    assert manual_key not in out
    assert json.loads(out) == {"status": "stored", "path": str(tmp_path / "auth.json")}


def test_api_key_stdin_login_rejects_missing_or_short_key(monkeypatch, tmp_path):
    monkeypatch.setenv("BH_AUTH_PATH", str(tmp_path / "auth.json"))

    for raw in ["", "too-short"]:
        try:
            auth.api_key_stdin_login(input_stream=StringIO(raw))
        except auth.AuthError as e:
            assert "API key" in str(e) or "api key" in str(e)
        else:
            raise AssertionError("expected AuthError")

    assert not (tmp_path / "auth.json").exists()


def test_manual_api_key_tty_eof_becomes_auth_error(monkeypatch):
    class TtyInput:
        def isatty(self):
            return True

    def fake_getpass(_prompt):
        raise EOFError

    monkeypatch.setattr(auth.getpass, "getpass", fake_getpass)

    with pytest.raises(auth.AuthError, match="no API key provided"):
        auth._read_manual_api_key(TtyInput())


def test_post_json_network_error_becomes_auth_error(monkeypatch):
    def fake_urlopen(_req, timeout):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(auth.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(auth.AuthError, match="network error: offline"):
        auth._post_json("https://api.example.test/auth", {"x": 1})


def test_browser_login_callback_exchanges_and_stores_key(monkeypatch, tmp_path):
    monkeypatch.setenv("BH_AUTH_PATH", str(tmp_path / "auth.json"))
    calls = []

    def fake_post(url, payload):
        calls.append((url, payload))
        if url.endswith("/cloud/cli-auth/browser"):
            return {"authorization_uri": "https://login.example/auth", "expires_in": 600}
        if url.endswith("/cloud/cli-auth/token"):
            return {
                "api_key": "oauth-key",
                "api_key_id": "key-id",
                "project_id": "project-id",
                "scopes": ["browser"],
            }
        raise AssertionError(url)

    monkeypatch.setattr(auth, "_post_json", fake_post)
    start = auth.start_browser_auth(open_url=False)
    callback_url = f"{start.redirect_uri}?code=abc123&state={start.callback.state}"
    t = threading.Thread(target=lambda: urllib.request.urlopen(callback_url, timeout=5).read())
    t.start()
    record = auth.complete_browser_auth(start, timeout=5)
    t.join(timeout=5)

    assert record.api_key == "oauth-key"
    assert auth.get_browser_use_api_key() == "oauth-key"
    assert calls[0][1]["client_id"] == "browser-use-terminal"
    assert calls[0][1]["redirect_uri"] == start.redirect_uri
    assert calls[0][1]["state"] == start.callback.state
    assert calls[1][1]["code"] == "abc123"
    assert calls[1][1]["code_verifier"] == start.verifier
    assert json.loads((tmp_path / "auth.json").read_text())["browser_use"]["api_key_id"] == "key-id"


def test_device_login_polls_and_stores_key(monkeypatch, tmp_path):
    monkeypatch.setenv("BH_AUTH_PATH", str(tmp_path / "auth.json"))
    token_attempts = []

    def fake_post(url, payload):
        if url.endswith("/cloud/cli-auth/device"):
            return {
                "device_code": "device-123",
                "user_code": "USER-123",
                "verification_uri": "https://login.example/device",
                "interval": 1,
                "expires_in": 60,
            }
        if url.endswith("/cloud/cli-auth/token"):
            token_attempts.append(payload)
            if len(token_attempts) == 1:
                raise auth.AuthError("authorization_pending")
            return {"api_key": "device-key", "api_key_id": "device-key-id"}
        raise AssertionError(url)

    monkeypatch.setattr(auth, "_post_json", fake_post)
    monkeypatch.setattr(auth.time, "sleep", lambda _seconds: None)

    start = auth.start_device_auth(open_url=False)
    record = auth.complete_device_auth(start, timeout=5)

    assert record.api_key == "device-key"
    assert token_attempts[0]["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code"
    assert auth.get_browser_use_api_key() == "device-key"
