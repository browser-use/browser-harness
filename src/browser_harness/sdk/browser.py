"""Async `Browser` over the browser-harness daemon.

Method names mirror the CLI helpers (goto_url, page_info, fill_input, ...).
Differences: everything is async, goto_url() skips domain-skill listings (a
CLI concern), and js() takes model= to validate JSON into a pydantic model.
find()/Element fold the documented AX-tree -> box-model -> coordinate-click
workflow into one call.
"""
import asyncio
import base64
import io
import json
import time
from pathlib import Path
from typing import TypeVar

from .. import _ipc as ipc
from .. import helpers
from .client import HarnessClient, HarnessError
from .views import DialogInfo, PageInfo, Rect, Tab

T = TypeVar("T")

INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")

_KEYS = {  # key -> (windowsVirtualKeyCode, code, text) -- mirrors helpers._KEYS
    "Enter": (13, "Enter", "\r"), "Tab": (9, "Tab", "\t"), "Backspace": (8, "Backspace", ""),
    "Escape": (27, "Escape", ""), "Delete": (46, "Delete", ""), " ": (32, "Space", " "),
    "ArrowLeft": (37, "ArrowLeft", ""), "ArrowUp": (38, "ArrowUp", ""),
    "ArrowRight": (39, "ArrowRight", ""), "ArrowDown": (40, "ArrowDown", ""),
    "Home": (36, "Home", ""), "End": (35, "End", ""),
    "PageUp": (33, "PageUp", ""), "PageDown": (34, "PageDown", ""),
}


def _js_snippet(expression: str, limit: int = 160) -> str:
    snippet = expression.strip().replace("\n", "\\n")
    return snippet[: limit - 3] + "..." if len(snippet) > limit else snippet


def _decode_unserializable(value: str):
    import math

    if value == "NaN":
        return math.nan
    if value == "Infinity":
        return math.inf
    if value == "-Infinity":
        return -math.inf
    if value == "-0":
        return -0.0
    if value.endswith("n"):
        return int(value[:-1])
    return value


def _runtime_value(response: dict, expression: str):
    result = response.get("result", {})
    details = response.get("exceptionDetails")
    if details or result.get("subtype") == "error":
        desc = result.get("description")
        exc = details.get("exception") if details else None
        if not desc and isinstance(exc, dict):
            desc = exc.get("description")
            if desc is None and "value" in exc:
                desc = str(exc["value"])
            if desc is None:
                desc = exc.get("className")
        if not desc and details:
            desc = details.get("text")
        desc = desc or "JavaScript evaluation failed"
        if details and details.get("lineNumber") is not None and details.get("columnNumber") is not None:
            loc = f" at line {details['lineNumber']}, column {details['columnNumber']}"
        else:
            loc = ""
        raise HarnessError(f"JavaScript evaluation failed{loc}: {desc}; expression: {_js_snippet(expression)}")
    if "value" in result:
        return result["value"]
    if "unserializableValue" in result:
        return _decode_unserializable(result["unserializableValue"])
    return None


def _stale(error: HarnessError, element: "Element") -> HarnessError:
    """Translate a stale-node CDP error; other errors pass through unchanged so
    callers keying on their text (e.g. "box model") still match."""
    if "does not belong to the document" in str(error) or "Could not find node" in str(error):
        return HarnessError(
            f"{element!r} is stale -- the page changed since it was found. Call find()/find_all() again"
        )
    return error


class Element:
    """Element handle from the AX tree. Actions click box-center coordinates,
    which pierce iframes and shadow DOM at the compositor level."""

    def __init__(self, browser: "Browser", *, backend_node_id: int, role: str = "", name: str = ""):
        self._browser = browser
        self.backend_node_id = backend_node_id
        self.role = role
        self.name = name

    def __repr__(self) -> str:
        return f"<Element {self.role or '?'} {self.name!r} backend_node_id={self.backend_node_id}>"

    async def rect(self) -> Rect:
        """Viewport-px bounding box, after scrolling into view."""
        try:
            await self._browser.cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=self.backend_node_id)
        except HarnessError:
            pass  # older chrome / detached node -- let getBoxModel report it
        try:
            model = (await self._browser.cdp("DOM.getBoxModel", backendNodeId=self.backend_node_id))["model"]
        except HarnessError as e:
            raise _stale(e, self) from e
        quad = model["content"]
        xs, ys = quad[0::2], quad[1::2]
        return Rect(x=min(xs), y=min(ys), width=max(xs) - min(xs), height=max(ys) - min(ys))

    async def click(self, button: str = "left", clicks: int = 1) -> None:
        x, y = (await self.rect()).center
        await self._browser.click_at_xy(x, y, button=button, clicks=clicks)

    async def type(self, text: str) -> None:
        """Focus + insertText -- fast, but bypasses per-key listeners."""
        await self._browser.cdp("DOM.focus", backendNodeId=self.backend_node_id)
        await self._browser.type_text(text)

    async def fill(self, text: str, clear_first: bool = True) -> None:
        """Clear and type via real key events, then fire input+change so
        framework-managed inputs see the update."""
        await self._browser.cdp("DOM.focus", backendNodeId=self.backend_node_id)
        if clear_first:
            await self._browser._select_all()
            await self._browser.press_key("Backspace")
        for ch in text:
            await self._browser.press_key(ch)
        await self._call_on_node(
            "function(){this.dispatchEvent(new Event('input',{bubbles:true}));"
            "this.dispatchEvent(new Event('change',{bubbles:true}));}"
        )

    async def text(self) -> str:
        """innerText of the element ('' for non-HTMLElement nodes)."""
        return await self._call_on_node("function(){return this.innerText ?? this.textContent ?? '';}") or ""

    async def _call_on_node(self, function_declaration: str, *args):
        try:
            obj = await self._browser.cdp("DOM.resolveNode", backendNodeId=self.backend_node_id)
        except HarnessError as e:
            raise _stale(e, self) from e
        object_id = obj["object"]["objectId"]
        r = await self._browser.cdp(
            "Runtime.callFunctionOn",
            objectId=object_id,
            functionDeclaration=function_declaration,
            arguments=[{"value": a} for a in args],
            returnByValue=True,
        )
        return _runtime_value(r, function_declaration)


class Browser:
    """One browser session, addressed by daemon name (the CLI's BU_NAME).

    Construction does no I/O; the daemon starts on `start()` / `async with`,
    or lazily on first call when auto_start=True (default).

        browser = Browser(name="worker-3")            # parallel session
        browser = Browser(cdp_url="http://host:9222") # remote browser
    """

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
        merged_env = dict(env or {})
        if cdp_url:
            merged_env.setdefault("BU_CDP_URL", cdp_url)
        if cdp_ws:
            merged_env.setdefault("BU_CDP_WS", cdp_ws)
        self.client = HarnessClient(name, request_timeout=request_timeout, env=merged_env)
        self.auto_start = auto_start
        self._started = False
        self._select_all_modifiers: int | None = None
        # the AX tree is megabytes on heavy pages; several find() calls in one
        # agent step would each refetch it. TTL is deliberately shorter than
        # find()'s poll interval so polling still observes fresh state.
        self._ax_cache: tuple[float, list[dict]] | None = None
        self.ax_cache_ttl = 0.2

    @property
    def name(self) -> str:
        return self.client.name

    # --- lifecycle ---

    async def start(self) -> "Browser":
        await self.client.ensure_daemon()
        self._started = True
        return self

    async def stop(self) -> None:
        """No-op: the daemon and browser outlive this object, like the CLI.
        shutdown_daemon() actually stops it."""
        self._started = False

    async def shutdown_daemon(self) -> None:
        await self.client.shutdown_daemon()
        self._started = False

    async def __aenter__(self) -> "Browser":
        return await self.start()

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    async def _ensure_started(self) -> None:
        if not self._started and self.auto_start:
            await self.start()

    # --- transport ---

    async def cdp(self, method: str, session_id: str | None = None, request_timeout: float | None = None, **params):
        """Raw CDP escape hatch: `await browser.cdp('Page.navigate', url=...)`."""
        await self._ensure_started()
        return await self.client.cdp(method, session_id=session_id, request_timeout=request_timeout, **params)

    async def meta(self, command: str, **fields) -> dict:
        await self._ensure_started()
        return await self.client.meta(command, **fields)

    async def drain_events(self) -> list[dict]:
        return (await self.meta("drain_events"))["events"]

    # --- navigation / page ---

    async def goto_url(self, url: str) -> dict:
        return await self.cdp("Page.navigate", url=url)

    goto = goto_url

    async def page_info(self) -> PageInfo:
        """Page geometry, or PageInfo(dialog=...) when a native dialog has the page frozen."""
        dialog = (await self.meta("pending_dialog")).get("dialog")
        if dialog:
            return PageInfo(dialog=DialogInfo.model_validate(dialog))
        # documentElement is briefly null mid-navigation -- guard, don't crash the observation.
        # _evaluate, not js(): the CLI's page_info does not await promises here
        raw = await self._evaluate(
            "(()=>{const d=document.documentElement;"
            "return JSON.stringify({url:location.href,title:document.title,w:innerWidth,h:innerHeight,"
            "sx:scrollX,sy:scrollY,pw:d?d.scrollWidth:0,ph:d?d.scrollHeight:0})})()",
            await_promise=False,
        )
        return PageInfo.model_validate(json.loads(raw))

    async def js(
        self,
        expression: str,
        target_id: str | None = None,
        model: type[T] | None = None,
        timeout: float | None = None,
    ):
        """Evaluate JS in the attached tab (or an iframe target). Retries with a
        function wrapper on illegal top-level `return`; model= validates the
        result into a pydantic model; timeout= allows long-running scripts past
        the default request timeout."""
        sid = None
        if target_id:
            sid = (await self.cdp("Target.attachToTarget", targetId=target_id, flatten=True))["sessionId"]
        try:
            value = await self._evaluate(expression, session_id=sid, timeout=timeout)
        except HarnessError as e:
            if "Illegal return statement" not in str(e):
                raise
            value = await self._evaluate(f"(function(){{{expression}}})()", session_id=sid, timeout=timeout)
        if model is None:
            return value
        if isinstance(value, str):
            return model.model_validate_json(value)  # type: ignore[attr-defined]
        return model.model_validate(value)  # type: ignore[attr-defined]

    async def _evaluate(
        self,
        expression: str,
        session_id: str | None = None,
        timeout: float | None = None,
        await_promise: bool = True,
    ):
        try:
            r = await self.cdp(
                "Runtime.evaluate", session_id=session_id, request_timeout=timeout, expression=expression,
                returnByValue=True, awaitPromise=await_promise,
            )
        except HarnessError as e:
            if "timed out" in str(e):
                raise HarnessError(f"Runtime.evaluate timed out; expression: {_js_snippet(expression)}") from e
            raise
        return _runtime_value(r, expression)

    # --- input ---

    async def click_at_xy(self, x: float, y: float, button: str = "left", clicks: int = 1) -> None:
        await self.cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button=button, clickCount=clicks)
        await self.cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button=button, clickCount=clicks)

    async def type_text(self, text: str) -> None:
        await self.cdp("Input.insertText", text=text)

    async def press_key(self, key: str, modifiers: int = 0) -> None:
        """Modifiers bitfield: 1=Alt, 2=Ctrl, 4=Meta(Cmd), 8=Shift."""
        vk, code, text = _KEYS.get(key, (ord(key[0]) if len(key) == 1 else 0, key, key if len(key) == 1 else ""))
        base = {"key": key, "code": code, "modifiers": modifiers, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
        shortcut_modifiers = modifiers & (1 | 2 | 4)  # Alt/Ctrl/Meta turn single keys into shortcuts
        printable_char = len(key) == 1 and bool(text) and not shortcut_modifiers
        await self.cdp("Input.dispatchKeyEvent", type="keyDown", **base, **({} if printable_char or not text else {"text": text}))
        if printable_char:
            await self.cdp("Input.dispatchKeyEvent", type="char", text=text, **base)
        await self.cdp("Input.dispatchKeyEvent", type="keyUp", **base)

    async def _select_all(self) -> None:
        # commands=["selectAll"] is the keymap-independent path: the bare
        # ctrl/cmd+a chord silently missed, so the following Backspace deleted
        # one character and the new text appended to the old value.
        # direct dispatch, not press_key -- its char event turns the chord into a literal "a".
        if self._select_all_modifiers is None:
            platform = str(await self.js("navigator.platform") or "")
            self._select_all_modifiers = 4 if "Mac" in platform else 2
        select_all = {"key": "a", "code": "KeyA", "modifiers": self._select_all_modifiers,
                      "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65}
        await self.cdp("Input.dispatchKeyEvent", type="rawKeyDown", commands=["selectAll"], **select_all)
        await self.cdp("Input.dispatchKeyEvent", type="keyUp", **select_all)

    async def fill_input(self, selector: str, text: str, clear_first: bool = True, timeout: float = 0.0) -> None:
        """Selector-based Element.fill: clear, real key events, then input+change."""
        if timeout > 0:
            if not await self.wait_for_element(selector, timeout=timeout):
                raise HarnessError(f"fill_input: element not found: {selector!r}")
        focused = await self.js(
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            f"if(!e)return false;e.focus();return true;}})()"
        )
        if not focused:
            raise HarnessError(f"fill_input: element not found: {selector!r}")
        if clear_first:
            await self._select_all()
            await self.press_key("Backspace")
        for ch in text:
            await self.press_key(ch)
        await self.js(
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            f"if(!e)return;"
            f"e.dispatchEvent(new Event('input',{{bubbles:true}}));"
            f"e.dispatchEvent(new Event('change',{{bubbles:true}}));}})();"
        )

    async def scroll(self, x: float, y: float, dy: float = -300, dx: float = 0) -> None:
        await self.cdp("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=dx, deltaY=dy)

    async def dispatch_key(self, selector: str, key: str = "Enter", event: str = "keypress") -> None:
        """Synthetic DOM KeyboardEvent -- some sites listen to these over raw CDP input."""
        kc = {"Enter": 13, "Tab": 9, "Escape": 27, "Backspace": 8, " ": 32,
              "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40}.get(
            key, ord(key) if len(key) == 1 else 0)
        await self.js(
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});if(e){{e.focus();"
            f"e.dispatchEvent(new KeyboardEvent({json.dumps(event)},{{key:{json.dumps(key)},"
            f"code:{json.dumps(key)},keyCode:{kc},which:{kc},bubbles:true}}));}}}})()"
        )

    async def upload_file(self, selector: str, path: str | list[str]) -> None:
        doc = await self.cdp("DOM.getDocument", depth=-1)
        nid = (await self.cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector))["nodeId"]
        if not nid:
            raise HarnessError(f"no element for {selector}")
        await self.cdp("DOM.setFileInputFiles", files=[path] if isinstance(path, str) else list(path), nodeId=nid)

    # --- visual ---

    async def capture_screenshot(self, path: str | Path | None = None, full: bool = False, max_dim: int | None = None) -> Path:
        """Save a PNG. Device px -- divide by device_pixel_ratio() to map to click coords."""
        path = Path(path) if path else ipc._TMP / "shot.png"
        data = base64.b64decode(await self._screenshot_b64_raw(full))
        if max_dim:
            data = _downscale_png(data, max_dim)
        path.write_bytes(data)
        return path

    async def screenshot_b64(self, full: bool = False, max_dim: int | None = None) -> str:
        """Base64 PNG, no disk -- for vision models."""
        b64 = await self._screenshot_b64_raw(full)
        if not max_dim:
            return b64
        return base64.b64encode(_downscale_png(base64.b64decode(b64), max_dim)).decode()

    async def _screenshot_b64_raw(self, full: bool) -> str:
        r = await self.cdp("Page.captureScreenshot", format="png", captureBeyondViewport=full, request_timeout=30.0)
        return r["data"]

    async def http_get(self, url: str, headers: dict | None = None, timeout: float = 20.0) -> str:
        """Pure HTTP, no browser -- same helper the CLI exposes. Routes through the
        fetch-use proxy when BROWSER_USE_API_KEY is set."""
        return await asyncio.to_thread(helpers.http_get, url, headers, timeout)

    async def device_pixel_ratio(self) -> float:
        return float(await self.js("window.devicePixelRatio") or 1)

    # --- tabs ---

    async def list_tabs(self, include_chrome: bool = True) -> list[Tab]:
        out = []
        for t in (await self.cdp("Target.getTargets"))["targetInfos"]:
            if t["type"] != "page":
                continue
            url = t.get("url", "")
            if _is_agent_startup_placeholder(t.get("title", ""), url):
                continue
            if not include_chrome and url.startswith(INTERNAL):
                continue
            out.append(Tab(target_id=t["targetId"], title=t.get("title", ""), url=url))
        return out

    async def current_tab(self) -> Tab:
        r = await self.meta("current_tab")
        return Tab(target_id=r["targetId"], title=r["title"], url=r["url"])

    async def switch_tab(self, target: str | Tab | dict) -> str:
        """Attach to a tab; accepts a Tab, a raw targetId, or a dict with one."""
        target_id = _target_id_of(target)
        # unmark old tab -- horse emoji is 2 utf-16 units + space, hence slice(3).
        # a wedged page raises TimeoutError here; marking is cosmetic, never fatal
        try:
            await self.cdp("Runtime.evaluate", expression="if(document.title.startsWith('\U0001F434 '))document.title=document.title.slice(3)")
        except HarnessError:
            pass
        await self.cdp("Target.activateTarget", targetId=target_id)
        sid = (await self.cdp("Target.attachToTarget", targetId=target_id, flatten=True))["sessionId"]
        await self.meta("set_session", session_id=sid, target_id=target_id)
        await self._mark_tab()
        return sid

    async def _mark_tab(self) -> None:
        try:
            await self.cdp("Runtime.evaluate", expression="if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title")
        except HarnessError:
            pass

    async def new_tab(self, url: str = "about:blank") -> str:
        """Create (or reuse a blank) tab, attach, navigate. Returns targetId."""
        if url != "about:blank":
            try:
                cur = await self.current_tab()
                if (
                    cur.url in ("", "about:blank")
                    or cur.url.startswith("about:blank#")
                    or cur.url.startswith(("chrome://newtab", "chrome://new-tab-page", "edge://newtab", "about:newtab"))
                ):
                    await self.goto_url(url)
                    return cur.target_id
            except HarnessError:
                pass
        tid = (await self.cdp("Target.createTarget", url="about:blank"))["targetId"]
        await self.switch_tab(tid)
        if url != "about:blank":
            await self.goto_url(url)
        return tid

    async def close_tab(self, target: str | Tab | dict | None = None) -> None:
        if target is None:
            target = await self.current_tab()
        await self.cdp("Target.closeTarget", targetId=_target_id_of(target))

    async def ensure_real_tab(self) -> Tab | None:
        """Switch to a real user tab if the current one is chrome:// or stale."""
        tabs = await self.list_tabs(include_chrome=False)
        if not tabs:
            return None
        try:
            cur = await self.current_tab()
            if cur.url and not cur.url.startswith(INTERNAL):
                return cur
        except HarnessError:
            pass
        await self.switch_tab(tabs[0])
        return tabs[0]

    async def iframe_target(self, url_substr: str) -> str | None:
        for t in (await self.cdp("Target.getTargets"))["targetInfos"]:
            if t["type"] == "iframe" and url_substr in t.get("url", ""):
                return t["targetId"]
        return None

    # --- waits ---

    async def wait(self, seconds: float = 1.0) -> None:
        await asyncio.sleep(seconds)

    async def wait_for_load(self, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self.js("document.readyState") == "complete":
                return True
            await asyncio.sleep(0.3)
        return False

    async def wait_for_element(self, selector: str, timeout: float = 10.0, visible: bool = False) -> bool:
        """Poll for a querySelector match -- wait_for_load() misses SPA renders.
        visible=True also requires checkVisibility."""
        if visible:
            check = (
                f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
                f"if(!e)return false;"
                f"if(typeof e.checkVisibility==='function')"
                f"return e.checkVisibility({{checkOpacity:true,checkVisibilityCSS:true}});"
                f"const s=getComputedStyle(e);"
                f"return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'}})()"
            )
        else:
            check = f"!!document.querySelector({json.dumps(selector)})"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self.js(check):
                return True
            await asyncio.sleep(0.3)
        return False

    async def wait_for_network_idle(self, timeout: float = 10.0, idle_ms: float = 500) -> bool:
        """Wait for no in-flight requests and idle_ms of Network.* silence,
        filtered to the active session -- background tabs keep emitting."""
        deadline = time.monotonic() + timeout
        last_activity = time.monotonic()
        inflight: set = set()
        active_session = (await self.meta("session")).get("session_id")
        while time.monotonic() < deadline:
            for e in await self.drain_events():
                if e.get("session_id") != active_session:
                    continue
                method = e.get("method", "")
                params = e.get("params", {})
                if method == "Network.requestWillBeSent":
                    inflight.add(params.get("requestId"))
                    last_activity = time.monotonic()
                elif method in ("Network.loadingFinished", "Network.loadingFailed"):
                    inflight.discard(params.get("requestId"))
                    last_activity = time.monotonic()
                elif method.startswith("Network."):
                    last_activity = time.monotonic()
            if not inflight and (time.monotonic() - last_activity) * 1000 >= idle_ms:
                return True
            await asyncio.sleep(0.1)
        return False

    # --- element discovery (AX tree) ---

    async def _ax_nodes(self, fresh: bool = False) -> list[dict]:
        now = time.monotonic()
        if not fresh and self._ax_cache is not None and now - self._ax_cache[0] < self.ax_cache_ttl:
            return self._ax_cache[1]
        nodes = (await self.cdp("Accessibility.getFullAXTree", request_timeout=30.0)).get("nodes", [])
        self._ax_cache = (now, nodes)
        return nodes

    async def find_all(
        self,
        role: str | None = None,
        name: str | None = None,
        *,
        limit: int | None = None,
        fresh: bool = False,
    ) -> list[Element]:
        """AX-tree elements, filtered by exact role/name equality -- no fuzzy
        matching. Skips ignored nodes and ones without a backing DOM node."""
        nodes = await self._ax_nodes(fresh=fresh)
        out: list[Element] = []
        for n in nodes:
            if n.get("ignored"):
                continue
            backend_id = n.get("backendDOMNodeId")
            if backend_id is None:
                continue
            r = (n.get("role") or {}).get("value") or ""
            nm = (n.get("name") or {}).get("value") or ""
            if role is not None and r != role:
                continue
            if name is not None and nm != name:
                continue
            out.append(Element(self, backend_node_id=backend_id, role=r, name=nm))
            if limit is not None and len(out) >= limit:
                break
        return out

    # --- browser_use.BrowserSession-compatible aliases ---
    # canonical names above mirror the CLI helpers; these let browser-use code
    # run unchanged. both call the same implementation.

    async def navigate_to(self, url: str, new_tab: bool = False) -> None:
        """browser_use.BrowserSession.navigate_to"""
        await (self.new_tab(url) if new_tab else self.goto_url(url))

    async def get_tabs(self) -> list[Tab]:
        """browser_use.BrowserSession.get_tabs"""
        return await self.list_tabs()

    async def get_current_page_url(self) -> str:
        """browser_use.BrowserSession.get_current_page_url"""
        return (await self.current_tab()).url

    async def get_current_page_title(self) -> str:
        """browser_use.BrowserSession.get_current_page_title"""
        return (await self.current_tab()).title

    async def take_screenshot(self, path: str | Path | None = None, full_page: bool = False) -> Path:
        """browser_use.BrowserSession.take_screenshot"""
        return await self.capture_screenshot(path, full=full_page)

    async def close(self) -> None:
        """browser_use.BrowserSession.close -- detaches; the browser stays open."""
        await self.stop()

    async def kill(self) -> None:
        """browser_use.BrowserSession.kill -- stops the daemon (and cloud billing)."""
        await self.shutdown_daemon()

    async def cookies(self) -> list[dict]:
        """browser_use.BrowserSession.cookies"""
        return (await self.cdp("Network.getCookies")).get("cookies", [])

    @classmethod
    def from_system_chrome(cls, **kwargs) -> "Browser":
        """browser_use.BrowserSession.from_system_chrome -- the harness always
        attaches to your real Chrome, so this is the default constructor."""
        return cls(**kwargs)

    async def find(
        self,
        role: str | None = None,
        name: str | None = None,
        *,
        timeout: float = 0.0,
    ) -> Element | None:
        """First exact match, polling up to `timeout` seconds. None if absent."""
        deadline = time.monotonic() + timeout
        while True:
            found = await self.find_all(role, name, limit=1, fresh=True)
            if found:
                return found[0]
            if time.monotonic() >= deadline:
                return None
            await asyncio.sleep(0.3)


def _target_id_of(target: str | Tab | dict) -> str:
    if isinstance(target, Tab):
        return target.target_id
    if isinstance(target, dict):
        return target.get("targetId") or target.get("target_id")  # type: ignore[return-value]
    return target


def _is_agent_startup_placeholder(title, url) -> bool:
    url = str(url or "")
    return str(title or "").startswith("Starting agent ") and (
        url in ("", "about:blank") or url.startswith("about:blank#")
    )


def _downscale_png(data: bytes, max_dim: int) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    if max(img.size) <= max_dim:
        return data
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
