import base64
import io
import os
import tempfile
from unittest.mock import patch

from PIL import Image

import helpers


def _fake_png(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _run(width, height, **kwargs):
    fake = lambda method, **_: {"data": _fake_png(width, height)}
    with patch("helpers.cdp", side_effect=fake), tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "shot.png")
        helpers.capture_screenshot(path, **kwargs)
        return Image.open(path).size


def test_max_dim_downsizes_oversized_image():
    assert max(_run(4592, 2286, max_dim=1800)) == 1800


def test_max_dim_skips_when_image_already_small():
    assert _run(800, 400, max_dim=1800) == (800, 400)


def test_max_dim_default_is_no_resize():
    assert _run(4592, 2286) == (4592, 2286)
