import base64
import os
import sys
from io import StringIO

import pytest

from browser_harness import run, secrets

RFC_SEED = base64.b32encode(b"12345678901234567890").decode()  # RFC 6238 SHA-1 test secret


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BH_HOME", str(tmp_path))
    monkeypatch.delenv("BH_CONFIG_DIR", raising=False)
    return tmp_path


def test_store_roundtrip(store):
    assert secrets.get_secret_value("github.com", "login-password") is None
    secrets.set_secret("github.com", "login-password", "hunter2pass")
    secrets.set_secret("GitHub.com", "github-2fa", RFC_SEED, kind="totp")
    assert secrets.get_secret_value("github.com", "login-password") == "hunter2pass"
    assert secrets.list_secrets() == {
        "github.com": [
            {"name": "github-2fa", "kind": "totp"},
            {"name": "login-password", "kind": "password"},
        ]
    }
    secrets.set_secret("github.com", "login-password", "hunter3")  # overwrite
    assert secrets.get_secret_value("github.com", "login-password") == "hunter3"
    assert secrets.remove_secret("github.com", "login-password") is True
    assert secrets.remove_secret("github.com", "login-password") is False
    assert secrets.get_secret_value("github.com", "login-password") is None


def test_set_validates_inputs(store):
    with pytest.raises(ValueError):
        secrets.set_secret("", "name", "v")
    with pytest.raises(ValueError):
        secrets.set_secret("a.com", "name", "")
    with pytest.raises(ValueError):
        secrets.set_secret("a.com", "name", "v", kind="ssh-key")
    with pytest.raises(ValueError):
        secrets.set_secret("a.com", "otp", "not!base32", kind="totp")
    with pytest.raises(ValueError):
        secrets.set_secret("a.com", "otp", "AAAA", kind="totp")  # < 10 bytes decoded


def test_encrypted_at_rest(store):
    secrets.set_secret("github.com", "login-password", "hunter2pass")
    raw = (store / "secrets-encrypted.json").read_bytes()
    # Value AND metadata live inside the ciphertext blob.
    assert b"hunter2pass" not in raw
    assert b"github.com" not in raw
    assert b"login-password" not in raw


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_secret_files_are_0600(store):
    secrets.set_secret("a.com", "n", "v")
    for name in ("secrets.key", "secrets-encrypted.json"):
        assert os.stat(store / name).st_mode & 0o777 == 0o600, name


def test_corrupt_key_or_data_refuses(store):
    secrets.set_secret("a.com", "n", "keepme")
    (store / "secrets-encrypted.json").write_bytes(b"not json {{{")
    with pytest.raises(RuntimeError):
        secrets.get_secret_value("a.com", "n")
    with pytest.raises(RuntimeError):
        secrets.set_secret("b.com", "n", "new")
    assert (store / "secrets-encrypted.json").read_bytes() == b"not json {{{"  # left intact
    (store / "secrets-encrypted.json").unlink()
    (store / "secrets.key").write_bytes(b"short")  # must not silently mint a new key
    with pytest.raises(RuntimeError):
        secrets.set_secret("a.com", "n", "v")


def test_totp_rfc6238_vectors():
    # RFC 6238 Appendix B (SHA-1, 8 digits) + the 6-digit low-order truncation.
    for t, expected in [(59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"),
                        (1234567890, "89005924"), (2000000000, "69279037"), (20000000000, "65353130")]:
        assert secrets.totp_now(RFC_SEED, at=t, digits=8) == expected
    assert secrets.totp_now(RFC_SEED, at=59) == "287082"
    assert secrets.totp_now(RFC_SEED.lower() + "  ", at=59) == "287082"  # case/whitespace tolerant


def test_domain_match():
    assert secrets.domain_matches("accounts.github.com", "github.com")
    assert secrets.domain_matches("github.com", "github.com")
    assert not secrets.domain_matches("notgithub.com", "github.com")
    assert not secrets.domain_matches("github.com", "accounts.github.com")
    assert secrets.domain_matches("a.b.com", "*.b.com")


def test_helpers_domain_scoping(store, monkeypatch):
    from browser_harness import helpers

    secrets.set_secret("github.com", "login-password", "hunter2pass")
    secrets.set_secret("github.com", "github-2fa", RFC_SEED, kind="totp")
    secrets.set_secret("evil.com", "login-password", "other")

    monkeypatch.setattr(helpers, "page_info", lambda: {"url": "https://accounts.github.com/login"})
    avail = helpers.available_secrets()
    assert {(e["domain"], e["name"], e["kind"]) for e in avail} == {
        ("github.com", "login-password", "password"),
        ("github.com", "github-2fa", "totp"),
    }
    assert all(set(e) == {"domain", "name", "kind"} for e in avail)  # never values
    assert helpers.secret("login-password") == "hunter2pass"
    code = helpers.totp("github-2fa")
    assert code.isdigit() and len(code) == 6
    with pytest.raises(RuntimeError, match="not a TOTP seed"):
        helpers.totp("login-password")

    monkeypatch.setattr(helpers, "page_info", lambda: {"url": "https://notgithub.com/login"})
    with pytest.raises(RuntimeError, match="no secret named"):
        helpers.secret("login-password")

    # No page open: metadata for every domain is visible, but values stay gated.
    monkeypatch.setattr(helpers, "page_info", lambda: (_ for _ in ()).throw(RuntimeError("no daemon")))
    assert {e["domain"] for e in helpers.available_secrets()} == {"github.com", "evil.com"}
    with pytest.raises(RuntimeError, match="no page is open"):
        helpers.secret("login-password")


def test_cli_set_list_remove(store, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", StringIO("hunter2pass\n"))
    assert secrets.run_secrets_cli(["set", "--domain", "github.com", "--name", "login-password", "--stdin"]) == 0
    out = capsys.readouterr().out
    assert "stored" in out and "hunter2pass" not in out

    assert secrets.run_secrets_cli(["list"]) == 0
    out = capsys.readouterr().out
    assert "login-password" in out and "hunter2pass" not in out
    assert secrets.get_secret_value("github.com", "login-password") == "hunter2pass"

    assert secrets.run_secrets_cli(["remove", "--domain", "github.com", "--name", "login-password"]) == 0
    assert "removed" in capsys.readouterr().out
    assert secrets.get_secret_value("github.com", "login-password") is None
    assert secrets.run_secrets_cli(["remove", "--domain", "github.com", "--name", "login-password"]) == 0
    assert "missing" in capsys.readouterr().out


def test_cli_prompts_with_getpass(store, monkeypatch, capsys):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "s3cret-value")
    assert secrets.run_secrets_cli(["set", "--domain", "a.com", "--name", "pw"]) == 0
    assert "s3cret-value" not in capsys.readouterr().out
    assert secrets.get_secret_value("a.com", "pw") == "s3cret-value"


def test_cli_rejects_bad_totp_seed(store, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", StringIO("not!base32\n"))
    assert secrets.run_secrets_cli(["set", "--domain", "a.com", "--name", "otp", "--totp", "--stdin"]) == 1
    assert "base32" in capsys.readouterr().err


def test_run_wiring(store, capsys):
    assert run._telemetry_command(["secrets", "list"]) == "secrets"
    with pytest.raises(SystemExit) as e:
        run._run(["secrets", "list"])
    assert e.value.code == 0
    assert "{}" in capsys.readouterr().out
