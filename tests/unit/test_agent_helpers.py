import json
import os
import sys
import time
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
AGENT_HELPERS = ROOT / "agent-workspace" / "agent_helpers.py"
REVIEWOPS_TEMPLATE = ROOT / "agent-workspace" / "reviewops_retriever_invocation_template.py"


def load_agent_helpers():
    spec = importlib.util.spec_from_file_location("agent_helpers_under_test", AGENT_HELPERS)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_reviewops_template():
    sys.path.insert(0, str(REVIEWOPS_TEMPLATE.parent))
    try:
        spec = importlib.util.spec_from_file_location("reviewops_template_under_test", REVIEWOPS_TEMPLATE)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(REVIEWOPS_TEMPLATE.parent))


def test_reviewops_download_is_complete_requires_terminal_status_and_output(tmp_path):
    h = load_agent_helpers()
    out = tmp_path / "response.md"
    out.write_text("ok", encoding="utf-8")

    assert h.reviewops_download_is_complete({"status": "downloaded", "output_file": str(out)}) is True
    assert h.reviewops_download_is_complete({"status": "watching", "output_file": str(out)}) is False
    assert h.reviewops_download_is_complete({"status": "downloaded", "output_file": str(tmp_path / "missing.md")}) is False


def test_reviewops_download_respects_enabled_identity_guard(tmp_path):
    h = load_agent_helpers()
    out = tmp_path / "response.md"
    out.write_text("ok", encoding="utf-8")

    rejected = {
        "status": "downloaded",
        "output_file": str(out),
        "export_identity_guard_enabled": True,
        "export_identity_guard_last_result": {"accepted": False, "reason": "rejected-heading:B3a"},
    }
    assert h.reviewops_download_is_complete(rejected) is False

    accepted = {
        "status": "downloaded",
        "output_file": str(out),
        "export_identity_guard_enabled": True,
        "export_identity_guard_last_result": {"accepted": True},
    }
    assert h.reviewops_download_is_complete(accepted) is True


def test_reviewops_download_template_mode_requires_accepted_identity_guard(tmp_path):
    h = load_agent_helpers()
    out = tmp_path / "response.md"
    out.write_text("ok", encoding="utf-8")

    missing_guard = {"status": "captured", "output_file": str(out)}
    disabled_guard = {
        "status": "captured",
        "output_file": str(out),
        "export_identity_guard_enabled": False,
        "export_identity_guard_last_result": {"accepted": True},
    }
    assert (
        h.reviewops_download_is_complete(
            missing_guard,
            require_identity_guard_accepted=True,
        )
        is False
    )
    assert (
        h.reviewops_download_is_complete(
            disabled_guard,
            require_identity_guard_accepted=True,
        )
        is False
    )

    accepted = {
        "status": "captured",
        "output_file": str(out),
        "export_identity_guard_enabled": True,
        "export_identity_guard_last_result": {"accepted": True},
    }
    assert (
        h.reviewops_download_is_complete(
            accepted,
            require_identity_guard_accepted=True,
        )
        is True
    )


def test_exit_if_reviewops_downloaded_raises_system_exit_only_when_complete(tmp_path):
    h = load_agent_helpers()
    status_file = tmp_path / "status.json"
    out = tmp_path / "response.md"

    status_file.write_text(json.dumps({"status": "downloaded", "output_file": str(out)}), encoding="utf-8")
    h.exit_if_reviewops_downloaded(status_file)  # no output file yet: do not exit

    out.write_text("ok", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        h.exit_if_reviewops_downloaded(status_file)
    assert exc.value.code == 0


def test_wait_for_reviewops_download_returns_immediately_when_status_and_output_exist(tmp_path):
    h = load_agent_helpers()
    status_file = tmp_path / "status.json"
    out = tmp_path / "response.md"
    out.write_text("ok", encoding="utf-8")
    status_file.write_text(json.dumps({"status": "downloaded", "output_file": str(out)}), encoding="utf-8")

    result = h.wait_for_reviewops_download(status_file, timeout=5, interval=0.01)

    assert result["status"] == "downloaded"
    assert result["watchdog_status"] == "downloaded"


def test_wait_for_reviewops_download_template_mode_waits_for_identity_acceptance(tmp_path):
    h = load_agent_helpers()
    status_file = tmp_path / "status.json"
    out = tmp_path / "response.md"
    out.write_text("ok", encoding="utf-8")
    status_file.write_text(
        json.dumps({"status": "captured", "output_file": str(out)}),
        encoding="utf-8",
    )

    result = h.wait_for_reviewops_download(
        status_file,
        timeout=0.01,
        interval=0.01,
        require_identity_guard_accepted=True,
    )

    assert result["status"] == "captured"
    assert result["watchdog_status"] == "timeout"

    status_file.write_text(
        json.dumps(
            {
                "status": "captured",
                "output_file": str(out),
                "export_identity_guard_enabled": True,
                "export_identity_guard_last_result": {"accepted": True},
            }
        ),
        encoding="utf-8",
    )

    result = h.wait_for_reviewops_download(
        status_file,
        timeout=5,
        interval=0.01,
        require_identity_guard_accepted=True,
    )

    assert result["status"] == "captured"
    assert result["watchdog_status"] == "downloaded"


def test_wait_for_reviewops_download_times_out_without_side_effects(tmp_path):
    h = load_agent_helpers()
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({"status": "watching"}), encoding="utf-8")

    result = h.wait_for_reviewops_download(status_file, timeout=0.01, interval=0.01)

    assert result["status"] == "watching"
    assert result["watchdog_status"] == "timeout"
    assert result["status_file"] == str(status_file)


def test_reviewops_invocation_template_no_command_requires_identity_guard(tmp_path):
    template = load_reviewops_template()
    status_file = tmp_path / "status.json"
    out = tmp_path / "response.md"
    out.write_text("ok", encoding="utf-8")
    status_file.write_text(json.dumps({"status": "captured", "output_file": str(out)}), encoding="utf-8")

    code = template.main(
        [
            "--status-file",
            str(status_file),
            "--out-file",
            str(out),
            "--watchdog-timeout",
            "0.01",
            "--watchdog-interval",
            "0.01",
        ]
    )
    assert code == 124

    status_file.write_text(
        json.dumps(
            {
                "status": "captured",
                "output_file": str(out),
                "export_identity_guard_enabled": True,
                "export_identity_guard_last_result": {"accepted": True},
            }
        ),
        encoding="utf-8",
    )

    code = template.main(
        [
            "--status-file",
            str(status_file),
            "--out-file",
            str(out),
            "--watchdog-timeout",
            "5",
            "--watchdog-interval",
            "0.01",
        ]
    )
    assert code == 0


def test_reviewops_invocation_template_command_success_without_guard_fails_closed(tmp_path):
    template = load_reviewops_template()
    status_file = tmp_path / "status.json"
    out = tmp_path / "response.md"
    out.write_text("ok", encoding="utf-8")
    status_file.write_text(json.dumps({"status": "captured", "output_file": str(out)}), encoding="utf-8")

    code = template.main(
        [
            "--status-file",
            str(status_file),
            "--out-file",
            str(out),
            "--",
            sys.executable,
            "-c",
            "import sys; sys.exit(0)",
        ]
    )

    assert code == 124


def test_reviewops_single_retriever_lock_rejects_duplicate(tmp_path):
    h = load_agent_helpers()
    lock_file = tmp_path / "retriever.lock"

    with h.reviewops_single_retriever(lock_file):
        assert lock_file.exists()
        with pytest.raises(h.ReviewOpsRetrieverLockError):
            with h.reviewops_single_retriever(lock_file):
                pass

    assert not lock_file.exists()


def test_reviewops_single_retriever_lock_can_break_stale_lock(tmp_path):
    h = load_agent_helpers()
    lock_file = tmp_path / "retriever.lock"
    lock_file.write_text("stale", encoding="utf-8")
    old = time.time() - 120
    os.utime(lock_file, (old, old))

    with h.reviewops_single_retriever(lock_file, stale_after=1):
        payload = json.loads(lock_file.read_text(encoding="utf-8"))
        assert payload["pid"] == os.getpid()
        assert payload["argv_redacted"] is True
        assert "argv" not in payload
