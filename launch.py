"""Launch Chrome with CDP remote debugging enabled on any profile.

Chrome 147+ blocks --remote-debugging-port on the default user data
directory (see chromium/browser_process_impl.cc kDisabledByDefaultUserDataDir).
This module provides launch_chrome() which works around the restriction by
setting CHROME_CONFIG_HOME to a temporary path, making Chrome think the
real profile directory is "non-default" while keeping all user data intact.
"""

import os
import platform
import subprocess
import time
from pathlib import Path

# Known default user data directories per platform
_DEFAULT_UDIR = {
    "Linux": Path.home() / ".config/google-chrome",
    "Darwin": Path.home() / "Library/Application Support/Google/Chrome",
    "Windows": Path.home() / "AppData/Local/Google/Chrome/User Data",
}

_CHROME_NAMES = {
    "Linux": ["google-chrome", "chromium-browser", "chromium"],
    "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
    "Windows": [
        str(Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))
            / "Google/Chrome/Application/chrome.exe"),
        str(Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"))
            / "Google/Chrome/Application/chrome.exe"),
    ],
}


def _find_chrome():
    """Return the path to the Chrome binary, or None."""
    system = platform.system()
    for name in _CHROME_NAMES.get(system, []):
        p = Path(name)
        if p.is_file():
            return str(p)
        # Search PATH
        import shutil
        found = shutil.which(name)
        if found:
            return found
    return None


def _get_default_user_data_dir():
    """Return the platform-specific default Chrome user data directory."""
    system = platform.system()
    return _DEFAULT_UDIR.get(system, Path.home() / ".config/google-chrome")


def _is_wayland_session():
    """Detect Wayland by checking loginctl or running processes."""
    try:
        # Try loginctl with session ID
        import subprocess
        r = subprocess.run(
            ["loginctl"], capture_output=True, text=True, timeout=3,
        )
        # Parse session ID from output
        for line in r.stdout.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 1:
                sid = parts[0]
                r2 = subprocess.run(
                    ["loginctl", "show-session", sid, "-p", "Type"],
                    capture_output=True, text=True, timeout=3,
                )
                if "wayland" in r2.stdout.lower():
                    return True
    except Exception:
        pass
    try:
        # Check if gnome-shell is running with wayland
        r = subprocess.run(
            ["pgrep", "-a", "gnome-shell"],
            capture_output=True, text=True, timeout=3,
        )
        if "wayland" in r.stdout.lower():
            return True
    except Exception:
        pass
    # Check for wayland socket
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
    if Path(runtime_dir, "wayland-0").exists():
        return True
    return False


def is_chrome147_plus():
    """Quick heuristic: Chrome 147+ blocks remote debugging on default profile."""
    # We can check by trying to start Chrome with remote debugging on the
    # default profile and seeing if DevToolsActivePort appears. But that's
    # expensive. For now, we assume Chrome 147+ on branded builds (the
    # check is #if BUILDFLAG(GOOGLE_CHROME_BRANDING)).
    chrome = _find_chrome()
    if not chrome:
        return False
    try:
        out = subprocess.check_output([chrome, "--version"], text=True, timeout=5).strip()
        # "Google Chrome 147.0.7727.55"
        parts = out.split()
        if len(parts) >= 3:
            version = parts[2].split(".")[0]
            return int(version) >= 147
    except Exception:
        pass
    return False


def launch_chrome(
    port=9222,
    user_data_dir=None,
    headless=False,
    extra_args=None,
    wait=True,
    wait_timeout=15,
):
    """Launch Chrome with remote debugging enabled, bypassing the Allow dialog.

    Works on Chrome 147+ by setting CHROME_CONFIG_HOME to a temp path so the
    default-user-data-dir check doesn't block remote debugging.

    Args:
        port:             Remote debugging port (default 9222).
        user_data_dir:    Path to Chrome profile. Default: platform default.
        headless:         Run headless (--headless=new).
        extra_args:       Additional Chrome flags (list of strings).
        wait:             Block until DevToolsActivePort appears.
        wait_timeout:     Seconds to wait for DevToolsActivePort.

    Returns:
        dict with keys:
            pid:              Chrome process PID.
            user_data_dir:    Absolute path to the profile used.
            port:             The debugging port.
            ws_url:           WebSocket debugger URL (only if wait=True).
            chrome_config_home: The temp CHROME_CONFIG_HOME path used.

    Raises:
        RuntimeError: If Chrome not found or DevTools doesn't come up.
    """
    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError(
            "Chrome not found. Install Google Chrome or Chromium, or set "
            "BU_CDP_WS to an existing browser's CDP WebSocket URL."
        )

    udir = Path(user_data_dir) if user_data_dir else _get_default_user_data_dir()
    udir = udir.expanduser().resolve()

    # Create a temp CHROME_CONFIG_HOME so IsUsingDefaultDataDirectory() returns false.
    # We set CHROME_CONFIG_HOME to /tmp/bu-chrome-config-XXXXX, and Chrome computes
    # the "default" dir as $CHROME_CONFIG_HOME/google-chrome. Since our --user-data-dir
    # points to the real ~/.config/google-chrome, the paths differ and the check passes.
    system = platform.system()
    if system == "Darwin":
        dir_name = "google-chrome"
    elif system == "Windows":
        dir_name = "Google\\Chrome"
    else:
        dir_name = "google-chrome"

    # Persistent fake CHROME_CONFIG_HOME so Chrome only asks to "Allow remote
    # debugging" once.  Chrome computes the default user-data dir from this
    # path; by pointing --user-data-dir at the real profile the paths differ
    # and Chrome 147+'s restriction is bypassed.  Keeping the same fake home
    # across restarts makes the permission sticky.
    config_home = Path.home() / ".local/share/browser-harness/chrome-config-home"
    config_home.mkdir(parents=True, exist_ok=True)

    cmd = [
        chrome,
        f"--remote-debugging-port={port}",
        "--no-first-run",
        f"--user-data-dir={udir}",
    ]
    # Auto-detect display server on Linux
    if system == "Linux":
        wayland = (
            os.environ.get("WAYLAND_DISPLAY")
            or os.environ.get("XDG_SESSION_TYPE") == "wayland"
            or _is_wayland_session()
        )
        if wayland:
            cmd.append("--ozone-platform=wayland")
    if headless:
        cmd.append("--headless=new")
    if extra_args:
        cmd.extend(extra_args)

    env = {**os.environ, "CHROME_CONFIG_HOME": config_home}

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )

    result = {
        "pid": proc.pid,
        "user_data_dir": str(udir),
        "port": port,
        "chrome_config_home": config_home,
    }

    if wait:
        import socket as _socket
        port_file = udir / "DevToolsActivePort"
        deadline = time.time() + wait_timeout
        while time.time() < deadline:
            # Method 1: Check DevToolsActivePort file
            if port_file.exists():
                try:
                    content = port_file.read_text().strip().split("\n")
                    if len(content) >= 2:
                        result["ws_url"] = f"ws://127.0.0.1:{content[0]}{content[1]}"
                        return result
                except Exception:
                    pass
            # Method 2: Probe the port directly (Chrome 147+ may not write DevToolsActivePort
            # when started with a fixed --remote-debugging-port and CHROME_CONFIG_HOME)
            try:
                s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect(("127.0.0.1", port))
                s.close()
                # Port is listening — fetch ws_url from /json/version
                import urllib.request, json
                resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3)
                data = json.loads(resp.read())
                result["ws_url"] = data.get("webSocketDebuggerUrl", f"ws://127.0.0.1:{port}/devtools/browser")
                return result
            except Exception:
                pass
            # Check if Chrome exited
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="replace")
                raise RuntimeError(
                    f"Chrome exited with code {proc.returncode}. stderr: {stderr[:500]}"
                )
            time.sleep(0.5)
        raise RuntimeError(
            f"Timed out waiting for DevToolsActivePort after {wait_timeout}s. "
            f"Chrome may be showing a dialog. Check the Chrome window."
        )

    return result
