import unittest
from pathlib import Path

import daemon


class RunningProfileRootsTests(unittest.TestCase):
    def test_prefers_real_browser_profiles_over_helpers(self):
        ps_output = """
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=renderer --user-data-dir=/Users/test/.chrome-real --remote-debugging-port=9222
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=50088 --user-data-dir=/var/folders/tmp/playwright_chromiumdev_profile-A2etvi --remote-debugging-pipe --no-startup-window
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --no-first-run --remote-debugging-port=9222 --user-data-dir=/Users/test/.chrome-real
""".strip()

        self.assertEqual(
            daemon._running_profile_roots(ps_output),
            [
                Path("/Users/test/.chrome-real"),
                Path("/var/folders/tmp/playwright_chromiumdev_profile-A2etvi"),
            ],
        )

    def test_extracts_remote_debugging_ports_from_real_browser_processes(self):
        ps_output = """
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=renderer --user-data-dir=/Users/test/.chrome-real --remote-debugging-port=9222
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=50088 --user-data-dir=/var/folders/tmp/playwright_chromiumdev_profile-A2etvi --remote-debugging-pipe --no-startup-window
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --no-first-run --remote-debugging-port=9222 --user-data-dir=/Users/test/.chrome-real
""".strip()

        self.assertEqual(
            daemon._running_debug_endpoints(ps_output),
            [
                (Path("/Users/test/.chrome-real"), 9222),
                (Path("/var/folders/tmp/playwright_chromiumdev_profile-A2etvi"), 50088),
            ],
        )


if __name__ == "__main__":
    unittest.main()
