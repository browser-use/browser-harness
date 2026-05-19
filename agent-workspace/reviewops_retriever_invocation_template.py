#!/usr/bin/env python3
"""Template wrapper for the next ReviewOps/Deep Research retriever invocation.

This wrapper is lifecycle-only: it does not click UI, send prompts, export files,
read browser profiles, or inspect credentials. It preserves the single-retriever
lock and exits only when the retriever status proves all required completion
conditions:

1. status-file status is downloaded/captured (or the supported captured variants),
2. out-file exists and is non-empty,
3. export_identity_guard_enabled is true and export_identity_guard_last_result.accepted is true.

Example shape for the next invocation:

    python agent-workspace/reviewops_retriever_invocation_template.py \
      --status-file "$RUN_DIR/retrieve-status.json" \
      --out-file "$RUN_DIR/deep-research-response.md" \
      --lock-file "$RUN_DIR/.retriever-wrapper.lock" \
      -- python path/to/existing_retriever.py --same --args --as-before

The command after ``--`` is the existing retriever. Use a wrapper-specific lock
file if that existing retriever already takes its own single-retriever lock; do
not point both wrapper and child at the same lock file. This template only
observes its status/output files and stops waiting once identity-guarded
completion is visible, instead of relying solely on an outer Hermes
notify_on_complete wait.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from agent_helpers import (
    read_reviewops_status_file,
    reviewops_download_is_complete,
    reviewops_single_retriever,
    wait_for_reviewops_download,
)


def _complete(status_file: Path, out_file: Path) -> bool:
    status = read_reviewops_status_file(status_file)
    return reviewops_download_is_complete(
        status,
        out_file,
        require_identity_guard_accepted=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--out-file", required=True, type=Path)
    parser.add_argument("--lock-file", type=Path)
    parser.add_argument("--watchdog-timeout", type=float, default=30.0)
    parser.add_argument("--watchdog-interval", type=float, default=1.0)
    parser.add_argument("--stale-lock-after", type=float)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    lock_file = args.lock_file or (args.status_file.parent / ".retriever-wrapper.lock")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command

    with reviewops_single_retriever(lock_file, stale_after=args.stale_lock_after):
        # Fast path: if a prior guarded retriever already completed this run,
        # exit successfully rather than launching a duplicate retrieve/export.
        if _complete(args.status_file, args.out_file):
            return 0

        if not command:
            result = wait_for_reviewops_download(
                args.status_file,
                args.out_file,
                timeout=args.watchdog_timeout,
                interval=args.watchdog_interval,
                require_identity_guard_accepted=True,
            )
            return 0 if result.get("watchdog_status") == "downloaded" else 124

        proc = subprocess.Popen(command)
        try:
            while proc.poll() is None:
                if _complete(args.status_file, args.out_file):
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    return 0
                time.sleep(args.watchdog_interval)

            # A successful child exit is not sufficient for ReviewOps completion:
            # the wrapper exists to require terminal status + non-empty output +
            # accepted identity guard. Fail closed if the child exits without that
            # proof, while preserving non-zero child failures for debugging.
            if _complete(args.status_file, args.out_file):
                return 0
            return int(proc.returncode) if proc.returncode else 124
        finally:
            if proc.poll() is None:
                proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
