"""solve_captcha() against a real Browser Use Cloud browser (bills a few minutes; skipped without auth)."""
import os
import time

import pytest

from browser_harness import admin, auth, helpers

DEMO = "https://www.google.com/recaptcha/api2/demo"
TOKEN_JS = "document.getElementById('g-recaptcha-response').value.length"

pytestmark = pytest.mark.skipif(
    auth.auth_status()["status"] != "authenticated", reason="needs Browser Use Cloud auth"
)


def _open(url):
    helpers.goto_url(url)
    helpers.wait_for_load()


def test_solve_captcha_on_a_cloud_browser(monkeypatch):
    monkeypatch.setenv("BH_OPEN_LIVE_URL", "0")
    name = f"captcha{os.getpid()}"
    monkeypatch.setattr(helpers, "NAME", name)
    browser = admin.start_remote_daemon(name, timeout=5)
    print("browser", browser["id"])
    try:
        helpers.new_tab("https://example.com")
        helpers.wait_for_load()
        r = helpers.solve_captcha(start_timeout=8)
        print("example.com", r)
        assert r["detail"] == "no captcha solve started within 8 s"

        _open(DEMO)  # solver on by default: the solve may finish before the call
        r = helpers.solve_captcha()
        print("demo, solver on", r)
        assert (r["solved"], r["vendor"]) == (True, "recaptcha")
        assert helpers.js(TOKEN_JS) > 0

        helpers.cdp("BrowserUse.setCaptchaSolverEnabled", enabled=False)
        _open(DEMO)
        time.sleep(2)
        r = helpers.solve_captcha()  # switches it on, waits, switches it back off
        print("demo, solver off", r)
        assert (r["solved"], r["vendor"]) == (True, "recaptcha")
        assert helpers.js(TOKEN_JS) > 0
        end = time.monotonic() + 5
        while helpers.cdp("BrowserUse.getCaptchaSolverEnabled")["enabled"] and time.monotonic() < end:
            time.sleep(0.2)
        assert helpers.cdp("BrowserUse.getCaptchaSolverEnabled") == {"enabled": False}
    finally:
        admin.stop_remote_daemon(name)
    status = admin._browser_use(f"/browsers/{browser['id']}", "GET")["status"]
    print("browser", browser["id"], status)
    assert status == "stopped"
