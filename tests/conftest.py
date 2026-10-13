import base64
import io

import pytest
from PIL import Image


def make_png(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def fake_png():
    return make_png


@pytest.fixture(autouse=True)
def _runtime_in_tmp(tmp_path, monkeypatch):
    """Tests must never write or sweep the real runtime dir."""
    from browser_harness import _ipc, daemon
    monkeypatch.setattr(daemon, "STATE", tmp_path / "owners.json")
    monkeypatch.setattr(_ipc, "_RUNTIME", tmp_path)
    monkeypatch.delenv("CLAUDE_CODE_CHILD_SESSION", raising=False)  # tests may themselves run inside a sub-agent
