import base64
import json

from PIL import Image

from browser_harness import inline_screenshot


def _image_block(data="abc", detail="auto"):
    return {
        "type": "input_image",
        "detail": detail,
        "image_url": f"data:image/png;base64,{data}",
    }


def _marker(block):
    return (
        "\x00INLINE_IMAGE:"
        + json.dumps(block, separators=(",", ":"))
        + ":INLINE_IMAGE\x00"
    )


def test_parse_tool_stdout_without_markers_returns_text_unchanged():
    clean, blocks = inline_screenshot.parse_tool_stdout("done\n")

    assert clean == "done\n"
    assert blocks == []


def test_parse_tool_stdout_strips_marker_and_returns_image_block():
    block = _image_block()
    clean, blocks = inline_screenshot.parse_tool_stdout(f"before{_marker(block)}after")

    assert clean == "beforeafter"
    assert blocks == [block]


def test_parse_tool_stdout_collects_multiple_images_in_order():
    first = _image_block("one")
    second = _image_block("two", detail="high")

    clean, blocks = inline_screenshot.parse_tool_stdout(
        f"a{_marker(first)}b{_marker(second)}c"
    )

    assert clean == "abc"
    assert blocks == [first, second]


def test_parse_tool_stdout_ignores_malformed_marker_json():
    clean, blocks = inline_screenshot.parse_tool_stdout(
        "a\x00INLINE_IMAGE:not-json:INLINE_IMAGE\x00b"
    )

    assert clean == "ab"
    assert blocks == []


def test_build_tool_content_returns_plain_text_without_images():
    assert inline_screenshot.build_tool_content("done\n", []) == "done\n"


def test_build_tool_content_returns_typed_blocks_with_text_and_images():
    image = _image_block()

    content = inline_screenshot.build_tool_content("done\n", [image])

    assert content == [{"type": "input_text", "text": "done\n"}, image]


def test_build_tool_content_returns_image_only_blocks_when_text_empty():
    image = _image_block()

    assert inline_screenshot.build_tool_content("\n", [image]) == [image]


def test_capture_screenshot_saves_file_returns_path_and_emits_marker(
    tmp_path, fake_png, capsys, monkeypatch
):
    png_data = fake_png(20, 10)
    shot_path = tmp_path / "shot.png"

    def fake_cdp(method, **kwargs):
        assert method == "Page.captureScreenshot"
        assert kwargs == {"format": "png", "captureBeyondViewport": False}
        return {"data": png_data}

    monkeypatch.setattr(inline_screenshot, "cdp", fake_cdp)

    returned = inline_screenshot.capture_screenshot(str(shot_path))

    assert returned == str(shot_path)
    assert Image.open(shot_path).size == (20, 10)

    clean, blocks = inline_screenshot.parse_tool_stdout(capsys.readouterr().out)
    assert clean == ""
    assert len(blocks) == 1
    assert blocks[0]["type"] == "input_image"
    assert blocks[0]["detail"] == "auto"
    assert blocks[0]["image_url"].startswith("data:image/png;base64,")
    assert base64.b64decode(blocks[0]["image_url"].split(",", 1)[1])


def test_capture_screenshot_attach_false_saves_without_marker(
    tmp_path, fake_png, capsys, monkeypatch
):
    png_data = fake_png(12, 8)
    shot_path = tmp_path / "shot.png"
    monkeypatch.setattr(
        inline_screenshot,
        "cdp",
        lambda method, **kwargs: {"data": png_data},
    )

    returned = inline_screenshot.capture_screenshot(str(shot_path), attach=False)

    assert returned == str(shot_path)
    assert Image.open(shot_path).size == (12, 8)
    assert capsys.readouterr().out == ""


def test_capture_screenshot_resizes_before_emitting_marker(
    tmp_path, fake_png, capsys, monkeypatch
):
    png_data = fake_png(120, 60)
    shot_path = tmp_path / "shot.png"
    monkeypatch.setattr(
        inline_screenshot,
        "cdp",
        lambda method, **kwargs: {"data": png_data},
    )

    inline_screenshot.capture_screenshot(str(shot_path), max_dim=30)

    assert max(Image.open(shot_path).size) == 30
    _, blocks = inline_screenshot.parse_tool_stdout(capsys.readouterr().out)
    emitted_png = base64.b64decode(blocks[0]["image_url"].split(",", 1)[1])
    emitted_path = tmp_path / "emitted.png"
    emitted_path.write_bytes(emitted_png)
    assert max(Image.open(emitted_path).size) == 30


def test_capture_screenshot_does_not_call_overwritten_helpers_function(
    tmp_path, fake_png, monkeypatch
):
    from browser_harness import helpers

    png_data = fake_png(10, 10)
    monkeypatch.setattr(
        inline_screenshot,
        "cdp",
        lambda method, **kwargs: {"data": png_data},
    )

    def overwritten_capture_screenshot(*args, **kwargs):
        raise AssertionError("inline capture must not call helpers.capture_screenshot")

    monkeypatch.setattr(helpers, "capture_screenshot", overwritten_capture_screenshot)

    returned = inline_screenshot.capture_screenshot(
        str(tmp_path / "shot.png"), attach=False
    )

    assert returned.endswith("shot.png")


def test_agent_workspace_activates_inline_capture_screenshot():
    agent_helpers = (
        inline_screenshot.REPO_ROOT / "agent-workspace" / "agent_helpers.py"
    ).read_text()

    assert (
        "from browser_harness.inline_screenshot import capture_screenshot"
        in agent_helpers
    )
