import unittest
from pathlib import Path
from unittest import mock

import admin


class SetupLauncherTests(unittest.TestCase):
    @mock.patch("platform.system", return_value="Windows")
    @mock.patch("admin._open_windows_internal_url")
    @mock.patch("webbrowser.open")
    def test_open_chrome_inspect_uses_local_browser_on_windows(self, open_browser, open_internal_url, _system):
        chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

        with (
            mock.patch("admin._find_windows_browser", return_value=chrome, create=True),
            mock.patch("admin._windows_profile_directory", return_value=None, create=True),
        ):
            admin._open_chrome_inspect()

        open_internal_url.assert_called_once_with(chrome, "chrome://inspect/#remote-debugging", None)
        open_browser.assert_not_called()

    @mock.patch("platform.system", return_value="Windows")
    @mock.patch("admin._open_windows_internal_url")
    @mock.patch("webbrowser.open")
    def test_open_chrome_inspect_targets_last_real_profile_when_guest_was_last_used(
        self, open_browser, open_internal_url, _system
    ):
        chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

        with (
            mock.patch("admin._find_windows_browser", return_value=chrome, create=True),
            mock.patch("admin._windows_profile_directory", return_value="Default", create=True),
        ):
            admin._open_chrome_inspect()

        open_internal_url.assert_called_once_with(chrome, "chrome://inspect/#remote-debugging", "Default")
        open_browser.assert_not_called()

    def test_windows_internal_url_script_targets_profile_and_omnibox(self):
        script = admin._windows_internal_url_script(
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            "chrome://inspect/#remote-debugging",
            "Default",
        )

        self.assertIn("$profile = 'Default'", script)
        self.assertIn('Set-Clipboard -Value $targetUrl', script)
        self.assertIn("SendWait('^l')", script)
        self.assertIn("SendWait('^v')", script)
        self.assertIn("SendWait('~')", script)

    @mock.patch("admin.time.sleep")
    @mock.patch("admin.time.time", side_effect=[0, 0, 61])
    @mock.patch("admin._chrome_running", return_value=True)
    @mock.patch("admin.daemon_alive", return_value=False)
    @mock.patch("admin._open_chrome_inspect")
    def test_run_setup_opens_inspect_once_then_only_polls(
        self, open_inspect, _daemon_alive, _chrome_running, _time, _sleep
    ):
        open_inspect_flags = []

        def fake_ensure_daemon(wait=60.0, name=None, env=None, open_inspect=True):
            open_inspect_flags.append(open_inspect)
            raise RuntimeError("DevToolsActivePort not found")

        with mock.patch("admin.ensure_daemon", side_effect=fake_ensure_daemon):
            exit_code = admin.run_setup()

        self.assertEqual(exit_code, 1)
        self.assertEqual(open_inspect_flags, [False, False])
        open_inspect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
