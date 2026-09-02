---
title: Fix --update crash when uv is missing - Plan
type: fix
date: 2026-09-01
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

## Goal Capsule

- **Objective:** `browser-harness --update` exits with a clear, actionable error message when the package was installed from PyPI and `uv` is not on PATH, instead of crashing with `FileNotFoundError`.
- **Means:** Detect `uv` availability before invoking it and report the missing prerequisite (KTD1).
- **Stop conditions:** The update path reports the missing-uv case cleanly, existing update paths keep working, and the unit suite passes.

## Product Contract

### Summary

`run_update()` in `src/browser_harness/admin.py` upgrades a PyPI-installed `browser-harness` by shelling out to `uv tool upgrade browser-harness` with no availability check. On a machine without `uv`, `subprocess.run` raises `FileNotFoundError`, which escapes as a traceback. The fix adds a `shutil.which("uv")` guard that prints an actionable message and returns a non-zero exit code.

### Problem Frame

The PyPI install path already has an "unknown install mode" error branch, but the `pypi` branch assumes `uv` exists. `uv` is the recommended install tool but not universal — users may have used `pip` or `pipx`. The crash is a poor UX regression for those users.

### Requirements

- R1. When install mode is `pypi` and `uv` is not on PATH, `--update` prints a clear error telling the user `uv` is required to auto-update, and exits non-zero.
- R2. When install mode is `pypi` and `uv` is present, `--update` keeps the existing `uv tool upgrade browser-harness` behavior.
- R3. The `git` and `unknown` install-mode paths are unchanged.

## Planning Contract

### Key Technical Decisions

- KTD1. Use `shutil.which("uv")` to detect `uv` before the `pypi` upgrade branch. Rationale: `shutil.which` is the existing convention in this file (used at `admin.py:748, 773, 1021`), and it is dependency-free.

### Assumptions

- A. A user on the `pypi` path without `uv` is expected to upgrade via `pip`/`pipx`/their package manager manually; `--update` only needs to say so.

### Sequencing

- U1 is the only unit; no dependencies.

### Deferred to Follow-Up Work

- The uv-present-but-not-uv-managed case: a pip/pipx-installed package on a machine where `uv` happens to be on PATH still gets uv's raw "not installed via uv" error from `uv tool upgrade`. Out of scope for this fix (R2 preserves existing behavior), but the same population the Problem Frame names would benefit from an actionable error there too.

## Implementation Units

### U1. Guard the uv upgrade path in run_update

- **Goal:** `--update` fails cleanly with an actionable message when `uv` is absent, and behaves identically when `uv` is present.
- **Requirements:** R1, R2, R3
- **Files:**
  - `src/browser_harness/admin.py`
  - `tests/unit/test_admin.py`
- **Approach:**
  1. In the `elif mode == "pypi":` branch of `run_update()`, before the `subprocess.run(["uv", ...])` call, check `shutil.which("uv")`.
  2. When `uv` is missing, print an error to stderr naming the missing prerequisite and pointing at the manual upgrade route for the tool the user installed with (`pip install --upgrade browser-harness`, `pipx upgrade browser-harness`, or their package manager), then `return 1`.
  3. Keep the existing `subprocess.run` call in the `uv`-present case.
- **Patterns to follow:** The `shutil.which` guard pattern at `admin.py:748` and `admin.py:773`; the stderr + non-zero exit convention in the `git status failed` branch at `admin.py:1219-1221`.
- **Test scenarios:**
  - Happy path: `run_update` with `_install_mode()` returning `"pypi"`, `shutil.which("uv")` returning a path, and a mocked `subprocess.run` returning returncode 0 → exits 0, calls `subprocess.run` with `["uv", "tool", "upgrade", "browser-harness"]`.
  - Error path: `_install_mode()` returns `"pypi"` and `shutil.which("uv")` returns `None` → exits 1, prints a message containing `uv` to stderr, and never calls `subprocess.run`.
  - Regression: `_install_mode()` returns `"git"` → the uv guard is not hit; existing git-path behavior is preserved.
  - Regression: `_install_mode()` returns `"unknown"` → existing "unknown install mode" error branch is preserved.
  - Hermeticity: every `run_update` test mocks `check_for_update()` and `daemon_alive()`/`_prompt_yes` so no test hits PyPI over the network or restarts a live daemon — matching the existing suite convention at `tests/unit/test_admin.py` (network is treated as a failure).
- **Verification:** `uv run --with pytest python -m pytest tests/unit/test_admin.py -q` passes, including the new scenarios; the full unit suite still passes.

## Verification Contract

- Run `uv run --with pytest python -m pytest tests/unit -q` from the repo root. All tests pass.
- No live browser or network is required.

## Definition of Done

- The `pypi`-mode missing-`uv` case produces a clear stderr message and exit code 1, with no `FileNotFoundError` traceback.
- The `pypi`-mode `uv`-present case still runs `uv tool upgrade browser-harness`.
- New unit tests cover the missing-uv and uv-present branches.
- The full unit suite passes.
- Cleanup: no dead-end code or stray files remain in the diff.
