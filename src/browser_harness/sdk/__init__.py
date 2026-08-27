"""Typed async browser control -- the library face of the CLI helpers.

One `Browser` per daemon name (the CLI's BU_NAME), so several sessions can
coexist in one process. Needs the `sdk` extra for pydantic.

    async with Browser() as browser:
        await browser.goto_url("https://example.com")
        el = await browser.find(role="button", name="Submit")
"""

from .browser import Browser, Element
from .sync import SyncBrowser, SyncElement
from .client import HarnessClient, HarnessError
from .views import DialogInfo, PageInfo, Rect, Tab

__all__ = [
    "Browser",
    "SyncBrowser",
    "SyncElement",
    "DialogInfo",
    "Element",
    "HarnessClient",
    "HarnessError",
    "PageInfo",
    "Rect",
    "Tab",
]
