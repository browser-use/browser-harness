import sys
from io import StringIO
from unittest.mock import patch

import pytest

from browser_harness import run


def test_stdin_executes_code():
    stdout = StringIO()
    fake_stdin = StringIO("print('hello from stdin')")

    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"), \
         patch("sys.stdin", fake_stdin), \
         patch("sys.stdout", stdout):
        run.main()

    assert stdout.getvalue().strip() == "hello from stdin"


def test_c_flag_is_rejected():
    with patch.object(sys, "argv", ["browser-harness", "-c", "print('old path')"]), \
         patch("sys.stdin", StringIO("print('ignored')")):
        try:
            run.main()
        except SystemExit as e:
            assert "browser-harness <<'PY'" in str(e)
        else:
            raise AssertionError("-c should be rejected")


def test_no_args_interactive_stdin_prints_usage():
    fake_stdin = StringIO("")
    fake_stdin.isatty = lambda: True

    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", fake_stdin):
        try:
            run.main()
        except SystemExit as e:
            assert "browser-harness <<'PY'" in str(e)
        else:
            raise AssertionError("interactive no-args invocation should exit with usage")


def test_no_args_empty_stdin_prints_usage():
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("")):
        try:
            run.main()
        except SystemExit as e:
            assert "browser-harness <<'PY'" in str(e)
        else:
            raise AssertionError("empty stdin should exit with usage")


def test_cloud_bootstrap_on_headless_server(monkeypatch):
    """No daemon, no local Chrome, API key + BU_AUTOSPAWN set -> auto-provision cloud daemon."""
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.daemon_alive", return_value=False), \
         patch("browser_harness.run._local_chrome_listening", return_value=False), \
         patch("browser_harness.run.start_remote_daemon") as mock_start, \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"):
        run.main()
    mock_start.assert_called_once()


def test_explicit_bu_cdp_url_blocks_cloud_bootstrap(monkeypatch):
    """BU_CDP_URL is documented to override local Chrome discovery (install.md:58-59),
    so it must also block cloud auto-bootstrap. Otherwise start_remote_daemon would
    overwrite BU_CDP_WS in the daemon env and silently bill the user for a cloud
    browser instead of attaching to their explicit endpoint."""
    monkeypatch.setenv("BU_CDP_URL", "http://127.0.0.1:9333")
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.daemon_alive", return_value=False), \
         patch("browser_harness.run._local_chrome_listening", return_value=False), \
         patch("browser_harness.run.start_remote_daemon") as mock_start, \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"):
        run.main()
    mock_start.assert_not_called()


def test_explicit_bu_cdp_ws_blocks_cloud_bootstrap(monkeypatch):
    """Same precedence guarantee for BU_CDP_WS — install.md:58 promises it overrides
    local Chrome discovery for remote browsers, so cloud auto-bootstrap must defer
    to the explicit WebSocket endpoint the caller already chose."""
    monkeypatch.setenv("BU_CDP_WS", "ws://example.test/devtools/browser/abc")
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.daemon_alive", return_value=False), \
         patch("browser_harness.run._local_chrome_listening", return_value=False), \
         patch("browser_harness.run.start_remote_daemon") as mock_start, \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"):
        run.main()
    mock_start.assert_not_called()


def test_empty_bu_cdp_url_does_not_block_bootstrap(monkeypatch):
    """An env var set to empty string is conventionally treated as unset; the helper
    must not let `BU_CDP_URL=""` accidentally suppress cloud bootstrap on the headless
    fresh-box path #277 explicitly preserved."""
    monkeypatch.setenv("BU_CDP_URL", "")
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.daemon_alive", return_value=False), \
         patch("browser_harness.run._local_chrome_listening", return_value=False), \
         patch("browser_harness.run.start_remote_daemon") as mock_start, \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"):
        run.main()
    mock_start.assert_called_once()


def test_bad_stored_cloud_auth_does_not_bootstrap_or_crash(monkeypatch):
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.daemon_alive", return_value=False), \
         patch("browser_harness.run._local_chrome_listening", return_value=False), \
         patch("browser_harness.run.auth.get_browser_use_api_key", side_effect=run.auth.AuthError("auth file is not valid JSON")), \
         patch("browser_harness.run.start_remote_daemon") as mock_start, \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"):
        run.main()

    mock_start.assert_not_called()


def test_both_bu_cdp_url_and_bu_cdp_ws_set_blocks_bootstrap(monkeypatch):
    """When the caller has BOTH endpoints configured (e.g. a parent agent that probes
    BU_CDP_URL first and falls back to a known BU_CDP_WS), bootstrap must still defer
    — the user has been doubly explicit about their intent."""
    monkeypatch.setenv("BU_CDP_URL", "http://127.0.0.1:9333")
    monkeypatch.setenv("BU_CDP_WS", "ws://example.test/devtools/browser/abc")
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.daemon_alive", return_value=False), \
         patch("browser_harness.run._local_chrome_listening", return_value=False), \
         patch("browser_harness.run.start_remote_daemon") as mock_start, \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"):
        run.main()
    mock_start.assert_not_called()


def test_explicit_endpoint_does_not_break_daemon_alive_short_circuit(monkeypatch):
    """daemon_alive=True must continue to short-circuit auto-bootstrap regardless of
    whether an explicit endpoint is configured — re-using a live daemon was the
    pre-existing fast path and the precedence guard must not regress it."""
    monkeypatch.setenv("BU_CDP_URL", "http://127.0.0.1:9333")
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.daemon_alive", return_value=True), \
         patch("browser_harness.run._local_chrome_listening", return_value=False), \
         patch("browser_harness.run.start_remote_daemon") as mock_start, \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"):
        run.main()
    mock_start.assert_not_called()


def test_explicit_endpoint_does_not_break_local_chrome_short_circuit(monkeypatch):
    """If a local Chrome is already listening on 9222/9223 the bootstrap must skip
    even when the user *also* set an explicit endpoint pointing somewhere else.
    The auto-bootstrap path is for cloud only; routing between local-default and
    explicit-non-default endpoints is handled later in daemon.py:get_ws_url()."""
    monkeypatch.setenv("BU_CDP_URL", "http://127.0.0.1:9333")
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.daemon_alive", return_value=False), \
         patch("browser_harness.run._local_chrome_listening", return_value=True), \
         patch("browser_harness.run.start_remote_daemon") as mock_start, \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"):
        run.main()
    mock_start.assert_not_called()


def test_explicit_cdp_configured_helper_truthy(monkeypatch):
    """Direct unit test of the helper: any non-empty BU_CDP_URL or BU_CDP_WS must
    return True so the bootstrap guard reads as 'caller has been explicit'."""
    for name, value in [
        ("BU_CDP_URL", "http://127.0.0.1:9333"),
        ("BU_CDP_WS", "ws://example.test/devtools/browser/abc"),
        ("BU_CDP_URL", "http://[::1]:9333"),  # IPv6 host
        ("BU_CDP_WS", "wss://cloud.example.com/devtools/browser/x"),  # secure WS
    ]:
        monkeypatch.delenv("BU_CDP_URL", raising=False)
        monkeypatch.delenv("BU_CDP_WS", raising=False)
        monkeypatch.setenv(name, value)
        assert run._explicit_cdp_configured() is True, f"{name}={value!r} should be truthy"


def test_explicit_cdp_configured_helper_falsy(monkeypatch):
    """Helper must return False for unset, empty-string, or both-unset cases —
    those are all 'caller has not chosen an endpoint' from the bootstrap's POV."""
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    assert run._explicit_cdp_configured() is False, "both unset"
    monkeypatch.setenv("BU_CDP_URL", "")
    assert run._explicit_cdp_configured() is False, "BU_CDP_URL empty string"
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setenv("BU_CDP_WS", "")
    assert run._explicit_cdp_configured() is False, "BU_CDP_WS empty string"


def test_local_chrome_listening_rejects_non_chrome():
    """A bare TCP listener on 9222/9223 must not fool the probe — only a real
    /json/version response counts as Chrome."""
    with patch("browser_harness.run.urllib.request.urlopen", side_effect=OSError):
        assert run._local_chrome_listening() is False
    with patch("browser_harness.run.urllib.request.urlopen") as mock_open:
        assert run._local_chrome_listening() is True
        mock_open.assert_called_once()


def test_cli_doctor_fix_snap_invokes_guide():
    with patch.object(sys, "argv", ["browser-harness", "doctor", "--fix-snap"]), \
         patch("browser_harness.run.run_doctor_fix_snap", return_value=0) as m:
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 0
    m.assert_called_once()


def test_cli_doctor_rejects_unknown_flags():
    err = StringIO()
    with patch.object(sys, "argv", ["browser-harness", "doctor", "--bogus"]), patch("sys.stderr", err):
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 2
    assert "usage" in err.getvalue().lower()
