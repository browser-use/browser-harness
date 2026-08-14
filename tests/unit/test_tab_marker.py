"""The 🐴 tab marker: visible to the human, invisible to the agent.

The marker exists so the user can see which tab the agent drives. It is
written into document.title — the same channel the page writes to — so it
leaked into every title the agent read, and agents repeatedly mistook it
for a property of the site under test.
"""
import asyncio

from browser_harness import daemon

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
