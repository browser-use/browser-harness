import json
import threading
import urllib.request

import pytest

from browser_harness import auth


@pytest.mark.parametrize("raw", ["[]", "null", '"token"', "123"])
def test_load_auth_file_rejects_non_object_json(tmp_path, raw):
    path = tmp_path / "auth.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(auth.AuthError):
        auth.load_auth_file(path)


def test_load_auth_file_accepts_object_and_missing(tmp_path):
    path = tmp_path / "auth.json"
    assert auth.load_auth_file(path) == {}
    path.write_text(json.dumps({"browser_use": {"api_key": "k"}}), encoding="utf-8")
    assert auth.load_auth_file(path) == {"browser_use": {"api_key": "k"}}


def test_stored_auth_record_rejects_non_object_json(tmp_path):
    path = tmp_path / "auth.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(auth.AuthError):
        auth.stored_auth_record(path)


def test_clear_auth_rejects_non_object_json(tmp_path):
    path = tmp_path / "auth.json"
    path.write_text("null", encoding="utf-8")
    with pytest.raises(auth.AuthError):
        auth.clear_auth(path)


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("state=s&code=c", b"You're signed in"),
        ("state=s&error=access_denied", b"Sign-in didn't finish"),
        ("state=wrong&code=c", b"Sign-in didn't finish"),
    ],
)
def test_callback_page_says_whether_sign_in_finished(query, message):
    server = auth._callback_server(auth.PendingCallback(state="s"))
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}{auth.CALLBACK_PATH}?{query}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = resp.read()
    thread.join()
    server.server_close()
    assert message in body, body
