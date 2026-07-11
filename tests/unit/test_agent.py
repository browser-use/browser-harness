from unittest.mock import patch

import pytest

from browser_harness import agent


def test_prepare_workspace_creates_wrapper_and_outputs(tmp_path):
    workspace = agent.prepare_workspace(tmp_path / "run")

    wrapper = workspace / "bin" / "browser-harness"
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111
    assert (workspace / "agent_outputs").is_dir()
    assert (workspace / "AGENTS.md").exists()
    assert "python" in wrapper.read_text()


def test_resolve_codex_paths_prefers_explicit_binary(tmp_path):
    codex_bin = tmp_path / "codex"
    codex_bin.write_text("#!/bin/sh\n")
    codex_bin.chmod(0o755)
    args = agent.build_parser().parse_args(["task", "--codex-bin", str(codex_bin)])

    paths = agent.resolve_codex_paths(args)

    assert paths.bin == codex_bin


def test_resolve_codex_paths_errors_when_no_binary(monkeypatch):
    args = agent.build_parser().parse_args(["task"])
    monkeypatch.delenv("BROWSER_HARNESS_CODEX_BIN", raising=False)
    monkeypatch.delenv("BH_CODEX_BIN", raising=False)

    with patch("browser_harness.agent.default_codex_repo", return_value=None), \
         pytest.raises(FileNotFoundError):
        agent.resolve_codex_paths(args)


def test_build_instructions_points_to_agent_outputs(tmp_path):
    text = agent.build_instructions(tmp_path)

    assert str(tmp_path / "agent_outputs") in text
    assert "./bin/browser-harness" in text


def test_resolved_task_reads_task_file(tmp_path):
    task_file = tmp_path / "prompt.md"
    task_file.write_text("do the browser thing")
    args = agent.build_parser().parse_args(["--task-file", str(task_file)])

    assert agent.resolved_task(args) == "do the browser thing"


def test_launch_tui_uses_fork_binary_and_workspace(tmp_path):
    codex_bin = tmp_path / "codex"
    codex_bin.write_text("#!/bin/sh\n")
    codex_bin.chmod(0o755)
    run_root = tmp_path / "run"
    args = agent.build_tui_parser().parse_args([
        "open example.com",
        "--codex-bin",
        str(codex_bin),
        "--run-root",
        str(run_root),
        "--approval-mode",
        "deny-all",
        "--no-alt-screen",
    ])

    with patch("browser_harness.agent.subprocess.call", return_value=0) as call:
        assert agent.launch_tui(args) == 0

    command = call.call_args.args[0]
    assert command[0] == str(codex_bin)
    assert "-C" in command
    assert str(run_root) in command
    assert "--no-alt-screen" in command
    assert "open example.com" == command[-1]


def test_run_task_prints_final_response(tmp_path, capsys):
    codex_bin = tmp_path / "codex"
    codex_bin.write_text("#!/bin/sh\n")
    codex_bin.chmod(0o755)
    run_root = tmp_path / "run"
    args = agent.build_parser().parse_args([
        "reply ready",
        "--codex-bin",
        str(codex_bin),
        "--run-root",
        str(run_root),
        "--approval-mode",
        "deny-all",
    ])

    class DummyApprovalMode:
        auto_review = object()
        deny_all = object()

    class DummySandbox:
        workspace_write = object()
        full_access = object()

    class DummyCodexConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DummyThread:
        def run(self, *_args, **_kwargs):
            return type("Result", (), {"final_response": "ready"})()

    class DummyCodex:
        def __init__(self, config):
            self.config = config

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def thread_start(self, *_args, **_kwargs):
            return DummyThread()

    with patch("browser_harness.agent._load_codex_sdk", return_value=(DummyApprovalMode, DummyCodex, DummyCodexConfig, DummySandbox)):
        assert agent.run_task(args) == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == "ready"
    assert "[browser-harness] run root:" in captured.err


def test_run_task_fails_when_no_final_response(tmp_path, capsys):
    codex_bin = tmp_path / "codex"
    codex_bin.write_text("#!/bin/sh\n")
    codex_bin.chmod(0o755)
    run_root = tmp_path / "run"
    args = agent.build_parser().parse_args([
        "reply ready",
        "--codex-bin",
        str(codex_bin),
        "--run-root",
        str(run_root),
    ])

    class DummyApprovalMode:
        auto_review = object()
        deny_all = object()

    class DummySandbox:
        workspace_write = object()
        full_access = object()

    class DummyCodexConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DummyThread:
        def run(self, *_args, **_kwargs):
            return type("Result", (), {"final_response": ""})()

    class DummyCodex:
        def __init__(self, config):
            self.config = config

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def thread_start(self, *_args, **_kwargs):
            return DummyThread()

    with patch("browser_harness.agent._load_codex_sdk", return_value=(DummyApprovalMode, DummyCodex, DummyCodexConfig, DummySandbox)):
        assert agent.run_task(args) == 1

    captured = capsys.readouterr()
    assert "finished without a final response" in captured.err
