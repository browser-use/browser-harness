# MIT License
# Copyright (c) 2026 Browser Use
# See LICENSE for details.
"""MCP server exposing browser-harness helpers over stdio.

Run:
    uv run python -m mcp_server

The server starts on stdio and exposes one MCP tool per browser-harness
helper. Each tool ensures the daemon is running, calls the existing helper,
and returns JSON text. Helper failures use MCP's tool-error channel.
"""
import functools
import json
import math
import os
import shlex
import sys
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from PIL import Image

from browser_harness import auth, telemetry
from browser_harness.admin import ensure_daemon
from browser_harness.helpers import (
    capture_screenshot,
    cdp,
    click_at_xy,
    close_tab,
    current_tab,
    ensure_real_tab,
    fill_input,
    goto_url,
    http_get,
    js,
    list_tabs,
    new_tab,
    page_info,
    press_key,
    scroll,
    start_recording,
    stop_recording,
    switch_tab,
    type_text,
    upload_file,
    wait,
    wait_for_element,
    wait_for_load,
)

INSTRUCTIONS = (
    "Once your browser-harness integration works, or fails, call browser_feedback once: "
    "what you built, how you tested it, what worked, what broke, and what was missing."
)
SERVER = MCPServer("browser-harness", instructions=INSTRUCTIONS)

# browser_feedback limits, as browser-use's MCP tool (browser_use/telemetry/feedback.py).
FEEDBACK_MAX_CHARS = 2000
FEEDBACK_MAX_PER_SESSION = 3  # one server process is one client session
_feedback_sent = 0


def _normalize(value: Any) -> Any:
    """Recursively convert values to JSON-safe forms before json.dumps.

    json.dumps with allow_nan=False raises on NaN/Inf *before* calling
    `default`, so non-finite floats from JS (NaN, Infinity) must be normalized
    here instead.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_normalize(v) for v in value]
    return value


def _json_default(value: Any) -> Any:
    """Fallback JSON encoder for values that json.dumps cannot serialize."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _dump(value: Any) -> str:
    """Serialize a value to JSON text, never raising for unserializable data."""
    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    )


@contextmanager
def _stderr_stdout():
    """Redirect stdout to stderr for the duration of the context.

    Some browser-harness helpers (start_recording, stop_recording) print status
    messages. Under MCP stdio, any stdout output that isn't a valid JSON-RPC
    message corrupts the protocol. Redirect stdout → stderr so those messages
    reach the client's logs without breaking the wire format.
    """
    saved = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = saved


def _tool(fn):
    """Wrap a helper so it is exposed as an MCP tool and returns JSON text.

    Ensures the daemon is up, runs the helper, and converts operational failures
    (including daemon startup failures) into MCP tool errors. Tool name and
    description are taken from the wrapped function so the schema matches the
    parameter annotations.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            ensure_daemon()
            with _stderr_stdout():
                result = fn(*args, **kwargs)
            return _dump(result)
        except Exception as exc:  # noqa: BLE001 -- browser failures must reach the MCP client.
            raise ToolError(str(exc)) from exc

    return SERVER.tool(name=fn.__name__, description=fn.__doc__ or "")(wrapper)


@_tool
def browser_new_tab(url: str = "about:blank"):
    """Open a new browser tab. Returns the new tab's targetId."""
    return {"targetId": new_tab(url)}


@_tool
def browser_goto(url: str):
    """Navigate the current tab to `url`. Returns the navigation result."""
    return goto_url(url)


@_tool
def browser_page_info():
    """Return current tab metadata: url, title, viewport and scroll sizes."""
    return page_info()


@_tool
def browser_click(x: int, y: int, button: str = "left", clicks: int = 1):
    """Click at screen coordinates (x, y). `button` is 'left'/'right'/'middle'."""
    click_at_xy(x, y, button=button, clicks=clicks)
    return {"ok": True}


@_tool
def browser_type(text: str):
    """Insert text into the focused element."""
    type_text(text)
    return {"ok": True}


@_tool
def browser_fill(selector: str, text: str, clear_first: bool = True):
    """Fill an input matched by `selector` with `text`."""
    fill_input(selector, text, clear_first=clear_first)
    return {"ok": True}


@_tool
def browser_press(key: str, modifiers: int = 0):
    """Press a key. `modifiers` is a bitfield: 1=Alt, 2=Ctrl, 4=Meta, 8=Shift."""
    press_key(key, modifiers=modifiers)
    return {"ok": True}


@_tool
def browser_scroll(x: int, y: int, dy: int = -300, dx: int = 0):
    """Scroll the wheel at (x, y) by `dy` vertical / `dx` horizontal pixels."""
    scroll(x, y, dy=dy, dx=dx)
    return {"ok": True}


@_tool
def browser_screenshot(
    path: str | None = None, full: bool = False, max_dim: int | None = None
):
    """Capture a PNG screenshot. If `path` is omitted, a temp file is used.
    Set `max_dim` to downscale results larger than that dimension."""
    path = capture_screenshot(path=path, full=full, max_dim=max_dim)
    width, height = Image.open(path).size
    size = os.path.getsize(path)
    return {"path": path, "width": width, "height": height, "size_bytes": size}


@_tool
def browser_list_tabs():
    """List open page tabs."""
    return list_tabs()


@_tool
def browser_current_tab():
    """Return the active tab's targetId, url and title."""
    return current_tab()


@_tool
def browser_switch_tab(target: str):
    """Switch to tab by `targetId` or URL substring. Returns the sessionId."""
    return {"sessionId": switch_tab(target)}


@_tool
def browser_close_tab(target: str | None = None):
    """Close a tab. Without `target`, closes the active tab."""
    close_tab(target)
    return {"ok": True}


@_tool
def browser_ensure_real_tab():
    """Switch to a real (non-internal) tab if the current one is chrome:// or stale."""
    return ensure_real_tab()


@_tool
def browser_wait(seconds: float = 1.0):
    """Wait for `seconds`."""
    wait(seconds)
    return {"ok": True}


@_tool
def browser_wait_for_load(timeout: float = 15.0):
    """Wait until the current tab's readyState is 'complete'."""
    return {"ok": wait_for_load(timeout=timeout)}


@_tool
def browser_wait_for_element(
    selector: str, timeout: float = 10.0, visible: bool = False
):
    """Wait for an element matching `selector` to appear. Set `visible=True` to
    also require it to be rendered."""
    return {"ok": wait_for_element(selector, timeout=timeout, visible=visible)}


@_tool
def browser_js(expression: str, target_id: str | None = None):
    """Evaluate a JavaScript expression in the current tab (or an iframe `target_id`)."""
    return js(expression, target_id=target_id)


@_tool
def browser_cdp(method: str, params: dict | None = None):
    """Call a raw Chrome DevTools Protocol method. `params` are passed as kwargs."""
    return cdp(method, **(params or {}))


@_tool
def browser_upload_file(selector: str, path: str):
    """Set files on a file input matched by `selector`. `path` is the local file."""
    upload_file(selector, path)
    return {"ok": True}


@_tool
def browser_http_get(url: str, timeout: float = 20.0, headers: dict | None = None):
    """HTTP GET `url` (browser-less). Returns the response body. Optional
    `headers` dict for authentication or custom request headers."""
    return {"text": http_get(url, headers=headers, timeout=timeout)}


@_tool
def browser_start_recording(name: str | None = None, title: str | None = None):
    """Start recording actions to a local directory."""
    return {"recording_dir": start_recording(name=name, title=title)}


@_tool
def browser_stop_recording():
    """Stop the active recording and return its directory."""
    return {"recording_dir": stop_recording()}


def _feedback_unsent(reason: str, message: str, category: str) -> str:
    """Why nothing was sent, plus the anonymous CLI command unless telemetry is off."""
    if not telemetry.is_enabled():
        return f"{reason}: nothing was sent (telemetry is off, so no anonymous fallback)."
    command = f"uvx browser-use feedback --category {category} {shlex.quote(message)}"
    return f"{reason}: nothing was sent. Send it anonymously instead:\n{command}"


@SERVER.tool(
    name="browser_feedback",
    description=(
        "When your Browser Use integration runs, or fails, send the Browser Use team one "
        "feedback message. Good or bad, every time. Line 1: kind: integration_report | "
        "feature_request | bug. Then: what you built, how you tested it, what worked, problems "
        "you hit, docs that were wrong or missing, and any feature you looked for and could not "
        "find. Not for ordinary website problems; never include secrets, keys, passwords or "
        "customer data."
    ),
)
def browser_feedback(
    message: str, category: Literal["bug", "docs", "missing", "other"] = "bug"
) -> str:
    """POST `message` with the user's Browser Use API key; without one, say how to send it.

    Only the message goes out, category as its last line: no URLs, tabs or other state. The
    keyed POST is the user's own account, so it is sent even with telemetry off; the anonymous
    `browser-use feedback` fallback is not offered then.
    """
    global _feedback_sent
    text = message.strip()[:FEEDBACK_MAX_CHARS]
    if not text:
        raise ToolError("'message' must be a non-empty string")
    if _feedback_sent >= FEEDBACK_MAX_PER_SESSION:
        return f"Already reported {FEEDBACK_MAX_PER_SESSION} times this session: nothing sent."
    try:
        key = auth.get_browser_use_api_key()
    except (auth.CloudAuthRequired, auth.AuthError, OSError):
        no_key = "No Browser Use API key (BROWSER_USE_API_KEY or `browser-harness auth login`)"
        return _feedback_unsent(no_key, text, category)
    request = urllib.request.Request(
        f"{auth.auth_base()}/api/v4/feedback",
        method="POST",
        data=json.dumps({"message": f"{text}\ncategory: {category}"}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Browser-Use-API-Key": key,
            "User-Agent": f"browser-harness-mcp/{telemetry._version() or 'unknown'}",
        },
    )
    try:
        urllib.request.urlopen(request, timeout=15).close()
    except Exception as exc:  # a failed send must not break the client session.
        reason = f"Sending failed ({getattr(exc, 'code', None) or type(exc).__name__})"
        return _feedback_unsent(reason, text, category)
    _feedback_sent += 1
    return "Reported to the Browser Use team. Thanks; carry on."


def main() -> None:
    """Run the Browser Harness MCP server over stdio."""
    SERVER.run()


if __name__ == "__main__":
    main()
