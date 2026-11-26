import asyncio
import json
import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from browser_harness import _ipc, daemon, run



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
        "new_tab: owned-target https://owned.test/",  # v0.1.15 new_tab() prints its own line
        "new_tab: owned-target",
        "second new_tab: owned-scope: second-target",
    ]
    # v0.1.15 list_tabs()/switch_tab() use owner metas; the scope refuses them on the wire.
    assert wire.log() == [
        ("ping", False),
        ("begin_owned_target", False),
        ("tabs", True),
        ("switch_tab", True),
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


def test_owned_target_keeps_scope_bound_and_post_run_ping_is_unscoped(monkeypatch):
    wire = _OwnedDaemonWire(monkeypatch)

    _run_owned(monkeypatch, "print('body ran')")

    assert _ipc.scope_bound()
    assert run.daemon_browser_kind() == daemon.BROWSER_KIND
    assert wire.log()[-1] == ("ping", False)
    # Late helper-style CDP still stamps the closed lease (refused), never unscoped.
    c, token = _ipc.connect("default")
    closed = _ipc.request(c, token, {"method": "Target.getTargets", "params": {}})
    c.close()
    assert closed == {"error": "owned-scope: scope-closed"}
    assert wire.log()[-1] == ("Target.getTargets", True)


def test_owned_target_body_error_keeps_traceback_and_still_ends(monkeypatch):
    wire = _OwnedDaemonWire(monkeypatch)

    with pytest.raises(ValueError, match="boom"):
        _run_owned(monkeypatch, "raise ValueError('boom')")

    assert wire.log()[-2:] == [("ping", True), ("end_owned_target", True)]
    assert wire.cdp_methods()[-1] == "Target.disposeBrowserContext"
