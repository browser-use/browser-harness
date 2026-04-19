import argparse
import json
import os
import platform
import shutil
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from admin import daemon_alive, ensure_daemon, restart_daemon
from helpers import INTERNAL, current_tab, ensure_real_tab, js, list_tabs, page_info

REPAIRABLE_ERROR_FRAGMENTS = (
    "no close frame received or sent",
    "stale",
    "connection refused",
    "didn't come up",
    "broken pipe",
)

PHASE_TIMEOUTS = {
    "ensure_daemon": 20.0,
    "ensure_real_tab": 12.0,
    "list_tabs": 5.0,
    "current_tab": 5.0,
    "page_info": 8.0,
    "ready_state": 4.0,
}


class SmokePhaseError(RuntimeError):
    def __init__(self, phase: str, message: str, phase_timings: dict):
        super().__init__(message)
        self.phase = phase
        self.phase_timings = dict(phase_timings or {})


def format_phase_timings(phase_timings: Optional[dict]) -> str:
    items = []
    for name, seconds in (phase_timings or {}).items():
        try:
            items.append(f"{name}:{float(seconds):.3f}s")
        except (TypeError, ValueError):
            items.append(f"{name}:{seconds}")
    return ", ".join(items)


def timed_phase(phase: str, fn, phase_timings: dict):
    timeout = PHASE_TIMEOUTS.get(phase)
    start = time.monotonic()
    timer_supported = sys.platform != "win32" and hasattr(signal, "setitimer") and hasattr(signal, "SIGALRM")
    previous_handler = None

    def _raise_timeout(_signum, _frame):
        raise TimeoutError(f"timed out during {phase} after {timeout:.1f}s")

    if timeout and timer_supported:
        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, _raise_timeout)
        signal.setitimer(signal.ITIMER_REAL, timeout)

    try:
        result = fn()
    except Exception as exc:
        phase_timings[phase] = round(time.monotonic() - start, 3)
        if isinstance(exc, SmokePhaseError):
            raise
        raise SmokePhaseError(phase=phase, message=str(exc), phase_timings=phase_timings) from exc
    finally:
        if timeout and timer_supported:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, previous_handler)

    phase_timings[phase] = round(time.monotonic() - start, 3)
    return result


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def is_repairable_error(message: str) -> bool:
    lowered = (message or "").lower()
    return any(fragment in lowered for fragment in REPAIRABLE_ERROR_FRAGMENTS)


def classify_error_code(message: str) -> str:
    lowered = (message or "").lower()
    if "devtoolsactiveport" in lowered:
        return "BH-ATTACH-001"
    if "opening handshake" in lowered or "click allow" in lowered or "allow in chrome" in lowered:
        return "BH-ATTACH-003"
    if "connection refused" in lowered:
        return "BH-ATTACH-002"
    if "timed out during ensure_daemon" in lowered:
        return "BH-DAEMON-005"
    if "timed out during ensure_real_tab" in lowered or "timed out during list_tabs" in lowered or "timed out during current_tab" in lowered:
        return "BH-ATTACH-005"
    if "timed out during page_info" in lowered:
        return "BH-PAGE-001"
    if "timed out during ready_state" in lowered:
        return "BH-PAGE-002"
    if "didn't come up" in lowered:
        return "BH-DAEMON-002"
    if "no real non-internal browser tab found" in lowered:
        return "BH-TAB-002"
    if "no close frame received or sent" in lowered:
        return "BH-DAEMON-003"
    if "stale" in lowered:
        return "BH-DAEMON-004"
    return "BH-UNKNOWN-001"


def failure_hints(message: str) -> list[str]:
    lowered = (message or "").lower()
    hints = []
    if "devtoolsactiveport" in lowered:
        hints.append("Enable Chrome remote debugging once in chrome://inspect/#remote-debugging for your normal profile.")
    if "no real non-internal browser tab found" in lowered:
        hints.append("Open at least one normal webpage tab; chrome:// pages do not count.")
    if "connection refused" in lowered or "didn't come up" in lowered:
        hints.append("Start Google Chrome and keep your normal profile open, then rerun the smoke test.")
    if "opening handshake" in lowered or "click allow" in lowered or "allow in chrome" in lowered:
        hints.append("Chrome is likely waiting on its remote-debugging Allow prompt; click Allow in Chrome, then rerun.")
    if "timed out during page_info" in lowered or "timed out during ready_state" in lowered:
        hints.append("The browser attached but the post-attach smoke path stalled; inspect /tmp/bu-<lane>.log and rerun on a fresh BU_NAME.")
    if "timed out during ensure_real_tab" in lowered or "timed out during list_tabs" in lowered or "timed out during current_tab" in lowered:
        hints.append("The attach/tab-selection phase stalled; check for Chrome prompts or stale CDP state, then rerun.")
    if "timed out during ensure_daemon" in lowered:
        hints.append("The daemon bootstrap stalled; inspect /tmp/bu-<lane>.log and verify Chrome/CDP is reachable.")
    if "no close frame received or sent" in lowered or "stale" in lowered:
        hints.append("The daemon websocket looks stale; rerun once or use restart_daemon() before retrying.")
    if not hints:
        hints.append("Check /tmp/bu-default.log or rerun with Chrome already open on a normal webpage.")
    return hints


def collect_smoke_details() -> dict:
    phase_timings = {}
    daemon_preexisting = daemon_alive()
    timed_phase("ensure_daemon", lambda: ensure_daemon(wait=20.0), phase_timings)
    selected_tab = timed_phase("ensure_real_tab", ensure_real_tab, phase_timings)
    tabs = timed_phase("list_tabs", lambda: list_tabs(include_chrome=False), phase_timings)
    current = timed_phase("current_tab", current_tab, phase_timings)

    if not tabs and (not current.get("url") or current["url"].startswith(INTERNAL)):
        raise SmokePhaseError(
            phase="tab_validation",
            message="no real non-internal browser tab found; open at least one normal webpage tab",
            phase_timings=phase_timings,
        )

    info = timed_phase("page_info", page_info, phase_timings)
    ready_state = None if "dialog" in info else timed_phase("ready_state", lambda: js("document.readyState"), phase_timings)

    return {
        "status": "pass",
        "error_code": None,
        "host": platform.node(),
        "repo_root": str(repo_root()),
        "command_path": shutil.which("browser-harness"),
        "smoke_command_path": shutil.which("browser-harness-smoke"),
        "bu_name": os.environ.get("BU_NAME", "default"),
        "daemon_preexisting": daemon_preexisting,
        "daemon_running": daemon_alive(),
        "tab_count": len(tabs),
        "selected_tab": selected_tab,
        "current_tab": current,
        "page": info,
        "ready_state": ready_state,
        "phase_timings": phase_timings,
        "repair_attempted": False,
        "repair_trigger": None,
    }


def run_smoke(repair_once: bool = True) -> dict:
    repair_attempted = False
    repair_trigger = None

    for attempt in range(2 if repair_once else 1):
        try:
            result = collect_smoke_details()
            result["repair_attempted"] = repair_attempted
            result["repair_trigger"] = repair_trigger
            return result
        except Exception as exc:
            message = str(exc)
            if attempt == 0 and repair_once and is_repairable_error(message):
                repair_attempted = True
                repair_trigger = message
                restart_daemon()
                time.sleep(1.0)
                continue
            raise

    raise RuntimeError("smoke test exhausted retries")


def make_failure(exc: Exception, repair_attempted: bool = False, repair_trigger: Optional[str] = None) -> dict:
    message = str(exc)
    phase = getattr(exc, "phase", None)
    phase_timings = getattr(exc, "phase_timings", None)
    return {
        "status": "fail",
        "error_code": classify_error_code(message),
        "host": platform.node(),
        "repo_root": str(repo_root()),
        "command_path": shutil.which("browser-harness"),
        "smoke_command_path": shutil.which("browser-harness-smoke"),
        "bu_name": os.environ.get("BU_NAME", "default"),
        "error": message,
        "phase": phase,
        "phase_timings": phase_timings,
        "repair_attempted": repair_attempted,
        "repair_trigger": repair_trigger,
        "hints": failure_hints(message),
    }


def format_text(result: dict) -> str:
    if result.get("status") == "pass":
        current = result.get("current_tab") or {}
        page = result.get("page") or {}
        lines = [
            "PASS browser-harness smoke",
            f"host={result.get('host')}",
            f"bu_name={result.get('bu_name')}",
            f"repo_root={result.get('repo_root')}",
            f"command_path={result.get('command_path')}",
            f"smoke_command_path={result.get('smoke_command_path')}",
            f"daemon_preexisting={result.get('daemon_preexisting')}",
            f"daemon_running={result.get('daemon_running')}",
            f"tab_count={result.get('tab_count')}",
            f"current_title={current.get('title')}",
            f"current_url={current.get('url')}",
            f"page_title={page.get('title')}",
            f"page_url={page.get('url')}",
            f"ready_state={result.get('ready_state')}",
            f"phase_timings={format_phase_timings(result.get('phase_timings'))}",
            f"repair_attempted={result.get('repair_attempted')}",
        ]
        if result.get("repair_trigger"):
            lines.append(f"repair_trigger={result['repair_trigger']}")
        if page.get("dialog"):
            lines.append(f"dialog={json.dumps(page['dialog'], sort_keys=True)}")
        return "\n".join(lines)

    lines = [
        "FAIL browser-harness smoke",
        f"host={result.get('host')}",
        f"bu_name={result.get('bu_name')}",
        f"repo_root={result.get('repo_root')}",
        f"command_path={result.get('command_path')}",
        f"smoke_command_path={result.get('smoke_command_path')}",
        f"error_code={result.get('error_code')}",
        f"phase={result.get('phase')}",
        f"phase_timings={format_phase_timings(result.get('phase_timings'))}",
        f"error={result.get('error')}",
        f"repair_attempted={result.get('repair_attempted')}",
    ]
    if result.get("repair_trigger"):
        lines.append(f"repair_trigger={result['repair_trigger']}")
    for hint in result.get("hints") or []:
        lines.append(f"hint={hint}")
    return "\n".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Read-only browser-harness attach smoke test")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--no-repair", action="store_true", help="Disable the one-time stale-daemon repair retry")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    repair_once = not args.no_repair
    repair_attempted = False
    repair_trigger = None
    try:
        result = run_smoke(repair_once=repair_once)
        output = json.dumps(result, indent=2, sort_keys=True) if args.json else format_text(result)
        print(output)
        return 0
    except Exception as exc:
        if repair_once and is_repairable_error(str(exc)):
            repair_attempted = True
            repair_trigger = str(exc)
        result = make_failure(exc, repair_attempted=repair_attempted, repair_trigger=repair_trigger)
        output = json.dumps(result, indent=2, sort_keys=True) if args.json else format_text(result)
        print(output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
