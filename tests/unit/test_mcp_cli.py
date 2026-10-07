"""Tests for the optional MCP console entry point."""

import builtins

import pytest

from browser_harness import mcp_cli


def test_main_explains_missing_mcp_extra(monkeypatch):
    real_import = builtins.__import__

    def import_without_mcp(name, *args, **kwargs):
        if name == "mcp_server":
            raise ModuleNotFoundError("No module named 'mcp'", name="mcp")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_mcp)

    with pytest.raises(SystemExit, match=r"pip install 'browser-harness\[mcp\]'"):
        mcp_cli.main()
