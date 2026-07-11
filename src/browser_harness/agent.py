import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MODEL = "gpt-5.4"


@dataclass(frozen=True)
class CodexPaths:
    repo: Path | None
    sdk_src: Path | None
    bin: Path


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_codex_repo() -> Path | None:
    env = os.environ.get("BROWSER_HARNESS_CODEX_REPO") or os.environ.get("BH_CODEX_REPO")
    if env:
        return Path(env).expanduser()
    for name in ("Codex-browser-harness-embed", "Codex"):
        candidate = package_root().parent / name
        if candidate.exists():
            return candidate
    return None


def resolve_codex_paths(args: argparse.Namespace) -> CodexPaths:
    repo = Path(args.codex_repo).expanduser() if args.codex_repo else default_codex_repo()
    sdk_env = args.codex_sdk or os.environ.get("BROWSER_HARNESS_CODEX_SDK") or os.environ.get("BH_CODEX_SDK")
    sdk_src = Path(sdk_env).expanduser() if sdk_env else None
    if sdk_src is None and repo is not None:
        candidate = repo / "sdk" / "python" / "src"
        if candidate.exists():
            sdk_src = candidate

    bin_env = args.codex_bin or os.environ.get("BROWSER_HARNESS_CODEX_BIN") or os.environ.get("BH_CODEX_BIN")
    if bin_env:
        codex_bin = Path(bin_env).expanduser()
    elif repo is not None and (repo / "codex-rs" / "target" / "debug" / "codex").exists():
        codex_bin = repo / "codex-rs" / "target" / "debug" / "codex"
    else:
        raise FileNotFoundError(
            "No integrated Codex fork binary found. Build the fork with "
            "`cd ../Codex-browser-harness-embed/codex-rs && cargo build -p codex-cli`, "
            "or pass --codex-bin /path/to/forked/codex."
        )

    if not codex_bin.exists():
        raise FileNotFoundError(f"Codex binary not found: {codex_bin}")
    return CodexPaths(repo=repo, sdk_src=sdk_src, bin=codex_bin)


def default_run_root() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Path.home() / ".browser-harness" / "agent-runs" / stamp


def _symlink_or_copy(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        return
    try:
        dst.symlink_to(src, target_is_directory=src.is_dir())
    except OSError:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def prepare_workspace(run_root: Path) -> Path:
    root = package_root()
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "agent_outputs").mkdir(exist_ok=True)
    (run_root / "bin").mkdir(exist_ok=True)

    for name in ("agent-workspace", "interaction-skills", "SKILL.md", "install.md"):
        src = root / name
        if src.exists():
            _symlink_or_copy(src, run_root / name)

    wrapper = run_root / "bin" / "browser-harness"
    src_dir = root / "src"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"PYTHONPATH={src_dir!s}${{PYTHONPATH:+:$PYTHONPATH}} "
        f"exec {sys.executable!s} -m browser_harness.run \"$@\"\n"
    )
    wrapper.chmod(0o755)
    (run_root / "AGENTS.md").write_text(build_instructions(run_root))
    return run_root


def build_instructions(run_root: Path) -> str:
    skill_path = package_root() / "SKILL.md"
    skill = skill_path.read_text(errors="replace") if skill_path.exists() else ""
    return f"""You are Browser Harness Agent, a browser automation agent built on the Browser Harness runtime.

Use the bundled browser-harness command from this workspace:

    ./bin/browser-harness <<'PY'
    ensure_real_tab()
    print(page_info())
    PY

For browser tasks, use screenshots first, coordinate clicks by default, and
verify every meaningful browser action with another screenshot or page-info read.
Put durable task deliverables in:

    {run_root / "agent_outputs"}

Do not assume a task succeeded from a command exit alone; inspect browser state or
saved artifacts. If a site requires login or human credentials, stop and explain
what is needed.

Browser-harness reference instructions:

{skill}
"""


def _load_codex_sdk(paths: CodexPaths):
    if paths.sdk_src is not None:
        sys.path.insert(0, str(paths.sdk_src))
    from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox

    return ApprovalMode, Codex, CodexConfig, Sandbox


def run_task(args: argparse.Namespace) -> int:
    paths = resolve_codex_paths(args)
    run_root = prepare_workspace(Path(args.run_root).expanduser() if args.run_root else default_run_root())
    ApprovalMode, Codex, CodexConfig, Sandbox = _load_codex_sdk(paths)
    task = resolved_task(args)

    env = os.environ.copy()
    env["PATH"] = str(run_root / "bin") + os.pathsep + env.get("PATH", "")
    env["BROWSER_HARNESS_AGENT_ROOT"] = str(run_root)
    if paths.sdk_src is not None:
        env["PYTHONPATH"] = str(paths.sdk_src) + os.pathsep + env.get("PYTHONPATH", "")

    approval_mode = ApprovalMode.auto_review if args.approval_mode == "auto-review" else ApprovalMode.deny_all
    sandbox = Sandbox.full_access if args.full_access else Sandbox.workspace_write
    config = CodexConfig(
        codex_bin=str(paths.bin),
        cwd=str(run_root),
        env=env,
        client_name="browser_harness",
        client_title="Browser Harness",
    )

    with Codex(config=config) as codex:
        thread = codex.thread_start(
            approval_mode=approval_mode,
            cwd=str(run_root),
            developer_instructions=build_instructions(run_root),
            model=args.model,
            sandbox=sandbox,
        )
        result = thread.run(task, approval_mode=approval_mode, cwd=str(run_root), sandbox=sandbox)

    if result.final_response:
        print(result.final_response)
    else:
        print("[browser-harness] Codex finished without a final response", file=sys.stderr)
        return 1
    print(f"\n[browser-harness] run root: {run_root}", file=sys.stderr)
    return 0


def launch_tui(args: argparse.Namespace) -> int:
    paths = resolve_codex_paths(args)
    run_root = prepare_workspace(Path(args.run_root).expanduser() if args.run_root else default_run_root())

    env = os.environ.copy()
    env["PATH"] = str(run_root / "bin") + os.pathsep + env.get("PATH", "")
    env["BROWSER_HARNESS_AGENT_ROOT"] = str(run_root)
    if paths.sdk_src is not None:
        env["PYTHONPATH"] = str(paths.sdk_src) + os.pathsep + env.get("PYTHONPATH", "")

    approval = "on-request" if args.approval_mode == "auto-review" else "never"
    sandbox = "danger-full-access" if args.full_access else "workspace-write"
    command = [
        str(paths.bin),
        "-C",
        str(run_root),
        "--add-dir",
        str(package_root()),
        "-m",
        args.model,
        "-s",
        sandbox,
        "-a",
        approval,
    ]
    if args.no_alt_screen:
        command.append("--no-alt-screen")
    if args.task:
        command.append(args.task)

    print(f"[browser-harness] run root: {run_root}", file=sys.stderr)
    return subprocess.call(command, cwd=run_root, env=env)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="browser-harness agent")
    parser.add_argument("task", nargs="?", help="Browser task to run with the embedded Codex fork.")
    parser.add_argument("--task-file", type=Path, help="Read the browser task prompt from this file.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--run-root")
    parser.add_argument("--codex-repo")
    parser.add_argument("--codex-sdk")
    parser.add_argument("--codex-bin")
    parser.add_argument("--approval-mode", choices=("auto-review", "deny-all"), default="auto-review")
    parser.add_argument("--full-access", action="store_true", help="Run Codex with danger-full-access sandbox.")
    return parser


def resolved_task(args: argparse.Namespace) -> str:
    if args.task_file:
        return args.task_file.expanduser().read_text()
    if args.task:
        return args.task
    raise SystemExit("browser-harness agent requires TASK or --task-file")


def build_tui_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="browser-harness tui")
    parser.add_argument("task", nargs="?", help="Optional initial browser task for the TUI.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--run-root")
    parser.add_argument("--codex-repo")
    parser.add_argument("--codex-sdk")
    parser.add_argument("--codex-bin")
    parser.add_argument("--approval-mode", choices=("auto-review", "deny-all"), default="auto-review")
    parser.add_argument("--full-access", action="store_true", help="Run Codex with danger-full-access sandbox.")
    parser.add_argument("--no-alt-screen", action="store_true", help="Keep the TUI in terminal scrollback.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_task(args)


def main_tui(argv: list[str] | None = None) -> int:
    parser = build_tui_parser()
    args = parser.parse_args(argv)
    return launch_tui(args)
