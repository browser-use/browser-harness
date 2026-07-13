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


def test_resolve_codex_paths_downloads_prebuilt_when_no_local_build(tmp_path):
    # No submodule and no explicit binary: fall back to the prebuilt download.
    prebuilt = tmp_path / "codex"
    prebuilt.write_text("#!/bin/sh\n")
    prebuilt.chmod(0o755)
    args = agent.build_parser().parse_args(["task"])

    with patch("browser_harness.agent.default_codex_repo", return_value=None), \
         patch("browser_harness.agent.download_prebuilt_agent", return_value=prebuilt) as dl:
        paths = agent.resolve_codex_paths(args)

    dl.assert_called_once()
    assert paths.bin == prebuilt


def test_target_triple_maps_platforms(monkeypatch):
    monkeypatch.setattr(agent.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(agent.platform, "machine", lambda: "arm64")
    assert agent._target_triple() == "aarch64-apple-darwin"
    monkeypatch.setattr(agent.platform, "machine", lambda: "x86_64")
    assert agent._target_triple() == "x86_64-apple-darwin"
    monkeypatch.setattr(agent.platform, "system", lambda: "Linux")
    monkeypatch.setattr(agent.platform, "machine", lambda: "x86_64")
    assert agent._target_triple() == "x86_64-unknown-linux-musl"


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


def test_run_task_streams_fork_exec_transcript(tmp_path):
    codex_bin = tmp_path / "codex"
    codex_bin.write_text("#!/bin/sh\n")
    codex_bin.chmod(0o755)
    run_root = tmp_path / "run"
    out_msg = tmp_path / "final.txt"
    args = agent.build_parser().parse_args([
        "reply ready",
        "--codex-bin",
        str(codex_bin),
        "--run-root",
        str(run_root),
        "--output-last-message",
        str(out_msg),
    ])

    with patch("browser_harness.agent.subprocess.run") as run:
        run.return_value = type("Completed", (), {"returncode": 0})()
        assert agent.run_task(args) == 0

    command = run.call_args.args[0]
    # Drives the fork's exec mode with the JSON event stream (evidence transcript).
    assert command[0] == str(codex_bin)
    assert command[1] == "exec"
    assert "--json" in command
    assert "--output-last-message" in command
    assert str(out_msg) == command[command.index("--output-last-message") + 1]
    # Default (non-sandboxed) is always-allow full access.
    assert "--dangerously-bypass-approvals-and-sandbox" in command
    assert command[-1] == "-"  # prompt over stdin
    assert run.call_args.kwargs["input"] == "reply ready"


def test_run_task_sandboxed_uses_sandbox_and_approval_flags(tmp_path):
    codex_bin = tmp_path / "codex"
    codex_bin.write_text("#!/bin/sh\n")
    codex_bin.chmod(0o755)
    args = agent.build_parser().parse_args([
        "reply ready",
        "--codex-bin",
        str(codex_bin),
        "--run-root",
        str(tmp_path / "run"),
        "--sandboxed",
        "--approval-mode",
        "auto-review",
    ])

    with patch("browser_harness.agent.subprocess.run") as run:
        run.return_value = type("Completed", (), {"returncode": 7})()
        assert agent.run_task(args) == 7  # propagates the fork's exit code

    command = run.call_args.args[0]
    assert "-s" in command and "workspace-write" == command[command.index("-s") + 1]
    assert "-a" in command and "on-request" == command[command.index("-a") + 1]
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
