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
