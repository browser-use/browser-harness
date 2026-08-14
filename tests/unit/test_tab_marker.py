"""The 🐴 tab marker: visible to the human, invisible to the agent.

The marker exists so the user can see which tab the agent drives. It is
written into document.title — the same channel the page writes to — so it
leaked into every title the agent read, and agents repeatedly mistook it
for a property of the site under test.
"""
import asyncio

from browser_harness import daemon, tab_marker

MARKER = "\U0001F434 "


class _FakeCDP:
    """Records send_raw calls."""

    def __init__(self):
        self.calls = []  # list of (method, params, session_id)

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        return {}


def _daemon(headless):
    d = daemon.Daemon()
    d.cdp = _FakeCDP()
    d.headless = headless
    return d


def _handle(d, req):
    """Run an IPC request and let its fire-and-forget tasks finish."""
    async def go():
        result = await d.handle(req)
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        return result
    return asyncio.run(go())


def _title_writes(d):
    return [
        (params or {}).get("expression", "")
        for (method, params, _sid) in d.cdp.calls
        if method == "Runtime.evaluate"
    ]


def test_headless_session_never_marks_the_tab():
    """No window, nobody watching: the marker can only pollute what the agent
    reads. So a headless session must not touch document.title at all."""
    d = _daemon(headless=True)

    _handle(d, {"meta": "set_session", "session_id": "session-2", "target_id": "target-2"})

    assert not [e for e in _title_writes(d) if "title" in e], (
        f"headless session wrote to document.title: {_title_writes(d)}"
    )


def test_headless_session_never_marks_on_page_load():
    """The load-event marking path is separate from the session one, and fires
    on every navigation — it must respect headless too."""
    d = _daemon(headless=True)
    d.session = "session-1"

    async def go():
        d.on_cdp_event("Page.loadEventFired", {})
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        await asyncio.gather(*pending, return_exceptions=True)
    asyncio.run(go())

    assert not [e for e in _title_writes(d) if "title" in e], (
        f"headless session wrote to document.title on load: {_title_writes(d)}"
    )


class _VersionCDP(_FakeCDP):
    def __init__(self, user_agent):
        super().__init__()
        self.user_agent = user_agent

    async def send_raw(self, method, params=None, session_id=None):
        await super().send_raw(method, params, session_id)
        if method == "Browser.getVersion":
            return {"userAgent": self.user_agent}
        return {}


def test_headless_is_detected_from_the_browser_user_agent():
    """Chrome announces itself as HeadlessChrome when it runs without a window."""
    d = daemon.Daemon()
    d.cdp = _VersionCDP("Mozilla/5.0 (Macintosh) HeadlessChrome/151.0.0.0 Safari/537.36")

    asyncio.run(d.detect_headless())

    assert d.headless is True


def test_headed_browser_is_not_reported_as_headless():
    d = daemon.Daemon()
    d.cdp = _VersionCDP("Mozilla/5.0 (Macintosh) Chrome/151.0.0.0 Safari/537.36")

    asyncio.run(d.detect_headless())

    assert d.headless is False


class _FakeBrowser(_FakeCDP):
    """Stands in for a live CDP connection, headless or headed."""

    def __init__(self, user_agent):
        super().__init__()
        self.user_agent = user_agent
        self._event_registry = type("R", (), {"handle_event": None})()

    async def start(self):
        pass

    async def send_raw(self, method, params=None, session_id=None):
        await super().send_raw(method, params, session_id)
        if method == "Browser.getVersion":
            return {"userAgent": self.user_agent}
        if method == "Target.getTargets":
            return {"targetInfos": [{"targetId": "t1", "type": "page", "url": "https://example.com/"}]}
        if method == "Target.attachToTarget":
            return {"sessionId": "s1"}
        return {}


def _started_daemon(monkeypatch, user_agent):
    browser = _FakeBrowser(user_agent)
    monkeypatch.setattr(daemon, "get_ws_url", lambda: "ws://fake")
    monkeypatch.setattr(daemon, "CDPClient", lambda url: browser)
    monkeypatch.setattr(daemon, "_PatientCDPClient", lambda url: browser)
    d = daemon.Daemon()
    asyncio.run(d.start())
    return d


def test_a_headless_browser_session_marks_nothing_end_to_end(monkeypatch):
    """From connection to tab switch: a daemon that connected to a headless
    browser never writes the marker, without anyone setting a flag by hand."""
    d = _started_daemon(monkeypatch, "Mozilla/5.0 HeadlessChrome/151.0.0.0 Safari/537.36")

    _handle(d, {"meta": "set_session", "session_id": "s2", "target_id": "t2"})
    _handle(d, {"meta": "ping"})

    assert not [e for e in _title_writes(d) if "title" in e], (
        f"headless browser got its titles rewritten: {_title_writes(d)}"
    )


def test_a_headed_browser_session_still_marks_the_tab(monkeypatch):
    """The marker is what tells the user which tab the agent drives — it must
    survive the headless work."""
    d = _started_daemon(monkeypatch, "Mozilla/5.0 Chrome/151.0.0.0 Safari/537.36")

    _handle(d, {"meta": "set_session", "session_id": "s2", "target_id": "t2"})

    assert tab_marker.MARK_JS in _title_writes(d), (
        f"headed session lost the marker: {_title_writes(d)}"
    )
