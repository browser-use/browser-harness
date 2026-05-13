import os
from unittest.mock import patch

from browser_harness import helpers
from browser_harness import run


def test_new_tab_tracks_and_close_opened_tabs_only_closes_created_targets():
    helpers._OPENED_TABS.clear()
    helpers.keep_opened_tabs(False)
    calls = []

    def fake_cdp(method, **kwargs):
        calls.append((method, kwargs))
        if method == "Target.createTarget":
            return {"targetId": "tab-created"}
        if method == "Target.attachToTarget":
            return {"sessionId": "session-created"}
        return {}

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp), \
         patch("browser_harness.helpers.goto_url", return_value={}):
        assert helpers.new_tab("https://example.com") == "tab-created"
        assert helpers.opened_tabs() == ["tab-created"]
        assert helpers.close_opened_tabs() == ["tab-created"]

    assert ("Target.closeTarget", {"targetId": "tab-created"}) in calls
    assert helpers.opened_tabs() == []


def test_keep_opened_tabs_opt_out_until_forced():
    helpers._OPENED_TABS.clear()
    helpers.keep_opened_tabs(True)

    with patch("browser_harness.helpers.cdp") as mock_cdp:
        helpers._OPENED_TABS.add("tab-keep")
        assert helpers.close_opened_tabs() == []
        mock_cdp.assert_not_called()
        assert helpers.close_opened_tabs(force=True) == ["tab-keep"]

    helpers.keep_opened_tabs(False)


def test_cli_auto_closes_opened_tabs_in_finally(monkeypatch):
    monkeypatch.delenv("BH_KEEP_TABS", raising=False)
    monkeypatch.setattr(run.sys, "argv", ["browser-harness", "-c", "new_tab('https://example.com')\nraise RuntimeError('boom')"])
    events = []

    def fake_cdp(method, **kwargs):
        events.append((method, kwargs))
        if method == "Target.createTarget":
            return {"targetId": "tab-cli"}
        if method == "Target.attachToTarget":
            return {"sessionId": "session-cli"}
        return {}

    with patch("browser_harness.run.print_update_banner"), \
         patch("browser_harness.run.daemon_alive", return_value=True), \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp), \
         patch("browser_harness.helpers.goto_url", return_value={}):
        try:
            run.main()
        except RuntimeError as exc:
            assert str(exc) == "boom"
        else:
            raise AssertionError("RuntimeError was not raised")

    assert ("Target.closeTarget", {"targetId": "tab-cli"}) in events


def test_cli_respects_bh_keep_tabs(monkeypatch):
    monkeypatch.setenv("BH_KEEP_TABS", "1")
    monkeypatch.setattr(run.sys, "argv", ["browser-harness", "-c", "new_tab('https://example.com')"])
    events = []

    def fake_cdp(method, **kwargs):
        events.append((method, kwargs))
        if method == "Target.createTarget":
            return {"targetId": "tab-kept-by-env"}
        if method == "Target.attachToTarget":
            return {"sessionId": "session-kept"}
        return {}

    with patch("browser_harness.run.print_update_banner"), \
         patch("browser_harness.run.daemon_alive", return_value=True), \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp), \
         patch("browser_harness.helpers.goto_url", return_value={}):
        run.main()

    assert not any(method == "Target.closeTarget" for method, _ in events)
    helpers._OPENED_TABS.clear()
    os.environ.pop("BH_KEEP_TABS", None)
