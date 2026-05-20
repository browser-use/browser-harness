"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""

from __future__ import annotations

import json as _json
import os as _os
import time as _time
from contextlib import contextmanager as _contextmanager
from pathlib import Path as _Path
from typing import Any as _Any


REVIEWOPS_TERMINAL_DOWNLOAD_STATUSES = frozenset(
    {
        "captured",
        "downloaded",
        "captured_markdown_export",
        "captured_native_markdown",
    }
)


class ReviewOpsRetrieverLockError(RuntimeError):
    """Raised when another guarded ReviewOps retriever already owns the run lock."""


class ReviewOpsRetrieverLock:
    """Small atomic lock for one retriever per run directory.

    This deliberately does not send prompts or click UI. It only prevents a second
    retrieval worker from running the same loop concurrently, preserving the
    single-retriever / no-duplicate-send guard used by ReviewOps scripts.
    """

    def __init__(self, path: str | _os.PathLike[str], *, stale_after: float | None = None):
        self.path = _Path(path)
        self.stale_after = stale_after
        self.acquired = False

    def acquire(self) -> "ReviewOpsRetrieverLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY
        payload = {
            "pid": _os.getpid(),
            "created_at": _time.time(),
            "argv_redacted": True,
        }
        try:
            fd = _os.open(self.path, flags)
        except FileExistsError as exc:
            if self._break_stale_lock():
                return self.acquire()
            raise ReviewOpsRetrieverLockError(
                f"retriever lock already exists: {self.path}"
            ) from exc
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        self.acquired = True
        return self

    def _break_stale_lock(self) -> bool:
        if self.stale_after is None:
            return False
        try:
            age = _time.time() - self.path.stat().st_mtime
        except OSError:
            return False
        if age < self.stale_after:
            return False
        try:
            self.path.unlink()
            return True
        except OSError:
            return False

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        finally:
            self.acquired = False

    def __enter__(self) -> "ReviewOpsRetrieverLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


@_contextmanager
def reviewops_single_retriever(lock_file: str | _os.PathLike[str], *, stale_after: float | None = None):
    """Context manager enforcing one guarded ReviewOps retriever at a time."""

    lock = ReviewOpsRetrieverLock(lock_file, stale_after=stale_after)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()


def read_reviewops_status_file(status_file: str | _os.PathLike[str]) -> dict[str, _Any] | None:
    """Read a JSON ReviewOps status file, returning None while it is absent/partial.

    Background retrievers can update a status file while a watcher polls it; this
    helper treats FileNotFoundError and JSONDecodeError as transient states instead
    of crashing the watchdog.
    """

    path = _Path(status_file)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        value = _json.loads(text)
    except _json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    return value


def _status_output_path(status: dict[str, _Any], explicit_output: str | _os.PathLike[str] | None) -> _Path | None:
    if explicit_output is not None:
        return _Path(explicit_output)
    for key in ("output_file", "out_file", "path"):
        value = status.get(key)
        if value:
            return _Path(str(value))
    return None


def _identity_guard_allows_completion(
    status: dict[str, _Any], *, require_accepted: bool = False
) -> bool:
    """Return False when a reported identity guard exists but did not accept.

    Older/local retrievers may not write identity-guard fields; those remain
    caller-governed by default. For ReviewOps invocation templates that must prove
    the current response before exiting, pass ``require_accepted=True`` so missing
    or disabled identity-guard evidence fails closed too. If the fields are
    present, the watchdog must not turn a stale or rejected export into a
    successful completion merely because a file exists.
    """

    result = status.get("export_identity_guard_last_result")
    accepted = isinstance(result, dict) and result.get("accepted") is True
    guard_enabled = status.get("export_identity_guard_enabled") is True
    if require_accepted:
        return guard_enabled and accepted
    if not guard_enabled:
        return True
    return accepted


def reviewops_download_is_complete(
    status: dict[str, _Any] | None,
    out_file: str | _os.PathLike[str] | None = None,
    *,
    terminal_statuses=REVIEWOPS_TERMINAL_DOWNLOAD_STATUSES,
    min_bytes: int = 1,
    require_identity_guard_accepted: bool = False,
) -> bool:
    """True only when status says downloaded/captured and the output file exists.

    This is intentionally narrow. It does not click, export, send, or bypass
    current-response identity checks. If the status file reports an enabled
    identity guard, completion is allowed only when that guard accepted. Pass
    ``require_identity_guard_accepted=True`` from ReviewOps retriever invocation
    templates so completion requires all three conditions: terminal
    downloaded/captured status, non-empty output file, and accepted identity guard.
    """

    if not status:
        return False
    if str(status.get("status", "")).strip() not in set(terminal_statuses):
        return False
    if not _identity_guard_allows_completion(
        status, require_accepted=require_identity_guard_accepted
    ):
        return False
    output = _status_output_path(status, out_file)
    if output is None:
        return False
    try:
        return output.is_file() and output.stat().st_size >= min_bytes
    except OSError:
        return False


def wait_for_reviewops_download(
    status_file: str | _os.PathLike[str],
    out_file: str | _os.PathLike[str] | None = None,
    *,
    timeout: float = 30.0,
    interval: float = 1.0,
    terminal_statuses=REVIEWOPS_TERMINAL_DOWNLOAD_STATUSES,
    min_bytes: int = 1,
    require_identity_guard_accepted: bool = False,
) -> dict[str, _Any]:
    """Short-poll a retriever status file until download completion or timeout.

    Use this as an outer watchdog around long-running ReviewOps/Deep Research
    retrievers. If the retriever writes `status: downloaded` (or a compatible
    captured status) and the output file exists, this returns immediately so the
    parent process can exit 0 and Hermes `notify_on_complete` fires. On timeout it
    returns the last status dict with `watchdog_status: timeout` and does not click
    or send anything. New ReviewOps invocation templates should pass
    ``require_identity_guard_accepted=True`` so this exits only after the stale
    export/current-response identity guard has accepted the output.
    """

    deadline = _time.time() + timeout
    last_status: dict[str, _Any] | None = None
    while _time.time() < deadline:
        last_status = read_reviewops_status_file(status_file)
        if reviewops_download_is_complete(
            last_status,
            out_file,
            terminal_statuses=terminal_statuses,
            min_bytes=min_bytes,
            require_identity_guard_accepted=require_identity_guard_accepted,
        ):
            result = dict(last_status or {})
            result["watchdog_status"] = "downloaded"
            return result
        _time.sleep(interval)
    result = dict(last_status or {})
    result.setdefault("status", "unknown")
    result["watchdog_status"] = "timeout"
    result["status_file"] = str(status_file)
    output = _status_output_path(result, out_file)
    if output is not None:
        result["output_file"] = str(output)
    return result


def exit_if_reviewops_downloaded(
    status_file: str | _os.PathLike[str],
    out_file: str | _os.PathLike[str] | None = None,
    *,
    code: int = 0,
    require_identity_guard_accepted: bool = False,
) -> None:
    """Exit the current retriever once status/output prove the download is done.

    Drop this near the top of a retriever loop after the identity/stale-export
    guards have written a terminal status. It fixes the lifecycle bug where the
    status file says downloaded and the output exists, but a background process
    keeps polling forever. New ReviewOps invocation templates should pass
    ``require_identity_guard_accepted=True`` and call this after the identity/stale
    guard status has been updated.
    """

    status = read_reviewops_status_file(status_file)
    if reviewops_download_is_complete(
        status,
        out_file,
        require_identity_guard_accepted=require_identity_guard_accepted,
    ):
        raise SystemExit(code)
