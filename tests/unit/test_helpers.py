import os
import tempfile
from unittest.mock import patch

import pytest
from PIL import Image

from browser_harness import helpers


def _run(fake_png, width, height, **kwargs):
    fake = lambda method, **_: {"data": fake_png(width, height)}
    with patch("browser_harness.helpers.cdp", side_effect=fake), tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "shot.png")
        helpers.capture_screenshot(path, **kwargs)
        return Image.open(path).size


def test_max_dim_downsizes_oversized_image(fake_png):
    assert max(_run(fake_png, 4592, 2286, max_dim=1800)) == 1800


def test_max_dim_skips_when_image_already_small(fake_png):
    assert _run(fake_png, 800, 400, max_dim=1800) == (800, 400)


def test_max_dim_default_is_no_resize(fake_png):
    assert _run(fake_png, 4592, 2286) == (4592, 2286)


def test_page_info_raises_clear_error_on_js_exception():
    def fake_send(req):
        return {}

    def fake_cdp(method, **kwargs):
        return {
            "result": {
                "type": "object",
                "subtype": "error",
                "description": "ReferenceError: location is not defined",
            },
            "exceptionDetails": {
                "text": "Uncaught",
                "lineNumber": 0,
                "columnNumber": 16,
            },
        }

    with patch("browser_harness.helpers._send", side_effect=fake_send), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        with pytest.raises(RuntimeError, match="ReferenceError"):
            helpers.page_info()


def test_current_tab_uses_daemon_connection_status_page():
    def fake_send(req):
        assert req == {"meta": "connection_status"}
        return {
            "target_id": "browser-target",
            "session_id": "session-1",
            "page": {
                "targetId": "page-target",
                "title": "Example",
                "url": "https://example.test",
            },
        }

    with patch("browser_harness.helpers._send", side_effect=fake_send):
        assert helpers.current_tab() == {
            "targetId": "page-target",
            "title": "Example",
            "url": "https://example.test",
        }


def test_current_tab_falls_back_to_target_id_from_connection_status():
    def fake_send(req):
        assert req == {"meta": "connection_status"}
        return {"target_id": "page-target", "session_id": "session-1", "page": None}

    def fake_cdp(method, **kwargs):
        assert method == "Target.getTargetInfo"
        assert kwargs == {"targetId": "page-target"}
        return {
            "targetInfo": {
                "targetId": "page-target",
                "type": "page",
                "title": "Example",
                "url": "https://example.test",
            }
        }

    with patch("browser_harness.helpers._send", side_effect=fake_send), \
         patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        assert helpers.current_tab() == {
            "targetId": "page-target",
            "title": "Example",
            "url": "https://example.test",
        }
