"""CDP WS holder + IPC relay (Unix socket on POSIX, TCP loopback on Windows). One daemon per BU_NAME."""
import asyncio
import ctypes
import ipaddress
import json
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from cdp_use.client import CDPClient

from . import _ipc as ipc
from . import auth, paths


def _load_env():
    repo_root = Path(__file__).resolve().parents[2]
    workspace = paths.workspace_dir()
    for p in (repo_root / ".env", workspace / ".env"):
        if not p.exists():
            continue
        _load_env_file(p)


def _load_env_file(p):
    for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

NAME = os.environ.get("BU_NAME", "default")
SOCK = ipc.sock_addr(NAME)
LOG = str(ipc.log_path(NAME))
PID = str(ipc.pid_path(NAME))
BUF = 500
_MAC_PROFILES = (
    "Library/Application Support/Google/Chrome",
    "Library/Application Support/Google/Chrome Beta",
    "Library/Application Support/Google/Chrome Dev",
    "Library/Application Support/Google/Chrome Canary",
    "Library/Application Support/Comet",
    "Library/Application Support/Comet Beta",
    "Library/Application Support/Comet Canary",
    "Library/Application Support/Arc/User Data",
    "Library/Application Support/Dia/User Data",
    "Library/Application Support/Microsoft Edge",
    "Library/Application Support/Microsoft Edge Beta",
    "Library/Application Support/Microsoft Edge Dev",
    "Library/Application Support/Microsoft Edge Canary",
    "Library/Application Support/BraveSoftware/Brave-Browser",
    "Library/Application Support/BraveSoftware/Brave-Browser-Beta",
    "Library/Application Support/BraveSoftware/Brave-Browser-Nightly",
    "Library/Application Support/BraveSoftware/Brave-Origin",
)
_LINUX_PROFILES = (
    ".config/google-chrome",
    ".config/chromium",
    ".config/chromium-browser",
    ".config/microsoft-edge",
    ".config/microsoft-edge-beta",
    ".config/microsoft-edge-dev",
    ".var/app/org.chromium.Chromium/config/chromium",
    ".var/app/com.google.Chrome/config/google-chrome",
    ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser",
    ".var/app/com.microsoft.Edge/config/microsoft-edge",
)
_WINDOWS_PROFILES = (  # relative to %LOCALAPPDATA%; SxS = Canary channel
    "Google/Chrome/User Data",
    "Google/Chrome SxS/User Data",
    "Google/Chrome Beta/User Data",
    "Google/Chrome Dev/User Data",
    "Chromium/User Data",
    "Microsoft/Edge/User Data",
    "Microsoft/Edge Beta/User Data",
    "Microsoft/Edge Dev/User Data",
    "Microsoft/Edge SxS/User Data",
    "BraveSoftware/Brave-Browser/User Data",
)


def _publish_own_pid(path=PID, pid=None):
    """Atomically retain or publish this daemon's PID record.

    The parent may already have published a process-start fingerprint while
    holding the spawn lock. Never truncate that record: another cold caller
    must not observe an empty PID file and start a sibling daemon.
    """
    pid = pid or os.getpid()
    target = Path(path)
    try:
        published = target.read_text()
        try:
            published_pid = int(json.loads(published)["pid"])
        except (json.JSONDecodeError, TypeError, KeyError):
            published_pid = int(published.split()[0])
    except (FileNotFoundError, OSError, ValueError, IndexError):
        published = str(pid)
        published_pid = pid
    if published_pid != pid:
        published = str(pid)
    tmp = target.with_name(f"{target.name}.{pid}.tmp")
    tmp.write_text(published)
    os.replace(tmp, target)


def profile_dirs(system=None):
    system = system or platform.system()
    if system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
        return [local / p for p in _WINDOWS_PROFILES]
    if system == "Darwin":
        return [Path.home() / p for p in _MAC_PROFILES]
    return [Path.home() / p for p in _LINUX_PROFILES]


PROFILES = profile_dirs()
INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")
BU_API = "https://api.browser-use.com/api/v3"
REMOTE_ID = os.environ.get("BU_BROWSER_ID")
_REMOTE_STOPPED = False
BROWSER_KIND = "cloud" if REMOTE_ID else ("cdp" if (os.environ.get("BU_CDP_WS") or os.environ.get("BU_CDP_URL")) else "local")
# Chrome 144+ shows a per-connection popup, and the connection that raised it is
# the only thing keeping it on screen. There is deliberately no approval
# deadline: expiry would drop the sheet and make a later attempt create another
# connection and another prompt. Chrome/process death and explicit cancellation
# still terminate the pending connection.
LOCAL_HANDSHAKE_TIMEOUT = None
# How long get_ws_url() keeps waiting for DevToolsActivePort before giving up
NO_TOGGLE_GRACE = 3
TOGGLE_BOOT_GRACE = 12
# Cancellation should make an in-flight CDP call finish immediately. Keep the
# drain bounded anyway so shutdown fails closed if a client ignores cancellation.
RECOVERY_CANCEL_DRAIN_TIMEOUT = 2
TAB_MARKER_JS = "if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title"


def tab_marker_enabled():
    """Whether the cosmetic controlled-tab title marker should be added."""
    return os.environ.get("BH_TAB_MARKER", "").strip().lower() not in {"0", "false", "no", "off"}


def _devtools_port_live(base):
    """True when something is listening on the profile's DevToolsActivePort port.

    A stale file left behind by a closed browser must not count as a running
    instance — it would route recovery to "click Allow" on a popup that can't
    exist."""
    try:
        port = int((base / "DevToolsActivePort").read_text(encoding="utf-8", errors="replace").splitlines()[0].strip())
    except (OSError, ValueError, IndexError):
        return False
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
        return True
    except OSError:
        return False


def remote_debugging_user_enabled():
    """chrome://inspect's "Allow remote debugging" toggle

    True only when a toggle-on profile also has a live DevTools port.
    False if a profile records it off, None when no profile records it."""
    seen = None
    for base in PROFILES:
        try:
            state = json.loads((base / "Local State").read_text(encoding="utf-8", errors="replace"))
            enabled = ((state.get("devtools") or {}).get("remote_debugging") or {}).get("user-enabled")
        except (OSError, ValueError, AttributeError):
            continue
        if enabled is True and _devtools_port_live(base):
            return True
        if enabled is False:
            seen = False
    return seen


def remote_debugging_toggle_profiles():
    """Profile dirs whose chrome://inspect toggle is recorded on in Local State"""
    out = []
    for base in PROFILES:
        try:
            state = json.loads((base / "Local State").read_text(encoding="utf-8", errors="replace"))
            if ((state.get("devtools") or {}).get("remote_debugging") or {}).get("user-enabled") is True:
                out.append(base)
        except (OSError, ValueError, AttributeError):
            continue
    return out


def browser_running_for_profile(base):
    """True when a running browser instance holds this user-data-dir (POSIX)"""
    try:
        target = os.readlink(str(base / "SingletonLock"))
    except OSError:
        return False
    try:
        pid = int(target.rsplit("-", 1)[-1])
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True  # pid exists but belongs to another user


def _devtools_active_port_snapshot(base):
    """Read the endpoint and filesystem identity as one validation snapshot."""
    try:
        path = base / "DevToolsActivePort"
        stat = path.stat()
        raw = path.read_bytes()
        lines = raw.decode("utf-8", errors="strict").splitlines()
        port = int(lines[0].strip())
        ws_path = lines[1].strip()
        if not 1 <= port <= 65535 or not ws_path.startswith("/devtools/browser/"):
            return None
        return (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size, raw, str(port), ws_path)
    except (OSError, AttributeError, TypeError, UnicodeError, ValueError, IndexError):
        return None


def _process_args(pid):
    """Return live process arguments using the operating system, or fail closed."""
    try:
        if platform.system() == "Darwin":
            # KERN_PROCARGS2 returns argc followed by NUL-delimited argv. `ps`
            # prints a display string, which cannot distinguish real arguments
            # from switch-like text embedded in another argument.
            mib = (ctypes.c_int * 3)(1, 49, int(pid))  # CTL_KERN, KERN_PROCARGS2
            size = ctypes.c_size_t(0)
            libc = ctypes.CDLL(None, use_errno=True)
            libc.sysctl.argtypes = (
                ctypes.POINTER(ctypes.c_int), ctypes.c_uint, ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t,
            )
            libc.sysctl.restype = ctypes.c_int
            if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
                return None
            buffer = ctypes.create_string_buffer(size.value)
            if libc.sysctl(mib, 3, buffer, ctypes.byref(size), None, 0) != 0:
                return None
            raw = buffer.raw[:size.value]
            argc = struct.unpack_from("i", raw)[0]
            if argc < 1 or len(raw) < 5:
                return None
            offset = 4
            executable_parts = raw[offset:].split(b"\0", 1)
            if len(executable_parts) != 2:
                return None
            executable = executable_parts[0]
            offset += len(executable) + 1
            while offset < len(raw) and raw[offset] == 0:
                offset += 1
            argv = []
            for _ in range(argc):
                arg_parts = raw[offset:].split(b"\0", 1)
                if len(arg_parts) != 2:
                    return None
                arg = arg_parts[0]
                argv.append(os.fsdecode(arg))
                offset += len(arg) + 1
            executable_info = subprocess.check_output(
                ["lsof", "-a", "-p", str(pid), "-d", "txt", "-Fn"],
                text=True, stderr=subprocess.DEVNULL, timeout=2,
            )
            actual_executable = next((line[1:] for line in executable_info.splitlines()
                                      if line.startswith("n") and line[1:].startswith("/")), None)
            if not actual_executable or os.path.realpath(actual_executable) != os.path.realpath(
                os.fsdecode(executable)
            ):
                return None
            return [actual_executable, *argv[1:]]
        if platform.system() == "Windows":
            command = (
                "$p=Get-CimInstance Win32_Process -Filter \"ProcessId=$env:BH_PROCESS_PID\"; "
                "ConvertTo-Json -Compress @{exe=$p.ExecutablePath; command=$p.CommandLine}"
            )
            process_env = os.environ.copy()
            process_env["BH_PROCESS_PID"] = str(int(pid))
            record = json.loads(subprocess.check_output(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                env=process_env,
                text=True, stderr=subprocess.DEVNULL, timeout=3,
            ))
            if not record.get("exe") or not record.get("command"):
                return None
            shell32 = ctypes.WinDLL("shell32", use_last_error=True)
            shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
            shell32.CommandLineToArgvW.argtypes = (
                ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int),
            )
            argc = ctypes.c_int()
            argv_ptr = shell32.CommandLineToArgvW(record["command"], ctypes.byref(argc))
            if not argv_ptr:
                return None
            try:
                argv = [argv_ptr[i] for i in range(argc.value)]
            finally:
                ctypes.windll.kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
                ctypes.windll.kernel32.LocalFree(argv_ptr)
            return [record["exe"], *argv[1:]]
        if platform.system() == "Linux":
            executable = os.readlink(f"/proc/{pid}/exe")
            args = [arg for arg in Path(f"/proc/{pid}/cmdline").read_bytes().decode().split("\0") if arg]
            return [executable, *args[1:]] if executable and args else None
    except (OSError, ValueError, KeyError, IndexError, struct.error, subprocess.SubprocessError):
        pass
    return None


def _trusted_browser_executable(executable):
    """Trust only browser binaries authenticated by the host's package/signing system."""
    system = platform.system()
    path = Path(os.path.realpath(executable))
    if system == "Darwin":
        trusted_signers = {
            "com.google.Chrome": "EQHXZ8M8AV",
            "com.google.Chrome.beta": "EQHXZ8M8AV",
            "com.google.Chrome.canary": "EQHXZ8M8AV",
            "com.google.Chrome.dev": "EQHXZ8M8AV",
            "ai.perplexity.comet": "7S8W4W365S",
            "ai.perplexity.comet-beta": "7S8W4W365S",
            "ai.perplexity.comet-canary": "7S8W4W365S",
            "company.thebrowser.Browser": "S6N382Y83G",
            "company.thebrowser.dia": "S6N382Y83G",
            "com.microsoft.edgemac": "UBF8T346G9",
            "com.microsoft.edgemac.beta": "UBF8T346G9",
            "com.microsoft.edgemac.dev": "UBF8T346G9",
            "com.microsoft.edgemac.canary": "UBF8T346G9",
            "com.brave.Browser": "K8S9R7G5K2",
            "com.brave.Browser.beta": "K8S9R7G5K2",
            "com.brave.Browser.nightly": "K8S9R7G5K2",
        }
        try:
            subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(path)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            details = subprocess.check_output(
                ["/usr/bin/codesign", "-dv", "--verbose=4", str(path)],
                text=True, stderr=subprocess.STDOUT, timeout=5,
            )
            fields = dict(line.split("=", 1) for line in details.splitlines() if "=" in line)
            identifier = fields.get("Identifier")
            image_names = {
                "com.google.Chrome": {"google chrome"},
                "com.google.Chrome.beta": {"google chrome beta"},
                "com.google.Chrome.canary": {"google chrome canary"},
                "com.google.Chrome.dev": {"google chrome dev"},
                "com.microsoft.edgemac": {"microsoft edge"},
                "com.microsoft.edgemac.beta": {"microsoft edge beta"},
                "com.microsoft.edgemac.dev": {"microsoft edge dev"},
                "com.microsoft.edgemac.canary": {"microsoft edge canary"},
                "com.brave.Browser": {"brave browser"},
                "com.brave.Browser.beta": {"brave browser"},
                "com.brave.Browser.nightly": {"brave browser"},
                "ai.perplexity.comet": {"comet"},
                "ai.perplexity.comet-beta": {"comet beta"},
                "ai.perplexity.comet-canary": {"comet canary"},
                "company.thebrowser.Browser": {"arc"},
                "company.thebrowser.dia": {"dia"},
            }
            return (trusted_signers.get(identifier) == fields.get("TeamIdentifier")
                    and path.name.casefold() in image_names.get(identifier, set()))
        except (OSError, ValueError, subprocess.SubprocessError):
            return False
    if system == "Windows":
        script = (
            "$p=$env:BH_BROWSER_EXE; $s=Get-AuthenticodeSignature -LiteralPath $p; "
            "$v=(Get-Item -LiteralPath $p).VersionInfo; "
            "$signer=''; if($s.SignerCertificate) "
            "{$signer=$s.SignerCertificate.GetNameInfo('SimpleName',$false)}; "
            "ConvertTo-Json -Compress @{status=$s.Status.ToString(); signer=$signer; "
            "product=$v.ProductName; description=$v.FileDescription}"
        )
        try:
            identity_env = os.environ.copy()
            identity_env["BH_BROWSER_EXE"] = str(path)
            identity = json.loads(subprocess.check_output(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                env=identity_env,
                text=True, stderr=subprocess.DEVNULL, timeout=5,
            ))
            image = path.name.casefold()
            product = str(identity.get("product") or "").strip().casefold()
            signer = str(identity.get("signer") or "").strip().casefold()
            supported = {
                "chrome.exe": ("google chrome", "google llc"),
                "chromium.exe": ("chromium", "google llc"),
                "brave.exe": ("brave", "brave software, inc."),
                "msedge.exe": ("microsoft edge", "microsoft corporation"),
            }
            expected = supported.get(image)
            return bool(
                identity.get("status") == "Valid" and expected
                and product == expected[0] and signer == expected[1]
            )
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            return False
    if system == "Linux":
        # Require both package ownership and the package's recognized browser image.
        browser_images = {
            "google-chrome": {"chrome", "google-chrome", "google-chrome-stable"},
            "chromium": {"chromium", "chromium-browser"},
            "brave-browser": {"brave-browser", "brave"},
            "microsoft-edge": {"microsoft-edge", "msedge"},
        }
        image = path.name.casefold()
        for command, args, trusted in (
            ("dpkg-query", ["-S", str(path)], ("google-chrome", "chromium", "brave-browser", "microsoft-edge")),
            ("rpm", ["-qf", str(path)], ("google-chrome", "chromium", "brave-browser", "microsoft-edge")),
        ):
            try:
                owner = subprocess.check_output([command, *args], text=True,
                                                stderr=subprocess.DEVNULL, timeout=3).casefold()
                if any(name in owner for name in trusted) and any(
                    image in images for package, images in browser_images.items()
                    if package in owner
                ):
                    return True
            except (OSError, subprocess.SubprocessError):
                continue
    return False


def _trusted_browser_executable_cached(executable, cache):
    """Reuse signature checks only while the executable file identity is unchanged."""
    try:
        path = Path(executable).resolve()
        stat = path.stat()
    except OSError:
        return False
    key = str(path)
    identity = (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
    cached = cache.get(key)
    if cached is None or cached[0] != identity:
        cached = (identity, _trusted_browser_executable(key))
        cache[key] = cached
    return cached[1]


def _profile_argument_matches(args, base):
    """Accept exactly one canonical, effective Chromium profile switch."""
    expected = str(Path(base).resolve())
    profile_switches = []
    for arg in args:
        if not isinstance(arg, str) or arg != arg.strip():
            return False
        if arg == "--":
            break
        if platform.system() == "Windows" and not profile_switches:
            # Windows Chromium treats this switch specially and changes how
            # subsequent command-line arguments are interpreted.
            switch = arg.lstrip("-/").split("=", 1)[0].casefold()
            if switch == "single-argument":
                return False
        # Chromium recognizes Windows-style slash switches as well as dashes.
        # Reject case/spacing/prefix variants and the separate-value form too.
        prefix = arg.lstrip("-/")
        name = prefix.split("=", 1)[0].casefold()
        if name == "user-data-dir":
            if arg.startswith("--user-data-dir="):
                profile_switches.append(arg)
            else:
                return False
    return len(profile_switches) == 1 and profile_switches[0] == f"--user-data-dir={expected}"


def _listener_pids(port):
    """Find OS processes holding a TCP LISTEN socket on port; unknown is empty."""
    try:
        if platform.system() == "Darwin":
            raw = subprocess.check_output(
                ["lsof", "-nP", "-t", f"-iTCP:{int(port)}", "-sTCP:LISTEN"],
                text=True, stderr=subprocess.DEVNULL, timeout=2,
            )
            return {int(line) for line in raw.splitlines() if line.strip()}
        if platform.system() == "Windows":
            raw = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True, stderr=subprocess.DEVNULL, timeout=3,
            )
            owners = set()
            for line in raw.splitlines():
                fields = line.split()
                if (len(fields) >= 5 and fields[0].upper() == "TCP"
                        and fields[3].upper() == "LISTENING"
                        and fields[1].rsplit(":", 1)[-1] == str(int(port))):
                    owners.add(int(fields[4]))
            return owners
        if platform.system() == "Linux":
            wanted = f"{int(port):04X}"
            inodes = set()
            for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
                try:
                    rows = table.read_text().splitlines()[1:]
                except OSError:
                    continue
                for row in rows:
                    fields = row.split()
                    if len(fields) > 9 and fields[3] == "0A" and fields[1].rsplit(":", 1)[-1] == wanted:
                        inodes.add(fields[9])
            if not inodes:
                return set()
            owners = set()
            for proc in Path("/proc").iterdir():
                if not proc.name.isdigit():
                    continue
                try:
                    if any(os.readlink(fd).startswith("socket:[") and
                           os.readlink(fd)[8:-1] in inodes for fd in (proc / "fd").iterdir()):
                        owners.add(int(proc.name))
                except OSError:
                    continue
            return owners
    except (OSError, ValueError, subprocess.SubprocessError):
        return set()
    return set()


def _profile_browser_pid(base, expected_pid=None, trusted_executable_cache=None):
    """Return the verified Chromium PID for this profile, otherwise None."""
    if platform.system() == "Windows":
        pid = expected_pid
        if pid is None:
            return None
    else:
        try:
            lock = os.readlink(str(Path(base) / "SingletonLock"))
            pid = int(lock.rsplit("-", 1)[-1])
        except (OSError, ValueError):
            return None
    if expected_pid is not None and pid != expected_pid:
        return None
    args = _process_args(pid)
    if not args:
        return None
    trusted = (_trusted_browser_executable(args[0]) if trusted_executable_cache is None
               else _trusted_browser_executable_cached(args[0], trusted_executable_cache))
    if not trusted:
        return None
    profile_matches = _profile_argument_matches(args[1:], base)
    if not profile_matches and not _default_profile_matches(args[0], args[1:], base):
        return None
    return pid


def _default_profile_matches(executable, args, base):
    """Allow Chromium's omitted profile switch only for its known default data dir."""
    if any(not isinstance(arg, str) or arg != arg.strip() for arg in args):
        return False
    if any(arg.lstrip("-/").split("=", 1)[0].casefold() == "user-data-dir" for arg in args):
        return False
    executable_name = Path(executable).name.casefold()
    defaults = {
        "Chrome": "google chrome",
        "Chrome Beta": "google chrome beta",
        "Chrome Dev": "google chrome dev",
        "Chrome Canary": "google chrome canary",
    }
    expected_image = defaults.get(Path(base).name)
    expected_profile = Path.home() / "Library/Application Support/Google" / Path(base).name
    return bool(
        expected_image
        and executable_name == expected_image
        and Path(base).resolve() == expected_profile.resolve()
    )


def _endpoint_owned_by_profile(
    base, port, ws_url, snapshot=None, expected_pid=None, expected_host="127.0.0.1",
    trusted_executable_cache=None,
):
    """Bind endpoint response, active-port file, browser PID, and listener PID."""
    before = snapshot or _devtools_active_port_snapshot(base)
    if not before or before[5] != str(port):
        return False
    listeners = _listener_pids(port)
    if len(listeners) != 1:
        return False
    pid = next(iter(listeners))
    if expected_pid is not None and pid != expected_pid:
        return False
    if _profile_browser_pid(base, pid, trusted_executable_cache) != pid:
        return False
    current = _devtools_active_port_snapshot(base)
    return (_listener_pids(port) == {pid}
            and _profile_browser_pid(base, pid, trusted_executable_cache) == pid
            and before == current and _ws_matches_devtools_active_port(
        base, str(port), ws_url, expected_host
    ))


def _profile_process_owns(base, expected_pid=None):
    """Verify SingletonLock's live process command line names this user-data dir."""
    if platform.system() == "Windows":
        return expected_pid is not None and _profile_browser_pid(base, expected_pid) == expected_pid
    try:
        target = os.readlink(str(base / "SingletonLock"))
        pid = int(target.rsplit("-", 1)[-1])
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    return _profile_browser_pid(base, expected_pid) == pid


def supported_browser_running():
    """Is any browser whose profile we scan actually running?"""
    if platform.system() == "Windows":
        # Chromium on Windows uses a named mutex instead of SingletonLock —
        import subprocess
        try:
            out = subprocess.check_output(["tasklist"], text=True, errors="replace", timeout=5).lower()
        except Exception:
            return True  # can't tell — assume running so recovery stays on the popup/toggle path
        return any(n in out for n in ("chrome.exe", "msedge.exe", "chromium.exe", "brave.exe", "helium.exe"))
    return any(browser_running_for_profile(base) for base in PROFILES)


def log(msg):
    open(LOG, "a", encoding="utf-8", errors="replace").write(f"{msg}\n")


def _safe_connection_label(url):
    """Log only endpoint topology, never CDP credentials or provider session paths."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.hostname:
            return "<redacted-cdp-endpoint>"
        host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{host}{port}"
    except (TypeError, ValueError):
        return "<redacted-cdp-endpoint>"


async def _silent(coro):
    try:
        await coro
    except Exception:
        pass


def _ws_from_devtools_active_port(
    http_url: str,
    profile=None,
    snapshot=None,
    expected_pid=None,
    trusted_executable_cache=None,
) -> str | None:
    """Recover a 404 DevTools endpoint only when its profile process owns the endpoint."""
    p = urlparse(http_url)
    want_port = str(p.port) if p.port else ""
    host = p.hostname or ""
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host.lower() == "localhost"
    if (
        p.scheme != "http"
        or not loopback
        or p.username is not None
        or p.password is not None
        or p.query
        or p.fragment
        or not want_port
    ):
        return None
    if ":" in host:  # urlparse strips IPv6 brackets; restore them for the ws:// URL
        host = f"[{host}]"
    for base in ([profile] if profile is not None else [*PROFILES, AUTOMATION_PROFILE]):
        try:
            active = (base / "DevToolsActivePort").read_text(encoding="utf-8", errors="strict").splitlines()
        except (OSError, UnicodeError):
            continue
        port = active[0].strip() if active else ""
        ws_path = active[1].strip() if len(active) > 1 else ""
        ws = f"ws://{host}:{port}{ws_path}"
        if (
            port == want_port
            and ws_path.startswith("/devtools/browser/")
            and _endpoint_owned_by_profile(
                base,
                port,
                ws,
                snapshot,
                expected_pid,
                expected_host=host.strip("[]"),
                trusted_executable_cache=trusted_executable_cache,
            )
        ):
            return ws
    return None


def _ws_matches_devtools_active_port(
    base: Path, port: str, ws_url: str, expected_host="127.0.0.1"
) -> bool:
    """Confirm /json/version belongs to this profile's active browser instance."""
    try:
        active = (base / "DevToolsActivePort").read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        endpoint = urlparse(ws_url)
        host = endpoint.hostname or ""
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == "localhost"
        return (
            len(active) > 1
            and active[0].strip() == port
            and endpoint.scheme == "ws"
            and loopback
            and (endpoint.hostname or "").lower() == expected_host.lower()
            and endpoint.username is None
            and endpoint.password is None
            and endpoint.port == int(port)
            and endpoint.path == active[1].strip()
            and not endpoint.query
            and not endpoint.fragment
        )
    except (OSError, TypeError, ValueError):
        return False


def _http_endpoint_snapshots(http_url, trusted_executable_cache=None):
    """Capture candidate local profile endpoint identities before an HTTP probe."""
    try:
        parsed = urlparse(http_url)
        host = parsed.hostname or ""
        if (parsed.scheme != "http" or parsed.port is None or parsed.username is not None or
                parsed.password is not None or parsed.query or parsed.fragment):
            return []
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == "localhost"
        if not loopback:
            return []
        candidates = [*PROFILES, AUTOMATION_PROFILE]
        # BU_CDP_URL may target an isolated profile outside the discovery list.
        # Derive it only from the process listening on this endpoint, after
        # verifying its browser executable and unambiguous profile argument.
        for pid in _listener_pids(parsed.port):
            args = _process_args(pid)
            if not args:
                continue
            cache = trusted_executable_cache if trusted_executable_cache is not None else {}
            if not _trusted_browser_executable_cached(args[0], cache):
                continue
            profile_arg = _profile_argument_value(args[1:])
            if profile_arg:
                candidates.append(Path(profile_arg))
        unique = dict.fromkeys(Path(base).resolve() for base in candidates)
        return [(base, snapshot) for base in unique
                if (snapshot := _devtools_active_port_snapshot(base))
                and snapshot[5] == str(parsed.port)]
    except (TypeError, ValueError):
        return []


def _profile_argument_value(args):
    """Return one canonical --user-data-dir value; reject ambiguous argv."""
    values = []
    for arg in args:
        if not isinstance(arg, str) or arg != arg.strip():
            return None
        if arg == "--":
            break
        name = arg.lstrip("-/").split("=", 1)[0].casefold()
        if name == "user-data-dir":
            if not arg.startswith("--user-data-dir=") or not arg.partition("=")[2]:
                return None
            values.append(arg.partition("=")[2])
    if len(values) != 1:
        return None
    profile = Path(values[0]).expanduser()
    if not profile.is_absolute():
        return None
    return str(profile.resolve())


def _websocket_url(payload):
    """Read a WebSocket endpoint only from a JSON object with a string field."""
    if not isinstance(payload, dict):
        return None
    ws = payload.get("webSocketDebuggerUrl")
    return ws if isinstance(ws, str) else None


def _http_endpoint_owned(http_url, ws_url, snapshots, trusted_executable_cache=None):
    """Accept a local HTTP endpoint only when its pre-probe identity still owns it."""
    try:
        parsed = urlparse(http_url)
        host = parsed.hostname or ""
        for base, snapshot in snapshots:
            if _endpoint_owned_by_profile(
                base,
                str(parsed.port),
                ws_url,
                snapshot,
                expected_host=host,
                trusted_executable_cache=trusted_executable_cache,
            ):
                return True
    except (TypeError, ValueError):
        return False
    return False


# macOS TCC blocks reading the default browser's profile dir, where the
# DevToolsActivePort file lives. That makes "attach to the running browser"
# impossible without Full Disk Access — so when every profile is unreadable we
# launch a dedicated automation Chrome instead. Its own --user-data-dir lives
# outside the protected path, so /json/version is reachable.
def automation_profile():
    raw = os.environ.get("BH_AUTOMATION_PROFILE")
    return Path(raw).expanduser().resolve() if raw else paths.home_dir() / "chrome-profile"


AUTOMATION_PROFILE = automation_profile()
# Deliberately not 9222 — the user's everyday Chrome usually claims it first,
# and Chrome refuses to share the port (our instance would end up IPv6-only and
# unreachable at 127.0.0.1:9222, which answers 404 from the other instance).
AUTOMATION_PORT = 9223


def _json_version_ws(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as r:
            return _websocket_url(json.loads(r.read()))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
        return None
    except (OSError, KeyError, ValueError):
        return None


def _automation_chrome_binary():
    for key in ("BH_CHROME_PATH", "CHROME_PATH"):
        raw = (os.environ.get(key) or "").strip()
        if raw and Path(raw).expanduser().is_file():
            return str(Path(raw).expanduser())
    if platform.system() == "Darwin":
        for app in ("Google Chrome", "Google Chrome Canary", "Brave Browser", "Microsoft Edge", "Chromium"):
            p = Path(f"/Applications/{app}.app/Contents/MacOS/{app}")
            if p.exists():
                return str(p)
    for cmd in ("google-chrome", "chromium", "chromium-browser", "brave-browser", "microsoft-edge"):
        if w := shutil.which(cmd):
            return w
    return None


def _port_in_use(port):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.3).close()
        return True
    except OSError:
        return False


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def launch_automation_chrome():
    """Launch (or reuse) a dedicated automation browser; return its WS URL.

    Only used as a fallback when the default profile is unreadable (macOS TCC)
    or no debuggable browser is running."""
    # Chrome chooses and records the actual listening port in this profile.
    # Rediscover it after daemon restarts, since AUTOMATION_PORT may have been
    # occupied when this profile was first launched.
    snapshot = _devtools_active_port_snapshot(AUTOMATION_PROFILE)
    active = [snapshot[5], snapshot[6]] if snapshot else []
    port = active[0].strip() if active else ""
    # The port file can outlive Chrome. Reuse it only when the live browser
    # process and OS listener still match the profile and endpoint snapshot.
    if (port.isdigit() and 1 <= int(port) <= 65535 and snapshot
            and (ws := _json_version_ws(int(port)))
            and _endpoint_owned_by_profile(AUTOMATION_PROFILE, port, ws, snapshot)):
        return ws
    binary = _automation_chrome_binary()
    if not binary:
        return None
    port = AUTOMATION_PORT if not _port_in_use(AUTOMATION_PORT) else _free_port()
    try:
        AUTOMATION_PROFILE.mkdir(parents=True, exist_ok=True)
        child = subprocess.Popen(
            [
                binary,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={AUTOMATION_PROFILE}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **ipc.spawn_kwargs(),
        )
    except OSError as e:
        log(f"automation chrome launch failed: {e}")
        return None
    deadline = time.time() + 20
    while time.time() < deadline:
        if child.poll() is not None:
            log("automation chrome launch exited before DevTools became available")
            return None
        snapshot = _devtools_active_port_snapshot(AUTOMATION_PROFILE)
        if (snapshot and (ws := _json_version_ws(port)) and
                _endpoint_owned_by_profile(AUTOMATION_PROFILE, str(port), ws, snapshot, child.pid)):
            log(f"launched dedicated automation chrome on :{port}")
            return ws
        time.sleep(0.3)
    return None


def get_ws_url():
    if url := os.environ.get("BU_CDP_WS"):
        return url
    if url := os.environ.get("BU_CDP_URL"):
        # HTTP DevTools endpoint (e.g. http://127.0.0.1:9333) — resolve to ws via /json/version.
        # Use this for a dedicated automation Chrome on a non-default profile, which avoids the
        # M144 "Allow remote debugging" dialog and the M136 default-profile lockdown.
        deadline = time.time() + 30
        last_err = None
        base_url = url.rstrip("/")
        # A running process cannot change its loaded executable identity during
        # this bounded probe. Cache signature checks by resolved path while
        # still re-reading the live listener argv and endpoint file each retry.
        trusted_executable_cache = {}
        snapshots = []
        next_snapshot_refresh = 0.0
        while time.time() < deadline:
            now = time.time()
            if now >= next_snapshot_refresh:
                snapshots = _http_endpoint_snapshots(url, trusted_executable_cache)
                next_snapshot_refresh = now + 5
            try:
                ws = _websocket_url(json.loads(urllib.request.urlopen(f"{base_url}/json/version", timeout=5).read()))
                if ws and _http_endpoint_owned(
                    url, ws, snapshots, trusted_executable_cache
                ):
                    return ws
                last_err = RuntimeError("endpoint ownership could not be verified")
                time.sleep(1)
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 403:
                    raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
                if e.code == 404:
                    for base, snapshot in snapshots:
                        if ws := _ws_from_devtools_active_port(
                            url,
                            profile=base,
                            snapshot=snapshot,
                            trusted_executable_cache=trusted_executable_cache,
                        ):
                            return ws
                time.sleep(1)
            except Exception as e:
                last_err = e
                time.sleep(1)
        hint = "is the dedicated automation Chrome running? Launch it with --remote-debugging-port=<port> --user-data-dir=<dedicated dir>"
        if platform.system() == "Windows":
            hint += "; on Windows also check that a firewall/antivirus isn't blocking localhost connections"
        raise RuntimeError(f"BU_CDP_URL={url} unreachable after 30s: {last_err} -- {hint}")
    deadline = time.time() + 30
    next_liveness_check = 0.0
    candidate_profiles = set()
    tcc_blocked_profiles = set()
    is_macos = platform.system() == "Darwin"
    while time.time() < deadline:
        for profile_index, base in enumerate(PROFILES):
            if base.exists():
                candidate_profiles.add(profile_index)
            try:
                active = (base / "DevToolsActivePort").read_text(encoding="utf-8", errors="replace").splitlines()
            except FileNotFoundError:
                continue
            except PermissionError:
                candidate_profiles.add(profile_index)
                if is_macos:
                    tcc_blocked_profiles.add(profile_index)
                continue
            except OSError:
                continue
            port = active[0].strip() if active else ""
            ws_path = active[1].strip() if len(active) > 1 else ""
            if not port:
                continue
            snapshot = _devtools_active_port_snapshot(base)
            if not snapshot or snapshot[5] != port:
                continue
            # Resolve the live WS URL via /json/version instead of trusting the path stored
            # alongside the port in DevToolsActivePort: if Chrome was previously launched
            # with a different --user-data-dir on the same port, that file is left behind
            # with a stale browser UUID and the WS upgrade returns 404.
            try:
                ws = _websocket_url(json.loads(
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/json/version", timeout=1
                    ).read()
                ))
                if ws and _endpoint_owned_by_profile(base, port, ws, snapshot):
                    return ws
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
                # Chrome 147+ disables /json/* HTTP discovery on the default user-data-dir;
                # the ws path Chrome wrote to DevToolsActivePort still works.
                if e.code == 404 and ws_path:
                    if ws := _ws_from_devtools_active_port(
                        f"http://127.0.0.1:{port}", profile=base, snapshot=snapshot
                    ):
                        return ws
            except (OSError, KeyError, ValueError):
                pass
        # Closed browser leaves stale DevToolsActivePort files
        now = time.time()
        if now >= next_liveness_check:
            if candidate_profiles and tcc_blocked_profiles == candidate_profiles:
                break
            if not supported_browser_running():
                raise RuntimeError(
                    "chrome-not-running: no supported Chromium-family browser is running -- start Chrome, then retry"
                )
            next_liveness_check = now + 2
        # The browser is running but the port isn't up; waiting 30s
        grace = TOGGLE_BOOT_GRACE if remote_debugging_toggle_profiles() else NO_TOGGLE_GRACE
        if now > deadline - 30 + grace:
            break
        time.sleep(0.2)
    for probe_port in (9222, 9223):
        snapshots = [(base, snapshot) for base in [*PROFILES, AUTOMATION_PROFILE]
                     if (snapshot := _devtools_active_port_snapshot(base))
                     and snapshot[5] == str(probe_port)]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{probe_port}/json/version", timeout=1) as r:
                ws = _websocket_url(json.loads(r.read()))
                owned = bool(ws) and any(
                    _endpoint_owned_by_profile(base, str(probe_port), ws, snapshot)
                    for base, snapshot in snapshots
                )
                if owned:
                    return ws
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
        except (OSError, KeyError, ValueError):
            continue
    all_profiles_tcc_blocked = (
        is_macos
        and bool(candidate_profiles)
        and tcc_blocked_profiles == candidate_profiles
    )
    if all_profiles_tcc_blocked:
        # No profile was readable (macOS TCC) and nothing answered on the probe
        # ports — launch a dedicated automation Chrome so the harness still works.
        if ws := launch_automation_chrome():
            return ws
    if all_profiles_tcc_blocked:
        raise RuntimeError("macOS blocked reading the browser profile dir (needs Full Disk Access). Grant Terminal Full Disk Access in System Settings → Privacy & Security, or run a dedicated automation Chrome and set BU_CDP_URL")
    if remote_debugging_user_enabled() is False:
        raise RuntimeError('remote debugging is turned off for this browser instance — enable chrome://inspect/#remote-debugging (tick "Allow remote debugging for this browser instance")')
    raise RuntimeError(f"DevToolsActivePort not found in {[str(p) for p in PROFILES]} — enable chrome://inspect/#remote-debugging, or set BU_CDP_WS for a remote browser")


def stop_remote(strict=False):
    global _REMOTE_STOPPED
    if not REMOTE_ID:
        return True
    if _REMOTE_STOPPED:
        return True
    last_error = None
    for attempt in range(3):
        try:
            key = auth.get_browser_use_api_key()
            req = urllib.request.Request(
                f"{BU_API}/browsers/{REMOTE_ID}",
                data=json.dumps({"action": "stop"}).encode(),
                method="PATCH",
                headers={"X-Browser-Use-API-Key": key, "Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=15).read()
            _REMOTE_STOPPED = True
            log(f"stopped remote browser {REMOTE_ID}")
            return True
        except Exception as e:
            last_error = e
            log(f"stop_remote attempt {attempt + 1}/3 failed ({REMOTE_ID}): {e}")
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    if strict:
        raise RuntimeError(f"failed to stop remote browser {REMOTE_ID}: {last_error}")
    return False


def is_real_page(t):
    return t["type"] == "page" and not t.get("url", "").startswith(INTERNAL)


def is_reusable_blank_page(t):
    """A plain about:blank tab that is safe to attach to and navigate"""
    url = t.get("url", "")
    return (
        t["type"] == "page"
        and (url == "about:blank" or url.startswith("about:blank#"))
        and not t.get("title", "").startswith("Starting agent ")
    )


def is_inspect_tab(t):
    """A chrome://inspect tab — normally the one the permission flow opened"""
    return t["type"] == "page" and t.get("url", "").startswith("chrome://inspect")


def harness_opened_inspect():
    """True when admin's recovery flow opened a chrome://inspect tab that is
    still awaiting cleanup (the marker survives until the next connect)."""
    try:
        return paths.inspect_marker().exists()
    except OSError:
        return False


def is_reusable_new_tab_page(t):
    """The browser's own New Tab Page, ex: from a fresh launch"""
    return t["type"] == "page" and t.get("url", "").startswith(
        ("chrome://newtab", "chrome://new-tab-page", "edge://newtab", "about:newtab")
    )


class _PatientCDPClient(CDPClient):
    """CDPClient whose local Chrome approval handshake has no deadline."""

    async def start(self):
        import websockets
        if self.ws is not None:
            raise RuntimeError("Client is already started")
        connect_kwargs = {"max_size": self.max_ws_frame_size, "open_timeout": LOCAL_HANDSHAKE_TIMEOUT}
        if self.additional_headers:
            connect_kwargs["additional_headers"] = self.additional_headers
        self.ws = await websockets.connect(self.url, **connect_kwargs)
        self._message_handler_task = asyncio.create_task(self._handle_messages())


class Daemon:
    def __init__(self):
        self.cdp = None
        self.session = None
        self.target_id = None
        self.dedicated_target_id = None
        self._dedicated_target_lock = asyncio.Lock()
        self._session_state_lock = asyncio.Lock()
        self._active_recoveries = 0
        self._recovery_tasks = set()
        self._recoveries_idle = asyncio.Event()
        self._recoveries_idle.set()
        self._shutting_down = False
        self._session_replacements = {}
        self.events = deque(maxlen=BUF)
        self.dialog = None
        self.stop = None  # asyncio.Event, set inside start()

    async def attach_first_page(self, replaces_session=None, enable_domains=True):
        """Attach to a real page (or any page). Sets self.session. Returns attached target or None."""
        targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
        # Named daemons (BU_NAME != "default") share one browser with other
        # daemons — attaching to the first page makes parallel daemons fight
        # over a single tab (navigations clobber each other). Give each named
        # daemon its own dedicated tab instead. REMOTE_ID (cloud) browsers are
        # already exclusive to this daemon, so first-page attach stays.
        if NAME != "default" and not REMOTE_ID:
            # The permission recovery flow can leave chrome://inspect open.
            # Clean it up before returning from this early path as well.
            if BROWSER_KIND == "local":
                await self._close_inspect_tabs(targets)
            pages_by_id = {t["targetId"]: t for t in targets if t["type"] == "page"}
            # A stale CDP session does not necessarily mean its tab disappeared.
            # Reattach to the current tab first, then the daemon's dedicated tab.
            page = pages_by_id.get(self.target_id) or pages_by_id.get(self.dedicated_target_id)
            if page is None:
                # Two stale IPC requests can recover concurrently. Recheck
                # inside a narrow lock so they share one replacement tab.
                async with self._dedicated_target_lock:
                    refreshed = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
                    pages_by_id = {t["targetId"]: t for t in refreshed if t["type"] == "page"}
                    page = pages_by_id.get(self.target_id) or pages_by_id.get(self.dedicated_target_id)
                    if page is None:
                        tid = (await self.cdp.send_raw(
                            "Target.createTarget", {"url": "about:blank", "background": True}
                        ))["targetId"]
                        self.dedicated_target_id = tid
                        log(f"named daemon {NAME}: created dedicated tab ({tid})")
                        page = {"targetId": tid, "url": "about:blank", "type": "page"}
            tid = page["targetId"]
            self.session = (await self.cdp.send_raw(
                "Target.attachToTarget", {"targetId": tid, "flatten": True}
            ))["sessionId"]
            self._record_session_replacement(replaces_session, self.session)
            self.target_id = tid
            log(f"attached {tid} ({page.get('url','')[:80]}) session={self.session}")
            if enable_domains:
                await self._enable_default_domains(self.session)
            return page

        pages = [t for t in targets if is_real_page(t)]
        if not pages:
            # Fresh browser (ex: BU cloud) starts w about:blank; reuse it
            pages = [t for t in targets if is_reusable_blank_page(t)]
        if not pages:
            # Freshly launched browser (ex: harness relaunching closed Chrome)
            # starts with just the New Tab Page. Reuse it — creating about:blank
            pages = [t for t in targets if is_reusable_new_tab_page(t)]
        take_over = None
        if not pages and harness_opened_inspect():
            # After perms granted, only tab is often chrome://inspect
            # Attach to it instead of creating a new about:blank
            inspect_tabs = [t for t in targets if is_inspect_tab(t)]
            if inspect_tabs:
                pages = [inspect_tabs[0]]
                take_over = inspect_tabs[0]["targetId"]
        if not pages:
            # No usable pages - create one instead of attaching to omnibox popup.
            tid = (await self.cdp.send_raw(
                "Target.createTarget", {"url": "about:blank", "background": True}
            ))["targetId"]
            log(f"no real pages found, created about:blank ({tid})")
            pages = [{"targetId": tid, "url": "about:blank", "type": "page"}]
        self.session = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": pages[0]["targetId"], "flatten": True}
        ))["sessionId"]
        self._record_session_replacement(replaces_session, self.session)
        self.target_id = pages[0]["targetId"]
        log(f"attached {pages[0]['targetId']} ({pages[0].get('url','')[:80]}) session={self.session}")
        if take_over:
            try:
                await self.cdp.send_raw("Page.navigate", {"url": "about:blank"}, session_id=self.session)
                log(f"took over inspect tab {take_over} -> about:blank")
            except Exception as e:
                log(f"take over inspect tab {take_over}: {e}")
        if BROWSER_KIND == "local":
            await self._close_inspect_tabs(targets)
        if enable_domains:
            await self._enable_default_domains(self.session)
        return pages[0]

    async def _close_inspect_tabs(self, targets):
        """Close chrome://inspect tabs left open by the permission recovery flow"""
        if not harness_opened_inspect():
            return
        for t in targets:
            if t["targetId"] != self.target_id and is_inspect_tab(t):
                try:
                    await self.cdp.send_raw("Target.closeTarget", {"targetId": t["targetId"]})
                    log(f"closed leftover chrome://inspect tab {t['targetId']}")
                except Exception as e:
                    log(f"close inspect tab {t['targetId']}: {e}")
        try:
            paths.inspect_marker().unlink()
        except OSError:
            pass

    async def _enable_default_domains(self, session_id):
        """Enable Page/DOM/Runtime/Network on a CDP session.

        Used by both initial attach and set_session (called after switch_tab/
        new_tab). Without this, helpers that depend on Network.* events —
        notably wait_for_network_idle() — silently stop receiving events
        after a tab switch, because each fresh CDP session starts with all
        domains disabled.

        Runs the four enables in parallel via gather so the worst-case time is
        bounded by a single CDP round trip rather than four sequential ones —
        important on the set_session path, where the helper's IPC socket has
        a 5s read timeout.
        """
        async def enable_one(d):
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw(f"{d}.enable", session_id=session_id),
                    timeout=4,
                )
            except Exception as e:
                log(f"enable {d} on {session_id}: {e}")
        await asyncio.gather(*(enable_one(d) for d in ("Page", "DOM", "Runtime", "Network")))

    def _record_session_replacement(self, stale_session, replacement_session):
        """Remember which recovered session still controls the same tab."""
        if not stale_session or not replacement_session or stale_session == replacement_session:
            return
        # Preserve chains so requests delayed across multiple recoveries still
        # land on their original tab, never whichever tab is current now.
        for source, replacement in list(self._session_replacements.items()):
            if replacement == stale_session:
                self._session_replacements[source] = replacement_session
        self._session_replacements[stale_session] = replacement_session
        while len(self._session_replacements) > 32:
            self._session_replacements.pop(next(iter(self._session_replacements)))

    def _begin_recovery(self):
        """Register the current IPC handler unless shutdown has started."""
        if self._shutting_down:
            return None
        task = asyncio.current_task()
        if task is None:
            return None
        self._recovery_tasks.add(task)
        self._active_recoveries += 1
        self._recoveries_idle.clear()
        return task

    def _finish_recovery(self, task):
        self._recovery_tasks.discard(task)
        self._active_recoveries -= 1
        if self._active_recoveries == 0:
            self._recoveries_idle.set()

    async def _cancel_and_drain_recoveries(self):
        """Cancel active stale-session handlers and wait a bounded time."""
        current = asyncio.current_task()
        tasks = [
            task for task in self._recovery_tasks
            if task is not current and not task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            _done, pending = await asyncio.wait(
                tasks, timeout=RECOVERY_CANCEL_DRAIN_TIMEOUT
            )
            if pending:
                return False
        return self._recoveries_idle.is_set()

    def _schedule_tab_marker(self, session_id):
        """Mark the controlled tab without extending the synchronous IPC path."""
        if not tab_marker_enabled():
            return None
        return asyncio.create_task(_silent(asyncio.wait_for(
            self.cdp.send_raw(
                "Runtime.evaluate",
                {"expression": TAB_MARKER_JS},
                session_id=session_id,
            ),
            timeout=2,
        )))

    def _record_event(self, method, params, session_id=None):
        self.events.append({"method": method, "params": params, "session_id": session_id})
        if method == "Page.javascriptDialogOpening":
            self.dialog = params
        elif method == "Page.javascriptDialogClosed":
            self.dialog = None
        elif method in ("Page.loadEventFired", "Page.domContentEventFired"):
            self._schedule_tab_marker(self.session)

    async def start(self):
        self.stop = asyncio.Event()
        url = get_ws_url()
        log(f"connecting to {_safe_connection_label(url)}")
        self.cdp = _PatientCDPClient(url) if BROWSER_KIND == "local" else CDPClient(url)
        if BROWSER_KIND == "local":
            # Allow while this handshake is still parked on the popup
            log("handshake-wait: if Chrome shows an 'Allow remote debugging?' popup, click Allow")
        try:
            await self.cdp.start()
        except Exception as e:
            if os.environ.get("BU_CDP_WS"):
                raise RuntimeError(
                    f"CDP WS handshake failed: {e} -- remote browser WebSocket connection failed. "
                    "This can happen when network policy blocks the connection, the WS URL is wrong or expired, or the remote endpoint is down. "
                    "If you use Browser Use cloud, verify auth and get a fresh URL via start_remote_daemon()."
                )
            if BROWSER_KIND == "local" and ("timed out" in str(e).lower() or "403" in str(e)) and remote_debugging_user_enabled():
                raise RuntimeError(
                    "permission-blocked: Chrome did not approve the remote debugging connection; "
                    "browser-harness did not retry or create another connection"
                )
            raise RuntimeError(f"CDP WS handshake failed: {e} -- click Allow in Chrome if prompted, then retry")
        await self.attach_first_page()
        orig = self.cdp._event_registry.handle_event
        async def tap(method, params, session_id=None):
            self._record_event(method, params, session_id)
            return await orig(method, params, session_id)
        self.cdp._event_registry.handle_event = tap

    async def handle(self, req):
        # Token guard for Windows TCP loopback: any local process can otherwise
        # connect and issue CDP commands. expected_token() is None on POSIX so
        # this check is a no-op there (AF_UNIX + chmod 600 is the boundary).
        expected = ipc.expected_token()
        if expected is not None and req.get("token") != expected:
            return {"error": "unauthorized"}
        meta = req.get("meta")
        # Liveness probe — lets clients confirm the listener is actually this
        # daemon and not an unrelated process that reused our port post-crash.
        # `pid` lets restart_daemon() verify the live daemon's identity before
        # signaling — protects against SIGTERM-by-stale-pid-file after PID reuse.
        if meta == "ping":        return {"pong": True, "pid": os.getpid(), "browser_kind": BROWSER_KIND}
        if meta == "drain_events":
            out = list(self.events); self.events.clear()
            return {"events": out}
        if meta == "session":     return {"session_id": self.session}
        if meta == "current_tab":
            # Resolve the attached page's target info server-side. Helpers can't
            # send Target.getTargetInfo themselves: daemon strips session_id for
            # any Target.* method (browser-level call), and without a targetId
            # Chrome silently returns the *browser* target.
            if not self.target_id:
                return {"error": "not_attached"}
            try:
                info = (await self.cdp.send_raw("Target.getTargetInfo", {"targetId": self.target_id}))["targetInfo"]
            except Exception:
                return {"error": "cdp_disconnected"}
            return {"targetId": info.get("targetId"), "url": info.get("url", ""), "title": info.get("title", "")}
        if meta == "connection_status":
            if not self.target_id:
                return {"error": "not_attached"}
            try:
                info = (await self.cdp.send_raw("Target.getTargetInfo", {"targetId": self.target_id}))["targetInfo"]
            except Exception:
                return {"error": "cdp_disconnected"}
            page = None
            if is_real_page(info):
                page = {
                    "targetId": info.get("targetId"),
                    "title": info.get("title") or "(untitled)",
                    "url": info.get("url") or "",
                }
            return {"target_id": self.target_id, "session_id": self.session, "page": page}
        if meta == "set_session":
            async with self._session_state_lock:
                old_session = self.session
                self.session = req.get("session_id")
                self.target_id = req.get("target_id") or self.target_id
                new_session = self.session
            # Run the old-session Network.disable (defense in depth — keeps
            # background-tab traffic out of the global event buffer; the
            # consumer-side filter in wait_for_network_idle is the actual
            # correctness gate) in parallel with the four enables on the new
            # session. Different sessions, independent CDP requests. Keeps
            # the synchronous reply under the helper's 5s IPC read timeout
            # even on a remote daemon — sequentially these would have stacked
            # to ~22s worst case.
            tasks = []
            if old_session and old_session != new_session:
                async def disable_old():
                    try:
                        await asyncio.wait_for(
                            self.cdp.send_raw("Network.disable", session_id=old_session),
                            timeout=2,
                        )
                    except Exception: pass
                tasks.append(disable_old())
            tasks.append(self._enable_default_domains(new_session))
            await asyncio.gather(*tasks)
            # 🐴 tab-marker title prefix is purely cosmetic — fire-and-forget so
            # it doesn't add to the synchronous IPC budget.
            self._schedule_tab_marker(new_session)
            return {"session_id": new_session}
        if meta == "pending_dialog": return {"dialog": self.dialog}
        if meta == "shutdown":
            # Flip the barrier synchronously with recovery registration, then
            # cancel/drain existing handlers. In particular, a CDP replay that
            # never answers must not prevent Cloud cleanup from being attempted.
            if self._shutting_down:
                return {"error": "shutdown already in progress"}
            self._shutting_down = True
            if not await self._cancel_and_drain_recoveries():
                # Preserve the daemon as a retryable cleanup authority. The
                # strict caller will leave its endpoint and PID file intact.
                self._shutting_down = False
                return {"error": "stale-session recovery did not stop"}
            try:
                stop_remote(strict=True)
            except Exception as e:
                # A failed Cloud stop must leave the daemon usable so a later
                # shutdown request can retry the billable-browser cleanup.
                async with self._session_state_lock:
                    self._shutting_down = False
                return {"error": str(e)}
            self.stop.set()
            return {"ok": True}

        method = req["method"]
        params = req.get("params") or {}
        # Browser-level Target.* calls must not use a session (stale or otherwise).
        # For everything else, explicit session in req wins; else default.
        sid = None if method.startswith("Target.") else (req.get("session_id") or self.session)
        try:
            return {"result": await self.cdp.send_raw(method, params, session_id=sid)}
        except Exception as e:
            msg = str(e)
            if "Session with given id not found" in msg and sid:
                # Explicit session callers asked for that exact session; do not
                # silently redirect them to the daemon's current tab.
                if req.get("session_id"):
                    return {"error": msg}
                recovery_task = self._begin_recovery()
                if recovery_task is None:
                    return {"error": "daemon is shutting down"}
                try:
                    recovered_here = False
                    async with self._session_state_lock:
                        if self._shutting_down:
                            return {"error": "daemon is shutting down"}
                        replacement_session = self._session_replacements.get(sid)
                        if replacement_session is None and sid == self.session:
                            log(f"stale session {sid}, re-attaching")
                            if not await self.attach_first_page(
                                replaces_session=sid, enable_domains=False
                            ):
                                return {"error": msg}
                            replacement_session = self._session_replacements.get(sid)
                            recovered_here = replacement_session is not None
                    if recovered_here:
                        await self._enable_default_domains(replacement_session)
                    # Retry only on a session known to replace this exact stale
                    # session. self.session may instead have changed because the
                    # user deliberately switched tabs while this request waited.
                    if replacement_session:
                        try:
                            return {"result": await self.cdp.send_raw(
                                method, params, session_id=replacement_session
                            )}
                        except Exception as retry_error:
                            return {"error": str(retry_error)}
                finally:
                    self._finish_recovery(recovery_task)
            return {"error": msg}


async def serve(d):
    async def handler(reader, writer):
        try:
            line = await reader.readline()
            if not line: return
            resp = await d.handle(json.loads(line))
            writer.write((json.dumps(resp, default=str) + "\n").encode())
            await writer.drain()
        except Exception as e:
            log(f"conn: {e}")
            try:
                writer.write((json.dumps({"error": str(e)}) + "\n").encode())
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()

    serve_task = asyncio.create_task(ipc.serve(NAME, handler))
    stop_task = asyncio.create_task(d.stop.wait())
    await asyncio.sleep(0.05)  # let serve() bind so sock_addr() resolves to the live endpoint
    log(f"listening on {ipc.sock_addr(NAME)} (name={NAME}, remote={REMOTE_ID or 'local'})")
    try:
        await asyncio.wait({serve_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        if serve_task.done(): await serve_task  # surfaces a serve crash
    finally:
        for t in (serve_task, stop_task):
            t.cancel()
            try: await t
            except (asyncio.CancelledError, Exception): pass
        # A server crash/cancellation does not pass through meta=shutdown.
        # Establish the same recovery barrier before touching owned targets.
        d._shutting_down = True
        recoveries_drained = await d._cancel_and_drain_recoveries()
        # Named non-cloud daemons create one dedicated background tab. Shutdown
        # has blocked new recovery and drained active recovery before setting
        # d.stop (or finalization established the barrier after a server crash).
        # Take the same locks, in the same order as recovery, so cleanup closes
        # exactly the final daemon-owned target and never races creation.
        if recoveries_drained:
            async with d._session_state_lock:
                async with d._dedicated_target_lock:
                    if d.dedicated_target_id and d.cdp:
                        try:
                            await d.cdp.send_raw(
                                "Target.closeTarget", {"targetId": d.dedicated_target_id}
                            )
                            d.dedicated_target_id = None
                        except Exception as e:
                            log(f"close dedicated tab on shutdown: {e}")
        else:
            log("skip dedicated-tab cleanup: stale-session recovery did not stop")
        ipc.cleanup_endpoint(NAME)


async def main():
    d = Daemon()
    await d.start()
    await serve(d)


def already_running():
    # Ping handshake (not a bare connect) so a stale .port file + port reuse
    # after a daemon crash doesn't make us mistake an unrelated listener for ours.
    return ipc.ping(NAME, timeout=1.0)


if __name__ == "__main__":
    if already_running():
        print(f"daemon already running on {SOCK}", file=sys.stderr)
        sys.exit(0)
    open(LOG, "w").close()
    _publish_own_pid()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log(f"fatal: {e}")
        sys.exit(1)
    finally:
        stop_remote()
        try: os.unlink(PID)
        except FileNotFoundError: pass
