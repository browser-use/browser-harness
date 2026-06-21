"""Model-visible browser lifecycle helpers."""
from __future__ import annotations

from . import context
from . import local_profiles
from . import manager_client


def browser_status(browser_id=None):
    """Return lifecycle state for a browser id, or manager guidance if omitted."""
    return manager_client.status(browser_id)


def browser_profiles(verbose=False):
    """List local Chrome/Chromium profiles for browser_use_profile(...)."""
    return local_profiles.list_browser_profiles_payload(verbose=verbose)


def browser_use_profile(profile_id):
    """Select the local browser profile future normal helper calls should use."""
    return local_profiles.use_browser_profile(profile_id)


def _manager_backend(kind, backend=None):
    value = backend if backend is not None else kind
    if value in (None, "private", "managed"):
        return "managed"
    if value == "cloud":
        return "cloud"
    raise ValueError("browser_new kind must be 'private' or 'cloud'")


def browser_new(kind="private", *, backend=None, profile="clean", proxy_country=None, reason=None):
    """Create a managed browser and return its short id."""
    resp = manager_client.new_browser(
        backend=_manager_backend(kind, backend),
        profile=profile,
        proxy_country=proxy_country,
        reason=reason,
    )
    return manager_client.public_state(resp)


def browser(browser_id):
    """Select a managed browser id for this Python script."""
    resp = manager_client.switch_browser(browser_id)
    binding = manager_client.binding_from_response(resp)
    context.activate_binding(binding)
    return manager_client.public_state(resp)


def browser_switch(browser_id):
    """Compatibility alias for browser(id)."""
    return browser(browser_id)


def browser_list():
    """List concise browser ids known to the manager."""
    return manager_client.list_browsers()


def browser_close(browser_id=None):
    """Close a browser by explicit id."""
    if not browser_id:
        raise ValueError("browser_close(id) requires a browser id")
    active = context.get_active_binding()
    closing_active = active and active.browser_id == browser_id
    resp = manager_client.close_browser(browser_id)
    if closing_active:
        context.clear_active_binding()
    return manager_client.public_state(resp)


def browser_close_owned():
    """Close managed browsers created by this agent identity."""
    active = context.get_active_binding()
    resp = manager_client.close_owned_browsers()
    if active and active.browser_id in set(resp.get("closed") or []):
        context.clear_active_binding()
    return manager_client.public_state(resp)
