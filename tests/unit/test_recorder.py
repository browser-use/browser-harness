import base64
import json
from unittest.mock import Mock

from browser_harness import helpers, recorder


def test_tab_selection_never_waits_for_a_recording_frame(monkeypatch):
    capture = Mock(side_effect=AssertionError("selection must not capture"))
    monkeypatch.setattr(recorder, "_capture", capture)
    monkeypatch.setenv("BH_RECORD", "1")
    recorder.observe("switch_tab", ("tab",), {}, 0.01)
    capture.assert_not_called()


class _FakeCDP:
    """Stand-in for helpers.cdp that records its calls."""

    def __init__(self, result=None, error=None):
        self.calls = []
        self._result = result
        self._error = error

    def __call__(self, method, **params):
        self.calls.append((method, params))
        if self._error is not None:
            raise self._error
        return self._result


def _screenshot_ok():
    return _FakeCDP(result={"data": base64.b64encode(b"jpeg-bytes").decode()})


def _events(directory):
    lines = (directory / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_capture_uses_the_screenshot_ipc_timeout(tmp_path, monkeypatch):
    """Frames must get the same budget capture_screenshot() uses.

    On the default 5s IPC timeout every cloud screenshot times out, and the
    handler in _capture swallows it — the recording keeps growing with no
    frames in it.
    """
    cdp = _screenshot_ok()
    monkeypatch.setattr(helpers, "cdp", cdp)
    monkeypatch.setattr(helpers, "js", lambda expression: {})

    recorder._capture(tmp_path, "click_at_xy", (10, 20), {})

    method, params = cdp.calls[0]
    assert method == "Page.captureScreenshot"
    assert params["_response_timeout"] == helpers.SCREENSHOT_IPC_RESPONSE_TIMEOUT_SECONDS
    assert params["_response_timeout"] > helpers.DEFAULT_IPC_RESPONSE_TIMEOUT_SECONDS

    event = _events(tmp_path)[0]
    assert event["frame"] == "0001.jpg"
    assert (tmp_path / "0001.jpg").read_bytes() == b"jpeg-bytes"


def test_dropped_frame_is_recorded_and_never_raises(tmp_path, monkeypatch):
    """A failed screenshot stays non-fatal, but stops being invisible.

    Drives the real IPC timeout rather than a hand-made TimeoutError: _send()
    is what actually raises when a cloud screenshot overruns, and a stand-in
    with a message of its own would hide an empty one on the real exception.
    """

    class _Socket:
        def settimeout(self, _value):
            pass

        def close(self):
            pass

    def _timeout(_conn, _token, _req):
        raise TimeoutError("timed out")

    monkeypatch.setattr(helpers, "_TARGET_ID", "recorded-target")
    monkeypatch.setattr(helpers.ipc, "connect", lambda _name, timeout=None: (_Socket(), None))
    monkeypatch.setattr(helpers.ipc, "request", _timeout)
    monkeypatch.setattr(helpers, "js", lambda expression: {})

    recorder._capture(tmp_path, "click_at_xy", (10, 20), {})

    event = _events(tmp_path)[0]
    assert "frame" not in event
    assert not list(tmp_path.glob("*.jpg"))

    detail = event["frame_error"]
    assert detail.startswith("_IPCResponseTimeout: ")
    # The whole point of the key: it has to say what timed out, and for how long.
    assert "Page.captureScreenshot" in detail
    assert f"{helpers.SCREENSHOT_IPC_RESPONSE_TIMEOUT_SECONDS:g}s" in detail


def test_frame_error_stays_useful_for_a_message_less_exception(tmp_path, monkeypatch):
    """Any bare `raise SomeError` must not record a dangling 'SomeError: '."""
    monkeypatch.setattr(helpers, "cdp", _FakeCDP(error=RuntimeError()))
    monkeypatch.setattr(helpers, "js", lambda expression: {})

    recorder._capture(tmp_path, "click_at_xy", (10, 20), {})

    assert _events(tmp_path)[0]["frame_error"] == "RuntimeError: no detail"
