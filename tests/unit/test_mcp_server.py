"""Tests for the MCP server tool wrappers in mcp_server.py.

Importing mcp_server requires the optional `mcp` extra; run the unit suite
with `uv run --extra mcp --with pytest python -m pytest tests/unit -q`.
"""
import inspect

import mcp_server


def test_browser_switch_tab_docstring_does_not_advertise_url_substring():
    """The tool description must match what switch_tab() actually does:
    switching by targetId only, with no URL-substring matching."""
    doc = mcp_server.browser_switch_tab.__doc__ or ""
    assert "URL substring" not in doc
    assert "targetId" in doc


def test_browser_cdp_uses_none_default_for_params():
    """browser_cdp must not use a mutable default for `params`."""
    sig = inspect.signature(mcp_server.browser_cdp)
    assert sig.parameters["params"].default is None


def test_browser_cdp_params_none_matches_omitted(monkeypatch):
    """browser_cdp(method, params=None) must behave identically to
    browser_cdp(method) — both unpack to an empty kwargs dict."""
    captured = []
    monkeypatch.setattr(mcp_server, "cdp", lambda method, **kwargs: captured.append((method, kwargs)) or {})

    mcp_server.browser_cdp("Page.navigate")
    mcp_server.browser_cdp("Page.navigate", params=None)

    assert captured == [("Page.navigate", {}), ("Page.navigate", {})]
