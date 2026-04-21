import json
import tempfile
import unittest
from pathlib import Path

from public_site_audit import analyze_html, write_packet


class AnalyzeHtmlTests(unittest.TestCase):
    def test_extracts_title_h1_and_internal_links(self):
        html = """
        <html>
          <head><title>Test Site</title></head>
          <body>
            <h1>Main Signal</h1>
            <a href="/pricing">Pricing</a>
            <a href="https://example.com/login">Login</a>
            <a href="mailto:test@example.com">Email</a>
          </body>
        </html>
        """
        result = analyze_html("https://example.com", html)
        self.assertEqual(result["title"], "Test Site")
        self.assertEqual(result["h1"], ["Main Signal"])
        self.assertEqual(result["internal_links"], ["https://example.com/pricing", "https://example.com/login"])
        self.assertEqual(result["issues"], [])

    def test_flags_missing_title_and_h1(self):
        html = "<html><body><p>No signal</p></body></html>"
        result = analyze_html("https://example.com", html)
        self.assertIn("missing_title", result["issues"])
        self.assertIn("missing_h1", result["issues"])


class WritePacketTests(unittest.TestCase):
    def test_writes_markdown_and_json_packets(self):
        packet = {
            "packet_id": "pkt-1",
            "created_at": "2026-04-19T00:00:00Z",
            "operator": "odinbot33",
            "node": "furnace",
            "lane": "deploy",
            "workflow": "public-site-smoke",
            "objective": "Audit site",
            "console": "public-web",
            "page_title": "Site",
            "page_url": "https://example.com",
            "object_under_inspection": "homepage",
            "observed_state": "healthy",
            "expected_state": "healthy",
            "drift_or_issue": "",
            "risk_level": "low",
            "recommended_next_action": "none",
            "approval_required": "false",
            "screenshot_paths": [],
            "supporting_artifacts": [],
            "notes": "ok",
        }
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            write_packet(outdir, packet)
            self.assertTrue((outdir / "packet.json").exists())
            self.assertTrue((outdir / "packet.md").exists())
            data = json.loads((outdir / "packet.json").read_text())
            self.assertEqual(data["packet_id"], "pkt-1")
            md = (outdir / "packet.md").read_text()
            self.assertIn("Packet ID:** pkt-1", md)


if __name__ == "__main__":
    unittest.main()
