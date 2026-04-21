import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def expected_skill_path(repo: Optional[Path] = None) -> Path:
    return (repo or repo_root()) / "SKILL.md"


def path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def resolve_path(path: Path) -> Optional[str]:
    if not path_exists(path):
        return None
    try:
        return str(path.resolve())
    except OSError:
        return None


def audit_link(path: Path, target: Path) -> dict:
    exists = path_exists(path)
    resolved = resolve_path(path)
    target_resolved = str(target.resolve())
    return {
        "path": str(path),
        "target": str(target),
        "resolved": resolved,
        "status": "ok" if exists and resolved == target_resolved else ("drift" if exists else "missing"),
    }


def audit_claude_import(path: Path, target: Path) -> dict:
    if not path_exists(path):
        return {
            "path": str(path),
            "target": str(target),
            "import_present": False,
            "status": "missing",
        }
    text = path.read_text()
    target_text = str(target)
    import_present = f"@{target_text}" in text or target_text in text
    return {
        "path": str(path),
        "target": target_text,
        "import_present": import_present,
        "status": "ok" if import_present else "drift",
    }


def run_smoke_command(lane: str = "smoke") -> dict:
    env = os.environ.copy()
    env["BU_NAME"] = lane
    try:
        proc = subprocess.run(["browser-harness-smoke", "--json"], capture_output=True, text=True, env=env, timeout=45)
    except (subprocess.TimeoutExpired, TimeoutError):
        return {
            "status": "fail",
            "error_code": "BH-ATTACH-005",
            "error": "browser-harness-smoke timed out after 45s",
            "lane": lane,
            "exit_code": 124,
        }
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    try:
        data = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        data = {
            "status": "fail",
            "error_code": "BH-UNKNOWN-001",
            "error": stdout or stderr or "browser-harness-smoke returned non-JSON output",
        }
    data.setdefault("status", "pass" if proc.returncode == 0 else "fail")
    data.setdefault("lane", lane)
    data["lane"] = lane
    data["exit_code"] = proc.returncode
    if stderr:
        data["stderr"] = stderr
    return data


def collect_local_audit(
    home: Optional[Path] = None,
    repo: Optional[Path] = None,
    smoke_runner: Optional[Callable[[str], dict]] = None,
    lane: str = "smoke",
) -> dict:
    home = home or Path.home()
    repo = repo or repo_root()
    smoke_runner = smoke_runner or run_smoke_command
    skill = expected_skill_path(repo)

    integrations = {
        "hermes": audit_link(home / ".hermes" / "skills" / "software-development" / "browser-harness" / "SKILL.md", skill),
        "claude": audit_claude_import(home / ".claude" / "CLAUDE.md", skill),
        "codex": audit_link(home / ".codex" / "skills" / "browser-harness" / "SKILL.md", skill),
    }

    return {
        "host": platform.node(),
        "repo_root": str(repo),
        "expected_skill": str(skill),
        "command_path": shutil.which("browser-harness"),
        "smoke_command_path": shutil.which("browser-harness-smoke"),
        "integrations": integrations,
        "smoke": smoke_runner(lane),
    }


def canonical_host_tokens(name: Optional[str]) -> set:
    if not name:
        return set()
    raw = str(name).strip().lower()
    tokens = {raw}
    short = raw.split(".")[0]
    tokens.add(short)
    for part in short.replace("_", "-").split("-"):
        if part:
            tokens.add(part)
    if "macbook" in raw or "athame" in raw:
        tokens.add("athame")
    if "mac-mini" in raw or "macmini" in raw or "furnace" in raw:
        tokens.add("furnace")
    return tokens


def is_self_host(host: Optional[str], node_name: Optional[str] = None) -> bool:
    if not host:
        return False
    return bool(canonical_host_tokens(host) & canonical_host_tokens(node_name or platform.node()))


def default_remote_host(node_name: Optional[str] = None) -> str:
    tokens = canonical_host_tokens(node_name or platform.node())
    if "furnace" in tokens:
        return "athame"
    return "furnace"


def resolve_remote_host(remote_host: Optional[str] = None, node_name: Optional[str] = None) -> Optional[str]:
    requested = (remote_host or "").strip()
    if requested and requested.lower() != "auto":
        return requested
    env_remote = (os.environ.get("BROWSER_HARNESS_REMOTE_HOST") or "").strip()
    if env_remote:
        return env_remote
    return default_remote_host(node_name=node_name)


def collect_remote_audit(host: str, repo: Optional[Path] = None, lane: str = "smoke") -> dict:
    repo = repo or repo_root()
    command = [
        "ssh",
        host,
        f"cd {shlex.quote(str(repo))} && python3 rollout_audit.py --json --local-only --lane {shlex.quote(lane)}",
    ]
    proc = subprocess.run(command, capture_output=True, text=True)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
        else:
            local_payload = (payload.get("nodes") or {}).get("local")
            if isinstance(local_payload, dict):
                return local_payload
    if proc.returncode != 0:
        return {
            "host": host,
            "repo_root": str(repo),
            "expected_skill": str(expected_skill_path(repo)),
            "command_path": None,
            "smoke_command_path": None,
            "integrations": {},
            "smoke": {
                "status": "fail",
                "error_code": "BH-REMOTE-900",
                "error": stderr or stdout or f"remote audit failed for {host}",
                "lane": lane,
                "exit_code": proc.returncode,
            },
        }
    payload = json.loads(stdout)
    return payload["nodes"]["local"]


def build_audit(remote_host: Optional[str] = None, lane: str = "smoke", local_only: bool = False) -> dict:
    repo = repo_root()
    chosen_remote = None if local_only else resolve_remote_host(remote_host)
    audit = {
        "repo_root": str(repo),
        "expected_skill": str(expected_skill_path(repo)),
        "remote_host": chosen_remote,
        "nodes": {
            "local": collect_local_audit(repo=repo, lane=lane),
        },
    }
    if chosen_remote and not is_self_host(chosen_remote, audit["nodes"]["local"].get("host")):
        audit["nodes"][chosen_remote] = collect_remote_audit(chosen_remote, repo=repo, lane=lane)
    return audit


def format_text(audit: dict) -> str:
    lines = [
        "BROWSER HARNESS ROLLOUT AUDIT",
        f"repo_root={audit.get('repo_root')}",
        f"expected_skill={audit.get('expected_skill')}",
        f"remote_host={audit.get('remote_host')}",
    ]
    for node_name, node in (audit.get("nodes") or {}).items():
        smoke = node.get("smoke") or {}
        lines.append("")
        lines.append(f"node={node_name} host={node.get('host')}")
        lines.append(f"  browser_harness={node.get('command_path')}")
        lines.append(f"  browser_harness_smoke={node.get('smoke_command_path')}")
        lines.append(f"  smoke={smoke.get('status')} error_code={smoke.get('error_code')}")
        if smoke.get("error"):
            lines.append(f"  smoke_error={smoke.get('error')}")
        for name, integration in (node.get("integrations") or {}).items():
            lines.append(f"  {name}={integration.get('status')} path={integration.get('path')}")
    return "\n".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Audit browser-harness rollout across local and remote nodes")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--remote-host",
        default="auto",
        help="Remote host to audit over ssh (default: auto-switch between athame and furnace; env override: BROWSER_HARNESS_REMOTE_HOST)",
    )
    parser.add_argument("--local-only", action="store_true", help="Only audit the local node")
    parser.add_argument("--lane", default="smoke", help="BU_NAME lane to use for smoke checks")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    audit = build_audit(remote_host=args.remote_host, lane=args.lane, local_only=args.local_only)
    print(json.dumps(audit, indent=2, sort_keys=True) if args.json else format_text(audit))
    failures = [
        node.get("smoke", {}).get("status") == "fail"
        or any(integration.get("status") != "ok" for integration in (node.get("integrations") or {}).values())
        for node in audit.get("nodes", {}).values()
    ]
    return 1 if any(failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
