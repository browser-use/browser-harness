import json
import os
import socket
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def _load_env():
    p = Path(__file__).parent / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

IS_WIN = sys.platform == "win32"
NAME = os.environ.get("BU_NAME", "default")
BU_API = "https://api.browser-use.com/api/v3"


def _tmp(name, suffix):
    # Unix keeps the fixed /tmp/ path so existing users (and macOS AF_UNIX
    # path-length limits) see zero change. Windows has no /tmp, so we fall
    # back to the per-user temp dir.
    n = name or NAME
    if IS_WIN:
        return os.path.join(tempfile.gettempdir(), f"bu-{n}.{suffix}")
    return f"/tmp/bu-{n}.{suffix}"


def _paths(name):
    # On Unix: (sock, pid). On Windows: (port_file, pid) — the port file
    # holds the TCP port the daemon is listening on, since AF_UNIX is
    # unavailable on Windows Python builds.
    return _tmp(name, "port" if IS_WIN else "sock"), _tmp(name, "pid")


def _token(name):
    # Windows TCP loopback IPC requires a shared-secret token on every
    # request. Missing/unreadable token => we can't talk to the daemon.
    if not IS_WIN:
        return None
    return open(_tmp(name, "token")).read().strip()


def _log_tail(name):
    try:
        return Path(_tmp(name, "log")).read_text().strip().splitlines()[-1]
    except (FileNotFoundError, IndexError):
        return None


def _connect(name, timeout=1):
    if IS_WIN:
        port = int(open(_tmp(name, "port")).read().strip())
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("127.0.0.1", port))
    else:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(_tmp(name, "sock"))
    return s


def daemon_alive(name=None):
    # On Windows a stale PORT_FILE can point at a port reused by an
    # unrelated process that happily accepts TCP connects. Send an
    # authenticated ping and require the token-checked {"ok":true}
    # reply before calling the daemon alive.
    try:
        s = _connect(name, timeout=1)
        if IS_WIN:
            s.sendall((json.dumps({"meta": "ping", "token": _token(name)}) + "\n").encode())
            data = b""
            while not data.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk: break
                data += chunk
            s.close()
            return bool(data) and json.loads(data).get("ok") is True
        s.close()
        return True
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout, ValueError, OSError, json.JSONDecodeError):
        return False


def _pid_alive(pid):
    # os.kill(pid, 0) is the POSIX idiom, but on Windows any sig value
    # other than CTRL_C_EVENT/CTRL_BREAK_EVENT unconditionally kills the
    # target via TerminateProcess — we must not send 0. Use OpenProcess
    # with PROCESS_QUERY_LIMITED_INFORMATION (0x1000) for a read-only check.
    if IS_WIN:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if h:
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        # Handle is NULL — distinguish "pid doesn't exist" from "access denied".
        # ERROR_INVALID_PARAMETER (87) means no such pid; anything else (e.g.
        # ERROR_ACCESS_DENIED 5 for a live process in a different token) we
        # conservatively treat as alive so we don't unlink state while the
        # real daemon is still running.
        err = ctypes.windll.kernel32.GetLastError()
        return err != 87
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def ensure_daemon(wait=60.0, name=None, env=None):
    """Idempotent. `env` is merged into the child process env."""
    if daemon_alive(name):
        return
    import subprocess

    e = {**os.environ, **({"BU_NAME": name} if name else {}), **(env or {})}
    kwargs = {}
    if IS_WIN:
        # start_new_session is POSIX-only; on Windows we detach the child
        # via CREATE_NEW_PROCESS_GROUP so it survives the parent exit.
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    p = subprocess.Popen(
        ["uv", "run", "daemon.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=e,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )
    deadline = time.time() + wait
    while time.time() < deadline:
        if daemon_alive(name):
            return
        if p.poll() is not None:
            break
        time.sleep(0.2)
    msg = _log_tail(name)
    raise RuntimeError(msg or f"daemon {name or NAME} didn't come up -- check {_tmp(name, 'log')}")


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
    ensure_daemon(). The function itself only stops."""
    import signal

    ipc_path, pid_path = _paths(name)
    token_path = _tmp(name, "token") if IS_WIN else None
    try:
        s = _connect(name, timeout=5)
        shutdown_req = {"meta": "shutdown"}
        if IS_WIN:
            try:
                shutdown_req["token"] = _token(name)
            except (FileNotFoundError, OSError):
                pass
        s.sendall((json.dumps(shutdown_req) + "\n").encode())
        s.recv(1024)
        s.close()
    except Exception:
        pass
    try:
        pid = int(open(pid_path).read())
    except (FileNotFoundError, ValueError):
        pid = None
    if pid:
        for _ in range(75):
            if not _pid_alive(pid):
                break
            time.sleep(0.2)
        else:
            # On Windows, SIGTERM maps to TerminateProcess — the daemon's
            # `finally` (which calls stop_remote() and unlinks PID/PORT)
            # would not run. Send CTRL_BREAK_EVENT instead; because the
            # daemon was spawned with CREATE_NEW_PROCESS_GROUP, it's the
            # leader of its own group and will receive the break as a
            # KeyboardInterrupt, letting its finally block execute.
            sig = signal.CTRL_BREAK_EVENT if IS_WIN else signal.SIGTERM
            try:
                os.kill(pid, sig)
            except (OSError, ProcessLookupError):
                pass
            # Give the daemon a second chance to exit after the signal;
            # its finally block will unlink its own state files.
            for _ in range(75):
                if not _pid_alive(pid):
                    break
                time.sleep(0.2)
    # Only unlink state files when no live daemon still holds them. If we
    # couldn't confirm the pid is gone, leave the files so ensure_daemon()
    # won't race and spawn a duplicate alongside a still-running daemon.
    if pid is None or not _pid_alive(pid):
        for f in (ipc_path, pid_path) + ((token_path,) if IS_WIN else ()):
            try:
                os.unlink(f)
            except (FileNotFoundError, TypeError):
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
    ensure_daemon(
        name=name,
        env={"BU_CDP_WS": _cdp_ws_from_url(browser["cdpUrl"]), "BU_BROWSER_ID": browser["id"]},
    )
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

    Shells out to `profile-use sync` (v1.0.4+). Requires BROWSER_USE_API_KEY and the
    target local Chrome profile to be closed (profile-use needs an exclusive lock on
    the Cookies DB).

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
