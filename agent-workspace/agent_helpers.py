"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""

import base64
from PIL import Image


def capture_screenshot_jpeg(path=None, full=False, max_dim=None, quality=80):
    """Save a JPEG of the current viewport. Much smaller than PNG — avoids
    LLM API input-length limits on 2× displays.

    quality: 0–100 (default 80). 80 is visually clean and ~5–10× smaller than PNG.
    max_dim: proportional downscale if either side exceeds this (e.g. 1800).
    """
    # Lazy import to avoid circular dep: helpers loads us at module init.
    from browser_harness.helpers import cdp
    from browser_harness._ipc import _TMP

    path = path or str(_TMP / "shot.jpg")
    r = cdp("Page.captureScreenshot", format="jpeg", quality=quality,
            captureBeyondViewport=full)
    open(path, "wb").write(base64.b64decode(r["data"]))
    if max_dim:
        img = Image.open(path)
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim))
            img.save(path, format="JPEG", quality=quality)
    return path