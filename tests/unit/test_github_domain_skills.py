from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_github_pr_issue_triage_skill_has_required_sections():
    path = ROOT / "agent-workspace" / "domain-skills" / "github" / "pr-issue-triage.md"
    assert path.exists(), "GitHub PR/Issue triage skill should be documented"

    text = path.read_text(encoding="utf-8")
    required = [
        "# GitHub - PR and Issue Triage",
        "## Do this first",
        "## Common workflows",
        "### PR shortlist (API)",
        "### Pull request detail and files (API)",
        "### Issue duplicate check (API)",
        "### Browser verification",
        "## Gotchas",
        "pulls?state=open",
        "issues?state=open",
        "/pulls/{pull_number}/files",
        "/issues/{issue_number}/comments",
        "/commits/{head_sha}/check-runs",
    ]

    for needle in required:
        assert needle in text


def test_github_pr_issue_triage_skill_addresses_reviewed_edge_cases():
    path = ROOT / "agent-workspace" / "domain-skills" / "github" / "pr-issue-triage.md"
    text = path.read_text(encoding="utf-8")

    required = [
        'query = f"repo:{owner}/{repo} github triage in:title,body is:open"',
        '"docs_or_skill_only": bool(paths) and all(',
        'runs = checks.get("check_runs", [])',
        'completed_runs = [r for r in runs if r.get("status") == "completed"]',
        '"checks_green": bool(runs) and len(completed_runs) == len(runs) and all(',
    ]

    for needle in required:
        assert needle in text
