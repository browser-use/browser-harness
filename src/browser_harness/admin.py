"""Daemon and cloud-browser management, callable from snippets. Implemented in browser-harness-core."""
import os

from .core import call

NAME = os.environ.get("BU_NAME", "default")


def ensure_daemon(wait=None, name=None, env=None):
    """Idempotent. Self-heals stale daemon, closed Chrome (launches it), cold
    Chrome, and missing Allow on chrome://inspect."""
    call("ensure_daemon", wait=wait, name=name or "", env=env or {})


def require_existing_daemon(name=None):
    """Require a healthy existing daemon without spawning or reconnecting."""
    call("require_existing_daemon", name=name or "")


def daemon_alive(name=None):
    return call("daemon_alive", name=name or "")


def daemon_browser_kind(name=None):
    """'cloud' | 'cdp' | 'local' as self-reported by a live daemon, else None."""
    return call("daemon_browser_kind", name=name or "")


def daemon_browser_ready(name=None):
    """Whether the selected daemon has a healthy attached browser connection."""
    return call("daemon_browser_ready", name=name or "")


def browser_connections():
    """Live browser-harness daemons with healthy CDP browser connections and their attached page."""
    return call("browser_connections")


def active_browser_connections():
    return len(browser_connections())


def restart_daemon(name=None, require_clean=False):
    """Stop the daemon; the next browser-harness call starts a fresh one."""
    call("restart_daemon", name=name or "", require_clean=require_clean)


def stop_remote_daemon(name="remote"):
    """Stop a remote daemon and its Browser Use cloud browser (billing ends, profile state persists)."""
    call("stop_remote_daemon", name=name)


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
    0, false, no, or off to suppress only those display side effects."""
    return call("start_remote_daemon", name=name, profileName=profileName or "", create=create_kwargs)


def list_cloud_profiles():
    """List cloud profiles under the current API key: [{id, name, userId, cookieDomains, lastUsedAt}, ...]."""
    return call("list_cloud_profiles")


def list_local_profiles():
    """Detected local browser profiles on this machine (via `profile-use list --json`)."""
    return call("list_local_profiles")


def sync_local_profile(profile_name, browser=None, cloud_profile_id=None,
                        include_domains=None, exclude_domains=None):
    """Sync a local profile's cookies to a cloud profile via `profile-use sync`. Returns the cloud UUID.

    Pass cloud_profile_id to refresh an existing cloud profile instead of creating one;
    include_domains / exclude_domains scope the cookies (exclude wins on overlap)."""
    return call("sync_local_profile", profile_name=profile_name, browser=browser or "",
                cloud_profile_id=cloud_profile_id or "", include_domains=include_domains or [],
                exclude_domains=exclude_domains or [])
