import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from browser_harness import helpers, run


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("BH_AGENT_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("BH_RUNTIME_DIR", str(tmp_path / "rt"))
    monkeypatch.setenv("BH_TELEMETRY", "0")
    for name in ("BH_PARAMS", "BU_NAME", "BU_AUTOSPAWN", "BH_REQUIRE_EXISTING_DAEMON"):
        monkeypatch.delenv(name, raising=False)
    # `scripts run` mutates these for the rest of its process; restore them per test.
    monkeypatch.setattr(helpers, "DEFAULT_IPC_RESPONSE_TIMEOUT_SECONDS", helpers.DEFAULT_IPC_RESPONSE_TIMEOUT_SECONDS)
    monkeypatch.setattr(helpers, "SAVED_SCRIPT_HINTS", True)
    return tmp_path / "ws"


def cli(*argv, stdin=""):
    out, err = StringIO(), StringIO()
    code = 0
    # patch.dict: `scripts run` exports BH_PARAMS for the script's child processes.
    with patch.object(sys, "argv", ["browser-harness", *argv]), patch.dict("os.environ"), \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.run.print_update_banner"), \
         patch("sys.stdin", StringIO(stdin)), \
         patch("sys.stdout", out), \
         patch("sys.stderr", err):
        try:
            run.main()
        except SystemExit as e:
            code = run._exit_code(e.code)
            if isinstance(e.code, str):
                err.write(e.code)
    return code, out.getvalue(), err.getvalue()


SCRIPT = 'new_tab_url = "https://www.example.com/search"\nprint("hello world")\n'


def test_save_from_last_then_run_with_new_param_stamps_verified(ws):
    assert cli(stdin=SCRIPT)[0] == 0
    code, out, _ = cli("scripts", "save", "greet", "--from-last", "--param", "q=hello world")
    assert code == 0
    path = ws / "scripts" / "example.com" / "greet.py"
    assert out.strip() == f"saved {path}"
    assert "# verified_at: never" in path.read_text()

    code, out, err = cli("scripts", "run", "greet", "--param", "q=bye")
    assert (code, out, err) == (0, "bye\n", "")
    assert "# verified_at: never" not in path.read_text()

    # Header default is used when no --param is given.
    assert cli("scripts", "run", "example.com/greet")[1] == "hello world\n"


def test_failed_stdin_script_is_not_saved_as_last(ws):
    assert cli(stdin=SCRIPT)[0] == 0
    with pytest.raises(ZeroDivisionError):
        cli(stdin='print("https://x.org/")\n1/0\n')
    cli("scripts", "save", "greet", "--from-last")
    assert (ws / "scripts" / "example.com" / "greet.py").exists()


def test_drift_prints_error_exits_nonzero_and_keeps_unverified(ws, tmp_path):
    src = tmp_path / "s.py"
    src.write_text('url = "https://news.ycombinator.com/"\nassert int(PARAMS["n"]) < 2, "no rows"\n')
    cli("scripts", "save", "top", "--file", str(src), "--param", "n=1")
    code, _, err = cli("scripts", "run", "top", "--param", "n=2")
    assert code == 1
    assert "drifted: AssertionError: no rows" in err.splitlines()[-2]
    assert "news.ycombinator.com/top" in err.splitlines()[-1]
    assert "# verified_at: never" in (ws / "scripts" / "news.ycombinator.com" / "top.py").read_text()


def test_bh_params_reaches_stdin_scripts(ws, monkeypatch):
    monkeypatch.setenv("BH_PARAMS", '{"q": "x"}')
    assert cli(stdin='print(PARAMS["q"])')[1] == "x\n"


def test_typed_secret_is_redacted_and_required_on_run(ws, tmp_path):
    src = tmp_path / "login.py"
    src.write_text('goto_url("https://app.example.com/login?token=abc123")\nfill_input("#password", "hunter2")\n')
    code, _, err = cli("scripts", "save", "login", "--file", str(src))
    saved = (ws / "scripts" / "app.example.com" / "login.py").read_text()
    assert code == 0 and "hunter2" not in saved and "abc123" not in saved
    assert 'fill_input("#password", PARAMS[\'secret_1\'])' in saved
    code, _, err = cli("scripts", "run", "login")
    assert code == 1 and "--param secret_1=..." in err


def test_list_filters_by_host(ws, tmp_path):
    for url, name in (("https://a.com/", "one"), ("https://b.com/", "two")):
        src = tmp_path / f"{name}.py"
        src.write_text(f'goto_url("{url}")\n')
        cli("scripts", "save", name, "--file", str(src))
    _, out, _ = cli("scripts", "list", "--host", "www.b.com")
    assert out.startswith("b.com/two  params={}  verified_at=never") and "a.com" not in out


def test_replay_raises_default_ipc_timeout(ws, tmp_path):
    src = tmp_path / "s.py"
    src.write_text('cdp("Page.enable")\n')
    cli("scripts", "save", "slow", "--file", str(src), "--host", "example.com")
    sock = MagicMock()
    with patch.object(helpers.ipc, "connect", return_value=(sock, None)), \
         patch.object(helpers.ipc, "request", return_value={"result": {}}):
        assert cli("scripts", "run", "slow")[0] == 0
    sock.settimeout.assert_called_once_with(30.0)


def test_goto_url_lists_saved_scripts_for_host(ws, monkeypatch):
    monkeypatch.setattr(helpers, "AGENT_WORKSPACE", ws)
    (ws / "scripts" / "example.com").mkdir(parents=True)
    (ws / "scripts" / "example.com" / "top.py").write_text("")
    with patch("browser_harness.helpers.cdp", return_value={"frameId": "f"}):
        assert helpers.goto_url("https://www.example.com/x") == {"frameId": "f", "saved_scripts": ["top"]}
