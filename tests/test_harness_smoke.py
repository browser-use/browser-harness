import unittest
from unittest.mock import patch


class HarnessSmokeTests(unittest.TestCase):
    def test_run_smoke_restarts_once_on_stale_error_then_succeeds(self):
        import harness_smoke

        calls = []

        def fake_collect():
            if not calls:
                calls.append("fail")
                raise RuntimeError("no close frame received or sent")
            return {"status": "pass", "page": {"url": "https://example.com"}}

        with patch("harness_smoke.collect_smoke_details", side_effect=fake_collect), patch(
            "harness_smoke.restart_daemon"
        ) as restart, patch("harness_smoke.time.sleep"):
            result = harness_smoke.run_smoke()

        self.assertEqual(result["status"], "pass")
        restart.assert_called_once()

    def test_collect_smoke_details_handles_dialog_without_ready_state(self):
        import harness_smoke

        with patch("harness_smoke.daemon_alive", return_value=False), patch(
            "harness_smoke.ensure_daemon"
        ), patch(
            "harness_smoke.ensure_real_tab",
            return_value={"targetId": "1", "url": "https://example.com", "title": "Example"},
        ), patch(
            "harness_smoke.current_tab",
            return_value={"targetId": "1", "url": "https://example.com", "title": "Example"},
        ), patch(
            "harness_smoke.list_tabs",
            return_value=[{"targetId": "1", "url": "https://example.com", "title": "Example"}],
        ), patch(
            "harness_smoke.page_info",
            return_value={"dialog": {"type": "alert", "message": "hi"}},
        ), patch("harness_smoke.shutil.which", side_effect=lambda name: f"/bin/{name}"):
            result = harness_smoke.collect_smoke_details()

        self.assertEqual(result["status"], "pass")
        self.assertIsNone(result["ready_state"])
        self.assertEqual(result["page"]["dialog"]["type"], "alert")

    def test_format_text_renders_pass_summary(self):
        import harness_smoke

        text = harness_smoke.format_text(
            {
                "status": "pass",
                "host": "athame",
                "repo_root": "/repo",
                "command_path": "/bin/browser-harness",
                "smoke_command_path": "/bin/browser-harness-smoke",
                "daemon_preexisting": True,
                "daemon_running": True,
                "tab_count": 2,
                "current_tab": {"title": "Example", "url": "https://example.com"},
                "page": {"url": "https://example.com", "title": "Example"},
                "ready_state": "complete",
                "phase_timings": {"ensure_daemon": 0.1, "ensure_real_tab": 0.2},
                "repair_attempted": False,
                "repair_trigger": None,
                "bu_name": "default",
            }
        )

        self.assertIn("PASS browser-harness smoke", text)
        self.assertIn("current_title=Example", text)
        self.assertIn("ready_state=complete", text)
        self.assertIn("phase_timings=ensure_daemon:0.100s, ensure_real_tab:0.200s", text)

    def test_failure_hints_cover_allow_prompt(self):
        import harness_smoke

        hints = harness_smoke.failure_hints(
            "fatal: CDP WS handshake failed: timed out during opening handshake -- click Allow in Chrome if prompted, then retry"
        )

        self.assertTrue(any("Allow prompt" in hint or "click Allow" in hint for hint in hints))

    def test_classify_error_code_detects_devtools_active_port(self):
        import harness_smoke

        code = harness_smoke.classify_error_code(
            "fatal: DevToolsActivePort not found in ['/Users/me/Library/Application Support/Google/Chrome']"
        )

        self.assertEqual(code, "BH-ATTACH-001")

    def test_format_text_renders_failure_error_code(self):
        import harness_smoke

        text = harness_smoke.format_text(
            {
                "status": "fail",
                "host": "furnace",
                "repo_root": "/repo",
                "command_path": "/bin/browser-harness",
                "smoke_command_path": "/bin/browser-harness-smoke",
                "bu_name": "smoke",
                "error": "fatal: CDP WS handshake failed: timed out during opening handshake -- click Allow in Chrome if prompted, then retry",
                "error_code": "BH-ATTACH-003",
                "phase": "ensure_real_tab",
                "phase_timings": {"ensure_daemon": 0.1, "ensure_real_tab": 10.0},
                "repair_attempted": False,
                "repair_trigger": None,
                "hints": ["Chrome is likely waiting on its remote-debugging Allow prompt; click Allow in Chrome, then rerun."],
            }
        )

        self.assertIn("error_code=BH-ATTACH-003", text)
        self.assertIn("phase=ensure_real_tab", text)
        self.assertIn("phase_timings=ensure_daemon:0.100s, ensure_real_tab:10.000s", text)

    def test_make_failure_preserves_phase_context(self):
        import harness_smoke

        error = harness_smoke.SmokePhaseError(
            phase="page_info",
            message="timed out during page_info after 10.0s",
            phase_timings={"ensure_daemon": 0.1, "page_info": 10.0},
        )

        with patch("harness_smoke.platform.node", return_value="athame"), patch(
            "harness_smoke.shutil.which", side_effect=lambda name: f"/bin/{name}"
        ):
            result = harness_smoke.make_failure(error)

        self.assertEqual(result["phase"], "page_info")
        self.assertEqual(result["phase_timings"], {"ensure_daemon": 0.1, "page_info": 10.0})

    def test_collect_smoke_details_records_phase_timings(self):
        import harness_smoke

        with patch("harness_smoke.daemon_alive", side_effect=[False, True]), patch(
            "harness_smoke.ensure_daemon"
        ), patch(
            "harness_smoke.ensure_real_tab",
            return_value={"targetId": "1", "url": "https://example.com", "title": "Example"},
        ), patch(
            "harness_smoke.current_tab",
            return_value={"targetId": "1", "url": "https://example.com", "title": "Example"},
        ), patch(
            "harness_smoke.list_tabs",
            return_value=[{"targetId": "1", "url": "https://example.com", "title": "Example"}],
        ), patch(
            "harness_smoke.page_info",
            return_value={"url": "https://example.com", "title": "Example"},
        ), patch(
            "harness_smoke.js",
            return_value="complete",
        ), patch("harness_smoke.shutil.which", side_effect=lambda name: f"/bin/{name}"):
            result = harness_smoke.collect_smoke_details()

        self.assertEqual(result["status"], "pass")
        self.assertIn("ensure_daemon", result["phase_timings"])
        self.assertIn("page_info", result["phase_timings"])
        self.assertIn("ready_state", result["phase_timings"])


if __name__ == "__main__":
    unittest.main()
