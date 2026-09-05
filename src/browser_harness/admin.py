import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import _ipc as ipc
from . import auth
from . import paths


def _process_start_time(pid):
    """Opaque process-start-time fingerprint at PID, or None if unavailable.

    Two reads returning the same non-None value mean the PID still refers to
    the same process; a different value means the PID was reused. Used by
    restart_daemon() to keep the force-kill recovery path working even when
    the daemon has already torn down its IPC socket (e.g. during a slow
    remote shutdown), without falling back to "trust the pid file" — which
    would re-introduce the PID-reuse hazard.

    Linux:   /proc/<pid>/stat field 22 (starttime in clock ticks since boot).
    macOS:   `ps -o lstart= -p <pid>` (an absolute timestamp string).
    Windows: GetProcessTimes via ctypes (FILETIME creation time, 100-ns since 1601).
    Anywhere else: returns None; restart_daemon falls back to its strict
    identify-only check, which is safer than no check at all.
    """
    if type(pid) is not int or pid <= 0:
        return None
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", "rb") as f:
                raw = f.read().decode("ascii", errors="replace")
        except (FileNotFoundError, PermissionError, OSError):
            return None
        # Field 2 is `(comm)`; comm can contain spaces and parens, so split off
        # everything after the LAST `)` and index from there.
        try:
            tail = raw[raw.rindex(")") + 2:].split()
            return tail[19]  # starttime is field 22 (0-indexed: 21 - skipped 2 = 19)
        except (ValueError, IndexError):
            return None
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                stderr=subprocess.DEVNULL, timeout=2,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        s = out.decode("ascii", errors="replace").strip()
        return s or None
    if sys.platform == "win32":
        # Windows users running a remote daemon hit the same slow-shutdown
        # window as POSIX (stop_remote() PATCHes api.browser-use.com after
        # the IPC socket has been torn down). Without a fingerprint here the
        # SIGTERM gate can never pass during that window, leaving an orphan
        # daemon that may continue to hold a billed cloud browser. Use
        # GetProcessTimes via ctypes to read the kernel-reported creation
        # time as a 64-bit FILETIME (100-ns intervals since 1601-01-01).
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return None
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
            ]
            kernel32.GetProcessTimes.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
        except (OSError, AttributeError):
            return None
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return None
        try:
            creation = wintypes.FILETIME()
            exit_ft = wintypes.FILETIME()
            kernel_ft = wintypes.FILETIME()
            user_ft = wintypes.FILETIME()
            ok = kernel32.GetProcessTimes(
                h, ctypes.byref(creation), ctypes.byref(exit_ft),
                ctypes.byref(kernel_ft), ctypes.byref(user_ft),
            )
            if not ok:
                return None
            return (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        finally:
            kernel32.CloseHandle(h)
    return None


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
BU_API = "https://api.browser-use.com/api/v3"
PYPI_JSON = "https://pypi.org/pypi/browser-harness/json"
VERSION_CACHE = paths.config_dir() / "version-cache.json"
VERSION_CACHE_TTL = 24 * 3600
DOCTOR_TEXT_LIMIT = 140


def _log_tail(name):
    try:
        return ipc.log_path(name or NAME).read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1]
    except (FileNotFoundError, IndexError, OSError):
        return None


def _is_daemon_process(pid):
    """Best effort: does `pid` look like one of our daemons?

    Guards against pid reuse — a dead daemon's number can be handed to an
    unrelated process, and treating that as parked would make every caller wait
    instead of spawning. Where the check cannot run (Windows, no ps) we fall
    back to the log-freshness guard rather than blocking startup.
    """
    command = (
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"]
        if sys.platform == "win32"
        else ["ps", "-o", "command=", "-p", str(pid)]
    )
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=2)
    except Exception:
        return False
    if result.returncode != 0:
        return False
    out = result.stdout
    if not out.strip():
        return False
    return "browser_harness" in out


def _pending_pid_record(path):
    """Read a parent-published PID plus process-start fingerprint."""
    try:
        raw = path.read_text()
        try:
            record = json.loads(raw)
            pid = int(record["pid"])
            fingerprint = record.get("started")
        except (json.JSONDecodeError, TypeError, KeyError):
            fields = raw.split()
            pid = int(fields[0])
            fingerprint = None
    except (FileNotFoundError, OSError, ValueError, IndexError):
        return None
    if pid <= 0:
        return None
    if fingerprint is not None:
        current = _process_start_time(pid)
        return pid if current is not None and current == fingerprint else None
    return pid if _is_daemon_process(pid) else None


def _fingerprinted_pending_generation(path):
    """Return (PID, start fingerprint) only while that generation is alive."""
    try:
        record = json.loads(path.read_text())
        pid = record["pid"]
        fingerprint = record.get("started")
    except (FileNotFoundError, OSError, TypeError, KeyError, json.JSONDecodeError):
        return None
    if type(pid) is not int or not 0 < pid < (1 << 31) or fingerprint is None:
        return None
    current = _process_start_time(pid)
    return (pid, fingerprint) if current is not None and current == fingerprint else None


def _fingerprinted_pending_pid(path):
    generation = _fingerprinted_pending_generation(path)
    return generation[0] if generation is not None else None


def _pid_number(path):
    """Read only the PID field, without treating it as a trusted identity."""
    try:
        raw = path.read_text()
        try:
            return int(json.loads(raw)["pid"])
        except (json.JSONDecodeError, TypeError, KeyError):
            return int(raw.split()[0])
    except (FileNotFoundError, OSError, ValueError, IndexError):
        return None


def _publish_pid(path, pid):
    fingerprint = _process_start_time(pid)
    value = json.dumps({"pid": pid, "started": fingerprint}, sort_keys=True, separators=(",", ":"))
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    tmp.write_text(value)
    os.replace(tmp, path)


def _parked_daemon_pid(name=None):
    """PID of a daemon whose handshake is still parked on Chrome's Allow popup.

    A parked daemon has no IPC socket yet, so daemon_alive() and identify() both
    say "nothing there" and every caller used to spawn a sibling, raising a
    second popup and truncating the first daemon's log. The pid file plus a
    fresh `handshake-wait` breadcrumb identify it without needing IPC.
    """
    if not (_log_tail(name) or "").startswith("handshake-wait"):
        return None
    pid = _pending_pid_record(ipc.pid_path(name or NAME))
    if pid is None:
        return None
    return pid


def _starting_daemon_pid(name=None):
    """PID of a daemon child in the short gap before it writes handshake-wait."""
    path = ipc.pid_path(name or NAME)
    try:
        pid = _pending_pid_record(path)
    except OSError:
        return None
    return pid


class _spawn_lock:
    """Only one process spawns a daemon at a time.

    Two cold invocations that both miss the parked check would otherwise open
    two connections and raise two popups, which is the bug this file is fixing.
    Best effort: if the lock cannot be taken we still proceed, because failing
    to start is worse than an extra popup.
    """

    def __init__(self, name=None, timeout=30.0):
        self.path = ipc.pid_path(name or NAME).with_suffix(".spawnlock")
        self.timeout = timeout
        self.fd = None

    def _try_lock(self):
        if sys.platform == "win32":
            import msvcrt
            os.lseek(self.fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                return False
        import fcntl
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def __enter__(self):
        deadline = time.time() + self.timeout
        self.fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR, 0o600)
        if os.fstat(self.fd).st_size == 0:
            os.write(self.fd, b"1")
        while True:
            if self._try_lock():
                return self
            if time.time() >= deadline:
                os.close(self.fd)
                self.fd = None
                return self
            time.sleep(0.1)

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self.fd)
            except OSError:
                pass
        return False


def _needs_chrome_remote_debugging_prompt(msg):
    """True when Chrome needs the inspect-page permission flow."""
    lower = (msg or "").lower()
    return (
        "devtoolsactiveport not found" in lower
        or "enable chrome://inspect" in lower
        or "not live yet" in lower
        or (
            "ws handshake failed" in lower
            and (
                "403" in lower
                or "opening handshake" in lower
                or "timed out" in lower
                or "timeout" in lower
            )
        )
    )


def _needs_chrome_permission_popup(msg):
    """True when Chrome is reachable but waiting on the per-session Allow popup."""
    lower = (msg or "").lower()
    return "permission-blocked" in lower


def _chrome_not_running(msg):
    """True when the daemon found no running supported browser"""
    return "chrome-not-running" in (msg or "").lower()


def _is_local_chrome_mode(env=None):
    """True when the daemon discovers a local Chrome instead of a remote CDP WS."""
    env = env or {}
    return not (
        env.get("BU_CDP_WS")
        or env.get("BU_CDP_URL")
        or os.environ.get("BU_CDP_WS")
        or os.environ.get("BU_CDP_URL")
    )


def _daemon_wait_windows(wait, local):
    """Return normal startup and Chrome-approval wait windows in seconds."""
    explicit_wait = wait is not None
    startup_wait = float(wait) if explicit_wait else 60.0
    approval_wait = None if local and not explicit_wait else startup_wait
    return startup_wait, approval_wait


def daemon_alive(name=None):
    # Ping handshake (not a bare connect) so a stale .port file + port reuse
    # after a daemon crash doesn't make us mistake an unrelated listener for ours.
    return ipc.ping(name or NAME, timeout=1.0)


def daemon_browser_kind(name=None):
    """'cloud' | 'cdp' | 'local' as self-reported by a live daemon, else None.

    None covers unreachable daemons and pre-browser_kind daemons still running
    from an older version."""
    c = None
    try:
        c, token = ipc.connect(name or NAME, timeout=1.0)
        response = ipc.request(c, token, {"meta": "ping"})
        kind = response.get("browser_kind") if isinstance(response, dict) else None
        return kind if kind in {"cloud", "cdp", "local"} else None
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError, ValueError):
        return None
    finally:
        if c:
            c.close()


def _daemon_endpoint_names():
    # BH_RUNTIME_DIR isolates one daemon per dir → no filename-prefix discovery,
    # just check whether our local endpoint exists. Without BH_RUNTIME_DIR, or
    # with BH_RUNTIME_DIR_SHARED=1, _RUNTIME is shared and we glob `bu-*.<suffix>`
    # to find every daemon in that runtime dir.
    suffix = ".port" if ipc.IS_WINDOWS else ".sock"
    if ipc.BH_RUNTIME_DIR and not ipc.BH_RUNTIME_DIR_SHARED:
        return [NAME] if (ipc._RUNTIME / f"bu{suffix}").exists() else []
    names = []
    for p in sorted(ipc._RUNTIME.glob(f"bu-*{suffix}")):
        raw = p.name[3:-len(suffix)]
        try:
            ipc._check(raw)
        except ValueError:
            continue
        names.append(raw)
    return names


def _daemon_browser_connection(name):
    c = None
    try:
        c, token = ipc.connect(name, timeout=1.0)
        response = ipc.request(c, token, {"meta": "connection_status"})
        if "error" in response:
            return None
        page = response.get("page")
        if page:
            page = {"title": page.get("title") or "(untitled)", "url": page.get("url") or ""}
        return {"name": name, "page": page}
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError, KeyError, ValueError, json.JSONDecodeError):
        return None
    finally:
        if c:
            c.close()


def daemon_browser_ready(name=None):
    """Whether the selected daemon has a healthy attached browser connection."""
    return _daemon_browser_connection(name or NAME) is not None


def browser_connections():
    """Live browser-harness daemons with healthy CDP browser connections and their attached page."""
    out = []
    for name in _daemon_endpoint_names():
        conn = _daemon_browser_connection(name)
        if conn:
            out.append(conn)
    return out


def active_browser_connections():
    """Count live browser-harness daemons with a healthy CDP browser connection."""
    return len(browser_connections())


def _doctor_short_text(value, limit=None):
    limit = limit or DOCTOR_TEXT_LIMIT
    value = str(value)
    return value if len(value) <= limit else value[:limit - 3] + "..."


def _is_snap_browser(path: str) -> bool:
    """True when a Chrome binary path lives under /snap/ (Snap confinement on Linux)."""
    return bool(path) and "/snap/" in path.lower()


def _doctor_snap_probe_path(path: str) -> str:
    raw = str(path)
    try:
        resolved = os.path.realpath(raw)
    except OSError:
        resolved = raw
    return raw if _is_snap_browser(raw) else resolved


def _doctor_probe_chrome_binary_for_snap():
    """Return (label, probe_path) for the first Chrome/Chromium binary found, else (None, None).

    Honors BH_CHROME_PATH and CHROME_PATH before searching PATH for common names.
    """
    import shutil

    for key in ("BH_CHROME_PATH", "CHROME_PATH"):
        raw = (os.environ.get(key) or "").strip()
        if not raw:
            continue
        p = Path(raw).expanduser()
        try:
            if p.is_file():
                return (p.name, _doctor_snap_probe_path(str(p)))
        except OSError:
            continue
    for cmd in ("google-chrome-stable", "google-chrome", "chromium-browser", "chromium"):
        w = shutil.which(cmd)
        if not w:
            continue
        try:
            return (cmd, _doctor_snap_probe_path(w))
        except OSError:
            continue
    return (None, None)


def _snap_linux_headless_doc_url():
    return "https://github.com/browser-use/browser-harness/blob/main/docs/snap-linux-headless.md"


def run_doctor_fix_snap():
    """Print steps to replace Snap Chromium with a native Chrome for CDP. Always exit 0."""
    doc = _snap_linux_headless_doc_url()
    print("browser-harness doctor --fix-snap")
    print()
    print("Snap-packaged Chromium cannot expose DevTools the way browser-harness needs.")
    print(f"Full background: {doc}")
    print()
    print("1. Install Google Chrome from Google's .deb (not the Snap store):")
    print("   wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
    print("   sudo apt install ./google-chrome-stable_current_amd64.deb")
    print()
    print("2. Point the harness (and your shell) at the native binary so PATH does not")
    print("   pick the Snap wrapper first. Example for bash (~/.bashrc or session env):")
    print("   export BH_CHROME_PATH=/usr/bin/google-chrome-stable")
    print("   # CHROME_PATH is also honored by doctor's snap probe if you prefer that name.")
    print()
    print("3. Launch Chrome from that path (Way 2) or open Chrome normally (Way 1),")
    print("   enable remote debugging per install.md, then verify:")
    print("   browser-harness --doctor")
    print()
    return 0


def ensure_daemon(wait=None, name=None, env=None):
    """Idempotent. Self-heals stale daemon, closed Chrome (launches it), cold
    Chrome, and missing Allow on chrome://inspect."""
    if daemon_alive(name):
        # Stale daemons accept connects AND reply to meta:* (pure Python) even when the
        # CDP WS to Chrome is dead — probe with a real CDP call and require "result".
        # Must go through ipc.connect so this works on Windows (TCP loopback) too;
        # raw AF_UNIX here would fail on every warm call and churn the daemon.
        try:
            s, token = ipc.connect(name or NAME, timeout=3.0)
            try:
                resp = ipc.request(s, token, {"method": "Target.getTargets", "params": {}})
                if "result" in resp: return
            finally:
                s.close()
        except TimeoutError as e:
            # A busy browser is not evidence its transport is dead. Restarting
            # here would interrupt every agent and raise another Allow prompt.
            raise RuntimeError("browser health check timed out; the shared daemon was left running") from e
        except OSError:
            # A closed IPC transport can be recovered through the normal path.
            pass
        browser_kind = daemon_browser_kind(name)
        if browser_kind in {"cloud", None}:
            # A stale Cloud daemon still owns a billable browser. Its shutdown
            # handler stops that browser before acknowledging, and stays alive
            # when the Cloud stop fails so a later call can retry cleanup. Treat
            # an unknown kind the same way: the health failure that made the
            # daemon stale may also prevent classification, and replacing an
            # unclassified daemon best-effort could orphan a Cloud browser.
            stop_remote_daemon(name or NAME)
        else:
            restart_daemon(name)

    import subprocess, sys
    local = _is_local_chrome_mode(env)
    startup_wait, approval_wait = _daemon_wait_windows(wait, local)
    # Remote/CDP daemons retain the normal 60s startup bound. Only a local
    # Chrome handshake displaying the per-connection approval sheet removes a
    # default caller's deadline, so Browser Use cloud startup is unaffected.
    launched_browser = None
    opened_inspect = False
    for _ in range(3):
        e = {**os.environ, **({"BU_NAME": name} if name else {}), **(env or {})}
        try:
            stderr_sink = open(ipc.log_path(name or NAME), "ab")
        except OSError:
            stderr_sink = subprocess.DEVNULL
        try:
            # One connection per name, including when agents share a remote
            # endpoint. Publish the child before releasing the spawn lock.
            with _spawn_lock(name, timeout=startup_wait) as lock:
                if lock.fd is None:
                    raise RuntimeError("daemon-starting: another browser-harness daemon is still starting; retry later")
                if daemon_alive(name):
                    return
                pending_pid = _parked_daemon_pid(name) or _starting_daemon_pid(name)
                if pending_pid:
                    p = None
                else:
                    p = subprocess.Popen(
                        [sys.executable, "-m", "browser_harness.daemon"],
                        env=e, stdout=subprocess.DEVNULL, stderr=stderr_sink, **ipc.spawn_kwargs(),
                    )
                    _publish_pid(ipc.pid_path(name or NAME), p.pid)
                    pending_pid = p.pid
        finally:
            if stderr_sink is not subprocess.DEVNULL:
                stderr_sink.close()
        spawned = time.monotonic()
        deadline = spawned + startup_wait
        hinted = not local
        approval_waiting = False
        pending_died = False
        while deadline is None or time.monotonic() < deadline:
            if daemon_alive(name):
                _cleanup_unattached_browser_launch(launched_browser)
                return
            if p is not None and p.poll() is not None:
                pending_died = True
                break
            if p is None and pending_pid and _pending_pid_record(ipc.pid_path(name or NAME)) != pending_pid:
                pending_died = True
                break
            log_tail = _log_tail(name) or ""
            if local and not approval_waiting and log_tail.startswith("handshake-wait"):
                approval_waiting = True
                deadline = None if approval_wait is None else max(deadline, spawned + approval_wait)
            if not hinted and time.monotonic() - spawned > 2 and log_tail.startswith("handshake-wait"):
                daemon_name = name or NAME
                approve_command = (
                    "browser-harness mac-approve"
                    if daemon_name == "default"
                    else f"BU_NAME={daemon_name} browser-harness mac-approve"
                )
                action = (
                    f"run `{approve_command}` in another shell or click Allow"
                    if sys.platform == "darwin"
                    else "click Allow"
                )
                print(
                    f'browser-harness: Chrome is asking "Allow remote debugging?" — {action} to continue.',
                    file=sys.stderr,
                )
                hinted = True
            time.sleep(0.2)
        msg = _log_tail(name) or ""
        permission_wait = local and (msg.startswith("handshake-wait") or _needs_chrome_permission_popup(msg))
        if local and pending_died:
            # Serialize cleanup with publishers and remove only the generation
            # we observed. Another waiter may already have published a healthy
            # successor while this caller was leaving its wait loop.
            with _spawn_lock(name, timeout=1.0) as cleanup_lock:
                if cleanup_lock.fd is not None and _pid_number(ipc.pid_path(name or NAME)) == pending_pid:
                    try:
                        ipc.pid_path(name or NAME).unlink()
                    except FileNotFoundError:
                        pass
            if permission_wait:
                # A denied/expired approval may already have dropped its sheet.
                # Never auto-spawn a replacement here: that would immediately
                # create another Chrome prompt and recreate the retry loop.
                raise RuntimeError(
                    "permission-blocked: the pending Chrome connection ended before approval; "
                    "browser-harness did not retry or create another connection."
                )
            continue
        if local and msg.startswith("handshake-wait"):
            # Leave it running: this daemon's connection is what holds the popup
            # on screen. Killing it dropped the popup and the retry raised a new
            # one, which is how a single approval turned into an endless prompt.
            raise RuntimeError(
                "permission-blocked: Chrome's Allow popup is still open and the pending daemon was left running. "
                "Approve that exact popup; browser-harness did not retry or create another connection."
            )
        if local and _needs_chrome_permission_popup(msg):
            print(
                'browser-harness: Chrome is asking "Allow remote debugging?". '
                "Approve that exact popup; no replacement connection was started.",
                file=sys.stderr,
            )
            raise RuntimeError(
                "permission-blocked: Chrome did not approve the connection; browser-harness did not retry or create another connection."
            )
        if local and launched_browser is None and _chrome_not_running(msg):
            # Chrome is closed — launch the browser and retry
            restart_daemon(name)
            launched_browser = _launch_browser()
            if launched_browser is None:
                raise RuntimeError(
                    "chrome-not-running: no supported browser is running and none could be launched -- ask the user to open Chrome, then retry."
                )
            print("browser-harness: Chrome isn't running — launching it. If Chrome shows an \"Allow remote debugging?\" popup, click Allow.", file=sys.stderr)
            from .daemon import supported_browser_running
            boot_deadline = time.time() + 15
            while time.time() < boot_deadline and not supported_browser_running():
                time.sleep(0.3)
            continue
        if local and not opened_inspect and _needs_chrome_remote_debugging_prompt(msg):
            opened_inspect = True
            from .daemon import remote_debugging_toggle_profiles, remote_debugging_user_enabled
            if remote_debugging_user_enabled():
                # chrome://inspect toggle is already on — connection died
                print(
                    'browser-harness: Chrome is asking "Allow remote debugging?". '
                    "Approve that exact popup; no replacement connection was started.",
                    file=sys.stderr,
                )
                raise RuntimeError(
                    "permission-blocked: Chrome did not approve the connection; browser-harness did not retry or create another connection."
                )
            restart_daemon(name)
            _open_chrome_inspect_once()
            if remote_debugging_toggle_profiles():
                # Toggle already ticked from a previous run, but Chrome 144+
                # wants new Allow for this browser run.
                todo = 'click Allow on Chrome\'s "Allow remote debugging?" popup (the checkbox is already ticked; if no popup appears, untick and re-tick it)'
            else:
                todo = 'tick "Allow remote debugging for this browser instance" and click Allow on the popup'
            raise RuntimeError(
                f"remote-debugging-setup: opened chrome://inspect/#remote-debugging in Chrome -- ask the user to {todo}. "
                "Warn them Chrome shows ONE more Allow popup when the harness connects on the next attempt (per-connection approval; it is expected, not a re-ask). "
                "Retry after the user confirms; do not retry before."
            )
        raise RuntimeError(msg or f"daemon {name or NAME} didn't come up -- check {ipc.log_path(name or NAME)}")
    raise RuntimeError(f"daemon {name or NAME} didn't come up -- check {ipc.log_path(name or NAME)}")


def require_existing_daemon(name=None):
    """Require a healthy existing daemon without spawning or reconnecting.

    Trusted orchestrators use this after they provision a scoped CDP transport.
    Failing closed prevents a later CLI call from silently discovering a
    different local Chrome when that orchestrator-owned daemon dies.
    """
    daemon_name = name or NAME
    if not daemon_alive(daemon_name):
        raise RuntimeError(f"required daemon {daemon_name!r} is not running")
    try:
        s, token = ipc.connect(daemon_name, timeout=3.0)
        try:
            resp = ipc.request(s, token, {"method": "Target.getTargets", "params": {}})
        finally:
            s.close()
    except Exception as exc:
        raise RuntimeError(f"required daemon {daemon_name!r} is unhealthy: {exc}") from exc
    if not isinstance(resp, dict) or "result" not in resp:
        raise RuntimeError(f"required daemon {daemon_name!r} failed its CDP health check")


def stop_remote_daemon(name="remote"):
    """Stop a remote daemon and its backing Browser Use cloud browser.

    Triggers the daemon's clean shutdown, which PATCHes
    /browsers/{id} {"action":"stop"} so billing ends and any profile
    state in the session is persisted."""
    # restart_daemon is misnamed — it only stops the daemon (sends
    # shutdown, SIGTERMs if needed, unlinks socket+pid). It never
    # restarts anything on its own; a follow-up `browser-harness`
    # call would auto-spawn a fresh one via ensure_daemon(). That
    # "run-it-again-to-restart" workflow is why it was named that way.
    restart_daemon(name, require_clean=True)


def restart_daemon(name=None, require_clean=False):
    """Best-effort daemon shutdown + socket/pid cleanup.

    Name is historical: callers typically follow this with another
    `browser-harness` invocation, which auto-spawns a fresh daemon via
    ensure_daemon(). The function itself only stops.

    With require_clean=True, an unavailable daemon or any response other than
    {"ok": true} raises before endpoint cleanup or process termination.

    Ready-daemon identity is verified via ipc.identify() before any process
    signal. A local daemon waiting on Chrome approval has no IPC socket yet;
    `--reload` may stop that exact pending generation only when its atomically
    published process-start fingerprint still matches. A stale or legacy PID
    file is never trusted for signaling.
    """
    import signal

    name = name or NAME
    pending_path = ipc.pid_path(name)
    pid_path = str(pending_path)
    pending_generation = None
    pending_unverified = False
    if (_log_tail(name) or "").startswith("handshake-wait"):
        parked_pid = _parked_daemon_pid(name)
        pending_generation = _fingerprinted_pending_generation(pending_path)
        pending_unverified = parked_pid is not None and pending_generation is None

    # Two pieces of information are tracked separately:
    #   - daemon_pid: the daemon's self-reported PID, or None. Only daemons
    #     running this version (or newer) include `pid` in the ping response;
    #     pre-upgrade daemons return {pong: True} only and yield None here.
    #   - daemon_alive: whether ANY daemon answers ping. Keeps the shutdown
    #     IPC path working across upgrades — without it, a still-running
    #     pre-upgrade daemon would have its socket deleted out from under it
    #     while the process stayed alive.
    daemon_pid = ipc.identify(name, timeout=5.0)
    daemon_alive = daemon_pid is not None or ipc.ping(name, timeout=1.0)
    if require_clean and not daemon_alive:
        raise RuntimeError(f"daemon {name!r} is unavailable for required clean shutdown")
    if not daemon_alive and pending_unverified:
        raise RuntimeError(
            f"pending daemon {name!r} is live but has no verifiable process fingerprint; "
            "it was not signaled and its ownership records were preserved"
        )
    if not daemon_alive and pending_generation is not None:
        with _spawn_lock(name, timeout=5.0) as owner_lock:
            if owner_lock.fd is None:
                raise RuntimeError(
                    f"pending daemon {name!r} is changing ownership; it was not signaled"
                )
            current_generation = _fingerprinted_pending_generation(pending_path)
            if current_generation != pending_generation:
                raise RuntimeError(
                    f"pending daemon {name!r} changed ownership; the successor was not signaled "
                    "and its records were preserved"
                )
            if ipc.ping(name, timeout=0.2):
                raise RuntimeError(
                    f"pending daemon {name!r} became ready during cancellation; run --reload again"
                )
            try:
                os.kill(pending_generation[0], signal.SIGTERM)
            except (ProcessLookupError, OSError, SystemError, OverflowError):
                pass
            ipc.cleanup_endpoint(name)
            try:
                os.unlink(pid_path)
            except FileNotFoundError:
                pass
        return
    # Snapshot the daemon's process start-time as a secondary identity check.
    # The IPC socket can disappear before the process exits (e.g. the shutdown
    # path tears down the socket and then waits on a slow remote `stop` PATCH),
    # so identify() going None partway through is not proof of process death.
    # Comparing start-time before SIGTERM lets us recover the original
    # force-kill behavior for slow shutdowns without re-opening the
    # PID-reuse hole — a reused PID would have a different start-time.
    daemon_start = _process_start_time(daemon_pid)

    if daemon_alive:
        c = None
        try:
            c, token = ipc.connect(name, timeout=50.0 if require_clean else 5.0)
            response = ipc.request(c, token, {"meta": "shutdown"})
            if require_clean and (
                not isinstance(response, dict)
                or response.get("ok") is not True
                or bool(response.get("error"))
            ):
                error = response.get("error") if isinstance(response, dict) else None
                raise RuntimeError(error or f"daemon {name!r} did not confirm clean shutdown")
        except Exception as exc:
            if require_clean:
                if isinstance(exc, RuntimeError):
                    raise
                raise RuntimeError(
                    f"daemon {name!r} did not confirm clean shutdown: {exc}"
                ) from exc
        finally:
            if c is not None:
                close = getattr(c, "close", None)
                if close:
                    close()

    if daemon_pid is not None:
        for _ in range(75):
            try:
                os.kill(daemon_pid, 0)
                time.sleep(0.2)
            except (ProcessLookupError, OSError, SystemError, OverflowError):
                break
        else:
            # Re-verify identity before escalating to SIGTERM. Two acceptable
            # signals, in priority order:
            #   1. ipc.identify() still returns the same PID — daemon's IPC is
            #      live, daemon is wedged. Safe to kill.
            #   2. start-time fingerprint of the original PID is unchanged —
            #      same process, just slow to exit (e.g. stuck in remote stop).
            #      The IPC may already be gone; that's expected.
            # If neither holds, the PID may have been reused; skip SIGTERM.
            verified_pid = ipc.identify(name, timeout=1.0)
            same_process = verified_pid == daemon_pid or (
                daemon_start is not None
                and _process_start_time(daemon_pid) == daemon_start
            )
            if same_process:
                try:
                    os.kill(daemon_pid, signal.SIGTERM)
                except (ProcessLookupError, OSError, SystemError, OverflowError):
                    pass

    ipc.cleanup_endpoint(name)
    try:
        os.unlink(pid_path)
    except FileNotFoundError:
        pass


def _browser_use(path, method, body=None):
    key = auth.get_browser_use_api_key()
    req = urllib.request.Request(
        f"{BU_API}{path}",
        method=method,
        data=(json.dumps(body).encode() if body is not None else None),
        headers={"X-Browser-Use-API-Key": key, "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")


def _stop_cloud_browser(browser_id, strict=False):
    if not browser_id:
        return True
    last_error = None
    for attempt in range(3):
        try:
            _browser_use(f"/browsers/{browser_id}", "PATCH", {"action": "stop"})
            return True
        except BaseException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    if strict:
        raise RuntimeError(f"failed to stop remote browser {browser_id}: {last_error}")
    return False


def _cdp_ws_from_url(cdp_url):
    return json.loads(urllib.request.urlopen(f"{cdp_url}/json/version", timeout=15).read())["webSocketDebuggerUrl"]


def _has_local_gui():
    """True when this machine plausibly has a browser we can open. False on headless servers."""
    import platform
    system = platform.system()
    if system in ("Darwin", "Windows"):
        return True
    if system == "Linux":
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return False


def _show_live_url(url):
    """Print liveUrl and auto-open it locally if there's a GUI."""
    import sys, webbrowser
    if not url: return
    print(url)
    if not _has_local_gui():
        print("(no local GUI — share the liveUrl with the user)", file=sys.stderr)
        return
    try:
        webbrowser.open(url, new=2)
        print("(opened liveUrl in your default browser)", file=sys.stderr)
    except Exception as e:
        print(f"(couldn't auto-open: {e} — share the liveUrl with the user)", file=sys.stderr)


def _should_show_remote_live_view():
    """Whether Cloud provisioning should print and open its interactive live view."""
    raw = os.environ.get("BH_OPEN_LIVE_URL")
    if raw is None:
        return True
    value = raw.strip().lower()
    if value in {"0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    raise ValueError("BH_OPEN_LIVE_URL must be one of: 1, true, yes, on, 0, false, no, off")


def list_cloud_profiles():
    """List cloud profiles under the current API key.

    Returns [{id, name, userId, cookieDomains, lastUsedAt}, ...]. `cookieDomains`
    is the array of domain strings the cloud profile has cookies for — use
    `len(cookieDomains)` as a cheap 'how much is logged in' summary. Per-cookie
    detail on a *local* profile before sync: `profile-use inspect --profile <name>`.

    Paginates through all pages — the API caps `pageSize` at 100."""
    out, page = [], 1
    while True:
        listing = _browser_use(f"/profiles?pageSize=100&pageNumber={page}", "GET")
        items = listing.get("items") if isinstance(listing, dict) else listing
        if not items:
            break
        for p in items:
            detail = _browser_use(f"/profiles/{p['id']}", "GET")
            out.append({
                "id": detail["id"],
                "name": detail.get("name"),
                "userId": detail.get("userId"),
                "cookieDomains": detail.get("cookieDomains") or [],
                "lastUsedAt": detail.get("lastUsedAt"),
            })
        if isinstance(listing, dict) and len(out) >= listing.get("totalItems", len(out)):
            break
        page += 1
    return out


def _resolve_profile_name(profile_name):
    """Find a single cloud profile by exact name; raise if 0 or >1 match."""
    matches = [p for p in list_cloud_profiles() if p.get("name") == profile_name]
    if not matches:
        raise RuntimeError(f"no cloud profile named {profile_name!r} -- call list_cloud_profiles() or sync_local_profile() first")
    if len(matches) > 1:
        raise RuntimeError(f"{len(matches)} cloud profiles named {profile_name!r} -- pass profileId=<uuid> instead")
    return matches[0]["id"]


def start_remote_daemon(name="remote", profileName=None, **create_kwargs):
    """Provision a Browser Use cloud browser and start a daemon attached to it.

    kwargs forwarded to `POST /browsers` (camelCase):
      profileId        — cloud profile UUID; start already-logged-in. Default: none (clean browser).
      profileName      — cloud profile name; resolved client-side to profileId via list_cloud_profiles().
      proxyCountryCode — ISO2 country code (default "us"); pass None to disable the BU proxy.
      timeout          — minutes, 1..240.
      customProxy      — {host, port, username, password, ignoreCertErrors}.
      browserScreenWidth / browserScreenHeight, allowResizing, enableRecording.

    Returns the full browser dict including `liveUrl`. By default, prints that
    URL and opens it locally when a GUI is detected. Set BH_OPEN_LIVE_URL to
    0, false, no, or off (case-insensitive) to suppress only those display side
    effects; the returned URL remains present."""
    show_live_view = _should_show_remote_live_view()
    if daemon_alive(name):
        raise RuntimeError(f"daemon {name!r} already alive -- restart_daemon({name!r}) first")
    if profileName:
        if "profileId" in create_kwargs:
            raise RuntimeError("pass profileName OR profileId, not both")
        create_kwargs["profileId"] = _resolve_profile_name(profileName)
    browser = _browser_use("/browsers", "POST", create_kwargs)
    try:
        ensure_daemon(
            name=name,
            env={"BU_CDP_WS": _cdp_ws_from_url(browser["cdpUrl"]), "BU_BROWSER_ID": browser["id"]},
        )
    except BaseException as start_error:
        try:
            _stop_cloud_browser(browser.get("id"), strict=True)
        except BaseException as cleanup_error:
            raise BaseExceptionGroup(
                "remote daemon startup and cloud browser cleanup both failed",
                [start_error, cleanup_error],
            )
        raise
    if show_live_view:
        _show_live_url(browser.get("liveUrl"))
    return browser


def list_local_profiles():
    """Detected local browser profiles on this machine. Shells out to `profile-use list --json`."""
    import json, shutil, subprocess
    if not shutil.which("profile-use"):
        raise RuntimeError("profile-use not installed -- curl -fsSL https://browser-use.com/profile.sh | sh")
    return json.loads(subprocess.check_output(["profile-use", "list", "--json"], text=True, encoding="utf-8", errors="replace"))


def sync_local_profile(profile_name, browser=None, cloud_profile_id=None,
                        include_domains=None, exclude_domains=None):
    """Sync a local profile's cookies to a cloud profile. Returns the cloud UUID.

    Shells out to `profile-use sync` (v1.0.5+). Requires BROWSER_USE_API_KEY.
    profile-use copies the profile dir to a temp and syncs from the copy, so Chrome
    can stay open.

    Args:
      profile_name:       local Chrome profile name (as shown by `list_local_profiles`).
      browser:            disambiguate when multiple browsers have profiles of the
                          same name (e.g. "Google Chrome"). Default: any match.
      cloud_profile_id:   push cookies into this existing cloud profile instead of
                          creating a new one. Idempotent — call again to refresh
                          the same profile. Default: create new.
      include_domains:    only sync cookies for these domains (and subdomains).
                          Leading dot is optional. Example: ["google.com", "stripe.com"].
      exclude_domains:    drop cookies for these domains (and subdomains). Applied
                          before `include_domains` so exclude wins on overlap."""
    import shutil, subprocess, sys
    if not shutil.which("profile-use"):
        raise RuntimeError("profile-use not installed -- curl -fsSL https://browser-use.com/profile.sh | sh")
    key = auth.get_browser_use_api_key()
    cmd = ["profile-use", "sync", "--profile", profile_name]
    if browser:
        cmd += ["--browser", browser]
    if cloud_profile_id:
        cmd += ["--cloud-profile-id", cloud_profile_id]
    for d in include_domains or []:
        cmd += ["--domain", d]
    for d in exclude_domains or []:
        cmd += ["--exclude-domain", d]
    r = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, env={**os.environ, "BROWSER_USE_API_KEY": key})
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"profile-use sync failed (exit {r.returncode})")
    # With --cloud-profile-id the tool prints "♻️ Using existing cloud profile"
    # instead of "Profile created: <uuid>", so we already know the UUID.
    if cloud_profile_id:
        return cloud_profile_id
    m = re.search(r"Profile created:\s+([0-9a-f-]{36})", r.stdout)
    if not m:
        raise RuntimeError(f"profile-use did not report a profile UUID (exit {r.returncode})")
    return m.group(1)


def _version():
    """Installed version of the browser-harness package. Empty string if unknown."""
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version("browser-harness")
        except PackageNotFoundError:
            return ""
    except Exception:
        return ""


def _repo_dir():
    """Return the repo root if this install is an editable git clone, else None.

    Only the directories that could actually hold this package as source count:
    the package's own parent (flat layout) and its grandparent (src layout).
    Walking all the way up would claim any enclosing repository — a wheel
    installed into a venv inside the user's project, or a tool install under a
    dotfiles-managed $HOME — and run_update() would then `git pull` that repo
    instead of upgrading browser-harness.
    """
    package = Path(__file__).resolve().parent
    for candidate in (package.parent, package.parent.parent):
        if (candidate / ".git").is_dir():
            return candidate
    return None


def _install_mode():
    """"git" for editable clone, "pypi" for an installed wheel, "unknown" otherwise."""
    if _repo_dir():
        return "git"
    return "pypi" if _version() else "unknown"


def _cache_read():
    try:
        return json.loads(VERSION_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _cache_write(data):
    try:
        VERSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
        VERSION_CACHE.write_text(json.dumps(data))
        try:
            os.chmod(VERSION_CACHE, 0o600)
        except OSError:
            pass
    except OSError:
        pass


def _latest_release_tag(force=False):
    """Return latest PyPI version, or None. Cached for 24h to avoid hammering PyPI."""
    cache = _cache_read()
    now = time.time()
    if not force and cache.get("tag") and now - cache.get("fetched_at", 0) < VERSION_CACHE_TTL:
        return cache["tag"]
    try:
        tag = json.loads(urllib.request.urlopen(PYPI_JSON, timeout=5).read()).get("info", {}).get("version") or ""
    except Exception:
        return cache.get("tag")  # fall back to last known
    tag = tag.lstrip("v")
    _cache_write({**cache, "tag": tag, "fetched_at": now})
    return tag or None


def _version_tuple(v):
    """Best-effort PEP 440-ish parse: alpha < beta < rc < final."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)(?:(a|b|rc)(\d+))?", v or "", re.I)
    if not m:
        return (0, 0, 0, 3, 0)
    nums = [int(p) for p in m.group(1).split(".")[:3]]
    nums.extend([0] * (3 - len(nums)))
    pre = (m.group(2) or "").lower()
    pre_rank = {"a": 0, "b": 1, "rc": 2}.get(pre, 3)
    pre_num = int(m.group(3) or 0)
    return (*nums, pre_rank, pre_num)


def check_for_update():
    """(current, latest, newer_available). latest may be None if the API was unreachable and no cache exists."""
    cur = _version()
    latest = _latest_release_tag()
    newer = bool(cur and latest and _version_tuple(latest) > _version_tuple(cur))
    return cur, latest, newer


def print_update_banner(out=None):
    """Print the update banner to stderr once per day. Silent when up-to-date or offline."""
    import sys
    if os.environ.get("BH_UPDATE_CHECK", "").strip().lower() in {"0", "false", "no", "off"}:
        return
    out = out or sys.stderr
    cache = _cache_read()
    today = time.strftime("%Y-%m-%d")
    if cache.get("banner_shown_on") == today:
        return
    cur, latest, newer = check_for_update()
    if not newer:
        return
    print(f"[browser-harness] update available: {cur} -> {latest}", file=out)
    print(f"[browser-harness] agents: run `browser-harness --update -y` to upgrade and restart the daemon", file=out)
    _cache_write({**cache, "banner_shown_on": today})


def _chrome_running():
    """Cross-platform best-effort check for a running Chromium-based browser."""
    import platform, subprocess
    system = platform.system()
    try:
        if system == "Windows":
            out = subprocess.check_output(["tasklist"], text=True, errors="replace", timeout=5)
            names = ("chrome.exe", "msedge.exe", "helium.exe")
        else:
            out = subprocess.check_output(["ps", "-A", "-o", "comm="], text=True, errors="replace", timeout=5)
            names = ("Google Chrome", "chrome", "chromium", "Microsoft Edge", "msedge", "helium")
        return any(n.lower() in out.lower() for n in names)
    except Exception:
        return False


_BROWSER_LAUNCH = (
    # (profile-dir fragment, macOS app name, POSIX commands, Windows `start` target)
    ("chrome canary", "Google Chrome Canary", ("google-chrome-canary",), "chrome"),
    ("chromium", "Chromium", ("chromium", "chromium-browser"), "chromium"),
    ("chrome", "Google Chrome", ("google-chrome-stable", "google-chrome"), "chrome"),
    ("edge", "Microsoft Edge", ("microsoft-edge", "microsoft-edge-stable"), "msedge"),
    ("brave-origin", "Brave Origin", (), None),
    ("brave", "Brave Browser", ("brave-browser", "brave"), "brave"),
    ("arc", "Arc", (), None),
    ("dia", "Dia", (), None),
    ("comet", "Comet", (), None),
)
_DEFAULT_LAUNCH = (
    "Google Chrome",
    ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "microsoft-edge"),
    "chrome",
)


def _browser_launch_spec(base):
    """(mac app, posix commands, windows target) for the browser w profile dir"""
    tail = "/".join(p.lower() for p in Path(base).parts[-2:])
    for frag, mac_app, posix_cmds, win_target in _BROWSER_LAUNCH:
        if frag in tail:
            return (mac_app, posix_cmds, win_target)
    return _DEFAULT_LAUNCH


def _browser_binary_matches_profile(binary, base):
    """True when an explicit browser binary belongs to ``base``."""
    name = Path(binary).name.lower().removesuffix(".exe")
    mac_app, posix_cmds, win_target = _browser_launch_spec(base)
    candidates = (mac_app, *posix_cmds, win_target)

    def normalize(value):
        return "".join(char for char in (value or "").lower() if char.isalnum())

    normalized_name = normalize(name)
    return any(normalized_name == normalize(candidate) for candidate in candidates)


def _profile_directory_args(base):
    """Relaunch skips Chrome's profile picker"""
    if not base:
        return []
    try:
        state = json.loads((Path(base) / "Local State").read_text(encoding="utf-8", errors="replace"))
        last = ((state.get("profile") or {}).get("last_used")) or "Default"
    except (OSError, ValueError, AttributeError):
        last = "Default"
    if not isinstance(last, str) or not (Path(base) / last).is_dir():
        return []
    return [f"--profile-directory={last}"]


def _launch_browser():
    """Prefers the browser whose profile already has perm box checked.

    Returns ``(process, profile)`` on success. ``process`` is available only
    when we launched the browser directly; ``profile`` is the user-data dir we
    expect that browser to use. The caller uses both to clean up a direct
    launch that never becomes reachable over CDP.
    """
    import platform, shutil, subprocess
    from .daemon import PROFILES, remote_debugging_toggle_profiles

    enabled = remote_debugging_toggle_profiles()
    known_profiles = enabled + [
        base for base in PROFILES if base not in enabled and (base / "Local State").exists()
    ]
    system = platform.system()
    for key in ("BH_CHROME_PATH", "CHROME_PATH"):
        raw = (os.environ.get(key) or "").strip()
        if raw and Path(raw).expanduser().is_file():
            try:
                binary = Path(raw).expanduser()
                process = subprocess.Popen(
                    [str(binary)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **ipc.spawn_kwargs(),
                )
                profile = next(
                    (base for base in known_profiles if _browser_binary_matches_profile(binary, base)),
                    None,
                ) if system not in ("Darwin", "Windows") else None
                return process, profile
            except (OSError, subprocess.SubprocessError):
                # A path that exists but can't execute (permissions, wrong arch)
                # must fall through to normal discovery, not abort
                continue

    base = enabled[0] if enabled else next((b for b in PROFILES if (b / "Local State").exists()), None)
    mac_app, posix_cmds, win_target = _browser_launch_spec(base) if base else _DEFAULT_LAUNCH
    profile_args = _profile_directory_args(base)
    try:
        if system == "Darwin":
            cmd = ["open", "-a", mac_app] + (["--args"] + profile_args if profile_args else [])
            r = subprocess.run(cmd, timeout=10, check=False, capture_output=True)
            if r.returncode != 0 and mac_app != "Google Chrome":
                # Different app → its profile dir may not match; launch plain
                r = subprocess.run(["open", "-a", "Google Chrome"], timeout=10, check=False, capture_output=True)
            return (None, base) if r.returncode == 0 else None
        if system == "Windows":
            # `start <name>` resolves browsers via App Paths without knowing the install dir
            subprocess.Popen(["cmd", "/c", "start", "", win_target or "chrome"] + profile_args, **ipc.spawn_kwargs())
            return None, base
        for cmd in posix_cmds or _DEFAULT_LAUNCH[1]:
            w = shutil.which(cmd)
            if w:
                process = subprocess.Popen(
                    [w] + profile_args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **ipc.spawn_kwargs(),
                )
                return process, base
        return None
    except (OSError, subprocess.SubprocessError):
        return None


def _cleanup_unattached_browser_launch(launch):
    """Stop a browser we launched when the daemon attached somewhere else."""
    if not launch:
        return
    process, profile = launch
    if process is None or profile is None or process.poll() is not None:
        return

    from .daemon import _devtools_port_live

    if _devtools_port_live(profile):
        return

    import signal

    try:
        if ipc.IS_WINDOWS:
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (OSError, subprocess.SubprocessError):
        pass


def _open_chrome_inspect():
    """Open chrome://inspect/#remote-debugging so the user can tick the checkbox."""
    import platform, subprocess, webbrowser
    url = "chrome://inspect/#remote-debugging"
    if platform.system() == "Darwin":
        try:
            r = subprocess.run([
                "osascript",
                "-e", 'tell application "Google Chrome" to activate',
                "-e", f'tell application "Google Chrome" to open location "{url}"',
            ], timeout=5, check=False, capture_output=True)
            if r.returncode == 0:
                return True
        except Exception:
            pass
    try:
        return bool(webbrowser.open(url, new=2))
    except Exception:
        return False


INSPECT_REOPEN_TTL = 180.0  # seconds open new chrome://inspect tab


def _open_chrome_inspect_once():
    """Open chrome://inspect at most once per INSPECT_REOPEN_TTL across invocations"""
    marker = paths.inspect_marker()
    try:
        if time.time() - marker.stat().st_mtime < INSPECT_REOPEN_TTL:
            return
    except OSError:
        pass
    if not _open_chrome_inspect():
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        pass


def run_doctor():
    """Read-only diagnostics. Exit 0 iff everything looks healthy."""
    import platform, sys
    cur = _version()
    mode = _install_mode()
    chrome = _chrome_running()
    daemon = daemon_alive()
    connections = browser_connections()
    try:
        auth_state = auth.auth_status()
    except (auth.AuthError, OSError) as e:
        auth_state = {"status": "error", "source": None, "reason": str(e)}
    cloud_auth = auth_state.get("status") == "authenticated"
    latest = _latest_release_tag()
    # Only claim an update when we know the installed version — `cur or "(unknown)"`
    # for display would otherwise be parsed as (0,) and flag every latest as newer.
    newer = bool(cur and latest and _version_tuple(latest) > _version_tuple(cur))
    cur_display = cur or "(unknown)"
    doc_url = _snap_linux_headless_doc_url()

    def row(label, ok, detail=""):
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")

    print("browser-harness doctor")
    print(f"  platform          {platform.system()} {platform.release()}")
    print(f"  python            {sys.version.split()[0]}")
    print(f"  version           {cur_display} ({mode})")
    if latest:
        print(f"  latest release    {latest}" + (" (update available)" if newer else ""))
    else:
        print("  latest release    (could not reach PyPI)")
    if platform.system() == "Linux":
        bname, bpath = _doctor_probe_chrome_binary_for_snap()
        if bname and bpath and _is_snap_browser(bpath):
            print("[snap-detect]")
            print(f"Browser: {bname} (snap) — WARNING: Snap confinement prevents CDP binding.")
            print(f"  Fix: Install Chrome natively (see docs/snap-linux-headless.md)")
            print(f"  Docs: {doc_url}")
    row("chrome running", chrome, "" if chrome else "start chrome/edge")
    row("daemon alive", daemon, "" if daemon else "see install.md")
    row("active browser connections", bool(connections), str(len(connections)))
    for conn in connections:
        page = conn.get("page")
        if page:
            title = _doctor_short_text(page["title"])
            url = _doctor_short_text(page["url"])
            print(f"        {conn['name']} — active page: {title} — {url}")
        else:
            print(f"        {conn['name']} — active page: (no real page)")
    row("Browser Use cloud auth", cloud_auth, auth_state.get("source") or auth_state.get("reason") or "optional: browser-harness auth login")
    # Core health = chrome + daemon. Cloud auth is optional.
    return 0 if (chrome and daemon) else 1


def run_doctor_json(require_existing_daemon=False):
    """Print a stable, non-networked runtime health report as JSON.

    The strict mode is intended for trusted orchestrators that provision an
    exact named daemon. It checks only that selected daemon and its live CDP
    connection; it never starts, repairs, or discovers another daemon.
    """
    strict = bool(require_existing_daemon)
    chrome = None if strict else _chrome_running()
    browser_ready = daemon_browser_ready(NAME)
    daemon = browser_ready or daemon_alive(NAME)
    healthy = (daemon and browser_ready) if strict else (browser_ready or (chrome and daemon))
    report = {
        "schema_version": 1,
        "healthy": healthy,
        "require_existing_daemon": strict,
        "version": _version() or None,
        "install_mode": _install_mode(),
        "chrome_running": chrome,
        "daemon": {
            "name": NAME,
            "alive": daemon,
            "browser_ready": browser_ready,
        },
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if healthy else 1


def _prompt_yes(question, default_yes=True, yes=False):
    if yes:
        return True
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        ans = input(f"{question} {suffix} ").strip().lower()
    except EOFError:
        return default_yes
    if not ans:
        return default_yes
    return ans.startswith("y")


def _uv_manages_browser_harness():
    """True when `uv tool list` shows browser-harness, i.e. `uv tool upgrade` owns it.

    Unknown counts as managed: if uv cannot be run or its output is unreadable we
    stay quiet rather than tell a uv user to reinstall with pip.
    """
    try:
        listed = subprocess.run(["uv", "tool", "list"], capture_output=True, text=True)
    except OSError:
        return True
    if listed.returncode != 0:
        return True
    # `uv tool list` prints one "name vX.Y.Z" line per tool, then its executables as
    # "- exe" lines. Match the entry name, so a tool merely containing our name (say
    # my-browser-harness-wrapper) cannot silence the hint for a real pip install.
    for line in (listed.stdout or "").splitlines():
        entry = line.strip()
        if entry.startswith("-"):
            continue
        if entry.split(" ", 1)[0] == "browser-harness":
            return True
    return False


def run_update(yes=False):
    """Pull the latest version and (after prompt) restart the daemon so it picks up changed code.

    Exit 0 on success, non-zero on failure."""
    import subprocess, sys
    cur, latest, newer = check_for_update()
    # Only short-circuit as "up to date" when we actually know the installed
    # version. Otherwise `newer=False` just means "couldn't compare" — proceed.
    if cur and latest and not newer:
        print(f"browser-harness is up to date ({cur}).")
        return 0
    if cur and latest:
        print(f"updating browser-harness: {cur} -> {latest}")
    elif latest:
        print(f"installed version unknown; will try to update to {latest}.")
    else:
        print("could not reach PyPI; will try to update anyway.")

    mode = _install_mode()
    if mode == "git":
        repo = _repo_dir()
        status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True)
        if status.returncode != 0:
            print(f"git status failed: {status.stderr.strip()}", file=sys.stderr)
            return 1
        if status.stdout.strip():
            print(f"refusing to update: uncommitted changes in {repo}", file=sys.stderr)
            print("commit or stash them first, or run `git -C %s pull` yourself." % repo, file=sys.stderr)
            return 1
        r = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"])
        if r.returncode != 0:
            return r.returncode
    elif mode == "pypi":
        tool_upgrade = subprocess.run(["uv", "tool", "upgrade", "browser-harness"])
        if tool_upgrade.returncode != 0:
            # `uv tool upgrade` only manages what `uv tool install` put there, so a pip
            # or pipx install fails here with "`browser-harness` is not installed" and
            # no way forward. Point only those users at the documented install: when the
            # tool IS uv-managed the failure is uv's own (offline, auth) and its message
            # already stands, so adding a pip hint there would just mislead.
            if not _uv_manages_browser_harness():
                print(
                    "if you installed with pip or pipx, upgrade with: "
                    "uv tool install --python 3.12 --upgrade --force browser-harness",
                    file=sys.stderr,
                )
            return tool_upgrade.returncode
    else:
        print("unknown install mode; can't auto-update.", file=sys.stderr)
        return 1

    # Invalidate banner/tag cache so the new version doesn't keep nagging.
    cache = _cache_read()
    cache.pop("banner_shown_on", None)
    _cache_write(cache)

    if daemon_alive():
        if _prompt_yes("restart the running daemon so it picks up the new code?", default_yes=True, yes=yes):
            restart_daemon()
            print("daemon stopped; it will auto-restart on next `browser-harness` call.")
        else:
            print("daemon left running on old code. run `browser-harness` and it'll use the new code after the daemon recycles.")
    print("update complete.")
    return 0
