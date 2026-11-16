"""macOS-only helpers for local Chrome automation."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from .admin import _BROWSER_LAUNCH, _DEFAULT_LAUNCH, daemon_browser_ready
from .daemon import remote_debugging_toggle_profiles

_APPLESCRIPT = r'''using terms from application "System Events"
    on hasApprovalHeading(nodeRef)
        try
            if (role of nodeRef as text) is "AXHeading" and ¬
                (name of nodeRef as text) is "Allow remote debugging?" then
                return true
            end if
        end try
        try
            repeat with childRef in UI elements of nodeRef
                if my hasApprovalHeading(childRef) then return true
            end repeat
        end try
        return false
    end hasApprovalHeading
    on isApprovalSheet(sheetRef)
        -- Chrome <=152 names the sheet; 153+ leaves the name empty and puts
        -- the title in a child AXHeading.
        try
            if (name of sheetRef as text) is "Allow remote debugging?" then return true
        end try
        return my hasApprovalHeading(sheetRef)
    end isApprovalSheet
    on clickAllow(nodeRef)
        try
            if (role of nodeRef as text) is "AXButton" and ¬
                (description of nodeRef as text) is "Allow" then
                perform action "AXPress" of nodeRef
                return true
            end if
        end try
        try
            repeat with childRef in UI elements of nodeRef
                if my clickAllow(childRef) then return true
            end repeat
        end try
        return false
    end clickAllow
end using terms from

set resultText to "not-found"
set browserNames to {__BROWSERS__}
tell application "System Events"
    repeat with browserName in browserNames
        if resultText is "ready" then exit repeat
        if exists process browserName then
            tell process browserName
                repeat with w in windows
                    try
                        repeat with s in sheets of w
                            if my isApprovalSheet(s) then
                                if my clickAllow(s) then
                                    set resultText to "ready"
                                    exit repeat
                                end if
                            end if
                        end repeat
                    end try
                    if resultText is "ready" then exit repeat
                end repeat
            end tell
        end if
    end repeat
end tell
return resultText
'''


# Chromium-family apps that show the same "Allow remote debugging?" sheet: every
# app the launcher knows (admin._BROWSER_LAUNCH) plus channels without a profile
# entry of their own.
_BROWSER_PROCESSES = tuple(dict.fromkeys(
    [_DEFAULT_LAUNCH[0], *(spec[1] for spec in _BROWSER_LAUNCH)]
    + ["Google Chrome Beta", "Google Chrome Dev", "Google Chrome for Testing", "Chromium",
       "Brave Browser Beta", "Brave Browser Nightly", "Microsoft Edge Beta", "Microsoft Edge Dev",
       "Microsoft Edge Canary", "Helium"]
))
_APPLESCRIPT = _APPLESCRIPT.replace(
    "__BROWSERS__", ", ".join(f'"{name}"' for name in _BROWSER_PROCESSES)
)


def _accessibility_trusted():
    """AXIsProcessTrusted() for this process, or None when it cannot be read.

    Same answer osascript would get, without the osascript run: an untrusted
    process otherwise blocks on macOS's Automation consent prompt (5 s here,
    forever for an unattended Mac) before reporting accessibility-required."""
    try:
        import ctypes
        lib = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except (OSError, AttributeError):
        return None


_ACCESSIBILITY_DETAIL = (
    "allow the app launching browser-harness (for example Terminal, iTerm, or Codex) "
    "in System Settings > Privacy & Security > Accessibility"
)


def _google_chrome_root() -> Path:
    return Path.home() / "Library/Application Support/Google/Chrome"


def _google_chrome_toggle_enabled() -> bool:
    """Kept for compatibility: the stock Google Chrome root has the toggle on."""
    return _google_chrome_root() in remote_debugging_toggle_profiles()


def _any_toggle_enabled() -> bool:
    """Some scanned Chromium-family profile has chrome://inspect's toggle on."""
    return bool(remote_debugging_toggle_profiles())


def approve_remote_debugging() -> tuple[str, str | None]:
    """Click Chrome's exact per-connection Allow sheet without activating Chrome."""
    if platform.system() != "Darwin":
        return "unsupported", "mac-approve is only available on macOS"

    if daemon_browser_ready():
        return "ready", None

    if not _any_toggle_enabled():
        return (
            "setup-required",
            'first enable "Allow remote debugging for this browser instance" at '
            "chrome://inspect/#remote-debugging, then run `browser-harness mac-approve` again",
        )

    if _accessibility_trusted() is False:
        return "accessibility-required", _ACCESSIBILITY_DETAIL

    try:
        completed = subprocess.run(
            ["osascript"],
            input=_APPLESCRIPT,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "accessibility-required", _ACCESSIBILITY_DETAIL
    except (OSError, subprocess.SubprocessError) as exc:
        return "error", str(exc)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or "osascript failed"
        if "not authorized" in detail.lower() or "assistive" in detail.lower():
            return (
                "accessibility-required",
                _ACCESSIBILITY_DETAIL,
            )
        return "error", detail

    status = completed.stdout.strip()
    if status == "ready":
        return "ready", None
    if status == "not-found":
        # The user may have accepted the sheet while AppleScript was looking.
        if daemon_browser_ready():
            return "ready", None
        return (
            "not-found",
            "retry the browser command and run `browser-harness mac-approve` when the prompt appears",
        )
    return "error", f"unexpected osascript result: {status or '<empty>'}"


def run_cli(args: list[str]) -> int:
    if args:
        print("usage: browser-harness mac-approve", flush=True)
        return 2

    status, detail = approve_remote_debugging()
    if detail:
        print(f"{status}: {detail}", flush=True)
    else:
        print(status, flush=True)
    return 0 if status == "ready" else 1
