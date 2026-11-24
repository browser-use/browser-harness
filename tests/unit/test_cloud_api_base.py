"""Regression tests for the optional Browser Use cloud API base override."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_NAME = "BROWSER_USE_CLOUD_API_BASE"
US_BASE = "https://api.browser-use.com/api/v3"
EU_BASE = "https://api.eu.browser-use.com/api/v4"


def bu_api_at_import(module: str, value: str | None = None) -> str:
    env = os.environ.copy()
    env.pop(ENV_NAME, None)
    if value is not None:
        env[ENV_NAME] = value

    pythonpath = str(ROOT / "src")
    if env.get("PYTHONPATH"):
        pythonpath += os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath

    result = subprocess.run(
        [sys.executable, "-c", f"from browser_harness import {module}; print({module}.BU_API)"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_bu_api_is_read_at_import_for_both_modules():
    for module in ("admin", "daemon"):
        assert bu_api_at_import(module) == US_BASE
        assert bu_api_at_import(module, EU_BASE + "/") == EU_BASE
