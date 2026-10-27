import json

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
