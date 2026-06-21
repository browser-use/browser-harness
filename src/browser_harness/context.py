"""Runtime browser binding state for manager mode.

Legacy browser-harness is environment-driven: BU_NAME, BH_RUNTIME_DIR, and
BH_TMP_DIR are read when modules import. Manager mode needs the active browser
binding to change inside one Python process, so helpers resolve this context at
call time.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import tempfile
from pathlib import Path


@dataclass(frozen=True)
class AgentIdentity:
    run_id: str | None
    agent_id: str | None

    @property
    def degraded(self) -> bool:
        return not (self.run_id and self.agent_id)

    def payload(self) -> dict:
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "identity_degraded": self.degraded,
        }


@dataclass(frozen=True)
class BrowserBinding:
    browser_id: str | None
    bu_name: str
    runtime_dir: Path | None = None
    tmp_dir: Path | None = None
    download_dir: Path | None = None
    artifact_dir: Path | None = None
    cdp_url: str | None = None
    cdp_ws: str | None = None
    manager_mode: bool = False

    @classmethod
    def from_manager(cls, data: dict) -> "BrowserBinding":
        return cls(
            browser_id=data.get("browser_id"),
            bu_name=data["bu_name"],
            runtime_dir=_path_or_none(data.get("runtime_dir")),
            tmp_dir=_path_or_none(data.get("tmp_dir")),
            download_dir=_path_or_none(data.get("download_dir")),
            artifact_dir=_path_or_none(data.get("artifact_dir")),
            cdp_url=data.get("cdp_url"),
            cdp_ws=data.get("cdp_ws"),
            manager_mode=True,
        )

    def daemon_env(self) -> dict[str, str]:
        env = {"BU_NAME": self.bu_name}
        if self.runtime_dir is not None:
            env["BH_RUNTIME_DIR"] = str(self.runtime_dir)
        if self.tmp_dir is not None:
            env["BH_TMP_DIR"] = str(self.tmp_dir)
        if self.cdp_url:
            env["BU_CDP_URL"] = self.cdp_url
        if self.cdp_ws:
            env["BU_CDP_WS"] = self.cdp_ws
        return env


def _path_or_none(value) -> Path | None:
    return Path(value) if value else None


def manager_enabled() -> bool:
    return os.environ.get("BH_MANAGER_MODE") == "1" or bool(os.environ.get("BH_MANAGER_SOCKET"))


def agent_identity() -> AgentIdentity:
    run_id = (
        os.environ.get("BH_RUN_ID")
        or os.environ.get("CODEX_THREAD_ID")
        or os.environ.get("CODEX_SESSION_ID")
        or _cwd_run_id()
    )
    agent_id = (
        os.environ.get("BH_AGENT_ID")
        or os.environ.get("CODEX_AGENT_ID")
        or os.environ.get("CODEX_SUBAGENT_ID")
        or "main"
    )
    return AgentIdentity(run_id=run_id, agent_id=agent_id)


def _cwd_run_id() -> str:
    raw = f"{os.environ.get('USER') or ''}:{Path.cwd()}"
    return "cwd-" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def default_binding_from_env() -> BrowserBinding:
    tmp_dir = _path_or_none(os.environ.get("BH_TMP_DIR"))
    runtime_dir = _path_or_none(os.environ.get("BH_RUNTIME_DIR")) or tmp_dir
    return BrowserBinding(
        browser_id=os.environ.get("BH_BROWSER_ID"),
        bu_name=os.environ.get("BU_NAME", "default"),
        runtime_dir=runtime_dir,
        tmp_dir=tmp_dir,
        cdp_url=os.environ.get("BU_CDP_URL") or None,
        cdp_ws=os.environ.get("BU_CDP_WS") or None,
        manager_mode=manager_enabled(),
    )


_active_binding: BrowserBinding | None = default_binding_from_env()


def get_active_binding() -> BrowserBinding | None:
    return _active_binding


def activate_binding(binding: BrowserBinding) -> None:
    global _active_binding
    _active_binding = binding
    for p in (binding.runtime_dir, binding.tmp_dir, binding.download_dir, binding.artifact_dir):
        if p is not None:
            p.mkdir(parents=True, exist_ok=True)


def clear_active_binding() -> None:
    global _active_binding
    _active_binding = None


def require_active_binding() -> BrowserBinding:
    binding = get_active_binding()
    if binding is None:
        raise RuntimeError('no-browser-selected: call browser("<id>") before page helpers')
    return binding


def active_bu_name() -> str:
    return require_active_binding().bu_name


def active_runtime_dir() -> Path | None:
    binding = get_active_binding()
    return binding.runtime_dir if binding else None


def active_tmp_dir() -> Path | None:
    binding = get_active_binding()
    return binding.tmp_dir if binding else None


def active_artifact_dir() -> Path:
    binding = require_active_binding()
    if binding.artifact_dir is not None:
        binding.artifact_dir.mkdir(parents=True, exist_ok=True)
        return binding.artifact_dir
    if binding.tmp_dir is not None:
        binding.tmp_dir.mkdir(parents=True, exist_ok=True)
        return binding.tmp_dir
    p = Path(tempfile.gettempdir())
    p.mkdir(parents=True, exist_ok=True)
    return p
