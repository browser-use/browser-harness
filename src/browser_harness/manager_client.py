"""Client for the browser-harness manager."""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

from . import context, manager_runtime


class ManagerError(RuntimeError):
    def __init__(self, response):
        self.response = response if isinstance(response, dict) else {"reason": str(response)}
        reason = self.response.get("reason") or self.response.get("error") or self.response.get("state") or "manager error"
        super().__init__(reason)


_manager_started = False
_CLIENT_ID = f"{os.getpid()}_{secrets.token_hex(4)}"


def default_manager_root() -> str:
    return str(manager_runtime.default_root())


def default_manager_socket() -> str:
    return str(manager_runtime.default_endpoint(Path(default_manager_root())))


def manager_socket() -> str:
    path = default_manager_socket()
    os.environ.setdefault("BH_MANAGER_SOCKET", path)
    os.environ.setdefault("BH_MANAGER_ROOT", default_manager_root())
    ensure_manager_running(path)
    return path


def ensure_manager_running(path: str | None = None) -> None:
    global _manager_started
    path = path or default_manager_socket()
    endpoint = Path(path)
    if _manager_socket_alive(endpoint):
        return
    root = Path(os.environ.get("BH_MANAGER_ROOT") or default_manager_root())
    manager_runtime.ensure_private_dir(root)
    with manager_runtime.start_lock(root):
        if _manager_socket_alive(endpoint):
            return
        log = manager_runtime.open_private_append(root / "manager.log")
        env = {**os.environ, "BH_MANAGER_SOCKET": path, "BH_MANAGER_ROOT": str(root)}
        try:
            subprocess.Popen(
                [sys.executable, "-m", "browser_harness.manager_daemon", "--socket", path, "--root", str(root)],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                env=env,
                **manager_runtime.spawn_kwargs(),
            )
        finally:
            log.close()
        _manager_started = True
        deadline = time.time() + float(os.environ.get("BH_MANAGER_START_TIMEOUT", "10"))
        while time.time() < deadline:
            if _manager_socket_alive(endpoint):
                return
            time.sleep(0.05)
        raise ManagerError({"state": "manager-unavailable", "reason": f"manager did not start at {path}"})


def _manager_socket_alive(path: Path) -> bool:
    if manager_runtime.ping(path, timeout=0.2):
        return True
    if manager_runtime.IS_WINDOWS:
        return False
    try:
        sock, _token = manager_runtime.connect(path, timeout=0.2)
    except OSError:
        return False
    try:
        sock.close()
    except OSError:
        pass
    return True


def request(op: str, **payload) -> dict:
    req = {"op": op, **context.agent_identity().payload(), "client_id": _CLIENT_ID, **payload}
    path = manager_socket()
    sock, token = manager_runtime.connect(Path(path), timeout=float(os.environ.get("BH_MANAGER_TIMEOUT", "30")))
    try:
        resp = manager_runtime.send_request(sock, token, req)
    finally:
        sock.close()
    if not isinstance(resp, dict):
        raise ManagerError({"state": "bad-response", "reason": "manager returned non-object JSON"})
    if resp.get("ok") is False:
        raise ManagerError(resp)
    return resp


def public_state(resp: dict) -> dict:
    return {k: v for k, v in resp.items() if k not in {"binding", "ok"}}


def binding_from_response(resp: dict) -> context.BrowserBinding:
    binding = resp.get("binding")
    if not isinstance(binding, dict):
        raise ManagerError({"state": "bad-response", "reason": "manager response missing binding"})
    return context.BrowserBinding.from_manager(binding)


def status(browser_id: str | None = None) -> dict:
    try:
        return public_state(request("status", browser_id=browser_id))
    except ManagerError as e:
        if e.response.get("state") == "manager-unavailable":
            return {"ready": False, "state": "manager-unavailable", "reason": str(e), "safe_actions": []}
        raise


def list_browsers() -> list[dict]:
    resp = request("list")
    browsers = resp.get("browsers", [])
    if not isinstance(browsers, list):
        raise ManagerError({"state": "bad-response", "reason": "manager list response missing browsers"})
    return browsers


def new_browser(backend="managed", *, profile="clean", proxy_country=None, reason=None) -> dict:
    return request(
        "new",
        backend=backend,
        profile=profile,
        proxy_country=proxy_country,
        reason=reason,
    )


def switch_browser(browser_id: str) -> dict:
    return request("switch", browser_id=browser_id)


def close_browser(browser_id: str | None = None) -> dict:
    return request("close", browser_id=browser_id)


def close_owned_browsers() -> dict:
    return request("close_owned")
