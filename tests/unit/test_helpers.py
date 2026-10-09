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


def test_goto_url_finds_domain_skills_for_subdomain_hosts(tmp_path):
    for site in ("taobao", "github", "item"):
        (tmp_path / "domain-skills" / site).mkdir(parents=True)
        (tmp_path / "domain-skills" / site / f"{site}.md").write_text("x")
    with patch("browser_harness.helpers.cdp", return_value={}), \
         patch("browser_harness.helpers.AGENT_WORKSPACE", tmp_path):
        assert helpers.goto_url("https://cart.taobao.com/cart.htm")["domain_skills"] == ["taobao.md"]
        assert helpers.goto_url("https://www.github.com/x")["domain_skills"] == ["github.md"]
        assert helpers.goto_url("https://item.taobao.com/item.htm")["domain_skills"] == ["item.md"]  # first label still wins
        assert "domain_skills" not in helpers.goto_url("https://example.com/")
