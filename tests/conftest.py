import base64
import io
import os
import shutil
import tempfile

import pytest
from PIL import Image

# Modules compute paths such as daemon.LOG at import. Without this, a test run
# writes fake lines into the live daemon log, and ensure_daemon() reads that
# log to judge the state of a real daemon.
_HOME = tempfile.mkdtemp(prefix="bh-tests-")
os.environ["BH_HOME"] = _HOME
for _key in ("BH_CONFIG_DIR", "BH_RUNTIME_DIR", "BH_TMP_DIR"):
    os.environ.pop(_key, None)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_HOME, ignore_errors=True)


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
    # Daemons the tests spawn (integration tests) read the dir from the env: without it they listen in the real
    # runtime dir while this process pings tmp_path, so start_remote_daemon() never sees them come up.
    monkeypatch.setenv("BH_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CODE_CHILD_SESSION", raising=False)  # tests may themselves run inside a sub-agent


@pytest.fixture(autouse=True)
def _no_real_telemetry(monkeypatch):
    """Tests must never send a real event: run.main() calls sent cli_events to PostHog. A test that checks what is
    sent replaces post_detached itself; processes the tests spawn send to a closed local port."""
    from browser_harness import telemetry
    monkeypatch.setattr(telemetry, "post_detached", lambda payload, host: None)
    monkeypatch.setenv("BH_POSTHOG_HOST", "http://127.0.0.1:9")
