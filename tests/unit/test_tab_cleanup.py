from unittest.mock import patch

import pytest

from browser_harness import helpers


@pytest.fixture(autouse=True)
def reset_tab_ownership():
    helpers._OPENED_TABS.clear()
    helpers._REUSED_BLANK_TABS.clear()
    helpers.keep_opened_tabs(False)
    yield
    helpers._OPENED_TABS.clear()
    helpers._REUSED_BLANK_TABS.clear()
    helpers.keep_opened_tabs(False)


def test_new_tab_tracks_only_targets_it_creates():
    def fake_cdp(method, **kwargs):
        if method == "Target.createTarget":
            return {"targetId": "created"}
        return {}

    with patch("browser_harness.helpers.current_tab", side_effect=RuntimeError("no tab")), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp), \
         patch("browser_harness.helpers.switch_tab"), \
         patch("browser_harness.helpers.goto_url"):
        assert helpers.new_tab("https://example.com") == "created"

    assert helpers.opened_tabs() == ["created"]


def test_reused_blank_tab_is_restored_instead_of_closed():
    with patch("browser_harness.helpers.current_tab", return_value={
        "targetId": "blank", "target_id": "blank", "url": "about:blank", "title": ""
    }), patch("browser_harness.helpers.goto_url"):
        assert helpers.new_tab("https://example.com") == "blank"

    assert helpers.opened_tabs() == []

    with patch("browser_harness.helpers.switch_tab") as switch, \
         patch("browser_harness.helpers.goto_url") as restore, \
         patch("browser_harness.helpers.cdp") as cdp:
        assert helpers.close_opened_tabs() == []

    switch.assert_called_once_with("blank")
    restore.assert_called_once_with("about:blank")
    assert not any(call.args[0] == "Target.closeTarget" for call in cdp.call_args_list)


def test_cleanup_closes_only_owned_tabs_and_uses_fresh_keeper():
    helpers._OPENED_TABS.update({"owned-a", "owned-b"})
    events = []

    def fake_cdp(method, **kwargs):
        events.append((method, kwargs))
        if method == "Target.createTarget":
            return {"targetId": "created"}
        return {"success": True}

    def fake_switch(target):
        events.append(("switch", {"targetId": target}))

    with patch("browser_harness.helpers.current_tab", return_value={"targetId": "owned-b"}), \
         patch("browser_harness.helpers.switch_tab", side_effect=fake_switch), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        closed = helpers.close_opened_tabs()

    assert set(closed) == {"owned-a", "owned-b"}
    assert events[:2] == [
        ("Target.createTarget", {"url": "about:blank"}),
        ("switch", {"targetId": "created"}),
    ]
    close_ids = {
        kwargs["targetId"] for method, kwargs in events if method == "Target.closeTarget"
    }
    assert close_ids == {"owned-a", "owned-b"}
    assert helpers.opened_tabs() == []


def test_cleanup_creates_keeper_before_closing_only_remaining_tab():
    helpers._OPENED_TABS.add("owned")
    events = []

    def fake_cdp(method, **kwargs):
        events.append((method, kwargs))
        if method == "Target.createTarget":
            return {"targetId": "keeper"}
        return {"success": True}

    def fake_switch(target):
        events.append(("switch", {"targetId": target}))

    with patch("browser_harness.helpers.current_tab", return_value={"targetId": "owned"}), \
         patch("browser_harness.helpers.switch_tab", side_effect=fake_switch), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        assert helpers.close_opened_tabs() == ["owned"]

    assert events[:3] == [
        ("Target.createTarget", {"url": "about:blank"}),
        ("switch", {"targetId": "keeper"}),
        ("Target.closeTarget", {"targetId": "owned"}),
    ]


def test_cleanup_keeps_current_tab_if_safe_session_handoff_fails():
    helpers._OPENED_TABS.update({"current", "other"})

    def fake_cdp(method, **kwargs):
        if method == "Target.createTarget":
            return {"targetId": "keeper"}
        return {"success": True}

    with patch("browser_harness.helpers.current_tab", return_value={"targetId": "current"}), \
         patch("browser_harness.helpers.switch_tab", side_effect=RuntimeError("attach failed")), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp) as cdp, \
         pytest.raises(RuntimeError, match="keeper handoff"):
        helpers.close_opened_tabs()

    closed = [
        call.kwargs["targetId"] for call in cdp.call_args_list
        if call.args[0] == "Target.closeTarget"
    ]
    assert closed == ["keeper", "other"]
    assert "current" in helpers.opened_tabs()


def test_keep_opened_tabs_requires_force_to_clean_up():
    helpers._OPENED_TABS.add("owned")
    helpers.keep_opened_tabs()

    with patch("browser_harness.helpers.cdp") as cdp:
        assert helpers.close_opened_tabs() == []
        cdp.assert_not_called()
    assert helpers.opened_tabs() == []

    helpers._OPENED_TABS.add("owned")
    with patch("browser_harness.helpers.current_tab", return_value={"targetId": "survivor"}), \
         patch("browser_harness.helpers.cdp", return_value={"success": True}), \
         patch("browser_harness.helpers.list_tabs", return_value=[]):
        assert helpers.close_opened_tabs(force=True) == ["owned"]


def test_keep_opened_tabs_does_not_restore_reused_blank():
    # Regression: new_tab() usually reuses the current blank tab instead of
    # creating a new one, so most "kept" tabs in practice are reused-blank
    # ones. keep_opened_tabs() must protect those too, or it silently fails
    # for the common single-tab case a caller relies on it for.
    helpers._OPENED_TABS.add("created")
    helpers._REUSED_BLANK_TABS["blank"] = "about:blank"
    helpers.keep_opened_tabs()

    with patch("browser_harness.helpers.switch_tab") as switch, \
         patch("browser_harness.helpers.goto_url") as restore:
        assert helpers.close_opened_tabs() == []

    switch.assert_not_called()
    restore.assert_not_called()
    assert helpers.opened_tabs() == []
    assert helpers._REUSED_BLANK_TABS == {}


def test_keep_opened_tabs_force_still_restores_reused_blank():
    helpers._REUSED_BLANK_TABS["blank"] = "about:blank"
    helpers.keep_opened_tabs()

    with patch("browser_harness.helpers.switch_tab") as switch, \
         patch("browser_harness.helpers.goto_url") as restore, \
         patch("browser_harness.helpers.current_tab", return_value={"targetId": "survivor"}), \
         patch("browser_harness.helpers.cdp", return_value={"success": True}), \
         patch("browser_harness.helpers.list_tabs", return_value=[]):
        assert helpers.close_opened_tabs(force=True) == []

    switch.assert_called_once_with("blank")
    restore.assert_called_once_with("about:blank")
    assert helpers._REUSED_BLANK_TABS == {}


def test_restore_failure_is_reported_and_retained_for_retry():
    helpers._REUSED_BLANK_TABS["blank"] = "about:blank"

    with patch("browser_harness.helpers.switch_tab", side_effect=RuntimeError("attach failed")), \
         pytest.raises(RuntimeError, match="blank: attach failed"):
        helpers.close_opened_tabs()

    assert helpers._REUSED_BLANK_TABS == {"blank": "about:blank"}


def test_unknown_current_target_fails_closed():
    helpers._OPENED_TABS.update({"owned-a", "owned-b"})

    with patch("browser_harness.helpers.current_tab", side_effect=RuntimeError("unknown")), \
         patch("browser_harness.helpers.cdp") as cdp, \
         pytest.raises(RuntimeError, match="current target: unknown"):
        helpers.close_opened_tabs()

    cdp.assert_not_called()
    assert set(helpers.opened_tabs()) == {"owned-a", "owned-b"}


def test_failed_close_is_retried_and_retained():
    helpers._OPENED_TABS.add("owned")

    with patch("browser_harness.helpers.current_tab", return_value={"targetId": "survivor"}), \
         patch("browser_harness.helpers.cdp", side_effect=RuntimeError("close failed")) as cdp, \
         pytest.raises(RuntimeError, match="owned: close failed"):
        helpers.close_opened_tabs()

    assert cdp.call_count == 2
    assert helpers.opened_tabs() == ["owned"]

    with patch("browser_harness.helpers.current_tab", return_value={"targetId": "survivor"}), \
         patch("browser_harness.helpers.cdp", return_value={"success": True}), \
         patch("browser_harness.helpers.list_tabs", return_value=[]):
        assert helpers.close_opened_tabs() == ["owned"]
    assert helpers.opened_tabs() == []


def test_failed_keeper_cleanup_is_retained_for_retry():
    helpers._OPENED_TABS.update({"current", "other"})

    def fake_cdp(method, **kwargs):
        if method == "Target.createTarget":
            return {"targetId": "keeper"}
        if method == "Target.closeTarget" and kwargs["targetId"] == "keeper":
            raise RuntimeError("keeper close failed")
        return {"success": True}

    with patch("browser_harness.helpers.current_tab", return_value={"targetId": "current"}), \
         patch("browser_harness.helpers.switch_tab", side_effect=RuntimeError("attach failed")), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp), \
         pytest.raises(RuntimeError, match="keeper: keeper close failed"):
        helpers.close_opened_tabs()

    assert set(helpers.opened_tabs()) == {"current", "keeper"}
