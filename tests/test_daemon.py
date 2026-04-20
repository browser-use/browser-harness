import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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

    def test_falls_back_to_json_version_when_devtoolsactiveport_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            profile = Path(td)
            (profile / "DevToolsActivePort").write_text("9999\n/devtools/browser/stale")

            fake_socket = SimpleNamespace(
                settimeout=lambda _: None,
                connect=lambda *_: (_ for _ in ()).throw(OSError("connection refused")),
                close=lambda: None,
            )

            with mock.patch.object(daemon, "_running_debug_endpoints", return_value=[(profile, 9222)]):
                with mock.patch.object(daemon, "_ws_url_from_port", return_value="ws://127.0.0.1:9222/devtools/browser/live") as ws_from_port:
                    with mock.patch.object(daemon.socket, "socket", return_value=fake_socket):
                        with mock.patch.object(daemon.time, "time", side_effect=[0, 31]):
                            with mock.patch.object(daemon.time, "sleep"):
                                self.assertEqual(
                                    daemon.get_ws_url(),
                                    "ws://127.0.0.1:9222/devtools/browser/live",
                                )

        ws_from_port.assert_called_once_with(9222)


if __name__ == "__main__":
    unittest.main()
