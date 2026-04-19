import json
import os
import socket
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

NAME = os.environ.get("BU_NAME", "default")
BU_API = "https://api.browser-use.com/api/v3"


def _paths(name):
    n = name or NAME
    return f"/tmp/bu-{n}.sock", f"/tmp/bu-{n}.pid"


def _log_tail(name):
    p = f"/tmp/bu-{name or NAME}.log"
    try:
        return Path(p).read_text().strip().splitlines()[-1]
    except (FileNotFoundError, IndexError):
        return None


def daemon_alive(name=None):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(_paths(name)[0])
        s.close()
        return True
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout):
        return False


def ensure_daemon(wait=60.0, name=None, env=None):
    """Idempotent. `env` is merged into the child process env."""
    if daemon_alive(name):
        return
    import subprocess

    e = {**os.environ, **({"BU_NAME": name} if name else {}), **(env or {})}
    p = subprocess.Popen(
        ["uv", "run", "daemon.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=e,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.time() + wait
    while time.time() < deadline:
        if daemon_alive(name):
            return
        if p.poll() is not None:
            break
        time.sleep(0.2)
    msg = _log_tail(name)
    raise RuntimeError(msg or f"daemon {name or NAME} didn't come up -- check /tmp/bu-{name or NAME}.log")


def restart_daemon(name=None):
    """Best-effort daemon restart for setup/debug flows."""
    import signal

    sock, pid_path = _paths(name)
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(sock)
        s.sendall(b'{"meta":"shutdown"}\n')
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
            try:
                os.kill(pid, 0)
                time.sleep(0.2)
            except ProcessLookupError:
                break
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for f in (sock, pid_path):
        try:
            os.unlink(f)
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
    detail on a *local* profile before sync: `profile-use inspect --profile <name>`."""
    listing = _browser_use("/profiles?pageSize=200", "GET")
    items = listing.get("items", listing) if isinstance(listing, dict) else listing
    out = []
    for p in items:
        detail = _browser_use(f"/profiles/{p['id']}", "GET")
        out.append({
            "id": detail["id"],
            "name": detail.get("name"),
            "userId": detail.get("userId"),
            "cookieDomains": detail.get("cookieDomains") or [],
            "lastUsedAt": detail.get("lastUsedAt"),
        })
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


def sync_local_profile(profile_name, browser=None):
    """Sync a local profile's cookies into a new cloud profile. Returns the cloud UUID.

    Shells out to `profile-use sync --profile <name> [--browser <browser>]`. Every call
    creates a *new* cloud profile (upstream limitation — see interaction-skills/profile-sync.md).
    Requires BROWSER_USE_API_KEY and that the target local Chrome profile is closed."""
    import os, re, shutil, subprocess, sys
    if not shutil.which("profile-use"):
        raise RuntimeError("profile-use not installed -- curl -fsSL https://browser-use.com/profile.sh | sh")
    if not os.environ.get("BROWSER_USE_API_KEY"):
        raise RuntimeError("BROWSER_USE_API_KEY missing")
    cmd = ["profile-use", "sync", "--profile", profile_name]
    if browser:
        cmd += ["--browser", browser]
    r = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    m = re.search(r"Profile created:\s+([0-9a-f-]{36})", r.stdout)
    if not m:
        raise RuntimeError(f"profile-use did not report a profile UUID (exit {r.returncode})")
    return m.group(1)
