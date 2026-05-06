import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from . import _ipc as ipc


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
    workspace = Path(os.environ.get("BH_AGENT_WORKSPACE", repo_root / "agent-workspace")).expanduser()
    for p in (repo_root / ".env", workspace / ".env"):
        if not p.exists():
            continue
        _load_env_file(p)


def _load_env_file(p):
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

NAME = os.environ.get("BU_NAME", "default")
BU_API = "https://api.browser-use.com/api/v3"
GH_RELEASES = "https://api.github.com/repos/browser-use/browser-harness/releases/latest"
VERSION_CACHE = Path(tempfile.gettempdir()) / "bu-version-cache.json"
VERSION_CACHE_TTL = 24 * 3600
DOCTOR_TEXT_LIMIT = 140


def _log_tail(name):
    try:
        return ipc.log_path(name or NAME).read_text().strip().splitlines()[-1]
    except (FileNotFoundError, IndexError):
        return None


def _needs_chrome_remote_debugging_prompt(msg):
    """True when Chrome needs the inspect-page permission/profile flow."""
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


def _is_local_chrome_mode(env=None):
    """True when the daemon discovers a local Chrome instead of a remote CDP WS."""
    return not (env or {}).get("BU_CDP_WS") and not os.environ.get("BU_CDP_WS")


def daemon_alive(name=None):
    # Ping handshake (not a bare connect) so a stale .port file + port reuse
    # after a daemon crash doesn't make us mistake an unrelated listener for ours.
    return ipc.ping(name or NAME, timeout=1.0)


def _daemon_endpoint_names():
    # BH_RUNTIME_DIR isolates one daemon per dir → no filename-prefix discovery,
    # just check whether our local endpoint exists. Without BH_RUNTIME_DIR,
    # _RUNTIME is the shared default (`/tmp` etc.) and we glob `bu-*.<suffix>`
    # to find every daemon on the machine.
    suffix = ".port" if ipc.IS_WINDOWS else ".sock"
    if ipc.BH_RUNTIME_DIR:
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


def ensure_daemon(wait=60.0, name=None, env=None):
    """Idempotent. Self-heals stale daemon, cold Chrome, and missing Allow on chrome://inspect."""
    if daemon_alive(name):
        # Stale daemons accept connects AND reply to meta:* (pure Python) even when the
        # CDP WS to Chrome is dead — probe with a real CDP call and require "result".
        # Must go through ipc.connect so this works on Windows (TCP loopback) too;
        # raw AF_UNIX here would fail on every warm call and churn the daemon.
        try:
            s, token = ipc.connect(name or NAME, timeout=3.0)
            resp = ipc.request(s, token, {"method": "Target.getTargets", "params": {}})
            if "result" in resp: return
        except Exception: pass
        restart_daemon(name)

    import subprocess, sys
    local = _is_local_chrome_mode(env)
    for attempt in (0, 1):
        e = {**os.environ, **({"BU_NAME": name} if name else {}), **(env or {})}
        p = subprocess.Popen(
            [sys.executable, "-m", "browser_harness.daemon"],
            env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **ipc.spawn_kwargs(),
        )
        deadline = time.time() + wait
        while time.time() < deadline:
            if daemon_alive(name): return
            if p.poll() is not None: break
            time.sleep(0.2)
        msg = _log_tail(name) or ""
        if local and attempt == 0 and _needs_chrome_remote_debugging_prompt(msg):
            _open_chrome_inspect()
            print('browser-harness: at chrome://inspect/#remote-debugging, tick "Allow remote debugging for this browser instance" and click Allow on the popup that appears', file=sys.stderr)
            restart_daemon(name)
            continue
        raise RuntimeError(msg or f"daemon {name or NAME} didn't come up -- check {ipc.log_path(name or NAME)}")


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
    restart_daemon(name)


def restart_daemon(name=None):
    """Best-effort daemon shutdown + socket/pid cleanup.

    Name is historical: callers typically follow this with another
    `browser-harness` invocation, which auto-spawns a fresh daemon via
    ensure_daemon(). The function itself only stops.

    Identity is verified via ipc.identify() before any process signal, so
    a stale pid file whose number has been reused by an unrelated process
    is never SIGTERM'd. If the daemon is unreachable, we just clean up the
    pid file and socket and return — never escalate to a kill-by-pid-file.
    """
    import signal

    name = name or NAME
    pid_path = str(ipc.pid_path(name))

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
    # Snapshot the daemon's process start-time as a secondary identity check.
    # The IPC socket can disappear before the process exits (e.g. the shutdown
    # path tears down the socket and then waits on a slow remote `stop` PATCH),
    # so identify() going None partway through is not proof of process death.
    # Comparing start-time before SIGTERM lets us recover the original
    # force-kill behavior for slow shutdowns without re-opening the
    # PID-reuse hole — a reused PID would have a different start-time.
    daemon_start = _process_start_time(daemon_pid)

    if daemon_alive:
        try:
            c, token = ipc.connect(name, timeout=5.0)
            ipc.request(c, token, {"meta": "shutdown"})
            c.close()
        except Exception:
            pass

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
    key = os.environ.get("BROWSER_USE_API_KEY")
    if not key:
        raise RuntimeError("BROWSER_USE_API_KEY missing -- see .env.example")
    req = urllib.request.Request(
        f"{BU_API}{path}",
        method=method,
        data=(json.dumps(body).encode() if body is not None else None),
        headers={"X-Browser-Use-API-Key": key, "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")


def _stop_cloud_browser(browser_id):
    if not browser_id:
        return
    try:
        _browser_use(f"/browsers/{browser_id}", "PATCH", {"action": "stop"})
    except BaseException:
        pass


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

    Returns the full browser dict including `liveUrl`. Prints the liveUrl and
    auto-opens it locally when a GUI is detected, so the user can watch along."""
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
    except BaseException:
        _stop_cloud_browser(browser.get("id"))
        raise
    _show_live_url(browser.get("liveUrl"))
    return browser


def list_local_profiles():
    """Detected local browser profiles on this machine. Shells out to `profile-use list --json`.
    Returns [{BrowserName, BrowserPath, ProfileName, ProfilePath, DisplayName}, ...].
    Requires `profile-use` (see interaction-skills/profile-sync.md for install)."""
    import json, shutil, subprocess
    if not shutil.which("profile-use"):
        raise RuntimeError("profile-use not installed -- curl -fsSL https://browser-use.com/profile.sh | sh")
    return json.loads(subprocess.check_output(["profile-use", "list", "--json"], text=True))


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
    import os, re, shutil, subprocess, sys
    if not shutil.which("profile-use"):
        raise RuntimeError("profile-use not installed -- curl -fsSL https://browser-use.com/profile.sh | sh")
    if not os.environ.get("BROWSER_USE_API_KEY"):
        raise RuntimeError("BROWSER_USE_API_KEY missing")
    cmd = ["profile-use", "sync", "--profile", profile_name]
    if browser:
        cmd += ["--browser", browser]
    if cloud_profile_id:
        cmd += ["--cloud-profile-id", cloud_profile_id]
    for d in include_domains or []:
        cmd += ["--domain", d]
    for d in exclude_domains or []:
        cmd += ["--exclude-domain", d]
    r = subprocess.run(cmd, text=True, capture_output=True)
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
    """Return the repo root if this install is an editable git clone, else None."""
    for p in Path(__file__).resolve().parents:
        if (p / ".git").is_dir():
            return p
    return None


def _install_mode():
    """"git" for editable clone, "pypi" for an installed wheel, "unknown" otherwise."""
    if _repo_dir():
        return "git"
    return "pypi" if _version() else "unknown"


def _cache_read():
    try:
        return json.loads(VERSION_CACHE.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _cache_write(data):
    try:
        VERSION_CACHE.write_text(json.dumps(data))
    except OSError:
        pass


def _latest_release_tag(force=False):
    """Return latest release tag from GitHub, or None. Cached for 24h to avoid hammering the API."""
    cache = _cache_read()
    now = time.time()
    if not force and cache.get("tag") and now - cache.get("fetched_at", 0) < VERSION_CACHE_TTL:
        return cache["tag"]
    try:
        req = urllib.request.Request(GH_RELEASES, headers={"Accept": "application/vnd.github+json"})
        tag = json.loads(urllib.request.urlopen(req, timeout=5).read()).get("tag_name") or ""
    except Exception:
        return cache.get("tag")  # fall back to last known
    tag = tag.lstrip("v")
    _cache_write({**cache, "tag": tag, "fetched_at": now})
    return tag or None


def _version_tuple(v):
    """Best-effort semver parse. Non-numeric components sort as 0, so pre-releases may not rank perfectly."""
    parts = []
    for s in (v or "").split("."):
        m = ""
        for ch in s:
            if ch.isdigit():
                m += ch
            else:
                break
        parts.append(int(m) if m else 0)
    return tuple(parts)


def check_for_update():
    """(current, latest, newer_available). latest may be None if the API was unreachable and no cache exists."""
    cur = _version()
    latest = _latest_release_tag()
    newer = bool(cur and latest and _version_tuple(latest) > _version_tuple(cur))
    return cur, latest, newer


def print_update_banner(out=None):
    """Print the update banner to stderr once per day. Silent when up-to-date or offline."""
    import sys
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
            out = subprocess.check_output(["tasklist"], text=True, timeout=5)
            names = ("chrome.exe", "msedge.exe", "helium.exe")
        else:
            out = subprocess.check_output(["ps", "-A", "-o", "comm="], text=True, timeout=5)
            names = ("Google Chrome", "chrome", "chromium", "Microsoft Edge", "msedge", "helium")
        return any(n.lower() in out.lower() for n in names)
    except Exception:
        return False


def _open_chrome_inspect():
    """Open chrome://inspect/#remote-debugging so the user can tick the checkbox."""
    import platform, subprocess, webbrowser
    url = "chrome://inspect/#remote-debugging"
    if platform.system() == "Darwin":
        try:
            subprocess.run([
                "osascript",
                "-e", 'tell application "Google Chrome" to activate',
                "-e", f'tell application "Google Chrome" to open location "{url}"',
            ], timeout=5, check=False)
            return
        except Exception:
            pass
    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass


def run_doctor():
    """Read-only diagnostics. Exit 0 iff everything looks healthy."""
    import platform, shutil, sys
    cur = _version()
    mode = _install_mode()
    chrome = _chrome_running()
    daemon = daemon_alive()
    connections = browser_connections()
    profile_use = shutil.which("profile-use") is not None
    api_key = bool(os.environ.get("BROWSER_USE_API_KEY"))
    latest = _latest_release_tag()
    # Only claim an update when we know the installed version — `cur or "(unknown)"`
    # for display would otherwise be parsed as (0,) and flag every latest as newer.
    newer = bool(cur and latest and _version_tuple(latest) > _version_tuple(cur))
    cur_display = cur or "(unknown)"

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
        print("  latest release    (could not reach github)")
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
    row("profile-use installed", profile_use, "" if profile_use else "optional: curl -fsSL https://browser-use.com/profile.sh | sh")
    row("BROWSER_USE_API_KEY set", api_key, "" if api_key else "optional: needed only for cloud browsers / profile sync")
    # Core health = chrome + daemon. Profile-use/api-key are optional.
    return 0 if (chrome and daemon) else 1


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
        print("could not reach github; will try to update anyway.")

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
            # Fall back to pip in case this wasn't a `uv tool install`.
            pip = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "browser-harness"])
            if pip.returncode != 0:
                return pip.returncode
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
