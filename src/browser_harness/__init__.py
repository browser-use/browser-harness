"""Browser Harness core package.

Library use (needs the `sdk` extra):

    from browser_harness import Browser

CLI helpers stay in `browser_harness.helpers` / `browser_harness.run`.
"""
from typing import TYPE_CHECKING

_LAZY_IMPORTS = {
    "Browser": ("browser_harness.sdk.browser", "Browser"),
    "Element": ("browser_harness.sdk.browser", "Element"),
    "SyncBrowser": ("browser_harness.sdk.sync", "SyncBrowser"),
    "SyncElement": ("browser_harness.sdk.sync", "SyncElement"),
    "HarnessClient": ("browser_harness.sdk.client", "HarnessClient"),
    "HarnessError": ("browser_harness.sdk.client", "HarnessError"),
    "DialogInfo": ("browser_harness.sdk.views", "DialogInfo"),
    "PageInfo": ("browser_harness.sdk.views", "PageInfo"),
    "Rect": ("browser_harness.sdk.views", "Rect"),
    "Tab": ("browser_harness.sdk.views", "Tab"),
}

if TYPE_CHECKING:
    from browser_harness.sdk.browser import Browser, Element
    from browser_harness.sdk.sync import SyncBrowser, SyncElement
    from browser_harness.sdk.client import HarnessClient, HarnessError
    from browser_harness.sdk.views import DialogInfo, PageInfo, Rect, Tab


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr = target
    import importlib

    return getattr(importlib.import_module(module_path), attr)


__all__ = [
    "Browser",
    "DialogInfo",
    "Element",
    "HarnessClient",
    "HarnessError",
    "PageInfo",
    "Rect",
    "SyncBrowser",
    "SyncElement",
    "Tab",
]
