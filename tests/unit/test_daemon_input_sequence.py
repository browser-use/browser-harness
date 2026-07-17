"""Hermetic test for the daemon input_sequence handler + Runtime.enable omission.

Stubs cdp_use.client so daemon.py imports without the real CDP dependency, then
drives Daemon.handle() with a recording fake CDP client. No browser, no daemon.

Run:  python3 tests/unit/test_daemon_input_sequence.py
"""
import asyncio
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

# Stub cdp_use.client so `from cdp_use.client import CDPClient` succeeds.
_cu = types.ModuleType("cdp_use")
_cuc = types.ModuleType("cdp_use.client")


class _StubCDPClient:
    def __init__(self, url):
        self.url = url


_cuc.CDPClient = _StubCDPClient
sys.modules["cdp_use"] = _cu
sys.modules["cdp_use.client"] = _cuc

import browser_harness.daemon as dm  # noqa: E402


class _RecCDP:
    def __init__(self):
        self.calls = []

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params or {}, session_id))
        return {}


def test_input_sequence_dispatches_in_order_with_delays():
    sleeps = []

    async def fake_sleep(d):
        sleeps.append(d)

    orig = asyncio.sleep
    asyncio.sleep = fake_sleep
    try:
        d = dm.Daemon()
        d.cdp = _RecCDP()
        d.session = "S1"
        events = [
            {"method": "Input.dispatchMouseEvent", "params": {"type": "mouseMoved", "x": 1, "y": 2}, "delay_ms": 0},
            {"method": "Input.dispatchMouseEvent", "params": {"type": "mouseMoved", "x": 3, "y": 4}, "delay_ms": 16},
            {"method": "Input.dispatchMouseEvent", "params": {"type": "mousePressed", "x": 3, "y": 4, "button": "left", "clickCount": 1}, "delay_ms": 50},
        ]
        res = asyncio.run(d.handle({"meta": "input_sequence", "events": events, "session_id": "S1"}))
        assert res == {"ok": True, "count": 3}, res
        assert [c[0] for c in d.cdp.calls] == ["Input.dispatchMouseEvent"] * 3
        assert d.cdp.calls[0][1] == {"type": "mouseMoved", "x": 1, "y": 2}
        assert d.cdp.calls[2][1]["type"] == "mousePressed"
        assert all(c[2] == "S1" for c in d.cdp.calls)        # all to the page session
        assert sorted(round(s * 1000) for s in sleeps) == [16, 50]  # delay_ms honored, 0 skipped
    finally:
        asyncio.sleep = orig


def test_input_sequence_aborts_on_send_error_with_count():
    async def fake_sleep(d):
        pass

    orig = asyncio.sleep
    asyncio.sleep = fake_sleep
    try:
        class _FailSecond:
            def __init__(self):
                self.n = 0

            async def send_raw(self, method, params=None, session_id=None):
                self.n += 1
                if self.n == 2:
                    raise RuntimeError("Session with given id not found")
                return {}

        d = dm.Daemon()
        d.cdp = _FailSecond()
        d.session = "S"
        events = [{"method": "Input.dispatchMouseEvent", "params": {}, "delay_ms": 0}] * 3
        res = asyncio.run(d.handle({"meta": "input_sequence", "events": events}))
        assert res.get("error") and res.get("count") == 1, res   # aborts, reports progress
    finally:
        asyncio.sleep = orig


def test_enabled_domains_omits_runtime_by_default():
    os.environ.pop("BH_CDP_ENABLE_RUNTIME", None)
    assert dm._enabled_domains() == ["Page", "DOM", "Network"]   # Runtime omitted
    os.environ["BH_CDP_ENABLE_RUNTIME"] = "1"
    try:
        assert "Runtime" in dm._enabled_domains()                # restorable via env
    finally:
        os.environ.pop("BH_CDP_ENABLE_RUNTIME", None)


def _run_all():
    fns = [g for n, g in sorted(globals().items()) if n.startswith("test_") and callable(g)]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print("\n%d/%d passed" % (len(fns), len(fns)))


if __name__ == "__main__":
    _run_all()
