#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path("/Users/odinbot33/Developer/browser-harness")
REPORT_DIR = REPO_ROOT / ".hermes" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CmdResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def run(command: str, timeout: int = 180) -> CmdResult:
    proc = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )
    return CmdResult(
        command=command,
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def parse_json(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    return json.loads(text)


def write_text(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return str(path)


def tail_result(command: str, path: Path) -> dict[str, Any]:
    result = run(command, timeout=60)
    write_text(path, result.stdout + ("\n[stderr]\n" + result.stderr if result.stderr else ""))
    return result.to_dict() | {"artifact": str(path)}


now = datetime.now().astimezone()
stamp = now.strftime("%Y-%m-%d_%H%M%S_%Z")
base = REPORT_DIR / f"{stamp}-browser-harness"

artifacts: dict[str, str] = {}
commands: dict[str, Any] = {}
summary: dict[str, Any] = {
    "generated_at": now.isoformat(),
    "repo_root": str(REPO_ROOT),
    "artifacts": artifacts,
    "commands": commands,
}


audit = run("browser-harness-rollout-audit --json", timeout=240)
commands["rollout_audit"] = audit.to_dict()
audit_artifact = base.with_name(base.name + "-rollout-audit.json")
write_text(audit_artifact, audit.stdout if audit.stdout else json.dumps({"error": "empty stdout", **audit.to_dict()}, indent=2))
artifacts["rollout_audit"] = str(audit_artifact)

try:
    audit_json = parse_json(audit.stdout)
except Exception as exc:  # pragma: no cover - defensive
    audit_json = {"parse_error": str(exc), "raw": audit.stdout}

summary["rollout_audit_exit_code"] = audit.exit_code
summary["rollout_audit"] = audit_json

failures: list[dict[str, Any]] = []
for node_name, node in (audit_json.get("nodes") or {}).items():
    smoke = node.get("smoke") or {}
    integrations = node.get("integrations") or {}
    broken_integrations = [name for name, info in integrations.items() if info.get("status") != "ok"]
    if smoke.get("status") != "pass" or broken_integrations:
        failures.append(
            {
                "node": node_name,
                "smoke_status": smoke.get("status"),
                "error_code": smoke.get("error_code"),
                "phase": smoke.get("phase"),
                "hints": smoke.get("hints"),
                "broken_integrations": broken_integrations,
            }
        )
summary["failures"] = failures
summary["verdict"] = "green" if not failures else "red"

local_log = base.with_name(base.name + "-athame-bu-smoke.log")
remote_log = base.with_name(base.name + "-furnace-bu-smoke.log")
artifacts["athame_smoke_log_tail"] = str(local_log)
artifacts["furnace_smoke_log_tail"] = str(remote_log)
commands["athame_smoke_log_tail"] = tail_result("tail -n 200 /tmp/bu-smoke.log || true", local_log)
commands["furnace_smoke_log_tail"] = tail_result("ssh furnace 'tail -n 200 /tmp/bu-smoke.log || true'", remote_log)

local_preflight = base.with_name(base.name + "-athame-preflight.json")
remote_preflight = base.with_name(base.name + "-furnace-preflight.json")
artifacts["athame_preflight_json"] = str(local_preflight)
artifacts["furnace_preflight_json"] = str(remote_preflight)
commands["athame_preflight_json"] = tail_result("cat /tmp/browser-harness-preflight.json || true", local_preflight)
commands["furnace_preflight_json"] = tail_result("ssh furnace 'cat /tmp/browser-harness-preflight.json || true'", remote_preflight)

local_tests = run("python3 -m unittest discover -s tests -v", timeout=240)
remote_tests = run("ssh furnace 'cd /Users/odinbot33/Developer/browser-harness && python3 -m unittest discover -s tests -v'", timeout=240)
commands["athame_tests"] = local_tests.to_dict()
commands["furnace_tests"] = remote_tests.to_dict()
local_tests_path = base.with_name(base.name + "-athame-tests.txt")
remote_tests_path = base.with_name(base.name + "-furnace-tests.txt")
write_text(local_tests_path, local_tests.stdout + ("\n[stderr]\n" + local_tests.stderr if local_tests.stderr else ""))
write_text(remote_tests_path, remote_tests.stdout + ("\n[stderr]\n" + remote_tests.stderr if remote_tests.stderr else ""))
artifacts["athame_tests"] = str(local_tests_path)
artifacts["furnace_tests"] = str(remote_tests_path)

status = run("git -C /Users/odinbot33/Developer/browser-harness status --short", timeout=60)
diffstat = run("git -C /Users/odinbot33/Developer/browser-harness diff --stat", timeout=60)
commands["git_status"] = status.to_dict()
commands["git_diff_stat"] = diffstat.to_dict()
status_path = base.with_name(base.name + "-git-status.txt")
diffstat_path = base.with_name(base.name + "-git-diff-stat.txt")
write_text(status_path, status.stdout + ("\n[stderr]\n" + status.stderr if status.stderr else ""))
write_text(diffstat_path, diffstat.stdout + ("\n[stderr]\n" + diffstat.stderr if diffstat.stderr else ""))
artifacts["git_status"] = str(status_path)
artifacts["git_diff_stat"] = str(diffstat_path)

summary_path = base.with_name(base.name + "-summary.json")
markdown_path = base.with_name(base.name + "-summary.md")
write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True))
artifacts["summary_json"] = str(summary_path)

lines = [
    f"# Browser Harness evidence packet {stamp}",
    "",
    f"- Verdict: {summary['verdict']}",
    f"- Rollout audit exit: {audit.exit_code}",
    f"- Local tests exit: {local_tests.exit_code}",
    f"- Remote tests exit: {remote_tests.exit_code}",
    "",
    "## Failures",
]
if failures:
    for failure in failures:
        lines.extend(
            [
                f"- node: {failure['node']}",
                f"  - smoke_status: {failure['smoke_status']}",
                f"  - error_code: {failure['error_code']}",
                f"  - phase: {failure['phase']}",
                f"  - hints: {failure['hints']}",
                f"  - broken_integrations: {failure['broken_integrations']}",
            ]
        )
else:
    lines.append("- none")
lines.extend(["", "## Artifacts"])
for key, value in sorted(artifacts.items()):
    lines.append(f"- {key}: {value}")
write_text(markdown_path, "\n".join(lines) + "\n")
artifacts["summary_md"] = str(markdown_path)

print(json.dumps(summary, indent=2, sort_keys=True))
