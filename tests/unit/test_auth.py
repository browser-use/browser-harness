import socket
import threading
import time
import urllib.parse
import urllib.request
from unittest.mock import patch

import pytest

from browser_harness import auth
from browser_harness.auth import (
    AuthError,
    BrowserAuthStart,
    PendingCallback,
    _callback_server,
    complete_browser_auth,
)


def test_callback_server_successful_oauth():
    cb = PendingCallback(state="secret-state")
    server = _callback_server(cb)
    host, port = server.server_address
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()

    url = f"http://{host}:{port}/browser-use-cloud/callback?state=secret-state&code=test-code-123"
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = resp.read().decode("utf-8")
        assert resp.status == 200

    t.join(timeout=2)
    server.server_close()

    assert cb.complete is True
    assert cb.code == "test-code-123"
    assert cb.error is None
    assert "Browser Use Cloud login complete" in body


def test_callback_server_invalid_state():
    cb = PendingCallback(state="secret-state")
    server = _callback_server(cb)
    host, port = server.server_address
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()

    url = f"http://{host}:{port}/browser-use-cloud/callback?state=wrong-state&code=test-code-123"
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = resp.read().decode("utf-8")
        assert resp.status == 200

    t.join(timeout=2)
    server.server_close()

    assert cb.complete is True
    assert cb.code is None
    assert cb.error == "invalid_state"
    assert "Browser Use Cloud login failed" in body
    assert "invalid_state" in body


def test_callback_server_oauth_error():
    cb = PendingCallback(state="secret-state")
    server = _callback_server(cb)
    host, port = server.server_address
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()

    url = f"http://{host}:{port}/browser-use-cloud/callback?state=secret-state&error=access_denied&error_description=User+declined"
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = resp.read().decode("utf-8")
        assert resp.status == 200

    t.join(timeout=2)
    server.server_close()

    assert cb.complete is True
    assert cb.error == "access_denied"
    assert cb.error_description == "User declined"
    assert "Browser Use Cloud login failed" in body
    assert "access_denied" in body


def test_callback_server_preconnect_does_not_block_callback():
    cb = PendingCallback(state="secret-state")
    server = _callback_server(cb)
    host, port = server.server_address

    preconnect = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    preconnect.connect((host, port))

    start = BrowserAuthStart(
        server=server,
        callback=cb,
        redirect_uri=f"http://{host}:{port}/browser-use-cloud/callback",
        verifier="test-verifier",
        auth_url="http://auth.example.com",
        expires_in=600,
        opened=True,
    )

    def send_real_callback():
        time.sleep(0.1)
        url = f"http://{host}:{port}/browser-use-cloud/callback?state=secret-state&code=valid-code"
        with urllib.request.urlopen(url, timeout=5) as resp:
            resp.read()

    sender = threading.Thread(target=send_real_callback, daemon=True)
    sender.start()

    try:
        with patch.object(auth, "_exchange_authorization_code", return_value={"api_key": "bu_test_key_123", "api_key_id": "key-id-1"}):
            with patch.object(auth, "save_auth_record"):
                record = complete_browser_auth(start, timeout=3.0)
                assert record.api_key == "bu_test_key_123"
                assert record.api_key_id == "key-id-1"
    finally:
        preconnect.close()
        sender.join(timeout=2)


def test_complete_browser_auth_timeout():
    cb = PendingCallback(state="secret-state")
    server = _callback_server(cb)
    host, port = server.server_address

    start = BrowserAuthStart(
        server=server,
        callback=cb,
        redirect_uri=f"http://{host}:{port}/browser-use-cloud/callback",
        verifier="test-verifier",
        auth_url="http://auth.example.com",
        expires_in=600,
        opened=True,
    )

    with pytest.raises(AuthError, match="timed out waiting for browser auth callback"):
        complete_browser_auth(start, timeout=0.1)


def test_complete_browser_auth_raises_on_callback_error():
    cb = PendingCallback(state="secret-state", complete=True, error="access_denied", error_description="consent declined")
    server = _callback_server(cb)
    start = BrowserAuthStart(
        server=server,
        callback=cb,
        redirect_uri="http://127.0.0.1:0/callback",
        verifier="verifier",
        auth_url="http://auth.example.com",
        expires_in=600,
        opened=True,
    )

    with pytest.raises(AuthError, match="auth failed: access_denied: consent declined"):
        complete_browser_auth(start)


def test_complete_browser_auth_raises_on_missing_code():
    cb = PendingCallback(state="secret-state", complete=True)
    server = _callback_server(cb)
    start = BrowserAuthStart(
        server=server,
        callback=cb,
        redirect_uri="http://127.0.0.1:0/callback",
        verifier="verifier",
        auth_url="http://auth.example.com",
        expires_in=600,
        opened=True,
    )

    with pytest.raises(AuthError, match="auth callback did not include a code"):
        complete_browser_auth(start)


def test_callback_server_missing_code_renders_failure():
    cb = PendingCallback(state="secret-state")
    server = _callback_server(cb)
    host, port = server.server_address
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()

    url = f"http://{host}:{port}/browser-use-cloud/callback?state=secret-state"
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = resp.read().decode("utf-8")
        assert resp.status == 200

    t.join(timeout=2)
    server.server_close()

    assert cb.complete is True
    assert cb.error == "missing_code"
    assert "Browser Use Cloud login failed" in body
    assert "missing_code" in body


def test_callback_server_duplicate_requests_preserves_first():
    cb = PendingCallback(state="secret-state")
    server = _callback_server(cb)
    host, port = server.server_address

    t1 = threading.Thread(target=server.handle_request, daemon=True)
    t1.start()

    url1 = f"http://{host}:{port}/browser-use-cloud/callback?state=secret-state&code=first-valid-code"
    with urllib.request.urlopen(url1, timeout=5) as resp:
        body1 = resp.read().decode("utf-8")
        assert resp.status == 200

    t1.join(timeout=2)

    t2 = threading.Thread(target=server.handle_request, daemon=True)
    t2.start()

    url2 = f"http://{host}:{port}/browser-use-cloud/callback?state=wrong-state&error=second_error"
    with urllib.request.urlopen(url2, timeout=5) as resp:
        body2 = resp.read().decode("utf-8")
        assert resp.status == 200

    t2.join(timeout=2)
    server.server_close()

    assert cb.complete is True
    assert cb.code == "first-valid-code"
    assert cb.error is None
    assert "Browser Use Cloud login complete" in body1
    assert "Browser Use Cloud login complete" in body2
