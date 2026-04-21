import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from run_browser_observatory import main


class BrowserObservatoryRunnerTests(unittest.TestCase):
    def test_runs_all_profiles(self):
        called = []

        def fake_audit_profile(name, workflow='public-site-smoke', lane='deploy'):
            called.append((name, workflow, lane))
            return '/tmp/out', {'risk_level': 'low'}

        with patch('run_browser_observatory.audit_profile', side_effect=fake_audit_profile):
            with patch('sys.argv', ['run_browser_observatory.py', '--all']):
                with redirect_stdout(io.StringIO()):
                    rc = main()
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(len(called), 2)


if __name__ == '__main__':
    unittest.main()
