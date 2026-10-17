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
