import re
from pathlib import Path

from browser_harness import helpers, recorder


def _capture_sends(monkeypatch, error=None):
    sent = []

    def _send(req, response_timeout=helpers.DEFAULT_IPC_RESPONSE_TIMEOUT_SECONDS):
        sent.append((req, response_timeout))
        if error is not None:
            raise error
        return {"ok": True}

    monkeypatch.setattr(helpers, "_send", _send)
    return sent


def test_observe_uses_the_screenshot_ipc_budget(monkeypatch):
    """Frames are screenshots; on the default 5s budget every cloud frame times out."""
    sent = _capture_sends(monkeypatch)

    recorder.observe("click_at_xy", (10, 20), {}, 0.1)

    req, timeout = sent[0]
    assert req["meta"] == "record_observe"
    assert req["call"]["helper"] == "click_at_xy"
    assert req["call"]["args"] == [10, 20]
    assert timeout > helpers.SCREENSHOT_IPC_RESPONSE_TIMEOUT_SECONDS


def test_observe_never_raises(monkeypatch):
    _capture_sends(monkeypatch, error=TimeoutError("timed out"))

    recorder.observe("click_at_xy", (10, 20), {})


def test_observe_skips_non_actions_and_stringifies_unjsonable_args(monkeypatch):
    sent = _capture_sends(monkeypatch)

    recorder.observe("js", ("1",), {})
    assert sent == []

    recorder.observe("type_text", (object(),), {"x": {1, 2}})
    call = sent[0][0]["call"]
    assert isinstance(call["args"][0], str) and isinstance(call["kwargs"]["x"], str)


def test_actions_mirror_the_go_recorder():
    go = Path(__file__).resolve().parents[2] / "go" / "internal" / "recorder" / "recorder.go"
    block = re.search(r"var Actions = map\[string\]bool\{(.*?)\n\}", go.read_text(), re.S).group(1)
    assert set(re.findall(r'"(\w+)": true', block)) == recorder.ACTIONS
