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
         patch("browser_harness.run._print_owner_alias"), \
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
    assert sock.settimeout.call_args_list[0].args == (30.0,)  # the script's call; the captcha note's 2 s probe follows


def test_goto_url_lists_saved_scripts_for_host(ws, monkeypatch):
    monkeypatch.setattr(helpers, "AGENT_WORKSPACE", ws)
    (ws / "scripts" / "example.com").mkdir(parents=True)
    (ws / "scripts" / "example.com" / "top.py").write_text("")
    with patch("browser_harness.helpers.cdp", return_value={"frameId": "f"}):
        assert helpers.goto_url("https://www.example.com/x") == {"frameId": "f", "saved_scripts": ["top"]}


def test_save_rewrites_only_whole_literals_and_keeps_valid_python(ws, tmp_path):
    src = tmp_path / "s.py"
    src.write_text(
        'lang = "python"\n'
        'sel = \'a[href*="python"]\'\n'
        'url = f"https://github.com/trending/{lang}?since=daily"\n'
    )
    assert cli("scripts", "save", "trend", "--file", str(src), "--param", "lang=python")[0] == 0
    saved = (ws / "scripts" / "github.com" / "trend.py").read_text()
    compile(saved, "trend.py", "exec")
    assert "lang = PARAMS['lang']\nsel = 'a[href*=\"python\"]'\n" in saved
    assert "# url: https://github.com/trending/\n" in saved


def test_typed_secret_with_trailing_comment_is_redacted(ws, tmp_path):
    src = tmp_path / "login.py"
    src.write_text('goto_url("https://app.example.com/")\nfill_input("#pw", "hunter2")  # password\n')
    assert cli("scripts", "save", "login", "--file", str(src))[0] == 0
    assert "hunter2" not in (ws / "scripts" / "app.example.com" / "login.py").read_text()


def _expect_line(path):
    return next((l for l in path.read_text().splitlines() if l.startswith("# expect: ")), None)


def test_first_replay_records_output_shape_and_empty_value_drifts(ws, tmp_path):
    # Mirrors the experiment's silent wrong answer: a replay printed top_comment: null
    # for a story whose earlier replays had a comment, and exited 0.
    src = tmp_path / "s.py"
    src.write_text(
        'import json\nurl = "https://news.ycombinator.com/"\n'
        'c = None if PARAMS["broken"] == "1" else "first!"\n'
        'print(json.dumps({"page": 1, "titles": ["a", "b"], "top_comment": c}))\n'
    )
    cli("scripts", "save", "hn", "--file", str(src), "--param", "broken=0")
    path = ws / "scripts" / "news.ycombinator.com" / "hn.py"
    assert _expect_line(path) is None
    assert cli("scripts", "run", "hn")[0] == 0
    assert _expect_line(path) is not None
    assert cli("scripts", "run", "hn")[0] == 0  # same shape still passes

    stamped = path.read_text()
    code, out, err = cli("scripts", "run", "hn", "--param", "broken=1")
    assert code == 1
    assert '"top_comment": null' in out  # output still reaches the caller
    assert "drifted: output changed: output.top_comment is null, was str" in err
    assert "--accept" in err and "hn" in err.splitlines()[-1]
    assert path.read_text() == stamped  # a drifted replay does not re-stamp

    # A legitimately empty value (story with no comments): --accept relaxes only that field.
    code, _, err = cli("scripts", "run", "hn", "--param", "broken=1", "--accept")
    assert code == 0 and "accepted: output check now allows: output.top_comment is null" in err
    assert cli("scripts", "run", "hn", "--param", "broken=1")[0] == 0
    assert cli("scripts", "run", "hn")[0] == 0
    path.write_text(path.read_text().replace('print(json.dumps({"page": 1, "titles": ["a", "b"]', 'print(json.dumps({"page": 1, "titles": []'))
    code, _, err = cli("scripts", "run", "hn")
    assert code == 1 and "output.titles is empty" in err  # the rest of the shape is still enforced


def test_output_check_flags_missing_keys_type_changes_and_empty_lists(ws, tmp_path):
    from browser_harness import scripts

    good = {"q": "x", "repos": [{"repo": "a/b", "stars": 3}], "n": 1}
    exp = scripts.shape(good)
    assert scripts.check_output(exp, {**good, "extra": True, "repos": good["repos"] * 3}) == []
    assert scripts.check_output(exp, {"q": "x", "n": 1}) == ["output.repos is missing"]
    assert scripts.check_output(exp, {**good, "repos": []}) == ["output.repos is empty"]
    assert scripts.check_output(exp, {**good, "n": "1"}) == ["output.n is str, was num"]
    assert scripts.check_output(exp, {**good, "repos": [{"repo": "", "stars": 3}]}) == ["output.repos[0].repo is empty"]
    # A value that was already null when recorded holds nothing to account.
    assert scripts.check_output(scripts.shape({"c": None}), {"c": "now set"}) == []


def test_no_json_output_skips_the_check_and_edited_expect_is_respected(ws, tmp_path):
    src = tmp_path / "s.py"
    src.write_text('url = "https://example.com/"\nprint("plain text")\n')
    cli("scripts", "save", "plain", "--file", str(src))
    path = ws / "scripts" / "example.com" / "plain.py"
    assert cli("scripts", "run", "plain")[0] == 0
    assert _expect_line(path) is None  # nothing to record

    path.write_text(path.read_text().replace("# verified_at:", '# expect: {"t":"obj","keys":{}}\n# verified_at:'))
    code, _, err = cli("scripts", "run", "plain")
    assert code == 1 and "no JSON output" in err

    path.write_text(path.read_text().replace('# expect: {"t":"obj","keys":{}}\n', "# expect: oops\n"))
    code, _, err = cli("scripts", "list")
    assert code != 0 and "bad '# expect:' header line" in err


def test_merge_shapes_keeps_only_what_both_outputs_share():
    from browser_harness import scripts

    old = scripts.shape({"a": "x", "b": [1], "c": "y"})
    merged = scripts.merge_shapes(old, scripts.shape({"a": "", "b": [2, 3]}))
    assert scripts.check_output(merged, {"a": "", "b": [9]}) == []
    assert scripts.check_output(merged, {"a": "z", "b": []}) == ["output.b is empty"]
    assert "c" not in merged["keys"]


def test_from_last_is_per_working_directory(ws, tmp_path, monkeypatch):
    a, b = tmp_path / "agent-a", tmp_path / "agent-b"
    a.mkdir(); b.mkdir()
    monkeypatch.chdir(a)
    assert cli(stdin=SCRIPT)[0] == 0
    monkeypatch.chdir(b)  # another agent on the same daemon, different folder
    assert cli(stdin='url = "https://other.org/"\nprint("b")\n')[0] == 0
    monkeypatch.chdir(a)
    assert cli("scripts", "save", "greet", "--from-last")[0] == 0
    assert (ws / "scripts" / "example.com" / "greet.py").exists()
    assert not (ws / "scripts" / "other.org").exists()


def test_secret_looking_param_is_not_stored_and_is_required(ws, tmp_path):
    src = tmp_path / "s.py"
    src.write_text('url = "https://example.com/login"\npw = "hunter2"\nprint("ok")\n')
    code, _, err = cli("scripts", "save", "login", "--file", str(src), "--param", "password=hunter2", "--param", "passage=x")
    text = (ws / "scripts" / "example.com" / "login.py").read_text()
    assert code == 0 and "hunter2" not in text
    assert '"password": null' in text and '"passage": "x"' in text
    assert "looks secret" in err
    code, _, err = cli("scripts", "run", "login")
    assert code != 0 and "--param password=" in err


def test_accept_without_json_keeps_the_check(ws, tmp_path):
    src = tmp_path / "s.py"
    src.write_text('import json\nurl = "https://example.com/"\nprint(json.dumps({"a": 1}) if PARAMS["state"] != "down" else "outage page")\n')
    cli("scripts", "save", "a", "--file", str(src), "--param", "state=up")
    path = ws / "scripts" / "example.com" / "a.py"
    assert cli("scripts", "run", "a")[0] == 0
    code, _, err = cli("scripts", "run", "a", "--param", "state=down", "--accept")
    assert code == 1 and "needs JSON output" in err
    assert "# expect:" in path.read_text()  # the check is still there


def test_host_qualified_refs_and_hints(ws, tmp_path, monkeypatch):
    for host in ("a.com", "b.com"):
        src = tmp_path / f"{host}.py"
        src.write_text(f'url = "https://{host}/"\nprint("{host}")\n')
        cli("scripts", "save", "top", "--file", str(src))
    assert cli("scripts", "run", "top")[0] != 0  # ambiguous bare name
    assert cli("scripts", "run", "www.A.com/top")[1] == "a.com\n"  # www. and case normalized
    code, _, err = cli("scripts", "run", "www./top")
    assert code != 0 and "bad script name" in err  # never falls back to the bare name
    from browser_harness import helpers
    monkeypatch.setattr(helpers, "AGENT_WORKSPACE", ws)
    assert helpers._saved_scripts("a.com") == ["top"]
    assert helpers._saved_scripts("..\\x") == [] and helpers._saved_scripts("a.com/../b") == []


def test_tee_caps_a_single_huge_write(monkeypatch):
    from io import StringIO
    from browser_harness import scripts
    monkeypatch.setattr(scripts, "_CAPTURE_LIMIT", 10)
    tee = scripts._Tee(StringIO())
    tee.write("x" * 100)
    assert tee.size == 10 and len("".join(tee.buf)) == 10


def test_accepting_an_empty_list_drops_its_item_shape():
    from browser_harness import scripts
    merged = scripts.merge_shapes(scripts.shape({"l": [{"a": 1}]}), scripts.shape({"l": []}))
    assert "item" not in merged["keys"]["l"]
    assert scripts.check_output(merged, {"l": ["anything"]}) == []


def test_stdin_script_ending_in_sys_exit_zero_is_journaled(ws):
    assert cli(stdin='import sys\nurl = "https://example.com/"\nprint("hi")\nsys.exit(0)\n')[0] == 0
    assert cli("scripts", "save", "bye", "--from-last")[0] == 0
    assert (ws / "scripts" / "example.com" / "bye.py").exists()


def test_explicit_zero_ipc_timeout_is_kept(monkeypatch):
    seen = {}
    class C:
        def settimeout(self, t): seen["t"] = t; raise RuntimeError("stop")
        def close(self): pass
    monkeypatch.setattr(helpers.ipc, "connect", lambda *a, **k: (C(), "tok"))
    with pytest.raises(RuntimeError):
        helpers._send({"x": 1}, response_timeout=0)
    assert seen["t"] == 0


def test_secret_params_stay_out_of_telemetry_steps(ws, tmp_path, monkeypatch):
    """Telemetry's cli_event carries helper arguments: a secret passed as --param or BH_PARAMS must not be in them."""
    src = tmp_path / "login.py"
    src.write_text('goto_url("https://app.example.com/login")\nfill_input("#password", "hunter2")\ntype_text(PARAMS["api_key"])\n')
    assert cli("scripts", "save", "login", "--file", str(src), "--param", "api_key=k-1")[0] == 0
    events = []
    monkeypatch.setattr(run.telemetry, "capture_cli_event", lambda **kw: events.append(kw))
    for name in ("goto_url", "fill_input", "type_text"):
        monkeypatch.setattr(run, name, lambda *a, **k: None)
    code, _, err = cli("scripts", "run", "login", "--param", "secret_1=s3cr'et", "--param", "api_key=k-2")
    assert code == 0, err
    steps = repr(events[-1]["steps"])
    assert "s3cr" not in steps and "k-2" not in steps and steps.count("[redacted]") == 2

    monkeypatch.setenv("BH_PARAMS", '{"token": "tok-9", "q": "plain"}')
    assert cli(stdin='type_text(PARAMS["token"])\ntype_text(PARAMS["q"])\n')[0] == 0
    steps = repr(events[-1]["steps"])
    assert "tok-9" not in steps and "plain" in steps


def test_empty_param_value_rewrites_no_literal(ws, tmp_path):
    src = tmp_path / "s.py"
    src.write_text('url = "https://example.com/"\nprint("a", "b", sep="")\n')
    code, _, err = cli("scripts", "save", "s", "--file", str(src), "--param", "q=")
    text = (ws / "scripts" / "example.com" / "s.py").read_text()
    assert code == 0 and 'sep="")' in text and "PARAMS" not in text and "param q: empty value" in err


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_journal_is_owner_only(ws):
    from browser_harness import scripts

    assert cli(stdin=SCRIPT)[0] == 0
    assert scripts.journal_path().stat().st_mode & 0o777 == 0o600
