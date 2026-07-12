import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


# None → let the forked Codex pick its own recommended default model (the
# strongest current model), exactly like real Codex + the browser-harness skill.
DEFAULT_MODEL = None


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
    # browser-env is written by the TUI's /browser picker; sourcing it here lets
    # a backend switch apply to the agent's next browser call without a restart.
    # Benchmark runs (BENCH_TASK_DIR) provide their own instrumented wrapper —
    # delegate to it so recording/cloud isolation apply no matter which wrapper
    # the model invokes.
    wrapper.write_text(
        "#!/bin/sh\n"
        f"[ -f {run_root!s}/browser-env ] && . {run_root!s}/browser-env\n"
        'if [ -n "$BENCH_TASK_DIR" ] && [ -x "$BENCH_TASK_DIR/bin/browser-harness" ] '
        f'&& [ "$BENCH_TASK_DIR/bin/browser-harness" != {str(wrapper)!r} ]; then\n'
        '  exec "$BENCH_TASK_DIR/bin/browser-harness" "$@"\n'
        "fi\n"
        f"PYTHONPATH={src_dir!s}${{PYTHONPATH:+:$PYTHONPATH}} "
        f"exec {sys.executable!s} -m browser_harness.run \"$@\"\n"
    )
    wrapper.chmod(0o755)
    (run_root / "AGENTS.md").write_text(build_instructions(run_root))
    return run_root


def build_instructions(run_root: Path) -> str:
    skill_path = package_root() / "SKILL.md"
    skill = skill_path.read_text(errors="replace") if skill_path.exists() else ""
    # Present the skill exactly as real Codex + the browser-harness skill would,
    # with only the workspace-specific notes prepended. No opinionated workflow
    # guidance here — the skill below is the single source of truth for how to
    # drive the browser, so the fork behaves like Codex-with-the-skill.
    return f"""The browser-harness skill is active. Follow it exactly.

Workspace notes for this run:
- Invoke the harness as `./bin/browser-harness` (the wrapped binary in this
  workspace), not the bare `browser-harness` name.
- Save durable deliverables under `{run_root / "agent_outputs"}`.
- Stored website credentials and 2FA codes are available inside PY scripts via
  `available_secrets()`, `secret(name)`, and `totp(name)`; use one when it
  matches the current page's domain, and never print the values.

{skill}
"""


def _load_codex_sdk(paths: CodexPaths):
    if paths.sdk_src is not None:
        sys.path.insert(0, str(paths.sdk_src))
    from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox

    return ApprovalMode, Codex, CodexConfig, Sandbox


def _browser_label() -> str:
    if os.environ.get("BU_CDP_WS") or os.environ.get("BU_CDP_URL"):
        return "Custom CDP"
    if os.environ.get("BROWSER_USE_API_KEY") and os.environ.get("BU_AUTOSPAWN"):
        return "Browser Use Cloud"
    return "Local Chrome"


def workspace_env(run_root: Path, paths: CodexPaths) -> dict:
    env = os.environ.copy()
    env["PATH"] = str(run_root / "bin") + os.pathsep + env.get("PATH", "")
    env["BROWSER_HARNESS_AGENT_ROOT"] = str(run_root)
    # The TUI's /secrets flows shell out to this exact CLI, and its composer
    # shows the backend name from BH_BROWSER_LABEL.
    env["BROWSER_HARNESS_CLI"] = str(run_root / "bin" / "browser-harness")
    env.setdefault("BH_BROWSER_LABEL", _browser_label())
    if paths.sdk_src is not None:
        env["PYTHONPATH"] = str(paths.sdk_src) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def run_task(args: argparse.Namespace) -> int:
    paths = resolve_codex_paths(args)
    run_root = prepare_workspace(Path(args.run_root).expanduser() if args.run_root else default_run_root())
    task = resolved_task(args)

    env = workspace_env(run_root, paths)

    # Drive the fork's `exec` mode directly rather than the SDK's collect-only
    # run(): this streams the full turn-by-turn transcript (tool calls, command
    # output, agent messages) to stdout, exactly like `codex exec`. Downstream
    # tooling — including the agent benchmark's step/evidence extractor — relies
    # on that transcript; the SDK's final-response-only path starves it.
    approval = "never" if args.approval_mode == "never" else (
        "on-request" if args.approval_mode == "auto-review" else "on-failure"
    )
    sandbox = "workspace-write" if args.sandboxed else "danger-full-access"
    last_message = (
        Path(args.output_last_message).expanduser()
        if getattr(args, "output_last_message", None)
        else run_root / "final_message.txt"
    )
    command = [
        str(paths.bin),
        "exec",
        "--json",
        "--skip-git-repo-check",
        "-C",
        str(run_root),
        "--add-dir",
        str(package_root()),
        "--output-last-message",
        str(last_message),
    ]
    # Only pin a model when the caller explicitly asked; otherwise use Codex's
    # own recommended default (the strongest current model), matching how real
    # Codex + the browser-harness skill runs.
    if args.model:
        command.extend(["-m", args.model])
    if args.sandboxed:
        command.extend(["-s", sandbox, "-a", approval])
    else:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    command.append("-")  # read the prompt from stdin

    # Keep stderr clean: the fork's `exec --json` puts the whole transcript on
    # stdout and nothing on stderr, so downstream extractors that prefer stderr
    # (e.g. the agent benchmark) fall through to the rich stdout stream. Emitting
    # a run-root banner here would shadow that transcript.
    completed = subprocess.run(command, input=task, text=True, cwd=run_root, env=env)
    return completed.returncode


def launch_tui(args: argparse.Namespace) -> int:
    paths = resolve_codex_paths(args)
    run_root = prepare_workspace(Path(args.run_root).expanduser() if args.run_root else default_run_root())

    env = workspace_env(run_root, paths)

    approval = "on-request" if args.approval_mode == "auto-review" else "never"
    sandbox = "workspace-write" if args.sandboxed else "danger-full-access"
    command = [
        str(paths.bin),
        "-C",
        str(run_root),
        "--add-dir",
        str(package_root()),
        "-s",
        sandbox,
        "-a",
        approval,
    ]
    if args.model:
        command.extend(["-m", args.model])
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
    # Always-allow by default: the workspace is generated by browser-harness and
    # the agent's job is driving the browser, so no approval prompts.
    parser.add_argument("--approval-mode", choices=("never", "auto-review", "deny-all"), default="never")
    parser.add_argument("--sandboxed", action="store_true", help="Constrain to the workspace-write sandbox (default: full access, never ask).")
    parser.add_argument("--full-access", action="store_true", help=argparse.SUPPRESS)  # legacy no-op; full access is the default
    parser.add_argument("--output-last-message", help="Write the agent's final message to this file (default: <run-root>/final_message.txt).")
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
    # Always-allow by default: the workspace is generated by browser-harness and
    # the agent's job is driving the browser, so no approval prompts.
    parser.add_argument("--approval-mode", choices=("never", "auto-review", "deny-all"), default="never")
    parser.add_argument("--sandboxed", action="store_true", help="Constrain to the workspace-write sandbox (default: full access, never ask).")
    parser.add_argument("--full-access", action="store_true", help=argparse.SUPPRESS)  # legacy no-op; full access is the default
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
