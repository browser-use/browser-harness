import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class RolloutAuditTests(unittest.TestCase):
    def test_collect_local_audit_marks_integrations_ready(self):
        import rollout_audit

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "browser-harness"
            repo.mkdir()
            skill = repo / "SKILL.md"
            skill.write_text("# skill\n")

            hermes_skill = root / ".hermes" / "skills" / "software-development" / "browser-harness"
            hermes_skill.mkdir(parents=True)
            (hermes_skill / "SKILL.md").symlink_to(skill)

            claude_dir = root / ".claude"
            claude_dir.mkdir()
            (claude_dir / "CLAUDE.md").write_text(f"@{skill}\n")

            codex_skill = root / ".codex" / "skills" / "browser-harness"
            codex_skill.mkdir(parents=True)
            (codex_skill / "SKILL.md").symlink_to(skill)

            audit = rollout_audit.collect_local_audit(
                home=root,
                repo=repo,
                smoke_runner=lambda lane: {"status": "pass", "error_code": None, "lane": lane},
            )

        self.assertEqual(audit["integrations"]["hermes"]["status"], "ok")
        self.assertEqual(audit["integrations"]["claude"]["status"], "ok")
        self.assertEqual(audit["integrations"]["codex"]["status"], "ok")
        self.assertEqual(audit["smoke"]["status"], "pass")
        self.assertEqual(audit["smoke"]["lane"], "smoke")

    def test_collect_local_audit_captures_missing_integrations_and_failed_smoke(self):
        import rollout_audit

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "browser-harness"
            repo.mkdir()
            (repo / "SKILL.md").write_text("# skill\n")

            audit = rollout_audit.collect_local_audit(
                home=root,
                repo=repo,
                smoke_runner=lambda lane: {
                    "status": "fail",
                    "error_code": "BH-ATTACH-001",
                    "error": "DevToolsActivePort not found",
                    "lane": lane,
                },
            )

        self.assertEqual(audit["integrations"]["hermes"]["status"], "missing")
        self.assertEqual(audit["integrations"]["claude"]["status"], "missing")
        self.assertEqual(audit["integrations"]["codex"]["status"], "missing")
        self.assertEqual(audit["smoke"]["status"], "fail")
        self.assertEqual(audit["smoke"]["error_code"], "BH-ATTACH-001")

    def test_format_text_renders_node_summary(self):
        import rollout_audit

        text = rollout_audit.format_text(
            {
                "repo_root": "/repo",
                "expected_skill": "/repo/SKILL.md",
                "nodes": {
                    "local": {
                        "host": "athame",
                        "smoke": {"status": "fail", "error_code": "BH-ATTACH-003", "error": "allow prompt"},
                        "integrations": {
                            "hermes": {"status": "ok", "path": "/Users/me/.hermes/skills/software-development/browser-harness/SKILL.md"},
                            "claude": {"status": "ok", "path": "/Users/me/.claude/CLAUDE.md"},
                            "codex": {"status": "missing", "path": "/Users/me/.codex/skills/browser-harness/SKILL.md"},
                        },
                    }
                },
            }
        )

        self.assertIn("BROWSER HARNESS ROLLOUT AUDIT", text)
        self.assertIn("node=local host=athame", text)
        self.assertIn("smoke=fail error_code=BH-ATTACH-003", text)
        self.assertIn("codex=missing", text)

    def test_run_smoke_command_timeout_returns_typed_failure(self):
        import rollout_audit

        with patch("rollout_audit.subprocess.run", side_effect=TimeoutError):
            result = rollout_audit.run_smoke_command("smoke")

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["error_code"], "BH-ATTACH-005")
        self.assertEqual(result["lane"], "smoke")

    def test_default_remote_host_flips_between_athame_and_furnace(self):
        import rollout_audit

        self.assertEqual(rollout_audit.default_remote_host("Odins-MacBook-Pro.local"), "furnace")
        self.assertEqual(rollout_audit.default_remote_host("Odins-Mac-mini.local"), "athame")
        self.assertEqual(rollout_audit.default_remote_host("athame"), "furnace")
        self.assertEqual(rollout_audit.default_remote_host("furnace"), "athame")

    def test_build_audit_skips_self_remote_probe(self):
        import rollout_audit

        fake_repo = Path("/repo")
        local_payload = {
            "host": "Odins-Mac-mini.local",
            "repo_root": str(fake_repo),
            "expected_skill": str(fake_repo / "SKILL.md"),
            "command_path": "/Users/me/.cargo/bin/browser-harness",
            "smoke_command_path": "/Users/me/.cargo/bin/browser-harness-smoke",
            "integrations": {},
            "smoke": {"status": "pass", "error_code": None, "lane": "smoke"},
        }

        with patch("rollout_audit.repo_root", return_value=fake_repo), patch(
            "rollout_audit.collect_local_audit", return_value=local_payload
        ), patch("rollout_audit.collect_remote_audit") as collect_remote:
            audit = rollout_audit.build_audit(remote_host="furnace", lane="smoke", local_only=False)

        collect_remote.assert_not_called()
        self.assertEqual(list(audit["nodes"].keys()), ["local"])

    def test_collect_remote_audit_parses_json_even_on_nonzero_exit(self):
        import rollout_audit

        payload = {
            "nodes": {
                "local": {
                    "host": "Odins-MacBook-Pro.local",
                    "repo_root": "/repo",
                    "expected_skill": "/repo/SKILL.md",
                    "command_path": "/Users/me/.cargo/bin/browser-harness",
                    "smoke_command_path": "/Users/me/.cargo/bin/browser-harness-smoke",
                    "integrations": {},
                    "smoke": {"status": "fail", "error_code": "BH-ATTACH-005", "lane": "smoke"},
                }
            }
        }
        proc = type("Proc", (), {"returncode": 1, "stdout": json.dumps(payload), "stderr": ""})()

        with patch("rollout_audit.subprocess.run", return_value=proc):
            result = rollout_audit.collect_remote_audit("athame", repo=Path("/repo"), lane="smoke")

        self.assertEqual(result["host"], "Odins-MacBook-Pro.local")
        self.assertEqual(result["smoke"]["error_code"], "BH-ATTACH-005")


if __name__ == "__main__":
    unittest.main()
