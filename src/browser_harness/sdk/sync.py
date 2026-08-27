"""Blocking facade over the async SDK -- the CLI's ergonomics with typed returns.

    from browser_harness import SyncBrowser

    with SyncBrowser() as browser:
        browser.new_tab("https://example.com")
        print(browser.page_info().title)

Every call runs on one shared background event loop, so this works from plain
scripts and from inside an already-running loop (notebooks) alike. The async
`Browser` is the only implementation; these methods just block on it, so the two
surfaces cannot diverge -- `test_sync_surface_matches_async` enforces that.
"""
import asyncio
import threading
from pathlib import Path
from typing import Any, TypeVar

from .browser import Browser, Element
from .views import PageInfo, Rect, Tab

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _shared_loop() -> asyncio.AbstractEventLoop:
    """One daemon-thread loop for the process, started on first use."""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, name="browser-harness-sync", daemon=True).start()
            _loop = loop
        return _loop


def _block(coro) -> Any:
    return asyncio.run_coroutine_threadsafe(coro, _shared_loop()).result()


class SyncElement:
    """Blocking `Element`."""

    def __init__(self, element: Element):
        self._element = element

    def __repr__(self) -> str:
        return repr(self._element).replace("<Element", "<SyncElement", 1)

    @property
    def backend_node_id(self) -> int:
        return self._element.backend_node_id

    @property
    def role(self) -> str:
        return self._element.role

    @property
    def name(self) -> str:
        return self._element.name

    def rect(self) -> Rect:
        return _block(self._element.rect())

    def click(self, button: str = "left", clicks: int = 1) -> None:
        return _block(self._element.click(button=button, clicks=clicks))

    def type(self, text: str) -> None:
        return _block(self._element.type(text))

    def fill(self, text: str, clear_first: bool = True) -> None:
        return _block(self._element.fill(text, clear_first=clear_first))

    def text(self) -> str:
        return _block(self._element.text())


class SyncBrowser:
    """Blocking `Browser`. Same names, same semantics, no await."""

    def __init__(
        self,
        name: str = "default",
        *,
        cdp_url: str | None = None,
        cdp_ws: str | None = None,
        env: dict[str, str] | None = None,
        auto_start: bool = True,
        request_timeout: float = 5.0,
    ):
        self._browser = Browser(
            name,
            cdp_url=cdp_url,
            cdp_ws=cdp_ws,
            env=env,
            auto_start=auto_start,
            request_timeout=request_timeout,
        )

    @property
    def name(self) -> str:
        return self._browser.name

    @property
    def client(self):
        return self._browser.client

    # --- lifecycle ---

    def start(self) -> "SyncBrowser":
        _block(self._browser.start())
        return self

    def stop(self) -> None:
        _block(self._browser.stop())

    def shutdown_daemon(self) -> None:
        _block(self._browser.shutdown_daemon())

    def __enter__(self) -> "SyncBrowser":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # --- transport ---

    def cdp(self, method: str, session_id: str | None = None, request_timeout: float | None = None, **params):
        return _block(self._browser.cdp(method, session_id=session_id, request_timeout=request_timeout, **params))

    def meta(self, command: str, **fields) -> dict:
        return _block(self._browser.meta(command, **fields))

    def drain_events(self) -> list[dict]:
        return _block(self._browser.drain_events())

    # --- navigation / page ---

    def goto_url(self, url: str) -> dict:
        return _block(self._browser.goto_url(url))

    goto = goto_url

    def page_info(self) -> PageInfo:
        return _block(self._browser.page_info())

    def js(self, expression: str, target_id: str | None = None, model: type[T] | None = None, timeout: float | None = None):
        return _block(self._browser.js(expression, target_id=target_id, model=model, timeout=timeout))

    def http_get(self, url: str, headers: dict | None = None, timeout: float = 20.0) -> str:
        return _block(self._browser.http_get(url, headers=headers, timeout=timeout))

    # --- input ---

    def click_at_xy(self, x: float, y: float, button: str = "left", clicks: int = 1) -> None:
        return _block(self._browser.click_at_xy(x, y, button=button, clicks=clicks))

    def type_text(self, text: str) -> None:
        return _block(self._browser.type_text(text))

    def press_key(self, key: str, modifiers: int = 0) -> None:
        return _block(self._browser.press_key(key, modifiers=modifiers))

    def fill_input(self, selector: str, text: str, clear_first: bool = True, timeout: float = 0.0) -> None:
        return _block(self._browser.fill_input(selector, text, clear_first=clear_first, timeout=timeout))

    def scroll(self, x: float, y: float, dy: float = -300, dx: float = 0) -> None:
        return _block(self._browser.scroll(x, y, dy=dy, dx=dx))

    def dispatch_key(self, selector: str, key: str = "Enter", event: str = "keypress") -> None:
        return _block(self._browser.dispatch_key(selector, key=key, event=event))

    def upload_file(self, selector: str, path: str | list[str]) -> None:
        return _block(self._browser.upload_file(selector, path))

    # --- visual ---

    def capture_screenshot(self, path: str | Path | None = None, full: bool = False, max_dim: int | None = None) -> Path:
        return _block(self._browser.capture_screenshot(path, full=full, max_dim=max_dim))

    def screenshot_b64(self, full: bool = False, max_dim: int | None = None) -> str:
        return _block(self._browser.screenshot_b64(full=full, max_dim=max_dim))

    def device_pixel_ratio(self) -> float:
        return _block(self._browser.device_pixel_ratio())

    # --- tabs ---

    def list_tabs(self, include_chrome: bool = True) -> list[Tab]:
        return _block(self._browser.list_tabs(include_chrome=include_chrome))

    def current_tab(self) -> Tab:
        return _block(self._browser.current_tab())

    def switch_tab(self, target: str | Tab | dict) -> str:
        return _block(self._browser.switch_tab(target))

    def new_tab(self, url: str = "about:blank") -> str:
        return _block(self._browser.new_tab(url))

    def close_tab(self, target: str | Tab | dict | None = None) -> None:
        return _block(self._browser.close_tab(target))

    def ensure_real_tab(self) -> Tab | None:
        return _block(self._browser.ensure_real_tab())

    def iframe_target(self, url_substr: str) -> str | None:
        return _block(self._browser.iframe_target(url_substr))

    # --- waits ---

    def wait(self, seconds: float = 1.0) -> None:
        return _block(self._browser.wait(seconds))

    def wait_for_load(self, timeout: float = 15.0) -> bool:
        return _block(self._browser.wait_for_load(timeout=timeout))

    def wait_for_element(self, selector: str, timeout: float = 10.0, visible: bool = False) -> bool:
        return _block(self._browser.wait_for_element(selector, timeout=timeout, visible=visible))

    def wait_for_network_idle(self, timeout: float = 10.0, idle_ms: float = 500) -> bool:
        return _block(self._browser.wait_for_network_idle(timeout=timeout, idle_ms=idle_ms))

    # --- element discovery ---

    # --- browser_use.BrowserSession-compatible aliases ---

    def navigate_to(self, url: str, new_tab: bool = False) -> None:
        return _block(self._browser.navigate_to(url, new_tab=new_tab))

    def get_tabs(self) -> list[Tab]:
        return _block(self._browser.get_tabs())

    def get_current_page_url(self) -> str:
        return _block(self._browser.get_current_page_url())

    def get_current_page_title(self) -> str:
        return _block(self._browser.get_current_page_title())

    def take_screenshot(self, path: str | Path | None = None, full_page: bool = False) -> Path:
        return _block(self._browser.take_screenshot(path, full_page=full_page))

    def close(self) -> None:
        return _block(self._browser.close())

    def kill(self) -> None:
        return _block(self._browser.kill())

    def cookies(self) -> list[dict]:
        return _block(self._browser.cookies())

    @classmethod
    def from_system_chrome(cls, **kwargs) -> "SyncBrowser":
        return cls(**kwargs)

    def find_all(
        self, role: str | None = None, name: str | None = None, *, limit: int | None = None, fresh: bool = False
    ) -> list[SyncElement]:
        return [SyncElement(e) for e in _block(self._browser.find_all(role, name, limit=limit, fresh=fresh))]

    def find(self, role: str | None = None, name: str | None = None, *, timeout: float = 0.0) -> SyncElement | None:
        element = _block(self._browser.find(role, name, timeout=timeout))
        return SyncElement(element) if element is not None else None
