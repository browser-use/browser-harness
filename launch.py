"""Launch Chrome with CDP remote debugging enabled on any profile.

Chrome 147+ blocks --remote-debugging-port on the default user data
directory (see chromium/browser_process_impl.cc kDisabledByDefaultUserDataDir).
This module provides launch_chrome() which works around the restriction
without copying data on Linux (CHROME_CONFIG_HOME), and by creating a
temp profile copy on macOS/Windows where the env-var trick does not apply.
"""

import os
import platform
import shutil
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


_BH_STATE = Path.home() / ".local/share/browser-harness"
if platform.system() == "Darwin":
    _BH_STATE = Path.home() / "Library/Application Support/browser-harness"
elif platform.system() == "Windows":
    _BH_STATE = Path.home() / "AppData/Local/browser-harness"


def _find_chrome():
    """Return the path to the Chrome binary, or None."""
    system = platform.system()
    for name in _CHROME_NAMES.get(system, []):
        p = Path(name)
        if p.is_file():
            return str(p)
        import shutil
        found = shutil.which(name)
        if found:
            return found
    return None


def _get_default_user_data_dir():
    """Return the platform-specific default Chrome user data directory."""
    system = platform.system()
    return _DEFAULT_UDIR.get(system, Path.home() / ".config/google-chrome")


def _copy_profile(src: Path, dst: Path):
    """Copy a Chrome profile, skipping lock files that prevent multi-instance."""
    def _ignore_locks(dirpath, names):
        return {n for n in names if n in (
            "SingletonLock", "SingletonSocket", "SingletonCookie",
            "DevToolsActivePort",
        )}
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=_ignore_locks, dirs_exist_ok=False)


def _is_wayland_session():
    """Detect Wayland by checking the current session only."""
    # 1. Check env vars first (fastest, most reliable).
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return True

    # 2. Check the current logind session (not all sessions).
    try:
        sid = os.environ.get("XDG_SESSION_ID")
        if not sid:
            # Fallback: ask loginctl for the current session
            r = subprocess.run(
                ["loginctl", "show-user", os.getlogin(), "-p", "Sessions"],
                capture_output=True, text=True, timeout=3,
            )
            for line in r.stdout.strip().splitlines():
                if line.startswith("Sessions="):
                    sid = line.split("=", 1)[1].strip()
                    break
        if sid:
            r2 = subprocess.run(
                ["loginctl", "show-session", sid, "-p", "Type"],
                capture_output=True, text=True, timeout=3,
            )
            if "wayland" in r2.stdout.lower():
                return True
    except Exception:
        pass

    # 3. Check for a Wayland socket as last resort.
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

    Chrome 147+ branded builds block --remote-debugging-port when the
    default user-data directory is used (chromium/browser_process_impl.cc
    kDisabledByDefaultUserDataDir).

    Strategy by platform:
      - Linux: set CHROME_CONFIG_HOME to a persistent fake path. Chrome
        computes the default dir as $CHROME_CONFIG_HOME/google-chrome; by
        keeping --user-data-dir on the real profile the paths differ and the
        check passes. No data copy needed.
      - macOS / Windows: CHROME_CONFIG_HOME is not honoured, so we create a
        temporary *copy* of the real profile and point --user-data-dir at the
        copy. The copy is refreshed on first launch after the real profile
        changes.

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
            chrome_config_home: The CHROME_CONFIG_HOME path used (Linux only).

    Raises:
        RuntimeError: If Chrome not found or DevTools doesn't come up.
    """
    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError(
            "Chrome not found. Install Google Chrome or Chromium, or set "
            "BU_CDP_WS to an existing browser's CDP WebSocket URL."
        )

    system = platform.system()
    real_udir = Path(user_data_dir) if user_data_dir else _get_default_user_data_dir()
    real_udir = real_udir.expanduser().resolve()

    # ------------------------------------------------------------------
    # Cross-platform workaround for Chrome 147+ default-profile block.
    # ------------------------------------------------------------------
    if system == "Linux":
        # Linux: CHROME_CONFIG_HOME is honoured by Chrome.
        config_home = _BH_STATE / "chrome-config-home"
        config_home.mkdir(parents=True, exist_ok=True)
        udir = real_udir
        env_extra = {"CHROME_CONFIG_HOME": str(config_home)}
    else:
        # macOS / Windows: CHROME_CONFIG_HOME is ignored.
        # Create a temp copy so --user-data-dir is "non-default".
        copy_udir = _BH_STATE / "chrome-profile-copy"
        # Only re-copy if the real profile is newer than the copy.
        should_copy = True
        if copy_udir.exists():
            real_mtime = max(
                (p.stat().st_mtime for p in real_udir.rglob("*") if p.is_file()),
                default=0,
            )
            copy_mtime = max(
                (p.stat().st_mtime for p in copy_udir.rglob("*") if p.is_file()),
                default=0,
            )
            should_copy = real_mtime > copy_mtime
        if should_copy:
            _copy_profile(real_udir, copy_udir)
        udir = copy_udir
        config_home = None
        env_extra = {}

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

    env = {**os.environ, **env_extra}

    # Redirect stderr to a temp file so the pipe buffer can't block Chrome.
    stderr_path = _BH_STATE / f"chrome-{port}.stderr.log"
    stderr_fh = open(stderr_path, "wb")

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=stderr_fh,
        start_new_session=True,
    )

    result = {
        "pid": proc.pid,
        "user_data_dir": str(udir),
        "port": port,
    }
    if config_home:
        result["chrome_config_home"] = str(config_home)

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
            # Method 2: Probe the port directly (Chrome 147+ may not write
            # DevToolsActivePort when started with a fixed
            # --remote-debugging-port and CHROME_CONFIG_HOME).
            try:
                s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect(("127.0.0.1", port))
                s.close()
                # Port is listening — fetch ws_url from /json/version
                import urllib.request, json
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/json/version", timeout=3
                )
                data = json.loads(resp.read())
                result["ws_url"] = data.get(
                    "webSocketDebuggerUrl",
                    f"ws://127.0.0.1:{port}/devtools/browser",
                )
                return result
            except Exception:
                pass
            # Check if Chrome exited
            if proc.poll() is not None:
                stderr_fh.close()
                try:
                    stderr = stderr_path.read_text(errors="replace")[:500]
                except Exception:
                    stderr = "<unable to read stderr log>"
                raise RuntimeError(
                    f"Chrome exited with code {proc.returncode}. "
                    f"stderr: {stderr}"
                )
            time.sleep(0.5)
        raise RuntimeError(
            f"Timed out waiting for DevToolsActivePort after {wait_timeout}s. "
            f"Chrome may be showing a dialog. Check the Chrome window."
        )

    return result
