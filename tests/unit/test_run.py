import asyncio
import json
import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from browser_harness import _ipc, daemon, run


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


def test_require_existing_daemon_never_auto_starts(monkeypatch):
    monkeypatch.setenv("BH_REQUIRE_EXISTING_DAEMON", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.require_existing_daemon") as mock_require, \
         patch("browser_harness.run.ensure_daemon") as mock_ensure, \
         patch("browser_harness.run.print_update_banner"):
        run.main()

    mock_require.assert_called_once_with()
    mock_ensure.assert_not_called()


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
    /json/version response with a DevTools WebSocket counts as Chrome."""
    with patch("browser_harness.run.urllib.request.urlopen", side_effect=OSError):
        assert run._local_chrome_listening() is False
    for payload in (b"not JSON", b"{}", b"[]", b'{"webSocketDebuggerUrl": ""}', b'{"webSocketDebuggerUrl": 1}'):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = payload
        with patch("browser_harness.run.urllib.request.urlopen", return_value=response) as mock_open:
            assert run._local_chrome_listening() is False
        assert mock_open.call_count == 2


def test_local_chrome_listening_accepts_devtools_response():
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/x"}'
    with patch("browser_harness.run.urllib.request.urlopen", return_value=response) as mock_open:
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


def test_cli_update_rejects_unknown_flags():
    err = StringIO()
    with patch.object(sys, "argv", ["browser-harness", "--update", "--bogus"]), \
         patch("sys.stderr", err), \
         patch("browser_harness.run.run_update") as m:
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 2
    assert "usage" in err.getvalue().lower()
    m.assert_not_called()


@pytest.mark.parametrize("flag,expected_yes", [(None, False), ("-y", True), ("--yes", True)])
def test_cli_update_forwards_yes_flag(flag, expected_yes):
    argv = ["browser-harness", "--update"] + ([flag] if flag else [])
    with patch.object(sys, "argv", argv), \
         patch("browser_harness.run.run_update", return_value=0) as m:
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 0
    m.assert_called_once_with(yes=expected_yes)


class _OwnedBrowser:
    def __init__(self):
        self.calls = []

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        return {
            "Target.createBrowserContext": {"browserContextId": "owned-ctx"},
            "Target.createTarget": {"targetId": "owned-target"},
            "Target.attachToTarget": {"sessionId": "owned-session"},
            "Target.getTargetInfo": {"targetInfo": {"targetId": "owned-target", "type": "page",
                                                    "url": "about:blank", "title": ""}},
        }.get(method, {})


class _OwnedDaemonWire:
    """Stands in for the daemon socket: each request runs through a real Daemon.handle."""

    def __init__(self, monkeypatch, ping_override=None):
        self.daemon = daemon.Daemon()
        self.daemon.cdp = _OwnedBrowser()
        self.daemon.session, self.daemon.target_id = "user-session", "user-tab"
        self.requests = []
        wire = self

        class Sock:
            def __init__(self):
                self.reply = b""

            def settimeout(self, _t): pass
            def close(self): pass

            def sendall(self, data):
                req = json.loads(data)
                wire.requests.append(req)
                override = ping_override(req) if ping_override and req.get("meta") == "ping" else None
                resp = override if override is not None else asyncio.run(wire.daemon.handle(req))
                self.reply = (json.dumps(resp) + "\n").encode()

            def recv(self, _n):
                out, self.reply = self.reply, b""
                return out

        monkeypatch.setattr(_ipc, "_scope", None)
        monkeypatch.setattr(_ipc, "connect", lambda _name, timeout=1.0: (Sock(), None))

    def log(self):
        return [(r.get("meta") or r.get("method"), "scope" in r) for r in self.requests]

    def cdp_methods(self):
        return [m for m, _, _ in self.daemon.cdp.calls]


def _run_owned(monkeypatch, code, flag="1"):
    monkeypatch.setenv("BH_OWNED_TARGET", flag)
    monkeypatch.setenv("BH_RECORD", "0")
    monkeypatch.delenv("BH_REQUIRE_EXISTING_DAEMON", raising=False)
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO(code)), \
         patch("browser_harness.run.ensure_daemon") as mock_ensure, \
         patch("browser_harness.run.require_existing_daemon") as mock_require, \
         patch("browser_harness.run.print_update_banner"):
        try:
            run._run([])
        finally:
            mock_ensure.assert_not_called()
            mock_require.assert_not_called()


OWNED_BODY = """
try:
    list_tabs()
except RuntimeError as e:
    print("list_tabs:", e)
try:
    switch_tab("user-tab")
except RuntimeError as e:
    print("switch_tab:", e)
print("current_tab:", current_tab()["targetId"])
print("new_tab:", new_tab("https://owned.test/"))
try:
    new_tab("https://second.test/")
except RuntimeError as e:
    print("second new_tab:", e)
"""


def test_owned_target_runs_ping_begin_body_end_without_enumeration(monkeypatch, capsys):
    wire = _OwnedDaemonWire(monkeypatch)

    _run_owned(monkeypatch, OWNED_BODY)

    assert capsys.readouterr().out.splitlines() == [
        "list_tabs: owned-scope: enumeration",
        "switch_tab: owned-scope: foreign-target",
        "current_tab: owned-target",
        "new_tab: owned-target",
        "second new_tab: owned-scope: second-target",
    ]
    assert wire.log() == [
        ("ping", False),
        ("begin_owned_target", False),
        ("Target.getTargets", True),
        ("Runtime.evaluate", True),
        ("Target.attachToTarget", True),
        ("current_tab", True),
        ("claim_owned_page", True),
        ("Page.navigate", True),
        ("claim_owned_page", True),
        ("ping", True),
        ("end_owned_target", True),
    ]
    assert "Target.getTargets" not in wire.cdp_methods()
    assert wire.cdp_methods()[:3] == ["Target.createBrowserContext", "Target.createTarget", "Target.attachToTarget"]
    assert wire.daemon.cdp.calls[-1] == ("Target.disposeBrowserContext", {"browserContextId": "owned-ctx"}, None)
    assert ("Page.navigate", {"url": "https://owned.test/"}, "owned-session") in wire.daemon.cdp.calls
    assert (wire.daemon.session, wire.daemon.target_id) == ("user-session", "user-tab")


def test_owned_target_missing_daemon_runs_nothing(monkeypatch, capsys):
    def refuse(_name, timeout=1.0):
        raise FileNotFoundError("no socket")

    monkeypatch.setattr(_ipc, "_scope", None)
    monkeypatch.setattr(_ipc, "connect", refuse)

    with pytest.raises(SystemExit) as exc:
        _run_owned(monkeypatch, "print('body ran')")

    assert exc.value.code == 1
    assert capsys.readouterr() == ("", "browser-harness: required daemon 'default' is not running\n")


def test_owned_target_old_daemon_without_capability_never_begins(monkeypatch, capsys):
    wire = _OwnedDaemonWire(monkeypatch, ping_override=lambda _req: {"pong": True, "pid": 7, "browser_kind": "local"})

    with pytest.raises(SystemExit) as exc:
        _run_owned(monkeypatch, "print('body ran')")

    assert exc.value.code == 1
    assert capsys.readouterr() == (
        "", "browser-harness: daemon 'default' does not support owned targets; restart it on this version\n")
    assert wire.log() == [("ping", False)]
    assert wire.cdp_methods() == []


@pytest.mark.parametrize("flag", ["true", "0", ""])
def test_owned_target_flag_must_be_exactly_one(monkeypatch, capsys, flag):
    wire = _OwnedDaemonWire(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        _run_owned(monkeypatch, "print('body ran')", flag=flag)

    assert exc.value.code == 1
    assert capsys.readouterr() == ("", 'browser-harness: BH_OWNED_TARGET must be unset or "1"\n')
    assert wire.requests == []


def test_owned_target_refuses_admin_prefix_scripts(monkeypatch, capsys):
    wire = _OwnedDaemonWire(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        _run_owned(monkeypatch, "stop_remote_daemon('x')")

    assert exc.value.code == 1
    assert capsys.readouterr() == ("", "browser-harness: owned-target mode refuses daemon admin scripts\n")
    assert wire.requests == []


def test_owned_target_cleanup_skips_dispose_when_daemon_pid_changed(monkeypatch, capsys):
    wire = _OwnedDaemonWire(
        monkeypatch,
        ping_override=lambda req: {"pong": True, "pid": os.getpid() + 1} if "scope" in req else None,
    )

    with pytest.raises(SystemExit) as exc:
        _run_owned(monkeypatch, "print('body ran')")

    assert exc.value.code == 1
    assert capsys.readouterr() == (
        "body ran\n",
        "browser-harness: owned target cleanup failed: daemon 'default' is not the one that opened the scope\n",
    )
    assert wire.log()[-1] == ("ping", True)
    assert "Target.disposeBrowserContext" not in wire.cdp_methods()


def test_owned_target_sys_exit_survives_cleanup_failure_and_reports_it(monkeypatch, capsys):
    _OwnedDaemonWire(
        monkeypatch,
        ping_override=lambda req: {"pong": True, "pid": os.getpid() + 1} if "scope" in req else None,
    )

    with pytest.raises(SystemExit) as exc:
        _run_owned(monkeypatch, "import sys; sys.exit(3)")

    assert exc.value.code == 3
    assert capsys.readouterr().err == (
        "browser-harness: owned target cleanup failed: daemon 'default' is not the one that opened the scope\n")


def test_owned_target_unbinds_so_post_run_ping_reaches_the_daemon(monkeypatch):
    wire = _OwnedDaemonWire(monkeypatch)

    _run_owned(monkeypatch, "print('body ran')")

    assert run.daemon_browser_kind() == daemon.BROWSER_KIND
    assert wire.log()[-1] == ("ping", False)


def test_owned_target_body_error_keeps_traceback_and_still_ends(monkeypatch):
    wire = _OwnedDaemonWire(monkeypatch)

    with pytest.raises(ValueError, match="boom"):
        _run_owned(monkeypatch, "raise ValueError('boom')")

    assert wire.log()[-2:] == [("ping", True), ("end_owned_target", True)]
    assert wire.cdp_methods()[-1] == "Target.disposeBrowserContext"
