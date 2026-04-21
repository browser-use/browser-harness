import unittest

from public_site_audit import evaluate_markers


class MarkerEvaluationTests(unittest.TestCase):
    def test_reports_missing_required_markers(self):
        text = "The Cathedral powered by LOGOS and Grimoire"
        result = evaluate_markers(text, ["LOGOS", "Sanctum"])
        self.assertEqual(result["present"], ["LOGOS"])
        self.assertEqual(result["missing"], ["Sanctum"])

    def test_is_case_insensitive(self):
        text = "expert pool management & staffing solutions"
        result = evaluate_markers(text, ["Expert Pool Management", "Staffing Solutions"])
        self.assertEqual(result["missing"], [])


if __name__ == "__main__":
    unittest.main()
