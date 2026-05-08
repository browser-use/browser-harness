"""Inline screenshot extension for browser-harness.

capture_screenshot() saves a PNG like the core helper, and can also emit a
base64 input_image marker on stdout for agent loops that support typed content.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from . import _ipc as ipc


CORE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CORE_DIR.parent.parent
NAME = os.environ.get("BU_NAME", "default")

_MARKER_START = "\x00INLINE_IMAGE:"
_MARKER_END = ":INLINE_IMAGE\x00"
_MARKER_RE = re.compile(r"\x00INLINE_IMAGE:(.*?):INLINE_IMAGE\x00", re.DOTALL)


def _send(req):
    c, token = ipc.connect(NAME, timeout=5.0)
    try:
        r = ipc.request(c, token, req)
    finally:
        c.close()
    if "error" in r:
        raise RuntimeError(r["error"])
    return r


def cdp(method, session_id=None, **params):
    """Raw CDP for the inline screenshot extension."""
    helpers = sys.modules.get("browser_harness.helpers")
    helpers_cdp = getattr(helpers, "cdp", None)
    if helpers_cdp is not None:
        return helpers_cdp(method, session_id=session_id, **params)
    return _send({"method": method, "params": params, "session_id": session_id}).get(
        "result", {}
    )


def _emit_inline(path: str, detail: str = "auto") -> None:
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    block = {
        "type": "input_image",
        "detail": detail,
        "image_url": f"data:image/png;base64,{data}",
    }
    sys.stdout.write(
        _MARKER_START + json.dumps(block, separators=(",", ":")) + _MARKER_END
    )
    sys.stdout.flush()


def capture_screenshot(
    path: str | None = None,
    full: bool = False,
    max_dim: int | None = None,
    attach: bool = True,
    detail: str = "auto",
) -> str:
    """Save a PNG and optionally emit it as an inline image marker."""
    path = path or str(ipc._TMP / "shot.png")
    r = cdp("Page.captureScreenshot", format="png", captureBeyondViewport=full)
    Path(path).write_bytes(base64.b64decode(r["data"]))
    if max_dim:
        from PIL import Image

        img = Image.open(path)
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim))
            img.save(path)
    if attach:
        _emit_inline(path, detail=detail)
    return path


def parse_tool_stdout(raw: str) -> tuple[str, list[dict[str, Any]]]:
    """Split raw stdout into clean text and input_image blocks."""
    image_blocks: list[dict[str, Any]] = []
    for match in _MARKER_RE.finditer(raw):
        try:
            image_blocks.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            pass
    return _MARKER_RE.sub("", raw), image_blocks


def build_tool_content(
    text: str,
    image_blocks: list[dict[str, Any]],
) -> str | list[dict[str, Any]]:
    """Build a provider-ready tool-result content value."""
    if not image_blocks:
        return text
    content: list[dict[str, Any]] = []
    if text.strip():
        content.append({"type": "input_text", "text": text})
    content.extend(image_blocks)
    return content
