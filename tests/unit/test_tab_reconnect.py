"""Fail-closed, exact-target tab reconnection tests (issue #998)."""

from unittest.mock import Mock

import pytest

from browser_harness import helpers


def _tab(target_id, url="https://example.test/work", title="Task owner-tag-37"):
    return {"targetId": target_id, "target_id": target_id, "url": url, "title": title}


def _fake_connection(monkeypatch, tabs, actual=None):
    listed = Mock(return_value=tabs)
    switched = Mock()
    attached = Mock(side_effect=lambda: actual or tabs[0])
    activated = Mock()
    monkeypatch.setattr(helpers, "list_tabs", listed)
    monkeypatch.setattr(helpers, "switch_tab", switched)
    monkeypatch.setattr(helpers, "current_tab", attached)
    monkeypatch.setattr(helpers, "activate_tab", activated)
    return listed, switched, attached, activated


def test_reconnect_reuses_live_exact_id_without_foregrounding(monkeypatch):
    tabs = [_tab("mine"), _tab("other")]
    listed, switched, _attached, activated = _fake_connection(monkeypatch, tabs)
    assert helpers.reconnect_tab("mine", expected_url="https://example.test/work", expected_title="Task") == "mine"
    listed.assert_called_once_with(include_chrome=False)
    switched.assert_called_once_with("mine")
    activated.assert_not_called()


def test_reconnect_stale_id_recovers_only_unique_tagged_candidate(monkeypatch):
    tabs = [_tab("other", title="Task without tag"), _tab("recovered", title="Task owner-tag-37")]
    _listed, switched, _attached, activated = _fake_connection(monkeypatch, tabs, actual=tabs[1])
    assert helpers.reconnect_tab(
        "old-target", expected_url="https://example.test/work", owned_marker="owner-tag-37"
    ) == "recovered"
    switched.assert_called_once_with("recovered")
    activated.assert_not_called()


def test_reconnect_fails_closed_for_duplicate_tagged_tabs(monkeypatch):
    tabs = [_tab("a"), _tab("b")]
    _listed, switched, _attached, activated = _fake_connection(monkeypatch, tabs)
    with pytest.raises(RuntimeError, match="ambiguous"):
        helpers.reconnect_tab(
            "stale", expected_url="https://example.test/work", owned_marker="owner-tag-37"
        )
    switched.assert_not_called()
    activated.assert_not_called()


def test_reconnect_fails_closed_for_stale_target_without_owner_marker(monkeypatch):
    _listed, switched, _attached, _activated = _fake_connection(monkeypatch, [_tab("someone-else")])
    with pytest.raises(RuntimeError, match="owned_marker"):
        helpers.reconnect_tab("stale", expected_url="https://example.test/work")
    switched.assert_not_called()


def test_reconnect_refuses_live_id_with_wrong_identity(monkeypatch):
    tabs = [_tab("mine", url="https://unrelated.test/"), _tab("fallback")]
    _listed, switched, _attached, _activated = _fake_connection(monkeypatch, tabs)
    with pytest.raises(RuntimeError, match="identity"):
        helpers.reconnect_tab(
            "mine", expected_url="https://example.test/work", owned_marker="owner-tag-37"
        )
    switched.assert_not_called()


def test_reconnect_refuses_unverifiable_post_attach_page(monkeypatch):
    tabs = [_tab("mine")]
    _listed, switched, _attached, _activated = _fake_connection(
        monkeypatch, tabs, actual=_tab("unrelated", url="https://unrelated.test/")
    )
    with pytest.raises(RuntimeError, match="verification"):
        helpers.reconnect_tab("mine", expected_url="https://example.test/work")
    switched.assert_called_once_with("mine")


def test_reconnect_rejects_unsafe_or_empty_identity_before_listing(monkeypatch):
    listed, switched, _attached, _activated = _fake_connection(monkeypatch, [_tab("mine")])
    with pytest.raises(ValueError, match="target_id"):
        helpers.reconnect_tab("", expected_url="https://example.test/work")
    with pytest.raises(ValueError, match="expected_url"):
        helpers.reconnect_tab("mine", expected_url="")
    listed.assert_not_called()
    switched.assert_not_called()
